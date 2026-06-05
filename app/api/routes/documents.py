import re
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.dependencies import get_db
from app.ingestion.parser import PDFParsingError
from app.ingestion.pipeline import (
    DocumentNotFoundError,
    InvalidDocumentStatusError,
    chunk_parsed_document,
    parse_uploaded_document,
)
from app.models.document import Document, DocumentChunk, ParsedDocumentPage
from app.schemas.document import (
    DocumentChunkPreview,
    DocumentChunkResponse,
    DocumentChunksResponse,
    DocumentClassification,
    DocumentPagePreview,
    DocumentPagesResponse,
    DocumentParseResponse,
    DocumentSourceType,
    DocumentUploadResponse,
)


router = APIRouter(prefix="/documents", tags=["documents"])
PDF_SIGNATURE = b"%PDF-"
UPLOAD_CHUNK_SIZE = 1024 * 1024


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    file: Annotated[UploadFile, File(description="PDF document to upload")],
    source_type: Annotated[DocumentSourceType, Form()],
    classification: Annotated[DocumentClassification, Form()],
    db: Session = Depends(get_db),
) -> DocumentUploadResponse:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a filename.",
        )

    if file.content_type != "application/pdf" or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF uploads are supported.",
        )

    document_id = uuid4()
    filename = _sanitize_filename(file.filename)
    file_path = _save_pdf_upload(file, document_id, filename)

    document = Document(
        id=document_id,
        title=filename,
        filename=filename,
        file_path=str(file_path),
        source=filename,
        document_type="pdf",
        status="uploaded",
        source_type=source_type,
        classification=classification,
        document_metadata={},
    )

    try:
        db.add(document)
        db.commit()
    except Exception:
        db.rollback()
        file_path.unlink(missing_ok=True)
        raise

    return DocumentUploadResponse(
        document_id=document.id,
        filename=document.filename,
        status=document.status,
        source_type=document.source_type,
        classification=document.classification,
    )


@router.post("/{document_id}/parse", response_model=DocumentParseResponse)
def parse_document(document_id: UUID, db: Session = Depends(get_db)) -> DocumentParseResponse:
    try:
        document = parse_uploaded_document(document_id, db)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDocumentStatusError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except PDFParsingError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    pages_parsed = (document.document_metadata or {}).get("pages_parsed", 0)
    return DocumentParseResponse(
        document_id=document.id,
        status=document.status,
        pages_parsed=pages_parsed,
    )


@router.post("/{document_id}/chunk", response_model=DocumentChunkResponse)
def chunk_document(document_id: UUID, db: Session = Depends(get_db)) -> DocumentChunkResponse:
    try:
        document = chunk_parsed_document(document_id, db)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidDocumentStatusError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    chunks_created = (document.document_metadata or {}).get("chunks_created", 0)
    return DocumentChunkResponse(
        document_id=document.id,
        status=document.status,
        chunks_created=chunks_created,
    )


@router.get("/{document_id}/pages", response_model=DocumentPagesResponse)
def get_document_pages(document_id: UUID, db: Session = Depends(get_db)) -> DocumentPagesResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    pages = db.scalars(
        select(ParsedDocumentPage)
        .where(ParsedDocumentPage.document_id == document.id)
        .order_by(ParsedDocumentPage.page_number)
    ).all()

    return DocumentPagesResponse(
        document_id=document.id,
        pages=[
            DocumentPagePreview(page_number=page.page_number, text_preview=page.text[:1000])
            for page in pages
        ],
    )


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
def get_document_chunks(document_id: UUID, db: Session = Depends(get_db)) -> DocumentChunksResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    chunks = db.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
    ).all()

    return DocumentChunksResponse(
        document_id=document.id,
        chunks=[
            DocumentChunkPreview(
                chunk_index=chunk.chunk_index,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                token_count=chunk.token_count,
                content_preview=chunk.content[:1000],
            )
            for chunk in chunks
        ],
    )


def _sanitize_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", name).strip("._")

    if not safe_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must include a valid filename.",
        )

    return safe_name


def _save_pdf_upload(file: UploadFile, document_id, filename: str) -> Path:
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{document_id}_{filename}"
    max_upload_bytes = settings.max_upload_mb * 1024 * 1024

    signature = file.file.read(len(PDF_SIGNATURE))
    if signature != PDF_SIGNATURE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not a valid PDF.",
        )

    bytes_written = len(signature)
    if bytes_written > max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds the {settings.max_upload_mb} MB limit.",
        )

    try:
        with file_path.open("wb") as buffer:
            buffer.write(signature)

            while chunk := file.file.read(UPLOAD_CHUNK_SIZE):
                bytes_written += len(chunk)
                if bytes_written > max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Uploaded file exceeds the {settings.max_upload_mb} MB limit.",
                    )
                buffer.write(chunk)
    except Exception:
        file_path.unlink(missing_ok=True)
        raise

    return file_path
