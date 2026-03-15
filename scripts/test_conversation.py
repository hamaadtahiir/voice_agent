"""CLI tool to simulate a conversation with the bot for testing.

Usage:
    python -m scripts.test_conversation [business_slug]

Defaults to "apex-roofing" if no slug is provided.  Run seed_dev_data.py
first so the business exists in the database.
"""

import asyncio
import sys


async def main():
    from sqlalchemy import select

    from app.db.engine import async_session_factory, init_db
    from app.models.business import Business
    from app.services.channel_router import Channel, NormalizedMessage, route_message

    await init_db()

    slug = sys.argv[1] if len(sys.argv) > 1 else "apex-roofing"

    async with async_session_factory() as db:
        result = await db.execute(
            select(Business).where(Business.slug == slug)
        )
        business = result.scalar_one_or_none()
        if not business:
            print(f"Business '{slug}' not found. Run seed_dev_data.py first.")
            return

        separator = "=" * 60
        print(f"\n{separator}")
        print(f"Testing conversation with: {business.name}")
        print(separator)

        welcome = "Hi! How can we help?"
        if business.branding and isinstance(business.branding, dict):
            welcome = business.branding.get("welcome_message", welcome)
        print(f"\nBot: {welcome}\n")

        session_id = "cli-test-user"

        while True:
            try:
                user_input = input("You: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\n\nGoodbye!")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "bye"):
                print("\nGoodbye!")
                break

            msg = NormalizedMessage(
                channel=Channel.WEB_CHAT,
                sender_id=session_id,
                content=user_input,
            )

            try:
                response = await route_message(msg, business, db)
                await db.commit()
                print(f"\nBot: {response}\n")
            except Exception as e:
                await db.rollback()
                print(f"\nError: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
