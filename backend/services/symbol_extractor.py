import asyncio
import re
from pathlib import Path
from typing import List, Dict
import cv2
import numpy as np
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Symbol


async def extract_symbols_from_legends(
    legend_dir: Path,
    output_dir: Path,
    db: AsyncSession
) -> List[Dict]:
    """
    Extract individual symbols from legend PDF files.
    
    This uses contour detection to find symbol boundaries in the legend pages.
    Each legend PDF is expected to have symbols arranged in a grid-like pattern.
    
    Args:
        legend_dir: Directory containing legend PDFs
        output_dir: Directory to save extracted symbol images
        db: Database session
    
    Returns:
        List of extracted symbol info dicts
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError("pdf2image not installed")
    
    extracted_symbols = []
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Category mapping from filename patterns
    category_patterns = {
        "Equipment": ["equipment"],
        "Valves": ["valves", "accessories"],
        "Piping": ["piping"],
        "Instruments": ["instruments"],
        "Motor Controls": ["motor", "profibus"],
        "Control Valves": ["control", "onoff"]
    }
    
    def get_category(filename: str) -> str:
        filename_lower = filename.lower()
        for category, patterns in category_patterns.items():
            if any(pattern in filename_lower for pattern in patterns):
                return category
        return "Other"
    
    def extract_symbols_from_image(image: Image.Image, category: str, base_name: str) -> List[Dict]:
        """Extract individual symbols from a legend page image."""
        # Convert to OpenCV format
        img_array = np.array(image)
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Threshold to get binary image
        _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        symbols = []
        min_area = 500  # Minimum contour area to consider
        max_area = image.width * image.height * 0.1  # Max 10% of page
        
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if min_area < area < max_area:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter out very thin or very wide regions (likely text or lines)
                aspect_ratio = w / h if h > 0 else 0
                if 0.2 < aspect_ratio < 5 and w > 20 and h > 20:
                    # Add padding
                    padding = 5
                    x1 = max(0, x - padding)
                    y1 = max(0, y - padding)
                    x2 = min(image.width, x + w + padding)
                    y2 = min(image.height, y + h + padding)
                    
                    # Crop symbol
                    symbol_img = image.crop((x1, y1, x2, y2))
                    
                    # Save symbol
                    symbol_name = f"{base_name}_symbol_{i+1}"
                    symbol_path = output_dir / f"{symbol_name}.png"
                    symbol_img.save(str(symbol_path), "PNG")
                    
                    symbols.append({
                        "name": symbol_name,
                        "category": category,
                        "image_path": str(symbol_path),
                        "width": x2 - x1,
                        "height": y2 - y1
                    })
        
        return symbols
    
    # Process each legend PDF
    for pdf_path in legend_dir.glob("*.pdf"):
        try:
            category = get_category(pdf_path.name)
            base_name = pdf_path.stem.replace(" ", "_").replace("-", "_")
            
            # Convert PDF to images
            def convert():
                return convert_from_path(str(pdf_path), dpi=200)
            
            loop = asyncio.get_event_loop()
            pages = await loop.run_in_executor(None, convert)
            
            for page_num, page_image in enumerate(pages):
                # Extract symbols from this page
                page_symbols = extract_symbols_from_image(
                    page_image, 
                    category, 
                    f"{base_name}_p{page_num+1}"
                )
                
                # Save to database
                for sym_info in page_symbols:
                    symbol = Symbol(
                        name=sym_info["name"],
                        category=sym_info["category"],
                        image_path=sym_info["image_path"],
                        description=f"Extracted from {pdf_path.name}"
                    )
                    db.add(symbol)
                    extracted_symbols.append(sym_info)
            
            await db.commit()
            
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {e}")
            continue
    
    return extracted_symbols
