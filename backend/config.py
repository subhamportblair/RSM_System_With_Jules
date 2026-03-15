import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    KITE_API_KEY = os.getenv("KITE_API_KEY")
    KITE_API_SECRET = os.getenv("KITE_API_SECRET")
    KITE_REDIRECT_URL = os.getenv("KITE_REDIRECT_URL", "http://localhost:8000/auth/callback")

    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./fo_rms.db")

    MAX_LOSS_DEFAULT = float(os.getenv("MAX_LOSS_DEFAULT", -5000))
    PROFIT_TARGET_DEFAULT = float(os.getenv("PROFIT_TARGET_DEFAULT", 10000))
    CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", 3))
    AUTO_SQUAREOFF_ENABLED = os.getenv("AUTO_SQUAREOFF_ENABLED", "true").lower() == "true"

config = Config()
