from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProductStatus(str, Enum):
    PROCESSING = "processing"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"


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
    product: Product
    evidence: list[FieldEvidence] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    source_name: str
    source_type: str
    source_preview: str
    processing_ms: float | None = None
    reviewer_note: str | None = None


class MetricsResponse(BaseModel):
    products_processed: int
    automatically_approved: int
    review_required: int
    rejected: int
    average_issues: float
    average_processing_ms: float
    human_review_rate: float
    auto_approval_rate: float
    estimated_manual_minutes_avoided: float
    estimate_assumption: str

