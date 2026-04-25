from abc import ABC, abstractmethod
from typing import Optional
from ..models import MarketData

class BaseStrategy(ABC):

    @abstractmethod
    async def on_tick(self, data: MarketData):
        pass