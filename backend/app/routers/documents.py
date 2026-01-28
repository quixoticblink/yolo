import os
import shutil
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..database import get_db
from ..models import Document, Page, User
from ..schemas import DocumentResponse, PageResponse
from ..auth import get_current_user
from ..config import settings
from services.pdf_processor import process_pdf, process_image

router = APIRouter(prefix="/api/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a P&ID/PFD document (PDF or image)."""
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {ALLOWED_EXTENSIONS}"
        )
    
    # Save uploaded file
    doc_path = settings.DOCUMENTS_DIR / file.filename
    with open(doc_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Create document record
    document = Document(
        filename=file.filename,
        original_path=str(doc_path),
        status="processing",
        uploaded_by=current_user.id
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    
    # Process document (convert to images)
    try:
        if file_ext == ".pdf":
            pages_info = await process_pdf(doc_path, document.id, settings.RENDERED_DIR, settings.PDF_DPI)
        else:
            pages_info = await process_image(doc_path, document.id, settings.RENDERED_DIR)
        
        # Create page records
        for page_info in pages_info:
            page = Page(
                document_id=document.id,
                page_number=page_info["page_number"],
                image_path=page_info["image_path"],
                width=page_info["width"],
                height=page_info["height"]
            )
            db.add(page)
        
        document.page_count = len(pages_info)
        document.status = "ready"
        await db.commit()
        await db.refresh(document)
        
    except Exception as e:
        document.status = "error"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing document: {str(e)}"
        )
    
    return document


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all uploaded documents."""
    result = await db.execute(select(Document).order_by(Document.uploaded_at.desc()))
    documents = result.scalars().all()
    return documents


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get document details."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.pages))
        .where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("/{document_id}/pages", response_model=List[PageResponse])
async def list_document_pages(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all pages of a document."""
    result = await db.execute(
        select(Page)
        .where(Page.document_id == document_id)
        .order_by(Page.page_number)
    )
    pages = result.scalars().all()
    return pages


@router.get("/{document_id}/pages/{page_number}/image")
async def get_page_image(
    document_id: int,
    page_number: int,
    db: AsyncSession = Depends(get_db)
):
    """Get rendered page image (public for canvas loading)."""
    result = await db.execute(
        select(Page)
        .where(Page.document_id == document_id, Page.page_number == page_number)
    )
    page = result.scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    
    if not os.path.exists(page.image_path):
        raise HTTPException(status_code=404, detail="Page image not found")
    
    return FileResponse(page.image_path, media_type="image/png")


@router.delete("/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a document and its pages."""
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.pages))
        .where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete rendered images
    for page in document.pages:
        if os.path.exists(page.image_path):
            os.remove(page.image_path)
    
    # Delete original document
    if os.path.exists(document.original_path):
        os.remove(document.original_path)
    
    await db.delete(document)
    await db.commit()
    
    return {"message": "Document deleted successfully"}
