from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.retrieval.vector_search import search_similar_chunks
from app.schemas.search import SearchRequest, SearchResponse, SearchResult


router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search_documents(request: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    try:
        results = search_similar_chunks(
            query=request.query,
            db=db,
            top_k=request.top_k,
            source_type=request.source_type,
            classification=request.classification,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return SearchResponse(
        query=request.query,
        results=[
            SearchResult(
                document_id=result.document_id,
                document_title=result.document_title,
                chunk_id=result.chunk_id,
                chunk_index=result.chunk_index,
                page_start=result.page_start,
                page_end=result.page_end,
                similarity_score=result.similarity_score,
                source_type=result.source_type,
                classification=result.classification,
                content_preview=result.content[:1000],
            )
            for result in results
        ],
    )
