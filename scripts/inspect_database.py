"""Read-only, redacted metadata inspection. Does not print password hashes or credentials."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from backend.db.connection import DEFAULT_DATABASE, database_path


def inspect_database(path: Path = DEFAULT_DATABASE):
    path = database_path(path)
    if not path.is_file():
        raise ValueError("Database does not exist; migrate and initialize first")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        users = [dict(row) for row in connection.execute(
            "SELECT username,role,active,must_change_password,auth_version FROM users ORDER BY username")]
        documents = [dict(row) for row in connection.execute("""
            SELECT d.id,d.display_name,u.username AS owner,d.visibility,d.status,v.id AS version_id,
                   v.page_count,count(p.id) AS registered_pages,min(p.page_index) AS first_page_index,
                   max(p.page_index) AS last_page_index
            FROM documents d JOIN users u ON u.id=d.owner_id
            JOIN document_versions v ON v.id=d.active_version_id AND v.document_id=d.id
            LEFT JOIN pages p ON p.document_version_id=v.id GROUP BY d.id ORDER BY u.username
        """)]
        indexes = [dict(row) for row in connection.execute("""
            SELECT p.name AS profile,p.status AS profile_status,i.collection_name,i.status,
                   i.page_count,i.vector_count FROM index_generations i
            JOIN pipeline_profiles p ON p.id=i.profile_id ORDER BY i.collection_name
        """)]
        counts = {table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                  for table in ("users", "documents", "document_versions", "pages", "pipeline_profiles", "index_generations")}
        return {"revision": connection.execute("SELECT version_num FROM alembic_version").fetchone()[0],
                "integrity_check": connection.execute("PRAGMA integrity_check").fetchone()[0],
                "foreign_key_violations": [list(row) for row in connection.execute("PRAGMA foreign_key_check")],
                "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
                "counts": counts, "users": users, "documents": documents, "indexes": indexes,
                "scope": "Metadata inspection only; authentication is separate; document HTTP authorization and vector indexing not implemented"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    print(json.dumps(inspect_database(args.database), ensure_ascii=False, indent=2))
