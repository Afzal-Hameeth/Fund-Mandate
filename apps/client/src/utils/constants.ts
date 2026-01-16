export const API = {
    BASE_URL: () => 'http://localhost:8000',
    ENDPOINTS: {
        CHAT: {
            BASE_URL: () => '/chat',
        },
        FUND_MANDATE: {
            PARSE: () => '/api/parse-mandate',
        },
        FILTER: {
            COMPANIES: () => '/api/filter-companies',
        },
        RISK: {
            ANALYZE_CUSTOM: () => '/risk/analyze-custom',
        },
    },
};
