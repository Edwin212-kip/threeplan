import asyncio
import websockets
import json
from datetime import datetime
from .models import MarketData

DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

class DerivConnector:
    def __init__(self):
        self.ws = None

    async def connect(self):
        print("[DERIV] Connecting...")
        self.ws = await websockets.connect(DERIV_WS_URL)
        print("[DERIV] Connected")

    async def subscribe_ticks(self, symbol: str, callback):
        """
        Subscribe to live ticks from Deriv
        """
        request = {
            "ticks": symbol,
            "subscribe": 1
        }

        await self.ws.send(json.dumps(request))

        while True:
            response = await self.ws.recv()
            data = json.loads(response)

            if "tick" in data:
                tick = data["tick"]

                # 🔥 THIS IS THE CRITICAL PART (mapping to schema)
                market_data = MarketData(
                    symbol=tick["symbol"],
                    price=tick["quote"] ,
                    timestamp=datetime.utcfromtimestamp(tick["epoch"]),
                    source="deriv"
                )

                await callback(market_data)