from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.api.app.db.base import Base


class MetricAlias(Base):
    __tablename__ = "metric_aliases"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    metric_definition_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    alias_pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    match_type: Mapped[str] = mapped_column(String(50), nullable=False, default="EXACT_NORMALIZED")
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="tr_TR")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
