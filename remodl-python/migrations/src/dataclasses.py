"""
Pydantic models for migration workflows.

Defines input/output contracts for migration activities and workflows.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ==================== Database Connection ====================

class DatabaseConnection(BaseModel):
    """Database connection parameters"""
    host: str = Field(description="Database host")
    port: int = Field(default=5432, description="Database port")
    user: str = Field(description="Database user")
    password: str = Field(description="Database password")
    database: str = Field(description="Database name")
    sslmode: str = Field(default="require", description="SSL mode")

    def connection_string(self) -> str:
        """Build PostgreSQL connection string"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?sslmode={self.sslmode}"


# ==================== Migration Activity Output ====================

class RunMigrationOutput(BaseModel):
    """Output from run_sql_migration activity"""
    success: bool = Field(description="Whether migration succeeded")
    statements_executed: int = Field(description="Number of SQL statements executed")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: int = Field(description="Execution time in milliseconds")


class ValidateMigrationOutput(BaseModel):
    """Output from validate_migration activity"""
    success: bool = Field(description="Whether validation passed")
    missing_tables: list[str] = Field(default_factory=list, description="Tables that don't exist")
    existing_tables: list[str] = Field(description="Tables that were found")
    error_message: Optional[str] = Field(default=None, description="Error message if validation failed")


# ==================== Migration Workflow Input/Output ====================

class MigrationWorkflowInput(BaseModel):
    """
    Input for MigrationWorkflow.

    Provides database connection parameters. The migration file itself
    is hardcoded in the workflow logic (001_create_inferx_schema.sql).
    """
    db_connection: DatabaseConnection = Field(description="Database connection parameters")


class MigrationWorkflowOutput(BaseModel):
    """Output from MigrationWorkflow"""
    success: bool = Field(description="Whether entire migration succeeded")
    statements_executed: int = Field(description="SQL statements executed")
    validation_passed: bool = Field(description="Whether post-migration validation passed")
    total_time_ms: int = Field(description="Total workflow execution time")
    started_at: datetime = Field(description="When migration started")
    completed_at: datetime = Field(description="When migration completed")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
