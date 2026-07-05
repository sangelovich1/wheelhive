from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from web.config import settings
from web.auth import router as auth_router
from web.routes.positions import router as positions_router


def create_app() -> FastAPI:
    app = FastAPI(title="WheelHive Web")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret or "dev-insecure",
        same_site="lax",
        https_only=False,
    )
    app.include_router(auth_router)
    app.include_router(positions_router)

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


app = create_app()
