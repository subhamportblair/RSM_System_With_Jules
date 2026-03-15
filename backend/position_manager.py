from .kite_session import kite_mgr
import logging
import asyncio

logger = logging.getLogger(__name__)

TRACKED_EXCHANGES = {"NFO", "BFO"}

def is_fo_instrument(tradingsymbol: str) -> bool:
    """Match CE/PE options or FUT futures for any underlying."""
    return (
        tradingsymbol.endswith(("CE", "PE"))
        or "FUT" in tradingsymbol
    )

def get_instrument_type(tradingsymbol: str) -> str:
    if tradingsymbol.endswith("CE"):
        return "CE"
    elif tradingsymbol.endswith("PE"):
        return "PE"
    elif "FUT" in tradingsymbol:
        return "FUT"
    return "UNKNOWN"

class PositionManager:
    def __init__(self):
        self.positions = {} # instrument_token -> position_dict
        self.lock = asyncio.Lock()

    async def fetch_and_filter_positions(self):
        try:
            all_positions = kite_mgr.kite.positions()

            # Filter MIS from "day" and NRML from "net"
            day_positions = [
                p for p in all_positions["day"]
                if p["exchange"] in TRACKED_EXCHANGES
                and is_fo_instrument(p["tradingsymbol"])
                and p["product"] == "MIS"
            ]

            net_positions = [
                p for p in all_positions["net"]
                if p["exchange"] in TRACKED_EXCHANGES
                and is_fo_instrument(p["tradingsymbol"])
                and p["product"] == "NRML"
            ]

            combined = day_positions + net_positions

            async with self.lock:
                # Keep track of instrument tokens for LTP updates
                new_positions = {}
                for p in combined:
                    token = p["instrument_token"]
                    # Preserve last_price if already exists
                    if token in self.positions:
                        p["last_price"] = self.positions[token].get("last_price", p["last_price"])
                    new_positions[token] = p
                self.positions = new_positions

            return combined
        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    async def update_ltp(self, token, ltp):
        async with self.lock:
            if token in self.positions:
                self.positions[token]["last_price"] = ltp

    def calc_unrealized_pnl(self, position: dict) -> float:
        qty = position["quantity"]       # negative if short
        avg = position["average_price"]
        ltp = position["last_price"]     # updated live by KiteTicker
        return (ltp - avg) * qty

    def get_all_positions_list(self):
        return list(self.positions.values())

    def get_pnl_breakdown(self):
        positions = self.get_all_positions_list()
        by_type = {"CE": 0.0, "PE": 0.0, "FUT": 0.0}
        by_exchange = {"NFO": 0.0, "BFO": 0.0}
        total_pnl = 0.0
        realized = 0.0
        unrealized = 0.0

        for p in positions:
            pnl = p["realised"] + self.calc_unrealized_pnl(p)
            itype = get_instrument_type(p["tradingsymbol"])
            exch = p["exchange"]

            total_pnl += pnl
            realized += p["realised"]
            unrealized += self.calc_unrealized_pnl(p)

            if itype in by_type:
                by_type[itype] += pnl
            if exch in by_exchange:
                by_exchange[exch] += pnl

        return {
            "total_pnl": total_pnl,
            "realized": realized,
            "unrealized": unrealized,
            "by_type": by_type,
            "by_exchange": by_exchange
        }

pos_mgr = PositionManager()
