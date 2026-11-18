import uuid

from fastapi import APIRouter, HTTPException, Query, UploadFile, status

from app.api.deps import CurrentUser
from app.db.dependencies import DbSession
from app.schemas.document import DocumentList, DocumentRead
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED
)
def upload_document(file: UploadFile, user: CurrentUser, db: DbSession):
    try:
        return document_service.save_upload(db, user.id, file)
    except document_service.FileTooLargeError as exc:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, str(exc))
    except document_service.InvalidDocumentError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("", response_model=DocumentList)
def list_documents(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    items, total = document_service.list_documents(db, user.id, limit, offset)
    return DocumentList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: uuid.UUID, user: CurrentUser, db: DbSession):
    document = document_service.get_document(db, user.id, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: uuid.UUID, user: CurrentUser, db: DbSession):
    document = document_service.get_document(db, user.id, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    try:
        document_service.delete_document(db, document)
    except document_service.DocumentInUseError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))