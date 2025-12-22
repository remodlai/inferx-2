"""
Activities for database migration workflows.

Activities perform the actual work (SQL execution, schema validation).
"""

from temporalio import activity
import asyncpg
from datetime import datetime
from pathlib import Path
import time

from .dataclasses import (
    RunMigrationOutput,
    ValidateMigrationOutput,
    DatabaseConnection,
)


@activity.defn
async def run_sql_migration(
    db_connection: DatabaseConnection,
    sql_file_path: str,
    migration_name: str
) -> RunMigrationOutput:
    """
    Execute SQL migration file against database.

    Args:
        db_connection: Database connection parameters
        sql_file_path: Path to SQL file
        migration_name: Migration identifier for logging

    Returns:
        RunMigrationOutput with execution results
    """
    start_time = time.time()

    try:
        # Read SQL file
        sql_path = Path(sql_file_path)
        if not sql_path.exists():
            return RunMigrationOutput(
                success=False,
                statements_executed=0,
                error_message=f"Migration file not found: {sql_file_path}",
                execution_time_ms=0
            )

        with open(sql_path, 'r') as f:
            sql = f.read()

        # Connect to database
        conn = await asyncpg.connect(db_connection.connection_string())

        try:
            # Execute migration SQL
            activity.logger.info(f"Executing migration: {migration_name}")
            await conn.execute(sql)

            # Count statements (rough approximation)
            statements_executed = len([s for s in sql.split(';') if s.strip()])

            execution_time_ms = int((time.time() - start_time) * 1000)

            activity.logger.info(f"Migration {migration_name} completed successfully in {execution_time_ms}ms")

            return RunMigrationOutput(
                success=True,
                statements_executed=statements_executed,
                error_message=None,
                execution_time_ms=execution_time_ms
            )

        finally:
            await conn.close()

    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)
        activity.logger.error(f"Migration {migration_name} failed: {e}")

        return RunMigrationOutput(
            success=False,
            statements_executed=0,
            error_message=str(e),
            execution_time_ms=execution_time_ms
        )


@activity.defn
async def validate_migration(
    db_connection: DatabaseConnection,
    expected_tables: list[str],
    expected_schema: str = "inferx"
) -> ValidateMigrationOutput:
    """
    Validate that migration created expected tables.

    Args:
        db_connection: Database connection parameters
        expected_tables: Tables that should exist
        expected_schema: Schema to check in

    Returns:
        ValidateMigrationOutput with validation results
    """
    try:
        # Connect to database
        conn = await asyncpg.connect(db_connection.connection_string())

        try:
            # Query for existing tables in schema
            existing_tables = await conn.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = $1
                ORDER BY table_name
            """, expected_schema)

            existing_table_names = [row['table_name'] for row in existing_tables]

            # Find missing tables
            missing_tables = [t for t in expected_tables if t not in existing_table_names]

            if missing_tables:
                activity.logger.warning(f"Missing tables: {missing_tables}")
                return ValidateMigrationOutput(
                    success=False,
                    missing_tables=missing_tables,
                    existing_tables=existing_table_names,
                    error_message=f"Missing tables: {', '.join(missing_tables)}"
                )

            activity.logger.info(f"Validation passed. Found {len(existing_table_names)} tables in schema '{expected_schema}'")

            return ValidateMigrationOutput(
                success=True,
                missing_tables=[],
                existing_tables=existing_table_names,
                error_message=None
            )

        finally:
            await conn.close()

    except Exception as e:
        activity.logger.error(f"Validation failed: {e}")

        return ValidateMigrationOutput(
            success=False,
            missing_tables=expected_tables,
            existing_tables=[],
            error_message=str(e)
        )
