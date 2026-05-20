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

### Pairing Your Device

1. **Start usbmuxd2** inside the container:
   ```bash
   usbmuxd -d
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

2. **Configure usbmuxd2** for wireless connection:
   - Kill the previous usbmuxd process
   - Restart it with your device's IP and UID:
     ```bash
     usbmuxd -c <idevice-ip> --pair-record-id <idevice-uid> -d
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
   idevicebackup2 backup -u <device-id> /backup-path
   ```

### REST API (After Initial USB Pairing)

Once your device has been paired once over USB, you can use the REST API for programmatic backup management. The API runs on port 5000 inside the container.

#### Starting the API Server

```bash
python3 src/script.py
```

#### API Endpoints

**1. Get Device List**
```bash
curl http://localhost:5000/idevice_id
```

Response:
```json
{
  "success": true,
  "devices": ["device-uid-1", "device-uid-2"],
  "stderr": ""
}
```

**2. Start usbmuxd for Wireless Connection**
```bash
curl "http://localhost:5000/start?ip=192.168.1.100&id=device-uid"
```

Parameters:
- `ip`: The IP address of your iOS device
- `id`: The pair record ID (device UID)

Response:
```json
{
  "success": true,
  "pid": 1234,
  "ip": "192.168.1.100",
  "pair_record_id": "device-uid"
}
```

**3. Stop usbmuxd**
```bash
curl http://localhost:5000/stop
```

Response:
```json
{
  "success": true,
  "message": "usbmuxd stopped"
}
```

**4. Check usbmuxd Status**
```bash
curl http://localhost:5000/status
```

Response:
```json
{
  "running": true
}
```

**5. Start Backup**
```bash
curl "http://localhost:5000/backup?uid=device-uid"
```

Parameters:
- `uid`: The device UID to back up

Response:
```json
{
  "success": true,
  "message": "Backup started",
  "uid": "device-uid",
  "backup_dir": "/mnt/backups",
  "pid": 5678
}
```

#### Example Workflow

```bash
# 1. Get available devices
curl http://localhost:5000/idevice_id

# 2. Start usbmuxd for wireless connection
curl "http://localhost:5000/start?ip=192.168.1.100&id=your-device-uid"

# 3. Wait a moment for connection to establish
sleep 2

# 4. Start backup
curl "http://localhost:5000/backup?uid=your-device-uid"

# 5. Monitor the backup progress (logs appear in container output)

# 6. Once backup completes, usbmuxd will automatically stop
```

## Restoring Backups

Backups can be moved to the iTunes backup folder and restored through iTunes. Direct restoration using `libimobiledevice` is also possible, haven't tried it tho.

## Future Enhancements

This project aims to streamline the backup process through:

- **Web UI**: Interactive interface for managing backups
- **REST API**: Programmatic backup management
- **Siri Shortcuts Integration**: Automate backups via iOS shortcuts

## Technical Notes

- **Automatic Network Discovery**: In an ideal setup, `usbmuxd` would automatically discover paired iDevices on the same network via Avahi/mDNS/DNS-SD/Bonjour. However, this is challenging in Docker environments.
- **Backup Location**: Backups are stored in `/backup-path` within the container. Mount a volume to persist backups on your host machine.
- **API Backups**: When using the REST API, backups are stored in `/mnt/backups` within the container.
- **Automatic Cleanup**: The API automatically stops usbmuxd after a backup completes.

## Troubleshooting

- Ensure the container has proper USB access when using wired backups
- Verify the iOS device is unlocked during the pairing process
- Check device connectivity before starting backups
- Use `idevice_id -n` to troubleshoot wireless device visibility
- For API issues, check the container logs for detailed error messages

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
