from datetime import datetime
from xml.etree import ElementTree as ET
from xml.dom import minidom
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Document


def generate_xml(document: "Document", annotated_by: str) -> str:
    """
    Generate XML export of document annotations.
    
    Args:
        document: Document model with pages, annotations, and connections loaded
        annotated_by: Username of the annotator
    
    Returns:
        XML string
    """
    # Create root element with namespace
    root = ET.Element("PIDDocument")
    root.set("version", "1.0")
    root.set("xmlns", "http://keppel.com/pid/v1")
    
    # Metadata
    metadata = ET.SubElement(root, "Metadata")
    ET.SubElement(metadata, "DocumentId").text = str(document.id)
    ET.SubElement(metadata, "SourceFile").text = document.filename
    ET.SubElement(metadata, "ExportDate").text = datetime.utcnow().isoformat() + "Z"
    ET.SubElement(metadata, "AnnotatedBy").text = annotated_by
    ET.SubElement(metadata, "PageCount").text = str(document.page_count)
    
    # Pages
    for page in sorted(document.pages, key=lambda p: p.page_number):
        page_elem = ET.SubElement(root, "Page")
        page_elem.set("number", str(page.page_number))
        page_elem.set("width", str(page.width))
        page_elem.set("height", str(page.height))
        
        # Symbols/Annotations
        symbols_elem = ET.SubElement(page_elem, "Symbols")
        for ann in page.annotations:
            symbol_elem = ET.SubElement(symbols_elem, "Symbol")
            symbol_elem.set("id", str(ann.id))
            
            if ann.symbol:
                symbol_elem.set("type", ann.symbol.name)
                symbol_elem.set("category", ann.symbol.category)
            
            # Bounding box
            bbox = ET.SubElement(symbol_elem, "BoundingBox")
            bbox.set("x", str(round(ann.x, 2)))
            bbox.set("y", str(round(ann.y, 2)))
            bbox.set("width", str(round(ann.width, 2)))
            bbox.set("height", str(round(ann.height, 2)))
            
            # Tag ID
            if ann.tag_id:
                ET.SubElement(symbol_elem, "TagId").text = ann.tag_id
            
            # Attributes
            if ann.attributes:
                attrs_elem = ET.SubElement(symbol_elem, "Attributes")
                for key, value in ann.attributes.items():
                    attr_elem = ET.SubElement(attrs_elem, "Attribute")
                    attr_elem.set("key", key)
                    attr_elem.text = str(value)
            
            # Detection info
            if ann.confidence is not None:
                det_elem = ET.SubElement(symbol_elem, "Detection")
                det_elem.set("source", ann.source)
                det_elem.set("confidence", str(round(ann.confidence, 3)))
        
        # Connections
        connections_elem = ET.SubElement(page_elem, "Connections")
        for conn in page.connections:
            conn_elem = ET.SubElement(connections_elem, "Connection")
            conn_elem.set("id", str(conn.id))
            conn_elem.set("type", conn.line_type)
            
            ET.SubElement(conn_elem, "From").set("symbolId", str(conn.from_annotation_id))
            ET.SubElement(conn_elem, "To").set("symbolId", str(conn.to_annotation_id))
            
            if conn.waypoints:
                waypoints_elem = ET.SubElement(conn_elem, "Waypoints")
                for point in conn.waypoints:
                    point_elem = ET.SubElement(waypoints_elem, "Point")
                    point_elem.set("x", str(round(point.get("x", 0), 2)))
                    point_elem.set("y", str(round(point.get("y", 0), 2)))
    
    # Pretty print
    xml_str = ET.tostring(root, encoding="unicode")
    dom = minidom.parseString(xml_str)
    return dom.toprettyxml(indent="  ")
