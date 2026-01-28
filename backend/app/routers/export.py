from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from ..database import get_db
from ..models import Document, Page, Annotation, Connection, Symbol, User
from ..auth import get_current_user
from services.xml_generator import generate_xml

router = APIRouter(prefix="/api/export", tags=["Export"])


@router.get("/{document_id}/xml")
async def export_document_xml(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export document annotations as XML."""
    # Fetch document with all related data
    result = await db.execute(
        select(Document)
        .options(
            selectinload(Document.pages)
            .selectinload(Page.annotations)
            .selectinload(Annotation.symbol)
        )
        .options(
            selectinload(Document.pages)
            .selectinload(Page.connections)
        )
        .where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Generate XML
    xml_content = generate_xml(document, current_user.username)
    
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'attachment; filename="{document.filename.rsplit(".", 1)[0]}_annotations.xml"'
        }
    )


@router.get("/{document_id}/yolo")
async def export_yolo_format(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export annotations in YOLO training format."""
    result = await db.execute(
        select(Document)
        .options(
            selectinload(Document.pages)
            .selectinload(Page.annotations)
            .selectinload(Annotation.symbol)
        )
        .where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get all unique symbols for class mapping
    symbols_result = await db.execute(select(Symbol).order_by(Symbol.id))
    symbols = symbols_result.scalars().all()
    class_map = {s.id: idx for idx, s in enumerate(symbols)}
    
    # Generate YOLO format annotations
    yolo_data = []
    for page in document.pages:
        page_annotations = []
        for ann in page.annotations:
            if ann.symbol_id and ann.symbol_id in class_map:
                # YOLO format: class_id x_center y_center width height (normalized)
                x_center = (ann.x + ann.width / 2) / page.width
                y_center = (ann.y + ann.height / 2) / page.height
                w_norm = ann.width / page.width
                h_norm = ann.height / page.height
                class_id = class_map[ann.symbol_id]
                page_annotations.append({
                    "class_id": class_id,
                    "x_center": round(x_center, 6),
                    "y_center": round(y_center, 6),
                    "width": round(w_norm, 6),
                    "height": round(h_norm, 6)
                })
        
        yolo_data.append({
            "page_number": page.page_number,
            "image_path": page.image_path,
            "annotations": page_annotations
        })
    
    # Class names for classes.txt
    class_names = [s.name for s in symbols]
    
    return {
        "document_id": document_id,
        "class_names": class_names,
        "pages": yolo_data
    }
