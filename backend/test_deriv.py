import asyncio
from app.deriv_connector import DerivConnector
from app.models import MarketData
from app.strategies.dummy_strategy import DummyStrategy

strategy = DummyStrategy()


async def price_handler(data: MarketData):
    print(f"✅ {data.symbol} | Price: {data.price} | Time: {data.timestamp}")

async def main():
    connector = DerivConnector()

    await connector.connect()

    # Try different symbols later: R_50, R_100, R_75
    await connector.subscribe_ticks("R_100", price_handler)

async def price_handler(data):
    print(f"📊 {data.symbol} | {data.price}")
    
    # 🔥 STRATEGY HOOK
    await strategy.on_tick(data)

if __name__ == "__main__":
    asyncio.run(main())
    