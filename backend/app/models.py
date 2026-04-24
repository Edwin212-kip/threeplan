from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Literal, Optional
from enum import Enum

class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

class TradeSignal(BaseModel):
    """THE SOURCE OF TRUTH - Every trade uses this"""
    symbol: str = Field(..., min_length=2, max_length=20)
    side: Side
    quantity: float = Field(..., gt=0)
    price: Optional[float] = Field(None, gt=0)
    order_type: OrderType = OrderType.MARKET
    strategy_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('price')
    def price_required_for_limit(cls, v, values):
        if values.get('order_type') == OrderType.LIMIT and v is None:
            raise ValueError('Price required for LIMIT orders')
        return v
    
    class Config:
        use_enum_values = True

class MarketData(BaseModel):
    symbol: str
    bid: float
    ask: float
    last_price: float
    volume_24h: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
