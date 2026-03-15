from kiteconnect import KiteTicker
from .config import config
from .position_manager import pos_mgr
import logging
import asyncio

logger = logging.getLogger(__name__)

class TickerManager:
    def __init__(self):
        self.ticker = None
        self.subscribed_tokens = set()
        self.loop = None

    def start(self, access_token):
        self.ticker = KiteTicker(config.KITE_API_KEY, access_token)
        self.loop = asyncio.get_event_loop()

        def on_ticks(ws, ticks):
            for tick in ticks:
                token = tick["instrument_token"]
                ltp = tick["last_price"]
                # Run the async update in the event loop
                asyncio.run_coroutine_threadsafe(pos_mgr.update_ltp(token, ltp), self.loop)

        def on_connect(ws, response):
            logger.info("Ticker connected")
            self.resubscribe()

        def on_error(ws, code, msg):
            logger.error(f"Ticker error: {code} - {msg}")

        def on_reconnect(ws, attempt, delay):
            logger.info(f"Ticker reconnecting... attempt {attempt}")

        self.ticker.on_ticks = on_ticks
        self.ticker.on_connect = on_connect
        self.ticker.on_error = on_error
        self.ticker.on_reconnect = on_reconnect
        self.ticker.connect(threaded=True)

    def subscribe(self, tokens):
        if not self.ticker or not self.ticker.is_connected():
            return

        new_tokens = [t for t in tokens if t not in self.subscribed_tokens]
        if new_tokens:
            self.ticker.subscribe(new_tokens)
            self.ticker.set_mode(self.ticker.MODE_LTP, new_tokens)
            self.subscribed_tokens.update(new_tokens)
            logger.info(f"Subscribed to {len(new_tokens)} new tokens")

    def resubscribe(self):
        if self.subscribed_tokens and self.ticker and self.ticker.is_connected():
            tokens = list(self.subscribed_tokens)
            self.ticker.subscribe(tokens)
            self.ticker.set_mode(self.ticker.MODE_LTP, tokens)
            logger.info(f"Resubscribed to {len(tokens)} tokens")

    def update_subscriptions(self, current_tokens):
        if not self.ticker or not self.ticker.is_connected():
            self.subscribed_tokens = set(current_tokens)
            return

        to_subscribe = [t for t in current_tokens if t not in self.subscribed_tokens]
        if to_subscribe:
            self.subscribe(to_subscribe)

ticker_mgr = TickerManager()
