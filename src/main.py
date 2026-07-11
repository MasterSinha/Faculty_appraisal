from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from sqlalchemy.exc import SQLAlchemyError
import logging
import time
import os
import traceback
import pathlib
from .api.v1 import router as api_v1_router
from .setup.admin_views import create_admin
from .setup.errors import AppError

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Faculty Appraisal API",
    description="Final Backend API for Faculty Appraisal System",
    version="2.0.0",
)

# Mount Local Storage (for local migration support)
# This allows serving files from the configured local directory via http://backend/uploads/...
local_storage_dir = os.getenv("LOCAL_STORAGE_DIR", "./uploads")
if os.path.exists(local_storage_dir):
    app.mount("/uploads", StaticFiles(directory=local_storage_dir), name="uploads")
elif os.getenv("USE_LOCAL_STORAGE", "false").replace('"', '').replace("'", "").lower() == "true":
    os.makedirs(local_storage_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=local_storage_dir), name="uploads")

# CORS Configuration
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8000",
    "http://localhost:5174",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8000",
    "http://10.10.53.122:8000",
    "http://10.10.53.122:3000",
    "http://10.100.0.23:3000",
    "http://10.100.0.23",
    "http://pbas.dypiu.ac.in",
    "https://pbas.dypiu.ac.in",
    "http://pbas.dypiu.ac.in:3000",
    "https://pbas.dypiu.ac.in:3000",
    "https://facultyappraisal-495011.web.app",
    "https://faculty-appraisal-frontend-376777978967.asia-south1.run.app",
    "https://faculty-appraisal-frontend-919405994318.asia-south1.run.app"
]

# Load additional origins from environment variables to support dynamic local IPs (like the 150.x.x.x public IP)
for env_var in ["FRONTEND_URL", "CORS_ALLOWED_ORIGINS"]:
    env_val = os.getenv(env_var)
    if env_val:
        for origin_uri in env_val.split(","):
            cleaned = origin_uri.strip().rstrip("/")
            if cleaned and cleaned not in ALLOWED_ORIGINS:
                ALLOWED_ORIGINS.append(cleaned)

# Trust X-Forwarded-Proto from Cloud Run's load balancer so that URL generation
# (and sqladmin's post-login redirects) use https:// instead of http://.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"],
)

# SessionMiddleware is required by sqladmin for its /admin web UI login flow.
_is_production = os.getenv("ENVIRONMENT", "development").lower() == "production"
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("JWT_SECRET_KEY", "fallback-secret-change-in-production"),
    https_only=_is_production,
)

def _cors_headers(request: Request) -> dict:
    """Return CORS headers for the request's origin, if it is allowed."""
    origin = request.headers.get("origin", "")
    if origin in ALLOWED_ORIGINS:
        return {"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true"}
    return {}

# Logging & Latency Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    logger.info(f"Incoming request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"Request {request.method} {request.url.path} completed in {process_time:.4f}s")
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        # Return JSONResponse instead of re-raising — re-raising inside BaseHTTPMiddleware
        # bypasses CORSMiddleware's response wrapper, making 500 errors appear as CORS errors.
        logger.error(f"Request failed: {request.method} {request.url.path} - Error: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "user_message": "An unexpected error occurred. Please try again or contact support.",
                "detail": str(e),
                "type": type(e).__name__,
                "path": request.url.path,
            },
            headers=_cors_headers(request),
        )

# ---------------------------------------------------------------------------
# Exception handlers
#
# Every handler emits the same two-field shape:
#   user_message  — plain-English sentence safe to display in the UI
#   detail        — technical description for the network tab / GCP logs
#
# 4xx errors (HTTPException): detail IS already user-friendly, so both fields
# carry the same text.  500s use a generic user_message and put the raw
# exception info only in detail so internal implementation details never leak.
# ---------------------------------------------------------------------------

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "user_message": exc.detail,
            "detail": exc.detail,
        },
        headers={**_cors_headers(request), **(exc.headers or {})},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "user_message": "The request data is invalid. Please check the highlighted fields and try again.",
            "detail": exc.errors(),
        },
        headers=_cors_headers(request),
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.error(
        f"AppError [{exc.status_code}] on {request.method} {request.url.path}: {exc.detail}"
    )
    if exc.status_code >= 500:
        logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "user_message": exc.user_message,
            "detail": exc.detail,
            "path": request.url.path,
        },
        headers=_cors_headers(request),
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error on {request.method} {request.url.path}: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "user_message": "A database error occurred. Please try again or contact support.",
            "detail": str(exc),
            "type": "SQLAlchemyError",
            "path": request.url.path,
        },
        headers=_cors_headers(request),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled {type(exc).__name__} on {request.method} {request.url.path}: {exc}"
    )
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "user_message": "An unexpected error occurred. Please try again or contact support.",
            "detail": str(exc),
            "type": type(exc).__name__,
            "path": request.url.path,
        },
        headers=_cors_headers(request),
    )

# Include Versioned API
app.include_router(api_v1_router, prefix="/api/v1")

# Mount sqladmin at /admin (login-protected, admin role only)
create_admin(app)

_ADMIN_DIST = pathlib.Path("admin_ui/dist")

if _ADMIN_DIST.exists():
    @app.get("/panel", include_in_schema=False)
    @app.get("/panel/{path:path}", include_in_schema=False)
    async def serve_admin_panel(path: str = ""):
        # Serve real files (assets, favicon, etc.) directly;
        # everything else returns index.html so React Router handles the path.
        # Resolve to prevent path traversal (e.g. /panel/../../etc/passwd).
        candidate = (_ADMIN_DIST / path).resolve()
        if not str(candidate).startswith(str(_ADMIN_DIST.resolve())):
            raise HTTPException(status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_ADMIN_DIST / "index.html")


@app.get("/")
def read_root():
    return {
        "message": "Welcome to the Faculty Appraisal API",
        "status": "online",
        "version": "2.0.0"
    }
