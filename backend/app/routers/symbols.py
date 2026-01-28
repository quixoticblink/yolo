import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import Symbol, User
from ..schemas import SymbolCreate, SymbolResponse
from ..auth import get_current_user
from ..config import settings

router = APIRouter(prefix="/api/symbols", tags=["Symbols"])


@router.get("/", response_model=List[SymbolResponse])
async def list_symbols(
    category: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all symbols, optionally filtered by category."""
    query = select(Symbol)
    if category:
        query = query.where(Symbol.category == category)
    query = query.order_by(Symbol.category, Symbol.name)
    
    result = await db.execute(query)
    symbols = result.scalars().all()
    return symbols


@router.get("/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all unique symbol categories."""
    result = await db.execute(
        select(Symbol.category).distinct().order_by(Symbol.category)
    )
    categories = [row[0] for row in result.fetchall()]
    return {"categories": categories}


@router.get("/{symbol_id}", response_model=SymbolResponse)
async def get_symbol(
    symbol_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get symbol details."""
    result = await db.execute(
        select(Symbol).where(Symbol.id == symbol_id)
    )
    symbol = result.scalar_one_or_none()
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")
    return symbol


@router.get("/{symbol_id}/image")
async def get_symbol_image(
    symbol_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get symbol image (public for palette loading)."""
    result = await db.execute(
        select(Symbol).where(Symbol.id == symbol_id)
    )
    symbol = result.scalar_one_or_none()
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")
    
    if not symbol.image_path or not os.path.exists(symbol.image_path):
        raise HTTPException(status_code=404, detail="Symbol image not found")
    
    return FileResponse(symbol.image_path, media_type="image/png")


@router.post("/", response_model=SymbolResponse)
async def create_symbol(
    symbol_data: SymbolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new symbol (admin only)."""
    symbol = Symbol(
        name=symbol_data.name,
        category=symbol_data.category,
        description=symbol_data.description
    )
    db.add(symbol)
    await db.commit()
    await db.refresh(symbol)
    return symbol


@router.post("/extract-from-legends")
async def extract_symbols_from_legends(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Extract symbols from legend PDFs in the Symbol library folder."""
    from services.symbol_extractor import extract_symbols_from_legends
    from pathlib import Path
    
    # Check multiple possible paths for symbol library
    possible_paths = [
        settings.BASE_DIR / "symbol_library",     # Docker mounted path
        settings.BASE_DIR.parent / "Symbol library",  # Local development path
        Path("/app/symbol_library"),              # Docker absolute path
    ]
    
    symbol_library_path = None
    for path in possible_paths:
        if path.exists():
            symbol_library_path = path
            break
    
    if not symbol_library_path:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol library folder not found. Checked: {[str(p) for p in possible_paths]}"
        )
    
    try:
        extracted_symbols = await extract_symbols_from_legends(
            symbol_library_path,
            settings.SYMBOLS_DIR,
            db
        )
        return {
            "message": f"Extracted {len(extracted_symbols)} symbols",
            "symbols": extracted_symbols
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error extracting symbols: {str(e)}"
        )


@router.delete("/{symbol_id}")
async def delete_symbol(
    symbol_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a symbol."""
    result = await db.execute(
        select(Symbol).where(Symbol.id == symbol_id)
    )
    symbol = result.scalar_one_or_none()
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")
    
    # Delete image file if exists
    if symbol.image_path and os.path.exists(symbol.image_path):
        os.remove(symbol.image_path)
    
    await db.delete(symbol)
    await db.commit()
    return {"message": "Symbol deleted successfully"}
