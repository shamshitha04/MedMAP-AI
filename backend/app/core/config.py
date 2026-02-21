from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


_CONFIG_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _CONFIG_FILE.parents[3]
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(_PROJECT_ROOT / "backend" / ".env")


@dataclass(frozen=True)
class Settings:
	app_name: str = "MedMap AI"
	api_prefix: str = ""
	pinecone_api_key: str | None = os.getenv("PINECONE_API_KEY")
	pinecone_index_name: str | None = os.getenv("PINECONE_INDEX_NAME")
	pinecone_namespace: str = os.getenv("PINECONE_NAMESPACE", "medicines")
	openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
	openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

	def validate_required_keys(self) -> None:
		"""Fail fast at startup if critical API keys are missing."""
		missing: list[str] = []
		if not self.openai_api_key:
			missing.append("OPENAI_API_KEY")
		if not self.pinecone_api_key:
			missing.append("PINECONE_API_KEY")
		if missing:
			raise RuntimeError(
				f"Missing required environment variable(s): {', '.join(missing)}. "
				f"Set them in your .env file or environment before starting the server."
			)

	def ensure_directories(self) -> None:
		"""Create required directories (database, cache, etc.) if they don't exist."""
		db_dir = self.project_root / "database"
		db_dir.mkdir(parents=True, exist_ok=True)

	@property
	def project_root(self) -> Path:
		return Path(__file__).resolve().parents[3]

	@property
	def database_url(self) -> str:
		db_path = self.project_root / "database" / "medmap.db"
		return f"sqlite+aiosqlite:///{db_path.as_posix()}"

	@property
	def golden_cache_path(self) -> Path:
		return self.project_root / "backend" / "app" / "cache" / "golden_responses.json"


settings = Settings()

