"""Generate sample files and ingest them into the configured PostgreSQL database."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from generate_sample_data import main as generate_sample_data

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.services.ingestion import IngestionService  # noqa: E402


async def seed() -> None:
    """Regenerate deterministic inputs and persist their metadata and chunks."""
    generate_sample_data()
    async with SessionLocal() as session:
        result = await IngestionService(session).ingest()
        await session.commit()
    logging.getLogger(__name__).info(
        "Ingestion complete: "
        f"{result.documents_added} documents added, "
        f"{result.documents_skipped} documents unchanged, "
        f"{result.datasets_added} datasets added, "
        f"{result.datasets_skipped} datasets unchanged."
    )


def main() -> None:
    """Run the asynchronous seed operation."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed())


if __name__ == "__main__":
    main()
