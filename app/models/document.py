from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "status IN ('uploaded', 'parsing', 'parsed', 'chunked', 'embedded', 'indexed', 'failed')",
            name="ck_documents_status",
        ),
        CheckConstraint(
            "source_type IN ('sec_filing', 'diligence_report', 'technology_assessment', 'board_material')",
            name="ck_documents_source_type",
        ),
        CheckConstraint(
            "classification IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_documents_classification",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    source: Mapped[str | None] = mapped_column(String(512))
    document_type: Mapped[str | None] = mapped_column(String(100))
    source_type: Mapped[str] = mapped_column(String(100), default="technology_assessment", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    classification: Mapped[str] = mapped_column(String(50), default="internal", nullable=False)
    document_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
    pages: Mapped[list["ParsedDocumentPage"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="ParsedDocumentPage.page_number",
    )
    document_set_links: Mapped[list["DocumentSetDocument"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class ParsedDocumentPage(Base):
    __tablename__ = "parsed_document_pages"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    page_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped[Document] = relationship(back_populates="pages")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped[Document] = relationship(back_populates="chunks")


class DocumentSet(Base):
    __tablename__ = "document_sets"

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document_links: Mapped[list["DocumentSetDocument"]] = relationship(
        back_populates="document_set",
        cascade="all, delete-orphan",
    )


class DocumentSetDocument(Base):
    __tablename__ = "document_set_documents"
    __table_args__ = (
        UniqueConstraint("document_set_id", "document_id", name="uq_document_set_documents"),
    )

    document_set_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_sets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document_set: Mapped[DocumentSet] = relationship(back_populates="document_links")
    document: Mapped[Document] = relationship(back_populates="document_set_links")
