from backend.position_manager import is_fo_instrument, TRACKED_EXCHANGES

def test_is_fo_instrument():
    assert is_fo_instrument("NIFTY23DEC19000CE") == True
    assert is_fo_instrument("BANKNIFTY23DECFUT") == True
    assert is_fo_instrument("RELIANCE23DECFUT") == True
    assert is_fo_instrument("NIFTY23DEC19000PE") == True
    assert is_fo_instrument("INFY") == False
    assert is_fo_instrument("SBIN") == False

def test_tracked_exchanges():
    assert "NFO" in TRACKED_EXCHANGES
    assert "BFO" in TRACKED_EXCHANGES
    assert "NSE" not in TRACKED_EXCHANGES
    assert "BSE" not in TRACKED_EXCHANGES
