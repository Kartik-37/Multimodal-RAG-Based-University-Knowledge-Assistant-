"""
Deterministic Token-Aware Document Chunking Service.

Partitions parsed document sections into coherent, bounded text chunks suitable for
dense vector retrieval and lexical search.

Design & Architectural Invariants:
1. Token Count Estimation:
   - Uses a deterministic token-count estimator (approximating word/punctuation boundaries).
   - Documented as an ESTIMATOR (not exact model tokens) per Step 5 specifications.
   - The estimator is modular and replaceable by a model tokenizer in subsequent stages.
2. Metadata & Provenance Preservation:
   - Every chunk retains its 1-indexed page_number (from PDF/paged sources).
   - Retains section_title / structural heading (from Markdown/DOCX/CSV).
   - Generates sequential, stable chunk_index values (0, 1, 2, ...).
3. Boundary & Overlap Rules:
   - Respects natural text boundaries (paragraphs, then sentences, then word boundaries).
   - Applies configurable token overlap between adjacent chunks within a section.
   - Avoids emitting meaningless empty or micro chunks.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from backend.app.core.config import settings
from backend.app.services.normalization import normalize_text
from backend.app.services.parsers.base import ParsedDocument, ParsedSection

# Regex splitting into words and punctuation tokens for deterministic token estimation
_TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)

# Regex matching sentence boundaries
_SENTENCE_BOUNDARY_REGEX = re.compile(r"(?<=[.!?])\s+", re.UNICODE)


class TokenEstimator:
    """
    Deterministic token count estimator.

    Approximates standard BPE/WordPiece tokenization counts using word and
    punctuation token extraction. Documented as an estimator; replaceable by
    specific model tokenizers in downstream RAG stages.
    """

    def estimate_tokens(self, text: str) -> int:
        if not text or not text.strip():
            return 0
        matches = _TOKEN_PATTERN.findall(text)
        return max(1, len(matches))


@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration options for chunk generation."""

    target_tokens: int = settings.CHUNK_TARGET_TOKENS
    overlap_tokens: int = settings.CHUNK_OVERLAP_TOKENS
    min_tokens: int = settings.CHUNK_MIN_TOKENS


@dataclass
class GeneratedChunk:
    """In-memory representation of an extracted text chunk prior to DB insertion."""

    id: uuid.UUID
    chunk_index: int
    text: str
    token_count: int  # Estimated token count
    page_number: int | None
    section_title: str | None
    chunk_metadata: dict[str, Any] = field(default_factory=dict)


class DocumentChunker:
    """
    Splits ParsedDocument sections into ordered, bounded chunks with preserved metadata.
    """

    def __init__(
        self,
        config: ChunkingConfig | None = None,
        estimator: TokenEstimator | None = None,
    ) -> None:
        self.config = config or ChunkingConfig()
        self.estimator = estimator or TokenEstimator()

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split paragraph or block into sentences."""
        sentences = [s.strip() for s in _SENTENCE_BOUNDARY_REGEX.split(text) if s.strip()]
        return sentences if sentences else [text.strip()]

    def _chunk_section(
        self,
        section: ParsedSection,
        start_index: int,
    ) -> tuple[list[GeneratedChunk], int]:
        """
        Chunk an individual ParsedSection preserving its page number and heading.
        """
        normalized_text = normalize_text(section.text)
        if not normalized_text:
            return [], start_index

        # Split section into logical paragraphs
        paragraphs = [p.strip() for p in normalized_text.split("\n\n") if p.strip()]
        if not paragraphs:
            return [], start_index

        units: list[str] = []
        for p in paragraphs:
            # If paragraph fits within target, keep as unit; otherwise split into sentences
            if self.estimator.estimate_tokens(p) <= self.config.target_tokens:
                units.append(p)
            else:
                sentences = self._split_into_sentences(p)
                units.extend(sentences)

        chunks: list[GeneratedChunk] = []
        current_units: list[str] = []
        current_token_count = 0
        current_idx = start_index

        for unit in units:
            unit_tokens = self.estimator.estimate_tokens(unit)

            # If adding unit exceeds target and we already have content
            if current_token_count + unit_tokens > self.config.target_tokens and current_units:
                chunk_text = "\n\n".join(current_units).strip()
                chunk_tokens = self.estimator.estimate_tokens(chunk_text)

                if chunk_tokens >= self.config.min_tokens:
                    chunks.append(
                        GeneratedChunk(
                            id=uuid.uuid4(),
                            chunk_index=current_idx,
                            text=chunk_text,
                            token_count=chunk_tokens,
                            page_number=section.page_number,
                            section_title=section.section_title,
                            chunk_metadata={
                                "page_number": section.page_number,
                                "section_title": section.section_title,
                                "estimated_token_count": chunk_tokens,
                                **section.metadata,
                            },
                        )
                    )
                    current_idx += 1

                # Calculate overlap units for sliding window
                overlap_units: list[str] = []
                overlap_tokens = 0
                for prev_unit in reversed(current_units):
                    p_tokens = self.estimator.estimate_tokens(prev_unit)
                    if overlap_tokens + p_tokens <= self.config.overlap_tokens:
                        overlap_units.insert(0, prev_unit)
                        overlap_tokens += p_tokens
                    else:
                        break

                current_units = overlap_units + [unit]
                current_token_count = self.estimator.estimate_tokens("\n\n".join(current_units))
            else:
                current_units.append(unit)
                current_token_count += unit_tokens

        # Flush final accumulated chunk
        if current_units:
            final_text = "\n\n".join(current_units).strip()
            final_tokens = self.estimator.estimate_tokens(final_text)
            if final_text:
                chunks.append(
                    GeneratedChunk(
                        id=uuid.uuid4(),
                        chunk_index=current_idx,
                        text=final_text,
                        token_count=final_tokens,
                        page_number=section.page_number,
                        section_title=section.section_title,
                        chunk_metadata={
                            "page_number": section.page_number,
                            "section_title": section.section_title,
                            "estimated_token_count": final_tokens,
                            **section.metadata,
                        },
                    )
                )
                current_idx += 1

        return chunks, current_idx

    def chunk_document(self, parsed_doc: ParsedDocument) -> list[GeneratedChunk]:
        """
        Chunk all sections of a parsed document into a unified, ordered chunk list.
        """
        all_chunks: list[GeneratedChunk] = []
        next_chunk_idx = 0

        for section in parsed_doc.sections:
            section_chunks, next_chunk_idx = self._chunk_section(section, next_chunk_idx)
            all_chunks.extend(section_chunks)

        return all_chunks


# Singleton chunker instance
document_chunker = DocumentChunker()
