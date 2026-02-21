from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.db_setup import init_db, seed_db


@asynccontextmanager
async def lifespan(_: FastAPI):
	_validate_required_settings()
	settings.ensure_directories()
	await init_db()
	await seed_db()
	try:
		yield
	finally:
		from app.core.db_setup import engine
		await engine.dispose()


def _validate_required_settings() -> None:
	"""Fail fast at startup if critical API keys are missing."""
	settings.validate_required_keys()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
	CORSMiddleware,
	allow_origins=[
		"http://localhost:3000",
		"http://127.0.0.1:3000",
		"http://localhost:3001",
		"http://127.0.0.1:3001",
	],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)
app.include_router(router, prefix=settings.api_prefix)

