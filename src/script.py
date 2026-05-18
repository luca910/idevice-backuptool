from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
import subprocess
import threading
import time
import os

PORT = 5000
BACKUP_DIR = "/mnt/backups"

USBMUXD_PROCESS = None


def stream_output(pipe, prefix="[proc]"):
    for line in iter(pipe.readline, ""):
        print(f"{prefix} {line}", end="")


def kill_existing_usbmuxd():
    subprocess.run(
        ["pkill", "-f", "usbmuxd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def monitor_backup_process(process, uid):
    """Monitor backup process and stop usbmuxd when done"""
    global USBMUXD_PROCESS
    
    # Wait for backup process to complete
    process.wait()
    
    print(f"[+] Backup completed for device: {uid}")
    
    # Stop usbmuxd after backup is done
    if USBMUXD_PROCESS and USBMUXD_PROCESS.poll() is None:
        print("[+] Stopping usbmuxd after backup completion")
        USBMUXD_PROCESS.terminate()
        try:
            USBMUXD_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            USBMUXD_PROCESS.kill()
        USBMUXD_PROCESS = None


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

            ip = query.get("ip", [""])[0]
            pair_record_id = query.get("id", [""])[0]

            if not ip:
                return self.send_json({
                    "success": False,
                    "message": "Missing ip parameter"
                }, 400)

            if USBMUXD_PROCESS and USBMUXD_PROCESS.poll() is None:
                return self.send_json({
                    "success": False,
                    "message": "usbmuxd already running"
                }, 400)

            kill_existing_usbmuxd()

            cmd = [
                "usbmuxd",
                "-c",
                ip,
                "--pair-record-id",
                pair_record_id,
                "-d"
            ]

            print(f"[+] Starting usbmuxd -> {ip}")
            print(f"[+] pair-record-id='{pair_record_id}'")

            USBMUXD_PROCESS = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            threading.Thread(
                target=stream_output,
                args=(USBMUXD_PROCESS.stdout, "[usbmuxd]"),
                daemon=True,
            ).start()

            time.sleep(2)

            return self.send_json({
                "success": True,
                "pid": USBMUXD_PROCESS.pid,
                "ip": ip,
                "pair_record_id": pair_record_id,
            })

        #
        # STOP USBMUXD
        #
        elif parsed.path == "/stop":

            if USBMUXD_PROCESS and USBMUXD_PROCESS.poll() is None:

                print("[+] Stopping usbmuxd")

                USBMUXD_PROCESS.terminate()
                try:
                    USBMUXD_PROCESS.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    USBMUXD_PROCESS.kill()

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
        # BACKUP DEVICE
        #
        elif parsed.path == "/backup":

            query = parse_qs(parsed.query)
            uid = query.get("uid", [""])[0]

            if not uid:
                return self.send_json({
                    "success": False,
                    "message": "Missing uid parameter"
                }, 400)

            os.makedirs(BACKUP_DIR, exist_ok=True)

            cmd = [
                "idevicebackup2",
                "backup",
                "-u",
                uid,
                "-n",
                BACKUP_DIR
            ]

            print(f"[+] Starting backup for device: {uid}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            threading.Thread(
                target=stream_output,
                args=(process.stdout, "[backup]"),
                daemon=True,
            ).start()

            # Start a monitor thread that will stop usbmuxd when backup completes
            threading.Thread(
                target=monitor_backup_process,
                args=(process, uid),
                daemon=True,
            ).start()

            return self.send_json({
                "success": True,
                "message": "Backup started",
                "uid": uid,
                "backup_dir": BACKUP_DIR,
                "pid": process.pid,
            })

        #
        # NOT FOUND
        #
        return self.send_json({
            "error": "Not found"
        }, 404)


if __name__ == "__main__":

    print(f"[+] API server running on 0.0.0.0:{PORT}")

    server = HTTPServer(("0.0.0.0", PORT), RequestHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[+] Shutting down")
        server.server_close()
