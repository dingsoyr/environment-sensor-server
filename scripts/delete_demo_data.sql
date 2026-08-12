PRAGMA foreign_keys = ON;

BEGIN IMMEDIATE;

DELETE FROM measurements
WHERE device_id = 'sensor-demo-001';

DELETE FROM devices
WHERE device_id = 'sensor-demo-001';

COMMIT;