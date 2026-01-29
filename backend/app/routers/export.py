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


@router.get("/{document_id}/yolo-training")
async def export_yolo_training_data(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export annotations as a YOLO training dataset (ZIP).
    Includes:
    - images/ (page images)
    - labels/ (YOLO encoded annotations)
    - data.yaml (class configuration)
    """
    import zipfile
    import io
    import os
    import shutil
    from pathlib import Path
    
    # Fetch document with data
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
    
    # Get all symbols used in this document to create minimal class map
    # Or should we use ALL symbols in DB? For consistency across multiple exports, use ALL.
    symbols_result = await db.execute(select(Symbol).order_by(Symbol.id))
    all_symbols = symbols_result.scalars().all()
    
    # Map symbol ID to consecutive class IDs (0, 1, 2...)
    # YOLO requires classes to be 0-indexed integers
    symbol_id_to_class_id = {}
    class_names = []
    
    for idx, sym in enumerate(all_symbols):
        symbol_id_to_class_id[sym.id] = idx
        class_names.append(sym.name)
        
    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        # Create data.yaml
        data_yaml = f"""train: ../train/images
val: ../valid/images
test: ../test/images

nc: {len(class_names)}
names: {class_names}
"""
        zip_file.writestr("data.yaml", data_yaml)
        
        # Process each page
        for page in document.pages:
            if not os.path.exists(page.image_path):
                continue
                
            # Add image to ZIP
            image_filename = f"page_{page.page_number}.jpg"
            zip_file.write(page.image_path, f"images/{image_filename}")
            
            # Generate labels
            label_lines = []
            for ann in page.annotations:
                if ann.symbol_id and ann.symbol_id in symbol_id_to_class_id:
                    # YOLO: class_id x_center y_center width height
                    # All normalized 0-1
                    
                    # Ensure width/height are positive
                    ann_w = abs(ann.width)
                    ann_h = abs(ann.height)
                    
                    # Calculate center (handling negative width/height if any)
                    x_center = (ann.x + ann.width / 2) / page.width
                    y_center = (ann.y + ann.height / 2) / page.height
                    w_norm = ann_w / page.width
                    h_norm = ann_h / page.height
                    
                    # Clamp values to 0-1
                    x_center = max(0, min(1, x_center))
                    y_center = max(0, min(1, y_center))
                    w_norm = max(0, min(1, w_norm))
                    h_norm = max(0, min(1, h_norm))
                    
                    class_id = symbol_id_to_class_id[ann.symbol_id]
                    
                    label_lines.append(f"{class_id} {x_center:.6f} {y_center:.6f} {w_norm:.6f} {h_norm:.6f}")
            
            # Add label file
            label_filename = f"page_{page.page_number}.txt"
            zip_file.writestr(f"labels/{label_filename}", "\n".join(label_lines))
            
    # Return ZIP
    zip_buffer.seek(0)
    filename = f"{document.filename.rsplit('.', 1)[0]}_yolo_dataset.zip"
    
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/{document_id}/json")
async def export_digital_twin_json(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export as Digital Twin JSON (Nodes + Edges + Metadata).
    Useful for Q&A and linking to other systems.
    """
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
        
    export_data = {
        "document_id": document.id,
        "filename": document.filename,
        "metadata": {
            "uploaded_at": document.uploaded_at.isoformat(),
            "uploaded_by": current_user.username,
            "page_count": document.page_count
        },
        "pages": []
    }
    
    for page in document.pages:
        nodes = []
        edges = []
        
        # Nodes (Annotations)
        for ann in page.annotations:
            node = {
                "id": ann.id,
                "type": ann.symbol.name if ann.symbol else "Unknown",
                "category": ann.symbol.category if ann.symbol else "Uncategorized",
                "tag_id": ann.tag_id,
                "bbox": {
                    "x": ann.x, 
                    "y": ann.y, 
                    "width": ann.width, 
                    "height": ann.height
                },
                "attributes": ann.attributes or {},
                "source": ann.source,
                "confidence": ann.confidence
            }
            nodes.append(node)
            
        # Edges (Connections)
        # Assuming we implement connections later, but structure is here
        if hasattr(page, 'connections'):
            for conn in page.connections:
                edges.append({
                    "id": conn.id,
                    "from_node": conn.from_annotation_id,
                    "to_node": conn.to_annotation_id,
                    "type": conn.line_type,
                    "waypoints": conn.waypoints
                })
                
        export_data["pages"].append({
            "page_number": page.page_number,
            "nodes": nodes,
            "edges": edges
        })
        
    return export_data
