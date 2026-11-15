import json
import os
import unittest
from datetime import datetime
from unittest.mock import patch

import live_widgets as live


class CalendarTests(unittest.TestCase):
    now = datetime(2026, 11, 15, 12, tzinfo=live.JST)

    @patch('live_widgets.request')
    def test_recurrence_overrides_exclusions_and_private_events(self, request):
        request.return_value = b'''BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Scribe Test//EN
BEGIN:VEVENT
UID:repeat
DTSTART:20261114T010000Z
DTEND:20261114T020000Z
RRULE:FREQ=DAILY;COUNT=4
EXDATE:20261116T010000Z
SUMMARY:Original
END:VEVENT
BEGIN:VEVENT
UID:repeat
RECURRENCE-ID:20261115T010000Z
DTSTART:20261115T030000Z
DTEND:20261115T040000Z
SUMMARY:Moved meeting
END:VEVENT
BEGIN:VEVENT
UID:holiday
DTSTART;VALUE=DATE:20261115
DTEND;VALUE=DATE:20261116
SUMMARY:Day off
END:VEVENT
BEGIN:VEVENT
UID:private
DTSTART:20261115T040000Z
DTEND:20261115T050000Z
CLASS:PRIVATE
SUMMARY:Do not display this
END:VEVENT
BEGIN:VEVENT
UID:cancelled
DTSTART:20261115T060000Z
DTEND:20261115T070000Z
STATUS:CANCELLED
SUMMARY:Cancelled
END:VEVENT
END:VCALENDAR
'''
        events = live.outlook_events(json.dumps(['https://example.test/feed.ics']), self.now)
        result = live.merge_events(events)
        self.assertEqual(result, [{'time': 'All day', 'title': 'Day off'},
                                  {'time': '12:00', 'title': 'Moved meeting'},
                                  {'time': '13:00', 'title': 'Busy'}])
        tomorrow = self.now.replace(day=16)
        self.assertEqual(live.outlook_events(json.dumps(['https://example.test/feed.ics']), tomorrow), [])

    @patch('live_widgets.request')
    def test_tokyo_day_boundary_and_overnight_overlap(self, request):
        request.return_value = b'''BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:overlap
DTSTART;TZID=America/New_York:20261114T080000
DTEND;TZID=America/New_York:20261114T120000
SUMMARY:Overnight
END:VEVENT
BEGIN:VEVENT
UID:outside
DTSTART:20261115T150000Z
DTEND:20261115T160000Z
SUMMARY:Tomorrow
END:VEVENT
END:VCALENDAR
'''
        result = live.merge_events(live.outlook_events('["https://example.test/feed.ics"]', self.now))
        self.assertEqual(result, [{'time': 'Ongoing', 'title': 'Overnight'}])

    def test_merge_normalizes_time_and_limits_after_combining(self):
        events = [{'time': f'{n:02}:00', 'title': f'Event {n}', '_uid': str(n),
                   '_start': f'2026-11-15T{n:02}:00:00+09:00',
                   '_sort': f'2026-11-15T{n:02}:00:00+09:00'} for n in range(10, 15)]
        events.append({**events[0], '_start': '2026-11-15T01:00:00Z'})
        events.append({'time': '09:00', 'title': 'Outlook first', '_uid': 'outlook',
                       '_start': '2026-11-15T09:00:00+09:00', '_sort': '2026-11-15T09:00:00+09:00'})
        self.assertEqual([e['title'] for e in live.merge_events(events)],
                         ['Outlook first', 'Event 10', 'Event 11', 'Event 12'])

    @patch.dict(os.environ, {'OUTLOOK_ICS_URLS': '["https://example.test/secret"]'})
    @patch('live_widgets.google_events')
    @patch('live_widgets.outlook_events', side_effect=OSError('private URL must not be logged'))
    def test_provider_failure_keeps_other_events(self, outlook, google):
        google.return_value = [{'time': '10:00', 'title': 'Google', '_sort': '2026-11-15T10:00:00+09:00',
                                '_start': '2026-11-15T10:00:00+09:00', '_uid': 'g'}]
        events, status = live.agenda_data(self.now)
        self.assertEqual(events, [{'time': '10:00', 'title': 'Google'}])
        self.assertEqual(status, 'SOME CALENDARS UNAVAILABLE')

    @patch('live_widgets.request')
    def test_feed_requires_https_and_valid_list(self, request):
        for value in ('[]', '{}', '["http://example.test/feed"]'):
            with self.assertRaises(ValueError): live.outlook_events(value, self.now)
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
