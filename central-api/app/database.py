"""PostgreSQL database connection and models for Central API."""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, Index, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session

logger = logging.getLogger(__name__)

engine = None
SessionLocal = None


class Base(DeclarativeBase):
    pass


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key_hash = Column(String(64), nullable=False, unique=True)
    owner_email = Column(String(255), nullable=False, index=True)
    label = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_api_keys_key_hash_active", "key_hash", "is_active"),
    )


def init_db(database_url: str):
    """Initialize the engine and create tables if they don't exist."""
    global engine, SessionLocal

    engine = create_engine(database_url, echo=False, pool_size=5, max_overflow=10)
    SessionLocal = sessionmaker(bind=engine, class_=Session)

    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized: tables ready")


def get_session() -> Session:
    """Get a new session. Caller must close it or use as context manager."""
    if not SessionLocal:
        raise RuntimeError("Database not initialized — call init_db() first")
    return SessionLocal()
