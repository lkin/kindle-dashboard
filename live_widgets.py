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

def build(fixture, state, now, lat, lon):
    result = dict(fixture)
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
    return result, {k: v for k, v in [('weather', weather), ('kanji', kanji)] if v}

if __name__ == '__main__':
    now = datetime.now(JST)
    state = previous_state(os.environ.get('DASHBOARD_IMAGE_URL'), os.environ.get('DASHBOARD_READ_TOKEN'))
    print('Private widget state:', 'available' if state else 'not yet available')
    result, state = build(json.loads(Path('demo.json').read_text(encoding='utf-8')), state, now,
                          os.environ.get('WEATHER_LATITUDE'), os.environ.get('WEATHER_LONGITUDE'))
    Path('/tmp/scribe-live-data.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    Path('/tmp/scribe-widget-state.json').write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
