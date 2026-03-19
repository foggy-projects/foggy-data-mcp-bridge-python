"""Natural Language Query schema definitions."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class QueryIntent(str, Enum):
    """Natural language query intent types."""

    DATA_QUERY = "data_query"
    METADATA_QUERY = "metadata_query"
    COMPARISON = "comparison"
    TREND = "trend"
    RANKING = "ranking"
    AGGREGATION = "aggregation"
    FILTER = "filter"
    UNKNOWN = "unknown"


class DatasetNLQueryRequest(BaseModel):
    """Natural language query request."""

    # Query content
    query: str = Field(..., description="Natural language query text")
    query_model: Optional[str] = Field(default=None, description="Target query model (optional)")

    # Context
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Previous conversation messages"
    )

    # Options
    max_rows: int = Field(default=100, description="Maximum rows to return")
    include_sql: bool = Field(default=False, description="Include generated SQL in response")
    include_explanation: bool = Field(default=True, description="Include query explanation")

    # Language settings
    language: str = Field(default="zh", description="Query language")
    response_language: str = Field(default="zh", description="Response language")

    model_config = {"extra": "allow"}


class QueryInterpretation(BaseModel):
    """Interpretation of natural language query."""

    # Intent analysis
    intent: QueryIntent = Field(default=QueryIntent.UNKNOWN, description="Detected query intent")
    confidence: float = Field(default=0.0, description="Confidence score (0-1)")

    # Entity extraction
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    time_range: Optional[Dict[str, str]] = Field(default=None, description="Detected time range")
    filters: List[Dict[str, Any]] = Field(default_factory=list, description="Extracted filters")
    aggregations: List[str] = Field(default_factory=list, description="Detected aggregations")
    group_by: List[str] = Field(default_factory=list, description="Detected groupings")
    order_by: List[Dict[str, str]] = Field(default_factory=list, description="Detected orderings")

    # Model mapping
    suggested_model: Optional[str] = Field(default=None, description="Suggested query model")
    suggested_columns: List[str] = Field(default_factory=list, description="Suggested columns")

    # Ambiguity handling
    ambiguities: List[str] = Field(default_factory=list, description="Detected ambiguities")
    clarification_questions: List[str] = Field(default_factory=list, description="Questions for clarification")

    model_config = {"extra": "allow"}


class DatasetNLQueryResponse(BaseModel):
    """Natural language query response."""

    # Query results
    success: bool = Field(default=True, description="Whether query was successful")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Query result data")

    # Interpretation
    interpretation: Optional[QueryInterpretation] = Field(
        default=None,
        description="How the query was interpreted"
    )

    # Generated content
    sql: Optional[str] = Field(default=None, description="Generated SQL query")
    explanation: Optional[str] = Field(default=None, description="Query explanation")
    summary: Optional[str] = Field(default=None, description="Natural language summary of results")

    # Suggestions
    follow_up_suggestions: List[str] = Field(
        default_factory=list,
        description="Suggested follow-up queries"
    )

    # Error handling
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    clarification_needed: bool = Field(default=False, description="Whether clarification is needed")

    # Metadata
    query_time_ms: Optional[float] = Field(default=None, description="Total query time")
    model_used: Optional[str] = Field(default=None, description="Model that was used")

    model_config = {"extra": "allow"}