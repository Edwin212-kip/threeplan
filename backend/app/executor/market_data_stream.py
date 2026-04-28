"""
REAL DERIV MARKET DATA INTEGRATION - FIXED VERSION
Now works with the locked WebSocket connection
"""

import asyncio
import json
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from collections import deque
from utils.logger import logger

class MarketDataStream:
    """
    Real-time market data handler for Deriv
    Subscribes to ticks and candles for multiple symbols
    NOW USES THE SAME LOCKED CONNECTION as DerivExecutor
    """
    
    def __init__(self, connection):
        """
        Args:
            connection: The WebSocket connection manager from Step 1
        """
        self.connection = connection
        self.subscriptions = {}  # symbol -> subscription type
        self.callbacks = []  # List of callback functions for price updates
        self.price_history = {}  # symbol -> deque of prices
        self.candle_history = {}  # symbol -> deque of candles
        self.listening = False
        self._listen_task = None
        
        # ✅ ADD: Reference to the executor's lock (will be set later)
        self._ws_lock = None
        self._executor = None
        
    def set_executor(self, executor):
        """
        ✅ NEW: Set the executor reference to use its lock
        This ensures both use the same lock for WebSocket operations
        """
        self._executor = executor
        self._ws_lock = executor._ws_lock
        
    async def _send_safe(self, request: Dict[str, Any]) -> None:
        """
        ✅ NEW: Send request using the executor's safe method
        This prevents collisions with trading operations
        """
        if self._executor:
            # Use executor's safe send method
            await self._executor._send_only(request)
        else:
            # Fallback: send without lock (risky)
            await self.connection.ws.send(json.dumps(request))
        
    async def subscribe_ticks(self, symbol: str, callback: Optional[Callable] = None):
        """
        Subscribe to real-time tick data from Deriv
        
        In Deriv's API:
        {"ticks": "R_100"} subscribes to live price ticks
        Each tick contains: {'tick': {'quote': 123.45, 'symbol': 'R_100', 'epoch': 1234567890}}
        """
        subscribe_msg = {
            "ticks": symbol,
            "subscribe": 1
        }
        
        # ✅ Use safe send method
        await self._send_safe(subscribe_msg)
        self.subscriptions[symbol] = "ticks"
        
        if callback:
            self.callbacks.append(callback)
        
        logger.info(f"📡 Subscribed to real-time ticks for {symbol}")
        
    async def subscribe_candles(self, symbol: str, granularity: int = 300, callback: Optional[Callable] = None):
        """
        Subscribe to candle data (OHLCV)
        
        Args:
            symbol: Trading symbol (e.g., "R_100")
            granularity: Candle duration in seconds (60=1min, 300=5min, 900=15min)
            callback: Function to call when new candle arrives
        """
        # Deriv uses 'candles' request with granularity
        subscribe_msg = {
            "candles": {
                "granularity": granularity,
                "symbol": symbol
            },
            "subscribe": 1
        }
        
        # ✅ Use safe send method
        await self._send_safe(subscribe_msg)
        self.subscriptions[f"{symbol}_{granularity}"] = "candles"
        
        # Initialize candle history storage
        if symbol not in self.candle_history:
            self.candle_history[symbol] = deque(maxlen=100)  # Store last 100 candles
        
        if callback:
            self.callbacks.append(callback)
        
        logger.info(f"📡 Subscribed to {granularity//60}-min candles for {symbol}")
        
    async def start_listening(self):
        """
        ✅ CHANGED: Start listening for market data messages
        Now uses the executor's lock to prevent conflicts
        """
        self.listening = True
        
        async def listen():
            while self.listening and self.connection.is_connected:
                try:
                    # ✅ CRITICAL FIX: Use the same lock as the executor
                    # This ensures we don't try to recv while a trade is happening
                    if self._ws_lock:
                        async with self._ws_lock:
                            # Only ONE operation at a time across the whole app
                            raw_message = await self.connection.ws.recv()
                            message = json.loads(raw_message)
                            await self._process_message(message)
                    else:
                        # Fallback - risky but better than nothing
                        raw_message = await self.connection.ws.recv()
                        message = json.loads(raw_message)
                        await self._process_message(message)
                    
                except Exception as e:
                    if self.listening:  # Only log if we're still supposed to be listening
                        logger.error(f"Error in market data stream: {e}")
                        await asyncio.sleep(1)
        
        self._listen_task = asyncio.create_task(listen())
        
    async def _process_message(self, message: Dict[str, Any]):
        """
        Process incoming WebSocket messages from Deriv
        Handles tick data, candle data, and subscription confirmations
        """
        # Check for tick data
        if "tick" in message:
            tick_data = message["tick"]
            symbol = tick_data.get("symbol")
            price = tick_data.get("quote")
            epoch = tick_data.get("epoch")
            timestamp = datetime.fromtimestamp(epoch)
            
            # Store in price history
            if symbol not in self.price_history:
                self.price_history[symbol] = deque(maxlen=1000)  # Store last 1000 ticks
            
            self.price_history[symbol].append({
                "price": price,
                "timestamp": timestamp,
                "volume": tick_data.get("volume", 0)
            })
            
            # Notify callbacks with real-time data
            market_data = {
                "current_price": price,
                "symbol": symbol,
                "timestamp": timestamp,
                "is_tick": True,
                "source": "real_time"
            }
            
            for callback in self.callbacks:
                try:
                    await callback(market_data)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
                    
        # Check for candle data
        elif "candles" in message:
            candles = message["candles"]
            for candle in candles:
                symbol = candle.get("symbol")
                open_price = candle.get("open")
                close_price = candle.get("close")
                high = candle.get("high")
                low = candle.get("low")
                epoch = candle.get("epoch")
                timestamp = datetime.fromtimestamp(epoch)
                
                # Store candle data
                if symbol not in self.candle_history:
                    self.candle_history[symbol] = deque(maxlen=100)
                
                candle_data = {
                    "open": open_price,
                    "close": close_price,
                    "high": high,
                    "low": low,
                    "timestamp": timestamp,
                    "volume": candle.get("volume", 0)
                }
                
                self.candle_history[symbol].append(candle_data)
                
                # Notify callbacks with candle data
                market_data = {
                    "current_price": close_price,  # Use close as current price
                    "symbol": symbol,
                    "timestamp": timestamp,
                    "high": high,
                    "low": low,
                    "open": open_price,
                    "is_candle": True,
                    "source": "real_time"
                }
                
                for callback in self.callbacks:
                    try:
                        await callback(market_data)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                        
        # Check for subscription confirmation
        elif "subscription" in message:
            subscription_id = message.get("subscription", {}).get("id")
            logger.info(f"✅ Subscription confirmed: {subscription_id}")
            
    async def stop_listening(self):
        """Stop the market data stream"""
        self.listening = False
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        # Unsubscribe from all symbols using safe send
        for symbol, sub_type in self.subscriptions.items():
            try:
                if sub_type == "ticks":
                    await self._send_safe({"forget": symbol})
                elif sub_type == "candles":
                    await self._send_safe({"forget_all": "candles"})
            except Exception as e:
                logger.warning(f"Error unsubscribing from {symbol}: {e}")
        
        logger.info("Market data stream stopped")
        
    def get_recent_prices(self, symbol: str, count: int = 20) -> list:
        """Get recent price history for strategy calculations"""
        if symbol in self.price_history:
            prices = list(self.price_history[symbol])
            return [p["price"] for p in prices[-count:]]
        return []
    
    def get_recent_candles(self, symbol: str, count: int = 20) -> list:
        """Get recent candle history for strategy calculations"""
        if symbol in self.candle_history:
            candles = list(self.candle_history[symbol])
            return list(candles[-count:])
        return []