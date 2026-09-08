from datetime import date, datetime
from io import BytesIO

import pytest

from workhours.web import create_app


@pytest.fixture()
def app(tmp_path):
    app = create_app(tmp_path / 'hours.db', lambda: date(2026, 7, 6),
                     lambda: datetime(2026, 7, 6, 8, 0))
    app.config.update(TESTING=True, HOLIDAY_NETWORK_ENABLED=False)
    return app


def test_interface_switch_remembers_selection_and_date(app):
    client = app.test_client()
    response = client.get('/interface/old?reference_date=2026-07-03', follow_redirects=True)
    assert response.status_code == 200
    assert '正在查看 2026-07-03' in response.text
    assert '切换新界面' in response.text
    assert '工作时长预测' in client.get('/').text
    response = client.get('/interface/new?reference_date=2026-07-03')
    assert 'reference_date=2026-07-03' in response.location
    assert client.get_cookie('workhours_ui').value == 'new'


def test_default_serves_built_react_interface(app):
    response = app.test_client().get('/')
    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text


def test_explicit_legacy_url_keeps_forms_and_date_navigation_in_legacy(app):
    client = app.test_client()
    assert client.get('/?ui=old').status_code == 200
    response = client.post('/entries', data={
        'work_date': '2026-07-06', 'start_time': '08:00', 'end_time': ''}, follow_redirects=True)
    assert response.status_code == 200
    assert '工作时长预测' in response.text
    assert '正在查看 2026-07-03' in client.get('/?reference_date=2026-07-03').text


def test_dashboard_uses_main_rules_and_supports_incomplete_and_overnight(app):
    client = app.test_client()
    assert client.put('/api/entries/2026-07-03', json={
        'start_time': '09:00', 'end_time': '18:30'}).status_code == 200
    assert client.put('/api/entries/2026-07-06', json={
        'start_time': '08:00', 'end_time': None}).status_code == 200
    data = client.get('/api/dashboard?reference_date=2026-07-06').json
    assert data['selected_preview']['required_minutes'] == 600
    # 08:00 + 10 working hours + 90 minutes lunch reaches 19:30 exactly;
    # the evening break starts at that instant and must not be deducted.
    assert data['selected_preview']['suggested_end'] == '19:30'
    assert data['month']['balance_minutes'] == -60
    legacy = client.get('/?ui=old&reference_date=2026-07-06').text
    assert '19:30' in legacy and '10小时' in legacy
    assert client.put('/api/entries/2026-07-06', json={
        'start_time': '22:00', 'end_time': '07:00'}).status_code == 200
    day = next(d for d in client.get('/api/dashboard').json['days'] if d['date'] == '2026-07-06')
    assert day['actual_minutes'] == 540


def test_leave_preserves_punches_and_manual_makeup_day(app):
    client = app.test_client()
    client.put('/api/calendar/2026-07-04', json={'kind': 'workday'})
    client.put('/api/entries/2026-07-04', json={'start_time': '08:00', 'end_time': '18:30'})
    before = client.get('/api/dashboard').json
    assert client.put('/api/leaves/2026-07-04', json={'enabled': True}).status_code == 200
    during = client.get('/api/dashboard').json
    assert during['month']['target_minutes'] == before['month']['target_minutes'] - 540
    day = next(d for d in during['days'] if d['date'] == '2026-07-04')
    assert day['leave'] and not day['is_workday']
    assert day['entry']['start_time'] == '08:00'
    assert day['manual_override'] == 'workday'
    assert day['actual_minutes'] is None
    client.put('/api/leaves/2026-07-04', json={'enabled': False})
    assert client.get('/api/dashboard').json['month'] == before['month']


def test_legacy_leave_and_refresh_controls_share_state(app):
    client = app.test_client()
    response = client.post('/leaves', data={
        'work_date': '2026-07-06', 'enabled': '1'}, follow_redirects=False)
    assert response.status_code == 302
    assert client.get('/api/dashboard').json['selected_preview']['available'] is False
    body = client.get('/?ui=old').text
    assert '全天请假' in body
    assert '导出备份' in body and '导入备份' in body and '刷新节假日' in body
    client.post('/leaves', data={'work_date': '2026-07-06', 'enabled': '0'})
    assert not next(d for d in client.get('/api/dashboard').json['days'] if d['date'] == '2026-07-06')['leave']


def test_holiday_fetch_refresh_manual_priority_and_leave(app):
    app.config.update(HOLIDAY_NETWORK_ENABLED=True, HOLIDAY_FETCHER=lambda url: {
        'days': [{'date': '2026-07-04', 'name': '补班', 'isOffDay': False},
                 {'date': '2026-07-06', 'name': '休息', 'isOffDay': True}]})
    client = app.test_client()
    first = client.get('/api/dashboard').json
    assert first['holiday_status']['source'] == 'remote'
    assert next(d for d in first['days'] if d['date'] == '2026-07-04')['is_workday']
    client.put('/api/calendar/2026-07-04', json={'kind': 'holiday'})
    client.put('/api/calendar/2026-07-06', json={'kind': 'workday'})
    client.put('/api/entries/2026-07-06', json={'start_time': '08:00', 'end_time': None})
    assert client.get('/api/dashboard').json['selected_preview']['available']
    client.put('/api/leaves/2026-07-06', json={'enabled': True})
    assert not client.get('/preview/earliest-end?work_date=2026-07-06&start_time=08:00').json['available']
    app.config['HOLIDAY_FETCHER'] = lambda url: (_ for _ in ()).throw(OSError('offline'))
    refreshed = client.post('/api/holidays/2026/refresh').json
    assert refreshed['source'] == 'cache' and refreshed['warning']


@pytest.mark.parametrize('path,payload', [
    ('/api/entries/2026-07-06', {'start_time': '08:00:59', 'end_time': None}),
    ('/api/entries/2026-02-30', {'start_time': '08:00', 'end_time': None}),
    ('/api/leaves/2026-07-06', {'enabled': 'false'}),
    ('/api/settings', {'period': 'year'}),
    ('/api/settings', {'period': []}),
    ('/api/settings', {'theme': {}}),
    ('/api/calendar/2026-07-06', {'kind': 'leave'}),
    ('/api/calendar/2026-07-06', {'kind': []}),
])
def test_invalid_api_mutations_return_readable_error_without_writes(app, path, payload):
    client = app.test_client()
    before = client.get('/api/dashboard').json
    response = client.put(path, json=payload)
    assert response.status_code == 400
    assert response.json['error']
    assert client.get('/api/dashboard').json['month'] == before['month']


def test_backup_download_restore_and_invalid_file_are_atomic(app):
    client = app.test_client()
    client.put('/api/entries/2026-07-06', json={'start_time': '08:00', 'end_time': None})
    exported = client.get('/api/backup')
    assert exported.status_code == 200
    assert exported.json['version'] == 3
    assert 'attachment;' in exported.headers['Content-Disposition']
    client.delete('/api/entries/2026-07-06')
    response = client.post('/api/backup', data={'file': (BytesIO(exported.data), 'backup.json')})
    assert response.status_code == 200
    assert client.get('/api/dashboard').json['selected_preview']['suggested_end'] == '18:30'
    response = client.post('/api/backup', data={'file': (BytesIO(b'{invalid'), 'bad.json')})
    assert response.status_code == 400
    assert client.get('/api/dashboard').json['selected_preview']['suggested_end'] == '18:30'


def test_settings_and_intervals_recompute_same_backend(app):
    client = app.test_client()
    client.put('/api/settings', json={'period': 'month', 'theme': 'teal'})
    client.put('/api/entries/2026-07-06', json={'start_time': '08:00', 'end_time': '18:30'})
    first = client.get('/api/dashboard').json
    assert first['settings']['period'] == 'month' and first['theme'] == 'teal'
    lunch = next(item for item in first['intervals'] if item['name'] == '午休')
    lunch['enabled'] = False
    assert client.post('/api/non-working-intervals', json=lunch).status_code == 200
    later = client.get('/api/dashboard').json
    assert later['month']['completed_minutes'] == first['month']['completed_minutes'] + 90


def test_classic_theme_setting_changes_only_presentation_and_round_trips_backup(app):
    client = app.test_client()
    client.put('/api/entries/2026-07-06', json={'start_time': '08:00', 'end_time': '18:30'})
    before = client.get('/api/dashboard').json
    saved = client.put('/api/settings', json={'theme': 'classic'})
    assert saved.status_code == 200
    after = client.get('/api/dashboard').json
    assert after['theme'] == 'classic'
    for field in ('month', 'forecast', 'days', 'intervals', 'settings', 'selected_preview'):
        assert after[field] == before[field]
    exported = client.get('/api/backup')
    assert exported.json['settings']['theme'] == 'classic'
    client.put('/api/settings', json={'theme': 'cool'})
    restored = client.post('/api/backup', data={'file': (BytesIO(exported.data), 'classic.json')})
    assert restored.status_code == 200
    assert client.get('/api/dashboard').json['theme'] == 'classic'
    rejected = client.put('/api/settings', json={'period': 'month', 'theme': 'invalid'})
    assert rejected.status_code == 400
    assert client.get('/api/dashboard').json['theme'] == 'classic'
    assert client.get('/api/dashboard').json['settings'] == before['settings']
