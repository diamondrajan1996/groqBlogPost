import os
import json
import logging
from pathlib import Path
from datetime import datetime, UTC
from dotenv import load_dotenv

from groq_client import fetch_latest_news
from ghostapi import GhostContentImporter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    ghost_url = os.getenv("GHOST_URL")
    ghost_key = os.getenv("GHOST_ADMIN_KEY")

    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing")

    posts = fetch_latest_news(api_key, max_results=1)

    output = {
        "generated_at": datetime.now(UTC).isoformat(),
        "posts": posts
    }

    out_file = Path("generated_posts.json")
    out_file.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    logger.info("generated_posts.json created")

    if ghost_url and ghost_key:
        importer = GhostContentImporter(ghost_url, ghost_key)
        importer.import_posts_from_file(str(out_file), publish=True)
        logger.info("Post sent to Ghost")


if __name__ == "__main__":
    main()
