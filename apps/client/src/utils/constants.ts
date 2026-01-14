export const API = {
    BASE_URL: () => 'http://localhost:8000',
    ENDPOINTS: {
        CHAT: {
            BASE_URL: () => '/chat',
        },
            FUND_MANDATE: {
                PARSE: () => '/api/parse-mandate',
            },
    },
};
