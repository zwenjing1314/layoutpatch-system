"""Explicitly import a verified full development page bundle into local Qdrant."""
import argparse
import json
from pathlib import Path

from backend.db.connection import DEFAULT_DATABASE, make_engine
from backend.search.indexing import import_features


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--features", type=Path, required=True)
    args = parser.parse_args()
    engine = make_engine(args.database)
    try:
        print(json.dumps(import_features(engine, args.features), indent=2))
    finally:
        engine.dispose()
