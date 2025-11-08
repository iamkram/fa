#!/usr/bin/env python3
"""
Apply Database Indexes and Views to FA AI System EDO Database

This script reads and executes the SQL migration file to create:
- Additional indexes for common query patterns
- Materialized views for pre-aggregated data
- Regular views for dynamic queries
- Utility functions for maintenance

Usage:
    python scripts/apply_indexes_views.py
    python scripts/apply_indexes_views.py --dry-run  # Show SQL without executing
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from src.config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def read_sql_file(file_path: Path) -> str:
    """Read SQL migration file"""
    try:
        with open(file_path, 'r') as f:
            sql_content = f.read()
        logger.info(f"Successfully read SQL file: {file_path}")
        return sql_content
    except FileNotFoundError:
        logger.error(f"SQL file not found: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading SQL file: {e}")
        raise


def parse_sql_statements(sql_content: str) -> list[str]:
    """
    Parse SQL content into individual statements.
    Handles multi-line statements and comments.
    """
    # Remove comments
    lines = []
    for line in sql_content.split('\n'):
        # Remove single-line comments
        if '--' in line:
            line = line[:line.index('--')]
        lines.append(line)

    sql_without_comments = '\n'.join(lines)

    # Split by semicolons but be careful with function definitions
    statements = []
    current_statement = []
    in_function = False

    for line in sql_without_comments.split('\n'):
        line_stripped = line.strip()

        # Track if we're inside a function/procedure definition
        if 'CREATE' in line_stripped.upper() and 'FUNCTION' in line_stripped.upper():
            in_function = True
        elif 'CREATE' in line_stripped.upper() and 'PROCEDURE' in line_stripped.upper():
            in_function = True

        current_statement.append(line)

        # End of statement
        if line_stripped.endswith(';'):
            # If we're in a function, only end on $$ LANGUAGE
            if in_function:
                if '$$ LANGUAGE' in line_stripped.upper():
                    in_function = False
                    statement = '\n'.join(current_statement)
                    if statement.strip():
                        statements.append(statement)
                    current_statement = []
            else:
                statement = '\n'.join(current_statement)
                if statement.strip():
                    statements.append(statement)
                current_statement = []

    return [s for s in statements if s.strip() and not s.strip().startswith('--')]


def execute_sql_migration(engine, sql_content: str, dry_run: bool = False) -> dict:
    """
    Execute SQL migration statements.

    Returns:
        dict: Summary of execution results
    """
    statements = parse_sql_statements(sql_content)

    results = {
        'total_statements': len(statements),
        'successful': 0,
        'failed': 0,
        'errors': [],
        'executed': []
    }

    logger.info(f"Parsed {len(statements)} SQL statements")

    if dry_run:
        logger.info("DRY RUN MODE - SQL will not be executed")
        for i, stmt in enumerate(statements, 1):
            preview = stmt.strip()[:100].replace('\n', ' ')
            logger.info(f"Statement {i}: {preview}...")
        return results

    with engine.connect() as conn:
        for i, statement in enumerate(statements, 1):
            stmt_preview = statement.strip()[:80].replace('\n', ' ')

            try:
                # Determine statement type for logging
                stmt_upper = statement.strip().upper()
                if 'CREATE INDEX' in stmt_upper:
                    stmt_type = 'INDEX'
                elif 'CREATE MATERIALIZED VIEW' in stmt_upper:
                    stmt_type = 'MATERIALIZED VIEW'
                elif 'CREATE OR REPLACE VIEW' in stmt_upper or 'CREATE VIEW' in stmt_upper:
                    stmt_type = 'VIEW'
                elif 'CREATE FUNCTION' in stmt_upper or 'CREATE OR REPLACE FUNCTION' in stmt_upper:
                    stmt_type = 'FUNCTION'
                elif 'REFRESH MATERIALIZED VIEW' in stmt_upper:
                    stmt_type = 'REFRESH'
                elif 'COMMENT ON' in stmt_upper:
                    stmt_type = 'COMMENT'
                elif 'SELECT' in stmt_upper and 'refresh_all_materialized_views' in statement:
                    stmt_type = 'REFRESH ALL'
                elif 'DO $$' in stmt_upper:
                    stmt_type = 'ANONYMOUS BLOCK'
                else:
                    stmt_type = 'SQL'

                logger.info(f"[{i}/{len(statements)}] Executing {stmt_type}: {stmt_preview}...")

                # Execute the statement
                result = conn.execute(text(statement))
                conn.commit()

                results['successful'] += 1
                results['executed'].append({
                    'number': i,
                    'type': stmt_type,
                    'preview': stmt_preview,
                    'status': 'SUCCESS'
                })

                logger.info(f"  ✓ {stmt_type} executed successfully")

            except SQLAlchemyError as e:
                results['failed'] += 1
                error_msg = str(e)
                results['errors'].append({
                    'statement_number': i,
                    'statement_preview': stmt_preview,
                    'error': error_msg
                })
                logger.error(f"  ✗ Error executing statement {i}: {error_msg}")

                # Decide whether to continue or stop
                if 'does not exist' in error_msg.lower() and 'drop' in statement.lower():
                    # Ignore errors dropping non-existent objects
                    logger.info("  → Continuing (object doesn't exist)")
                    continue
                elif 'already exists' in error_msg.lower():
                    # Ignore errors creating existing objects
                    logger.info("  → Continuing (object already exists)")
                    continue
                else:
                    # For other errors, log but continue
                    logger.warning(f"  → Continuing after error")
                    continue

    return results


def print_summary(results: dict, start_time: datetime):
    """Print execution summary"""
    duration = (datetime.now() - start_time).total_seconds()

    logger.info("\n" + "="*80)
    logger.info("DATABASE OPTIMIZATION SUMMARY")
    logger.info("="*80)
    logger.info(f"Total statements: {results['total_statements']}")
    logger.info(f"Successful: {results['successful']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Duration: {duration:.2f} seconds")
    logger.info("="*80)

    if results['executed']:
        logger.info("\nExecuted statements by type:")
        stmt_types = {}
        for stmt in results['executed']:
            stmt_type = stmt['type']
            stmt_types[stmt_type] = stmt_types.get(stmt_type, 0) + 1

        for stmt_type, count in sorted(stmt_types.items()):
            logger.info(f"  {stmt_type}: {count}")

    if results['errors']:
        logger.info("\nErrors encountered:")
        for error in results['errors']:
            logger.error(f"  Statement {error['statement_number']}: {error['error'][:100]}")

    logger.info("="*80 + "\n")


def verify_objects_created(engine):
    """Verify that indexes and views were created successfully"""
    logger.info("Verifying database objects...")

    verification_queries = {
        'indexes': """
            SELECT indexname, tablename
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND (indexname LIKE 'idx_%' OR indexname LIKE 'idx_mv_%')
            ORDER BY tablename, indexname;
        """,
        'materialized_views': """
            SELECT schemaname, matviewname
            FROM pg_matviews
            WHERE schemaname = 'public'
            ORDER BY matviewname;
        """,
        'views': """
            SELECT schemaname, viewname
            FROM pg_views
            WHERE schemaname = 'public'
            AND viewname LIKE 'v_%'
            ORDER BY viewname;
        """,
        'functions': """
            SELECT routine_name, routine_type
            FROM information_schema.routines
            WHERE routine_schema = 'public'
            AND routine_name LIKE '%refresh%'
            ORDER BY routine_name;
        """
    }

    with engine.connect() as conn:
        for obj_type, query in verification_queries.items():
            result = conn.execute(text(query))
            rows = result.fetchall()
            logger.info(f"\n{obj_type.upper()}: {len(rows)} found")
            for row in rows:
                logger.info(f"  - {row[1] if len(row) > 1 else row[0]}")


def main():
    parser = argparse.ArgumentParser(
        description='Apply database indexes and views to FA AI System EDO database'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show SQL statements without executing them'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify existing objects, do not execute migration'
    )
    parser.add_argument(
        '--sql-file',
        type=Path,
        default=Path(__file__).parent / 'create_indexes_views.sql',
        help='Path to SQL migration file'
    )

    args = parser.parse_args()

    start_time = datetime.now()

    logger.info("="*80)
    logger.info("FA AI System - Database Optimization")
    logger.info("="*80)
    logger.info(f"Start time: {start_time}")
    logger.info(f"Database URL: {settings.database_url.split('@')[-1]}")  # Hide credentials
    logger.info(f"SQL file: {args.sql_file}")
    logger.info("="*80 + "\n")

    try:
        # Create database engine
        logger.info("Connecting to database...")
        engine = create_engine(settings.database_url)

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            logger.info(f"Connected to: {version[:50]}...")

        # Verify only mode
        if args.verify_only:
            verify_objects_created(engine)
            return

        # Read SQL migration file
        logger.info("Reading SQL migration file...")
        sql_content = read_sql_file(args.sql_file)

        # Execute migration
        logger.info("Executing SQL migration...\n")
        results = execute_sql_migration(engine, sql_content, dry_run=args.dry_run)

        # Print summary
        print_summary(results, start_time)

        # Verify objects created (if not dry run)
        if not args.dry_run:
            verify_objects_created(engine)

        # Final status
        if results['failed'] > 0:
            logger.warning(f"Migration completed with {results['failed']} errors")
            sys.exit(1)
        else:
            logger.info("✓ Migration completed successfully!")
            logger.info("\nNext steps:")
            logger.info("  1. Run sample queries to test performance")
            logger.info("  2. Set up cron job to refresh materialized views:")
            logger.info("     SELECT refresh_all_materialized_views();")
            logger.info("  3. Monitor query performance with EXPLAIN ANALYZE")

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
