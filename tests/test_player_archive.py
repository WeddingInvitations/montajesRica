from types import SimpleNamespace

from club_store import set_player_active


class FakeReference:
    def __init__(self):
        self.values = {"name": "Jugador de prueba", "active": True}
        self.writes = []

    def get(self):
        return SimpleNamespace(exists=True, to_dict=lambda: dict(self.values))

    def set(self, values, merge=False):
        assert merge is True
        self.writes.append(dict(values))
        for key, value in values.items():
            if value is DELETE_FIELD:
                self.values.pop(key, None)
            elif value is not SERVER_TIMESTAMP:
                self.values[key] = value


class FakeCollection:
    def __init__(self, reference):
        self.reference = reference

    def document(self, _record_id):
        return self.reference


class FakeClient:
    def __init__(self, reference):
        self.reference = reference

    def collection(self, _name):
        return FakeCollection(self.reference)


SERVER_TIMESTAMP = object()
DELETE_FIELD = object()


def test_soft_archive_and_restore_keep_player_document(monkeypatch):
    import google.cloud.firestore
    import club_store

    reference = FakeReference()
    monkeypatch.setattr(club_store, "firestore_client", lambda: FakeClient(reference))
    monkeypatch.setattr(club_store, "datastore_mode_enabled", lambda: False)
    monkeypatch.setattr(google.cloud.firestore, "SERVER_TIMESTAMP", SERVER_TIMESTAMP)
    monkeypatch.setattr(google.cloud.firestore, "DELETE_FIELD", DELETE_FIELD)

    set_player_active("player-1", False, "admin-uid")

    assert reference.values["active"] is False
    assert reference.values["deleted_by"] == "admin-uid"
    assert "name" in reference.values

    set_player_active("player-1", True, "admin-uid")

    assert reference.values["active"] is True
    assert "deleted_at" not in reference.values
    assert "deleted_by" not in reference.values
    assert reference.values["name"] == "Jugador de prueba"
