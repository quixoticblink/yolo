import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { documentsApi, symbolsApi, authApi, modelsApi, exportApi } from '../services/api';

export default function Dashboard() {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [user, setUser] = useState(null);
    const [models, setModels] = useState([]);
    const [activeModelId, setActiveModelId] = useState('');
    const fileInputRef = useRef(null);
    const navigate = useNavigate();

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [docs, userData, modelsData] = await Promise.all([
                documentsApi.list(),
                authApi.getCurrentUser(),
                modelsApi.list()
            ]);
            setDocuments(docs);
            setUser(userData);
            setModels(modelsData);
            const active = modelsData.find(m => m.active);
            if (active) setActiveModelId(active.id);
        } catch (err) {
            console.error('Error loading data:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        setUploading(true);
        try {
            const doc = await documentsApi.upload(file);
            setDocuments([doc, ...documents]);
            navigate(`/annotate/${doc.id}`);
        } catch (err) {
            alert('Upload failed: ' + err.message);
        } finally {
            setUploading(false);
        }
    };

    const handleExtractSymbols = async () => {
        try {
            const result = await symbolsApi.extractFromLegends();
            alert(`Extracted ${result.symbols.length} symbols from legend PDFs`);
        } catch (err) {
            alert('Symbol extraction failed: ' + err.message);
        }
    };

    const handleDelete = async (id, e) => {
        e.stopPropagation();
        if (!confirm('Delete this document?')) return;

        try {
            await documentsApi.delete(id);
            setDocuments(documents.filter(d => d.id !== id));
        } catch (err) {
            alert('Delete failed: ' + err.message);
        }
    };

    const handleModelChange = async (e) => {
        const newModelId = e.target.value;
        try {
            await modelsApi.activate(newModelId);
            setActiveModelId(newModelId);
            // Refresh list to update active flags if needed, but local state is arguably enough
            const updatedModels = models.map(m => ({
                ...m,
                active: m.id === newModelId
            }));
            setModels(updatedModels);
            alert(`Switched to model: ${newModelId}`);
        } catch (err) {
            alert('Failed to switch model: ' + err.message);
        }
    };

    const handleExportYolo = async (id, e) => {
        e.stopPropagation();
        try {
            await exportApi.downloadYoloTraining(id);
        } catch (err) {
            alert('Export failed: ' + err.message);
        }
    };

    const handleExportJson = async (id, e) => {
        e.stopPropagation();
        try {
            await exportApi.downloadJson(id);
        } catch (err) {
            alert('Export failed: ' + err.message);
        }
    };

    return (
        <div className="app-container">
            <header className="header">
                <h1>P&ID Digitization Tool</h1>
                <div className="header-actions">
                    <div style={{ marginRight: 'var(--spacing-md)' }}>
                        <select
                            value={activeModelId}
                            onChange={handleModelChange}
                            style={{
                                padding: '4px 8px',
                                borderRadius: '4px',
                                border: '1px solid var(--border-color)',
                                backgroundColor: 'var(--bg-secondary)',
                                color: 'var(--text-primary)'
                            }}
                        >
                            {models.map(m => (
                                <option key={m.id} value={m.id}>
                                    {m.name}
                                </option>
                            ))}
                        </select>
                    </div>
                    <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                        {user?.username}
                    </span>
                    <button className="btn btn-secondary" onClick={() => authApi.logout()}>
                        Logout
                    </button>
                </div>
            </header>

            <main style={{ padding: 'var(--spacing-xl)', maxWidth: '1200px', margin: '0 auto', width: '100%' }}>
                {/* Upload Section */}
                <div style={{ marginBottom: 'var(--spacing-xl)' }}>
                    <h2 style={{ marginBottom: 'var(--spacing-md)' }}>Upload Document</h2>
                    <div
                        className="upload-area"
                        onClick={() => fileInputRef.current?.click()}
                    >
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp"
                            onChange={handleUpload}
                            style={{ display: 'none' }}
                        />
                        {uploading ? (
                            <p>Uploading and processing...</p>
                        ) : (
                            <>
                                <p style={{ fontSize: '1.125rem', marginBottom: 'var(--spacing-sm)' }}>
                                    📄 Click or drag to upload P&ID/PFD
                                </p>
                                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                                    Supports PDF, PNG, JPG, TIFF
                                </p>
                            </>
                        )}
                    </div>
                </div>

                {/* Actions */}
                <div style={{ marginBottom: 'var(--spacing-xl)', display: 'flex', gap: 'var(--spacing-md)' }}>
                    <button className="btn btn-secondary" onClick={handleExtractSymbols}>
                        🔧 Extract Symbols from Legends
                    </button>
                </div>

                {/* Documents List */}
                <div>
                    <h2 style={{ marginBottom: 'var(--spacing-md)' }}>Documents</h2>
                    {loading ? (
                        <p style={{ color: 'var(--text-muted)' }}>Loading...</p>
                    ) : documents.length === 0 ? (
                        <p style={{ color: 'var(--text-muted)' }}>No documents uploaded yet</p>
                    ) : (
                        <div className="document-list">
                            {documents.map(doc => (
                                <div
                                    key={doc.id}
                                    className="document-item"
                                    onClick={() => navigate(`/annotate/${doc.id}`)}
                                >
                                    <div className="document-info">
                                        <h4>{doc.filename}</h4>
                                        <p>
                                            {doc.page_count} page{doc.page_count !== 1 ? 's' : ''} •
                                            Status: <span style={{
                                                color: doc.status === 'ready' ? 'var(--accent-success)' :
                                                    doc.status === 'error' ? 'var(--accent-danger)' : 'var(--accent-warning)'
                                            }}>{doc.status}</span> •
                                            {new Date(doc.uploaded_at).toLocaleDateString()}
                                        </p>
                                    </div>
                                    <div style={{ display: 'flex', gap: 'var(--spacing-sm)' }}>
                                        <button
                                            className="btn btn-secondary"
                                            onClick={(e) => handleExportJson(doc.id, e)}
                                            title="Export Digital Twin JSON"
                                        >
                                            📄 JSON
                                        </button>
                                        <button
                                            className="btn btn-secondary"
                                            onClick={(e) => handleExportYolo(doc.id, e)}
                                            title="Export YOLO Training Data"
                                        >
                                            📥 YOLO
                                        </button>
                                        <button
                                            className="btn btn-primary"
                                            onClick={(e) => { e.stopPropagation(); navigate(`/annotate/${doc.id}`); }}
                                        >
                                            Annotate
                                        </button>
                                        <button
                                            className="btn btn-danger"
                                            onClick={(e) => handleDelete(doc.id, e)}
                                        >
                                            Delete
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </main>
        </div>
    );
}
