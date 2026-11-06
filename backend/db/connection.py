from pathlib import Path

from sqlalchemy import create_engine, event

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = ROOT / "runtime/metadata.sqlite3"


def database_path(path: Path = DEFAULT_DATABASE) -> Path:
    path = path.resolve()
    if not path.is_relative_to((ROOT / "runtime").resolve()):
        raise ValueError("Database must be inside this project's runtime/")
    return path


def make_engine(path: Path = DEFAULT_DATABASE):
    path = database_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine("sqlite:///" + path.as_posix(), connect_args={"timeout": 5})

    @event.listens_for(engine, "connect")
    def pragmas(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine
