from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from executor.market_data_stream import MarketDataStream

class BaseStrategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, name: str, symbol: str, stake_amount: float, multiplier: int):
        """
        Initialize base strategy
        
        Args:
            name: Strategy name
            symbol: Trading symbol (e.g., "R_100")
            stake_amount: Amount to stake per trade
            multiplier: Deriv multiplier
        """
        self.name = name
        self.symbol = symbol
        self.stake_amount = stake_amount
        self.multiplier = multiplier
        self.is_active = True
        self.positions = []  # Track open positions
    
    @abstractmethod
    async def on_tick(self, data: MarketDataStream):
        """Called on every price tick - MUST be implemented by child classes"""
        pass
    
    def on_position_opened(self, contract_id: str):
        """Called when a position is opened"""
        self.positions.append(contract_id)
    
    def on_position_closed(self, contract_id: str):
        """Called when a position is closed"""
        if contract_id in self.positions:
            self.positions.remove(contract_id)
    
    @property
    def has_active_positions(self) -> bool:
        """Check if strategy has any active positions"""
        return len(self.positions) > 0