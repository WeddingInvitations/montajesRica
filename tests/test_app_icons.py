import json
import struct
from pathlib import Path

from app import app

ROOT = Path(__file__).resolve().parents[1]


def test_login_has_browser_and_mobile_icon_links_without_authentication():
    page = app.test_client().get('/').get_data(as_text=True)
    assert 'rel="icon"' in page
    assert 'rel="apple-touch-icon"' in page
    assert 'sizes="180x180"' in page
    assert 'rel="manifest"' in page
    assert 'name="apple-mobile-web-app-title" content="Montajes Rica"' in page
    for template in ['index.html', 'admin.html', 'error.html']:
        assert "include 'partials/app_icons.html'" in (ROOT / 'templates' / template).read_text(encoding='utf-8')


def test_manifest_launches_home_and_has_public_android_icons():
    client = app.test_client()
    response = client.get('/static/manifest.webmanifest')
    assert response.status_code == 200
    manifest = json.loads(response.data)
    assert manifest['start_url'] == '/'
    assert manifest['scope'] == '/'
    assert manifest['display'] == 'standalone'
    assert manifest['short_name'] == 'Montajes Rica'
    assert {icon['sizes'] for icon in manifest['icons']} == {'192x192', '512x512'}
    for icon in manifest['icons']:
        assert client.get(icon['src']).status_code == 200


def test_generated_png_dimensions_and_favicon_resolutions():
    client = app.test_client()
    for size in [16, 32, 48, 180, 192, 512]:
        response = client.get(f'/static/icons/icon-{size}.png')
        assert response.status_code == 200
        assert response.mimetype == 'image/png'
        assert response.data[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II', response.data[16:24]) == (size, size)
    response = client.get('/static/icons/favicon.ico')
    assert response.status_code == 200
    assert struct.unpack('<HHH', response.data[:6]) == (0, 1, 3)
    for index, size in enumerate([16, 32, 48]):
        entry = response.data[6 + index * 16:22 + index * 16]
        width, height, _, _, planes, bits, length, offset = struct.unpack('<BBBBHHII', entry)
        assert (width, height, planes, bits) == (size, size, 1, 32)
        assert response.data[offset:offset + 8] == b'\x89PNG\r\n\x1a\n'
        assert offset + length <= len(response.data)