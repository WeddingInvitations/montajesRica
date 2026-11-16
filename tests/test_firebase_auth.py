import pytest

import firebase_auth


def _claims(provider="google.com", email_verified=True, auth_time=1000):
    return {
        "uid": "firebase-uid",
        "email": "player@example.com",
        "email_verified": email_verified,
        "auth_time": auth_time,
        "firebase": {"sign_in_provider": provider},
    }


def test_firebase_token_requires_google_verified_email_and_recent_sign_in(monkeypatch):
    monkeypatch.setattr(firebase_auth, "firebase_app", lambda: object())
    monkeypatch.setattr(firebase_auth.auth, "verify_id_token", lambda token, **kwargs: _claims())

    claims = firebase_auth.verify_google_id_token("id-token", now=1010)

    assert claims["uid"] == "firebase-uid"


def test_firebase_token_rejects_non_google_provider(monkeypatch):
    monkeypatch.setattr(firebase_auth, "firebase_app", lambda: object())
    monkeypatch.setattr(firebase_auth.auth, "verify_id_token", lambda token, **kwargs: _claims(provider="password"))

    with pytest.raises(ValueError, match="Google"):
        firebase_auth.verify_google_id_token("id-token", now=1010)


def test_firebase_token_rejects_unverified_email_and_stale_auth(monkeypatch):
    monkeypatch.setattr(firebase_auth, "firebase_app", lambda: object())
    monkeypatch.setattr(firebase_auth.auth, "verify_id_token", lambda token, **kwargs: _claims(email_verified=False))
    with pytest.raises(ValueError, match="verificado"):
        firebase_auth.verify_google_id_token("id-token", now=1010)

    monkeypatch.setattr(firebase_auth.auth, "verify_id_token", lambda token, **kwargs: _claims(auth_time=1))
    with pytest.raises(ValueError, match="iniciar sesión"):
        firebase_auth.verify_google_id_token("id-token", now=1000)
