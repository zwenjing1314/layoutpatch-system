"""Explicit R20 isolated HTTP server, never formal credentials or parser test doubles."""
import os
from backend.auth.settings import AuthSettings
from backend.main import create_app
from scripts.check_parsing import DATABASE, OUT

os.environ['LAYOUTPATCH_QUERY_AUDIT_DIR']=str(OUT/'queries')
app=create_app(AuthSettings(database=DATABASE),ingestion_enabled=False,parsing_enabled=False)
