import { useState, useEffect } from 'react';

export default function AnnotationPanel({ annotation, symbols, onUpdate, onDelete }) {
    const [tagId, setTagId] = useState('');
    const [symbolId, setSymbolId] = useState('');
    const [attributes, setAttributes] = useState([]);
    const [newAttrKey, setNewAttrKey] = useState('');
    const [newAttrValue, setNewAttrValue] = useState('');

    useEffect(() => {
        if (annotation) {
            setTagId(annotation.tag_id || '');
            setSymbolId(annotation.symbol_id?.toString() || '');
            setAttributes(Object.entries(annotation.attributes || {}));
        } else {
            setTagId('');
            setSymbolId('');
            setAttributes([]);
        }
    }, [annotation]);

    const handleSave = () => {
        if (!annotation) return;

        const attrObj = {};
        attributes.forEach(([key, value]) => {
            if (key) attrObj[key] = value;
        });

        onUpdate(annotation.id, {
            tag_id: tagId || null,
            symbol_id: symbolId ? parseInt(symbolId) : null,
            attributes: attrObj
        });
    };

    const handleAddAttribute = () => {
        if (!newAttrKey) return;
        setAttributes([...attributes, [newAttrKey, newAttrValue]]);
        setNewAttrKey('');
        setNewAttrValue('');
    };

    const handleRemoveAttribute = (index) => {
        setAttributes(attributes.filter((_, i) => i !== index));
    };

    const handleDelete = () => {
        if (!annotation) return;
        if (confirm('Delete this annotation?')) {
            onDelete(annotation.id);
        }
    };

    // Group symbols by category for select
    const groupedSymbols = symbols.reduce((acc, sym) => {
        const cat = sym.category || 'Other';
        if (!acc[cat]) acc[cat] = [];
        acc[cat].push(sym);
        return acc;
    }, {});

    if (!annotation) {
        return (
            <aside className="properties-panel">
                <div style={{
                    height: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--text-muted)',
                    textAlign: 'center',
                    padding: 'var(--spacing-lg)'
                }}>
                    <div>
                        <p style={{ fontSize: '2rem', marginBottom: 'var(--spacing-md)' }}>📐</p>
                        <p>Select an annotation to view and edit its properties</p>
                    </div>
                </div>
            </aside>
        );
    }

    return (
        <aside className="properties-panel">
            <h3 style={{
                marginBottom: 'var(--spacing-lg)',
                padding: 'var(--spacing-sm)',
                background: 'var(--bg-tertiary)',
                borderRadius: 'var(--radius-md)',
                textAlign: 'center'
            }}>
                Annotation #{annotation.id}
            </h3>

            {/* Detection source badge */}
            {annotation.source !== 'manual' && (
                <div style={{
                    padding: 'var(--spacing-xs) var(--spacing-sm)',
                    background: annotation.source === 'yolo' ? 'rgba(79, 156, 249, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                    border: `1px solid ${annotation.source === 'yolo' ? 'var(--accent-primary)' : 'var(--accent-success)'}`,
                    borderRadius: 'var(--radius-md)',
                    marginBottom: 'var(--spacing-md)',
                    fontSize: '0.75rem',
                    textAlign: 'center'
                }}>
                    AI Detected ({annotation.source}) • Confidence: {Math.round((annotation.confidence || 0) * 100)}%
                </div>
            )}

            {/* Tag ID */}
            <div className="property-group">
                <label>Tag ID</label>
                <input
                    type="text"
                    value={tagId}
                    onChange={(e) => setTagId(e.target.value)}
                    placeholder="e.g., FIC-101"
                />
            </div>

            {/* Symbol Type */}
            <div className="property-group">
                <label>Symbol Type</label>
                <select
                    value={symbolId}
                    onChange={(e) => setSymbolId(e.target.value)}
                >
                    <option value="">-- Select Symbol --</option>
                    {Object.entries(groupedSymbols).map(([category, syms]) => (
                        <optgroup key={category} label={category}>
                            {syms.map(sym => (
                                <option key={sym.id} value={sym.id}>
                                    {sym.name}
                                </option>
                            ))}
                        </optgroup>
                    ))}
                </select>
            </div>

            {/* Bounding Box (read-only) */}
            <div className="property-group">
                <label>Bounding Box</label>
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: 'var(--spacing-xs)',
                    fontSize: '0.75rem',
                    color: 'var(--text-muted)'
                }}>
                    <span>X: {Math.round(annotation.x)}</span>
                    <span>Y: {Math.round(annotation.y)}</span>
                    <span>W: {Math.round(annotation.width)}</span>
                    <span>H: {Math.round(annotation.height)}</span>
                </div>
            </div>

            {/* Custom Attributes */}
            <div className="property-group">
                <label>Attributes</label>
                {attributes.map(([key, value], index) => (
                    <div key={index} style={{
                        display: 'flex',
                        gap: 'var(--spacing-xs)',
                        marginBottom: 'var(--spacing-xs)'
                    }}>
                        <input
                            type="text"
                            value={key}
                            onChange={(e) => {
                                const newAttrs = [...attributes];
                                newAttrs[index][0] = e.target.value;
                                setAttributes(newAttrs);
                            }}
                            placeholder="Key"
                            style={{ flex: 1 }}
                        />
                        <input
                            type="text"
                            value={value}
                            onChange={(e) => {
                                const newAttrs = [...attributes];
                                newAttrs[index][1] = e.target.value;
                                setAttributes(newAttrs);
                            }}
                            placeholder="Value"
                            style={{ flex: 1 }}
                        />
                        <button
                            className="btn btn-icon"
                            onClick={() => handleRemoveAttribute(index)}
                            style={{ color: 'var(--accent-danger)' }}
                        >
                            ×
                        </button>
                    </div>
                ))}

                <div style={{ display: 'flex', gap: 'var(--spacing-xs)', marginTop: 'var(--spacing-sm)' }}>
                    <input
                        type="text"
                        value={newAttrKey}
                        onChange={(e) => setNewAttrKey(e.target.value)}
                        placeholder="New key"
                        style={{ flex: 1 }}
                    />
                    <input
                        type="text"
                        value={newAttrValue}
                        onChange={(e) => setNewAttrValue(e.target.value)}
                        placeholder="Value"
                        style={{ flex: 1 }}
                    />
                    <button className="btn btn-secondary" onClick={handleAddAttribute}>
                        +
                    </button>
                </div>
            </div>

            {/* Actions */}
            <div style={{
                marginTop: 'auto',
                paddingTop: 'var(--spacing-lg)',
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--spacing-sm)'
            }}>
                <button className="btn btn-primary" onClick={handleSave} style={{ width: '100%' }}>
                    Save Changes
                </button>
                <button className="btn btn-danger" onClick={handleDelete} style={{ width: '100%' }}>
                    Delete Annotation
                </button>
            </div>
        </aside>
    );
}
