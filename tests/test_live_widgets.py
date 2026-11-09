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

    @patch('live_widgets.request')
    def test_private_image_state_round_trip(self, request):
        image = Image.new('L', (1860,2480)); info = PngImagePlugin.PngInfo()
        info.add_text(live.STATE_KEY, json.dumps({'weather': self.weather}))
        data = BytesIO(); image.save(data, format='PNG', pnginfo=info); request.return_value = data.getvalue()
        self.assertEqual(live.previous_state('https://example.test/dashboard.png', 'readtoken')['weather'], self.weather)
        self.assertEqual(request.call_args.args[1]['Authorization'], 'Bearer readtoken')

if __name__ == '__main__': unittest.main()
