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
from backend.app.persistence.database import ProductRecord, SessionLocal, load
from backend.app.services.intake import IntakeService, NotFoundError


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Validate configuration early; a bad provider setting should be visible at startup.
    provider_from_settings()
    yield


app = FastAPI(title="EK Product Intake Automation", version="0.1.0", description="Synthetic-data-only product intake case-study PoC.", lifespan=lifespan)


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
    count = lambda state: sum(record.status == state.value for record in records)
    average_issues = mean(len(load(record.issues_json)) for record in records) if records else 0.0
    average_ms = mean(record.processing_ms or 0 for record in records) if records else 0.0
    approved = count(ProductStatus.APPROVED)
    return MetricsResponse(products_processed=total, automatically_approved=approved, review_required=count(ProductStatus.REVIEW_REQUIRED), rejected=count(ProductStatus.REJECTED), average_issues=round(average_issues, 2), average_processing_ms=round(average_ms, 2), human_review_rate=round(count(ProductStatus.REVIEW_REQUIRED) / total, 3) if total else 0, auto_approval_rate=round(approved / total, 3) if total else 0, estimated_manual_minutes_avoided=round(approved * settings.manual_minutes_per_product, 1), estimate_assumption=f"Illustrative only: {settings.manual_minutes_per_product} assumed manual minutes per safely auto-approved synthetic record.")
