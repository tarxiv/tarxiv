#!/usr/bin/env python3
"""Utility commands for managing Supabase users from the CLI."""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict

from tarxiv.auth import ensure_user_record, get_supabase_client


def get_service_client():
    """Return a Supabase client authenticated with the service role."""
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not service_key:
        raise SystemExit("Set SUPABASE_SERVICE_ROLE_KEY in your environment to run this script.")
    return get_supabase_client(api_key=service_key)


def create_user(args: argparse.Namespace) -> None:
    """Create a user using the Supabase admin API."""
    client = get_service_client()
    metadata = {
        "preferred_username": args.username,
        "full_name": args.full_name or args.username,
        "avatar_url": args.picture_url,
        "institution": args.institution,
        "bio": args.bio,
    }
    metadata = {k: v for k, v in metadata.items() if v}

    payload: Dict[str, Any] = {
        "email": args.email,
        "password": args.password,
        "email_confirm": not args.skip_confirmation,
    }
    if metadata:
        payload["user_metadata"] = metadata

    result = client.auth.admin.create_user(payload)
    user = getattr(result, "user", None)
    if not user:
        raise SystemExit("Supabase did not return a user. Check logs for details.")

    profile = ensure_user_record(client, user)
    print("Created user:")
    print(f"  id: {profile['id']}")
    print(f"  email: {profile['email']}")
    print(f"  username: {profile.get('username')}")
    print(f"  institution: {profile.get('institution')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Supabase admin helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-user", help="Create a Supabase user via the admin API.")
    create_parser.add_argument("--email", required=True, help="Email address for the user.")
    create_parser.add_argument("--password", required=True, help="Password for the new user.")
    create_parser.add_argument("--username", help="Preferred username / handle.")
    create_parser.add_argument("--full-name", help="Display name.")
    create_parser.add_argument("--institution", help="Institution metadata.")
    create_parser.add_argument("--bio", help="Bio metadata.")
    create_parser.add_argument("--picture-url", help="Avatar URL.")
    create_parser.add_argument(
        "--skip-confirmation",
        action="store_true",
        help="Do not auto-confirm the email (defaults to confirmed).",
    )
    create_parser.set_defaults(func=create_user)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
