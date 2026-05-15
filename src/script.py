#!/usr/bin/env python3

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
import subprocess
import threading
import time

HOST = "10.110.10.45"
PORT = 5000

USBMUXD_PROCESS = None


def stream_output(pipe):
    """
    Forward usbmuxd output to main terminal.
    """
    for line in iter(pipe.readline, ""):
        print(f"[usbmuxd] {line}", end="")


def kill_existing_usbmuxd():
    """
    Kill any existing usbmuxd processes.
    """
    subprocess.run(
        ["pkill", "-f", "usbmuxd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


class RequestHandler(BaseHTTPRequestHandler):

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        global USBMUXD_PROCESS

        parsed = urlparse(self.path)

        #
        # START USBMUXD
        #
        if parsed.path == "/start":

            query = parse_qs(parsed.query)
            pair_record_id = query.get("id", [""])[0]

            if USBMUXD_PROCESS and USBMUXD_PROCESS.poll() is None:
                return self.send_json({
                    "success": False,
                    "message": "usbmuxd already running"
                }, 400)

            kill_existing_usbmuxd()

            cmd = [
                "usbmuxd",
                "-c",
                HOST,
                "--pair-record-id",
                pair_record_id,
                "-d"
            ]

            print(f"[+] Starting usbmuxd with pair-record-id='{pair_record_id}'")

            USBMUXD_PROCESS = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            threading.Thread(
                target=stream_output,
                args=(USBMUXD_PROCESS.stdout,),
                daemon=True,
            ).start()

            time.sleep(2)

            return self.send_json({
                "success": True,
                "pid": USBMUXD_PROCESS.pid,
                "pair_record_id": pair_record_id,
            })

        #
        # STOP USBMUXD
        #
        elif parsed.path == "/stop":

            if USBMUXD_PROCESS and USBMUXD_PROCESS.poll() is None:

                print("[+] Stopping usbmuxd")

                USBMUXD_PROCESS.terminate()
                USBMUXD_PROCESS.wait(timeout=5)

                USBMUXD_PROCESS = None

                return self.send_json({
                    "success": True,
                    "message": "usbmuxd stopped"
                })

            return self.send_json({
                "success": False,
                "message": "usbmuxd not running"
            }, 400)

        #
        # STATUS
        #
        elif parsed.path == "/status":

            running = (
                USBMUXD_PROCESS is not None
                and USBMUXD_PROCESS.poll() is None
            )

            return self.send_json({
                "running": running
            })

        #
        # idevice_id -n
        #
        elif parsed.path == "/idevice_id":

            result = subprocess.run(
                ["idevice_id", "-n"],
                capture_output=True,
                text=True,
            )

            devices = [
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip()
            ]

            return self.send_json({
                "success": result.returncode == 0,
                "devices": devices,
                "stderr": result.stderr.strip(),
            })

        #
        # UNKNOWN ROUTE
        #
        self.send_json({
            "error": "Not found"
        }, 404)


if __name__ == "__main__":

    print(f"[+] API server listening on port {PORT}")

    server = HTTPServer(("0.0.0.0", PORT), RequestHandler)

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print("\n[+] Shutting down server")
        server.server_close()
