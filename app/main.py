from fastapi import FastAPI
from .database import init_db
from .routers import expenses as expenses_router
from .routers import auth as auth_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Finance Manager – Backend", version="0.1.0")

    @app.on_event("startup")
    def on_startup():
        init_db()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(expenses_router.router)
    app.include_router(auth_router.router)

    return app


app = create_app()
