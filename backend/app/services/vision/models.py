"""
Data models and representations for visual PDF evidence extraction and analysis.
Part of Phase 11A: Multimodal RAG MVP for Visual PDF Evidence.
"""

from dataclasses import dataclass, field


@dataclass
class VisualPageCandidate:
    """
    Candidate PDF page identified as containing meaningful visual evidence
    (diagram, chart, figure, or scanned page).
    """

    page_number: int  # 1-indexed page number
    has_images: bool = False
    image_count: int = 0
    image_area_ratio: float = 0.0
    has_vector_drawings: bool = False
    drawing_count: int = 0
    text_char_count: int = 0
    is_sparse_text: bool = False
    reasons: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class VisualAnalysisResult:
    """
    Validated structured outcome of vision-language model analysis for a single visual page.
    """

    visual_type: str  # diagram, chart, table, scanned_page, photograph, flowchart, architecture, other
    summary: str  # Concise factual summary of the visual content and message
    visible_text: list[str] = field(default_factory=list)  # Legible labels, titles, data points, values
    relationships: list[str] = field(default_factory=list)  # Connections, sequences, flows, comparisons
    uncertainties: list[str] = field(default_factory=list)  # Ambiguous, low-confidence, or unreadable elements
    model_name: str = ""
    page_number: int = 1
    raw_response: str | None = None
    error: str | None = None
    is_success: bool = True

    def to_section_text(self) -> str:
        """
        Format the structured visual analysis into rich textual visual evidence suitable
        for standard text embedding, dense vector retrieval, and lexical indexing.
        """
        lines = [
            f"[Visual Content Type]: {self.visual_type.title()}",
            f"[Visual Summary]: {self.summary}",
        ]
        if self.visible_text:
            labels_str = ", ".join(self.visible_text)
            lines.append(f"[Visible Text & Labels]: {labels_str}")
        if self.relationships:
            rel_str = "; ".join(self.relationships)
            lines.append(f"[Key Flows & Relationships]: {rel_str}")
        if self.uncertainties:
            unc_str = "; ".join(self.uncertainties)
            lines.append(f"[Visual Uncertainties]: {unc_str}")
        return "\n".join(lines)


@dataclass
class DocumentVisualSummary:
    """
    Summary of visual processing across an entire document.
    """

    total_pages: int
    visual_pages_detected: int
    visual_pages_processed: int
    results: list[VisualAnalysisResult] = field(default_factory=list)
    skipped_due_to_cap: int = 0
    errors: list[str] = field(default_factory=list)
