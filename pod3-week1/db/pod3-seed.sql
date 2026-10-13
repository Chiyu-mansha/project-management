-- Minimal POD-3 integration seed data.
-- Run after pod3-schema.sql.

BEGIN;

INSERT INTO pod3.checkin_record (
    id,
    activity_id,
    student_id,
    status,
    channel,
    idempotency_key,
    checkin_at
) VALUES (
    '10000000-0000-4000-8000-000000000001',
    '20000000-0000-4000-8000-000000000001',
    '30000000-0000-4000-8000-000000000001',
    'SUCCESS',
    'QR',
    'seed-checkin-001',
    '2026-10-13T08:00:00Z'
) ON CONFLICT DO NOTHING;

INSERT INTO pod3.credential (
    id,
    credential_no,
    checkin_id,
    activity_id,
    student_id,
    title,
    organizer_name,
    comprehensive_score,
    status,
    issued_at
) VALUES (
    '40000000-0000-4000-8000-000000000001',
    'ET-20261013-DEMO01',
    '10000000-0000-4000-8000-000000000001',
    '20000000-0000-4000-8000-000000000001',
    '30000000-0000-4000-8000-000000000001',
    '校园软件项目管理实践活动',
    '软件工程课程组',
    1.00,
    'ISSUED',
    '2026-10-13T08:00:01Z'
) ON CONFLICT DO NOTHING;

COMMIT;

