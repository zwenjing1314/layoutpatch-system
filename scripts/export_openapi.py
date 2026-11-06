"""Run with .venv-web Python from the project root."""
import json
from pathlib import Path
from backend.main import app

path = Path("frontend/docs/openapi.json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
