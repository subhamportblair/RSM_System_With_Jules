from .kite_session import kite_mgr
from .position_manager import pos_mgr, get_instrument_type
from .telegram_notifier import telegram
import logging

logger = logging.getLogger(__name__)

async def square_off_position(pos: dict):
    side = (
        kite_mgr.kite.TRANSACTION_TYPE_SELL
        if pos["quantity"] > 0
        else kite_mgr.kite.TRANSACTION_TYPE_BUY
    )

    success = False
    last_error = ""
    order_id = None

    for attempt in range(2):
        try:
            order_id = kite_mgr.kite.place_order(
                variety=kite_mgr.kite.VARIETY_REGULAR,
                exchange=pos["exchange"],
                tradingsymbol=pos["tradingsymbol"],
                transaction_type=side,
                quantity=abs(pos["quantity"]),
                product=pos["product"],
                order_type=kite_mgr.kite.ORDER_TYPE_MARKET
            )
            success = True
            break
        except Exception as e:
            last_error = str(e)
            logger.error(f"Square-off attempt {attempt+1} failed for {pos['tradingsymbol']}: {e}")

    if success:
        return {
            "symbol": pos["tradingsymbol"],
            "exchange": pos["exchange"],
            "type": get_instrument_type(pos["tradingsymbol"]),
            "product": pos["product"],
            "qty": abs(pos["quantity"]),
            "order_id": order_id,
            "status": "OK"
        }
    else:
        await telegram.send(
            f"❌ <b>Square-off FAILED</b>\n"
            f"{pos['exchange']}:{pos['tradingsymbol']} — {last_error}"
        )
        return {
            "symbol": pos["tradingsymbol"],
            "exchange": pos["exchange"],
            "error": last_error,
            "status": "FAILED"
        }

async def square_off_all_fo():
    positions = pos_mgr.get_all_positions_list()
    results = []

    for pos in positions:
        if pos["quantity"] == 0:
            continue

        result = await square_off_position(pos)
        results.append(result)

    return results
