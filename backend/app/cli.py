import argparse
import asyncio
import getpass
import json
import sys

from app.auth.security import get_user_by_email, get_user_by_username, hash_password
from app.database import async_session_factory
from app.models import User, UserAccess, UserRole


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
            access_level=UserAccess.SUBMIT_AND_VOTE,
            is_auto_editor=True,
            email_verified=True,
        )
        db.add(user)
        await db.commit()
        print(f"Admin user '{username}' created successfully.")


async def set_user_role(
    *,
    username: str | None,
    email: str | None,
    role: str,
) -> None:
    try:
        new_role = UserRole(role)
    except ValueError as e:
        raise SystemExit(f"Invalid role '{role}'. Use: user, mod, admin") from e

    async with async_session_factory() as db:
        user = None
        if username:
            user = await get_user_by_username(db, username)
        elif email:
            user = await get_user_by_email(db, email)
        else:
            raise SystemExit("Provide --username or --email")

        if not user:
            label = username or email
            raise SystemExit(f"User not found: {label}")

        user.role = new_role
        user.is_auto_editor = new_role in (UserRole.MOD, UserRole.ADMIN)
        if new_role in (UserRole.MOD, UserRole.ADMIN):
            user.access_level = UserAccess.SUBMIT_AND_VOTE
        await db.commit()
        print(f"User '{user.username}' role set to {new_role.value}.")


async def set_user_access(
    *,
    username: str | None,
    email: str | None,
    access: str,
) -> None:
    try:
        new_access = UserAccess(access)
    except ValueError as e:
        raise SystemExit(f"Invalid access '{access}'. Use: vote_only, submit_and_vote") from e

    async with async_session_factory() as db:
        user = None
        if username:
            user = await get_user_by_username(db, username)
        elif email:
            user = await get_user_by_email(db, email)
        else:
            raise SystemExit("Provide --username or --email")

        if not user:
            raise SystemExit(f"User not found: {username or email}")

        user.access_level = new_access
        await db.commit()
        print(f"User '{user.username}' access set to {new_access.value}.")


async def expire_edits_cmd() -> None:
    from app.services import EditService
    from app.services.hash_queue import enqueue_hash_job

    async with async_session_factory() as db:
        count, pending_jobs = await EditService.expire_open_edits(db)
        await db.commit()
        for job_id in pending_jobs:
            await enqueue_hash_job(job_id)
        print(f"Processed {count} expired edits.")


async def generate_dump_cmd() -> None:
    from app.api.v1.dumps import generate_dump

    path = await generate_dump()
    print(f"Dump written to {path}")


async def export_archive_org_cmd() -> None:
    from app.services.archive_export_queue import run_archive_export

    result = await run_archive_export()
    print(json.dumps(result, indent=2, default=str))


def main() -> None:
    parser = argparse.ArgumentParser(prog="commercialbrainz", description="CommercialBrainz CLI")
    sub = parser.add_subparsers(dest="command")

    seed = sub.add_parser("seed-admin", help="Create admin user")
    seed.add_argument("--email", required=True)
    seed.add_argument("--username", required=True)
    seed.add_argument("--password")

    role_cmd = sub.add_parser("set-role", help="Change an existing user's role")
    role_cmd.add_argument("--username")
    role_cmd.add_argument("--email")
    role_cmd.add_argument("--role", required=True, choices=["user", "mod", "admin"])

    access_cmd = sub.add_parser("set-access", help="Change vote-only vs submit-and-vote access")
    access_cmd.add_argument("--username")
    access_cmd.add_argument("--email")
    access_cmd.add_argument("--access", required=True, choices=["vote_only", "submit_and_vote"])

    sub.add_parser("expire-edits", help="Process expired open edits")
    sub.add_parser("generate-dump", help="Generate public data dump")
    sub.add_parser("export-archive-org", help="Build dataset bundle and upload to Internet Archive")

    args = parser.parse_args()

    if args.command == "seed-admin":
        password = args.password or getpass.getpass("Admin password: ")
        asyncio.run(seed_admin(args.email, args.username, password))
    elif args.command == "set-role":
        if not args.username and not args.email:
            parser.error("set-role requires --username or --email")
        asyncio.run(
            set_user_role(username=args.username, email=args.email, role=args.role)
        )
    elif args.command == "set-access":
        if not args.username and not args.email:
            parser.error("set-access requires --username or --email")
        asyncio.run(
            set_user_access(username=args.username, email=args.email, access=args.access)
        )
    elif args.command == "expire-edits":
        asyncio.run(expire_edits_cmd())
    elif args.command == "generate-dump":
        asyncio.run(generate_dump_cmd())
    elif args.command == "export-archive-org":
        asyncio.run(export_archive_org_cmd())
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
