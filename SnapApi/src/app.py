import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging
import os
import kopf
import urllib3
import flows.snap_init

# Suppress urllib3 InsecureRequestWarning globally
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
flows.snap_init.snap_init()

# Import operator functionality - this registers the kopf event handlers with the framework
import classes.operator_watcher  # noqa: F401

# Load watcher configurations on startup - will be called in lifespan function

# SnapHook configurations will be loaded on FastAPI startup event


# Import routers
from routes.registry import router as registry_router
from routes.checkpoint import router as checkpoint_router
from routes.pod import router as pod_router
from routes.automation import router as automation_router
from routes.kubectl import router as kubectl_router
from routes.config import router as config_router
from routes.cluster import router as cluster_router
from routes.cluster_cache import router as cluster_cache_router
from routes.download import router as cluster_download
from routes.websocket import router as websocket_router
from routes.imagetag import router as imagetag_router
from routes.operator import router as operator_router
from routes.cluster_status import router as cluster_status_router
from routes.webhooks import router as webhooks_router
from routes.snaphook import router as snaphook_router
from routes.docs import router as docs_router
from routes.rbac import router as rbac_router

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
checkpoint_path = os.path.join(BASE_DIR, 'checkpoints')
origins_env = os.getenv("SNAP_ORIGINS", "http://localhost,http://localhost:3000,*")
origins = origins_env.split(",")

# Reverse proxy middleware to ensure X-Forwarded-* headers are available
# Note: uvicorn's --proxy-headers flag makes uvicorn trust these headers
# This middleware ensures they're available for CORS and other middleware
class ReverseProxyMiddleware(BaseHTTPMiddleware):
    """Middleware to ensure reverse proxy headers are available for downstream processing."""
    async def dispatch(self, request: Request, call_next):
        # The --proxy-headers flag in uvicorn already handles X-Forwarded-* headers
        # This middleware ensures the headers are available for CORS and logging
        # FastAPI/Starlette will use these headers when --proxy-headers is enabled
        response = await call_next(request)
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events."""
    # Startup
    log_info(logger, 'SnapApi', 'Application Start', f'Starting SnapAPI application...')
    
    # Load SnapWatcher configurations and auto-start them
    try:
        from routes.operator import watcher_instances
        from flows.config.watcher.load_snapwatchers_on_startup import load_snapwatchers_on_startup
        await load_snapwatchers_on_startup(watcher_instances)
        log_success(logger, 'SnapApi', 'Configuration Loading', f'SnapWatcher configurations loaded and auto-started successfully')
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to load and start SnapWatcher configurations: {e}')
    
    # Initialize shared HTTPS server
    try:
        from classes.shared_https_server import shared_https_server
        if shared_https_server.start_shared_server():
            log_success(logger, 'SnapApi', 'HTTPS Server', f'Shared HTTPS server started successfully')
        else:
            log_error(logger, 'SnapApi', 'Error Handling', f'Failed to start shared HTTPS server')
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to initialize shared HTTPS server: {e}')
    
    # Load SnapHook configurations on startup
    try:
        from routes.snaphook import snaphook_instances
        from flows.config.hook.load_snaphooks_on_startup import load_snaphooks_on_startup
        await load_snaphooks_on_startup(snaphook_instances)
        log_success(logger, 'SnapApi', 'Configuration Loading', f'SnapHook configurations loaded successfully')
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Failed to load SnapHook configurations: {e}')
    
    yield
    
    # Shutdown
    log_info(logger, 'SnapApi', 'Application Stop', f'Shutting down SnapAPI application...')
    
    # Cleanup WebSocket logging handler
    try:
        from classes.websocket_log_handler import cleanup_websocket_logging
        cleanup_websocket_logging()
        log_success(logger, 'SnapApi', 'Cleanup', f'WebSocket logging handler cleaned up successfully')
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Error cleaning up WebSocket logging handler: {e}')
    
    # Stop shared HTTPS server
    try:
        from classes.shared_https_server import shared_https_server
        if shared_https_server.stop_shared_server():
            log_success(logger, 'SnapApi', 'HTTPS Server', f'Shared HTTPS server stopped successfully')
        else:
            log_warning(logger, 'SnapApi', 'HTTPS Server', f'Failed to stop shared HTTPS server gracefully')
    except Exception as e:
        log_error(logger, 'SnapApi', 'Error Handling', f'Error stopping shared HTTPS server: {e}')

# Initialize FastAPI app with lifespan
app = FastAPI(lifespan=lifespan)

# Add reverse proxy middleware first (before CORS)
app.add_middleware(ReverseProxyMiddleware)

# CORS middleware - allow all origins if "*" is in the list, otherwise use specified origins
# This supports reverse proxy scenarios where the origin may vary
allow_all_origins = "*" in origins
cors_origins = ["*"] if allow_all_origins else origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True if not allow_all_origins else False,  # Can't use credentials with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("automation_api")
logger.setLevel(logging.INFO)  # Ensure automation_api logger accepts INFO, WARNING, ERROR
logging.getLogger().setLevel(logging.ERROR)  # Root logger
logging.getLogger("multipart.multipart").setLevel(logging.ERROR)  # Full path to multipart logger
logging.getLogger("multipart.multipart.parse").setLevel(logging.ERROR)  # Parser specific logger
logging.getLogger("uvicorn").setLevel(logging.ERROR)

# Filter out /logs/stream, /docs, and /cluster/status/report access logs
class FilterLogsStream(logging.Filter):
    """Filter to suppress noisy access logs."""
    def filter(self, record):
        # Check if the log message contains paths we want to filter
        message = record.getMessage()
        filtered_paths = ["/logs/stream", "/docs", "/cluster/status/report"]
        return not any(path in message for path in filtered_paths)

# Apply filter to uvicorn.access logger and set level to WARNING to reduce noise
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.setLevel(logging.WARNING)
uvicorn_access_logger.addFilter(FilterLogsStream())

# Setup WebSocket logging handler
from classes.websocket_log_handler import setup_websocket_logging, log_info, log_error, log_warning, log_success
from routes.websocket import broadcast_progress

# Initialize WebSocket logging handler
websocket_log_handler = setup_websocket_logging(broadcast_progress)

# Set the buffer function for the handler after routes are loaded
from routes.logs import add_log_to_buffer
websocket_log_handler.set_add_log_to_buffer_func(add_log_to_buffer)

# Verify handler is working - send a test log
logger.info("SnapApi: WebSocket log handler initialized and ready")
print("[SnapApi] WebSocket log handler setup complete. Buffer function:", "set" if websocket_log_handler._add_log_to_buffer_func else "NOT SET")

# Include routers
app.include_router(registry_router, prefix="/registry", tags=["registry"])
app.include_router(cluster_router, prefix="/cluster", tags=["cluster"])
app.include_router(cluster_cache_router, prefix="/config/clusterCache", tags=["clusterCache"])
app.include_router(cluster_status_router, prefix="/cluster/status", tags=["clusterStatus"])
app.include_router(checkpoint_router, prefix="/checkpoint", tags=["checkpoint"])
app.include_router(pod_router, prefix="/pod", tags=["pod"])
app.include_router(automation_router, prefix="/automation", tags=["automation"])
app.include_router(kubectl_router, prefix="/kubectl", tags=["kubectl"])
app.include_router(config_router, prefix="/config", tags=["config"])
app.include_router(cluster_download, prefix="/download", tags=["download"])
app.include_router(websocket_router, prefix="/ws", tags=["websocket"])
app.include_router(imagetag_router, prefix="/imagetag", tags=["imagetag"])
app.include_router(operator_router, prefix="/operator", tags=["operator"])
app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
app.include_router(snaphook_router, tags=["snaphook"])
app.include_router(docs_router, prefix="/docs", tags=["docs"])
app.include_router(rbac_router, prefix="/rbac", tags=["rbac"])

# Import and include logs router
from routes.logs import router as logs_router
app.include_router(logs_router, prefix="/logs", tags=["logs"])

# SnapWatcher operator will be started via API request
