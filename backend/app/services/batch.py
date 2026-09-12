from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.extraction.providers import ExtractionProvider
from backend.app.models.domain import BatchResponse, BatchRowError, BatchStatus, ProductResponse, ProductStatus
from backend.app.parsers import parse_spreadsheet_batch
from backend.app.persistence.database import BatchRecord, ProductRecord, dump, load
from backend.app.services.intake import IntakeService, NotFoundError


class BatchService:
    def __init__(self, session: Session, provider: ExtractionProvider):
        self.session = session
        self.intake = IntakeService(session, provider)

    def _find(self, batch_id: str) -> BatchRecord:
        record = self.session.get(BatchRecord, batch_id)
        if not record:
            raise NotFoundError(f"Batch '{batch_id}' was not found.")
        return record

    def _products(self, batch_id: str) -> list[ProductRecord]:
        query = (
            select(ProductRecord)
            .where(ProductRecord.batch_id == batch_id)
            .order_by(ProductRecord.source_row_number, ProductRecord.created_at)
        )
        return list(self.session.scalars(query).all())

    def _response(self, record: BatchRecord) -> BatchResponse:
        products = self._products(record.id)
        straight_through = sum(product.initial_status == ProductStatus.APPROVED.value for product in products)
        ever_reviewed = sum(product.review_required_at is not None for product in products)
        current_review = sum(product.status == ProductStatus.REVIEW_REQUIRED.value for product in products)
        ready = sum(product.status == ProductStatus.READY_FOR_APPROVAL.value for product in products)
        human_approved = sum(product.approved_at is not None and product.approval_source == "human" for product in products)
        rejected = sum(product.rejected_at is not None for product in products)
        return BatchResponse(
            id=record.id,
            source_name=record.source_name,
            source_type=record.source_type,
            status=BatchStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
            total_rows=record.total_rows,
            processed_rows=record.processed_rows,
            failed_rows=record.failed_rows,
            row_errors=[BatchRowError.model_validate(error) for error in load(record.row_errors_json)],
            straight_through_approved=straight_through,
            ever_required_human_review=ever_reviewed,
            currently_review_required=current_review,
            ready_for_approval=ready,
            human_approved=human_approved,
            rejected=rejected,
        )

    def create(self, filename: str, content: bytes) -> BatchResponse:
        parsed = parse_spreadsheet_batch(filename, content)
        row_errors = list(parsed.row_errors)
        record = BatchRecord(
            source_name=filename,
            source_type=parsed.source_type,
            status=BatchStatus.PROCESSING.value,
            total_rows=parsed.total_rows,
            processed_rows=0,
            failed_rows=len(row_errors),
            row_errors_json=dump([error.model_dump() for error in row_errors]),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)

        processed_rows = 0
        failed_rows = len(row_errors)
        for row in parsed.rows:
            try:
                self.intake.create(
                    row.text,
                    source_name=f"{filename}#row-{row.row_number}",
                    source_type=parsed.source_type,
                    batch_id=record.id,
                    source_row_number=row.row_number,
                )
                processed_rows += 1
            except Exception as error:
                self.session.rollback()
                row_errors.append(
                    BatchRowError(
                        row_number=row.row_number,
                        code=error.__class__.__name__.lower(),
                        message=str(error) or "Row ingestion failed.",
                    )
                )
                failed_rows += 1

        record.processed_rows = processed_rows
        record.failed_rows = failed_rows
        if processed_rows == 0 and failed_rows > 0:
            record.status = BatchStatus.FAILED.value
        elif failed_rows > 0:
            record.status = BatchStatus.COMPLETED_WITH_ERRORS.value
        else:
            record.status = BatchStatus.COMPLETED.value
        record.row_errors_json = dump([error.model_dump() for error in row_errors])
        self.session.commit()
        self.session.refresh(record)
        return self._response(record)

    def list(self) -> list[BatchResponse]:
        query = select(BatchRecord).order_by(BatchRecord.created_at.desc())
        return [self._response(record) for record in self.session.scalars(query).all()]

    def get(self, batch_id: str) -> BatchResponse:
        return self._response(self._find(batch_id))

    def products(self, batch_id: str) -> list[ProductResponse]:
        self._find(batch_id)
        return [self.intake._response(record) for record in self._products(batch_id)]
