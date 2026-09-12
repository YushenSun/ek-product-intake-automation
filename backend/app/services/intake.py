from __future__ import annotations

from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.domain import Product, ProductPatch, ProductResponse, ProductStatus, Severity, ValidationIssue
from backend.app.persistence.database import ProductRecord, dump, load
from backend.app.extraction.providers import ExtractionProvider
from backend.app.validation.rules import validate_product


class NotFoundError(LookupError):
    pass


class IntakeService:
    def __init__(self, session: Session, provider: ExtractionProvider):
        self.session, self.provider = session, provider

    @staticmethod
    def _response(record: ProductRecord) -> ProductResponse:
        return ProductResponse(id=record.id, status=ProductStatus(record.status), product=Product.model_validate(load(record.product_json)), evidence=load(record.evidence_json), issues=load(record.issues_json), source_name=record.source_name, source_type=record.source_type, source_preview=record.source_preview, processing_ms=record.processing_ms, reviewer_note=record.reviewer_note)

    def _find(self, product_id: str) -> ProductRecord:
        record = self.session.get(ProductRecord, product_id)
        if not record:
            raise NotFoundError(f"Product '{product_id}' was not found.")
        return record

    def _duplicate_issue(self, product: Product, exclude_id: str | None = None) -> ValidationIssue | None:
        for record in self.session.scalars(select(ProductRecord)).all():
            if record.id == exclude_id:
                continue
            other = Product.model_validate(load(record.product_json))
            same_ean = bool(product.ean and other.ean and product.ean == other.ean)
            same_name_supplier = bool(product.product_name and other.product_name and product.product_name.casefold() == other.product_name.casefold() and product.supplier_name and other.supplier_name and product.supplier_name.casefold() == other.supplier_name.casefold())
            if same_ean or same_name_supplier:
                return ValidationIssue(code="possible_duplicate", field="ean" if same_ean else "product_name", severity=Severity.ERROR, message=f"Potential duplicate of existing record {record.id}.")
        return None

    @staticmethod
    def _decide(issues: list[ValidationIssue]) -> ProductStatus:
        return ProductStatus.REVIEW_REQUIRED if any(issue.severity == Severity.ERROR for issue in issues) else ProductStatus.APPROVED

    def create(self, text: str, source_name: str, source_type: str) -> ProductResponse:
        started = perf_counter()
        result = self.provider.extract(text, source_name)
        product, issues = validate_product(result.product)
        issues.extend(ValidationIssue(code="source_conflict", field=field, severity=Severity.ERROR, message=f"Conflicting source values found for '{field}'.") for field in result.conflicts)
        duplicate = self._duplicate_issue(product)
        if duplicate:
            issues.append(duplicate)
        record = ProductRecord(status=self._decide(issues).value, product_json=dump(product.model_dump()), evidence_json=dump([item.model_dump() for item in result.evidence]), issues_json=dump([item.model_dump(mode="json") for item in issues]), source_name=source_name, source_type=source_type, source_preview=text[:4000], processing_ms=round((perf_counter() - started) * 1000, 2))
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return self._response(record)

    def list(self, status: ProductStatus | None = None) -> list[ProductResponse]:
        query = select(ProductRecord).order_by(ProductRecord.created_at.desc())
        if status:
            query = query.where(ProductRecord.status == status.value)
        return [self._response(record) for record in self.session.scalars(query).all()]

    def get(self, product_id: str) -> ProductResponse:
        return self._response(self._find(product_id))

    def patch(self, product_id: str, patch: ProductPatch) -> ProductResponse:
        record = self._find(product_id)
        product, issues = validate_product(patch.product)
        duplicate = self._duplicate_issue(product, exclude_id=record.id)
        if duplicate:
            issues.append(duplicate)
        record.product_json, record.issues_json = dump(product.model_dump()), dump([item.model_dump(mode="json") for item in issues])
        record.reviewer_note = patch.reviewer_note
        record.status = self._decide(issues).value
        self.session.commit()
        return self._response(record)

    def set_status(self, product_id: str, status: ProductStatus) -> ProductResponse:
        record = self._find(product_id)
        if status == ProductStatus.APPROVED:
            issues = [ValidationIssue.model_validate(i) for i in load(record.issues_json)]
            if any(issue.severity == Severity.ERROR for issue in issues):
                raise ValueError("Cannot approve while error-level validation issues remain; correct the record first.")
        record.status = status.value
        self.session.commit()
        return self._response(record)
