from pydantic import BaseModel
from datetime import datetime

from typing import Literal

class TradeSignal(BaseModel):
    symbol: str
    action: Literal["BUY", "SELL", "MULTUP", "MULTDOWN"]
    price: float
    timestamp: datetime

class MarketData(BaseModel):
    symbol: str
    price: float
    timestamp: datetime
    source: str