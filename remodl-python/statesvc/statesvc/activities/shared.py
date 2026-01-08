"""
Shared utilities for StateSvc activities.
"""

import asyncpg
import os


async def get_db_connection():
    """
    Create a new database connection.

    Returns:
        asyncpg.Connection
    """
    return await asyncpg.connect(
        os.environ["DATABASE_URL"],
        server_settings={'search_path': 'inferx,public'}
    )
