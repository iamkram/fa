from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Generator
import logging

from src.config.settings import get_settings
from src.shared.models.database import Base

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.settings = get_settings()
        self.engine = create_engine(
            self.settings.database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def create_tables(self):
        """Create all tables in the database"""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created successfully")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            session.close()

# Global instance
db_manager = DatabaseManager()

def get_db_session() -> Generator[Session, None, None]:
    """Dependency for FastAPI or direct use"""
    return db_manager.get_session()

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions"""
    session = db_manager.SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {str(e)}")
        raise
    finally:
        session.close()
