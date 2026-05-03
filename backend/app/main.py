from fastapi import FastAPI, WebSocket
import asyncio
from .deriv_connector import DerivConnector
from .strategies.sma_momentum import SMAMomentumStrategy
from fastapi.responses import HTMLResponse  
import os 
from pathlib import Path
from .position_manager import PositionManager
from .executor import DerivExecutor


app = FastAPI()

connector = DerivConnector()
strategies = [
    SMAMomentumStrategy("R_100"),
]
position_manager = PositionManager()
executor = DerivExecutor()

# Store connected clients
clients = []
PROJECT_ROOT = Path(__file__).parent.parent.parent  # backend/app/main.py -> threeplan/
FRONTEND_DIR = PROJECT_ROOT / "frontend"
# ---------- 🔥 NEW: SERVE THE HTML PAGE ----------
@app.get("/")
async def serve_dashboard():
    """Serve the HTML dashboard - FIXED with UTF-8 encoding"""
    html_path = FRONTEND_DIR / "dashboard.html"
    
    # If dashboard.html doesn't exist, try simple.html
    if not html_path.exists():
        html_path = FRONTEND_DIR / "simple.html"
    
    if not html_path.exists():
        return HTMLResponse(content=f"""
        <html>
            <body>
                <h1>No dashboard found</h1>
                <p>Create one of these files:</p>
                <ul>
                    <li>{FRONTEND_DIR / 'dashboard.html'}</li>
                    <li>{FRONTEND_DIR / 'simple.html'}</li>
                </ul>
            </body>
        </html>
        """)
    
    # 🔥 CRITICAL FIX: encoding="utf-8"
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return HTMLResponse(content=html_content)
# ---------- STARTUP ----------
@app.on_event("startup")
async def startup():
    await connector.connect()
    await executor.connect()
    asyncio.create_task(stream_prices())  # Start the price streaming background task

# ---------- STREAM LOOP ----------
async def stream_prices():
    """This function runs continuously, processing each price update"""
    
    # Define what happens when a NEW price arrives
    async def on_tick_received(market_data):
        """This gets called for EVERY tick from Deriv"""
        
        # Log to console
        print(f"📊 {market_data.symbol} | {market_data.price}")
        
        # SEND PRICE TO ALL CONNECTED UI CLIENTS
        # Use clients[:] to safely iterate over a copy (in case clients list changes)
        for ws in clients[:]:
            try:
                await ws.send_json({
                    "type": "price",
                    "data": {
                        "symbol": market_data.symbol,
                        "price": market_data.price,
                        "timestamp": market_data.timestamp.isoformat()
                    }
                })
            except Exception as e:
                # If sending fails, client probably disconnected
                print(f"Error sending to client: {e}")
                if ws in clients:
                    clients.remove(ws)
        
        # If strategy generates a signal, send to all UI clients
        for strat in strategies:
            signal = await strat.on_tick(market_data)
            if signal:
                print(f"🚀 [{strat.__class__.__name__}] → {signal}")
                positions = position_manager.open_position(signal)
                asyncio.create_task(executor.open_position(signal))  # Execute trade asynchronously
                for ws in clients[:]:
                    try:
                        await ws.send_json({
                            "type": "signal",
                            "strat": strat.__class__.__name__,
                            "data": signal.model_dump(mode="json"),
                            "position": positions,
                            "deriv": deriv_response
                        })
                    except Exception as e:
                        print(f"Error sending signal: {e}")
                        if ws in clients:
                            clients.remove(ws)    
    # Subscribe to price updates from Deriv
    # You need to implement this method in DerivConnector
    await connector.subscribe_ticks(symbol="R_100", callback=on_tick_received)  # You can change the symbol as needed  
    
    # Keep this task running forever
    await asyncio.Event().wait()  # This never completes, so stream_prices runs indefinitely

# ---------- WEBSOCKET ----------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    print("✅ UI connected")
    
    try:
        while True:
            # Keep connection alive and optionally receive messages from UI
            message = await websocket.receive_text()
            # You could handle UI commands here (e.g., "subscribe to EUR/USD")
            print(f"📨 Received from UI: {message}")
    except:
        if websocket in clients:
            clients.remove(websocket)
        print("❌ UI disconnected")

#uvicorn backend.app.main:app --reload --port 8000