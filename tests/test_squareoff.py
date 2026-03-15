import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.squareoff_engine import square_off_all_fo

@pytest.mark.asyncio
async def test_square_off_all_fo():
    mock_positions = [
        {
            "tradingsymbol": "NIFTY23DEC19000CE",
            "exchange": "NFO",
            "quantity": 50,
            "product": "MIS"
        },
        {
            "tradingsymbol": "BANKNIFTY23DECFUT",
            "exchange": "BFO",
            "quantity": -25,
            "product": "NRML"
        }
    ]

    with patch("backend.squareoff_engine.pos_mgr.get_all_positions_list", return_value=mock_positions), \
         patch("backend.squareoff_engine.kite_mgr") as mock_kite_mgr:

        mock_kite_mgr.kite.place_order.return_value = "ORDER123"
        mock_kite_mgr.kite.TRANSACTION_TYPE_SELL = "SELL"
        mock_kite_mgr.kite.TRANSACTION_TYPE_BUY = "BUY"
        mock_kite_mgr.kite.VARIETY_REGULAR = "regular"
        mock_kite_mgr.kite.ORDER_TYPE_MARKET = "MARKET"

        results = await square_off_all_fo()

        assert len(results) == 2
        assert results[0]["status"] == "OK"
        assert results[1]["status"] == "OK"

        # Verify correct side and exchange
        assert mock_kite_mgr.kite.place_order.call_count == 2

        # First call: NIFTY (qty 50 > 0) -> SELL, NFO
        call1 = mock_kite_mgr.kite.place_order.call_args_list[0]
        assert call1.kwargs["transaction_type"] == "SELL"
        assert call1.kwargs["exchange"] == "NFO"

        # Second call: BANKNIFTY (qty -25 < 0) -> BUY, BFO
        call2 = mock_kite_mgr.kite.place_order.call_args_list[1]
        assert call2.kwargs["transaction_type"] == "BUY"
        assert call2.kwargs["exchange"] == "BFO"
