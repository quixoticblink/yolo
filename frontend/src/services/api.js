const API_BASE = '/api';

// Get stored token
const getToken = () => localStorage.getItem('token');

// Make authenticated API request
async function apiRequest(endpoint, options = {}) {
    const token = getToken();
    const headers = {
        ...options.headers,
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers,
    });

    if (response.status === 401) {
        localStorage.removeItem('token');
        window.location.href = '/login';
        throw new Error('Unauthorized');
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
        throw new Error(error.detail || 'Request failed');
    }

    // Handle empty responses
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
        return response.json();
    }
    return response;
}

// Auth API
export const authApi = {
    login: async (username, password) => {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);

        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }

        const data = await response.json();
        localStorage.setItem('token', data.access_token);
        return data;
    },

    logout: () => {
        localStorage.removeItem('token');
        window.location.href = '/login';
    },

    getCurrentUser: () => apiRequest('/auth/me'),
};

// Documents API
export const documentsApi = {
    list: () => apiRequest('/documents'),

    get: (id) => apiRequest(`/documents/${id}`),

    getPages: (id) => apiRequest(`/documents/${id}/pages`),

    getPageImageUrl: (docId, pageNum) => `/api/documents/${docId}/pages/${pageNum}/image`,

    upload: async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        return apiRequest('/documents/upload', {
            method: 'POST',
            body: formData,
        });
    },

    delete: (id) => apiRequest(`/documents/${id}`, { method: 'DELETE' }),
};

// Annotations API
export const annotationsApi = {
    listForPage: (pageId) => apiRequest(`/annotations/page/${pageId}`),

    create: (data) => apiRequest('/annotations', {
        method: 'POST',
        body: JSON.stringify(data),
    }),

    update: (id, data) => apiRequest(`/annotations/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
    }),

    delete: (id) => apiRequest(`/annotations/${id}`, { method: 'DELETE' }),

    // Connections
    listConnectionsForPage: (pageId) => apiRequest(`/annotations/connections/page/${pageId}`),

    createConnection: (data) => apiRequest('/annotations/connections', {
        method: 'POST',
        body: JSON.stringify(data),
    }),

    deleteConnection: (id) => apiRequest(`/annotations/connections/${id}`, { method: 'DELETE' }),
};

// Symbols API
export const symbolsApi = {
    list: (category = null) => {
        const params = category ? `?category=${encodeURIComponent(category)}` : '';
        return apiRequest(`/symbols${params}`);
    },

    getCategories: () => apiRequest('/symbols/categories'),

    getImageUrl: (id) => `/api/symbols/${id}/image`,

    extractFromLegends: () => apiRequest('/symbols/extract-from-legends', { method: 'POST' }),
};

// Export API
export const exportApi = {
    downloadXml: async (documentId) => {
        const token = getToken();
        const response = await fetch(`${API_BASE}/export/${documentId}/xml`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });

        if (!response.ok) throw new Error('Export failed');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `document_${documentId}_annotations.xml`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    },

    downloadYoloTraining: async (documentId) => {
        const token = getToken();
        const response = await fetch(`${API_BASE}/export/${documentId}/yolo-training`, {
            headers: { 'Authorization': `Bearer ${token}` },
        });

        if (!response.ok) throw new Error('Export failed');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `document_${documentId}_yolo_dataset.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    },

    downloadJson: async (documentId) => {
        // For JSON, we can just fetch and download or open in new tab
        const data = await apiRequest(`/export/${documentId}/json`);
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `document_${documentId}_digital_twin.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    },

    getYoloFormat: (documentId) => apiRequest(`/export/${documentId}/yolo`),
};

// Models API (AI Model Switching)
export const modelsApi = {
    list: () => apiRequest('/models'),

    activate: (id) => apiRequest(`/models/${id}/activate`, { method: 'POST' }),

    status: () => apiRequest('/models/status'),
};

// Inference API (AI detection)
export const inferenceApi = {
    // Preview detection without saving
    detect: (documentId, pageNumber = 1, confidence = 0.25) =>
        apiRequest(`/inference/${documentId}/detect?page_number=${pageNumber}&confidence=${confidence}`, {
            method: 'POST',
        }),

    // Run detection and create annotations
    autoAnnotate: (documentId, pageNumber = 1, confidence = 0.25) =>
        apiRequest(`/inference/${documentId}/auto-annotate?page_number=${pageNumber}&confidence=${confidence}`, {
            method: 'POST',
        }),

    // Check if AI models are ready
    status: () => apiRequest('/inference/status'),
};
