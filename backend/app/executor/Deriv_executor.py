"""
DERIV EXECUTOR - Fixed WebSocket Communication
Added locking mechanism to prevent concurrent send/receive operations
"""

import json
import asyncio
from typing import Dict, Any, Optional
from urllib import request
from models.signal import TradingSignal, ActionType
from executor.connection_manager import ConnectionManager
from utils.logger import logger
import os
from dotenv import load_dotenv

load_dotenv()

class DerivExecutor:
    """Main trading executor for Deriv platform with WebSocket lock protection"""
    
    def __init__(self):
        self.app_id = os.getenv("DERIV_APP_ID", "1089")
        self.token = os.getenv("DERIV_TOKEN")
        self.ws_url = os.getenv("DERIV_WS_URL", "wss://ws.derivws.com/websockets/v3")
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        
        if not self.token:
            raise ValueError("DERIV_TOKEN not found in environment variables")
        
        self.connection = ConnectionManager(
            url=self.ws_url,
            app_id=self.app_id,
            token=self.token,
            max_retries=self.max_retries
        )
        self._trade_history = []
        
        # ✅ ADDED: Lock to prevent concurrent WebSocket operations
        self._ws_lock = asyncio.Lock()
    
    async def connect(self) -> bool:
        """Connect to Deriv"""
        return await self.connection.connect()
    
    async def disconnect(self):
        """Disconnect from Deriv"""
        await self.connection.disconnect()
    
    async def _send_and_receive_safe(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ NEW METHOD: Send request and receive response with LOCK protection
        This prevents multiple coroutines from using the WebSocket simultaneously
        """
        async with self._ws_lock:  # Only ONE coroutine can execute this at a time
            # Send the request
            await self.connection.ws.send(json.dumps(request))
            logger.debug(f"📤 Sent: {request}")
            
            # Wait for response (SAFE - only one at a time)
            response_text = await self.connection.ws.recv()
            response = json.loads(response_text)
            logger.debug(f"📥 Received: {response}")
            
            return response
    
    async def open_position(self, signal: TradingSignal) -> Dict[str, Any]:
        """
        Open a multiplier position based on trading signal
        NOW USING THE SAFE LOCKED METHOD
        """
        
        if not self.connection.is_connected:
            raise ConnectionError("Not connected to Deriv. Call connect() first.")
        
        # Validate and prepare contract type
        contract_type = signal.action.value
        if contract_type not in ["MULTUP", "MULTDOWN"]:
            raise ValueError(f"Invalid action: {contract_type}")
        
        # Prepare buy proposal
        proposal = {
            "buy": 1,
            "price": signal.stake_amount,
            "parameters": {
                "amount": signal.stake_amount,
                "basis": "stake",
                "symbol": signal.symbol,
                "contract_type": contract_type,
                "currency": signal.currency,
                "multiplier": signal.multiplier
            }
        }
        
        try:
            logger.info(f"Opening {contract_type} position for {signal.symbol} with ${signal.stake_amount}")
            
            # ✅ USE THE SAFE LOCKED METHOD instead of direct connection.send
            response = await self._send_and_receive_safe(proposal)
            
            # Check for errors
            if response.get("error"):
                error_msg = response['error'].get('message', 'Unknown error')
                raise Exception(f"Trade failed: {error_msg}")
            
            # Log successful trade
            trade_record = {
                "contract_id": response.get("buy", {}).get("contract_id"),
                "signal": signal.to_dict(),
                "response": response,
                "timestamp": signal.timestamp.isoformat() if hasattr(signal, 'timestamp') else None
            }
            self._trade_history.append(trade_record)
            
            logger.info(f"✅ Position opened - Contract ID: {trade_record['contract_id']}")
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to open position: {e}")
            raise
    
    async def get_balance(self) -> Optional[float]:
        """
        Get account balance
        NOW USING THE SAFE LOCKED METHOD
        """
        try:
            # ✅ USE THE SAFE LOCKED METHOD
            response = await self._send_and_receive_safe({"balance": 1})
            
            if response.get("balance"):
                balance = response["balance"]["balance"]
                currency = response["balance"]["currency"]
                logger.info(f"💰 Balance: {balance} {currency}")
                return balance
            return None
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None
    
    async def get_active_positions(self) -> list:
        """
        Get list of active positions
        NOW USING THE SAFE LOCKED METHOD
        """
        try:
            # ✅ USE THE SAFE LOCKED METHOD
            response = await self._send_and_receive_safe({"portfolio": 1})
            
            if response.get("portfolio"):
                contracts = response["portfolio"].get("contracts", [])
                logger.info(f"📊 Active positions: {len(contracts)}")
                return contracts
            return []
        except Exception as e:
            logger.error(f"Failed to get portfolio: {e}")
            return []
    
    async def close_position(self, contract_id: str) -> Dict[str, Any]:
        """
        ✅ NEW METHOD: Close an open position
        """
        try:
            close_request = {
                "sell": contract_id,
                "price": 0  # 0 = market price
            }
            
            logger.info(f"Closing position: {contract_id}")
            
            # ✅ USE THE SAFE LOCKED METHOD
            response = await self._send_and_receive_safe(close_request)
            
            if response.get("error"):
                error_msg = response['error'].get('message', 'Unknown error')
                raise Exception(f"Close failed: {error_msg}")
            
            if response.get("sell"):
                profit = response["sell"].get("profit", 0)
                logger.info(f"✅ Position closed - Profit: ${profit:.2f}")
                return response
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            raise
    
    async def get_tick_history(self, symbol: str, count: int = 10) -> list:
        """
        ✅ NEW METHOD: Get recent tick history for a symbol
        """
        try:
            request = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": count,
                "end": "latest",
                "start": 1,
                "style": "ticks"
            }
            
            # ✅ USE THE SAFE LOCKED METHOD
            response = await self._send_and_receive_safe(request)
            
            if response.get("error"):
                logger.error(f"Tick history error: {response['error']}")
                return []
            
            if response.get("history"):
                return response["history"].get("prices", [])
            return []
            
        except Exception as e:
            logger.error(f"Failed to get tick history: {e}")
            return []
    
    def get_trade_history(self) -> list:
        """Return trade history"""
        return self._trade_history.copy()
    async def _send_only(self, request: Dict[str, Any]) -> None:

       
         async with self._ws_lock:
            await self.connection.ws.send(json.dumps(request))
            logger.debug(f"📤 Sent (no response expected): {request}")
   