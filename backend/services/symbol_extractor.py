import asyncio
from pathlib import Path
from typing import List, Dict
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete
from app.models import Symbol

# Predefined P&ID symbol categories with common symbol names
PID_SYMBOL_LIBRARY = {
    "Equipment": [
        "Pump - Centrifugal",
        "Pump - Positive Displacement", 
        "Compressor",
        "Tank - Vertical",
        "Tank - Horizontal",
        "Vessel - Pressure",
        "Heat Exchanger - Shell & Tube",
        "Heat Exchanger - Plate",
        "Reactor",
        "Column - Distillation",
        "Filter",
        "Blower",
        "Turbine",
        "Motor",
        "Agitator",
    ],
    "Valves": [
        "Gate Valve",
        "Globe Valve", 
        "Ball Valve",
        "Butterfly Valve",
        "Check Valve",
        "Relief Valve",
        "Safety Valve",
        "Needle Valve",
        "Plug Valve",
        "Diaphragm Valve",
        "3-Way Valve",
        "4-Way Valve",
    ],
    "Instruments": [
        "Pressure Indicator (PI)",
        "Pressure Transmitter (PT)",
        "Flow Indicator (FI)",
        "Flow Transmitter (FT)",
        "Flow Controller (FIC)",
        "Level Indicator (LI)",
        "Level Transmitter (LT)",
        "Level Controller (LIC)",
        "Temperature Indicator (TI)",
        "Temperature Transmitter (TT)",
        "Temperature Controller (TIC)",
        "Analyzer (AT)",
        "Controller (C)",
        "Control Valve (CV)",
    ],
    "Control Valves": [
        "Control Valve - Globe",
        "Control Valve - Ball",
        "Control Valve - Butterfly",
        "On/Off Valve",
        "Actuator - Pneumatic",
        "Actuator - Electric",
        "Positioner",
    ],
    "Piping": [
        "Pipe Line",
        "Reducer",
        "Tee",
        "Elbow 90°",
        "Elbow 45°",
        "Flange",
        "Union",
        "Cap",
        "Blind",
        "Spectacle Blind",
        "Strainer",
        "Steam Trap",
    ],
    "Motor Controls": [
        "Motor Starter",
        "VFD (Variable Frequency Drive)",
        "Soft Starter",
        "Contactor",
        "Overload Relay",
        "Emergency Stop",
        "Start/Stop Station",
        "Indicator Light",
    ],
}


async def extract_symbols_from_legends(
    legend_dir: Path,
    output_dir: Path,
    db: AsyncSession
) -> List[Dict]:
    """
    Create symbol palette from predefined P&ID symbol library.
    
    Since automated contour extraction from legend PDFs doesn't work reliably,
    this creates a usable symbol library based on standard P&ID categories.
    
    For production: Train a custom YOLO model to detect symbols directly in P&IDs.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise RuntimeError("pdf2image not installed")
    
    extracted_symbols = []
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Clear existing symbols
    await db.execute(delete(Symbol))
    await db.commit()
    
    # Clear existing symbol images
    for f in output_dir.glob("*.png"):
        try:
            f.unlink()
        except:
            pass
    
    # Detect which categories are present based on legend PDFs
    pdf_files = list(legend_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} legend PDFs to process")
    
    detected_categories = set()
    category_patterns = {
        "Equipment": ["equipment"],
        "Valves": ["valves", "accessories"],
        "Piping": ["piping"],
        "Instruments": ["instruments"],
        "Motor Controls": ["motor", "profibus"],
        "Control Valves": ["control", "onoff"]
    }
    
    for pdf_path in pdf_files:
        filename_lower = pdf_path.name.lower()
        for category, patterns in category_patterns.items():
            if any(pattern in filename_lower for pattern in patterns):
                detected_categories.add(category)
                print(f"  Found category: {category} from {pdf_path.name}")
    
    # If no categories detected, use all
    if not detected_categories:
        detected_categories = set(PID_SYMBOL_LIBRARY.keys())
    
    # Create symbols for detected categories
    symbol_id = 0
    for category in sorted(detected_categories):
        if category not in PID_SYMBOL_LIBRARY:
            continue
            
        symbols = PID_SYMBOL_LIBRARY[category]
        print(f"Creating {len(symbols)} symbols for category: {category}")
        
        for symbol_name in symbols:
            symbol_id += 1
            
            # Create a simple placeholder image with symbol name
            img = create_symbol_placeholder(symbol_name, category)
            image_path = output_dir / f"symbol_{symbol_id:03d}_{category}_{symbol_name.replace(' ', '_').replace('/', '_')[:30]}.png"
            img.save(str(image_path), "PNG")
            
            # Save to database
            symbol = Symbol(
                name=symbol_name,
                category=category,
                image_path=str(image_path),
                description=f"Standard P&ID symbol: {symbol_name}"
            )
            db.add(symbol)
            
            extracted_symbols.append({
                "id": symbol_id,
                "name": symbol_name,
                "category": category,
                "image_path": str(image_path)
            })
    
    await db.commit()
    print(f"Total symbols created: {len(extracted_symbols)}")
    
    return extracted_symbols


def create_symbol_placeholder(name: str, category: str) -> Image.Image:
    """Create a simple placeholder image for a symbol."""
    from PIL import ImageDraw, ImageFont
    
    # Category colors
    colors = {
        "Equipment": "#8b5cf6",
        "Valves": "#ef4444",
        "Piping": "#3b82f6",
        "Instruments": "#10b981",
        "Motor Controls": "#f59e0b",
        "Control Valves": "#ec4899",
    }
    color = colors.get(category, "#6b7280")
    
    # Create image
    size = (100, 80)
    img = Image.new('RGB', size, '#1a1f2e')
    draw = ImageDraw.Draw(img)
    
    # Draw border
    draw.rectangle([2, 2, size[0]-3, size[1]-3], outline=color, width=2)
    
    # Draw symbol abbreviation
    abbrev = "".join(word[0] for word in name.split()[:3]).upper()
    
    # Use default font
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
    except:
        font = ImageFont.load_default()
        small_font = font
    
    # Center the abbreviation
    bbox = draw.textbbox((0, 0), abbrev, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2 - 5
    
    draw.text((x, y), abbrev, fill=color, font=font)
    
    # Draw category at bottom
    cat_abbrev = category[:8]
    bbox = draw.textbbox((0, 0), cat_abbrev, font=small_font)
    cat_width = bbox[2] - bbox[0]
    draw.text(((size[0] - cat_width) // 2, size[1] - 18), cat_abbrev, fill='#9ca3af', font=small_font)
    
    return img
