# Private Kindle Scribe dashboard

GitHub Actions renders a grayscale landscape dashboard with live weather, Japanese practice, Japanese calendar information, agenda and tasks, and writes it to private Cloudflare KV at minute :55 each hour. The Kindle's authenticated client fetches it from a Cloudflare Worker. GitHub Pages is not used.

The renderer draws at 2480 × 1860 in landscape and rotates the finished image to 1860 × 2480 for the Scribe. `demo.json` contains sample data only; `site/dashboard.png` in the repository is an older sample, not the image served by the Worker. Actions renders a fresh image during each run.

## Private publishing

The workflow requires the `CF_API_TOKEN` GitHub secret and `CF_ACCOUNT_ID` and `CF_KV_NAMESPACE_ID` repository variables. The token should have only the Cloudflare KV write access needed for the namespace. The Worker must require the separate read token for `GET /dashboard.png`. Never publish personal calendar or task data to Pages or the repository.

## Kindle

The Kindle client is `kindle/update.sh`; install it as `/mnt/us/kindle-dashboard/update.sh`. Configure the Worker HTTPS URL and `REDRAW_WHILE_ASLEEP=0` in `/mnt/us/kindle-dashboard/config.sh`. Store only `READ_TOKEN='<64-character hex token>'` in the separate device-only `/mnt/us/kindle-dashboard/secrets.sh`; it must match the Worker's `READ_TOKEN`. This credential is readable by someone with access to the USB storage. Never commit or share it.

The authenticated client uses curl, validates PNG dimensions and size, and preserves the prior image on a failed fetch. Its log is `/mnt/us/kindle-dashboard/update.log`. The KOReader sleep-screen patch runs the client and displays `/mnt/us/screensavers/dashboard.png`. On this device it is configured for 07:15–22:15 local time, after the preceding :55 render. GitHub Actions may run late; in that case the previous image remains until the next fetch. The KOReader patch and its Wi-Fi wake handling are a locally adapted version of [koreader-live-sleepscreen](https://github.com/file99/koreader-live-sleepscreen); the 2022 Scribe remains an independently tested configuration, not an upstream guarantee.

The adapted patch source is `kindle/2-live-sleepscreen.lua` (upstream MIT licence in `kindle/LIVE-SLEEPSCREEN-LICENSE.txt`). It starts with downloads disabled unless `/mnt/us/live-sleepscreen.enablefetch` exists; `/mnt/us/live-sleepscreen.nowake` disables scheduled wakes. For testing only, `/mnt/us/live-sleepscreen.fasttest` schedules frequent wakes and should be removed after testing. Restart KOReader after editing the patch.

The older KindleCron and Chengandre scripts in this repository are legacy, not required for the KOReader setup. Do not enable a second sleep-screen renderer alongside KOReader's sleep screen.

## Local render

Install Pillow from `requirements.txt` and a Japanese font (Ubuntu: `fonts-noto-cjk`), then run `python render.py --data demo.json --output /tmp/dashboard.png`. The script also supports macOS system fonts for previews. Run `python -m unittest discover -s tests` for downloader checks.

## Live weather and Japanese

Actions needs the additional secrets `WEATHER_LATITUDE` and `WEATHER_LONGITUDE` (an approximate location is sufficient), and `DASHBOARD_IMAGE_URL` and `DASHBOARD_READ_TOKEN` for retrieving the previous private image. These values must not be put into source files or logs. The image URL must be HTTPS, with no redirect. The read token is separate from the Cloudflare API upload token.

Open-Meteo provides current and three-hourly forecast data without an API key for non-commercial use; attribution is shown on the dashboard. If it fails, the last successful forecast is recovered from metadata in the private image. After three hours, the display shows when that forecast was saved. If no previous forecast is available, it shows weather unavailable. Only weather and Japanese widget state is stored there; do not add personal events, task details or credentials to this metadata.

The kanji and example words come from kanjiapi.dev and the EDRDG KANJIDIC/JMdict dictionaries. Grades 4–6 and 8 are Jōyō kanji; the 440 characters taught in grades 1–3 are excluded. A date-seeded selection keeps the same character for a day. The previous character is kept if the dictionary API fails. No LLM or preprocessed dataset is needed.

## Calendar and tasks

Calendar and Notion integrations are optional and read-only. The Google Calendar client accepts an OAuth desktop-client ID, client secret and refresh token as JSON in the `GOOGLE_CALENDAR_CREDENTIALS` Actions secret, and a JSON array of calendar IDs in `GOOGLE_CALENDAR_IDS`. It reads each selected calendar separately, expands recurring events, deduplicates shared events and displays up to four events for the current Tokyo day. API keys alone cannot access private calendar data. For personal External OAuth applications in Testing mode, Google may expire refresh tokens after seven days; use the appropriate Google OAuth configuration and be prepared to reauthorize.

The Notion connection uses the `NOTION_TOKEN` and `NOTION_DATA_SOURCE_ID` Actions secrets. It reads the selected Tasks data source, excludes Done and Dropped items, and shows five open tasks, ordered by priority (High, then Normal) then due date. It requests read access only; no task contents or calendar events are written to logs, source files, shared caches or PNG metadata. The rendered image itself contains any displayed private information and must remain behind the authenticated Worker. Failed calendar or Notion requests produce an unavailable notice instead of displaying stale or sample information.

### Shared Google calendars

Include the primary and shared calendar IDs together in the JSON array in `GOOGLE_CALENDAR_IDS`. The authorizing Google account must have permission to read every selected calendar. Each calendar is queried separately: events visible in Google's interface are not automatically part of the primary calendar's API response. The agenda combines all configured sources before choosing the first four events for the Tokyo day. Duplicate copies with the same iCalendar UID and occurrence start are displayed once; distinct events with the same title remain separate.

### Optional Outlook / Microsoft 365 calendar

If the calendar owner's organization permits external calendar publishing, obtain its HTTPS **ICS subscription link** from Outlook on the web under Settings → Calendar → Shared calendars → Publish a calendar. Choose the minimum detail level needed (availability only produces Busy entries). Publishing grants access to anyone holding that URL, so only use it when the owner and the employer permit this disclosure. Store it directly as an encrypted repository Actions secret named `OUTLOOK_ICS_URLS`, containing the subscription URL directly, one URL per line, or a JSON array of URLs. Do not paste real links into source code, issues, chat, or workflow inputs. No Microsoft password is needed for this method.

The hourly renderer downloads the feed directly with a timeout and size limit; redirects are refused. It expands recurrence rules and exceptions, handles all-day and overlapping events, converts timed entries to Tokyo time, and combines them with Google events. Private/confidential ICS entries display as Busy. Floating event times without a time zone are interpreted as Tokyo time. A failed provider does not remove events already loaded from another provider, and the agenda displays a partial-outage notice. Feed URLs and events are never saved in caches or image metadata. The provider's own publication delay may still affect freshness.

If publishing is blocked or a bearer-link feed is unsuitable for work data, use delegated Microsoft Graph read access instead. That requires a separate Microsoft app registration/sign-in and any employer consent requirements; this repository does not yet implement Graph authentication. Do not relax the employer's sharing policy to enable a feed.
