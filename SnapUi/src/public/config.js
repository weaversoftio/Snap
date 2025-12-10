// Auto-detect API and WebSocket URLs
// If API_URL is empty or not set, use relative paths (for reverse proxy)
// Otherwise, use the configured URL
function getApiUrl() {
    const apiUrl = window.API_URL;
    // Check if placeholder wasn't replaced (fallback for reverse proxy)
    if (!apiUrl || apiUrl === '' || apiUrl === '%REACT_APP_API_URL%' || apiUrl.includes('%REACT_APP_API_URL%')) {
        // Behind reverse proxy - use relative path
        return '';
    }
    return apiUrl;
}

function getWsUrl() {
    const wsUrl = window.WS_URL;
    // Check if placeholder wasn't replaced (fallback for reverse proxy)
    if (!wsUrl || wsUrl === '' || wsUrl === '%REACT_APP_WS_URL%' || wsUrl.includes('%REACT_APP_WS_URL%')) {
        // Behind reverse proxy - auto-detect protocol based on current page
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        return `${protocol}//${host}`;
    }
    return wsUrl;
}

window.ENV = {
    apiUrl: getApiUrl(),
    wsUrl: getWsUrl(),
}