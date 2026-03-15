import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.risk_monitor import RiskMonitor

@pytest.mark.asyncio
async def test_risk_trigger_max_loss():
    rm = RiskMonitor()
    rm.get_app_status = AsyncMock(return_value="ACTIVE")
    rm.set_app_status = AsyncMock()

    mock_config = MagicMock()
    mock_config.max_loss = -5000
    mock_config.profit_target = 10000
    mock_config.check_interval = 3
    mock_config.auto_exit_time = "15:15"
    mock_config.trailing_sl_enabled = False

    rm.get_config = AsyncMock(return_value=mock_config)

    mock_breakdown = {
        "total_pnl": -6000,
        "realized": -5000,
        "unrealized": -1000,
        "by_type": {"CE": -3000, "PE": -2000, "FUT": -1000},
        "by_exchange": {"NFO": -4000, "BFO": -2000}
    }

    with patch("backend.risk_monitor.pos_mgr") as mock_pos_mgr, \
         patch("backend.risk_monitor.square_off_all_fo", new_callable=AsyncMock) as mock_sq, \
         patch("backend.risk_monitor.telegram", new_callable=AsyncMock) as mock_tg, \
         patch("backend.risk_monitor.ticker_mgr") as mock_ticker, \
         patch("backend.risk_monitor.SessionLocal") as mock_session_local:

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        # Mock both first() and all() for DB queries
        mock_db.query.return_value.first.return_value = mock_config
        mock_db.query.return_value.all.return_value = []

        mock_pos_mgr.fetch_and_filter_positions = AsyncMock(return_value=[])
        mock_pos_mgr.get_pnl_breakdown.return_value = mock_breakdown
        mock_sq.return_value = []

        # Actually, let's mock the loop to run once
        rm.is_running = True
        def stop_running(*args, **kwargs):
            rm.is_running = False
            return "ACTIVE"
        rm.get_app_status.side_effect = stop_running

        await rm.check_risk_loop()

        mock_sq.assert_called_once()
        rm.set_app_status.assert_called_with("HALTED")
        assert mock_tg.send.call_count >= 1

@pytest.mark.asyncio
async def test_trailing_sl_logic():
    rm = RiskMonitor()

    # Mock RiskConfig
    mock_config = MagicMock()
    mock_config.trailing_sl_enabled = True
    mock_config.peak_pnl = 5000.0
    mock_config.max_loss = 3000.0
    mock_config.trail_distance = 2000.0

    with patch("backend.risk_monitor.SessionLocal") as mock_session_local:
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.first.return_value = mock_config

        # Test 1: PnL reaches new high
        await rm.update_peak_pnl_and_sl(8000.0)
        assert mock_config.peak_pnl == 8000.0
        assert mock_config.max_loss == 6000.0 # 8000 - 2000
        mock_db.commit.assert_called()

        # Test 2: PnL drops (should not change peak or max_loss)
        mock_db.commit.reset_mock()
        await rm.update_peak_pnl_and_sl(7000.0)
        assert mock_config.peak_pnl == 8000.0
        assert mock_config.max_loss == 6000.0
