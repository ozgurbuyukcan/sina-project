"""Windows-friendly localhost HTTP launch with freshly generated bearer token."""
import secrets
from pathlib import Path
from live_gateway import serve_http

if __name__ == '__main__':
    token = secrets.token_urlsafe(32)
    print('SINA loopback-only gateway: http://127.0.0.1:8765/v1/measurements', flush=True)
    print('Source: field-http-01', flush=True)
    print('Copy this token into your local HTTP client:', flush=True)
    print(token, flush=True)
    print('Keep this token private. Ctrl+C stops the gateway.', flush=True)
    serve_http(Path(__file__).resolve().parent/'user_data'/'live_measurements.sqlite3',
               'field-http-01', token, 8765)
