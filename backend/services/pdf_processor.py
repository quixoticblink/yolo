import asyncio
from pathlib import Path
from typing import List, Dict
from PIL import Image
import shutil


async def process_pdf(
    pdf_path: Path,
    document_id: int,
    output_dir: Path,
    dpi: int = 200
) -> List[Dict]:
    """
    Convert PDF pages to PNG images.
    
    Args:
        pdf_path: Path to the PDF file
        document_id: Database document ID
        output_dir: Directory to save rendered images
        dpi: Resolution for rendering
    
    Returns:
        List of dicts with page info (page_number, image_path, width, height)
    """
    # Import pdf2image here to avoid import errors if poppler not installed
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError("pdf2image not installed. Run: pip install pdf2image")
    
    # Create document output directory
    doc_output_dir = output_dir / str(document_id)
    doc_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert PDF to images in a thread pool (blocking operation)
    def convert_pdf():
        return convert_from_path(str(pdf_path), dpi=dpi)
    
    loop = asyncio.get_event_loop()
    images = await loop.run_in_executor(None, convert_pdf)
    
    pages_info = []
    for i, image in enumerate(images):
        page_number = i + 1
        image_filename = f"page_{page_number}.png"
        image_path = doc_output_dir / image_filename
        
        # Save image
        image.save(str(image_path), "PNG")
        
        pages_info.append({
            "page_number": page_number,
            "image_path": str(image_path),
            "width": image.width,
            "height": image.height
        })
    
    return pages_info


async def process_image(
    image_path: Path,
    document_id: int,
    output_dir: Path
) -> List[Dict]:
    """
    Process an image file (copy to rendered directory).
    
    Args:
        image_path: Path to the image file
        document_id: Database document ID
        output_dir: Directory to save rendered images
    
    Returns:
        List with single page info dict
    """
    # Create document output directory
    doc_output_dir = output_dir / str(document_id)
    doc_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy and convert to PNG if needed
    output_path = doc_output_dir / "page_1.png"
    
    with Image.open(image_path) as img:
        # Convert to RGB if necessary (for RGBA or palette images)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.save(str(output_path), "PNG")
        width, height = img.size
    
    return [{
        "page_number": 1,
        "image_path": str(output_path),
        "width": width,
        "height": height
    }]
