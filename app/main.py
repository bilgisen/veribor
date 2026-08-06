"""FastAPI uygulaması — veribor."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core import get_cache, get_fetcher, shutdown
from app.routers import health, instruments, quote, stocks, summary

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        logging.basicConfig(level=logging.INFO)
        cache = await get_cache()
        await cache.connect()
        fetcher = get_fetcher()
        await fetcher.start()
        try:
            yield
        finally:
            await shutdown()

    app = FastAPI(
        title=settings.APP_NAME,
        description="BIST canlı fiyat verisi alternatif kaynağı (Anadolu Ajansı, İş Yatırım, Oyak Yatırım)",
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(stocks.router)
    app.include_router(summary.router)
    app.include_router(instruments.router)
    app.include_router(quote.router)

    return app


app = create_app()
