import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime
from utils.logger import logger
import websockets

class ConnectionManager:
    """Manages WebSocket connection lifecycle"""
    
    def __init__(self, url: str, app_id: str, token: str, max_retries: int = 3):
        self.url = url
        self.app_id = app_id
        self.token = token
        self.max_retries = max_retries
        self.ws = None
        self.is_connected = False
        self._reconnect_task = None
        self._should_stop = False
    
    async def connect(self) -> bool:
        """Establish connection with retry logic"""
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Connection attempt {attempt + 1}/{self.max_retries}")
                
                # Connect WebSocket
                import websockets
                self.ws = await websockets.connect(
                    f"{self.url}?app_id={self.app_id}",
                    ping_interval=20,
                    ping_timeout=20
                )
                
                # Authenticate
                auth_response = await self._send_and_receive({
                    "authorize": self.token
                })
                
                if auth_response.get("error"):
                    raise Exception(f"Authentication failed: {auth_response['error']}")
                
                self.is_connected = True
                logger.info("✅ Successfully connected and authenticated")
                
                # Start health check
                self._start_health_check()
                
                return True
                
            except Exception as e:
                logger.error(f"Connection attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    delay = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logger.critical("Failed to connect after all retries")
                    return False
    
    async def _send_and_receive(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message and receive response"""
        await self.ws.send(json.dumps(message))
        response = await self.ws.recv()
        return json.loads(response)
    
    def _start_health_check(self):
        """Start periodic connection health check"""
        async def health_check():
            while self.is_connected and not self._should_stop:
                await asyncio.sleep(30)
                if self.ws and not self.ws.closed:
                    try:
                        await self.ws.send(json.dumps({"ping": 1}))
                        await asyncio.wait_for(self.ws.recv(), timeout=5)
                    except Exception as e:
                        logger.warning(f"Health check failed: {e}")
                        self.is_connected = False
                        await self.reconnect()
        
        self._reconnect_task = asyncio.create_task(health_check())
    
    async def reconnect(self):
        """Attempt to reconnect"""
        logger.info("Attempting to reconnect...")
        await self.disconnect()
        await asyncio.sleep(5)
        await self.connect()
    
    async def disconnect(self):
        """Clean disconnect"""
        self._should_stop = True
        self.is_connected = False
        
        if self._reconnect_task:
            self._reconnect_task.cancel()
        
        if self.ws:
            await self.ws.close()
            logger.info("Disconnected")
    
    async def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message with connection check"""
        if not self.is_connected or not self.ws:
            raise ConnectionError("Not connected to Deriv")
        
        return await self._send_and_receive(message)