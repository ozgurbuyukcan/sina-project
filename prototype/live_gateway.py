"""Serial and loopback HTTP sensor gateway. Both use the same validated SQLite ingest.

No control commands are sent to pumps, valves or hardware.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import sys
import time

from sina.live import (MAX_PACKET_BYTES, ingest_packet, live_connect,
                       log_ingestion_error, parse_sensor_line, validate_source_id, register_source, log_gateway_event)

ROOT = Path(__file__).resolve().parent
DEFAULT_DB = ROOT / 'user_data' / 'live_measurements.sqlite3'


def serve_http(db_path: Path, source_id: str, token: str, port: int) -> None:
    if len(token) < 16:
        raise SystemExit('SINA_INGEST_TOKEN must be at least 16 characters.')

    connection=live_connect(db_path)
    try: register_source(connection, source_id, 'HTTP')
    finally: connection.close()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != '/v1/measurements':
                self.send_error(404)
                return
            supplied = self.headers.get('Authorization','')
            if not hmac.compare_digest(supplied, f'Bearer {token}'):
                self.send_error(401)
                return
            try:
                size = int(self.headers.get('Content-Length','0'))
            except ValueError:
                self.send_error(400)
                return
            if not 0 < size <= MAX_PACKET_BYTES:
                self.send_error(413)
                return
            raw = self.rfile.read(size).decode('utf-8', errors='replace')
            conn = live_connect(db_path)
            try:
                data = parse_sensor_line(raw)
                outcome = ingest_packet(conn, data, source_id)
                response = {'outcome':outcome.outcome,'timestamp':outcome.timestamp,'line_id':outcome.line_id}
                code = 201 if outcome.outcome == 'inserted' else 200
            except (ValueError, TypeError) as exc:
                log_ingestion_error(conn, source_id, str(exc), raw)
                response={'error':str(exc)}
                code=400
            finally:
                conn.close()
            body=json.dumps(response).encode()
            self.send_response(code)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.send_error(404)

        def log_message(self, fmt, *args):
            print(f'[HTTP {self.client_address[0]}] {fmt % args}')

    # Explicitly local-only. Remote devices require an independently secured tunnel/broker.
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'SINA HTTP gateway: http://127.0.0.1:{port}/v1/measurements | source={source_id}')
    try: server.serve_forever(poll_interval=.25)
    except KeyboardInterrupt: pass
    finally: server.server_close()


def collect_serial(db_path: Path, source_id: str, port: str, baud: int,
                   *, serial_factory, connection_error=OSError,
                   should_stop=None, sleep_fn=time.sleep, retry_seconds: float = 3) -> None:
    """A recoverable serial ingest loop; tests can inject a fake physical transport.

    A packet does not automatically trigger any actuator command.
    """
    should_stop = should_stop or (lambda: False)
    conn=live_connect(db_path)
    try:
        register_source(conn, source_id, 'SERIAL')
    finally:
        conn.close()
    print(f'SINA serial gateway: port={port} baud={baud} source={source_id}. Ctrl+C to stop.')
    while not should_stop():
        try:
            with serial_factory(port, baudrate=baud, timeout=1) as device:
                conn=live_connect(db_path)
                try: log_gateway_event(conn,source_id,'CONNECTED',f'port={port}')
                finally: conn.close()
                print('Connected. Reading JSONL or CSV sensor packets...')
                while not should_stop():
                    data=device.readline(MAX_PACKET_BYTES + 1)
                    if not data:
                        continue
                    raw=data.decode('utf-8', errors='replace')
                    conn=live_connect(db_path)
                    try:
                        payload=parse_sensor_line(raw)
                        result=ingest_packet(conn,payload,source_id)
                        if result.outcome=='inserted':
                            print(f'[{result.timestamp}] {result.line_id}: recorded')
                    except (ValueError, TypeError) as exc:
                        log_ingestion_error(conn,source_id,str(exc),raw)
                        print(f'[REJECT] {exc}')
                    finally: conn.close()
        except KeyboardInterrupt:
            break
        except (connection_error, OSError) as exc:
            conn=live_connect(db_path)
            try: log_gateway_event(conn,source_id,'DISCONNECTED',str(exc))
            finally: conn.close()
            print(f'Serial disconnected: {exc}. Retrying after {retry_seconds:g} seconds.')
            if should_stop(): break
            conn=live_connect(db_path)
            try: log_gateway_event(conn,source_id,'RETRYING',f'next attempt in {retry_seconds:g} s')
            finally: conn.close()
            sleep_fn(retry_seconds)
    conn=live_connect(db_path)
    try: log_gateway_event(conn,source_id,'STOPPED','serial gateway exited')
    finally:conn.close()


def collect_serial(db_path: Path, source_id: str, port: str, baud: int,
                   *, serial_factory, connection_error=OSError,
                   should_stop=None, sleep_fn=time.sleep, retry_seconds: float = 3) -> None:
    """A recoverable serial ingest loop; tests can inject a fake physical transport.

    A packet does not automatically trigger any actuator command.
    """
    should_stop = should_stop or (lambda: False)
    conn=live_connect(db_path)
    try:
        register_source(conn, source_id, 'SERIAL')
    finally:
        conn.close()
    print(f'SINA serial gateway: port={port} baud={baud} source={source_id}. Ctrl+C to stop.')
    while not should_stop():
        try:
            with serial_factory(port, baudrate=baud, timeout=1) as device:
                conn=live_connect(db_path)
                try: log_gateway_event(conn,source_id,'CONNECTED',f'port={port}')
                finally: conn.close()
                print('Connected. Reading JSONL or CSV sensor packets...')
                while not should_stop():
                    data=device.readline(MAX_PACKET_BYTES + 1)
                    if not data:
                        continue
                    raw=data.decode('utf-8', errors='replace')
                    conn=live_connect(db_path)
                    try:
                        payload=parse_sensor_line(raw)
                        result=ingest_packet(conn,payload,source_id)
                        if result.outcome=='inserted':
                            print(f'[{result.timestamp}] {result.line_id}: recorded')
                    except (ValueError, TypeError) as exc:
                        log_ingestion_error(conn,source_id,str(exc),raw)
                        print(f'[REJECT] {exc}')
                    finally: conn.close()
        except KeyboardInterrupt:
            break
        except (connection_error, OSError) as exc:
            conn=live_connect(db_path)
            try: log_gateway_event(conn,source_id,'DISCONNECTED',str(exc))
            finally: conn.close()
            print(f'Serial disconnected: {exc}. Retrying after {retry_seconds:g} seconds.')
            if should_stop(): break
            conn=live_connect(db_path)
            try: log_gateway_event(conn,source_id,'RETRYING',f'next attempt in {retry_seconds:g} s')
            finally: conn.close()
            sleep_fn(retry_seconds)
    conn=live_connect(db_path)
    try: log_gateway_event(conn,source_id,'STOPPED','serial gateway exited')
    finally:conn.close()


def serve_serial(db_path: Path, source_id: str, port: str, baud: int) -> None:
    try:
        import serial
    except ImportError as exc:
        raise SystemExit('Install pyserial: python -m pip install pyserial') from exc
    collect_serial(db_path,source_id,port,baud,serial_factory=serial.Serial,
                   connection_error=serial.SerialException)

def replay_file(db_path: Path, source_id: str, path: Path) -> None:
    """Explicitly marked offline test replay; never claimed to be a physical live stream."""
    conn=live_connect(db_path)
    register_source(conn, source_id, 'OFFLINE_REPLAY')
    inserted=dupes=rejected=0
    try:
        for raw in path.read_text(encoding='utf-8-sig').splitlines():
            if not raw.strip() or raw.lstrip().startswith('#'): continue
            try:
                outcome=ingest_packet(conn,parse_sensor_line(raw),source_id)
                if outcome.outcome=='inserted': inserted+=1
                else: dupes+=1
            except ValueError as exc:
                log_ingestion_error(conn,source_id,str(exc),raw)
                rejected+=1
        print(f'OFFLINE REPLAY: inserted={inserted}, duplicates={dupes}, rejected={rejected}, source={source_id}')
    finally:conn.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description='SINA local-only serial/HTTP ingestion')
    parser.add_argument('--mode',choices=['serial','http','replay'],required=True)
    parser.add_argument('--source',default='field-01',help='Provenance source ID (use demo-... for simulated traffic)')
    parser.add_argument('--db',type=Path,default=DEFAULT_DB)
    parser.add_argument('--port',default='COM3',help='serial device name, e.g. COM3 or /dev/ttyACM0')
    parser.add_argument('--baud',type=int,default=115200)
    parser.add_argument('--http-port',type=int,default=8765)
    parser.add_argument('--input',type=Path,help='offline line-based JSONL/CSV for --mode replay')
    args=parser.parse_args(argv)
    sid=validate_source_id(args.source)
    if args.mode=='http':
        serve_http(args.db,sid,os.environ.get('SINA_INGEST_TOKEN',''),args.http_port)
    elif args.mode=='serial':
        serve_serial(args.db,sid,args.port,args.baud)
    else:
        if not args.input or not args.input.is_file(): parser.error('Provide existing --input file for replay')
        replay_file(args.db,sid,args.input)


if __name__=='__main__':main()
