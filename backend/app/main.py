from __future__ import annotations

from contextlib import asynccontextmanager
from statistics import mean

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.extraction.providers import ExtractionProviderError, provider_from_settings
from backend.app.models.domain import MetricsResponse, ProductPatch, ProductResponse, ProductStatus, ProductSubmission
from backend.app.parsers import ParseError, parse_file, parse_text
from backend.app.persistence.database import ProductRecord, SessionLocal
from backend.app.services.intake import IntakeService, NotFoundError


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Validate configuration early; a bad provider setting should be visible at startup.
    provider_from_settings()
    yield


app = FastAPI(title="EK Product Intake Automation", version="0.2.0", description="Synthetic-data-only product intake case-study PoC.", lifespan=lifespan)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_service(session: Session = Depends(get_session)) -> IntakeService:
    return IntakeService(session, provider_from_settings())


def as_http_error(error: Exception):
    if isinstance(error, NotFoundError):
        raise HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (ParseError, ExtractionProviderError, ValueError)):
        raise HTTPException(status_code=422, detail=str(error))
    raise error


@app.get("/health")
def health():
    return {"status": "ok", "provider": settings.extraction_provider, "synthetic_data_only": True}


@app.post("/products", response_model=ProductResponse, status_code=201)
def create_product(submission: ProductSubmission, service: IntakeService = Depends(get_service)):
    try:
        parsed = parse_text(submission.text, submission.source_type)
        return service.create(parsed.text, submission.source_name, parsed.source_type)
    except Exception as error:
        as_http_error(error)


@app.post("/products/upload", response_model=ProductResponse, status_code=201)
async def upload_product(file: UploadFile = File(...), service: IntakeService = Depends(get_service)):
    try:
        parsed = parse_file(file.filename or "upload", await file.read())
        return service.create(parsed.text, file.filename or "upload", parsed.source_type)
    except Exception as error:
        as_http_error(error)


@app.get("/products", response_model=list[ProductResponse])
def list_products(status: ProductStatus | None = Query(default=None), service: IntakeService = Depends(get_service)):
    return service.list(status)


@app.get("/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: str, service: IntakeService = Depends(get_service)):
    try:
        return service.get(product_id)
    except Exception as error:
        as_http_error(error)


@app.get("/products/{product_id}/issues")
def get_issues(product_id: str, service: IntakeService = Depends(get_service)):
    try:
        return service.get(product_id).issues
    except Exception as error:
        as_http_error(error)


@app.get("/products/{product_id}/export")
def export_product(product_id: str, service: IntakeService = Depends(get_service)):
    """JSON payload suitable for a later PIM/ERP connector; no external system is called."""
    try:
        product = service.get(product_id)
        return {"id": product.id, "status": product.status, "product": product.product, "source_name": product.source_name}
    except Exception as error:
        as_http_error(error)


@app.patch("/products/{product_id}", response_model=ProductResponse)
def patch_product(product_id: str, patch: ProductPatch, service: IntakeService = Depends(get_service)):
    try:
        return service.patch(product_id, patch)
    except Exception as error:
        as_http_error(error)


@app.post("/products/{product_id}/approve", response_model=ProductResponse)
def approve_product(product_id: str, service: IntakeService = Depends(get_service)):
    try:
        return service.set_status(product_id, ProductStatus.APPROVED)
    except Exception as error:
        as_http_error(error)


@app.post("/products/{product_id}/reject", response_model=ProductResponse)
def reject_product(product_id: str, service: IntakeService = Depends(get_service)):
    try:
        return service.set_status(product_id, ProductStatus.REJECTED)
    except Exception as error:
        as_http_error(error)


@app.get("/metrics", response_model=MetricsResponse)
def metrics(session: Session = Depends(get_session)):
    records = session.scalars(select(ProductRecord)).all()
    total = len(records)
    straight_through = sum(record.initial_status == ProductStatus.APPROVED.value for record in records)
    ever_reviewed = sum(record.review_required_at is not None for record in records)
    waiting = sum(record.status == ProductStatus.REVIEW_REQUIRED.value for record in records)
    ready = sum(record.status == ProductStatus.READY_FOR_APPROVAL.value for record in records)
    human_approved = sum(record.approved_at is not None and record.approval_source == "human" for record in records)
    rejected = sum(record.rejected_at is not None for record in records)
    average_ms = mean(record.processing_ms or 0 for record in records) if records else 0.0

    return MetricsResponse(
        products_processed=total,
        straight_through_approved=straight_through,
        ever_required_human_review=ever_reviewed,
        currently_waiting_for_review=waiting,
        ready_for_approval=ready,
        human_approved=human_approved,
        rejected=rejected,
        straight_through_processing_rate=round(straight_through / total, 3) if total else 0,
        historical_human_review_rate=round(ever_reviewed / total, 3) if total else 0,
        review_to_approval_rate=round(human_approved / ever_reviewed, 3) if ever_reviewed else 0,
        average_processing_ms=round(average_ms, 2),
        estimated_manual_minutes_avoided=round(straight_through * settings.manual_minutes_per_product, 1),
        estimate_assumption=f"Illustrative only: {settings.manual_minutes_per_product} assumed manual minutes per straight-through approved synthetic record.",
    )
