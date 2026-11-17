from types import SimpleNamespace

import pytest
from werkzeug.exceptions import BadRequest
from flask import g, abort

from app import app
import club_store
import admin_routes
import firebase_auth
from firebase_admin import auth


def test_unknown_account_gives_registration_instructions_without_writes(monkeypatch):
    monkeypatch.setattr(firebase_auth, 'firebase_app', lambda: object())

    def missing_account(*args, **kwargs):
        raise auth.UserNotFoundError('Account does not exist')

    monkeypatch.setattr(auth, 'get_user_by_email', missing_account)
    monkeypatch.setattr(club_store, 'firestore_client', lambda: pytest.fail('No writes allowed for an unknown account'))
    with app.test_request_context('/'):
        with pytest.raises(BadRequest, match='todavía no está registrado'):
            club_store.add_admin('missing@example.com')


def test_verified_password_account_can_be_granted_admin(monkeypatch):
    user = SimpleNamespace(uid='existing-uid', email='person@example.com', display_name='Demo',
                           disabled=False, email_verified=True,
                           provider_data=[SimpleNamespace(provider_id='password')])
    monkeypatch.setattr(firebase_auth, 'firebase_app', lambda: object())
    monkeypatch.setattr(auth, 'get_user_by_email', lambda *args, **kwargs: user)
    profiles = []
    monkeypatch.setattr(club_store, 'ensure_user_profile', lambda **kwargs: profiles.append(kwargs))
    writes = []
    reference = SimpleNamespace(get=lambda: SimpleNamespace(to_dict=lambda: {'role': 'watcher'}),
                                set=lambda values, **kwargs: writes.append(values))
    client = SimpleNamespace(collection=lambda name: SimpleNamespace(document=lambda uid: reference))
    monkeypatch.setattr(club_store, 'firestore_client', lambda: client)

    club_store.add_admin(user.email)

    assert profiles[0]['provider'] == 'password'
    assert writes == [{'role': 'admin', 'active': True}]


def test_unverified_password_account_cannot_be_granted_admin(monkeypatch):
    user = SimpleNamespace(disabled=False, email_verified=False,
                           provider_data=[SimpleNamespace(provider_id='password')])
    monkeypatch.setattr(firebase_auth, 'firebase_app', lambda: object())
    monkeypatch.setattr(auth, 'get_user_by_email', lambda *args, **kwargs: user)
    monkeypatch.setattr(club_store, 'ensure_user_profile', lambda **kwargs: pytest.fail('No writes permitted'))
    with app.test_request_context('/'):
        with pytest.raises(BadRequest, match='verificar su correo'):
            club_store.add_admin('person@example.com')


def test_unknown_admin_returns_to_panel_with_message_not_404(monkeypatch):
    monkeypatch.setattr('app.authenticate_request', lambda: setattr(g, 'current_user', {
        'uid': 'admin-uid', 'role': 'admin', 'active': True,
    }))
    monkeypatch.setattr(admin_routes, 'storage_enabled', lambda: True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    monkeypatch.setattr(admin_routes, 'add_admin', lambda email: abort(400, description='Primero debe registrarse.'))
    client = app.test_client()
    response = client.post('/admin/admins', data={'email': 'new@example.com'})
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/admin#administradores')
    with client.session_transaction() as session:
        assert ('error', 'Primero debe registrarse.') in session['_flashes']
