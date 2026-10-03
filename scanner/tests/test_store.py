from scanner.store import SignalRecord, SignalStore


def rec(**kw):
    base = dict(strategy_id="s1", ticker="AAPL", timeframe="1d", side="BUY",
                fired_at="2026-10-02T20:00:00+00:00", entry_price=100.0,
                details={"rsi": 21.5}, recorded_at="2026-10-02T20:05:00+00:00")
    base.update(kw)
    return SignalRecord(**base)


def test_creates_database_and_inserts(tmp_path):
    path = tmp_path / "signals.db"
    store = SignalStore(path)
    assert store.record_signals([rec(), rec(ticker="MSFT")]) == 2
    assert store.count() == 2
    store.close()
    assert path.exists()


def test_duplicate_is_ignored_and_original_row_is_untouched(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.record_signals([rec(entry_price=100.0, recorded_at="2026-10-02T20:05:00+00:00")])
    inserted = store.record_signals([rec(entry_price=999.0, recorded_at="2026-10-03T00:00:00+00:00")])
    assert inserted == 0
    row = store.conn.execute("SELECT entry_price, recorded_at FROM signals").fetchall()
    assert row == [(100.0, "2026-10-02T20:05:00+00:00")]


def test_different_side_or_time_is_a_new_signal(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.record_signals([rec()])
    assert store.record_signals([rec(side="SELL"), rec(fired_at="2026-10-05T20:00:00+00:00")]) == 2


def test_reopening_keeps_data(tmp_path):
    path = tmp_path / "signals.db"
    SignalStore(path).record_signals([rec()])
    assert SignalStore(path).count() == 1


def test_empty_batch_is_fine(tmp_path):
    assert SignalStore(tmp_path / "signals.db").record_signals([]) == 0


def test_creates_missing_parent_directories(tmp_path):
    store = SignalStore(tmp_path / "nested" / "history" / "signals.db")
    assert store.record_signals([rec()]) == 1
