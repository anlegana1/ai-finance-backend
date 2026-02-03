from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .routers import expenses as expenses_router
from .routers import auth as auth_router
from .routers import receipts as receipts_router


def create_app() -> FastAPI:
    app = FastAPI(title="AI Finance Manager – Backend", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def on_startup():
        init_db()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(expenses_router.router)
    app.include_router(auth_router.router)
    app.include_router(receipts_router.router)

    return app


app = create_app()
