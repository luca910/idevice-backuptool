# iDevice Backup Tool

A Docker-based tool for creating iOS device backups using `libimobiledevice` and `usbmuxd2`.

## Core Tools
- [libimobiledevice](https://github.com/libimobiledevice/libimobiledevice)
- [usbmuxd2](https://github.com/tihmstar/usbmuxd2)

## Overview

This tool allows you to perform backups of iOS devices from within a Docker container. Backups can be copied directly to the iTunes backup folder to restore an iDevice. `libimobiledevice` also supports direct restoration (though this hasn't been thoroughly tested yet).

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

## Restoring Backups

Backups can be moved to the iTunes backup folder and restored through iTunes. Direct restoration using `libimobiledevice` is also possible, haven't tried it tho.

## Future Enhancements

This project aims to streamline the backup process through:

- **Web UI**: Interactive interface for managing backups
- **REST API**: Programmatic backup management
- **Siri Shortcuts Integration**: Automate backups via iOS shortcuts

## Technical Notes

- **Automatic Network Discovery**: In an ideal setup, `usbmuxd` would automatically discover paired iDevices on the same network via Avahi/mDNS/DNS-SD/Bonjour. However, this is challenging in Docker environments due to network namespace isolation.
- **Backup Location**: Backups are stored in `/backup-path` within the container. Mount a volume to persist backups on your host machine.

## Troubleshooting

- Ensure the container has proper USB access when using wired backups
- Verify the iOS device is unlocked during the pairing process
- Check device connectivity before starting backups
- Use `idevice_id -n` to troubleshoot wireless device visibility

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.



