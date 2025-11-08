#!/usr/bin/env python3
"""
Clean EDO Load Test Tables

Drops all EDO load test tables and recreates them.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from src.shared.models.edo_database import Base
from src.config.settings import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Cleaning EDO load test tables...")

    engine = create_engine(settings.database_url)

    # Drop all tables
    logger.info("Dropping tables...")
    Base.metadata.drop_all(engine)
    logger.info("✅ Tables dropped")

    # Recreate
    logger.info("Recreating tables...")
    Base.metadata.create_all(engine)
    logger.info("✅ Tables recreated")

    logger.info("Done!")

if __name__ == "__main__":
    main()
