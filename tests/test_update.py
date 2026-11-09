"""Host-side tests with a fake curl; no Kindle or network required."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PNG = ROOT / 'site' / 'dashboard.png'
UPDATER = ROOT / 'kindle' / 'update.sh'


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.us = self.base / 'us'
        self.dest = self.us / 'screensavers'
        self.dest.mkdir(parents=True)
        self.app = self.us / 'kindle-dashboard'
        self.app.mkdir()
        (self.app / 'config.sh').write_text("IMAGE_URL='https://example.com/dashboard.png'\nREDRAW_WHILE_ASLEEP=0\n")
        (self.app / 'secrets.sh').write_text("READ_TOKEN='" + 'a' * 64 + "'\n")
        tools = self.base / 'tools'
        tools.mkdir()
        curl = tools / 'curl'
        curl.write_text('''#!/bin/sh
out=''
while [ "$#" -gt 0 ]; do
  if [ "$1" = '--output' ]; then shift; out="$1"; fi
  shift
done
[ "${MOCK_CURL_FAIL:-0}" = '0' ] || exit 22
cp "$MOCK_PNG" "$out"
''')
        curl.chmod(0o755)
        self.env = os.environ.copy()
        self.env.update(KINDLE_ROOT=str(self.us),
                        DASHBOARD_LOCK=str(self.base / 'lock'),
                        PATH=str(tools) + os.pathsep + self.env['PATH'],
                        MOCK_PNG=str(PNG))

    def update(self, **kwargs):
        env = dict(self.env, **kwargs)
        return subprocess.run(['/bin/sh', str(UPDATER)], env=env, capture_output=True, text=True)

    def test_new_png(self):
        result = self.update()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.dest/'dashboard.png').read_bytes(), PNG.read_bytes())

    def test_network_failure_preserves_previous(self):
        (self.dest/'dashboard.png').write_bytes(b'OLD IMAGE')
        self.assertEqual(self.update(MOCK_CURL_FAIL='1').returncode, 0)
        self.assertEqual((self.dest/'dashboard.png').read_bytes(), b'OLD IMAGE')

    def test_invalid_image_preserves_previous(self):
        invalid = self.base/'bad.png'
        invalid.write_bytes(b'<html>' + b' ' * 3000)
        (self.dest/'dashboard.png').write_bytes(b'OLD IMAGE')
        self.assertNotEqual(self.update(MOCK_PNG=str(invalid)).returncode, 0)
        self.assertEqual((self.dest/'dashboard.png').read_bytes(), b'OLD IMAGE')

    def test_unchanged_no_backup(self):
        self.assertEqual(self.update().returncode, 0)
        self.assertEqual(self.update().returncode, 0)
        self.assertFalse((self.app/'previous-dashboard.png').exists())

    def test_wrong_dimensions_rejected(self):
        from PIL import Image
        bad = self.base/'wrong.png'
        Image.new('L', (600, 800), 255).save(bad)
        self.assertNotEqual(self.update(MOCK_PNG=str(bad)).returncode, 0)
        self.assertFalse((self.dest/'dashboard.png').exists())


if __name__ == '__main__':
    unittest.main()
