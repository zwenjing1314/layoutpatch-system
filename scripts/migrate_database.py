"""Versioned SQLite migration. Paths must be inside this project's runtime/."""
import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from backend.db.connection import DEFAULT_DATABASE, ROOT, database_path


def migrate(path: Path = DEFAULT_DATABASE):
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["database_path"] = str(database_path(path))
    command.upgrade(config, "head")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    migrate(args.database)
    print("Database migration completed: 0001_metadata")
