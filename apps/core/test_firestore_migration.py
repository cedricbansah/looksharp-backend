from unittest.mock import patch

from apps.core.firestore_migration import flush_batch


class _FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeConnection:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return _FakeCursor()

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class _FakeStatement:
    def as_string(self, conn):
        return "INSERT INTO public.redemptions VALUES %s ON CONFLICT (user_id, offer_id) DO UPDATE"


def test_flush_batch_recovers_after_batch_conflict():
    conn = _FakeConnection()
    rows = [
        ("redemptions/doc-1", ("id-1", "user-1", "offer-1")),
        ("redemptions/doc-2", ("id-2", "user-1", "offer-1")),
    ]

    call_sizes = []

    def _fake_execute_values(cursor, sql_text, values, page_size):
        call_sizes.append(len(values))
        if len(values) == 2:
            raise Exception("ON CONFLICT DO UPDATE command cannot affect row a second time")

    with patch("apps.core.firestore_migration.execute_values", side_effect=_fake_execute_values):
        loaded = flush_batch(
            conn=conn,
            statement=_FakeStatement(),
            rows=rows,
            columns=["id", "user_id", "offer_id"],
            varchar_limits={},
            mapping_name="redemptions",
            page_size=500,
            dry_run=False,
        )

    assert loaded == 2
    assert call_sizes == [2, 1, 1]
    assert conn.rollbacks == 1
    assert conn.commits == 2
