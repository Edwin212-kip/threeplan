import streamlit as st
import asyncio
import websockets
import json
from datetime import datetime

st.set_page_config(page_title="Deriv Bot", layout="wide")
st.title("📈 Deriv Multipliers Bot")

WS_URL = "ws://localhost:8000/ws"

# Session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "connected" not in st.session_state:
    st.session_state.connected = False


# ---------- WEBSOCKET LISTENER ----------
async def listen():
    try:
        async with websockets.connect(WS_URL) as ws:
            st.session_state.connected = True

            while True:
                msg = await ws.recv()
                data = json.loads(msg)

                st.session_state.messages.insert(0, {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "data": data
                })

                # keep last 20
                st.session_state.messages = st.session_state.messages[:20]

                st.rerun()

    except Exception as e:
        st.session_state.connected = False
        st.error(f"Connection error: {e}")


# ---------- CONNECT BUTTON ----------
if st.button("Connect to Bot"):
    asyncio.run(listen())


# ---------- STATUS ----------
st.sidebar.header("Status")
st.sidebar.write(f"Connected: {st.session_state.connected}")
st.sidebar.write(f"Messages: {len(st.session_state.messages)}")


# ---------- DISPLAY ----------
st.subheader("📡 Live Feed")

for msg in st.session_state.messages:
    data = msg["data"]

    if data["type"] == "price":
        st.write(f"📊 {data['data']['symbol']} → {data['data']['price']}")

    elif data["type"] == "signal":
        st.success(f"🚀 SIGNAL → {data['data']}")

    else:
        st.write(data)

