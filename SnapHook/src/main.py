import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from webhook import router as webhook_router
from certs import ensure_certs

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    ensure_certs()
    yield
    # Shutdown (if needed)

app = FastAPI(title="SnapHook Webhook", lifespan=lifespan)

# Register webhook endpoint
app.include_router(webhook_router, prefix="/mutate")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8443,
        ssl_keyfile="/certs/tls.key",
        ssl_certfile="/certs/tls.crt"
    )
