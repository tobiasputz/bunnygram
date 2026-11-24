"""Flash Bunnygram v5 on Freenove FNK0104B (landscape 320x240 + Railway)."""
import argparse
import getpass
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEVICE = ROOT / 'device'
LOCAL = ROOT / 'local_settings' / 'config.json'


def run(port, *args):
    cmd = [sys.executable, '-m', 'mpremote', 'connect', port, *args]
    print('Uploading:', args[-1].split('/')[-1] if args else 'command')
    subprocess.run(cmd, check=True)


def configure(force=False):
    old = {}
    if LOCAL.is_file():
        old = json.loads(LOCAL.read_text(encoding='utf-8'))
        if old.get('railway_url') and old.get('device_token') and not force:
            print('Using saved local settings (run --configure to change them).')
            return LOCAL
    print('Bunnygram v5 uses Railway HTTPS; no phone server is exposed on the board.')
    ssid = old.get('ssid') or input('2.4 GHz Wi-Fi SSID: ').strip()
    while not ssid:
        ssid = input('Wi-Fi name is required: ').strip()
    password = old.get('wifi_password') or getpass.getpass('Wi-Fi password (hidden): ')
    default_url = old.get('railway_url', '')
    url = input('Railway public HTTPS URL' + (' ['+default_url+']' if default_url else '') + ': ').strip() or default_url
    url = url.rstrip('/')
    if not url.startswith('https://') or '/' in url[8:] or len(url) > 260:
        raise SystemExit('Expected a simple HTTPS hostname such as https://bunnygram-production.up.railway.app')
    token = getpass.getpass('Railway DEVICE_TOKEN (paste secret; hidden)' + (' [Enter to keep saved]' if old.get('device_token') else '') + ': ')
    token = token or old.get('device_token', '')
    if len(token) < 32:
        raise SystemExit('DEVICE_TOKEN must be at least 32 characters, identical to Railway.')
    data = {'ssid': ssid, 'wifi_password': password,
            'railway_url': url, 'device_token': token}
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    LOCAL.write_text(json.dumps(data, indent=2), encoding='utf-8')
    try: LOCAL.chmod(0o600)
    except OSError: pass
    print('Saved private settings to local_settings/config.json (excluded from Git).')
    return LOCAL


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port', required=True, help='Board COM port, e.g. COM5 or /dev/ttyACM0')
    parser.add_argument('--configure', action='store_true', help='Edit Railway URL and token')
    parser.add_argument('--assets-only', action='store_true', help='Upload only six sprite files')
    args=parser.parse_args()
    from prepare_assets import convert
    convert()
    if not args.assets_only:
        config = configure(force=args.configure)
        for name in ('ili9341.py','companion.py','cloud.py'):
            run(args.port, 'fs','cp', str(DEVICE/name), ':'+name)
        run(args.port, 'fs','cp', str(DEVICE/'trust_roots.pem'), ':trust_roots.pem')
        run(args.port, 'fs','cp', str(config), ':config.json')
    try: run(args.port,'fs','mkdir',':assets')
    except subprocess.CalledProcessError: print('assets folder already exists (okay).')
    for pet in ('bunny','cat','fox','frog','cookie','bee'):
        run(args.port,'fs','cp',str(DEVICE/'assets'/(pet+'.bin')),':assets/'+pet+'.bin')
    if not args.assets_only:
        run(args.port,'fs','cp',str(DEVICE/'main.py'),':main.py')
    print('Done. Restart your Freenove ESP32-S3. Cloud address:',
          (json.loads(LOCAL.read_text()).get('railway_url','(assets only)') if LOCAL.is_file() else '(not saved)'))
    print('Serial logs: py -m mpremote connect',args.port,'repl')

if __name__=='__main__':main()
