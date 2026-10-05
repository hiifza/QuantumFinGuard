from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging_config import configure_logging
from app.core.middleware import RequestContextMiddleware, SimpleRateLimiter
from app.db.session import Base, engine

configure_logging()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="AI and Blockchain Framework for Intelligent Financial Risk and Fraud Analytics",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Order matters: outermost middleware runs first on request, last on response.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SimpleRateLimiter)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.on_event("startup")
    def on_startup():
        # Local/dev convenience: create tables if they don't exist yet.
        # Staging/production use Alembic migrations instead (see alembic/).
        if settings.ENVIRONMENT == "local":
            Base.metadata.create_all(bind=engine)

    return app


app = create_app()
