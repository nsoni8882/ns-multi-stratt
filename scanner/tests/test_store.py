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


def test_conviction_is_stored(tmp_path):
    store = SignalStore(tmp_path / "signals.db")
    store.record_signals([rec(conviction="high"), rec(ticker="MSFT", conviction="low")])
    rows = dict(store.conn.execute("SELECT ticker, conviction FROM signals").fetchall())
    assert rows == {"AAPL": "high", "MSFT": "low"}
    store.close()


def test_reopening_an_old_database_adds_the_conviction_column(tmp_path):
    """The column was added after the table shipped, so opening a pre-existing DB migrates it."""
    path = tmp_path / "signals.db"
    import sqlite3

    from scanner.store import SCHEMA

    legacy = sqlite3.connect(str(path))
    legacy.execute(SCHEMA)
    legacy.execute(
        "INSERT INTO signals (strategy_id, ticker, timeframe, side, fired_at, entry_price, details, recorded_at)"
        " VALUES ('s1', 'OLD', '1d', 'BUY', 'then', 1.0, '{}', 'then')"
    )
    legacy.commit()
    legacy.close()

    store = SignalStore(path)
    assert store.record_signals([rec(conviction="high")]) == 1
    assert store.conn.execute("SELECT conviction FROM signals WHERE ticker = 'OLD'").fetchone()[0] == "standard"
    assert store.count() == 2
    store.close()


def test_rules_version_is_stored_against_each_signal(tmp_path):
    store = SignalStore(tmp_path / "s.db")
    store.record_signals([
        SignalRecord("trend-pullback", "AAA", "1d", "BUY", "2026-01-02T21:00:00+00:00",
                     10.0, {}, "2026-01-02T21:05:00+00:00", "standard", "abc123def456"),
    ])
    row = store.conn.execute("SELECT rules_version FROM signals").fetchone()
    assert row[0] == "abc123def456"
    store.close()


def test_rules_version_defaults_empty_for_rows_written_before_the_column(tmp_path):
    """The migration is a guarded ALTER, so a pre-existing database stays readable."""
    store = SignalStore(tmp_path / "s.db")
    store.record_signals([
        SignalRecord("x", "AAA", "1d", "BUY", "2026-01-02T21:00:00+00:00", 1.0, {},
                     "2026-01-02T21:05:00+00:00"),
    ])
    assert store.conn.execute("SELECT rules_version FROM signals").fetchone()[0] == ""
    store.close()
