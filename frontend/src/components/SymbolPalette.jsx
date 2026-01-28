import { useState, useMemo } from 'react';

export default function SymbolPalette({ symbols, selectedSymbol, onSelectSymbol }) {
    const [searchTerm, setSearchTerm] = useState('');
    const [expandedCategories, setExpandedCategories] = useState({});

    // Group symbols by category
    const groupedSymbols = useMemo(() => {
        const groups = {};
        symbols.forEach(symbol => {
            const category = symbol.category || 'Other';
            if (!groups[category]) {
                groups[category] = [];
            }
            groups[category].push(symbol);
        });
        return groups;
    }, [symbols]);

    // Filter symbols by search term
    const filteredGroups = useMemo(() => {
        if (!searchTerm) return groupedSymbols;

        const filtered = {};
        Object.entries(groupedSymbols).forEach(([category, syms]) => {
            const matching = syms.filter(s =>
                s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                category.toLowerCase().includes(searchTerm.toLowerCase())
            );
            if (matching.length > 0) {
                filtered[category] = matching;
            }
        });
        return filtered;
    }, [groupedSymbols, searchTerm]);

    const toggleCategory = (category) => {
        setExpandedCategories(prev => ({
            ...prev,
            [category]: !prev[category]
        }));
    };

    const categories = Object.keys(filteredGroups).sort();

    return (
        <aside className="sidebar">
            <div className="sidebar-section">
                <h3>Symbol Palette</h3>
                <input
                    type="text"
                    placeholder="Search symbols..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    style={{
                        width: '100%',
                        padding: 'var(--spacing-sm)',
                        background: 'var(--bg-tertiary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-md)',
                        color: 'var(--text-primary)',
                        fontSize: '0.875rem'
                    }}
                />
            </div>

            <div style={{ flex: 1, overflow: 'auto' }}>
                {symbols.length === 0 ? (
                    <div className="sidebar-section">
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                            No symbols extracted yet. Click "Extract Symbols from Legends" on the dashboard.
                        </p>
                    </div>
                ) : categories.length === 0 ? (
                    <div className="sidebar-section">
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                            No symbols match your search.
                        </p>
                    </div>
                ) : (
                    categories.map(category => (
                        <div key={category} className="sidebar-section" style={{ borderBottom: 'none', paddingBottom: 0 }}>
                            <button
                                onClick={() => toggleCategory(category)}
                                style={{
                                    width: '100%',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between',
                                    background: 'none',
                                    border: 'none',
                                    color: 'var(--text-primary)',
                                    cursor: 'pointer',
                                    padding: 'var(--spacing-sm) 0',
                                    fontSize: '0.875rem',
                                    fontWeight: 500
                                }}
                            >
                                <span>{category}</span>
                                <span style={{ color: 'var(--text-muted)' }}>
                                    {expandedCategories[category] ? '▼' : '▶'} ({filteredGroups[category].length})
                                </span>
                            </button>

                            {expandedCategories[category] && (
                                <div className="symbol-grid" style={{ marginTop: 'var(--spacing-sm)' }}>
                                    {filteredGroups[category].map(symbol => (
                                        <div
                                            key={symbol.id}
                                            className={`symbol-item ${selectedSymbol?.id === symbol.id ? 'active' : ''}`}
                                            onClick={() => onSelectSymbol(symbol)}
                                            title={symbol.name}
                                        >
                                            {symbol.image_path ? (
                                                <img
                                                    src={`/api/symbols/${symbol.id}/image`}
                                                    alt={symbol.name}
                                                    onError={(e) => {
                                                        e.target.style.display = 'none';
                                                        e.target.nextSibling.style.display = 'block';
                                                    }}
                                                />
                                            ) : null}
                                            <span
                                                style={{
                                                    fontSize: '0.625rem',
                                                    textAlign: 'center',
                                                    display: symbol.image_path ? 'none' : 'block'
                                                }}
                                            >
                                                {symbol.name.slice(0, 10)}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))
                )}
            </div>

            {selectedSymbol && (
                <div className="sidebar-section" style={{
                    background: 'var(--bg-tertiary)',
                    margin: 'var(--spacing-sm)',
                    borderRadius: 'var(--radius-md)'
                }}>
                    <h3>Selected Symbol</h3>
                    <p style={{ fontSize: '0.875rem', marginTop: 'var(--spacing-xs)' }}>
                        {selectedSymbol.name}
                    </p>
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {selectedSymbol.category}
                    </p>
                    <button
                        className="btn btn-secondary"
                        onClick={() => onSelectSymbol(null)}
                        style={{ marginTop: 'var(--spacing-sm)', width: '100%' }}
                    >
                        Clear Selection
                    </button>
                </div>
            )}
        </aside>
    );
}
