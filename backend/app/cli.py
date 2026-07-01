import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.auth.security import get_user_by_email, get_user_by_username, hash_password
from app.database import async_session_factory
from app.models import User, UserRole


async def seed_admin(email: str, username: str, password: str) -> None:
    async with async_session_factory() as db:
        if await get_user_by_username(db, username):
            print(f"User '{username}' already exists.")
            return
        if await get_user_by_email(db, email):
            print(f"Email '{email}' already registered.")
            return

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
            is_auto_editor=True,
        )
        db.add(user)
        await db.commit()
        print(f"Admin user '{username}' created successfully.")


async def expire_edits_cmd() -> None:
    from app.services import EditService

    async with async_session_factory() as db:
        count = await EditService.expire_open_edits(db)
        await db.commit()
        print(f"Processed {count} expired edits.")


async def generate_dump_cmd() -> None:
    from app.api.v1.dumps import generate_dump

    path = await generate_dump()
    print(f"Dump written to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="commercialbrainz", description="CommercialBrainz CLI")
    sub = parser.add_subparsers(dest="command")

    seed = sub.add_parser("seed-admin", help="Create admin user")
    seed.add_argument("--email", required=True)
    seed.add_argument("--username", required=True)
    seed.add_argument("--password")

    sub.add_parser("expire-edits", help="Process expired open edits")
    sub.add_parser("generate-dump", help="Generate public data dump")

    args = parser.parse_args()

    if args.command == "seed-admin":
        password = args.password or getpass.getpass("Admin password: ")
        asyncio.run(seed_admin(args.email, args.username, password))
    elif args.command == "expire-edits":
        asyncio.run(expire_edits_cmd())
    elif args.command == "generate-dump":
        asyncio.run(generate_dump_cmd())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
