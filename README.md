# Zerodha F&O Risk Management System (RMS)

A robust, real-time risk management system for tracking and protecting intraday (MIS) and overnight (NRML) Options and Futures positions across NFO and BFO exchanges.

## 🚀 Features

- **Multi-Exchange Tracking:** Supports both NFO (NSE F&O) and BFO (BSE F&O).
- **Instrument Coverage:** Monitors all CE/PE options and FUT futures for any underlying (NIFTY, BANKNIFTY, etc.).
- **Live PnL Dashboard:** WebSocket-powered real-time updates for PnL, breakdown by type, and exchange.
- **Automated Square-off:** Automatically exits all positions when Max Loss or Profit Target is reached.
- **Trailing Stop-Loss:** Dynamically moves the Max Loss threshold upward as PnL hits new peaks.
- **Telegram Alerts:** Real-time notifications for login, warnings, breaches, and hourly updates.
- **Audit Trail:** Detailed square-off reports sent via Telegram.

## 🛠️ Configuration

The system is configured via a `.env` file. Copy `.env.example` to `.env` and fill in the following:

- `KITE_API_KEY`: Your Zerodha Kite Connect API Key.
- `KITE_API_SECRET`: Your Zerodha Kite Connect API Secret.
- `TELEGRAM_BOT_TOKEN`: Token from [@BotFather](https://t.me/botfather).
- `TELEGRAM_CHAT_ID`: Your Chat ID from [@userinfobot](https://t.me/userinfobot).
- `KITE_REDIRECT_URL`: Set to `http://localhost:8000/auth/callback`.

## 📦 Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start the backend:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000
   ```

3. Access the dashboard:
   Open `http://localhost:8000` in your browser.

## 🔑 Daily Login

At the start of each trading session, you must authorize the system:
1. Open the dashboard.
2. Click **"Login Kite"**.
3. Complete the Zerodha login.
4. The system will start monitoring once the session is ACTIVE.

## 🧪 Running Tests

```bash
PYTHONPATH=. pytest
```

## ⚠️ Important Note

The **HALTED** state is sticky. If a risk breach occurs and positions are squared off, the system will remain in HALTED state until you manually click **"Resume Monitoring"** on the dashboard.
