# Bunnygram v5 — Railway + Landscape Freenove ESP32-S3

A USB-powered **floating pixel-art companion**, without Tamagotchi care mechanics or scenery. **Six pets:** bunny, cat, fox, frog, chocolate-chip cookie, bee. **Freenove FNK0104B, 2.8-inch IPS 240×320 ILI9341 display**, set to **landscape 320×240** by default. Your phone controls the display from anywhere through Railway. The display has no phone-pairing buttons or exposed local HTTP service when Railway is configured.

**Important:** This repository is *built and tested locally*, not deployed to your Railway account or validated on an actual FNK0104B board. Check the full end-to-end behavior before giving the gift. Remote firmware updates (OTA) and automatic sprite downloads are **not yet included**.

## Folder overview

- `railway/` — FastAPI app, mobile browser dashboard, HTTPS endpoints, Postgres queue, Dockerfile.
- `device/` — MicroPython, ILI9341 SPI driver, six pets, 84 RGB565 sprite frames, verified-TLS Railway client.
- `desktop/` — **unchanged original desktop Pygame prototype** and editable sprites. You can keep running `python desktop/run.py` for normal-Python local tests.
- `tools/railway_desktop_preview.py` — **new desktop display simulator connected to your real Railway backend**, using the actual MicroPython companion rules and binary sprites. Useful before you buy/flash hardware.
- `tools/deploy.py` — uploads the app over USB to the already-flashed ESP32-S3.
- `tools/prepare_assets.py` — regenerates 84 ESP32 sprite frames from your PNG artwork.
- `tools/prepare_roots.py` — updates the small trusted CA root bundle from certifi's Mozilla root store.
- `tools/generate_secrets.py` — generates the Railway passwords and device tokens.
- `tests/` — automatic source, relay, auth, replay, and display checks.

## 1 — Install Python tools on your computer

Extract the ZIP, open PowerShell **inside this folder**, and run:

```powershell
py -m pip install -r requirements.txt
py -m unittest discover -s tests -v
```

Python 3.10+ is recommended locally. The Railway Docker image uses Python 3.12.

## 2 — Create strong secrets for Railway

```powershell
py tools/generate_secrets.py
```

You receive four **different** randomly generated values. Copy them to your password manager:

- `DEVICE_TOKEN`: shared *only* between the ESP32 and Railway server; **never put in a webpage**.
- `SESSION_SECRET`: signs private browser session cookies; **server only**.
- `OWNER_PASSWORD`: your own phone password; **can send letters** and control pets.
- `COMPANION_PASSWORD`: her phone password; **can switch pets, react, adjust settings, and read letters**, but cannot send new letters.

**Do not commit these values, Wi-Fi passwords, or `local_settings/` to GitHub.** The `.gitignore` covers local settings. The `railway/.env.example` contains placeholders only.

## 3 — Upload this repository to GitHub

Create an empty **private** GitHub repository (e.g. `bunnygram`). From inside the extracted project folder:

```powershell
git init
git add .
git commit -m "Bunnygram v5: Railway + landscape"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/bunnygram.git
git push -u origin main
```

If your GitHub repo already exists, replace the remote step with your existing repository; you do not need a new repo. Check `git status` before pushing to verify that `local_settings` and passwords are not included.

## 4 — Deploy the online server to Railway

1. In **Railway**, choose **New Project → Deploy from GitHub Repo** and select your Bunnygram repository.
2. Open the **Bunnygram web service settings**. Set **Root Directory** to `/railway`. Railway will find `railway/Dockerfile` as the service's Dockerfile in that root. Railway runs one Uvicorn worker and binds to its provided `$PORT`.
3. In the same Railway project, choose **+ New → Database → PostgreSQL** (wording may vary). Wait until the database service is ready.
4. In the **Bunnygram web service → Variables** set:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` if database service is named `Postgres` (adjust the service name if different) |
   | `OWNER_PASSWORD` | generated owner password |
   | `COMPANION_PASSWORD` | generated companion password |
   | `DEVICE_TOKEN` | generated device token |
   | `SESSION_SECRET` | generated session secret |
   | `SECURE_COOKIES` | `1` |

5. Go to the web service's **Settings → Networking → Public Networking → Generate Domain**. Copy the HTTPS URL, e.g. `https://bunnygram-production.up.railway.app`.
6. Set **`PUBLIC_ORIGIN`** on the web service to **exactly that URL**, with `https://` and **no trailing slash**.
7. Apply/deploy the pending changes. If an initial deployment failed while your variables or database were missing, **redeploy** the web service after setting them.
8. Check `https://YOUR-DOMAIN/health` — it should show `{"ok":true,"service":"bunnygram-relay"}`.
9. Open your public Railway URL on your phone. Sign in with `OWNER_PASSWORD`. The dashboard should show **Offline** until your ESP32 (or desktop cloud simulator) first connects.

**Railway costs:** A web service **and** a PostgreSQL service both consume resources. Review the current usage/pricing in your Railway dashboard; do not assume the hosting is free.

The database persists commands and the last device state between app restarts/redeployments. The ESP32 only **pulls** commands; no external access to its local IP or port forwarding is needed.

## 5 — Test Railway with *normal Python* before touching the board

Install the tools as in step 1. Run the device-config wizard once when you deploy, or create `local_settings/config.json` manually with the structure below. This file stays on your own computer:

```json
{
  "ssid": "YOUR_HOME_2.4_GHZ_WIFI",
  "wifi_password": "YOUR_WIFI_PASSWORD",
  "railway_url": "https://YOUR-DOMAIN.up.railway.app",
  "device_token": "SAME_DEVICE_TOKEN_AS_RAILWAY"
}
```

Now launch the **new** Railway-connected desktop preview:

```powershell
py tools/railway_desktop_preview.py
```

Open your Railway dashboard on your phone; switch to the bee or chocolate-chip cookie, tap Wave/Dance, or send a letter. The desktop window will show the selected companion. The **actual display graphics** use the same 32×32 frame data and animation rules as the ESP32.

To preview without internet, run `py tools/railway_desktop_preview.py --offline`.

**Only run ONE connected display client at a time.** Turn off the physical ESP32 when using the desktop Railway preview; both would otherwise consume the same commands.

The original richer desktop app is still available:

```powershell
py desktop/run.py
```

That old desktop app retains its *local-network* controller; the **new** `tools/railway_desktop_preview.py` is the one that tests the Railway connection.

## 6 — Flash Bunnygram onto the Freenove board

Your device is the **Freenove ESP32-S3 FNK0104B 2.8-inch IPS (ILI9341)**. It **already includes** its LCD, Wi-Fi and CPU. No display wiring or physical input buttons are needed.

If you have already installed a compatible **ESP32_GENERIC_S3-SPIRAM_OCT MicroPython** firmware for Bunnygram v4, **you can skip erasing/flashing MicroPython again**. Keep the board plugged in over USB with a *data cable*.

If this is a new board that still has Freenove's example firmware installed:

1. Download the latest **ESP32_GENERIC_S3, Support for Octal-SPIRAM** stable `.bin` from https://micropython.org/download/ESP32_GENERIC_S3/ (verify it is the correct variant).
2. Identify your COM port: `py -m serial.tools.list_ports`.
3. Put the board into download mode if necessary: **hold BOOT, tap RESET, release BOOT**.
4. Erase existing flash (this deletes the original demo and any prior saved data):

   ```powershell
   py -m esptool --chip esp32s3 --port COM5 erase-flash
   ```

5. Flash your downloaded firmware (substitute its **actual** filename; do **not** blindly reuse an old version number):

   ```powershell
   py -m esptool --chip esp32s3 --port COM5 --baud 460800 write-flash 0 YOUR_ACTUAL_FIRMWARE_FILENAME.bin
   ```

6. Then install Bunnygram:

   ```powershell
   py tools/deploy.py --port COM5
   ```

   The wizard asks for your Wi-Fi SSID/password, Railway HTTPS URL and the exact Railway `DEVICE_TOKEN`. It writes a local ignored config file and uploads all 6 pets and app code. If you've set up `local_settings/config.json` already, it reuses it.

7. Press RESET or power-cycle via the **USB-C power cable**. The pet should float on an otherwise **pure black, landscape 320×240 screen**. Check serial logs if necessary:

   ```powershell
   py -m mpremote connect COM5 repl
   ```

   Press Ctrl+C to interrupt the app if debugging. After Wi-Fi and NTP time sync, cloud polling should start. The device reports to Railway roughly every 10 seconds. If Wi-Fi/cloud fails, animations continue locally and queued commands wait online.

8. From anywhere, open the Railway HTTPS URL on your phone and sign in. Try switching to **Cookie**, then **Bee**, and sending a letter. Commands show as *queued* until the board receives them.

**Important first-run limitation:** MicroPython on the ESP32-S3 must support `ssl.SSLContext`, `ssl.CERT_REQUIRED`, `load_verify_locations(cadata=...)`, and SNI/hostname checks. The certificate CA bundle is included. If the Railway TLS chain is not anchored by one of those trusted roots, the client **intentionally refuses** to connect instead of disabling certificate verification. See troubleshooting below. Actual MicroPython TLS and LCD behavior must be tested on the physical board.

## 7 — Adjust the floating reflection from the phone

The new default is **`rotation=1` => 320×240 landscape**. Once, on upgrade from v4, the app migrates its old portrait state to landscape **without deleting letters or pet names**. You can later switch to `rotation=3` for upside-down landscape, or choose portrait if desired. Rotation + horizontal/vertical mirroring are independent controls; use them to correct the Pepper's Ghost reflection.

**Screen size:** 2.8 inches diagonally (~71 mm); reflection is the same optical size as the displayed image. On a small reflector, try `scale=4` (128px sprite) or `scale=5` (160px sprite). The LCD emits light from its black pixels/backlight, so a physically dark enclosure helps make the character seem freestanding.

## 8 — Replace/edit sprites

Replace any of the PNGs in `desktop/assets/{pet}/{frame}.png`, keeping the original filenames. Then:

```powershell
py tools/prepare_assets.py
py tools/deploy.py --port COM5 --assets-only
```

If you change Python source, use the normal `deploy.py` command instead. All 84 existing sprite frames are included; `tests/test_freenove.py` checks their shape/size.

## Troubleshooting

| Symptom | Check |
|---|---|
| Railway page shows Offline | Check deployment `/health`, device Wi-Fi, NTP, and the serial console; backend will show Offline before the first device sync |
| Railway backend crashes at startup | Ensure **all six required secrets/URLs** plus `DATABASE_URL` are set, and the Postgres service is reachable |
| Login says wrong origin | `PUBLIC_ORIGIN` must exactly match the displayed HTTPS hostname; avoid custom redirects/extra trailing slash |
| Device says TLS certificate error | Correct the ESP32 clock with NTP; verify Railway domain; run `py tools/prepare_roots.py` and re-upload CA bundle, or add the *correct trusted CA root* to the bundle. **Never disable verification.** |
| Nothing on LCD | Check correct FNK0104B vs another Freenove variant, backlight settings, USB power, and rotation |
| Wrong orientation | In Railway dashboard select 90° or 270° landscape (`rotation=1` or `3`) |
| Letter appears twice | Use just one connected display client and avoid erasing persistent state; command cursor saves with each action |
| Can't send letters from her login | By design, only `OWNER_PASSWORD` has permission to send letters |
| Desktop simulator seems disconnected | Make sure you've configured `local_settings/config.json` and you're running **railway_desktop_preview.py**, not the older desktop app |
| Old installer credentials | Run `py tools/deploy.py --port COM5 --configure` to update the local board settings |

## Security and current limitations

- Phone sessions are signed, **HttpOnly**, **Secure**, **SameSite=Strict** cookies (not stored in browser localStorage). Browser changes require JSON and a matching Origin. A basic login-attempt limit is included.
- Only the owner role may send letters. The companion role can switch pets and interact.
- The device uses a **separate high-entropy bearer token**; it never receives either phone password or `SESSION_SECRET`.
- The ESP32 **initiates** HTTPS connections to Railway; no local HTTP server is started in cloud mode, no router configuration, and no device IP exposure.
- The cloud code requires **valid TLS CA certificates and hostname validation**; it fails closed if verification cannot be configured. Test with your selected MicroPython build.
- PostgreSQL stores device state and ordered commands. The device saves a processed-command cursor in its persistent state, providing retry/reconnect deduplication while that state survives.
- **Not yet implemented:** internet OTA firmware updates, remotely uploaded image packs, push notifications, multiple independent display devices, and professional security auditing. Long passwords, backups, and Railway account 2FA remain your responsibility.

## Verified references

- Freenove FNK0104B driver / specs: https://docs.freenove.com/projects/fnk0104/en/latest/fnk0104/codes/MAIN/Freenove_ESP32S3_Display.html
- Railway GitHub deploy & domains: https://docs.railway.com/quick-start and https://docs.railway.com/networking/public-networking
- Railway Postgres / variables: https://docs.railway.com/databases/postgresql and https://docs.railway.com/variables
- MicroPython TLS certificate validation: https://docs.micropython.org/en/latest/library/ssl.html

## GitHub checks

The included `.github/workflows/tests.yml` runs source, API, command-queue and driver-mock tests on push/pull request. A green result **does not replace** testing the actual Freenove hardware, MicroPython TLS or real Railway deployment.
