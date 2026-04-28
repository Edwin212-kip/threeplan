"""
ADVANCED RISK MANAGEMENT SYSTEM
Protects capital by enforcing position limits, daily loss limits, and risk per trade
This module integrates with the trading engine to prevent over-trading
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass
from utils.logger import logger

@dataclass
class RiskConfig:
    """Configuration for risk management parameters"""
    max_position_size: float = 10.0  # Maximum $ per position
    max_daily_loss: float = 50.0  # Maximum daily loss in $
    max_drawdown: float = 20.0  # Maximum drawdown percentage
    max_concurrent_positions: int = 3  # Max open positions at once
    max_daily_trades: int = 10  # Maximum trades per day
    risk_per_trade: float = 0.02  # 2% of account per trade
    stop_loss_percentage: float = 0.05  # 5% stop loss
    take_profit_percentage: float = 0.10  # 10% take profit
    
class RiskManager:
    """
    Risk Manager - Validates all trade requests before execution
    Tracks P&L, enforces limits, and calculates position sizing
    """
    
    def __init__(self, initial_balance: float, config: Optional[RiskConfig] = None):
        """
        Args:
            initial_balance: Starting account balance
            config: Risk configuration parameters
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.config = config or RiskConfig()
        
        # Tracking variables
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.today = datetime.now().date()
        self.trade_history = []
        self.open_positions = []
        self.peak_balance = initial_balance
        
        logger.info(f"🎯 Risk Manager initialized with ${initial_balance:.2f} capital")
        logger.info(f"   Max position: ${self.config.max_position_size}")
        logger.info(f"   Max daily loss: ${self.config.max_daily_loss}")
        logger.info(f"   Risk per trade: {self.config.risk_per_trade*100}%")
        
    def reset_daily_counters(self):
        """Reset daily counters at midnight"""
        current_day = datetime.now().date()
        if current_day != self.today:
            logger.info(f"📅 New trading day - Resetting daily counters")
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.today = current_day
            
    def calculate_position_size(self, account_balance: float, confidence: float = 1.0) -> float:
        """
        Calculate position size based on risk per trade and account balance
        
        Args:
            account_balance: Current account balance
            confidence: Strategy confidence (0-1) to adjust position size
            
        Returns:
            Recommended position size in USD
        """
        # Base position size from risk percentage
        risk_based_size = account_balance * self.config.risk_per_trade
        
        # Apply confidence factor (lower confidence = smaller position)
        adjusted_size = risk_based_size * confidence
        
        # Enforce maximum position size
        final_size = min(adjusted_size, self.config.max_position_size)
        
        # Round to 2 decimal places
        final_size = round(final_size, 2)
        
        logger.debug(f"Position size calculation: Balance=${account_balance:.2f}, "
                    f"Confidence={confidence:.2f}, Size=${final_size:.2f}")
        
        return final_size
        
    def validate_trade(self, signal_amount: float, current_balance: float) -> tuple[bool, str]:
        """
        Validate if a trade should be allowed based on risk rules
        
        Args:
            signal_amount: Proposed trade amount
            current_balance: Current account balance
            
        Returns:
            (is_allowed, reason)
        """
        self.reset_daily_counters()
        self.current_balance = current_balance
        
        # Track peak balance for drawdown calculation
        if current_balance > self.peak_balance:
            self.peak_balance = current_balance
        
        # Check 1: Daily trade count limit
        if self.daily_trades >= self.config.max_daily_trades:
            return False, f"Daily trade limit reached ({self.config.max_daily_trades})"
        
        # Check 2: Daily loss limit
        if self.daily_pnl <= -self.config.max_daily_loss:
            return False, f"Daily loss limit reached (${abs(self.daily_pnl):.2f} loss)"
        
        # Check 3: Maximum drawdown
        drawdown = ((self.peak_balance - current_balance) / self.peak_balance) * 100
        if drawdown > self.config.max_drawdown:
            return False, f"Max drawdown exceeded ({drawdown:.1f}% > {self.config.max_drawdown}%)"
        
        # Check 4: Position size limit
        if signal_amount > self.config.max_position_size:
            return False, f"Position size ${signal_amount} exceeds ${self.config.max_position_size} limit"
        
        # Check 5: Account health (minimum balance)
        if current_balance < self.initial_balance * 0.5:  # 50% drawdown protection
            return False, f"Account balance critically low (${current_balance:.2f})"
        
        # Check 6: Concurrent positions limit
        if len(self.open_positions) >= self.config.max_concurrent_positions:
            return False, f"Max concurrent positions reached ({self.config.max_concurrent_positions})"
        
        return True, "Trade validated"
        
    def record_trade(self, trade: Dict[str, Any]):
        """
        Record a trade for tracking and performance analysis
        
        Args:
            trade: Trade details including amount, action, result
        """
        self.daily_trades += 1
        
        # Track loss for daily limit
        if trade.get("profit_loss", 0) < 0:
            self.daily_pnl += trade["profit_loss"]
        
        trade_record = {
            "trade_id": trade.get("contract_id"),
            "timestamp": datetime.now(),
            "action": trade.get("action"),
            "amount": trade.get("amount"),
            "profit_loss": trade.get("profit_loss", 0),
            "balance_after": trade.get("balance_after", self.current_balance)
        }
        
        self.trade_history.append(trade_record)
        
        # Update current balance if P&L provided
        if "profit_loss" in trade:
            self.current_balance += trade["profit_loss"]
            
        # Update open positions
        if trade.get("is_open", False):
            self.open_positions.append(trade_record)
        elif trade.get("contract_id"):
            # Remove closed position
            self.open_positions = [p for p in self.open_positions 
                                  if p["trade_id"] != trade["contract_id"]]
        
        logger.info(f"📝 Trade recorded: {trade['action']} ${trade['amount']:.2f} "
                   f"P/L: ${trade.get('profit_loss', 0):+.2f}")
        
    def get_risk_metrics(self) -> Dict[str, Any]:
        """
        Calculate current risk metrics for monitoring
        
        Returns:
            Dictionary of risk metrics
        """
        total_trades = len(self.trade_history)
        winning_trades = len([t for t in self.trade_history if t.get("profit_loss", 0) > 0])
        losing_trades = len([t for t in self.trade_history if t.get("profit_loss", 0) < 0])
        
        total_pnl = sum(t.get("profit_loss", 0) for t in self.trade_history)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        current_drawdown = ((self.peak_balance - self.current_balance) / self.peak_balance * 100) if self.peak_balance > 0 else 0
        
        return {
            "current_balance": self.current_balance,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "current_drawdown": current_drawdown,
            "daily_trades": self.daily_trades,
            "daily_pnl": self.daily_pnl,
            "open_positions": len(self.open_positions),
            "peak_balance": self.peak_balance,
            "risk_per_trade": self.config.risk_per_trade,
            "max_daily_loss": self.config.max_daily_loss
        }
        
    def should_stop_trading(self) -> tuple[bool, str]:
        """
        Emergency check - determines if trading should stop completely
        
        Returns:
            (should_stop, reason)
        """
        metrics = self.get_risk_metrics()
        
        # Emergency stop conditions
        if metrics["current_balance"] < self.initial_balance * 0.3:
            return True, f"Critical capital loss (>70% drawdown)"
            
        if metrics["win_rate"] < 20 and metrics["total_trades"] > 10:
            return True, f"Very low win rate ({metrics['win_rate']:.1f}%)"
            
        if metrics["current_drawdown"] > 30:
            return True, f"Severe drawdown ({metrics['current_drawdown']:.1f}%)"
            
        return False, "Trading allowed"