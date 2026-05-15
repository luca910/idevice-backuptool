import subprocess
import threading
import time
import sys
import re

HOST = "10.110.10.45"

USBMUXD_CMD = [
    "usbmuxd",
    "-c",
    HOST,
    "--pair-record-id",
    "",
    "-d"
]

SUCCESS_PATTERNS = [
    r"connected",
    r"connection established",
    r"tcp.*ok",
    r"success",
]

FAIL_PATTERNS = [
    r"connection refused",
    r"failed",
    r"error",
    r"unable to connect",
]


def kill_existing_usbmuxd():
    subprocess.run(
        ["pkill", "-f", "usbmuxd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    print("[+] Killed existing usbmuxd instances")


def monitor_output(pipe, result):
    """
    Read usbmuxd output and detect success/failure.
    """
    for line in iter(pipe.readline, ""):
        line = line.strip()
        print(line)

        lower = line.lower()

        for pattern in SUCCESS_PATTERNS:
            if re.search(pattern, lower):
                result["success"] = True
                return

        for pattern in FAIL_PATTERNS:
            if re.search(pattern, lower):
                result["success"] = False
                return


def main():
    kill_existing_usbmuxd()

    print(f"[+] Starting usbmuxd connection to {HOST}")

    process = subprocess.Popen(
        USBMUXD_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    result = {"success": None}

    monitor_thread = threading.Thread(
        target=monitor_output,
        args=(process.stdout, result),
        daemon=True,
    )

    monitor_thread.start()

    timeout = 15
    start = time.time()

    while time.time() - start < timeout:
        if result["success"] is not None:
            break
        time.sleep(0.1)

    if result["success"] is True:
        print("[+] usbmuxd TCP connection successful")
        sys.exit(0)

    elif result["success"] is False:
        print("[!] usbmuxd reported connection failure")
        process.terminate()
        sys.exit(1)

    else:
        print("[!] Timed out waiting for usbmuxd connection result")
        process.terminate()
        sys.exit(2)


if __name__ == "__main__":
    main()
