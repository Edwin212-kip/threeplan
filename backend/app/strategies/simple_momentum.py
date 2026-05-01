"""
SIMPLE MOMENTUM STRATEGY - COMPLETE FIXED VERSION
Both strategies now have:
- on_tick() method (for live market data)
- analyze() method (for dictionary market data)
- on_signal_executed() method (required by trade engine)
"""

from collections import deque
from datetime import datetime
from typing import Optional, Dict, Any
import statistics

from models.signal import TradingSignal, ActionType
from executor.market_data_stream import MarketDataStream
from strategies.base import BaseStrategy
from utils.logger import logger


# ==================================================================
# 1st STRATEGY: SMA Crossover Momentum (uses BaseStrategy)
# ==================================================================
class SMAMomentumStrategy(BaseStrategy):
    """Uses fast/slow SMA crossover + price momentum to generate signals."""
    
    def __init__(self, symbol: str, stake_amount: float = 1.0, multiplier: int = 100,lookback_periods: int = 5, momentum_threshold: float = 0.5):
        self.symbol = symbol
        self.stake_amount = stake_amount
        self.multiplier = multiplier
        self.lookback_periods = lookback_periods
        self.momentum_threshold = momentum_threshold
        self.prices = deque(maxlen=50)          # store last 50 prices
        self.fast_period = 5
        self.slow_period = 20
        self.volatility_threshold = 2.0
        self.is_active = True
        self.positions = []
        self.name = f"SMAMomentum_{symbol}"

    # ---------- REQUIRED BY MARKET DATA STREAM ----------
    async def on_tick(self, data: MarketDataStream) -> Optional[TradingSignal]:
        """Called on every price tick – generates signals."""
        if data.symbol != self.symbol:
            return None

        self.prices.append(data.price)
        if len(self.prices) < self.slow_period:
            return None

        fast_sma = sum(list(self.prices)[-self.fast_period:]) / self.fast_period
        slow_sma = sum(list(self.prices)[-self.slow_period:]) / self.slow_period
        momentum = self.prices[-1] - self.prices[-2]
        volatility = statistics.stdev(self.prices)

        if volatility > self.volatility_threshold:
            return None

        action = None
        if fast_sma > slow_sma and momentum > 0:
            action = ActionType.MULTUP
        elif fast_sma < slow_sma and momentum < 0:
            action = ActionType.MULTDOWN

        if action is None:
            return None

        confidence = abs(fast_sma - slow_sma) + abs(momentum)
        if confidence < 0.1:
            return None

        return TradingSignal(
            symbol=self.symbol,
            action=action,
            stake_amount=self.stake_amount,
            currency="USD",
            multiplier=100,
            timestamp=datetime.utcnow()
        )
    async def analyze(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """Same logic but works with dictionary market data (not ticks)."""
        current_price = market_data.get("current_price")
        timestamp = market_data.get("timestamp", datetime.utcnow())
        if not current_price:
            return None
        self.prices.append(current_price)
        if len(self.prices) < self.slow_period:
            return None
        fast_sma = sum(list(self.prices)[-self.fast_period:]) / self.fast_period
        slow_sma = sum(list(self.prices)[-self.slow_period:]) / self.slow_period
        momentum = self.prices[-1] - self.prices[-2]
        volatility = statistics.stdev(self.prices)
        if volatility > self.volatility_threshold:
            return None
        action = None
        if fast_sma > slow_sma and momentum > 0:
            action = ActionType.MULTUP
        elif fast_sma < slow_sma and momentum < 0:
            action = ActionType.MULTDOWN
        if action is None:
            return None
        confidence = abs(fast_sma - slow_sma) + abs(momentum)
        if confidence < 0.1:
            return None
        return TradingSignal(
            symbol=self.symbol,
            action=action,
            stake_amount=self.stake_amount,
            currency="USD",
            multiplier=100,
            timestamp=timestamp
        )

    # ---------- REQUIRED BY TRADE ENGINE (after trade execution) ----------
    def on_signal_executed(self, signal: TradingSignal, result: dict):
        """
        Callback called by trade_engine.py after a trade is opened.
        Even if empty, it MUST exist – otherwise engine crashes.
        """
        logger.info(f"✅ {self.name}: Trade executed | Action: {signal.action.value} | Result: {result.get('buy', {}).get('contract_id')}")


# ==================================================================
# 2nd STRATEGY: Simple Percentage Change Momentum (no base class)
# ==================================================================
class SimpleMomentumStrategy(BaseStrategy):
    """
    Generates BUY/SELL signals based on price change percentage over N periods.
    """
    
    def __init__(self, symbol: str, stake_amount: float = 1.0, multiplier: int = 100,
                 lookback_periods: int = 5, momentum_threshold: float = 0.5):
        self.name = f"Momentum_{symbol}"
        self.symbol = symbol
        self.stake_amount = stake_amount
        self.multiplier = multiplier
        self.is_active = True
        self.positions = []
        self.lookback_periods = lookback_periods
        self.momentum_threshold = momentum_threshold
        self.price_history = deque(maxlen=lookback_periods + 1)

    # ---------- REQUIRED BY MARKET DATA STREAM ----------
    async def on_tick(self, data: MarketDataStream) -> Optional[TradingSignal]:
        """Called on every price tick – core signal logic."""
        try:
            # Extract price (handles different attribute names)
            current_price = None
            if hasattr(data, 'price'):
                current_price = data.price
            elif hasattr(data, 'current_price'):
                current_price = data.current_price
            elif isinstance(data, dict):
                current_price = data.get('price') or data.get('current_price')

            if current_price is None:
                return None

            if hasattr(data, 'symbol') and data.symbol != self.symbol:
                return None

            self.price_history.append(current_price)
            if len(self.price_history) < self.lookback_periods + 1:
                return None

            old_price = self.price_history[0]
            price_change_pct = ((current_price - old_price) / old_price) * 100

            if len(self.positions) >= self.max_positions:
                return None

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

    # ---------- OPTIONAL / ALTERNATIVE ----------
    async def analyze(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """Same logic but works with dictionary market data (not ticks)."""
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

    # ---------- REQUIRED BY TRADE ENGINE (after trade execution) ----------
    def on_signal_executed(self, signal: TradingSignal, result: dict):
        """
        Callback called by trade_engine.py after a trade is opened.
        MUST exist even if empty. Here we log it.
        """
        logger.info(f"✅ {self.name}: Executed {signal.action.value} trade | Contract ID: {result.get('buy', {}).get('contract_id')}")

    # ---------- PROPERTIES USED BY ENGINE ----------
    @property
    def max_positions(self) -> int:
        return 2

    @property
    def min_signal_interval(self) -> int:
        return 30