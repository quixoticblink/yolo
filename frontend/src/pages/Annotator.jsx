import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { documentsApi, annotationsApi, symbolsApi, exportApi, inferenceApi, modelsApi } from '../services/api';
import CanvasViewer from '../components/CanvasViewer';
import SymbolPalette from '../components/SymbolPalette';
import AnnotationPanel from '../components/AnnotationPanel';
import Toolbar from '../components/Toolbar';

export default function Annotator() {
    const { id } = useParams();
    const navigate = useNavigate();

    const [document, setDocument] = useState(null);
    const [pages, setPages] = useState([]);
    const [currentPage, setCurrentPage] = useState(1);
    const [annotations, setAnnotations] = useState([]);
    const [connections, setConnections] = useState([]);
    const [symbols, setSymbols] = useState([]);
    const [selectedSymbol, setSelectedSymbol] = useState(null);
    const [selectedAnnotation, setSelectedAnnotation] = useState(null);
    const [tool, setTool] = useState('select'); // select, rectangle, line
    const [loading, setLoading] = useState(true);
    const [detecting, setDetecting] = useState(false);
    const [models, setModels] = useState([]);
    const [activeModelId, setActiveModelId] = useState('');
    const [showAnnotations, setShowAnnotations] = useState(true);

    useEffect(() => {
        loadDocument();
        loadSymbols();
        loadModels();
    }, [id]);

    useEffect(() => {
        if (pages.length > 0) {
            loadPageAnnotations();
        }
    }, [currentPage, pages]);

    const loadDocument = async () => {
        try {
            const [doc, pagesData] = await Promise.all([
                documentsApi.get(id),
                documentsApi.getPages(id)
            ]);
            setDocument(doc);
            setPages(pagesData);
        } catch (err) {
            console.error('Error loading document:', err);
            navigate('/');
        } finally {
            setLoading(false);
        }
    };

    const loadSymbols = async () => {
        try {
            const data = await symbolsApi.list();
            setSymbols(data);
        } catch (err) {
            console.error('Error loading symbols:', err);
        }
    };

    const loadModels = async () => {
        try {
            const data = await modelsApi.list();
            setModels(data);
            const active = data.find(m => m.active);
            if (active) setActiveModelId(active.id);
        } catch (err) {
            console.error('Error loading models:', err);
        }
    };

    const handleModelChange = async (e) => {
        const newModelId = e.target.value;
        try {
            await modelsApi.activate(newModelId);
            setActiveModelId(newModelId);
            setModels(models.map(m => ({ ...m, active: m.id === newModelId })));
            alert(`Switched to model: ${newModelId}`);
        } catch (err) {
            alert('Failed to switch model: ' + err.message);
        }
    };

    const loadPageAnnotations = async () => {
        const page = pages.find(p => p.page_number === currentPage);
        if (!page) return;

        try {
            const [anns, conns] = await Promise.all([
                annotationsApi.listForPage(page.id),
                annotationsApi.listConnectionsForPage(page.id)
            ]);
            setAnnotations(anns);
            setConnections(conns);
        } catch (err) {
            console.error('Error loading annotations:', err);
        }
    };

    const handleAnnotationCreate = async (annotationData) => {
        const page = pages.find(p => p.page_number === currentPage);
        if (!page) return;

        try {
            const newAnnotation = await annotationsApi.create({
                page_id: page.id,
                symbol_id: selectedSymbol?.id,
                ...annotationData
            });
            setAnnotations([...annotations, newAnnotation]);
            setSelectedAnnotation(newAnnotation);
        } catch (err) {
            console.error('Error creating annotation:', err);
        }
    };

    const handleAnnotationUpdate = async (annotationId, updateData) => {
        try {
            const updated = await annotationsApi.update(annotationId, updateData);
            setAnnotations(annotations.map(a => a.id === annotationId ? updated : a));
            setSelectedAnnotation(updated);
        } catch (err) {
            console.error('Error updating annotation:', err);
        }
    };

    const handleAnnotationDelete = async (annotationId) => {
        try {
            await annotationsApi.delete(annotationId);
            setAnnotations(annotations.filter(a => a.id !== annotationId));
            setSelectedAnnotation(null);
        } catch (err) {
            console.error('Error deleting annotation:', err);
        }
    };

    const handleConnectionCreate = async (fromId, toId, waypoints) => {
        const page = pages.find(p => p.page_number === currentPage);
        if (!page) return;

        try {
            const newConnection = await annotationsApi.createConnection({
                page_id: page.id,
                from_annotation_id: fromId,
                to_annotation_id: toId,
                waypoints
            });
            setConnections([...connections, newConnection]);
        } catch (err) {
            console.error('Error creating connection:', err);
        }
    };

    const handleExportXml = async () => {
        try {
            await exportApi.downloadXml(id);
        } catch (err) {
            alert('Export failed: ' + err.message);
        }
    };

    const handleAutoDetect = async () => {
        setDetecting(true);
        try {
            const result = await inferenceApi.autoAnnotate(id, currentPage);
            alert(`AI Detection complete! Created ${result.annotations_created} annotations.`);
            // Reload annotations to show new detections
            await loadPageAnnotations();
        } catch (err) {
            alert('AI Detection failed: ' + err.message);
        } finally {
            setDetecting(false);
        }
    };

    const currentPageData = pages.find(p => p.page_number === currentPage);

    if (loading) {
        return (
            <div className="app-container" style={{ alignItems: 'center', justifyContent: 'center' }}>
                <p>Loading document...</p>
            </div>
        );
    }

    return (
        <div className="app-container">
            <header className="header">
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-md)' }}>
                    <button className="btn btn-icon" onClick={() => navigate('/')}>
                        ← Back
                    </button>
                    <h1>{document?.filename}</h1>
                </div>
                <div className="header-actions">
                    {pages.length > 1 && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
                            <button
                                className="btn btn-secondary"
                                disabled={currentPage <= 1}
                                onClick={() => setCurrentPage(p => p - 1)}
                            >
                                ←
                            </button>
                            <span>Page {currentPage} of {pages.length}</span>
                            <button
                                className="btn btn-secondary"
                                disabled={currentPage >= pages.length}
                                onClick={() => setCurrentPage(p => p + 1)}
                            >
                                →
                            </button>
                        </div>
                    )}
                    <div style={{ marginRight: 'var(--spacing-sm)' }}>
                        <select
                            value={activeModelId}
                            onChange={handleModelChange}
                            style={{
                                padding: '6px 10px',
                                borderRadius: '4px',
                                border: '1px solid var(--border-color)',
                                backgroundColor: 'var(--bg-secondary)',
                                color: 'var(--text-primary)',
                                height: '36px'
                            }}
                        >
                            {models.map(m => (
                                <option key={m.id} value={m.id}>
                                    {m.name}
                                </option>
                            ))}
                        </select>
                    </div>
                    <button
                        className={`btn ${showAnnotations ? 'btn-primary' : 'btn-secondary'}`}
                        onClick={() => setShowAnnotations(!showAnnotations)}
                        title="Toggle annotation visibility"
                        style={{ minWidth: '120px' }}
                    >
                        {showAnnotations ? '👁 Hide Boxes' : '👁 Show Boxes'}
                    </button>
                    <button
                        className="btn btn-secondary"
                        onClick={handleAutoDetect}
                        disabled={detecting}
                        title="Run AI to detect symbols and tag IDs"
                    >
                        {detecting ? '🔄 Detecting...' : '🤖 AI Auto-Detect'}
                    </button>
                    <button className="btn btn-primary" onClick={handleExportXml}>
                        📥 Export XML
                    </button>
                </div>
            </header>

            <div className="main-content">
                {/* Left Sidebar - Symbol Palette */}
                <SymbolPalette
                    symbols={symbols}
                    selectedSymbol={selectedSymbol}
                    onSelectSymbol={setSelectedSymbol}
                    onSymbolsExtracted={loadSymbols}
                />

                {/* Center - Canvas */}
                <div className="canvas-container">
                    <Toolbar tool={tool} onToolChange={setTool} />

                    {currentPageData && (
                        <CanvasViewer
                            imageUrl={documentsApi.getPageImageUrl(id, currentPage)}
                            pageWidth={currentPageData.width}
                            pageHeight={currentPageData.height}
                            annotations={annotations}
                            connections={connections}
                            symbols={symbols}
                            tool={tool}
                            selectedAnnotation={selectedAnnotation}
                            onAnnotationSelect={setSelectedAnnotation}
                            onAnnotationCreate={handleAnnotationCreate}
                            onAnnotationUpdate={handleAnnotationUpdate}
                            onConnectionCreate={handleConnectionCreate}
                            showAnnotations={showAnnotations}
                        />
                    )}
                </div>

                {/* Right Sidebar - Properties */}
                <AnnotationPanel
                    annotation={selectedAnnotation}
                    symbols={symbols}
                    onUpdate={handleAnnotationUpdate}
                    onDelete={handleAnnotationDelete}
                />
            </div>
        </div>
    );
}
