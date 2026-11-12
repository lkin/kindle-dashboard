import json
import unittest
from datetime import datetime, timedelta
from io import BytesIO
from unittest.mock import patch
from PIL import Image, PngImagePlugin
import live_widgets as live

class WidgetTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 9, 15, 5, tzinfo=live.JST)
        self.weather = {'display_temperature': '19°C / 66°F', 'condition': 'Clear sky', 'high_low': '', 'forecast': [], 'fetched_at': (self.now-timedelta(hours=4)).isoformat()}
        self.kanji = {'character': '学', 'meaning': 'study', 'readings': '', 'examples': [], 'date': '2026-11-09'}
        self.koyomi_patch = patch('live_widgets.koyomi_data', side_effect=OSError('offline'))
        self.koyomi_patch.start()
        self.addCleanup(self.koyomi_patch.stop)

    @patch('live_widgets.get_json')
    def test_koyomi_date_fields_and_optional_values(self, get_json):
        get_json.return_value = {'datelist': {'2026-11-09': {'inreki': '霜月', 'eto': '午',
                            'sekki': '', 'rokuyou': '先勝', 'holiday': None}}}
        # setUp patches the network-facing function; restore it for this focused test.
        self.koyomi_patch.stop()
        result = live.koyomi_data(self.now)
        self.assertEqual((result['date'], result['inreki'], result['holiday']), ('2026-11-09', '霜月', ''))

    @patch('live_widgets.kanji_data', side_effect=OSError('offline'))
    @patch('live_widgets.weather_data', side_effect=OSError('offline'))
    def test_koyomi_cache_only_used_for_matching_date(self, *_):
        saved = {'date': '2026-11-09', 'inreki': '霜月', 'eto': '午', 'rokuyou': '先勝'}
        out, state = live.build({}, {'kanji': self.kanji, 'koyomi': saved}, self.now, '1', '2')
        self.assertEqual(out['koyomi'], saved)
        self.assertEqual(state['koyomi'], saved)
        out, state = live.build({}, {'kanji': self.kanji, 'koyomi': saved}, self.now + timedelta(days=1), '1', '2')
        self.assertIsNone(out['koyomi'])
        self.assertNotIn('koyomi', state)

    @patch('live_widgets.weather_data', side_effect=OSError('offline'))
    def test_stale_weather_and_saved_kanji(self, _):
        out, state = live.build({}, {'weather': self.weather, 'kanji': self.kanji}, self.now, '1', '2')
        self.assertEqual(out['weather']['display_temperature'], self.weather['display_temperature'])
        self.assertIn('Forecast saved', out['weather']['status'])
        self.assertEqual(state['weather']['fetched_at'], self.weather['fetched_at'])
        self.assertEqual(out['kanji']['character'], '学')

    @patch('live_widgets.weather_data', side_effect=OSError('offline'))
    @patch('live_widgets.kanji_data', side_effect=OSError('offline'))
    def test_no_saved_data_is_not_fake_weather(self, *_):
        out, _ = live.build({}, {}, self.now, '1', '2')
        self.assertEqual(out['weather']['condition'], 'Weather unavailable')
        self.assertEqual(out['kanji']['meaning'], 'Dictionary unavailable')

    @patch('live_widgets.OPENER.open')
    def test_notion_prioritizes_open_tasks_without_leaking_into_state(self, open_mock):
        def row(name, status, priority, due):
            return {'properties': {'Task name': {'title': [{'plain_text': name}]},
                    'Status': {'status': {'name': status}},
                    'Priority': {'select': {'name': priority}},
                    'Due': {'date': {'start': due}}}}
        payload = {'results': [row('Low', 'Not started', 'Low', '2026-11-09'),
                    row('Normal later', 'Not started', 'Normal', '2026-11-12'),
                    row('Normal earlier', 'Not started', 'normal', '2026-11-10'),
                    row('High later', 'Not started', 'High', '2026-11-20'),
                    row('Urgent', 'In progress', 'High', '2026-11-15'),
                    row('Other', 'Not started', None, '2026-11-01'),
                    row('Done', 'Done', 'High', '2026-11-01')], 'has_more': False}
        open_mock.return_value.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        self.assertEqual(live.notion_tasks('token', 'b94d217e-c3e7-4ea2-a705-6df1674278f8'),
                         ['Urgent', 'High later', 'Normal earlier', 'Normal later', 'Low'])

    @patch('live_widgets.request')
    @patch('live_widgets.OPENER.open')
    def test_calendar_combines_and_deduplicates(self, token_open, request):
        token_open.return_value.__enter__.return_value.read.return_value = b'{"access_token":"token"}'
        event = {'iCalUID': 'shared', 'start': {'dateTime': '2026-11-09T09:00:00+09:00'}, 'summary': 'Meeting'}
        request.side_effect = [json.dumps({'items': [event]}).encode(), json.dumps({'items': [event, {
            'iCalUID': 'other', 'start': {'date': '2026-11-09'}, 'summary': 'Holiday'}]}).encode()]
        creds = json.dumps({'client_id':'id','client_secret':'secret','refresh_token':'refresh'})
        result = live.google_events(creds, json.dumps(['a','b']), self.now)
        self.assertEqual([x['title'] for x in result], ['Holiday','Meeting'])
        self.assertEqual(result[0]['time'], 'All day')
        self.assertEqual(request.call_count, 2)

    @patch('live_widgets.request')
    def test_private_image_state_round_trip(self, request):
        image = Image.new('L', (1860,2480)); info = PngImagePlugin.PngInfo()
        info.add_text(live.STATE_KEY, json.dumps({'weather': self.weather}))
        data = BytesIO(); image.save(data, format='PNG', pnginfo=info); request.return_value = data.getvalue()
        self.assertEqual(live.previous_state('https://example.test/dashboard.png', 'readtoken')['weather'], self.weather)
        self.assertEqual(request.call_args.args[1]['Authorization'], 'Bearer readtoken')

if __name__ == '__main__': unittest.main()
