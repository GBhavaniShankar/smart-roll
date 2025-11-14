from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from httpx import HTTPStatusError

from app.routers import auth, admin, teacher, student, ta

app = FastAPI(
    title="TechNova Institute - Smart API",
    description="API for Attendance and Course Recommendation System",
    version="1.0.0"
)

# --- CORS Middleware ---
# Configure this to be more restrictive in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# --- Exception Handlers ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Custom handler for Pydantic validation errors."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation Error", "errors": exc.errors()},
    )

@app.exception_handler(HTTPStatusError)
async def http_status_error_handler(request: Request, exc: HTTPStatusError):
    """Custom handler for errors from external APIs (httpx)."""
    return JSONResponse(
        status_code=exc.response.status_code,
        content={"detail": f"Error from external service: {exc.response.text}"},
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unexpected errors."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected internal server error occurred.", "error": str(exc)},
    )

# --- API Routers ---
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(teacher.router)
app.include_router(student.router)
app.include_router(ta.router)

@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint for health checks."""
    return {"message": "Welcome to TechNova Institute API"}