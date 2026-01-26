"""
Simple example of using Supabase with Tarxiv for user authentication and data storage.

This example demonstrates:
1. User signup and login
2. Storing user-specific astronomical object data
3. Querying user data with Row Level Security
"""

from supabase import create_client, Client
import os

# Configuration
SUPABASE_URL = "http://localhost:8000"  # Kong API Gateway
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyAgCiAgICAicm9sZSI6ICJhbm9uIiwKICAgICJpc3MiOiAic3VwYWJhc2UtZGVtbyIsCiAgICAiaWF0IjogMTY0MTc2OTIwMCwKICAgICJleHAiOiAxNzk5NTM1NjAwCn0.dc_X5iR_VP_qT0zsiyj_I_OZ2T9FtRU2BBNWN8Bu4GE"


def create_supabase_client() -> Client:
    """Create and return a Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


def example_signup(supabase: Client, email: str, password: str):
    """Sign up a new user."""
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        print(f"✓ User created: {response.user.email}")
        print(f"  User ID: {response.user.id}")
        return response
    except Exception as e:
        print(f"✗ Signup failed: {e}")
        return None


def example_login(supabase: Client, email: str, password: str):
    """Log in an existing user."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        print(f"✓ Logged in: {response.user.email}")
        print(f"  Access token: {response.session.access_token[:20]}...")
        return response
    except Exception as e:
        print(f"✗ Login failed: {e}")
        return None


def example_create_user_profile(supabase: Client, username: str, full_name: str):
    """Create a user profile after signup."""
    try:
        user = supabase.auth.get_user()
        response = supabase.table("user_profiles").insert({
            "id": user.user.id,
            "username": username,
            "full_name": full_name
        }).execute()
        print(f"✓ User profile created for {username}")
        return response
    except Exception as e:
        print(f"✗ Profile creation failed: {e}")
        return None


def example_add_favorite_object(supabase: Client, object_name: str, notes: str = None, tags: list = None):
    """Add a favorite astronomical object for the logged-in user."""
    try:
        user = supabase.auth.get_user()
        data = {
            "user_id": user.user.id,
            "object_name": object_name,
            "is_favorite": True
        }
        if notes:
            data["notes"] = notes
        if tags:
            data["tags"] = tags

        response = supabase.table("tarxiv_user_data").insert(data).execute()
        print(f"✓ Added favorite: {object_name}")
        return response
    except Exception as e:
        print(f"✗ Failed to add favorite: {e}")
        return None


def example_get_user_favorites(supabase: Client):
    """Get all favorite objects for the logged-in user."""
    try:
        response = supabase.table("tarxiv_user_data")\
            .select("*")\
            .eq("is_favorite", True)\
            .execute()

        print(f"✓ Found {len(response.data)} favorites:")
        for item in response.data:
            print(f"  - {item['object_name']}")
            if item.get('notes'):
                print(f"    Notes: {item['notes']}")
            if item.get('tags'):
                print(f"    Tags: {', '.join(item['tags'])}")
        return response
    except Exception as e:
        print(f"✗ Failed to get favorites: {e}")
        return None


def example_update_object_notes(supabase: Client, object_name: str, notes: str):
    """Update notes for an astronomical object."""
    try:
        user = supabase.auth.get_user()
        response = supabase.table("tarxiv_user_data")\
            .update({"notes": notes})\
            .eq("user_id", user.user.id)\
            .eq("object_name", object_name)\
            .execute()

        print(f"✓ Updated notes for {object_name}")
        return response
    except Exception as e:
        print(f"✗ Failed to update notes: {e}")
        return None


def main():
    """Run example workflows."""
    print("=== Supabase + Tarxiv Example ===\n")

    # Create client
    supabase = create_supabase_client()

    # Example 1: Sign up a new user
    print("1. Creating new user...")
    email = "astronomer@example.com"
    password = "secure_password_123"
    signup_response = example_signup(supabase, email, password)

    if signup_response:
        # Example 2: Create user profile
        print("\n2. Creating user profile...")
        example_create_user_profile(supabase, "astro_hunter", "Jane Astronomer")

        # Example 3: Add favorite objects
        print("\n3. Adding favorite objects...")
        example_add_favorite_object(
            supabase,
            "SN2024abc",
            notes="Interesting Type Ia supernova in NGC 1234",
            tags=["supernova", "type-ia", "monitoring"]
        )
        example_add_favorite_object(
            supabase,
            "AT2024xyz",
            notes="Possible tidal disruption event",
            tags=["tde", "follow-up-needed"]
        )

        # Example 4: Get favorites
        print("\n4. Retrieving favorites...")
        example_get_user_favorites(supabase)

        # Example 5: Update notes
        print("\n5. Updating object notes...")
        example_update_object_notes(
            supabase,
            "SN2024abc",
            "Type Ia confirmed. Peak magnitude reached."
        )

    # Example 6: Login existing user (use this for subsequent sessions)
    print("\n6. Logging in existing user...")
    login_response = example_login(supabase, email, password)

    if login_response:
        print("\n7. Getting favorites after login...")
        example_get_user_favorites(supabase)

    print("\n=== Example complete ===")


if __name__ == "__main__":
    main()
