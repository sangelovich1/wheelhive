from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from web.config import settings
from web.auth import router as auth_router
from web.routes.positions import router as positions_router

STATIC = Path(__file__).parent / "static"


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

    if (STATIC / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="spa")

    return app


app = create_app()


def main():
    import uvicorn

    uvicorn.run("web.app:app", host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
