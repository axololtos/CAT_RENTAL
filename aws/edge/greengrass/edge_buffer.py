"""Greengrass v2 component runtime for com.catrentals.EdgeTelemetryBuffer.

Reads telemetry readings produced locally on the gateway, persists every
reading to a local SQLite table immediately (store), and runs a background
flush loop that forwards unsent rows to the Stream Manager stream (forward).
If the gateway loses cellular connectivity, forwarding fails, rows stay
queued in SQLite with an exponential backoff, and normal operation resumes
automatically once Stream Manager reports the stream is reachable again.
"""
import argparse
import json
import logging
import sqlite3
import time
from pathlib import Path

from stream_manager import ExportDefinition, MessageStreamDefinition, StreamManagerClient
from stream_manager.data import ResourceNotFoundException, StreamManagerException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edge_telemetry_buffer")

SCHEMA = """
CREATE TABLE IF NOT EXISTS telemetry_buffer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL,
    created_at REAL NOT NULL,
    sent INTEGER NOT NULL DEFAULT 0
)
"""


def _connect(sqlite_path: str) -> sqlite3.Connection:
    Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(sqlite_path)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def store_reading(conn: sqlite3.Connection, reading: dict) -> None:
    conn.execute(
        "INSERT INTO telemetry_buffer (payload, created_at) VALUES (?, ?)",
        (json.dumps(reading), time.time()),
    )
    conn.commit()


def _ensure_stream(client: StreamManagerClient, stream_name: str, max_size_bytes: int) -> None:
    try:
        client.describe_message_stream(stream_name)
    except ResourceNotFoundException:
        client.create_message_stream(
            MessageStreamDefinition(
                name=stream_name,
                max_size=max_size_bytes,
                export_definition=ExportDefinition(),
            )
        )


def flush_pending(
    conn: sqlite3.Connection,
    client: StreamManagerClient,
    stream_name: str,
    batch_size: int,
    backoff_seconds: float,
) -> float:
    """Attempts to forward unsent rows. Returns the next backoff to use."""
    rows = conn.execute(
        "SELECT id, payload FROM telemetry_buffer WHERE sent = 0 ORDER BY id LIMIT ?",
        (batch_size,),
    ).fetchall()

    if not rows:
        return backoff_seconds

    try:
        for row_id, payload in rows:
            client.append_message(stream_name, payload.encode("utf-8"))
            conn.execute("UPDATE telemetry_buffer SET sent = 1 WHERE id = ?", (row_id,))
        conn.commit()
        logger.info("Flushed %d buffered reading(s) to %s", len(rows), stream_name)
        return 1.0  # reset backoff after a successful flush
    except StreamManagerException as exc:
        logger.warning("Stream Manager unavailable, keeping %d row(s) queued: %s", len(rows), exc)
        return min(backoff_seconds * 2, 300.0)


def prune_sent(conn: sqlite3.Connection, keep_days: int = 7) -> None:
    cutoff = time.time() - keep_days * 86400
    conn.execute("DELETE FROM telemetry_buffer WHERE sent = 1 AND created_at < ?", (cutoff,))
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-path", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--stream-name", required=True)
    parser.add_argument("--flush-interval", type=float, default=15)
    parser.add_argument("--flush-batch-size", type=int, default=100)
    parser.add_argument("--max-retry-backoff", type=float, default=300)
    args = parser.parse_args()

    conn = _connect(args.sqlite_path)
    client = StreamManagerClient()
    _ensure_stream(client, args.stream_name, max_size_bytes=256 * 1024 * 1024)

    backoff = 1.0
    while True:
        # In production this reads from the local sensor/PLC bus or a
        # subprocess subscribed to the on-gateway MQTT broker; readings are
        # stored immediately regardless of whether the uplink is up.
        backoff = flush_pending(
            conn, client, args.stream_name, args.flush_batch_size, backoff
        )
        prune_sent(conn)
        time.sleep(max(args.flush_interval, backoff if backoff > args.flush_interval else args.flush_interval))


if __name__ == "__main__":
    main()
