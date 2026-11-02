"""
Pydantic schemas for Structured Query Understanding.
Captures semantic intent, entity targets, requested properties, and pre-retrieval routing.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class QueryIntent(str, Enum):
    CONVERSATIONAL = "conversational"
    IDENTITY = "identity"
    GREETING = "greeting"
    HELP = "help"
    DEFINITION = "definition"
    EXPLANATION = "explanation"
    LIST = "list"
    STEPS = "steps"
    COMPARISON = "comparison"
    FACT_LOOKUP = "fact_lookup"
    AMBIGUOUS = "ambiguous"
    OUT_OF_SCOPE = "out_of_scope"
    DOCUMENT_SUMMARY = "document_summary"


class StructuredQuery(BaseModel):
    """
    Structured semantic representation of a user query.
    Preserves original user query immutably while recording intent, target entity, and routing decisions.
    """

    original_query: str = Field(..., description="Exact immutable original user query string.")
    normalized_query: str = Field(..., description="Cleaned, lowercased query string for matching.")
    detected_language: str = Field(default="english", description="Detected language code (e.g. 'english').")
    intent: QueryIntent = Field(..., description="Classified semantic query intent.")
    subject: str = Field(
        default="general",
        description="Core subject or topic (e.g. 'flutter_widget', 'flutter', 'ios_device', 'android_version', 'act_title', 'assistant', 'native_app', 'hybrid_app').",
    )
    requested_property: str = Field(
        default="general",
        description="Specific property or relation requested (e.g. 'definition', 'list', 'categories', 'advantages', 'benefits', 'install_steps', 'comparison', 'title', 'identity').",
    )
    target_entity_type: str | None = Field(
        default=None,
        description="Expected entity type for lists or lookups (e.g. 'widget', 'widget_category', 'device', 'version', 'act', 'app_type', 'step').",
    )
    is_conversational: bool = Field(
        default=False,
        description="Whether query is conversational (identity, greeting, small talk) and should bypass document retrieval.",
    )
    is_ambiguous: bool = Field(
        default=False,
        description="Whether query lacks clear subject or entity and requires user clarification.",
    )
    is_out_of_scope: bool = Field(
        default=False,
        description="Whether query is outside academic course scope (e.g. celebrity/pop-culture) requiring polite refusal.",
    )
    requires_retrieval: bool = Field(
        default=True,
        description="Whether query requires document retrieval over authorized knowledge bases.",
    )
    requires_document_summary: bool = Field(
        default=False,
        description="Whether query requests a whole-document summary or overview rather than chunk QA.",
    )
    target_document_hint: str | None = Field(
        default=None,
        description="Document title or filename hint extracted from the query if specified.",
    )
    clarification_prompt: str | None = Field(
        default=None,
        description="Clarification question to return when is_ambiguous is True.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional diagnostic metadata or debug attributes.",
    )

