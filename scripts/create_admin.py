#!/usr/bin/env python3
"""Create admin user."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.session import AsyncSessionLocal
from src.db.repositories.user import UserRepository
from src.schemas.user import UserCreate


async def create_admin(
    email: str = "admin@api-cyber.local",
    username: str = "admin",
    password: str = "admin123",
    full_name: str = "Administrator",
):
    """Create an admin user."""
    async with AsyncSessionLocal() as db:
        user_repo = UserRepository(db)

        existing = await user_repo.get_by_username(username)
        if existing:
            print(f"User '{username}' already exists.")
            return

        user_create = UserCreate(
            email=email,
            username=username,
            password=password,
            full_name=full_name,
            is_active=True,
            is_admin=True,
        )

        user = await user_repo.create(user_create)
        print(f"Admin user created successfully:")
        print(f"  Username: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  ID: {user.id}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create admin user")
    parser.add_argument("--email", default="admin@api-cyber.local", help="Admin email")
    parser.add_argument("--username", default="admin", help="Admin username")
    parser.add_argument("--password", default="admin123", help="Admin password")
    parser.add_argument("--full-name", default="Administrator", help="Full name")

    args = parser.parse_args()

    asyncio.run(create_admin(
        email=args.email,
        username=args.username,
        password=args.password,
        full_name=args.full_name,
    ))
