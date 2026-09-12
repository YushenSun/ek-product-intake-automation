from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductStatus(str, Enum):
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class BatchStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Product(BaseModel):
    """Canonical product record. All fields are synthetic-demo safe."""
    model_config = ConfigDict(extra="forbid")

    product_name: str | None = None
    brand: str | None = None
    ean: str | None = None
    sku: str | None = None
    category: str | None = None
    description: str | None = None
    weight: float | None = None
    weight_unit: str | None = None
    ingredients: str | None = None
    allergens: str | None = None
    country_of_origin: str | None = None
    packaging: str | None = None
    supplier_name: str | None = None
    price: float | None = None
    currency: str | None = None


class FieldEvidence(BaseModel):
    field: str
    value: Any | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source: str
    source_snippet: str | None = None


class ValidationIssue(BaseModel):
    code: str
    field: str | None = None
    severity: Severity
    message: str


class ExtractionResult(BaseModel):
    product: Product
    evidence: list[FieldEvidence] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    provider: str


class ProductSubmission(BaseModel):
    source_name: str = "manual-text"
    text: str = Field(min_length=1, max_length=100_000)
    source_type: str = "txt"


class ProductPatch(BaseModel):
    product: Product
    reviewer_note: str | None = Field(default=None, max_length=1000)


class ProductResponse(BaseModel):
    id: str
    status: ProductStatus
    initial_status: ProductStatus
    decision_source: str
    approval_source: str | None = None
    product: Product
    evidence: list[FieldEvidence] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    source_name: str
    source_type: str
    source_preview: str
    batch_id: str | None = None
    source_row_number: int | None = None
    processing_ms: float | None = None
    reviewer_note: str | None = None
    review_required_at: datetime | None = None
    reviewed_at: datetime | None = None
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    correction_count: int = 0


class BatchRowError(BaseModel):
    row_number: int
    code: str
    message: str


class BatchResponse(BaseModel):
    id: str
    source_name: str
    source_type: str
    status: BatchStatus
    created_at: datetime
    updated_at: datetime
    total_rows: int
    processed_rows: int
    failed_rows: int
    row_errors: list[BatchRowError] = Field(default_factory=list)
    straight_through_approved: int
    ever_required_human_review: int
    currently_review_required: int
    ready_for_approval: int
    human_approved: int
    rejected: int


class MetricsResponse(BaseModel):
    products_processed: int
    straight_through_approved: int
    ever_required_human_review: int
    currently_waiting_for_review: int
    ready_for_approval: int
    human_approved: int
    rejected: int
    straight_through_processing_rate: float
    historical_human_review_rate: float
    review_to_approval_rate: float
    average_processing_ms: float
    estimated_manual_minutes_avoided: float
    estimate_assumption: str
