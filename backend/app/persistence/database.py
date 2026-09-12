from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid

from sqlalchemy import DateTime, Float, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from backend.app.config import settings


class Base(DeclarativeBase):
    pass


class BatchRecord(Base):
    __tablename__ = "batches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    total_rows: Mapped[int] = mapped_column(default=0)
    processed_rows: Mapped[int] = mapped_column(default=0)
    failed_rows: Mapped[int] = mapped_column(default=0)
    row_errors_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ProductRecord(Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    status: Mapped[str] = mapped_column(String(32), index=True)
    initial_status: Mapped[str] = mapped_column(String(32), index=True)
    decision_source: Mapped[str] = mapped_column(String(32), index=True)
    approval_source: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    batch_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source_row_number: Mapped[int | None] = mapped_column(nullable=True)
    product_json: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    issues_json: Mapped[str] = mapped_column(Text, default="[]")
    source_name: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(32))
    source_preview: Mapped[str] = mapped_column(Text)
    processing_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_required_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    correction_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


def make_session_factory(database_url: str | None = None):
    url = database_url or settings.database_url
    kwargs = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=kwargs)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


SessionLocal = make_session_factory()


def dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def load(value: str):
    return json.loads(value)
