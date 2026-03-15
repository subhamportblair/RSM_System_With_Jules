import pytest
from backend.position_manager import PositionManager

@pytest.mark.asyncio
async def test_pnl_calculation():
    pm = PositionManager()

    # Mock positions
    pm.positions = {
        123: {
            "instrument_token": 123,
            "tradingsymbol": "NIFTY23DEC19000CE",
            "exchange": "NFO",
            "quantity": 50,
            "average_price": 100.0,
            "last_price": 110.0,
            "realised": 500.0,
            "product": "MIS"
        },
        456: {
            "instrument_token": 456,
            "tradingsymbol": "BANKNIFTY23DECFUT",
            "exchange": "BFO",
            "quantity": -25,
            "average_price": 45000.0,
            "last_price": 45100.0,
            "realised": -1000.0,
            "product": "NRML"
        }
    }

    breakdown = pm.get_pnl_breakdown()

    # NIFTY CE: (110 - 100) * 50 + 500 = 500 + 500 = 1000
    # BANKNIFTY FUT: (45100 - 45000) * (-25) + (-1000) = 100 * (-25) - 1000 = -2500 - 1000 = -3500

    assert breakdown["total_pnl"] == 1000 - 3500 # -2500
    assert breakdown["by_type"]["CE"] == 1000
    assert breakdown["by_type"]["FUT"] == -3500
    assert breakdown["by_exchange"]["NFO"] == 1000
    assert breakdown["by_exchange"]["BFO"] == -3500
