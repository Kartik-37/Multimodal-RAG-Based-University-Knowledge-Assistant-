"""
Administrator Account Bootstrap Script.

Controlled CLI tool for provisioning initial Administrator accounts for local
development and deployment bootstrap.

Security Rule:
There is NO public or unauthenticated HTTP endpoint to create an administrator.
Admin accounts must be provisioned via this controlled script or direct operational access.

Usage:
    python scripts/bootstrap_admin.py --email admin@university.edu --password SecurePassword123! --name "Administrator"
"""

import argparse
import sys

from sqlalchemy import select

from backend.app.core.security import get_password_hash
from backend.app.db.session import get_db_session
from backend.app.models.user import User, UserRole


def bootstrap_admin(email: str, password: str, full_name: str) -> None:
    """Create or promote an administrator account safely."""
    email_clean = email.strip().lower()
    if not email_clean or not password:
        print("Error: Email and password are required.", file=sys.stderr)
        sys.exit(1)

    if len(password) < 8:
        print("Error: Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    with get_db_session() as db:
        stmt = select(User).where(User.email == email_clean)
        user = db.execute(stmt).scalar_one_or_none()

        password_hash = get_password_hash(password)

        if user:
            user.role = UserRole.ADMIN
            user.password_hash = password_hash
            user.full_name = full_name or user.full_name
            user.is_active = True
            db.commit()
            print(f"Success: Existing user '{email_clean}' promoted to ADMIN.")
        else:
            new_admin = User(
                email=email_clean,
                password_hash=password_hash,
                full_name=full_name or "System Administrator",
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(new_admin)
            db.commit()
            print(f"Success: Created new ADMIN account for '{email_clean}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap an administrator account.")
    parser.add_argument(
        "--email",
        default="admin@university.edu",
        help="Administrator email address (default: admin@university.edu)",
    )
    parser.add_argument(
        "--password",
        default="AdminPass123!",
        help="Administrator password (default: AdminPass123!)",
    )
    parser.add_argument(
        "--name",
        default="System Administrator",
        help="Administrator full name",
    )

    args = parser.parse_args()
    bootstrap_admin(args.email, args.password, args.name)


if __name__ == "__main__":
    main()
