-- POD-3 formal SQLite MVP schema.
-- Production migration target is pod3-week1/db/pod3-schema.sql (PostgreSQL).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    student_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    roles TEXT NOT NULL DEFAULT '["STUDENT"]',
    organization_ids TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS activities (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    organizer_id TEXT NOT NULL,
    organizer_name TEXT,
    comprehensive_score REAL,
    status TEXT NOT NULL DEFAULT 'published',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checkin_records (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'SUCCESS' CHECK (status IN ('SUCCESS', 'CANCELLED')),
    channel TEXT NOT NULL CHECK (channel IN ('QR', 'MANUAL', 'IMPORT')),
    idempotency_key TEXT NOT NULL UNIQUE,
    checkin_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (activity_id, student_id)
);

CREATE TABLE IF NOT EXISTS credentials (
    id TEXT PRIMARY KEY,
    credential_no TEXT NOT NULL UNIQUE,
    checkin_id TEXT NOT NULL UNIQUE REFERENCES checkin_records(id),
    activity_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    title TEXT NOT NULL,
    organizer_name TEXT,
    comprehensive_score REAL,
    status TEXT NOT NULL DEFAULT 'ISSUED' CHECK (status IN ('ISSUED', 'CONFIRMED', 'SEALED', 'REVOKED')),
    issued_at TEXT NOT NULL,
    confirmed_at TEXT,
    sealed_at TEXT,
    revoked_at TEXT,
    revoke_reason TEXT,
    pdf_object_key TEXT,
    pdf_sha256 TEXT,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_credentials_student_status
    ON credentials (student_id, status, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_credentials_activity_status
    ON credentials (activity_id, status, issued_at DESC);

CREATE TABLE IF NOT EXISTS confirmation_batches (
    id TEXT PRIMARY KEY,
    activity_id TEXT NOT NULL,
    batch_no TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('CONFIRMED', 'SEALED', 'CANCELLED')),
    created_by TEXT NOT NULL,
    confirmed_by TEXT NOT NULL,
    confirmed_at TEXT NOT NULL,
    sealed_at TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS confirmation_items (
    batch_id TEXT NOT NULL REFERENCES confirmation_batches(id) ON DELETE CASCADE,
    credential_id TEXT NOT NULL REFERENCES credentials(id),
    decision TEXT NOT NULL DEFAULT 'APPROVED',
    PRIMARY KEY (batch_id, credential_id)
);

CREATE TABLE IF NOT EXISTS seal_records (
    id TEXT PRIMARY KEY,
    credential_id TEXT NOT NULL UNIQUE REFERENCES credentials(id),
    seal_id TEXT NOT NULL,
    signed_by TEXT NOT NULL,
    provider TEXT NOT NULL,
    signed_file_object_key TEXT NOT NULL,
    signed_file_sha256 TEXT NOT NULL,
    signed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS export_jobs (
    id TEXT PRIMARY KEY,
    export_type TEXT NOT NULL CHECK (export_type IN ('STUDENT_CREDENTIAL_BUNDLE', 'ORGANIZER_BONUS_LIST')),
    requester_id TEXT NOT NULL,
    student_id TEXT,
    activity_id TEXT,
    status TEXT NOT NULL DEFAULT 'SUCCEEDED' CHECK (status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED')),
    idempotency_key TEXT NOT NULL,
    file_object_key TEXT,
    file_sha256 TEXT,
    row_count INTEGER,
    expires_at TEXT,
    created_at TEXT NOT NULL,
    error_code TEXT,
    UNIQUE (requester_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL,
    actor_id TEXT,
    actor_role TEXT,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    result TEXT NOT NULL CHECK (result IN ('SUCCESS', 'FAILURE')),
    detail TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
