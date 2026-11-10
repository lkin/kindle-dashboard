"""Fetch live dashboard widgets; cache only inside the private dashboard PNG."""
import hashlib
import json
import os
import random
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

JST = ZoneInfo('Asia/Tokyo')
TIMEOUT = 12
STATE_KEY = 'scribe_widget_state_v1'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

OPENER = urllib.request.build_opener(NoRedirect())

def request(url, headers=None, limit=4_000_000):
    if not url.startswith('https://'):
        raise ValueError('HTTPS required')
    req = urllib.request.Request(url, headers={'User-Agent': 'ScribeDashboard/1.0', **(headers or {})})
    with OPENER.open(req, timeout=TIMEOUT) as response:
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError('response too large')
        return body

def get_json(url):
    return json.loads(request(url))

def previous_state(url, token):
    if not url or not token:
        return {}
    try:
        image = Image.open(BytesIO(request(url, {'Authorization': 'Bearer ' + token})))
        if image.format != 'PNG' or image.size != (1860, 2480):
            return {}
        return json.loads(image.info.get(STATE_KEY, '{}'))
    except (ValueError, OSError, urllib.error.URLError):
        return {}

def degrees(value):
    c = round(float(value)); f = round(float(value) * 9 / 5 + 32)
    return f'{c}°C / {f}°F'

def condition(code):
    if code == 0: return 'Clear sky'
    if code == 1: return 'Mostly clear'
    if code == 2: return 'Partly cloudy'
    if code == 3: return 'Overcast'
    if code in (45, 48): return 'Fog'
    if code in (51, 53, 55, 56, 57): return 'Drizzle'
    if code in (61, 63, 65, 66, 67): return 'Rain'
    if code in (71, 73, 75, 77): return 'Snow'
    if code in (80, 81, 82): return 'Rain showers'
    if code in (85, 86): return 'Snow showers'
    if code in (95, 96, 99): return 'Thunderstorms'
    return 'Conditions unavailable'

def weather_data(lat, lon, now):
    q = urllib.parse.urlencode({'latitude': lat, 'longitude': lon, 'timezone': 'Asia/Tokyo',
        'forecast_days': 3, 'current': 'temperature_2m,weather_code',
        'hourly': 'temperature_2m,precipitation_probability',
        'daily': 'temperature_2m_max,temperature_2m_min'})
    data = get_json('https://api.open-meteo.com/v1/forecast?' + q)
    current, daily, hourly = data['current'], data['daily'], data['hourly']
    times = hourly['time']; temperatures = hourly['temperature_2m']; rain = hourly['precipitation_probability']
    # Start at the next three-hour boundary in local time; next day is included.
    entries = []
    for i, value in enumerate(times):
        dt = datetime.fromisoformat(value).replace(tzinfo=JST)
        if dt >= now.replace(minute=0, second=0, microsecond=0) and dt.hour % 3 == 0:
            if temperatures[i] is None: continue
            c = round(float(temperatures[i])); f = round(float(temperatures[i]) * 9 / 5 + 32)
            entries.append({'time': dt.strftime('%H:%M'), 'temperature': f'{c}°/{f}°',
                            'precipitation': f'{round(rain[i])}%' if rain[i] is not None else '—'})
            if len(entries) == 5: break
    if len(entries) < 5: raise ValueError('incomplete hourly forecast')
    return {'display_temperature': degrees(current['temperature_2m']), 'condition': condition(int(current['weather_code'])),
            'high_low': 'High ' + degrees(daily['temperature_2m_max'][0]) + '   ·   Low ' + degrees(daily['temperature_2m_min'][0]),
            'forecast': entries, 'fetched_at': now.isoformat()}

def kanji_data(now):
    # Grades 4–6 and 8: Jōyō, omitting the 440 characters in grades 1–3.
    candidates = []
    for grade in (4, 5, 6, 8):
        candidates.extend(get_json(f'https://kanjiapi.dev/v1/kanji/grade-{grade}'))
    if not candidates: raise ValueError('empty kanji list')
    rng = random.Random(int.from_bytes(hashlib.sha256(now.date().isoformat().encode()).digest()[:8], 'big'))
    character = rng.choice(candidates)
    path = urllib.parse.quote(character, safe='')
    item = get_json('https://kanjiapi.dev/v1/kanji/' + path)
    words = get_json('https://kanjiapi.dev/v1/words/' + path)
    examples = []
    for word in words:
        glosses = [g for meaning in word.get('meanings', []) for g in meaning.get('glosses', [])]
        if not glosses: continue
        for variant in word.get('variants', []):
            written = variant.get('written', '')
            if character not in written or not 2 <= len(written) <= 5: continue
            priority = bool(variant.get('priorities'))
            examples.append((not priority, len(written), written, variant.get('pronounced', ''), glosses[0]))
    examples.sort()
    selected = []
    seen = set()
    for _, _, written, reading, meaning in examples:
        if written in seen: continue
        seen.add(written)
        selected.append({'word': written, 'reading': reading[:10], 'meaning': meaning[:24]})
        if len(selected) == 3: break
    if not selected: raise ValueError('no dictionary examples')
    return {'character': character, 'meaning': ' · '.join(item.get('meanings', [])[:2])[:28] or '—',
            'readings': ' / '.join((item.get('on_readings', [])[:2] + item.get('kun_readings', [])[:2]))[:28] or '—',
            'examples': selected, 'date': now.date().isoformat()}

def notion_tasks(token, source_id):
    """Read a bounded set of open tasks without logging the response."""
    if not token or not source_id:
        raise ValueError('Notion connection not configured')
    # Source ID is configured independently of the access token.
    import uuid
    source_id = str(uuid.UUID(source_id))
    url = 'https://api.notion.com/v1/data_sources/' + source_id + '/query'
    headers = {'Authorization': 'Bearer ' + token, 'Notion-Version': '2025-09-03',
               'Content-Type': 'application/json', 'User-Agent': 'ScribeDashboard/1.0'}
    results = []
    cursor = None
    for _ in range(3):
        query = {'page_size': 100, 'filter': {'and': [
            {'property': 'Status', 'status': {'does_not_equal': 'Done'}},
            {'property': 'Status', 'status': {'does_not_equal': 'Dropped'}}]}}
        if cursor: query['start_cursor'] = cursor
        req = urllib.request.Request(url, data=json.dumps(query).encode(), headers=headers, method='POST')
        with OPENER.open(req, timeout=TIMEOUT) as response:
            raw = response.read(2_000_001)
            if len(raw) > 2_000_000: raise ValueError('Notion response too large')
            data = json.loads(raw)
        results.extend(data['results'])
        if not data.get('has_more'): break
        cursor = data.get('next_cursor')
        if not cursor: raise ValueError('Notion pagination missing cursor')
    if data.get('has_more'): raise ValueError('Notion result limit exceeded')
    tasks = []
    for row in results:
        properties = row.get('properties', {})
        title = ''.join(item.get('plain_text', '') for item in properties.get('Task name', {}).get('title', [])).strip()
        if not title: continue
        status = (properties.get('Status', {}).get('status') or {}).get('name')
        if status in ('Done', 'Dropped'): continue
        priority = (properties.get('Priority', {}).get('select') or {}).get('name')
        due = (properties.get('Due', {}).get('date') or {}).get('start') or '9999-12-31'
        tasks.append(({'high': 0, 'normal': 1, 'medium': 1, 'low': 2}.get((priority or '').casefold(), 3), due, title))
    tasks.sort(key=lambda item: (item[0], item[1], item[2].casefold()))
    return [item[2] for item in tasks[:5]]

def google_events(credentials_json, calendar_ids_json, now):
    """Read today's events using an OAuth refresh token; never log data or URLs."""
    if not credentials_json or not calendar_ids_json:
        raise ValueError('Calendar authorization not configured')
    credentials = json.loads(credentials_json)
    calendar_ids = json.loads(calendar_ids_json)
    if not isinstance(calendar_ids, list) or not calendar_ids:
        raise ValueError('Calendar IDs not configured')
    token_data = urllib.parse.urlencode({'client_id': credentials['client_id'],
        'client_secret': credentials['client_secret'], 'refresh_token': credentials['refresh_token'],
        'grant_type': 'refresh_token'}).encode()
    token_req = urllib.request.Request('https://oauth2.googleapis.com/token', data=token_data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
    with OPENER.open(token_req, timeout=TIMEOUT) as response:
        access_token = json.loads(response.read(100_000))['access_token']
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    events, seen = [], set()
    for calendar_id in calendar_ids:
        cursor = None
        for _ in range(5):
            params = {'timeMin': start.isoformat(), 'timeMax': end.isoformat(), 'singleEvents': 'true',
                      'orderBy': 'startTime', 'maxResults': '250',
                      'fields': 'items(start,end,summary,status,iCalUID,attendees(self,responseStatus)),nextPageToken'}
            if cursor: params['pageToken'] = cursor
            url = ('https://www.googleapis.com/calendar/v3/calendars/' +
                   urllib.parse.quote(calendar_id, safe='') + '/events?' + urllib.parse.urlencode(params))
            data = json.loads(request(url, {'Authorization': 'Bearer ' + access_token}, limit=2_000_000))
            for event in data.get('items', []):
                if event.get('status') == 'cancelled': continue
                if any(a.get('self') and a.get('responseStatus') == 'declined' for a in event.get('attendees', [])): continue
                begin = event.get('start', {})
                instant = begin.get('dateTime') or begin.get('date')
                if not instant: continue
                uid = event.get('iCalUID')
                # Instances of one recurring event share an iCalUID, so include start.
                key = (uid, instant) if uid else None
                if key and key in seen: continue
                if key: seen.add(key)
                if begin.get('dateTime'):
                    dt = datetime.fromisoformat(begin['dateTime'].replace('Z', '+00:00')).astimezone(JST)
                    label = dt.strftime('%H:%M') if dt >= start else 'Ongoing'
                    sort_key = max(dt, start).isoformat()
                else:
                    label, sort_key = 'All day', start.isoformat()
                events.append((sort_key, label, event.get('summary') or 'Busy'))
            cursor = data.get('nextPageToken')
            if not cursor: break
        if cursor: raise ValueError('Calendar result limit exceeded')
    events.sort(key=lambda e: (e[0], e[2].casefold()))
    return [{'time': label, 'title': title} for _, label, title in events[:4]]

def build(fixture, state, now, lat, lon):
    result = dict(fixture)
    try:
        result['events'] = google_events(os.environ.get('GOOGLE_CALENDAR_CREDENTIALS'), os.environ.get('GOOGLE_CALENDAR_IDS'), now)
        result['events_status'] = 'GOOGLE CALENDAR' if result['events'] else 'NO EVENTS TODAY'
        print('Calendar: events loaded')
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError):
        result['events'] = []
        result['events_status'] = 'CALENDAR UNAVAILABLE' if os.environ.get('GOOGLE_CALENDAR_CREDENTIALS') else 'CALENDAR SETUP REQUIRED'
        print('Calendar: unavailable or not configured')
    prior_weather = state.get('weather')
    try:
        if not lat or not lon: raise ValueError('weather location is not configured')
        weather = weather_data(lat, lon, now)
        print('Weather: live')
    except (ValueError, KeyError, IndexError, TypeError, OSError, urllib.error.URLError):
        weather = prior_weather
        print('Weather: using private saved forecast' if weather else 'Weather: unavailable (no saved forecast)')
    if weather:
        result['weather'] = dict(weather)
        age = now - datetime.fromisoformat(weather['fetched_at'])
        result['weather']['status'] = ('Forecast saved ' + datetime.fromisoformat(weather['fetched_at']).strftime('%b %d %H:%M') if age >= timedelta(hours=3) else 'Precipitation chance')
    else:
        result['weather'] = {'display_temperature': '—', 'condition': 'Weather unavailable', 'high_low': '', 'forecast': [], 'status': 'No saved forecast'}
    try:
        kanji = state.get('kanji')
        if not kanji or kanji.get('date') != now.date().isoformat():
            kanji = kanji_data(now)
            print('Kanji: dictionary')
        else:
            print('Kanji: saved daily selection')
    except (ValueError, KeyError, IndexError, TypeError, OSError, urllib.error.URLError):
        kanji = state.get('kanji')
        print('Kanji: saved' if kanji else 'Kanji: unavailable')
    result['kanji'] = kanji or {'character': '—', 'meaning': 'Dictionary unavailable', 'readings': '', 'examples': []}
    try:
        result['tasks'] = notion_tasks(os.environ.get('NOTION_TOKEN'), os.environ.get('NOTION_DATA_SOURCE_ID'))
        result['tasks_status'] = 'NOTION  ·  OPEN TASKS' if result['tasks'] else 'NO OPEN TASKS'
        print('Notion: tasks loaded')
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError):
        result['tasks'] = []
        result['tasks_status'] = 'NOTION UNAVAILABLE'
        print('Notion: unavailable')
    return result, {k: v for k, v in [('weather', weather), ('kanji', kanji)] if v}

if __name__ == '__main__':
    now = datetime.now(JST)
    state = previous_state(os.environ.get('DASHBOARD_IMAGE_URL'), os.environ.get('DASHBOARD_READ_TOKEN'))
    print('Private widget state:', 'available' if state else 'not yet available')
    result, state = build(json.loads(Path('demo.json').read_text(encoding='utf-8')), state, now,
                          os.environ.get('WEATHER_LATITUDE'), os.environ.get('WEATHER_LONGITUDE'))
    Path('/tmp/scribe-live-data.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    Path('/tmp/scribe-widget-state.json').write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
