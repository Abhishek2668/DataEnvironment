from datetime import datetime, time, timezone

from forex.realtime.session import SessionConfig, SessionController


def test_session_halts_on_profit_target() -> None:
    config = SessionConfig(
        session_start=time(0, 0),
        session_end=time(23, 59),
        timezone=timezone.utc,
        daily_profit_target_pct=1.0,
        daily_loss_limit_pct=1.0,
    )
    controller = SessionController(config)
    now = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    controller.start_day(1000.0, now)
    controller.update_equity(1015.0, now)
    assert controller.state.target_hit is True
    assert controller.state.halted is True


def test_session_resets_next_day() -> None:
    config = SessionConfig(
        session_start=time(0, 0),
        session_end=time(23, 59),
        timezone=timezone.utc,
    )
    controller = SessionController(config)
    day_one = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    controller.start_day(1000.0, day_one)
    controller.update_equity(990.0, day_one)
    controller.state.halted = True
    controller.state.loss_limit_hit = True
    controller.maybe_reset(datetime(2024, 1, 2, 0, 5, tzinfo=timezone.utc))
    assert controller.state.halted is False
    assert controller.state.loss_limit_hit is False
