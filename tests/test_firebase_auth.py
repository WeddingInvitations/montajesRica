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


def test_firebase_token_accepts_google_and_password_with_verified_recent_email(monkeypatch):
    monkeypatch.setattr(firebase_auth, "firebase_app", lambda: object())
    monkeypatch.setattr(firebase_auth.auth, "verify_id_token", lambda token, **kwargs: _claims())

    claims = firebase_auth.verify_firebase_id_token("id-token", now=1010)

    assert claims["uid"] == "firebase-uid"
    monkeypatch.setattr(firebase_auth.auth, "verify_id_token", lambda token, **kwargs: _claims(provider="password"))
    password_claims = firebase_auth.verify_firebase_id_token("email-password-token", now=1010)
    assert password_claims["firebase"]["sign_in_provider"] == "password"


def test_firebase_token_rejects_providers_other_than_google_or_password(monkeypatch):
    monkeypatch.setattr(firebase_auth, "firebase_app", lambda: object())
    monkeypatch.setattr(firebase_auth.auth, "verify_id_token", lambda token, **kwargs: _claims(provider="facebook.com"))

    with pytest.raises(ValueError, match="Google o correo"):
        firebase_auth.verify_firebase_id_token("id-token", now=1010)


def test_firebase_token_rejects_unverified_email_and_stale_auth(monkeypatch):
    monkeypatch.setattr(firebase_auth, "firebase_app", lambda: object())
    monkeypatch.setattr(firebase_auth.auth, "verify_id_token", lambda token, **kwargs: _claims(email_verified=False))
    with pytest.raises(ValueError, match="verificar el correo"):
        firebase_auth.verify_firebase_id_token("id-token", now=1010)

    monkeypatch.setattr(firebase_auth.auth, "verify_id_token", lambda token, **kwargs: _claims(auth_time=1))
    with pytest.raises(ValueError, match="iniciar sesión"):
        firebase_auth.verify_firebase_id_token("id-token", now=1000)
