import asyncio
import re
from pathlib import Path
from typing import List, Dict
import cv2
import numpy as np
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from app.models import Symbol


async def extract_symbols_from_legends(
    legend_dir: Path,
    output_dir: Path,
    db: AsyncSession
) -> List[Dict]:
    """
    Extract individual symbols from legend PDF files.
    
    Uses contour detection with parameters tuned for P&ID legend pages
    where symbols are typically 50-500 pixels in size.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError("pdf2image not installed")
    
    extracted_symbols = []
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clear existing symbols and files
    await db.execute(delete(Symbol))
    await db.commit()
    
    # Clear existing symbol images
    for f in output_dir.glob("*.png"):
        f.unlink()
    
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
        """Extract individual symbols from a legend page image using contour detection."""
        # Convert to OpenCV format
        img_array = np.array(image)
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        # Threshold to get binary image - use adaptive threshold for better results
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 5
        )
        
        # Apply morphological operations to clean up
        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        symbols = []
        
        # Symbol size thresholds (in pixels at 200dpi)
        # Typical P&ID symbols are 0.5" to 2" -> 100 to 400 pixels at 200dpi
        min_size = 30   # Minimum width/height
        max_size = 400  # Maximum width/height (symbols shouldn't be larger)
        min_area = 900  # Minimum area (30x30)
        max_area = 160000  # Maximum area (400x400)
        
        # Sort contours by position (top to bottom, left to right) for consistent naming
        contour_data = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            contour_data.append((x, y, w, h, area, contour))
        
        # Sort by y first (rows), then by x (columns)
        contour_data.sort(key=lambda c: (c[1] // 100, c[0]))  # Group by rows of ~100px
        
        symbol_count = 0
        for x, y, w, h, area, contour in contour_data:
            # Filter by size constraints
            if not (min_size <= w <= max_size and min_size <= h <= max_size):
                continue
            if not (min_area <= area <= max_area):
                continue
            
            # Filter out thin rectangles (likely text or lines)
            aspect_ratio = w / h if h > 0 else 0
            if not (0.3 <= aspect_ratio <= 3.0):
                continue
            
            # Check fill ratio - symbols typically have reasonable fill
            bbox_area = w * h
            fill_ratio = area / bbox_area if bbox_area > 0 else 0
            if fill_ratio < 0.05:  # Very sparse, probably not a symbol
                continue
            
            symbol_count += 1
            
            # Add padding
            padding = 10
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(image.width, x + w + padding)
            y2 = min(image.height, y + h + padding)
            
            # Crop symbol
            symbol_img = image.crop((x1, y1, x2, y2))
            
            # Save symbol
            symbol_name = f"{category}_{symbol_count:03d}"
            symbol_path = output_dir / f"{base_name}_{symbol_name}.png"
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
    pdf_files = list(legend_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} legend PDFs to process")
    
    for pdf_path in pdf_files:
        try:
            category = get_category(pdf_path.name)
            base_name = pdf_path.stem.replace(" ", "_").replace("-", "_").replace("&", "and")
            
            print(f"Processing: {pdf_path.name} -> Category: {category}")
            
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
                
                print(f"  Page {page_num+1}: extracted {len(page_symbols)} symbols")
                
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
            import traceback
            traceback.print_exc()
            continue
    
    print(f"Total symbols extracted: {len(extracted_symbols)}")
    return extracted_symbols
