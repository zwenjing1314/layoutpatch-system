from pathlib import Path

from alembic import context
from backend.db.connection import DEFAULT_DATABASE, make_engine
from backend.db.models import Base

# The CLI supplies this path; no model, web server or Qdrant is started.
engine = make_engine(Path(context.config.attributes.get("database_path", DEFAULT_DATABASE)))
try:
    with engine.connect() as connection:
        connection.commit()
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        context.configure(connection=connection, target_metadata=Base.metadata,
                          render_as_batch=True, compare_type=True, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()
finally:
    engine.dispose()
