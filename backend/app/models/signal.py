from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from enum import Enum

class ActionType(Enum):
    MULTUP = "MULTUP"
    MULTDOWN = "MULTDOWN"
    HOLD = "HOLD"

@dataclass
class TradingSignal:
    """Trading signal model"""
    action: ActionType
    symbol: str
    stake_amount: float
    multiplier: int = 100
    currency: str = "USD"
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.stake_amount <= 0:
            raise ValueError(f"Stake amount must be positive, got {self.stake_amount}")
        if self.multiplier not in [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]:
            raise ValueError(f"Invalid multiplier: {self.multiplier}")
        if self.currency not in ["USD", "EUR", "GBP"]:
            raise ValueError(f"Unsupported currency: {self.currency}")
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "action": self.action.value,
            "symbol": self.symbol,
            "stake_amount": self.stake_amount,
            "multiplier": self.multiplier,
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TradingSignal':
        """Create from dictionary"""
        return cls(
            action=ActionType(data["action"]),
            symbol=data["symbol"],
            stake_amount=data["stake_amount"],
            multiplier=data.get("multiplier", 100),
            currency=data.get("currency", "USD"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else None
        )