import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(os.environ.get("API_PORT", "5000"))
BACKUP_DIR = os.environ.get("BACKUP_DIR", "/mnt/backups")
LOG_TAIL_LINES = int(os.environ.get("LOG_TAIL_LINES", "50"))
# Where users may place backups via the optional "dir" parameter
ALLOWED_BACKUP_ROOTS = (BACKUP_DIR, "/backups")
ALLOWED_BACKUP_REALPATHS = {os.path.realpath(p) for p in ALLOWED_BACKUP_ROOTS}

STATE_LOCK = threading.Lock()

usbmuxd_process = None
usbmuxd_mode = None  # "wired" or "wireless"

backup_state = {
    "running": False,
    "uid": None,
    "pid": None,
    "started_at": None,
    "finished_at": None,
    "exit_code": None,
    "success": None,
    "backup_dir": None,
}
backup_process = None
backup_logs = deque(maxlen=LOG_TAIL_LINES)
usbmuxd_logs = deque(maxlen=LOG_TAIL_LINES)


def log(msg):
    print(msg, flush=True)


class OutputRecorder:
    """Prints subprocess output to stdout and keeps the last lines in memory."""

    def __init__(self, pipe, sink, prefix):
        self.pipe = pipe
        self.sink = sink
        self.prefix = prefix

    def run(self):
        for line in iter(self.pipe.readline, ""):
            self.sink.append(line.rstrip("\n"))
            print(f"{self.prefix} {line}", end="", flush=True)


def start_output_recorder(process, sink, prefix):
    threading.Thread(
        target=OutputRecorder(process.stdout, sink, prefix).run,
        daemon=True,
    ).start()


def snapshot_logs(deq):
    return list(deq)


def kill_existing_usbmuxd():
    subprocess.run(
        ["pkill", "-f", "usbmuxd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def stop_usbmuxd_locked():
    """Stop the usbmuxd process we started. Caller must hold STATE_LOCK."""
    global usbmuxd_process, usbmuxd_mode
    if not (usbmuxd_process and usbmuxd_process.poll() is None):
        usbmuxd_process = None
        usbmuxd_mode = None
        return
    log("[+] Stopping usbmuxd")
    usbmuxd_process.terminate()
    try:
        usbmuxd_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        usbmuxd_process.kill()
    usbmuxd_process = None
    usbmuxd_mode = None


def get_devices():
    result = subprocess.run(
        ["idevice_id", "-n"],
        capture_output=True,
        text=True,
        check=False,
    )
    devices = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    return result.returncode, devices, result.stderr.strip()


def finish_backup(process, uid):
    """Runs in a thread: record the result when the backup process exits,
    then stop usbmuxd if it was started for a wireless connection."""
    global backup_process, backup_state

    exit_code = process.wait()

    with STATE_LOCK:
        backup_state.update(
            running=False,
            uid=uid,
            pid=process.pid,
            started_at=backup_state["started_at"],
            finished_at=time.time(),
            exit_code=exit_code,
            success=exit_code == 0,
        )
        backup_process = None

    log(f"[+] Backup for {uid} exited with code {exit_code}")

    # Only auto-stop wireless sessions; a wired usbmuxd should keep
    # serving the USB connection after the backup.
    with STATE_LOCK:
        if usbmuxd_mode == "wireless":
            stop_usbmuxd_locked()


def start_backup(requested_uid, backup_dir):
    """Validate and launch a backup. Returns (response_dict, http_status)."""
    global backup_process, backup_state

    uid = requested_uid
    if not uid:
        code, devices, _ = get_devices()
        if len(devices) == 1:
            uid = devices[0]
            log(f"[+] No uid given, using single connected device: {uid}")
        elif not devices:
            return ({"success": False,
                     "message": "No device found. Start usbmuxd first (/start)."}, 400)
        else:
            return ({"success": False,
                     "message": f"Multiple devices found, specify uid: {devices}"}, 400)

    os.makedirs(backup_dir, exist_ok=True)

    with STATE_LOCK:
        if backup_state["running"]:
            return ({"success": False,
                     "message": "A backup is already running",
                     "uid": backup_state["uid"]}, 409)
        if usbmuxd_process is None or usbmuxd_process.poll() is not None:
            return ({"success": False,
                     "message": "usbmuxd is not running, call /start first"}, 400)

        mode = usbmuxd_mode
        cmd = ["idevicebackup2", "backup"]
        if uid:
            cmd += ["-u", uid]
        if mode == "wireless":
            cmd += ["-n"]
        cmd += [backup_dir]

        backup_state.update(
            running=True,
            uid=uid,
            pid=None,
            started_at=time.time(),
            finished_at=None,
            exit_code=None,
            success=None,
            backup_dir=backup_dir,
        )
        backup_logs.clear()

    log(f"[+] Starting backup for device {uid} ({mode}) -> {backup_dir}")
    log(f"[+] cmd: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    with STATE_LOCK:
        backup_process = process
        backup_state["pid"] = process.pid

    start_output_recorder(process, backup_logs, "[backup]")
    threading.Thread(
        target=finish_backup,
        args=(process, uid),
        daemon=True,
    ).start()

    return ({"success": True,
             "message": "Backup started",
             "uid": uid,
             "backup_dir": backup_dir,
             "mode": mode,
             "pid": process.pid}, 200)


def start_usbmuxd(ip, pair_record_id):
    """Start usbmuxd in wireless mode (ip given) or wired mode. Returns
    (response_dict, http_status)."""
    global usbmuxd_process, usbmuxd_mode

    with STATE_LOCK:
        if usbmuxd_process and usbmuxd_process.poll() is None:
            return ({"success": False,
                     "message": "usbmuxd already running",
                     "mode": usbmuxd_mode}, 409)

        if ip:
            cmd = ["usbmuxd", "-c", ip]
            if pair_record_id:
                cmd += ["--pair-record-id", pair_record_id]
            mode = "wireless"
        else:
            # No -d: keep usbmuxd in the foreground so we can capture its
            # output and detect when it dies.
            cmd = ["usbmuxd"]
            mode = "wired"

        kill_existing_usbmuxd()

        log(f"[+] Starting usbmuxd ({mode})")
        if ip:
            log(f"[+] -> {ip} pair-record-id='{pair_record_id}'")

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        usbmuxd_logs.clear()
        start_output_recorder(process, usbmuxd_logs, "[usbmuxd]")

        # Give usbmuxd a moment to fail fast on bad targets (e.g. wrong IP)
        time.sleep(2)
        if process.poll() is not None:
            stderr_tail = list(usbmuxd_logs)[-5:]
            usbmuxd_process = None
            usbmuxd_mode = None
            return ({"success": False,
                     "message": f"usbmuxd exited immediately (code {process.returncode})",
                     "log_tail": stderr_tail}, 502)

        usbmuxd_process = process
        usbmuxd_mode = mode

    return ({"success": True,
             "mode": mode,
             "pid": process.pid,
             "ip": ip or None,
             "pair_record_id": pair_record_id or None}, 200)


def list_backups(root):
    """List backup directories under root with size and mtime."""
    result = []
    if not os.path.isdir(root):
        return result
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.isdir(path) or os.path.isfile(path):
            try:
                stat = os.stat(path)
                result.append({
                    "name": name,
                    "type": "dir" if os.path.isdir(path) else "file",
                    "size_bytes": stat.st_size,
                    "modified": stat.st_mtime,
                })
            except OSError:
                continue
    return result


def delete_backup(root, name):
    """Delete a single backup directory/file by name. Returns
    (response_dict, http_status)."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in (".", ".."):
        return ({"success": False, "message": "Invalid backup name"}, 400)
    path = os.path.realpath(os.path.join(root, name))
    if os.path.dirname(path) != os.path.realpath(root):
        return ({"success": False, "message": "Invalid backup name"}, 400)
    if not os.path.exists(path):
        return ({"success": False, "message": f"'{name}' not found in {root}"}, 404)
    if backup_state.get("running") and backup_state.get("backup_dir") == os.path.join(root, name):
        return ({"success": False, "message": "Cannot delete the backup currently in progress"}, 409)
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)
    log(f"[+] Deleted backup '{name}' from {root}")
    return ({"success": True, "message": f"Deleted '{name}'"}, 200)


class RequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_json(self, data, status=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path.rstrip("/") or "/"

        #
        # INDEX
        #
        if path == "/":
            return self.send_json({
                "service": "idevice-backuptool",
                "endpoints": {
                    "/start?ip=<ip>&id=<uid>": "Start usbmuxd. Omit ip for wired mode.",
                    "/stop": "Stop usbmuxd",
                    "/status": "usbmuxd and backup state",
                    "/devices": "List connected devices (idevice_id -n)",
                    "/idevice_id": "Alias of /devices",
                    "/backup?uid=<uid>&dir=<abs-path>": "Start a backup",
                    "/backup/status": "Last/current backup state and log tail",
                    "/backups": "List backups in the backup dir",
                    "/delete_backup?name=<name>": "Delete a backup by name",
                },
            })

        #
        # START USBMUXD
        #
        elif path == "/start":
            ip = query.get("ip", [""])[0]
            pair_record_id = query.get("id", [""])[0]
            resp, status = start_usbmuxd(ip, pair_record_id)
            return self.send_json(resp, status)

        #
        # STOP USBMUXD
        #
        elif path == "/stop":
            with STATE_LOCK:
                if usbmuxd_process and usbmuxd_process.poll() is None:
                    stop_usbmuxd_locked()
                    return self.send_json({"success": True, "message": "usbmuxd stopped"})
            return self.send_json({"success": False, "message": "usbmuxd not running"}, 400)

        #
        # STATUS
        #
        elif path == "/status":
            with STATE_LOCK:
                running = (
                    usbmuxd_process is not None
                    and usbmuxd_process.poll() is None
                )
                state = {
                    "usbmuxd": {"running": running, "mode": usbmuxd_mode if running else None},
                    "backup": backup_state,
                }
            return self.send_json(state)

        #
        # idevice_id -n
        #
        elif path in ("/idevice_id", "/devices"):
            code, devices, stderr = get_devices()
            return self.send_json({
                "success": code == 0,
                "devices": devices,
                "stderr": stderr,
            })

        #
        # BACKUP DEVICE
        #
        elif path == "/backup":
            uid = query.get("uid", [""])[0]
            backup_dir = query.get("dir", [BACKUP_DIR])[0]
            if not backup_dir.startswith("/"):
                return self.send_json({"success": False, "message": "dir must be an absolute path"}, 400)
            if os.path.realpath(backup_dir) not in ALLOWED_BACKUP_REALPATHS:
                return self.send_json({"success": False, "message": f"dir must be one of {list(ALLOWED_BACKUP_ROOTS)}"}, 400)
            resp, status = start_backup(uid, backup_dir)
            return self.send_json(resp, status)

        elif path == "/backup/status":
            with STATE_LOCK:
                status = dict(backup_state)
            if status["started_at"] and status["finished_at"]:
                status["duration_seconds"] = round(status["finished_at"] - status["started_at"], 1)
            elif status["started_at"]:
                status["duration_seconds"] = round(time.time() - status["started_at"], 1)
            status["log_tail"] = snapshot_logs(backup_logs)
            return self.send_json(status)

        #
        # LIST BACKUPS
        #
        elif path == "/backups":
            entries = list_backups(BACKUP_DIR)
            return self.send_json({
                "backup_dir": BACKUP_DIR,
                "count": len(entries),
                "backups": entries,
            })

        #
        # DELETE A BACKUP
        #
        elif path == "/delete_backup":
            name = query.get("name", [""])[0]
            if not name:
                return self.send_json({"success": False, "message": "Missing name parameter"}, 400)
            resp, status = delete_backup(BACKUP_DIR, name)
            return self.send_json(resp, status)

        return self.send_json({"error": "Not found"}, 404)


# A tiny marker endpoint the Docker healthcheck can hit without side effects
def start_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), RequestHandler)
    server.daemon_threads = True
    log(f"[+] API server running on 0.0.0.0:{PORT}")
    log(f"[+] Backup dir: {BACKUP_DIR}")
    return server


def shutdown_handler(server, signum, frame):
    log(f"\n[+] Caught signal {signum}, shutting down")

    with STATE_LOCK:
        if backup_process and backup_process.poll() is None:
            log("[+] Terminating running backup")
            backup_process.terminate()
        stop_usbmuxd_locked()

    threading.Thread(target=server.shutdown, daemon=True).start()


if __name__ == "__main__":
    server = start_server()
    signal.signal(signal.SIGTERM, lambda s, f: shutdown_handler(server, s, f))
    signal.signal(signal.SIGINT, lambda s, f: shutdown_handler(server, s, f))

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        sys.exit(0)
