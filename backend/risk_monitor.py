import asyncio
import logging
from .position_manager import pos_mgr
from .squareoff_engine import square_off_all_fo, square_off_position
from .telegram_notifier import telegram
from .database import SessionLocal
from .models import RiskConfig, AppStatus, SymbolRisk
from .ticker_manager import ticker_mgr

logger = logging.getLogger(__name__)

from datetime import datetime, timezone

class RiskMonitor:
    def __init__(self):
        self.warning_sent = False
        self.is_running = False
        self.last_hourly_update = 0

    async def get_config(self):
        db = SessionLocal()
        config = db.query(RiskConfig).first()
        db.close()
        return config

    async def update_peak_pnl_and_sl(self, current_pnl):
        db = SessionLocal()
        config = db.query(RiskConfig).first()
        if config and config.trailing_sl_enabled:
            if current_pnl > config.peak_pnl:
                config.peak_pnl = current_pnl
                new_max_loss = current_pnl - config.trail_distance
                # Only move max_loss UP
                if new_max_loss > config.max_loss:
                    config.max_loss = new_max_loss
                    logger.info(f"Trailing SL: New peak {current_pnl}, updated Max Loss to {config.max_loss}")
            db.commit()
        db.close()

    async def set_app_status(self, status):
        db = SessionLocal()
        app_status = db.query(AppStatus).first()
        if not app_status:
            app_status = AppStatus(status=status)
            db.add(app_status)
        else:
            app_status.status = status
        db.commit()
        db.close()

    async def get_app_status(self):
        db = SessionLocal()
        app_status = db.query(AppStatus).first()
        db.close()
        return app_status.status if app_status else "ACTIVE"

    def format_alert(self, title, emoji, day_pnl, breakdown):
        bt = breakdown["by_type"]
        be = breakdown["by_exchange"]
        return (
            f"{emoji} <b>{title}</b>\n"
            f"Day PnL: ₹{day_pnl:,.2f}\n\n"
            f"<b>By Type:</b>\n"
            f"CE: ₹{bt['CE']:,.2f} | PE: ₹{bt['PE']:,.2f} | FUT: ₹{bt['FUT']:,.2f}\n\n"
            f"<b>By Exchange:</b>\n"
            f"NFO: ₹{be['NFO']:,.2f} | BFO: ₹{be['BFO']:,.2f}\n\n"
            f"Squaring off ALL F&O positions (NFO + BFO)!"
        )

    async def send_hourly_update(self, breakdown, positions):
        bt = breakdown["by_type"]
        be = breakdown["by_exchange"]

        msg = "<b>📊 HOURLY UPDATE</b>\n\n"
        msg += f"<b>Day PnL: ₹{breakdown['total_pnl']:,.2f}</b>\n"
        msg += f"Realized: ₹{breakdown['realized']:,.2f} | Unrealized: ₹{breakdown['unrealized']:,.2f}\n\n"

        msg += "<b>Positions:</b>\n"
        msg += "Symbol | Exch | Type | Prod | Qty | LTP | P&L\n"
        for p in positions:
            pnl = (p["last_price"] - p["average_price"]) * p["quantity"] + p["realised"]
            itype = p["tradingsymbol"][-2:] if p["tradingsymbol"].endswith(("CE", "PE")) else "FUT"
            msg += f"{p['tradingsymbol']} | {p['exchange']} | {itype} | {p['product']} | {p['quantity']} | {p['last_price']} | ₹{pnl:,.0f}\n"

        await telegram.send(msg)

    async def get_symbol_risks(self):
        db = SessionLocal()
        risks = {r.tradingsymbol: r for r in db.query(SymbolRisk).all()}
        db.close()
        return risks

    async def check_risk_loop(self):
        self.is_running = True
        while self.is_running:
            try:
                status = await self.get_app_status()
                if status == "HALTED":
                    await asyncio.sleep(5)
                    continue

                config = await self.get_config()
                if not config:
                    await asyncio.sleep(3)
                    continue

                # Time Based Exit
                now = datetime.now()
                current_time_str = now.strftime("%H:%M")
                if current_time_str >= config.auto_exit_time:
                    # Check if there are any MIS positions open
                    positions = await pos_mgr.fetch_and_filter_positions()
                    mis_positions = [p for p in positions if p["product"] == "MIS" and p["quantity"] != 0]
                    if mis_positions:
                        logger.info(f"Time-based exit triggered at {current_time_str} (Target: {config.auto_exit_time})")
                        for p in mis_positions:
                            await square_off_position(p)
                        await telegram.send(f"🕒 <b>AUTO EXIT TIME REACHED</b>\nAll MIS positions squared off at {current_time_str}.")

                # Refresh positions from Kite occasionally
                positions = await pos_mgr.fetch_and_filter_positions()

                # Update ticker subscriptions
                tokens = [p["instrument_token"] for p in positions]
                ticker_mgr.update_subscriptions(tokens)

                breakdown = pos_mgr.get_pnl_breakdown()
                day_pnl = breakdown["total_pnl"]

                # Update Trailing SL if enabled
                await self.update_peak_pnl_and_sl(day_pnl)

                # Per-Symbol Risk Check
                symbol_risks = await self.get_symbol_risks()
                for p in positions:
                    if p["quantity"] == 0: continue
                    pnl = (p["last_price"] - p["average_price"]) * p["quantity"] + p["realised"]
                    risk = symbol_risks.get(p["tradingsymbol"])
                    if risk:
                        if risk.stop_loss is not None and pnl <= risk.stop_loss:
                            await square_off_position(p)
                            await telegram.send(f"⚠️ <b>SYMBOL SL HIT</b>\n{p['tradingsymbol']} closed at ₹{pnl:,.2f} (SL: ₹{risk.stop_loss})")
                        elif risk.target is not None and pnl >= risk.target:
                            await square_off_position(p)
                            await telegram.send(f"✅ <b>SYMBOL TARGET HIT</b>\n{p['tradingsymbol']} closed at ₹{pnl:,.2f} (Target: ₹{risk.target})")

                if day_pnl <= config.max_loss:
                    await self.set_app_status("HALTED")
                    results = await square_off_all_fo()
                    await telegram.send(self.format_alert(
                        f"MAX LOSS HIT | Limit: ₹{config.max_loss:,.0f}", "🚨", day_pnl, breakdown
                    ))
                    # Also send square-off report
                    report = "<b>SQUARE-OFF REPORT:</b>\n"
                    for r in results:
                        report += f"{r['symbol']} ({r['exchange']}): {r['status']}\n"
                    await telegram.send(report)

                elif day_pnl >= config.profit_target:
                    await self.set_app_status("HALTED")
                    results = await square_off_all_fo()
                    await telegram.send(self.format_alert(
                        f"PROFIT TARGET HIT | Target: ₹{config.profit_target:,.0f}", "✅", day_pnl, breakdown
                    ))
                    # Also send square-off report
                    report = "<b>SQUARE-OFF REPORT:</b>\n"
                    for r in results:
                        report += f"{r['symbol']} ({r['exchange']}): {r['status']}\n"
                    await telegram.send(report)

                elif day_pnl <= config.max_loss * 0.80 and not self.warning_sent:
                    bt = breakdown["by_type"]
                    be = breakdown["by_exchange"]
                    await telegram.send(
                        f"⚠️ <b>WARNING</b>\n"
                        f"Day PnL: ₹{day_pnl:,.2f} — approaching max loss ₹{config.max_loss:,.0f}\n"
                        f"CE: ₹{bt['CE']:,.2f} | PE: ₹{bt['PE']:,.2f} | FUT: ₹{bt['FUT']:,.2f}\n"
                        f"NFO: ₹{be['NFO']:,.2f} | BFO: ₹{be['BFO']:,.2f}"
                    )
                    self.warning_sent = True

                # Reset warning if PnL recovers significantly
                if day_pnl > config.max_loss * 0.70:
                    self.warning_sent = False

                # Hourly Update
                current_hour = datetime.now().hour
                if current_hour != self.last_hourly_update:
                    await self.send_hourly_update(breakdown, positions)
                    self.last_hourly_update = current_hour

                await asyncio.sleep(config.check_interval)
            except Exception as e:
                logger.error(f"Error in risk monitor loop: {e}")
                await asyncio.sleep(5)

risk_monitor = RiskMonitor()
