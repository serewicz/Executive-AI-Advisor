import shutil
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.dependencies import get_db
from app.models.document import Document
from app.schemas.document import DocumentClassification, DocumentSourceType, DocumentUploadResponse


router = APIRouter(prefix="/documents", tags=["documents"])


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
    filename = Path(file.filename.replace("\\", "/")).name
    stored_filename = f"{document_id}_{filename}"
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / stored_filename

    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

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

    return DocumentUploadResponse(document_id=document.id, status=document.status)
