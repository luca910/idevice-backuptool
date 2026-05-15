import subprocess
import threading
import time
import sys

HOST = "10.110.10.45"

USBMUXD_CMD = [
    "usbmuxd",
    "-c",
    HOST,
    "--pair-record-id",
    "",
    "-d"
]


def kill_existing_usbmuxd():
    subprocess.run(
        ["pkill", "-f", "usbmuxd"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    print("[+] Killed existing usbmuxd instances")


def stream_output(pipe):
    """
    Forward usbmuxd output to the main terminal.
    """
    for line in iter(pipe.readline, ""):
        print(f"[usbmuxd] {line}", end="")


def start_usbmuxd():
    print(f"[+] Starting usbmuxd -> {HOST}")

    process = subprocess.Popen(
        USBMUXD_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    threading.Thread(
        target=stream_output,
        args=(process.stdout,),
        daemon=True,
    ).start()

    return process


def run_idevice_id():
    print("[+] Running idevice_id -n")

    result = subprocess.run(
        ["idevice_id", "-n"],
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        print("[+] Device(s) found:")
        print(result.stdout.strip())
        return True

    print("[!] No devices found")

    if result.stderr.strip():
        print(result.stderr.strip())

    return False


def main():
    kill_existing_usbmuxd()

    process = start_usbmuxd()

    # Let usbmuxd initialize
    time.sleep(2)

    success = run_idevice_id()

    print("[+] usbmuxd is still running in background")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[+] Stopping usbmuxd")
        process.terminate()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
