"""Database migration system."""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import List
import aiosqlite

from src.core.constants import DB_NAME

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Handles database schema migrations."""

    def __init__(self, db_path: str = DB_NAME, migrations_dir: str | None = None):
        """Initialize migration runner.

        Args:
            db_path: Path to database file.
            migrations_dir: Path to migrations directory.
        """
        self.db_path = db_path
        if migrations_dir is None:
            # Default to migrations directory relative to this file
            current_dir = Path(__file__).parent
            migrations_dir = str(current_dir / "migrations")
        self.migrations_dir = Path(migrations_dir)

    async def get_applied_migrations(self, conn: aiosqlite.Connection) -> List[str]:
        """Get list of applied migrations.

        Args:
            conn: Database connection.

        Returns:
            List of applied migration names.
        """
        # Create migrations table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.commit()

        cursor = await conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    def get_pending_migrations(self, applied: List[str]) -> List[Path]:
        """Get list of pending migration files.

        Args:
            applied: List of applied migration names.

        Returns:
            List of migration file paths to apply.
        """
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")
            return []

        all_migrations = sorted(self.migrations_dir.glob("*.sql"))
        pending = []

        for migration_file in all_migrations:
            migration_name = migration_file.stem
            if migration_name not in applied:
                pending.append(migration_file)

        return pending

    async def apply_migration(
        self, conn: aiosqlite.Connection, migration_file: Path
    ) -> None:
        """Apply a single migration file.

        Args:
            conn: Database connection.
            migration_file: Path to migration SQL file.
        """
        migration_name = migration_file.stem
        logger.info(f"Applying migration: {migration_name}")

        # Read and execute migration SQL
        sql = migration_file.read_text(encoding="utf-8")

        # Execute each statement separately (split by semicolon)
        statements = [s.strip() for s in sql.split(";") if s.strip()]
        for statement in statements:
            await conn.execute(statement)

        # Record migration as applied
        await conn.execute(
            "INSERT INTO schema_migrations (version) VALUES (?)", (migration_name,)
        )

        await conn.commit()
        logger.info(f"Migration applied successfully: {migration_name}")

    async def run_migrations(self) -> int:
        """Run all pending migrations.

        Returns:
            Number of migrations applied.
        """
        async with aiosqlite.connect(self.db_path) as conn:
            applied = await self.get_applied_migrations(conn)
            pending = self.get_pending_migrations(applied)

            if not pending:
                logger.info("No pending migrations")
                return 0

            logger.info(f"Found {len(pending)} pending migration(s)")

            for migration_file in pending:
                await self.apply_migration(conn, migration_file)

            return len(pending)

    async def init_database(self) -> None:
        """Initialize database with all migrations.

        This is the main entry point for setting up the database.
        """
        logger.info("Initializing database...")
        count = await self.run_migrations()
        if count > 0:
            logger.info(f"Database initialized with {count} migration(s)")
        else:
            logger.info("Database already up to date")


# Global migration runner instance
migration_runner = MigrationRunner()
