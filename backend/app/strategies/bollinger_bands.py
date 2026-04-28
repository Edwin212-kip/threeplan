"""
BOLLINGER BANDS STRATEGY
Opens MULTUP position when price touches lower band
Closes when price touches upper band
"""

import numpy as np
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from collections import deque
from strategies.base import BaseStrategy
from models.signal import TradingSignal, ActionType
from utils.logger import logger

class BollingerBandsStrategy(BaseStrategy):
    """
    Bollinger Bands strategy:
    - Open MULTUP when price touches lower band
    - Close position when price touches upper band
    """
    
    def __init__(self, symbol: str, stake_amount: float = 1.0, multiplier: int = 100,
                 period: int = 20, num_std: float = 2.0):
        """
        Args:
            period: Moving average period (default 20 for 5-min candles = 100 minutes)
            num_std: Number of standard deviations for bands (default 2)
        """
        super().__init__(
            name=f"BollingerBands_{symbol}",
            symbol=symbol,
            stake_amount=stake_amount,
            multiplier=multiplier
        )
        self.period = period
        self.num_std = num_std
        self.price_history = deque(maxlen=period * 2)
        self.bb_lower = None
        self.bb_upper = None
        self.bb_middle = None
        
    # ========== REQUIRED ABSTRACT METHODS ==========
    
    async def on_tick(self, price_data: Dict[str, Any]) -> None:
        """
        REQUIRED: Called on every price tick from Deriv
        This method MUST be implemented because BaseStrategy defines it as abstract
        """
        # Extract price from tick data (Deriv sends different formats)
        current_price = price_data.get("quote") or price_data.get("current_price")
        
        if current_price:
            # Update price history
            self.price_history.append(current_price)
            
            # Calculate Bollinger Bands if we have enough data
            if len(self.price_history) >= self.period:
                self.bb_lower, self.bb_middle, self.bb_upper = self.calculate_bollinger_bands(
                    list(self.price_history)
                )
                
                # Check for lower band touch (entry signal)
                if current_price <= self.bb_lower:
                    logger.info(f"🔔 {self.name}: LOWER BAND TOUCH at {current_price:.5f}")
                    # Generate signal (will be picked up by analyze method or directly)
    
    async def analyze(self, market_data: Dict[str, Any]) -> Optional[TradingSignal]:
        """
        REQUIRED: Analyze market data and return trading signal
        """
        current_price = market_data.get("current_price")
        timestamp = market_data.get("timestamp", datetime.now())
        
        if not current_price:
            return None
        
        # Update price history
        self.price_history.append(current_price)
        
        # Calculate Bollinger Bands from historical prices
        if len(self.price_history) >= self.period:
            self.bb_lower, self.bb_middle, self.bb_upper = self.calculate_bollinger_bands(
                list(self.price_history)
            )
            
            # Get previous price for touch detection
            prev_price = self.price_history[-2] if len(self.price_history) >= 2 else None
            
            # Detect band touch
            touch = self.detect_band_touch(current_price, prev_price)
            
            # Generate signal for lower band touch
            if touch == 'lower' and len(self.positions) < self.max_positions:
                logger.info(f"🔔 {self.name}: LOWER BAND TOUCH - Generating MULTUP signal")
                
                # Create MULTUP signal
                signal = TradingSignal(
                    action=ActionType.MULTUP,
                    symbol=self.symbol,
                    stake_amount=self.stake_amount,
                    multiplier=self.multiplier,
                    currency="USD",
                    timestamp=timestamp
                )
                
                return signal
        
        return None
    
    # ========== HELPER METHODS ==========
    
    def calculate_bollinger_bands(self, prices: List[float]) -> tuple:
        """Calculate Bollinger Bands"""
        if len(prices) < self.period:
            return None, None, None
        
        # Calculate simple moving average
        sma = np.mean(prices[-self.period:])
        
        # Calculate standard deviation
        std = np.std(prices[-self.period:])
        
        # Calculate bands
        upper_band = sma + (std * self.num_std)
        lower_band = sma - (std * self.num_std)
        
        return lower_band, sma, upper_band
    
    def detect_band_touch(self, current_price: float, prev_price: Optional[float] = None) -> Optional[str]:
        """Detect if price touched lower or upper band"""
        if self.bb_lower is None or self.bb_upper is None:
            return None
        
        # Check for lower band touch
        if current_price <= self.bb_lower:
            if prev_price is None or prev_price > self.bb_lower:
                return 'lower'
        
        # Check for upper band touch
        elif current_price >= self.bb_upper:
            if prev_price is None or prev_price < self.bb_upper:
                return 'upper'
        
        return None