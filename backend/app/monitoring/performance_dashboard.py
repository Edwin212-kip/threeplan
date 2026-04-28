"""
PERFORMANCE METRICS DASHBOARD
Real-time monitoring of trading performance, risk metrics, and system health
Displays formatted output with colors and progress bars
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import deque
from utils.logger import logger
import math

class PerformanceDashboard:
    """
    Live trading dashboard showing key metrics
    Updates in real-time and provides performance analysis
    """
    
    def __init__(self, update_interval: int = 5):
        """
        Args:
            update_interval: How often to refresh display (seconds)
        """
        self.update_interval = update_interval
        self.start_time = datetime.now()
        self.metrics_history = deque(maxlen=100)  # Store last 100 metrics snapshots
        
        # Trade statistics
        self.trades = []
        self.winning_trades = []
        self.losing_trades = []
        
    def update_metrics(self, risk_metrics: Dict[str, Any], strategy_stats: Dict[str, Any]):
        """
        Update dashboard with latest metrics
        
        Args:
            risk_metrics: Metrics from RiskManager
            strategy_stats: Performance per strategy
        """
        snapshot = {
            "timestamp": datetime.now(),
            "risk_metrics": risk_metrics.copy(),
            "strategy_stats": strategy_stats.copy()
        }
        self.metrics_history.append(snapshot)
        
    def add_trade(self, trade: Dict[str, Any]):
        """Add a trade to the history"""
        self.trades.append(trade)
        if trade.get("profit_loss", 0) > 0:
            self.winning_trades.append(trade)
        else:
            self.losing_trades.append(trade)
            
    def calculate_sharpe_ratio(self) -> float:
        """
        Calculate Sharpe ratio (risk-adjusted returns)
        Higher is better (>1 is good, >2 is excellent)
        """
        if len(self.trades) < 2:
            return 0.0
            
        returns = [t.get("profit_loss", 0) / t.get("amount", 1) for t in self.trades]
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance) if variance > 0 else 0.001
        
        # Risk-free rate assumed 0 for crypto/Forex (simplified)
        sharpe = avg_return / std_dev if std_dev > 0 else 0
        return sharpe
        
    def calculate_max_drawdown_from_history(self) -> float:
        """Calculate maximum drawdown from historical trades"""
        if not self.trades:
            return 0.0
            
        balance_curve = [self.starting_balance]
        for trade in self.trades:
            last_balance = balance_curve[-1]
            new_balance = last_balance + trade.get("profit_loss", 0)
            balance_curve.append(new_balance)
            
        peak = balance_curve[0]
        max_drawdown = 0
        
        for balance in balance_curve:
            if balance > peak:
                peak = balance
            drawdown = (peak - balance) / peak * 100 if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
                
        return max_drawdown
        
    def create_progress_bar(self, percentage: float, width: int = 30) -> str:
        """Create a text-based progress bar"""
        filled = int(width * percentage / 100)
        bar = '█' * filled + '░' * (width - filled)
        return f"[{bar}] {percentage:.1f}%"
        
    def display(self):
        """Display the dashboard with all metrics"""
        if not self.metrics_history:
            return
            
        latest = self.metrics_history[-1]
        risk = latest["risk_metrics"]
        strategies = latest["strategy_stats"]
        
        # Clear screen for live update effect
        print("\033[2J\033[H", end="")  # ANSI clear screen
        print("=" * 80)
        print("📊 DERIV TRADING BOT - LIVE PERFORMANCE DASHBOARD")
        print("=" * 80)
        
        # Header with runtime
        runtime = datetime.now() - self.start_time
        print(f"⏱️  Runtime: {str(runtime).split('.')[0]} | 📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 80)
        
        # ACCOUNT METRICS SECTION
        print("\n💰 ACCOUNT METRICS")
        print(f"   Initial Balance:     ${risk.get('initial_balance', 0):10,.2f}")
        print(f"   Current Balance:     ${risk.get('current_balance', 0):10,.2f}")
        
        total_pnl = risk.get('total_pnl', 0)
        pnl_color = "🟢" if total_pnl >= 0 else "🔴"
        print(f"   Total P&L:            ${total_pnl:10,.2f} {pnl_color}")
        
        total_return = (total_pnl / risk.get('initial_balance', 1)) * 100 if risk.get('initial_balance', 0) > 0 else 0
        print(f"   Total Return:         {total_return:9.2f}%")
        
        # RISK METRICS SECTION
        print("\n🎯 RISK METRICS")
        print(f"   Daily Trades:         {risk.get('daily_trades', 0):3d} / {risk.get('max_daily_trades', 0)}")
        daily_trades_bar = self.create_progress_bar(
            (risk.get('daily_trades', 0) / risk.get('max_daily_trades', 1)) * 100, 20
        )
        print(f"                         {daily_trades_bar}")
        
        print(f"   Daily P&L:            ${risk.get('daily_pnl', 0):+10,.2f}")
        daily_loss_pct = abs(risk.get('daily_pnl', 0) / risk.get('max_daily_loss', 1)) * 100
        if risk.get('daily_pnl', 0) < 0:
            print(f"   Daily Loss Usage:     {daily_loss_pct:.1f}% of ${risk.get('max_daily_loss', 0)}")
        
        current_drawdown = risk.get('current_drawdown', 0)
        drawdown_color = "🟢" if current_drawdown < 10 else "🟡" if current_drawdown < 20 else "🔴"
        print(f"   Current Drawdown:     {current_drawdown:9.2f}% {drawdown_color}")
        print(f"   Open Positions:       {risk.get('open_positions', 0):3d} / {risk.get('max_concurrent_positions', 0)}")
        
        # PERFORMANCE METRICS SECTION
        print("\n📈 PERFORMANCE METRICS")
        win_rate = risk.get('win_rate', 0)
        win_rate_color = "🟢" if win_rate >= 50 else "🟡" if win_rate >= 30 else "🔴"
        print(f"   Win Rate:             {win_rate:9.1f}% {win_rate_color}")
        
        total_trades = risk.get('total_trades', 0)
        print(f"   Total Trades:         {total_trades:3d}")
        print(f"   Winning Trades:       {risk.get('winning_trades', 0):3d}")
        print(f"   Losing Trades:        {risk.get('losing_trades', 0):3d}")
        
        # Calculate additional metrics from history
        if total_trades > 0:
            sharpe = self.calculate_sharpe_ratio()
            sharpe_color = "🟢" if sharpe > 1 else "🟡" if sharpe > 0.5 else "🔴"
            print(f"   Sharpe Ratio:         {sharpe:9.2f} {sharpe_color}")
            
            max_dd = self.calculate_max_drawdown_from_history()
            print(f"   Historical Max DD:    {max_dd:9.2f}%")
            
            avg_win = sum(t.get('profit_loss', 0) for t in self.winning_trades) / len(self.winning_trades) if self.winning_trades else 0
            avg_loss = sum(t.get('profit_loss', 0) for t in self.losing_trades) / len(self.losing_trades) if self.losing_trades else 0
            print(f"   Avg Win / Loss:       ${avg_win:+.2f} / ${avg_loss:+.2f}")
        
        # STRATEGY PERFORMANCE SECTION
        print("\n🤖 STRATEGY PERFORMANCE")
        for strategy_name, stats in strategies.items():
            print(f"   📊 {strategy_name}")
            print(f"      Signals: {stats.get('signals', 0)} | Trades: {stats.get('trades', 0)} | P&L: ${stats.get('pnl', 0):+.2f}")
        
        # HEALTH INDICATORS
        print("\n🩺 SYSTEM HEALTH")
        should_stop, stop_reason = risk.get('should_stop', (False, "Normal"))
        if should_stop:
            print(f"   ⚠️  EMERGENCY STOP: {stop_reason}")
        else:
            print(f"   ✅ System Status: {stop_reason}")
            
        print(f"   📡 Market Data: {'🟢 Connected' if risk.get('market_connected', False) else '🔴 Disconnected'}")
        
        print("\n" + "=" * 80)
        print(f"🔄 Dashboard refreshes every {self.update_interval} seconds (Press Ctrl+C to stop)")
        
    def generate_report(self) -> str:
        """Generate a detailed performance report"""
        if not self.trades:
            return "No trades executed yet"
            
        report = []
        report.append("\n" + "=" * 80)
        report.append("DERIV TRADING BOT - PERFORMANCE REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Runtime: {datetime.now() - self.start_time}")
        
        # Trade statistics
        total_pnl = sum(t.get('profit_loss', 0) for t in self.trades)
        winning_trades = [t for t in self.trades if t.get('profit_loss', 0) > 0]
        losing_trades = [t for t in self.trades if t.get('profit_loss', 0) < 0]
        
        report.append(f"\n📊 TRADE SUMMARY")
        report.append(f"   Total Trades:      {len(self.trades)}")
        report.append(f"   Winning Trades:    {len(winning_trades)}")
        report.append(f"   Losing Trades:     {len(losing_trades)}")
        report.append(f"   Win Rate:          {(len(winning_trades)/len(self.trades)*100):.1f}%")
        report.append(f"   Total P&L:         ${total_pnl:+.2f}")
        
        if winning_trades:
            avg_win = sum(t.get('profit_loss', 0) for t in winning_trades) / len(winning_trades)
            report.append(f"   Average Win:       ${avg_win:+.2f}")
        if losing_trades:
            avg_loss = sum(t.get('profit_loss', 0) for t in losing_trades) / len(losing_trades)
            report.append(f"   Average Loss:      ${avg_loss:+.2f}")
            
        # Best/Worst trades
        if self.trades:
            best_trade = max(self.trades, key=lambda x: x.get('profit_loss', 0))
            worst_trade = min(self.trades, key=lambda x: x.get('profit_loss', 0))
            report.append(f"\n🏆 BEST TRADE: +${best_trade.get('profit_loss', 0):.2f} on {best_trade.get('timestamp', 'N/A')}")
            report.append(f"💩 WORST TRADE: ${worst_trade.get('profit_loss', 0):.2f} on {worst_trade.get('timestamp', 'N/A')}")
            
        # Risk metrics
        report.append(f"\n⚠️  RISK METRICS")
        report.append(f"   Max Drawdown:      {self.calculate_max_drawdown_from_history():.1f}%")
        report.append(f"   Sharpe Ratio:      {self.calculate_sharpe_ratio():.2f}")
        
        report.append("\n" + "=" * 80)
        
        return "\n".join(report)