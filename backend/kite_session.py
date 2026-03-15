from kiteconnect import KiteConnect
from .config import config
from .database import SessionLocal, engine
from .models import KiteSession, Base
from datetime import datetime, timezone
import logging

Base.metadata.create_all(bind=engine)

logger = logging.getLogger(__name__)

class KiteSessionManager:
    def __init__(self):
        self.kite = KiteConnect(api_key=config.KITE_API_KEY)
        self.lot_size_map = {}
        self.access_token = None

    def get_login_url(self):
        return self.kite.login_url()

    def set_access_token(self, request_token):
        try:
            data = self.kite.generate_session(request_token, api_secret=config.KITE_API_SECRET)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)

            # Store in DB
            db = SessionLocal()
            # Clear old sessions
            db.query(KiteSession).delete()
            new_session = KiteSession(access_token=self.access_token, login_date=datetime.now(timezone.utc))
            db.add(new_session)
            db.commit()
            db.close()

            self.cache_lot_sizes()
            return True
        except Exception as e:
            logger.error(f"Error setting access token: {e}")
            return False

    def load_session(self):
        db = SessionLocal()
        session = db.query(KiteSession).order_by(KiteSession.login_date.desc()).first()
        db.close()

        if session:
            # Check if session is from today
            if session.login_date.date() == datetime.now(timezone.utc).date():
                self.access_token = session.access_token
                self.kite.set_access_token(self.access_token)
                try:
                    # Test if token is still valid
                    self.kite.profile()
                    self.cache_lot_sizes()
                    return "ACTIVE"
                except Exception:
                    return "TOKEN_EXPIRED"
            return "TOKEN_EXPIRED"
        return "NOT_LOGGED_IN"

    def cache_lot_sizes(self):
        try:
            nfo_instruments = self.kite.instruments("NFO")
            bfo_instruments = self.kite.instruments("BFO")

            self.lot_size_map = {
                i["tradingsymbol"]: i["lot_size"]
                for i in nfo_instruments + bfo_instruments
            }
            logger.info(f"Cached {len(self.lot_size_map)} lot sizes from NFO and BFO")
        except Exception as e:
            logger.error(f"Error caching lot sizes: {e}")

    def get_lot_size(self, tradingsymbol):
        return self.lot_size_map.get(tradingsymbol, 1)

kite_mgr = KiteSessionManager()
