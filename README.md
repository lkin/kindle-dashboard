# Private Kindle Scribe dashboard

GitHub Actions renders a sample grayscale landscape dashboard and writes it to private Cloudflare KV at minute :55 each hour. The Kindle's authenticated client fetches it from a Cloudflare Worker. GitHub Pages is not used. The current weather, kanji, agenda and tasks are sample data, not live integrations.

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

The Notion connection uses the `NOTION_TOKEN` and `NOTION_DATA_SOURCE_ID` Actions secrets. It reads the selected Tasks data source, excludes Done and Dropped items, and shows two open tasks, ordered by priority then due date. It requests read access only; no task contents or calendar events are written to logs, source files, shared caches or PNG metadata. The rendered image itself contains any displayed private information and must remain behind the authenticated Worker. Failed calendar or Notion requests produce an unavailable notice instead of displaying stale or sample information.
