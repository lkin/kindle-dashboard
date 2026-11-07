# Kindle Scribe native sleep dashboard (prototype)

A light integration for the **2022 Kindle Scribe**, intended to preserve the
stock reader and handwriting experience. Rendering happens on GitHub Actions,
not on the Kindle. Uses **Chengandre Custom Screensaver v0.6.0**, which you
already have working, plus optional **KindleCron v0.2.0**.

**Status:** The renderer and downloader are locally tested. Hourly RTC waking,
Wi-Fi reconnection, and framebuffer redraw on your Scribe are **not yet
hardware-validated**. No automatic network wake-up/power-button emulation is
included, by design. The scheduled job will skip safely when offline.

## Files

- `render.py` and `demo.json`: render 1860×2480 grayscale PNG with sample data.
- `.github/workflows/publish.yml`: GitHub Actions hourly Pages deployment.
- `site/dashboard.png`: generated during rendering, not committed.
- `kindle/config.sh`: URL and direct-redraw switch.
- `kindle/update.sh`: 4 KB shell client; bounded HTTPS fetch, PNG checks, atomic
  replacement, previous-image backup, and conditional redraw.
- `kindle/install-schedule.sh`: register daytime hourly KindleCron job.
- `kindle/disable-schedule.sh`: remove just our job.
- `kindle/activate-dashboard-only.sh`: *optional* move other custom images into
  a timestamped backup folder; does not delete them.

## Step A: publish demo image on GitHub Pages

1. Create **your own repository** and upload these files, preserving the
   `.github/workflows/publish.yml` path. Do **not** upload personal calendar data.
2. On GitHub, go to **Settings → Pages → Build and deployment → Source:
   GitHub Actions**.
3. On the **Actions** tab, run **Publish Scribe dashboard → Run workflow** once.
   Scheduled runs follow hourly at minute 05 (UTC), subject to GitHub delays.
4. Verify the public URL in your browser:
   `https://YOUR-USERNAME.github.io/YOUR-REPO/dashboard.png`
5. Edit `kindle/config.sh`, replacing the example `IMAGE_URL` with that URL.

The published file is **publicly accessible**. It uses sample appointments and
sample weather deliberately. Do not add private calendar entries before setting
up authenticated delivery in place of public Pages.

You can render locally with `pip install -r requirements.txt && python render.py`.

## Step B: install the Kindle client (nothing changes the upstream daemon)

With the Kindle connected over USB, copy the **contents of `kindle/`** to a
new folder named `kindle-dashboard` at the root of the Kindle drive, i.e. on
the Kindle they should be `/mnt/us/kindle-dashboard/update.sh` etc. Do *not*
overwrite `/mnt/us/extensions/custom-screensaver/`.

Disconnect USB, open kterm or SSH on the Kindle, and run while awake and
connected to Wi-Fi:

```sh
/bin/sh /mnt/us/kindle-dashboard/update.sh
cat /mnt/us/kindle-dashboard/update.log
ls -l /mnt/us/screensavers/dashboard.png
```

It should report `updated` and create a PNG. Press the Kindle power button:
Chengandre should now show the dashboard **sometimes** if you still have other
images in `/mnt/us/screensavers` and its mode is shuffle. To make it the **only**
image, after confirming the download works, run:

```sh
/bin/sh /mnt/us/kindle-dashboard/activate-dashboard-only.sh
```

This moves other `.png`, `.jpg`, `.jpeg` files to `/mnt/us/screensavers-backup-<date>/`
without deleting them. The existing Chengandre Scriptlet stays enabled.
To restore your images, move the backed-up files back to `/mnt/us/screensavers/`.

## Step C: optional RTC schedule

1. Download and inspect the official [KindleCron v0.2.0](https://github.com/lennardollesch/KindleCron/releases/tag/v0.2.0)
   release, then copy its `kron/` folder to the Kindle drive root. Ensure
   `/mnt/us/kron/kron` exists and is executable. Its optional `extensions/`
   folder adds KUAL controls.
2. Start the KindleCron daemon with KUAL → KindleCron → Start, or in a terminal:

   ```sh
   /mnt/us/kron/kron daemon >/mnt/us/kron/dashboard-daemon.log 2>&1 </dev/null &
   ```

   No boot-time service is installed by this bundle. If kron stops after a
   restart, start it again.
3. Register the job:

   ```sh
   /bin/sh /mnt/us/kindle-dashboard/install-schedule.sh
   /mnt/us/kron/kron list
   ```

The schedule runs `update.sh` at **07:15–22:15** device-local time, hourly,
with a **90-second maximum job timeout**. This daytime window is intentional:
it leaves a long uninterrupted overnight hibernation window. Use 24-hour
`15 * * * *` if you prefer, after verifying RTC behavior and battery life.
GitHub renders at :05. Actual deployments may be delayed.

### Crucial limitation: 5.18.6 Wi-Fi while asleep

On some modern firmware, waking by RTC leaves the device in `screenSaver`
state, where **Wi-Fi will not reconnect**. This is documented for firmware
5.18.6 in `koreader-live-sleepscreen`. So **KindleCron may wake and execute the
job without network access**. The downloader will log a harmless failure and
retain the existing image. When Wi-Fi does work, it will download and may redraw
immediately.

To permit a direct redraw while sleeping, `update.sh` demands **all** of:
- `REDRAW_WHILE_ASLEEP=1` in your config;
- Kindle `powerd` explicitly reports `screenSaver`;
- Chengandre's current shield PID exists **and is alive**;
- Chengandre's original `screensaver_draw` binary exists.

No redraw is attempted when the reader is active. The renderer is *not* modified.
A scheduled direct redraw may still need a hardware-specific adjustment.

**Do not** add an automatic power-state change yet: the stock `outOfScreenSaver`
event can make Chengandre remove its shield, unexpectedly exposing the reader.
A fully unattended reliable Wi-Fi association dance needs a tested extension
that coordinates with Chengandre's event loop. This prototype purposely does
not promise that behavior.

## Diagnostics and rollback

To check a run:

```sh
tail -30 /mnt/us/kindle-dashboard/update.log
/mnt/us/kron/kron list
tail -30 /mnt/us/kron/kron.log
lipc-get-prop com.lab126.powerd state
```

To remove only the schedule:

```sh
/bin/sh /mnt/us/kindle-dashboard/disable-schedule.sh
```

Then remove `/mnt/us/kindle-dashboard/` if desired. The scripts never alter
Chengandre's binaries, book/note data, or Amazon system files. The only
non-temporary new screensaver file is `/mnt/us/screensavers/dashboard.png`;
if `activate-dashboard-only.sh` was run, the other images remain in the
separate timestamped backup folder. Uninstall KindleCron separately if desired.
If the display behaves strangely, rebooting disables Chengandre until its
Scriptlet is enabled again.

## Future integration

Replace `demo.json` with sanitized data on a private GitHub Actions runner, and
publish through an authenticated endpoint if actual calendar data is shown.
Keep secret tokens out of the public image URL and logs. The native Kindle
client still only has to fetch one PNG.

## References

- https://github.com/chengandre/kindle-custom-screensaver
- https://github.com/lennardollesch/KindleCron
- https://github.com/file99/koreader-live-sleepscreen
- https://github.com/shenliucn-prog/daypane
