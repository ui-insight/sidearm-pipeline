"""Shared API dependencies (database sessions, auth, etc.)."""

from app.db.engine import get_db

# Re-export for convenient imports in route handlers
get_db = get_db

# Add authentication dependencies here as the application grows:
# async def get_current_user(...) -> User:
#     ...
