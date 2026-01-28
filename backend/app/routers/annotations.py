from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import Annotation, Connection, User
from ..schemas import (
    AnnotationCreate, AnnotationUpdate, AnnotationResponse,
    ConnectionCreate, ConnectionResponse
)
from ..auth import get_current_user

router = APIRouter(prefix="/api/annotations", tags=["Annotations"])


@router.post("/", response_model=AnnotationResponse)
async def create_annotation(
    annotation_data: AnnotationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new annotation (bounding box)."""
    annotation = Annotation(
        page_id=annotation_data.page_id,
        symbol_id=annotation_data.symbol_id,
        x=annotation_data.x,
        y=annotation_data.y,
        width=annotation_data.width,
        height=annotation_data.height,
        tag_id=annotation_data.tag_id,
        attributes=annotation_data.attributes or {},
        confidence=annotation_data.confidence,
        source=annotation_data.source,
        created_by=current_user.id
    )
    db.add(annotation)
    await db.commit()
    await db.refresh(annotation)
    return annotation


@router.get("/page/{page_id}", response_model=List[AnnotationResponse])
async def list_page_annotations(
    page_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all annotations for a page."""
    result = await db.execute(
        select(Annotation).where(Annotation.page_id == page_id)
    )
    annotations = result.scalars().all()
    return annotations


@router.get("/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(
    annotation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get annotation details."""
    result = await db.execute(
        select(Annotation).where(Annotation.id == annotation_id)
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation


@router.put("/{annotation_id}", response_model=AnnotationResponse)
async def update_annotation(
    annotation_id: int,
    update_data: AnnotationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update an annotation."""
    result = await db.execute(
        select(Annotation).where(Annotation.id == annotation_id)
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    # Update fields if provided
    update_dict = update_data.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(annotation, key, value)
    
    await db.commit()
    await db.refresh(annotation)
    return annotation


@router.delete("/{annotation_id}")
async def delete_annotation(
    annotation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete an annotation."""
    result = await db.execute(
        select(Annotation).where(Annotation.id == annotation_id)
    )
    annotation = result.scalar_one_or_none()
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    
    await db.delete(annotation)
    await db.commit()
    return {"message": "Annotation deleted successfully"}


# Connection endpoints
@router.post("/connections", response_model=ConnectionResponse)
async def create_connection(
    connection_data: ConnectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a connection between two annotations."""
    connection = Connection(
        page_id=connection_data.page_id,
        from_annotation_id=connection_data.from_annotation_id,
        to_annotation_id=connection_data.to_annotation_id,
        line_type=connection_data.line_type,
        waypoints=connection_data.waypoints,
        created_by=current_user.id
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


@router.get("/connections/page/{page_id}", response_model=List[ConnectionResponse])
async def list_page_connections(
    page_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all connections for a page."""
    result = await db.execute(
        select(Connection).where(Connection.page_id == page_id)
    )
    connections = result.scalars().all()
    return connections


@router.delete("/connections/{connection_id}")
async def delete_connection(
    connection_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a connection."""
    result = await db.execute(
        select(Connection).where(Connection.id == connection_id)
    )
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    await db.delete(connection)
    await db.commit()
    return {"message": "Connection deleted successfully"}
