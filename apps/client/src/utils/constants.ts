export const API = {
    BASE_URL: () => 'http://localhost:8000',
    // Helper to build absolute HTTP URLs and websocket URLs
    makeUrl: (path: string) => `${API.BASE_URL()}${path}`,
    wsUrl: (path: string) => {
        const base = API.BASE_URL();
        const host = base.replace(/^https?:\/\//, '');
        const protocol = base.startsWith('https') ? 'wss:' : 'ws:';
        return `${protocol}//${host}${path}`;
    },
    ENDPOINTS: {
        CHAT: {
            BASE_URL: () => '/chat',
        },
        FUND_MANDATE: {
            PARSE: () => '/api/parse-mandate',
            UPLOAD: () => '/api/parse-mandate-upload',
            WS_PARSE: (connId: string) => `/api/ws/parse-mandate/option2/${connId}`,
        },
        FILTER: {
            COMPANIES: () => '/api/filter-companies',
            FILTER_COMPANIES_WS: (connId: string) => `/api/ws/filter-companies/${connId}`,
            SCREEN_WS: () => '/api/ws/screen',
        },
        RISK: {
            ANALYZE_CUSTOM: () => '/risk/analyze-custom',
            ANALYZE_STREAM: () => '/risk/analyze',
        },
    },
};
