from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import create_engine, create_session_factory
from app.core.exceptions import register_exception_handlers
from app.fees import router as fees_router
from app.health.router import router as health_router
from app.members import router as members_router
from app.membership_types import router as membership_types_router
from app.payments import router as payments_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_engine(get_settings())
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    try:
        yield
    finally:
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title='bpif-admin',
        lifespan=lifespan,
        docs_url='/api/docs',
        openapi_url='/api/v1/openapi.json',
        redoc_url=None,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=['*'],
            allow_headers=['*'],
        )

    register_exception_handlers(app)

    api_router = APIRouter(prefix='/api/v1')
    api_router.include_router(health_router)
    api_router.include_router(membership_types_router.public_router)
    api_router.include_router(payments_router.public_router)

    # Every management endpoint is mounted here. Step 4 protects all of them
    # with APIRouter(dependencies=[Depends(get_current_admin)]). Until then
    # they are open: don't deploy publicly.
    admin_router = APIRouter()
    admin_router.include_router(members_router.admin_router)
    admin_router.include_router(fees_router.admin_router)
    admin_router.include_router(payments_router.admin_router)

    api_router.include_router(admin_router)
    app.include_router(api_router)

    return app


app = create_app()
