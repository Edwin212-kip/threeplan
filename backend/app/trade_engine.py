"""
ENHANCED TRADING ENGINE - STEP 3
Integration of real market data, risk management, and performance dashboard
This replaces the simulated engine from Step 2 with production-ready features
"""

import asyncio
import signal
import sys
from datetime import datetime
from typing import Dict, Any, Optional

from executor.Deriv_executor import DerivExecutor
from executor.market_data_stream import MarketDataStream
from risk_management.risk_manager import RiskManager, RiskConfig
from monitoring.performance_dashboard import PerformanceDashboard
from strategies.bollinger_bands import BollingerBandsStrategy
from strategies.simple_momentum import SMAMomentumStrategy
from utils.logger import logger


class EnhancedTradingEngine:
    """
    Production trading engine with:
    - Real Deriv market data integration
    - Advanced risk management
    - Live performance dashboard
    """
    
    def __init__(self, demo_mode: bool = True):
        """
        Args:
            demo_mode: If True, uses simulation; if False, uses real Deriv data
        """
        self.executor = DerivExecutor()
        self.market_stream = None
        self.risk_manager = None
        self.dashboard = PerformanceDashboard(update_interval=5)
        self.strategies = []
        self.running = False
        self.demo_mode = demo_mode
        
        # Track strategy performance
        self.strategy_stats = {}
        
    async def initialize(self):
        """Initialize all components"""
        logger.info("🚀 Initializing Enhanced Trading Engine (Step 3)")
        
        # Connect to Deriv
        if not await self.executor.connect():
            raise Exception("Failed to connect to Deriv")
        
        # Get initial balance for risk management
        balance = await self.executor.get_balance()
        if balance:
            # Configure risk management
            risk_config = RiskConfig(
                max_position_size=10.0,
                max_daily_loss=50.0,
                max_drawdown=20.0,
                max_concurrent_positions=3,
                max_daily_trades=10,
                risk_per_trade=0.02  # 2% per trade
            )
            self.risk_manager = RiskManager(initial_balance=balance, config=risk_config)
            logger.info(f"✅ Risk Manager initialized with ${balance:.2f}")

            self.dashboard.starting_balance = balance  # Pass initial balance to dashboard
            logger.info(f"✅ Dashboard initialized with starting balance ${balance:.2f}")
        else:
            logger.warning("Could not fetch balance, using default risk settings")
            self.risk_manager = RiskManager(initial_balance=10000)
            self.dashboard.starting_balance = 10000  # Default starting balance for dashboard           
        
        # Initialize market data stream
        self.market_stream = MarketDataStream(self.executor.connection)
        
        # Initialize strategies
        self._init_strategies()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _init_strategies(self):
        """Initialize trading strategies"""
        
        # Strategy 1: Bollinger Bands (your requested strategy)
        bb_strategy = BollingerBandsStrategy(
            symbol="R_100",
            stake_amount=1.0,
            multiplier=100,
            period=20,  # 20 periods = 100 minutes for 5-min candles
            num_std=2.0
        )
        self.strategies.append(bb_strategy)
        self.strategy_stats[bb_strategy.name] = {
            "signals": 0,
            "trades": 0,
            "pnl": 0.0
        }
        
        # Strategy 2: Momentum Strategy
        mom_strategy = SMAMomentumStrategy(
            symbol="R_100",
            stake_amount=1.0,
            multiplier=100,
            lookback_periods=5,
            momentum_threshold=0.3
        )
        self.strategies.append(mom_strategy)
        self.strategy_stats[mom_strategy.name] = {
            "signals": 0,
            "trades": 0,
            "pnl": 0.0
        }
        
        logger.info(f"✅ Loaded {len(self.strategies)} strategies")
        
    async def handle_market_data(self, market_data: Dict[str, Any]):
        """
        Process incoming market data through all strategies
        This is called for every tick/candle from Deriv
        """
        if not self.running:
            return
            
        # Process each strategy
        for strategy in self.strategies:
            if not strategy.is_active:
                continue
                
            try:
                # Analyze market data
                signal = await strategy.analyze(market_data)
                
                if signal:
                    self.strategy_stats[strategy.name]["signals"] += 1
                    logger.info(f"📊 SIGNAL: {strategy.name} -> {signal.action.value} on {signal.symbol}")
                    
                    # Apply position sizing from risk manager
                    confidence = 1.0  # Could be based on signal strength
                    recommended_size = self.risk_manager.calculate_position_size(
                        self.risk_manager.current_balance,
                        confidence
                    )
                    
                    # Override signal stake with risk-managed size
                    signal.stake_amount = min(signal.stake_amount, recommended_size)
                    
                    # Validate trade with risk manager
                    is_allowed, reason = self.risk_manager.validate_trade(
                        signal.stake_amount,
                        self.risk_manager.current_balance
                    )
                    
                    if not is_allowed:
                        logger.warning(f"🚫 Trade blocked by risk manager: {reason}")
                        continue
                    
                    # Execute trade
                    result = await self.executor.open_position(signal)
                    
                    # Record trade
                    trade_record = {
                        "contract_id": result.get("buy", {}).get("contract_id"),
                        "action": signal.action.value,
                        "amount": signal.stake_amount,
                        "profit_loss": 0,  # Will update when closed
                        "timestamp": datetime.now(),
                        "is_open": True,
                        "strategy": strategy.name
                    }
                    self.risk_manager.record_trade(trade_record)
                    self.dashboard.add_trade(trade_record)
                    
                    self.strategy_stats[strategy.name]["trades"] += 1
                    
                    # Notify strategy
                    strategy.on_signal_executed(signal, result)
                    
            except Exception as e:
                logger.error(f"Error in strategy {strategy.name}: {e}")
                
    async def monitor_positions(self):
        """Monitor open positions and check for take profit/stop loss"""
        while self.running:
            try:
                # Get active positions from Deriv
                active_positions = await self.executor.get_active_positions()
                
                # Check each position against risk rules
                for position in active_positions:
                    contract_id = position.get("contract_id")
                    current_profit = position.get("profit", 0)
                    entry_price = position.get("entry_price", 0)
                    current_price = position.get("current_price", entry_price)
                    
                    # Calculate percentage change
                    pct_change = ((current_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
                    
                    # Check stop loss
                    if pct_change <= -self.risk_manager.config.stop_loss_percentage * 100:
                        logger.warning(f"⚠️ STOP LOSS triggered for {contract_id} (Loss: {pct_change:.1f}%)")
                        # Close position
                        close_request = {"sell": contract_id, "price": 0}
                        response = await self.executor.connection.send(close_request)
                        
                        if response.get("sell"):
                            profit_loss = response["sell"].get("profit", 0)
                            # Update trade record with P&L
                            for trade in self.risk_manager.trade_history:
                                if trade.get("trade_id") == contract_id:
                                    trade["profit_loss"] = profit_loss
                                    trade["is_open"] = False
                                    self.strategy_stats[trade.get("strategy", "Unknown")]["pnl"] += profit_loss
                                    break
                    
                    # Check take profit
                    elif pct_change >= self.risk_manager.config.take_profit_percentage * 100:
                        logger.info(f"🎯 TAKE PROFIT triggered for {contract_id} (Profit: {pct_change:.1f}%)")
                        close_request = {"sell": contract_id, "price": 0}
                        response = await self.executor.connection.send(close_request)
                        
                        if response.get("sell"):
                            profit_loss = response["sell"].get("profit", 0)
                            for trade in self.risk_manager.trade_history:
                                if trade.get("trade_id") == contract_id:
                                    trade["profit_loss"] = profit_loss
                                    trade["is_open"] = False
                                    self.strategy_stats[trade.get("strategy", "Unknown")]["pnl"] += profit_loss
                                    break
                
                await asyncio.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring positions: {e}")
                await asyncio.sleep(5)
                
    async def display_dashboard_loop(self):
        """Continuous dashboard display"""
        while self.running:
            # Update dashboard with latest metrics
            risk_metrics = self.risk_manager.get_risk_metrics()
            
            # Add emergency stop flag
            should_stop, stop_reason = self.risk_manager.should_stop_trading()
            risk_metrics["should_stop"] = (should_stop, stop_reason)
            risk_metrics["initial_balance"] = self.risk_manager.initial_balance
            risk_metrics["max_daily_trades"] = self.risk_manager.config.max_daily_trades
            risk_metrics["max_daily_loss"] = self.risk_manager.config.max_daily_loss
            risk_metrics["max_concurrent_positions"] = self.risk_manager.config.max_concurrent_positions
            risk_metrics["market_connected"] = self.market_stream.listening if self.market_stream else False
            
            self.dashboard.update_metrics(risk_metrics, self.strategy_stats)
            self.dashboard.display()
            
            await asyncio.sleep(self.dashboard.update_interval)
            
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info("\n⚠️ Shutdown signal received. Closing positions and saving data...")
        self.running = False
        
    async def run(self, duration_minutes: int = None, use_realtime: bool = True):
        """
        Run the enhanced trading engine
        
        Args:
            duration_minutes: How long to run (None = run until stopped)
            use_realtime: True = use real Deriv data, False = use simulation
        """
        await self.initialize()
        
        self.running = True
        
        # Start market data stream
        if use_realtime and not self.demo_mode:
            logger.info("📡 Connecting to REAL Deriv market data...")
            
            # Subscribe to real data
            await self.market_stream.subscribe_candles("R_100", granularity=300)  # 5-min candles
            await self.market_stream.start_listening()
            
            # Register market data handler
            self.market_stream.callbacks.append(self.handle_market_data)
            
        else:
            logger.info("🎮 Running in DEMO mode with simulated data")
            # In demo mode, we'll simulate data
            asyncio.create_task(self._simulate_market_data())
        
        # Start background tasks
        monitor_task = asyncio.create_task(self.monitor_positions())
        dashboard_task = asyncio.create_task(self.display_dashboard_loop())
        
        logger.info("=" * 80)
        logger.info("🚀 ENHANCED TRADING ENGINE RUNNING")
        logger.info(f"   Market Data: {'REAL DERIV' if use_realtime and not self.demo_mode else 'SIMULATED'}")
        logger.info(f"   Risk Management: ACTIVE (Max Loss: ${self.risk_manager.config.max_daily_loss})")
        logger.info(f"   Dashboard: LIVE (updates every {self.dashboard.update_interval}s)")
        if duration_minutes:
            logger.info(f"   Run Duration: {duration_minutes} minutes")
        logger.info("=" * 80)
        
        try:
            if duration_minutes:
                await asyncio.sleep(duration_minutes * 60)
                self.running = False
            else:
                while self.running:
                    await asyncio.sleep(1)
                    
        except KeyboardInterrupt:
            logger.info("\n⚠️ Stopping trading engine...")
        finally:
            self.running = False
            
            # Cleanup
            if self.market_stream:
                await self.market_stream.stop_listening()
            
            await monitor_task
            await dashboard_task
            
            # Generate final report
            report = self.dashboard.generate_report()
            logger.info(report)
            
            # Save report to file
            report_file = f"trading_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w') as f:
                f.write(report)
            logger.info(f"📄 Performance report saved to {report_file}")
            
            await self.executor.disconnect()
            
    async def _simulate_market_data(self):
        """Simulate market data for demo/testing"""
        import random
        current_price = 100.0
        
        while self.running:
            # Simulate price movement
            change = random.uniform(-1.5, 1.5)
            current_price += change
            current_price = max(90, min(110, current_price))
            
            market_data = {
                "current_price": current_price,
                "symbol": "R_100",
                "timestamp": datetime.now(),
                "is_simulated": True
            }
            
            await self.handle_market_data(market_data)
            await asyncio.sleep(5)  # Simulate 5-second updates

async def main():
    """Main entry point for Step 3"""
    engine = EnhancedTradingEngine(demo_mode=True)  # Set to False for real Deriv data
    
    try:
        # Run for 2 minutes in demo mode, or indefinitely with real data
        await engine.run(duration_minutes=20, use_realtime=False)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())