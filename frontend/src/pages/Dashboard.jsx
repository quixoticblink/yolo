import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { documentsApi, symbolsApi, authApi } from '../services/api';

export default function Dashboard() {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [user, setUser] = useState(null);
    const fileInputRef = useRef(null);
    const navigate = useNavigate();

    useEffect(() => {
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [docs, userData] = await Promise.all([
                documentsApi.list(),
                authApi.getCurrentUser()
            ]);
            setDocuments(docs);
            setUser(userData);
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

    return (
        <div className="app-container">
            <header className="header">
                <h1>P&ID Digitization Tool</h1>
                <div className="header-actions">
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
