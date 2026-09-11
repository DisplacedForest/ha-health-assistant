from __future__ import annotations

from datetime import datetime

from .reconciliation import provider_rank, rule_for, values_close


def sync_exclusions(database):
    database.execute(
        "UPDATE bridge_records SET locally_excluded=COALESCE((SELECT status='excluded' FROM source_claims WHERE id=bridge_records.projection_id),locally_excluded) WHERE domain='scalar' AND projection_id IS NOT NULL"
    )
    database.execute(
        "UPDATE bridge_records SET locally_excluded=COALESCE((SELECT status='excluded' FROM workouts WHERE id=bridge_records.projection_id),locally_excluded) WHERE domain='workout' AND projection_id IS NOT NULL"
    )


def reconcile_streaming(database, person_id, metric, priority):
    rule = rule_for(metric)
    database.execute(
        "CREATE TEMP TABLE bridge_groups(group_id INTEGER PRIMARY KEY, canonical_id INTEGER NOT NULL, supplier_id INTEGER NOT NULL, anchor REAL NOT NULL, excluded INTEGER NOT NULL, flagged INTEGER NOT NULL DEFAULT 0)"
    )
    database.execute("CREATE INDEX temp.bridge_group_time ON bridge_groups(anchor)")
    database.execute(
        "CREATE TEMP TABLE bridge_members(claim_id INTEGER PRIMARY KEY,group_id INTEGER NOT NULL,provider TEXT NOT NULL)"
    )
    database.execute(
        "CREATE UNIQUE INDEX temp.bridge_member_provider ON bridge_members(group_id,provider)"
    )
    try:
        group_id = 0
        anchor = minimum = maximum = supplier_rank = canonical_id = supplier_id = None
        excluded = False

        def finish():
            if group_id:
                database.execute(
                    "INSERT INTO bridge_groups(group_id,canonical_id,supplier_id,anchor,excluded) VALUES(?,?,?,?,?)",
                    (
                        group_id,
                        canonical_id,
                        supplier_id,
                        anchor.timestamp(),
                        int(excluded),
                    ),
                )

        for row in database.iterate(
            "SELECT * FROM source_claims INDEXED BY idx_claims_reconcile WHERE person_id=? AND metric=? ORDER BY observed_at,provider,external_id",
            (person_id, metric.value),
        ):
            observed = datetime.fromisoformat(row["observed_at"])
            append = (
                group_id
                and rule.merge_window is not None
                and observed - anchor <= rule.merge_window
                and not database.execute(
                    "SELECT 1 FROM bridge_members WHERE group_id=? AND provider=?",
                    (group_id, row["provider"]),
                )
                and values_close(row["value"], minimum, rule.value_tolerance)
                and values_close(row["value"], maximum, rule.value_tolerance)
            )
            rank = provider_rank(row["provider"], priority)
            if not append:
                finish()
                group_id += 1
                anchor = observed
                minimum = maximum = row["value"]
                canonical_id = supplier_id = row["id"]
                supplier_rank = rank
                excluded = row["status"] == "excluded"
            else:
                minimum, maximum = (
                    min(minimum, row["value"]),
                    max(maximum, row["value"]),
                )
                canonical_id = min(canonical_id, row["id"])
                excluded = excluded or row["status"] == "excluded"
                if rank < supplier_rank:
                    supplier_id, supplier_rank = row["id"], rank
            database.execute(
                "INSERT INTO bridge_members VALUES(?,?,?)",
                (row["id"], group_id, row["provider"]),
            )
        finish()
        if rule.suspicious_window is not None:
            window = rule.suspicious_window.total_seconds()
            database.execute(
                """
                UPDATE bridge_groups AS a SET flagged=1 WHERE EXISTS(
                    SELECT 1 FROM bridge_groups b WHERE b.anchor BETWEEN a.anchor-? AND a.anchor+? AND b.group_id<>a.group_id
                    AND EXISTS(SELECT 1 FROM bridge_members x WHERE x.group_id=a.group_id AND NOT EXISTS(SELECT 1 FROM bridge_members y WHERE y.group_id=b.group_id AND y.provider=x.provider))
                    AND EXISTS(SELECT 1 FROM bridge_members x WHERE x.group_id=b.group_id AND NOT EXISTS(SELECT 1 FROM bridge_members y WHERE y.group_id=a.group_id AND y.provider=x.provider))
                )
            """,
                (window, window),
            )
        database.execute("""
            INSERT INTO observations(id,person_id,metric,value,unit,observed_at,provider,external_id,ingested_at,provenance,status,possible_duplicate)
            SELECT g.canonical_id,c.person_id,c.metric,c.value,c.unit,c.observed_at,c.provider,c.external_id,c.ingested_at,c.provenance,CASE g.excluded WHEN 1 THEN 'excluded' ELSE 'active' END,g.flagged
            FROM bridge_groups g JOIN source_claims c ON c.id=g.supplier_id WHERE 1
            ON CONFLICT(id) DO UPDATE SET person_id=excluded.person_id,metric=excluded.metric,value=excluded.value,unit=excluded.unit,observed_at=excluded.observed_at,provider=excluded.provider,external_id=excluded.external_id,ingested_at=excluded.ingested_at,provenance=excluded.provenance,status=excluded.status,possible_duplicate=excluded.possible_duplicate
        """)
        database.execute(
            """
            UPDATE source_claims SET
            observation_id=(SELECT g.canonical_id FROM bridge_members m JOIN bridge_groups g USING(group_id) WHERE m.claim_id=source_claims.id),
            status=(SELECT CASE g.excluded WHEN 1 THEN 'excluded' ELSE 'active' END FROM bridge_members m JOIN bridge_groups g USING(group_id) WHERE m.claim_id=source_claims.id)
            WHERE person_id=? AND metric=?
        """,
            (person_id, metric.value),
        )
        database.execute(
            "DELETE FROM observations WHERE person_id=? AND metric=? AND NOT EXISTS(SELECT 1 FROM source_claims WHERE observation_id=observations.id)",
            (person_id, metric.value),
        )
        sync_exclusions(database)
    finally:
        database.execute("DROP TABLE bridge_members")
        database.execute("DROP TABLE bridge_groups")
