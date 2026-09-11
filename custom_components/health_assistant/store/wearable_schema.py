MIGRATION = (
    """
    CREATE TABLE wearable_streams (
        id INTEGER PRIMARY KEY,
        stream_id TEXT NOT NULL UNIQUE,
        source_id TEXT NOT NULL REFERENCES bridge_sources(source_id),
        metric TEXT NOT NULL CHECK(metric='heart_rate'),
        unit TEXT NOT NULL CHECK(unit='bpm'),
        weighting TEXT NOT NULL CHECK(weighting IN ('sample','time')),
        algorithm_id TEXT,
        algorithm_version TEXT,
        retired INTEGER NOT NULL DEFAULT 0 CHECK(retired IN (0,1)),
        origin_mode TEXT NOT NULL CHECK(origin_mode IN ('local_enrollment','imported_history')),
        sequence INTEGER NOT NULL DEFAULT 0 CHECK(sequence>=0),
        content_hash BLOB,
        degraded INTEGER NOT NULL DEFAULT 0 CHECK(degraded IN (0,1)),
        CHECK((sequence=0 AND content_hash IS NULL) OR
              (sequence>0 AND length(content_hash)=32))
    )
    """,
    "CREATE INDEX idx_wearable_source ON wearable_streams(source_id)",
    """
    CREATE TABLE wearable_buckets (
        stream_id INTEGER NOT NULL REFERENCES wearable_streams(id),
        start_us INTEGER NOT NULL,
        resolution_s INTEGER NOT NULL CHECK(resolution_s IN (60,300,3600)),
        weight INTEGER NOT NULL CHECK(weight>0),
        total REAL NOT NULL,
        minimum REAL NOT NULL,
        maximum REAL NOT NULL,
        PRIMARY KEY(stream_id,start_us)
    ) WITHOUT ROWID
    """,
    """
    CREATE TABLE wearable_state (
        id INTEGER PRIMARY KEY CHECK(id=1),
        generation TEXT NOT NULL
    )
    """,
    "INSERT INTO wearable_state(id,generation) VALUES(1,lower(hex(randomblob(16))))",
)
