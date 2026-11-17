# iDevice Backup Tool

A Docker-based tool for creating iOS device backups using `libimobiledevice` and `usbmuxd2`.

## Core Tools
- [libimobiledevice](https://github.com/libimobiledevice/libimobiledevice)
- [usbmuxd2](https://github.com/tihmstar/usbmuxd2)

## Overview

This tool allows you to perform backups of iOS devices from within a Docker container. Backups can be copied directly to the iTunes backup folder to restore an iDevice. `libimobiledevice` also supports backups through a REST API for programmatic management.

## Prerequisites

- Docker (with USB support or privileged mode)
- An iOS device (iPhone, iPad, etc.)
- macOS or Windows machine with iTunes (for wireless backup setup)

## Quick Start

### Initial Setup

The tool requires USB access to the iOS device. Run the Docker container in privileged mode:

```bash
docker run --privileged -it [container-image]
```

Or use the provided `docker-compose.yml` (connects USB, D-Bus and Avahi, persists pairing records and backups).

### Pairing Your Device

1. **Start usbmuxd2** inside the container (or via the API, see below):
   ```bash
   usbmuxd
   ```

2. **Pair your iOS device**:
   ```bash
   idevicepair pair
   ```

3. **Note the device UID**:
   ```bash
   idevice_id
   ```

## Usage

### Wired Backups

Once your device is paired, create a backup using:

```bash
idevicebackup2 backup /backup-path
```

**Options:**
- For a list of all available parameters, run: `idevicebackup2 --help`
- Consider enabling encryption for added security
- To back up a specific device, use: `idevicebackup2 backup -u <device-id> /backup-path`

### Wireless Backups

1. **Enable WiFi Sync** on your iOS device:
   - Use iTunes on macOS or Windows to enable WiFi sync for your device

2. **Configure usbmuxd2** for wireless connection via the API or manually:
   ```bash
   usbmuxd -c <idevice-ip> --pair-record-id <idevice-uid>
   ```

3. **Verify device visibility**:
   ```bash
   idevice_id -n
   ```

4. **Create the backup**:
   ```bash
   idevicebackup2 backup -n /backup-path
   ```

5. **For multiple devices**, specify the device ID:
   ```bash
   idevicebackup2 backup -u <device-id> -n /backup-path
   ```

### REST API (After Initial USB Pairing)

Once your device has been paired once over USB, you can use the REST API for programmatic backup management. The API runs on port 5000 inside the container.

#### Shortcuts Template

[iCloud](https://www.icloud.com/shortcuts/acda9cd3de7b4f308d9f55902972064d)

#### API Endpoints

**1. Start usbmuxd (wired or wireless)**
```bash
# Wireless
curl "http://localhost:5000/start?ip=192.168.1.100&id=device-uid"

# Wired (no parameters)
curl "http://localhost:5000/start"
```

Parameters:
- `ip`: The IP address of your iOS device (omit for wired USB mode)
- `id`: The pair record ID (device UID), required when `ip` is given

Response:
```json
{
  "success": true,
  "mode": "wireless",
  "pid": 1234,
  "ip": "192.168.1.100",
  "pair_record_id": "device-uid"
}
```

If usbmuxd cannot establish the connection it usually exits within a few seconds; the response then reports `success: false` with the last log lines in `log_tail`.

**2. Stop usbmuxd**
```bash
curl http://localhost:5000/stop
```

**3. Check Status (usbmuxd and current/last backup)**
```bash
curl http://localhost:5000/status
```

Response:
```json
{
  "usbmuxd": { "running": true, "mode": "wireless" },
  "backup": {
    "running": false,
    "uid": "device-uid",
    "exit_code": 0,
    "success": true,
    "backup_dir": "/mnt/backups",
    "duration_seconds": 612.5
  }
}
```

**4. Start Backup**
```bash
curl "http://localhost:5000/backup?uid=device-uid"
```

Parameters:
- `uid`: The device UID to back up. Optional: if exactly one device is connected it is used automatically.
- `dir`: Optional absolute path for this backup. Only `/mnt/backups` and `/backups` are allowed.

Only one backup can run at a time; a second request returns HTTP 409 while one is in progress.

**5. Backup Status / Result**

```bash
curl http://localhost:5000/backup/status
```

Returns whether a backup is running, its uid/pid, elapsed time and - once finished - the exit code and `success: true/false`, plus the last 50 log lines.

**6. List Backups**
```bash
curl http://localhost:5000/backups
```

**7. Delete a Backup**
```bash
curl "http://localhost:5000/delete_backup?name=00000030-001941100A5F802E"
```

Deletes a single backup (by name, as listed by `/backups`). Deleting the currently running backup is refused.

**8. List Connected Devices**
```bash
curl http://localhost:5000/devices
```

(`idevice_id -n`; `/idevice_id` still works as an alias.)

#### Example Workflow

```bash
# 1. Start usbmuxd for wireless connection
curl "http://localhost:5000/start?ip=192.168.1.100&id=your-device-uid"

# 2. Start backup
curl "http://localhost:5000/backup?uid=your-device-uid"

# 3. Poll for the result
curl http://localhost:5000/backup/status

# 4. Once the backup completes, usbmuxd is automatically stopped
```

## Restoring Backups

Backups can be moved to the iTunes backup folder and restored through iTunes. Direct restoration using `libimobiledevice` is also possible, haven't tried it tho.

## Future Enhancements

This project aims to streamline the backup process through:

- **Web UI**: Interactive interface for managing backups
- **Siri Shortcuts Integration**: Automate backups via iOS shortcuts

## Technical Notes

- **Automatic Network Discovery**: In an ideal setup, `usbmuxd` would automatically discover paired iDevices on the same network via Avahi/mDNS/DNS-SD/Bonjour. However, this is challenging in Docker environments.
- **Backup Location**: Backups are stored in `/mnt/backups` within the container (configurable via the `BACKUP_DIR` env var). Mount a volume to persist backups on your host machine.
- **Automatic Cleanup**: The API automatically stops usbmuxd after a wireless backup completes; a wired session stays connected.
- **Health check**: The container has a Docker `HEALTHCHECK` hitting `/status`, so `docker ps` reflects API health.
- **Building the image**: Dependency versions are pinned via `--branch`/commit refs at image build time (see the `ARG`s at the top of the `Dockerfile`). Override them with `--build-arg`, e.g. to track `master`.
- **Testing**: `tests/smoke.sh` runs the API against stub binaries - no device or docker needed.

## Troubleshooting

- Ensure the container has proper USB access when using wired backups
- Verify the iOS device is unlocked during the pairing process
- Check device connectivity before starting backups
- Use `/devices` (or `idevice_id -n`) to troubleshoot wireless device visibility
- The API logs usbmuxd and backup output to the container log; `/backup/status` also returns the last log lines
- For API issues, check the container logs for detailed error messages

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
