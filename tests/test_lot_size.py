from unittest.mock import MagicMock
from backend.kite_session import KiteSessionManager

def test_cache_lot_sizes():
    mgr = KiteSessionManager()
    mgr.kite = MagicMock()

    mgr.kite.instruments.side_effect = lambda exch: [
        {"tradingsymbol": f"{exch}_SYM1", "lot_size": 50},
        {"tradingsymbol": f"{exch}_SYM2", "lot_size": 100}
    ] if exch in ["NFO", "BFO"] else []

    mgr.cache_lot_sizes()

    assert mgr.get_lot_size("NFO_SYM1") == 50
    assert mgr.get_lot_size("BFO_SYM2") == 100
    assert mgr.get_lot_size("UNKNOWN") == 1
