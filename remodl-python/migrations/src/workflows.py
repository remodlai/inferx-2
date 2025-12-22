"""
Migration workflows for InferX database schema.
"""

from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta

# Import Pydantic models through sandbox
with workflow.unsafe.imports_passed_through():
    from pathlib import Path
    from .dataclasses import (
        MigrationWorkflowInput,
        MigrationWorkflowOutput,
    )
    from .activities import (
        run_sql_migration,
        validate_migration,
    )


@workflow.defn
class MigrationWorkflow:
    """
    One-off workflow to execute database migration for InferX schema.

    This workflow:
    1. Executes the 001_create_inferx_schema.sql migration
    2. Validates that all expected tables were created
    3. Returns comprehensive results
    4. Completes (does not run forever)
    """

    @workflow.run
    async def run(self, input: MigrationWorkflowInput) -> MigrationWorkflowOutput:
        """
        Execute migration workflow.

        Args:
            input: Database connection parameters

        Returns:
            MigrationWorkflowOutput with migration results
        """
        started_at = workflow.now()

        # Migration file path (hardcoded - this is what we're migrating)
        migrations_dir = Path(__file__).parent.parent / "sql"
        sql_file_path = str(migrations_dir / "001_create_inferx_schema.sql")
        migration_name = "001_create_inferx_schema"

        # Expected tables after migration
        expected_tables = [
            "tenants",
            "namespaces",
            "functions",
            "function_status",
            "nodes",
            "userrole",
            "apikey"
        ]

        # Step 1: Execute migration
        workflow.logger.info(f"Starting migration: {migration_name}")

        migration_result = await workflow.execute_activity(
            run_sql_migration,
            args=[input.db_connection, sql_file_path, migration_name],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
                backoff_coefficient=2.0,
            )
        )

        if not migration_result.success:
            workflow.logger.error(f"Migration failed: {migration_result.error_message}")
            return MigrationWorkflowOutput(
                success=False,
                statements_executed=migration_result.statements_executed,
                validation_passed=False,
                total_time_ms=migration_result.execution_time_ms,
                started_at=started_at,
                completed_at=workflow.now(),
                error_message=migration_result.error_message
            )

        # Step 2: Validate migration created expected tables
        workflow.logger.info(f"Validating migration created {len(expected_tables)} tables")

        validation_result = await workflow.execute_activity(
            validate_migration,
            args=[input.db_connection, expected_tables, "inferx"],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        if not validation_result.success:
            workflow.logger.warning(f"Validation failed: {validation_result.error_message}")

        # Calculate total time
        completed_at = workflow.now()
        total_time_ms = int((completed_at - started_at).total_seconds() * 1000)

        workflow.logger.info(
            f"Migration complete. Success: {migration_result.success}, "
            f"Validated: {validation_result.success}, "
            f"Time: {total_time_ms}ms"
        )

        return MigrationWorkflowOutput(
            success=migration_result.success and validation_result.success,
            statements_executed=migration_result.statements_executed,
            validation_passed=validation_result.success,
            total_time_ms=total_time_ms,
            started_at=started_at,
            completed_at=completed_at,
            error_message=validation_result.error_message if not validation_result.success else None
        )
