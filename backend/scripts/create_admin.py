"""Create an admin user directly in the database.

There is no public /auth/register/admin endpoint on purpose (see
app/api/v1/endpoints/auth.py) — admins are provisioned out-of-band, the same
way `django-admin createsuperuser` works.

Usage:
    python scripts/create_admin.py --email admin@ondc.example --name "Ops Admin"
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True, help="Full name")
    parser.add_argument("--phone", default=None)
    args = parser.parse_args()

    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        raise SystemExit(1)
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        raise SystemExit(1)

    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == args.email)) is not None:
            print(f"A user with email {args.email} already exists.", file=sys.stderr)
            raise SystemExit(1)

        admin = User(
            email=args.email,
            password_hash=hash_password(password),
            full_name=args.name,
            phone=args.phone,
            role=UserRole.admin,
            is_verified=True,
        )
        db.add(admin)
        db.commit()
        print(f"Created admin user {args.email} ({admin.id})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
