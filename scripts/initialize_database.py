"""Create missing development accounts and complete corpus metadata; never reset existing users."""
import argparse
import getpass
import json
from pathlib import Path
import secrets
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.connection import DEFAULT_DATABASE, ROOT, make_engine
from backend.db.models import User
from backend.db.seed import MANIFEST, seed, validate_corpus


def initial_password(username):
    if not sys.stdin.isatty():
        raise ValueError("Use an interactive terminal or --generate-credentials; never pipe plaintext passwords")
    password = getpass.getpass(f"Initial password for {username} (12+ characters): ")
    if password != getpass.getpass("Confirm password: "):
        raise ValueError("Password confirmation differs")
    return password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--generate-credentials", type=Path,
                        help="Save generated temporary passwords to a NEW ignored runtime/ file; never print secrets")
    args = parser.parse_args()
    validate_corpus(args.manifest)
    engine = make_engine(args.database)
    try:
        provider = initial_password
        if args.generate_credentials:
            target = args.generate_credentials.resolve()
            if not target.is_relative_to((ROOT / "runtime").resolve()):
                raise ValueError("Credentials must be stored inside ignored project runtime/")
            with Session(engine) as session:
                existing = {name.casefold() for name in session.scalars(select(User.username))}
            missing = [name for name in ("admin", "A", "B") if name.casefold() not in existing]
            if missing:
                credentials = {name: secrets.token_urlsafe(24) for name in missing}
                target.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation: never replace a previous credential handoff file.
                with target.open("x", encoding="utf-8") as stream:
                    json.dump(credentials, stream, indent=2)
                    stream.write("\n")
                provider = credentials.__getitem__
                print("Temporary credentials saved locally; values are not printed. Keep the file private.")
            else:
                def provider(_):
                    raise ValueError("Concurrent account removal; retry initialization")
        result = seed(engine, provider, args.manifest)
        print(json.dumps({"created": result, "existing_rows": "verified; not overwritten"}, ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
