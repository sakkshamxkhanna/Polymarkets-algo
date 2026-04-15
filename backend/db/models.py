from datetime import datetime
from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, Text, Enum
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config.settings import settings
import enum


class Base(DeclarativeBase):
    pass


class OrderStatus(str, enum.Enum):
    PENDING_SUBMIT = "pending_submit"
    SUBMITTED = "submitted"
    LIVE = "live"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    PENDING_CANCEL = "pending_cancel"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ORPHANED = "orphaned"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(String, primary_key=True)
    market_id = Column(String, nullable=False, index=True)
    token_id = Column(String, nullable=False, index=True)
    question = Column(Text, nullable=True)
    side = Column(String, nullable=False)  # YES / NO
    price = Column(Float, nullable=False)
    size = Column(Float, nullable=False)  # USDC
    strategy = Column(String, nullable=False, default="resolution_timing")
    status = Column(String, nullable=False, default=OrderStatus.PENDING_SUBMIT)
    clob_order_id = Column(String, nullable=True)
    fill_price = Column(Float, nullable=True)
    fill_size = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    signal_confidence = Column(Float, nullable=True)
    edge_cents = Column(Float, nullable=True)
    sim_mode = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Position(Base):
    __tablename__ = "positions"

    token_id = Column(String, primary_key=True)
    market_id = Column(String, nullable=False, index=True)
    question = Column(Text, nullable=True)
    side = Column(String, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=True)
    size_usdc = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, default=0.0)
    is_open = Column(Boolean, default=True)
    strategy = Column(String, nullable=False, default="resolution_timing")
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)


class CalibrationLog(Base):
    __tablename__ = "calibration_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String, nullable=False, index=True)
    question = Column(Text, nullable=True)
    predicted_prob = Column(Float, nullable=False)
    actual_outcome = Column(Float, nullable=True)  # 0.0 or 1.0 after resolution
    strategy = Column(String, nullable=False)
    brier_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False, index=True)
    message = Column(Text, nullable=False)
    severity = Column(String, nullable=False, default="info")  # info/warning/critical
    agent = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Database engine and session factory
engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
