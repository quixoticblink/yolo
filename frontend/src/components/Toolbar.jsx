export default function Toolbar({ tool, onToolChange }) {
    const tools = [
        { id: 'select', label: '🖱️ Select', description: 'Select and move annotations' },
        { id: 'rectangle', label: '⬜ Rectangle', description: 'Draw bounding boxes' },
        { id: 'line', label: '📏 Line', description: 'Draw connections between symbols' },
    ];

    return (
        <div className="toolbar">
            <div className="tool-group">
                {tools.map(t => (
                    <button
                        key={t.id}
                        className={`tool-btn ${tool === t.id ? 'active' : ''}`}
                        onClick={() => onToolChange(t.id)}
                        title={t.description}
                    >
                        {t.label}
                    </button>
                ))}
            </div>

            <div style={{ flex: 1 }} />

            <div style={{
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--spacing-sm)'
            }}>
                <span>💡</span>
                {tool === 'select' && 'Click annotations to select and edit them'}
                {tool === 'rectangle' && 'Click and drag to draw a bounding box'}
                {tool === 'line' && 'Click on two annotations to connect them'}
            </div>
        </div>
    );
}
