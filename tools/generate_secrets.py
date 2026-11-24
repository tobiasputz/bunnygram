"""Run locally. Copy secrets to Railway Variables; never commit them to Git."""
import secrets
print('DEVICE_TOKEN=' + secrets.token_hex(32))
print('SESSION_SECRET=' + secrets.token_hex(32))
print('OWNER_PASSWORD=' + secrets.token_urlsafe(24))
print('COMPANION_PASSWORD=' + secrets.token_urlsafe(24))
