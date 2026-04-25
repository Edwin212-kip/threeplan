from datetime import datetime
from ..models import MarketData, TradeSignal
from .base import BaseStrategy

class DummyStrategy(BaseStrategy):

    def __init__(self):
        self.threshold = 10

    async def on_tick(self, data: MarketData):
        if data.price > self.threshold:
            return TradeSignal(
                symbol=data.symbol,
                action="BUY",
                price=data.price,
                timestamp=datetime.utcnow()
            )
        return None