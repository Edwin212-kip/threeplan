"""
SIMPLE MOMENTUM STRATEGY - COMPLETE FIXED VERSION
Both strategies now have the required on_tick method
"""

from collections import deque
from datetime import datetime
from typing import Optional, Dict, Any
import statistics

from models.signal import TradingSignal, ActionType
from executor.market_data_stream import MarketDataStream
from strategies.base import BaseStrategy
from utils.logger import logger


class SMAMomentumStrategy(BaseStrategy):
    """SMA crossover momentum strategy"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        
        # Price history
        self.prices = deque(maxlen=50)
        
        # Parameters
        self.fast_period = 5
        self.slow_period = 20
        self.volatility_threshold = 2.0
        self.is_active = True
        self.positions = []
        self.name = f"SMAMomentum_{symbol}"

    async def on_tick(self, data: MarketDataStream) -> Optional[TradingSignal]:
        """✅ HAS on_tick method - GOOD!"""
        
        if data.symbol != self.symbol:
            return None

        self.prices.append(data.price)

        # Need enough data
        if len(self.prices) < self.slow_period:
            return None

        # Indicators
        fast_sma = sum(list(self.prices)[-self.fast_period:]) / self.fast_period
        slow_sma = sum(list(self.prices)[-self.slow_period:]) / self.slow_period
        momentum = self.prices[-1] - self.prices[-2]
        volatility = statistics.stdev(self.prices)

        # Volatility filter
        if volatility > self.volatility_threshold:
            return None

        # Signal generation
        action = None
        
        if fast_sma > slow_sma and momentum > 0:
            action = ActionType.MULTUP
        elif fast_sma < slow_sma and momentum < 0:
            action = ActionType.MULTDOWN

        if action is None:
            return None

        # Confidence check
        confidence = abs(fast_sma - slow_sma) + abs(momentum)
        if confidence < 0.1:
            return None

        return TradingSignal(
            symbol=self.symbol,
            action=action,
            stake_amount=1.0,  # Default stake
            currency="USD",
            multiplier=100,
            timestamp=datetime.utcnow()
        )


class SimpleMomentumStrategy(BaseStrategy):
    """
    Simple momentum strategy:
    - Tracks price changes over short period
    - BUY if momentum is positive and strong
    - SELL if momentum is negative and strong
    """
    
    def __init__(self, symbol: str, stake_amount: float = 1.0, multiplier: int = 100,
                 lookback_periods: int = 5, momentum_threshold: float = 0.5):
        # Set attributes directly (no super call because BaseStrategy has no __init__)
        self.name = f"Momentum_{symbol}"
        self.symbol = symbol
        self.stake_amount = stake_amount
        self.multiplier = multiplier
        self.is_active = True
        self.positions = []
        
        self.lookback_periods = lookback_periods
        self.momentum_threshold = momentum_threshold
        self.price_history = deque(maxlen=lookback_periods + 1)
        
    # ========== ✅ ADDED: REQUIRED on_tick METHOD ==========
    
    async def on_tick(self, data: MarketDataStream) -> Optional[TradingSignal]:
        """
        ✅ REQUIRED by BaseStrategy - Called on every price tick from Deriv
        This method MUST exist for the strategy to be instantiated!
        """
        try:
            # Extract price from the data object
            current_price = None
            
            # MarketDataStream might have different attributes
            if hasattr(data, 'price'):
                current_price = data.price
            elif hasattr(data, 'current_price'):
                current_price = data.current_price
            elif isinstance(data, dict):
                current_price = data.get('price') or data.get('current_price')
            
            if current_price is None:
                return None
            
            # Filter for correct symbol
            if hasattr(data, 'symbol') and data.symbol != self.symbol:
                return None
            
            # Update price history
            self.price_history.append(current_price)
            
            # Need enough data points
            if len(self.price_history) < self.lookback_periods + 1:
                return None
            
            # Calculate momentum
            old_price = self.price_history[0]
            price_change_pct = ((current_price - old_price) / old_price) * 100
            
            # Check position limit
            if len(self.positions) >= self.max_positions:
                return None
            
            # Generate signals
            if price_change_pct > self.momentum_threshold:
                logger.info(f"🔔 {self.name}: Strong UP momentum ({price_change_pct:.2f}%)")
                return TradingSignal(
                    action=ActionType.MULTUP,
                    symbol=self.symbol,
                    stake_amount=self.stake_amount,
                    multiplier=self.multiplier,
                    currency="USD",
                    timestamp=datetime.utcnow()
                )
            
            elif price_change_pct < -self.momentum_threshold:
                logger.info(f"🔔 {self.name}: Strong DOWN momentum ({price_change_pct:.2f}%)")
                return TradingSignal(
                    action=ActionType.MULTDOWN,
                    symbol=self.symbol,
                    stake_amount=self.stake_amount,
                    multiplier=self.multiplier,
                    currency="USD",
                    timestamp=datetime.utcnow()
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error in on_tick: {e}")
            return None
    
    # ========== OPTIONAL: analyze method for compatibility ==========
    
    async def analyze(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        Alternative method that works with dictionary market data
        """
        current_price = market_data.get("current_price")
        timestamp = market_data.get("timestamp", datetime.utcnow())
        
        if not current_price:
            return None
        
        self.price_history.append(current_price)
        
        if len(self.price_history) < self.lookback_periods + 1:
            return None
        
        old_price = self.price_history[0]
        price_change_pct = ((current_price - old_price) / old_price) * 100
        
        if len(self.positions) >= self.max_positions:
            return None
        
        if price_change_pct > self.momentum_threshold:
            return TradingSignal(
                action=ActionType.MULTUP,
                symbol=self.symbol,
                stake_amount=self.stake_amount,
                multiplier=self.multiplier,
                currency="USD",
                timestamp=timestamp
            )
        elif price_change_pct < -self.momentum_threshold:
            return TradingSignal(
                action=ActionType.MULTDOWN,
                symbol=self.symbol,
                stake_amount=self.stake_amount,
                multiplier=self.multiplier,
                currency="USD",
                timestamp=timestamp
            )
        
        return None
    
    @property
    def max_positions(self) -> int:
        return 2
    
    @property
    def min_signal_interval(self) -> int:
        return 30