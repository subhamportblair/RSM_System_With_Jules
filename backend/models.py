from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from .database import Base
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional, Dict

class KiteSession(Base):
    __tablename__ = "kite_sessions"
    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(String)
    login_date = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class RiskConfig(Base):
    __tablename__ = "risk_configs"
    id = Column(Integer, primary_key=True, index=True)
    max_loss = Column(Float)
    profit_target = Column(Float)
    auto_squareoff = Column(Boolean, default=True)
    check_interval = Column(Integer, default=3)
    trailing_sl_enabled = Column(Boolean, default=False)
    trail_distance = Column(Float, default=0.0)
    peak_pnl = Column(Float, default=0.0)

class AppStatus(Base):
    __tablename__ = "app_status"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="ACTIVE") # ACTIVE or HALTED

# Pydantic models
class RiskConfigUpdate(BaseModel):
    max_loss: float
    profit_target: float
    auto_squareoff: bool
    check_interval: int
    trailing_sl_enabled: bool
    trail_distance: float

class PnLSummary(BaseModel):
    day_pnl: float
    realized: float
    unrealized: float
    by_type: Dict[str, float]
    by_exchange: Dict[str, float]
