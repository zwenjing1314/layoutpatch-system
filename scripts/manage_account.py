"""Local administrator CLI: disable, enable, revoke sessions or reset a password."""
import argparse
from pathlib import Path
import time

from backend.auth.accounts import change_account
from backend.db.connection import DEFAULT_DATABASE, make_engine
from scripts.initialize_database import initial_password

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["disable", "enable", "revoke", "reset"])
    parser.add_argument("username")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()
    password = initial_password(args.username) if args.action == "reset" else None
    engine = make_engine(args.database)
    try:
        change_account(engine, args.username, args.action, time.time(), password)
        print("Account action completed; existing sessions revoked.")
    finally:
        engine.dispose()
