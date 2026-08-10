# EduManage Attendance Edge Connector

The Edge Connector lets a school connect LAN/SDK-only attendance machines to EduManage **without logging into the VPS**. It runs on a Windows school PC, mini-PC or Raspberry Pi that can reach the physical attendance machine.

The connector is intentionally dependency-light: its core uses Python's standard library and SQLite.

## Recommended setup flow

1. In EduManage open **Attendance → Devices → Connect machine**.
2. Select the connection method recommended for the machine.
3. If Edge Connector is recommended, download the generated `edumanage-attendance-<DEVICE>.json` file.
4. Copy the `edge/` folder to the local connector computer or deploy this repository checkout there.
5. Store the one-time device key in the environment variable `EDUMANAGE_ATTENDANCE_DEVICE_KEY`.
6. Configure a vendor bridge source that reads the local machine/SDK and outputs canonical JSON events.
7. Validate, run once, then run continuously.
8. Keep the EduManage setup page open: it automatically changes from **Waiting** to **Online** to **Connected and receiving attendance** when heartbeats and punches arrive.

## Requirements

- Python 3.11+
- Network access from the connector computer to the attendance machine/vendor server
- Outbound HTTPS access to the school's EduManage tenant domain
- The generated EduManage device code and one-time device key

No inbound internet port needs to be opened on the school network for the normal Edge Connector pattern.

## Configuration

Download the generated file from the EduManage device setup page or start from `edge/attendance-connector.example.json`.

Example:

```json
{
  "server_url": "https://school.example.com",
  "device_code": "MAIN-GATE-01",
  "queue_path": "./data/attendance-edge.sqlite3",
  "device_key_env": "EDUMANAGE_ATTENDANCE_DEVICE_KEY",
  "poll_seconds": 5,
  "batch_size": 100,
  "heartbeat_seconds": 60,
  "sources": [
    {
      "type": "command_json",
      "name": "main-gate-vendor",
      "command": ["python", "vendor_bridge.py"]
    }
  ]
}
```

The configuration file intentionally does **not** contain the device secret.

### Windows PowerShell

```powershell
$env:EDUMANAGE_ATTENDANCE_DEVICE_KEY="<one-time key from EduManage>"
python -m edge.attendance_connector --config .\edumanage-attendance-MAIN-GATE-01.json validate
python -m edge.attendance_connector --config .\edumanage-attendance-MAIN-GATE-01.json once
python -m edge.attendance_connector --config .\edumanage-attendance-MAIN-GATE-01.json run
```

For a permanent deployment, run the command as a Windows service using the school's normal service manager or Task Scheduler with a dedicated operating-system account. Keep the device key in that account's protected environment/secret store rather than embedding it in the command line.

### Linux / Raspberry Pi

```bash
export EDUMANAGE_ATTENDANCE_DEVICE_KEY='<one-time key from EduManage>'
python -m edge.attendance_connector --config ./edumanage-attendance-MAIN-GATE-01.json validate
python -m edge.attendance_connector --config ./edumanage-attendance-MAIN-GATE-01.json once
python -m edge.attendance_connector --config ./edumanage-attendance-MAIN-GATE-01.json run
```

A production Raspberry Pi/mini-PC deployment should run this command under `systemd` using a restricted service account and an environment file readable only by that account/root.

## Vendor bridge contract

The core connector deliberately does not embed proprietary SDK code. A vendor bridge is a small script/executable that reads new logs from the physical device or vendor software and writes canonical JSON to stdout.

EduManage passes the last successfully queued source cursor through:

```text
EDUMANAGE_EDGE_CURSOR
```

The bridge may return a simple JSON array:

```json
[
  {
    "event_id": "1001",
    "person_id": "42",
    "timestamp": "2026-08-10T07:31:04+03:00",
    "direction": "IN",
    "auth_method": "FINGERPRINT"
  }
]
```

or a cursor-aware object:

```json
{
  "events": [
    {
      "event_id": "1001",
      "person_id": "42",
      "timestamp": "2026-08-10T07:31:04+03:00"
    }
  ],
  "next_cursor": "1001"
}
```

The bridge must not calculate present/late/absent/payroll status. It only extracts machine evidence. EduManage owns attendance policy.

## Drop-directory source

For vendor software that can export JSON/JSONL files to a folder, use:

```json
{
  "type": "drop_directory",
  "name": "vendor-export-folder",
  "path": "./attendance-inbox",
  "archive_path": "./attendance-inbox/archive"
}
```

Files are moved into the archive only after their events are durably written to the local SQLite queue.

## Offline behavior

The connector uses a WAL-mode SQLite queue. Once a vendor event is queued locally:

- a school internet outage does not lose it;
- rebooting the connector computer does not lose it;
- repeated vendor reads are locally deduplicated;
- failed deliveries use bounded exponential backoff;
- EduManage's server-side event idempotency provides another replay-protection layer.

## Useful commands

Validate config and secret:

```bash
python -m edge.attendance_connector --config edge-attendance.json validate
```

Run one collection/delivery cycle:

```bash
python -m edge.attendance_connector --config edge-attendance.json once
```

View queue state:

```bash
python -m edge.attendance_connector --config edge-attendance.json status
```

Purge delivered queue rows older than 14 days:

```bash
python -m edge.attendance_connector --config edge-attendance.json purge --days 14
```

## Security boundary

- Use HTTPS for EduManage except localhost testing.
- The device key is not stored in the generated connector JSON.
- The connector only needs outbound access to EduManage.
- EduManage strips biometric template/image material from stored event evidence.
- Do not copy fingerprint/face templates into the connector queue.
- Use a dedicated OS account and restrict access to the SQLite queue and secret environment file.
- If the local machine/SDK requires a vendor password, keep that credential in the local vendor bridge secret store, not in EduManage's web configuration page.

## Device setup page

The web console calculates the tenant-specific values an administrator may need to enter into the terminal/vendor software, including:

- server/domain;
- HTTPS port;
- event endpoint/path;
- heartbeat endpoint;
- remote configuration endpoint;
- EduManage device code;
- identity namespace/timezone context;
- recommended direct-vs-edge method;
- one-time device key rotation;
- generated Edge Connector config;
- live Waiting / Online / Receiving status.

This keeps routine hardware onboarding inside the school-management UI rather than requiring VPS access.
