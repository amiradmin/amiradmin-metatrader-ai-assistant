from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path

from .models import HistoryBar, HistoryStatus, HistorySync


_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


class HistoryStore:
    """Persistent MT5 bar store optimized for multi-year chunked history sync.

    Older versions rewrote one large JSON file for every history sync and kept
    only 20,000 bars.  That was fine for a few months of M15 data, but it became
    expensive and silently discarded older bars when we started training across
    years.  The SQLite store upserts chunks by timestamp and keeps a much larger
    configurable window.

    ``MTAI_HISTORY_MAX_BARS`` controls the per-symbol/timeframe cap.  The default
    500,000 M15 bars is intentionally generous (many years for continuously
    traded instruments) while still providing a safety bound for disk/memory.
    Set it to 0 to disable pruning entirely.
    """

    def __init__(self, root: str | Path | None = None, max_bars: int | None = None) -> None:
        self.root = Path(root or os.getenv("MTAI_HISTORY_DIR", ".mtai_data/history"))
        self.root.mkdir(parents=True, exist_ok=True)
        if max_bars is None:
            max_bars = int(os.getenv("MTAI_HISTORY_MAX_BARS", "500000"))
        self.max_bars = max(0, int(max_bars))
        self.db_path = self.root / "history.sqlite3"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS history_meta (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    point REAL NOT NULL,
                    PRIMARY KEY(symbol, timeframe)
                );

                CREATE TABLE IF NOT EXISTS history_bars (
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    time INTEGER NOT NULL,
                    broker_date TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    spread_points INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(symbol, timeframe, time)
                );

                CREATE INDEX IF NOT EXISTS idx_history_bars_symbol_tf_date
                    ON history_bars(symbol, timeframe, broker_date, time);
                """
            )

    def _legacy_path(self, symbol: str, timeframe: str) -> Path:
        safe_symbol = _SAFE.sub("_", symbol)
        safe_tf = _SAFE.sub("_", timeframe)
        return self.root / f"{safe_symbol}_{safe_tf}.json"

    def _ensure_legacy_migrated(self, symbol: str, timeframe: str) -> None:
        """Import the pre-SQLite JSON file once, preserving the user's bars."""
        legacy = self._legacy_path(symbol, timeframe)
        if not legacy.exists():
            return

        with self._connect() as conn:
            exists = conn.execute(
                "SELECT 1 FROM history_bars WHERE symbol=? AND timeframe=? LIMIT 1",
                (symbol, timeframe),
            ).fetchone()
            if exists:
                return

            payload = json.loads(legacy.read_text(encoding="utf-8"))
            rows = [HistoryBar.model_validate(item) for item in payload.get("bars", [])]
            point = payload.get("point")
            if point is not None:
                conn.execute(
                    """
                    INSERT INTO history_meta(symbol,timeframe,point) VALUES(?,?,?)
                    ON CONFLICT(symbol,timeframe) DO UPDATE SET point=excluded.point
                    """,
                    (symbol, timeframe, float(point)),
                )
            self._upsert_rows(conn, symbol, timeframe, rows)
            self._prune(conn, symbol, timeframe)

        # Keep the legacy file as an explicit backup instead of deleting it.
        backup = legacy.with_suffix(legacy.suffix + ".migrated")
        if not backup.exists():
            legacy.replace(backup)

    @staticmethod
    def _upsert_rows(
        conn: sqlite3.Connection,
        symbol: str,
        timeframe: str,
        bars: list[HistoryBar],
    ) -> None:
        if not bars:
            return
        conn.executemany(
            """
            INSERT INTO history_bars(
                symbol,timeframe,time,broker_date,open,high,low,close,spread_points
            ) VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(symbol,timeframe,time) DO UPDATE SET
                broker_date=excluded.broker_date,
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                spread_points=excluded.spread_points
            """,
            [
                (
                    symbol,
                    timeframe,
                    bar.time,
                    bar.broker_date,
                    bar.open,
                    bar.high,
                    bar.low,
                    bar.close,
                    bar.spread_points,
                )
                for bar in bars
            ],
        )

    def _prune(self, conn: sqlite3.Connection, symbol: str, timeframe: str) -> None:
        if self.max_bars <= 0:
            return
        count = int(
            conn.execute(
                "SELECT COUNT(*) FROM history_bars WHERE symbol=? AND timeframe=?",
                (symbol, timeframe),
            ).fetchone()[0]
        )
        excess = count - self.max_bars
        if excess <= 0:
            return
        conn.execute(
            """
            DELETE FROM history_bars
            WHERE rowid IN (
                SELECT rowid FROM history_bars
                WHERE symbol=? AND timeframe=?
                ORDER BY time ASC
                LIMIT ?
            )
            """,
            (symbol, timeframe, excess),
        )

    @staticmethod
    def _row_to_bar(row: sqlite3.Row) -> HistoryBar:
        return HistoryBar(
            time=int(row["time"]),
            broker_date=str(row["broker_date"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            spread_points=int(row["spread_points"]),
        )

    def load(self, symbol: str, timeframe: str) -> list[HistoryBar]:
        self._ensure_legacy_migrated(symbol, timeframe)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT time,broker_date,open,high,low,close,spread_points
                FROM history_bars
                WHERE symbol=? AND timeframe=?
                ORDER BY time ASC
                """,
                (symbol, timeframe),
            ).fetchall()
        return [self._row_to_bar(row) for row in rows]

    def load_range(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
        *,
        lookback_bars: int = 300,
    ) -> list[HistoryBar]:
        """Load a calendar range plus a small pre-roll for indicators/context."""
        self._ensure_legacy_migrated(symbol, timeframe)
        with self._connect() as conn:
            range_rows = conn.execute(
                """
                SELECT time,broker_date,open,high,low,close,spread_points
                FROM history_bars
                WHERE symbol=? AND timeframe=? AND broker_date BETWEEN ? AND ?
                ORDER BY time ASC
                """,
                (symbol, timeframe, start_date, end_date),
            ).fetchall()
            if not range_rows:
                return []
            first_time = int(range_rows[0]["time"])
            pre_rows = conn.execute(
                """
                SELECT time,broker_date,open,high,low,close,spread_points
                FROM history_bars
                WHERE symbol=? AND timeframe=? AND time < ?
                ORDER BY time DESC
                LIMIT ?
                """,
                (symbol, timeframe, first_time, max(0, int(lookback_bars))),
            ).fetchall()
        rows = list(reversed(pre_rows)) + list(range_rows)
        return [self._row_to_bar(row) for row in rows]

    def save(self, sync: HistorySync) -> HistoryStatus:
        self._ensure_legacy_migrated(sync.symbol, sync.timeframe)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO history_meta(symbol,timeframe,point) VALUES(?,?,?)
                ON CONFLICT(symbol,timeframe) DO UPDATE SET point=excluded.point
                """,
                (sync.symbol, sync.timeframe, sync.point),
            )
            self._upsert_rows(conn, sync.symbol, sync.timeframe, sync.bars)
            self._prune(conn, sync.symbol, sync.timeframe)
        return self.status(sync.symbol, sync.timeframe)

    def point(self, symbol: str, timeframe: str) -> float | None:
        self._ensure_legacy_migrated(symbol, timeframe)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT point FROM history_meta WHERE symbol=? AND timeframe=?",
                (symbol, timeframe),
            ).fetchone()
        return float(row["point"]) if row is not None else None

    def status(self, symbol: str, timeframe: str) -> HistoryStatus:
        self._ensure_legacy_migrated(symbol, timeframe)
        with self._connect() as conn:
            aggregate = conn.execute(
                """
                SELECT COUNT(*) AS bars, MIN(broker_date) AS earliest, MAX(broker_date) AS latest
                FROM history_bars WHERE symbol=? AND timeframe=?
                """,
                (symbol, timeframe),
            ).fetchone()
            dates = [
                str(row["broker_date"])
                for row in conn.execute(
                    """
                    SELECT DISTINCT broker_date FROM history_bars
                    WHERE symbol=? AND timeframe=?
                    ORDER BY broker_date ASC
                    """,
                    (symbol, timeframe),
                ).fetchall()
            ]
        return HistoryStatus(
            symbol=symbol,
            timeframe=timeframe,
            bars=int(aggregate["bars"] or 0),
            earliest_date=str(aggregate["earliest"]) if aggregate["earliest"] is not None else None,
            latest_date=str(aggregate["latest"]) if aggregate["latest"] is not None else None,
            available_dates=dates,
        )
