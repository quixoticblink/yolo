import { useEffect, useRef, useState, useCallback } from 'react';
import { fabric } from 'fabric';

// Category colors for annotations
const CATEGORY_COLORS = {
    'Equipment': '#8b5cf6',
    'Valves': '#ef4444',
    'Piping': '#3b82f6',
    'Instruments': '#10b981',
    'Motor Controls': '#f59e0b',
    'Control Valves': '#ec4899',
    'Other': '#6b7280'
};

export default function CanvasViewer({
    imageUrl,
    pageWidth,
    pageHeight,
    annotations,
    connections,
    symbols,
    tool,
    selectedAnnotation,
    onAnnotationSelect,
    onAnnotationCreate,
    onAnnotationUpdate,
    onConnectionCreate
}) {
    const containerRef = useRef(null);
    const canvasRef = useRef(null);
    const fabricRef = useRef(null);
    const [zoom, setZoom] = useState(1);
    const [isDrawing, setIsDrawing] = useState(false);
    const [drawStart, setDrawStart] = useState(null);
    const [tempRect, setTempRect] = useState(null);
    const [isPanning, setIsPanning] = useState(false);
    const [lastPanPoint, setLastPanPoint] = useState(null);

    // Initialize Fabric canvas
    useEffect(() => {
        if (!containerRef.current || fabricRef.current) return;

        const canvas = new fabric.Canvas(canvasRef.current, {
            backgroundColor: '#1a1f2e',
            selection: false,
        });

        fabricRef.current = canvas;

        // Handle window resize
        const handleResize = () => {
            const container = containerRef.current;
            if (container) {
                canvas.setDimensions({
                    width: container.clientWidth,
                    height: container.clientHeight
                });
                canvas.renderAll();
            }
        };

        handleResize();
        window.addEventListener('resize', handleResize);

        // Mouse wheel zoom
        canvas.on('mouse:wheel', (opt) => {
            const delta = opt.e.deltaY;
            let newZoom = canvas.getZoom() * (delta > 0 ? 0.9 : 1.1);
            newZoom = Math.min(Math.max(newZoom, 0.1), 5);

            const pointer = canvas.getPointer(opt.e);
            canvas.zoomToPoint({ x: pointer.x, y: pointer.y }, newZoom);
            setZoom(newZoom);

            opt.e.preventDefault();
            opt.e.stopPropagation();
        });

        return () => {
            window.removeEventListener('resize', handleResize);
            canvas.dispose();
            fabricRef.current = null;
        };
    }, []);

    // Load background image
    useEffect(() => {
        const canvas = fabricRef.current;
        if (!canvas || !imageUrl) return;

        // Add auth header to image request
        const token = localStorage.getItem('token');

        fabric.Image.fromURL(
            imageUrl,
            (img) => {
                if (!img.width) return;

                // Calculate scale to fit container
                const container = containerRef.current;
                const scaleX = container.clientWidth / img.width;
                const scaleY = container.clientHeight / img.height;
                const scale = Math.min(scaleX, scaleY, 1) * 0.9;

                img.set({
                    left: (container.clientWidth - img.width * scale) / 2,
                    top: (container.clientHeight - img.height * scale) / 2,
                    scaleX: scale,
                    scaleY: scale,
                    selectable: false,
                    evented: false,
                    name: 'backgroundImage'
                });

                // Remove old background
                const objects = canvas.getObjects();
                const oldBg = objects.find(o => o.name === 'backgroundImage');
                if (oldBg) canvas.remove(oldBg);

                canvas.add(img);
                canvas.sendToBack(img);
                canvas.renderAll();

                setZoom(scale);
            },
            { crossOrigin: 'anonymous' }
        );
    }, [imageUrl]);

    // Render annotations
    useEffect(() => {
        const canvas = fabricRef.current;
        if (!canvas) return;

        // Remove existing annotation objects
        const objects = canvas.getObjects();
        objects.forEach(obj => {
            if (obj.name?.startsWith('annotation-') || obj.name?.startsWith('connection-')) {
                canvas.remove(obj);
            }
        });

        // Get background image for coordinate conversion
        const bgImage = objects.find(o => o.name === 'backgroundImage');
        if (!bgImage) return;

        const scale = bgImage.scaleX;
        const offsetX = bgImage.left;
        const offsetY = bgImage.top;

        // Draw annotations
        annotations.forEach(ann => {
            const symbol = symbols.find(s => s.id === ann.symbol_id);
            const category = symbol?.category || 'Other';
            const color = CATEGORY_COLORS[category] || CATEGORY_COLORS['Other'];

            const rect = new fabric.Rect({
                left: offsetX + ann.x * scale,
                top: offsetY + ann.y * scale,
                width: ann.width * scale,
                height: ann.height * scale,
                fill: 'transparent',
                stroke: color,
                strokeWidth: selectedAnnotation?.id === ann.id ? 3 : 2,
                strokeDashArray: ann.source === 'yolo' ? [5, 5] : null,
                name: `annotation-${ann.id}`,
                annotationId: ann.id,
                selectable: tool === 'select',
                hasControls: tool === 'select',
                hasBorders: true,
            });

            // Add label
            const label = new fabric.Text(ann.tag_id || symbol?.name || `#${ann.id}`, {
                left: offsetX + ann.x * scale,
                top: offsetY + ann.y * scale - 18,
                fontSize: 12,
                fill: color,
                backgroundColor: 'rgba(15, 20, 25, 0.8)',
                padding: 2,
                name: `annotation-${ann.id}-label`,
                selectable: false,
                evented: false
            });

            canvas.add(rect);
            canvas.add(label);

            // Click handler
            rect.on('selected', () => {
                onAnnotationSelect(ann);
            });
        });

        // Draw connections
        connections.forEach(conn => {
            const fromAnn = annotations.find(a => a.id === conn.from_annotation_id);
            const toAnn = annotations.find(a => a.id === conn.to_annotation_id);
            if (!fromAnn || !toAnn) return;

            const fromX = offsetX + (fromAnn.x + fromAnn.width / 2) * scale;
            const fromY = offsetY + (fromAnn.y + fromAnn.height / 2) * scale;
            const toX = offsetX + (toAnn.x + toAnn.width / 2) * scale;
            const toY = offsetY + (toAnn.y + toAnn.height / 2) * scale;

            const line = new fabric.Line([fromX, fromY, toX, toY], {
                stroke: conn.line_type === 'signal' ? '#fbbf24' : '#3b82f6',
                strokeWidth: 2,
                strokeDashArray: conn.line_type === 'signal' ? [5, 5] : null,
                name: `connection-${conn.id}`,
                selectable: false,
                evented: false
            });

            canvas.add(line);
            canvas.sendToBack(line);
        });

        // Keep background at back
        if (bgImage) canvas.sendToBack(bgImage);
        canvas.renderAll();

    }, [annotations, connections, symbols, selectedAnnotation, tool]);

    // Handle drawing tool and panning
    useEffect(() => {
        const canvas = fabricRef.current;
        if (!canvas) return;

        // Set selection mode based on tool
        canvas.selection = tool === 'select';
        canvas.getObjects().forEach(obj => {
            if (obj.name?.startsWith('annotation-') && !obj.name?.includes('-label')) {
                obj.selectable = tool === 'select';
                obj.evented = tool === 'select' || tool === 'line';
            }
        });

        let panning = false;
        let lastPosX = 0;
        let lastPosY = 0;

        const handleMouseDown = (opt) => {
            const e = opt.e;

            // Pan with middle mouse button, space key, or alt key
            if (e.button === 1 || e.altKey || e.spaceKey) {
                panning = true;
                lastPosX = e.clientX;
                lastPosY = e.clientY;
                canvas.setCursor('grab');
                return;
            }

            if (tool !== 'rectangle') return;

            const pointer = canvas.getPointer(opt.e);
            setIsDrawing(true);
            setDrawStart({ x: pointer.x, y: pointer.y });

            const rect = new fabric.Rect({
                left: pointer.x,
                top: pointer.y,
                width: 0,
                height: 0,
                fill: 'rgba(79, 156, 249, 0.2)',
                stroke: '#4f9cf9',
                strokeWidth: 2,
                selectable: false,
                name: 'temp-rect'
            });

            canvas.add(rect);
            setTempRect(rect);
        };

        const handleMouseMove = (opt) => {
            // Handle panning
            if (panning) {
                const e = opt.e;
                const vpt = canvas.viewportTransform;
                vpt[4] += e.clientX - lastPosX;
                vpt[5] += e.clientY - lastPosY;
                lastPosX = e.clientX;
                lastPosY = e.clientY;
                canvas.requestRenderAll();
                return;
            }

            if (!isDrawing || !tempRect || !drawStart) return;

            const pointer = canvas.getPointer(opt.e);
            const width = pointer.x - drawStart.x;
            const height = pointer.y - drawStart.y;

            tempRect.set({
                width: Math.abs(width),
                height: Math.abs(height),
                left: width > 0 ? drawStart.x : pointer.x,
                top: height > 0 ? drawStart.y : pointer.y
            });

            canvas.renderAll();
        };

        const handleMouseUp = () => {
            // Stop panning
            if (panning) {
                panning = false;
                canvas.setCursor('default');
                return;
            }

            if (!isDrawing || !tempRect || !drawStart) return;

            const bgImage = canvas.getObjects().find(o => o.name === 'backgroundImage');
            if (!bgImage) return;

            const scale = bgImage.scaleX;
            const offsetX = bgImage.left;
            const offsetY = bgImage.top;

            // Convert canvas coords to image coords
            const x = (tempRect.left - offsetX) / scale;
            const y = (tempRect.top - offsetY) / scale;
            const width = tempRect.width / scale;
            const height = tempRect.height / scale;

            // Remove temp rect
            canvas.remove(tempRect);
            setTempRect(null);
            setIsDrawing(false);
            setDrawStart(null);

            // Create annotation if big enough
            if (width > 10 && height > 10) {
                onAnnotationCreate({ x, y, width, height });
            }

            canvas.renderAll();
        };

        canvas.on('mouse:down', handleMouseDown);
        canvas.on('mouse:move', handleMouseMove);
        canvas.on('mouse:up', handleMouseUp);

        return () => {
            canvas.off('mouse:down', handleMouseDown);
            canvas.off('mouse:move', handleMouseMove);
            canvas.off('mouse:up', handleMouseUp);
        };
    }, [tool, isDrawing, tempRect, drawStart, onAnnotationCreate]);

    // Zoom controls
    const handleZoomIn = () => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        const newZoom = Math.min(zoom * 1.2, 5);
        canvas.setZoom(newZoom);
        setZoom(newZoom);
    };

    const handleZoomOut = () => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        const newZoom = Math.max(zoom / 1.2, 0.1);
        canvas.setZoom(newZoom);
        setZoom(newZoom);
    };

    const handleResetZoom = () => {
        const canvas = fabricRef.current;
        if (!canvas) return;
        canvas.setZoom(1);
        setZoom(1);
        canvas.setViewportTransform([1, 0, 0, 1, 0, 0]);
    };

    return (
        <div className="canvas-wrapper" ref={containerRef}>
            <canvas ref={canvasRef} />

            <div className="zoom-controls">
                <button className="btn btn-icon" onClick={handleZoomOut} title="Zoom Out">
                    −
                </button>
                <span style={{ padding: '0 8px', fontSize: '0.875rem' }}>
                    {Math.round(zoom * 100)}%
                </span>
                <button className="btn btn-icon" onClick={handleZoomIn} title="Zoom In">
                    +
                </button>
                <button className="btn btn-icon" onClick={handleResetZoom} title="Reset">
                    ⟲
                </button>
            </div>
        </div>
    );
}
