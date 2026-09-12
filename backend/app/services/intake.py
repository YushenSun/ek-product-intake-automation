from __future__ import annotations

from datetime import datetime, timezone
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
        return ProductResponse(
            id=record.id,
            status=ProductStatus(record.status),
            initial_status=ProductStatus(record.initial_status),
            decision_source=record.decision_source,
            approval_source=record.approval_source,
            product=Product.model_validate(load(record.product_json)),
            evidence=load(record.evidence_json),
            issues=load(record.issues_json),
            source_name=record.source_name,
            source_type=record.source_type,
            source_preview=record.source_preview,
            batch_id=record.batch_id,
            source_row_number=record.source_row_number,
            processing_ms=record.processing_ms,
            reviewer_note=record.reviewer_note,
            review_required_at=record.review_required_at,
            reviewed_at=record.reviewed_at,
            approved_at=record.approved_at,
            rejected_at=record.rejected_at,
            correction_count=record.correction_count,
        )

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
    def _initial_decision(issues: list[ValidationIssue]) -> ProductStatus:
        return ProductStatus.REVIEW_REQUIRED if any(issue.severity == Severity.ERROR for issue in issues) else ProductStatus.APPROVED

    def create(
        self,
        text: str,
        source_name: str,
        source_type: str,
        *,
        batch_id: str | None = None,
        source_row_number: int | None = None,
    ) -> ProductResponse:
        started = perf_counter()
        result = self.provider.extract(text, source_name)
        product, issues = validate_product(result.product)
        issues.extend(ValidationIssue(code="source_conflict", field=field, severity=Severity.ERROR, message=f"Conflicting source values found for '{field}'.") for field in result.conflicts)
        duplicate = self._duplicate_issue(product)
        if duplicate:
            issues.append(duplicate)

        now = datetime.now(timezone.utc)
        initial_status = self._initial_decision(issues)
        record = ProductRecord(
            status=initial_status.value,
            initial_status=initial_status.value,
            decision_source="automatic" if initial_status == ProductStatus.APPROVED else "pending_review",
            approval_source="automatic" if initial_status == ProductStatus.APPROVED else None,
            batch_id=batch_id,
            source_row_number=source_row_number,
            review_required_at=now if initial_status == ProductStatus.REVIEW_REQUIRED else None,
            approved_at=now if initial_status == ProductStatus.APPROVED else None,
            product_json=dump(product.model_dump()),
            evidence_json=dump([item.model_dump() for item in result.evidence]),
            issues_json=dump([item.model_dump(mode="json") for item in issues]),
            source_name=source_name,
            source_type=source_type,
            source_preview=text[:4000],
            processing_ms=round((perf_counter() - started) * 1000, 2),
        )
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

        record.product_json = dump(product.model_dump())
        record.issues_json = dump([item.model_dump(mode="json") for item in issues])
        record.reviewer_note = patch.reviewer_note
        record.reviewed_at = datetime.now(timezone.utc)
        record.correction_count += 1

        has_errors = any(issue.severity == Severity.ERROR for issue in issues)
        ever_required_review = record.review_required_at is not None
        if has_errors:
            record.status = ProductStatus.REVIEW_REQUIRED.value
            record.review_required_at = record.review_required_at or record.reviewed_at
            record.decision_source = "pending_review"
        elif ever_required_review:
            record.status = ProductStatus.READY_FOR_APPROVAL.value
            record.decision_source = "pending_review"
        else:
            # This record was already approved automatically; a valid edit does
            # not manufacture a second approval decision.
            record.status = ProductStatus.APPROVED.value

        self.session.commit()
        return self._response(record)

    def set_status(self, product_id: str, status: ProductStatus) -> ProductResponse:
        record = self._find(product_id)
        now = datetime.now(timezone.utc)

        if status == ProductStatus.APPROVED:
            issues = [ValidationIssue.model_validate(issue) for issue in load(record.issues_json)]
            if any(issue.severity == Severity.ERROR for issue in issues):
                raise ValueError("Cannot approve while error-level validation issues remain; correct the record first.")
            if record.review_required_at is not None:
                record.decision_source = "human"
                record.approval_source = "human"
                record.reviewed_at = now
            record.approved_at = now
            record.rejected_at = None
        elif status == ProductStatus.REJECTED:
            record.decision_source = "human"
            record.reviewed_at = now
            record.rejected_at = now

        record.status = status.value
        self.session.commit()
        return self._response(record)
