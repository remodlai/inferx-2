"""
Shared utilities for StateSvc activities.
"""

import asyncpg
from typing import Optional
import os


# Database connection pool (initialized by worker)
DB_POOL: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """Get or create database connection pool to Neon PostgreSQL"""
    global DB_POOL
    if DB_POOL is None:
        # Connect to Neon PostgreSQL (shared with LiteLLM, separate schema for InferX)
        connection_string = os.getenv(
            "DATABASE_URL",
            "postgresql://neondb_owner:npg_YIynbl1f3MUc@ep-autumn-king-a4xm63yd-pooler.us-east-1.aws.neon.tech/litellm?sslmode=require"
        )
        DB_POOL = await asyncpg.create_pool(
            connection_string,
            min_size=2,
            max_size=10,
            server_settings={'search_path': 'inferx,public'},
        )
    return DB_POOL
