from uuid import UUID, uuid4

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from services.api.app.db.base import Base


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    document_version_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    width_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_px: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_layer_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    raw_page_text: Mapped[str | None] = mapped_column(Text, nullable=True)
