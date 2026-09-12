"""CLI utility to manually seed or promote an Admin user in the PyRedis database."""

import argparse
import asyncio
import sys
from pyredis.auth.security import hash_password
from pyredis.core.types import Role
from pyredis.db.models import UserModel
from pyredis.db.session import get_session_factory, init_db
from sqlalchemy import select


async def seed_or_promote_admin(email: str, password: str, name: str) -> None:
    await init_db()
    factory = get_session_factory()
    email_clean = email.strip().lower()

    async with factory() as session:
        result = await session.execute(select(UserModel).where(UserModel.email == email_clean))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            existing_user.role = Role.ADMIN.value
            if password:
                existing_user.password_hash = hash_password(password)
            if name:
                existing_user.name = name
            await session.commit()
            print(f"[SUCCESS] Existing user '{email_clean}' promoted to ADMIN.")
        else:
            if not password:
                print("[ERROR] Password is required when creating a new user.", file=sys.stderr)
                sys.exit(1)
            new_user = UserModel(
                email=email_clean,
                name=name or "Administrator",
                password_hash=hash_password(password),
                role=Role.ADMIN.value,
            )
            session.add(new_user)
            await session.commit()
            print(f"[SUCCESS] New ADMIN user '{email_clean}' created successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed or promote an Admin user in PyRedis.")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--name", default="Admin", help="User full name")

    args = parser.parse_args()
    asyncio.run(seed_or_promote_admin(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
