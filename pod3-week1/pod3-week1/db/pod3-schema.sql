-- POD-3 credential management schema v1.0
-- Target: PostgreSQL 15+

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS pod3;

CREATE TABLE IF NOT EXISTS pod3.checkin_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_id UUID NOT NULL,
    student_id UUID NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'SUCCESS'
        CHECK (status IN ('SUCCESS', 'CANCELLED')),
    channel VARCHAR(16) NOT NULL DEFAULT 'QR'
        CHECK (channel IN ('QR', 'MANUAL', 'IMPORT')),
    idempotency_key VARCHAR(128) NOT NULL,
    operator_id UUID,
    checkin_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMPTZ,
    cancel_reason VARCHAR(500),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_checkin_idempotency UNIQUE (idempotency_key),
    CONSTRAINT ck_checkin_cancelled_fields CHECK (
        (status = 'SUCCESS' AND cancelled_at IS NULL)
        OR (status = 'CANCELLED' AND cancelled_at IS NOT NULL)
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_checkin_active_student_activity
    ON pod3.checkin_record (activity_id, student_id)
    WHERE status = 'SUCCESS';

CREATE INDEX IF NOT EXISTS idx_checkin_activity_time
    ON pod3.checkin_record (activity_id, checkin_at DESC);

CREATE INDEX IF NOT EXISTS idx_checkin_student_time
    ON pod3.checkin_record (student_id, checkin_at DESC);

CREATE TABLE IF NOT EXISTS pod3.credential (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    credential_no VARCHAR(64) NOT NULL,
    checkin_id UUID NOT NULL REFERENCES pod3.checkin_record(id),
    activity_id UUID NOT NULL,
    student_id UUID NOT NULL,
    title VARCHAR(200) NOT NULL,
    organizer_name VARCHAR(200),
    comprehensive_score NUMERIC(6,2)
        CHECK (comprehensive_score IS NULL OR comprehensive_score >= 0),
    status VARCHAR(16) NOT NULL DEFAULT 'ISSUED'
        CHECK (status IN ('ISSUED', 'CONFIRMED', 'SEALED', 'REVOKED')),
    issued_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMPTZ,
    sealed_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoke_reason VARCHAR(500),
    pdf_object_key VARCHAR(500),
    pdf_sha256 CHAR(64),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_credential_no UNIQUE (credential_no),
    CONSTRAINT uq_credential_checkin UNIQUE (checkin_id),
    CONSTRAINT ck_credential_sealed_file CHECK (
        status <> 'SEALED'
        OR (sealed_at IS NOT NULL AND pdf_object_key IS NOT NULL AND pdf_sha256 IS NOT NULL)
    ),
    CONSTRAINT ck_credential_revoked_fields CHECK (
        status <> 'REVOKED'
        OR (revoked_at IS NOT NULL AND revoke_reason IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_credential_student_status
    ON pod3.credential (student_id, status, issued_at DESC);

CREATE INDEX IF NOT EXISTS idx_credential_activity_status
    ON pod3.credential (activity_id, status, issued_at DESC);

CREATE TABLE IF NOT EXISTS pod3.confirmation_batch (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_id UUID NOT NULL,
    batch_no VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT', 'CONFIRMED', 'SEALED', 'CANCELLED')),
    created_by UUID NOT NULL,
    confirmed_by UUID,
    confirmed_at TIMESTAMPTZ,
    sealed_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    note VARCHAR(1000),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_confirmation_batch_no UNIQUE (batch_no),
    CONSTRAINT ck_confirmation_confirmed_fields CHECK (
        status NOT IN ('CONFIRMED', 'SEALED')
        OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_confirmation_batch_activity
    ON pod3.confirmation_batch (activity_id, created_at DESC);

CREATE TABLE IF NOT EXISTS pod3.confirmation_item (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES pod3.confirmation_batch(id) ON DELETE CASCADE,
    credential_id UUID NOT NULL REFERENCES pod3.credential(id),
    decision VARCHAR(16) NOT NULL DEFAULT 'APPROVED'
        CHECK (decision IN ('APPROVED', 'REJECTED')),
    reason VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_confirmation_item UNIQUE (batch_id, credential_id),
    CONSTRAINT ck_rejected_reason CHECK (decision <> 'REJECTED' OR reason IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_confirmation_item_credential
    ON pod3.confirmation_item (credential_id);

CREATE TABLE IF NOT EXISTS pod3.seal_record (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id UUID NOT NULL REFERENCES pod3.confirmation_batch(id),
    seal_id UUID NOT NULL,
    signed_by UUID NOT NULL,
    provider VARCHAR(64) NOT NULL DEFAULT 'PENDING_ADAPTER',
    provider_request_id VARCHAR(128),
    signed_file_object_key VARCHAR(500) NOT NULL,
    signed_file_sha256 CHAR(64) NOT NULL,
    signed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_seal_batch UNIQUE (batch_id)
);

CREATE INDEX IF NOT EXISTS idx_seal_signed_by_time
    ON pod3.seal_record (signed_by, signed_at DESC);

CREATE TABLE IF NOT EXISTS pod3.export_job (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    export_type VARCHAR(32) NOT NULL
        CHECK (export_type IN ('STUDENT_CREDENTIAL_BUNDLE', 'ORGANIZER_BONUS_LIST')),
    requester_id UUID NOT NULL,
    student_id UUID,
    activity_id UUID,
    status VARCHAR(16) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING', 'PROCESSING', 'SUCCEEDED', 'FAILED')),
    idempotency_key VARCHAR(128) NOT NULL,
    filters JSONB NOT NULL DEFAULT '{}'::jsonb,
    file_object_key VARCHAR(500),
    file_sha256 CHAR(64),
    row_count INTEGER CHECK (row_count IS NULL OR row_count >= 0),
    expires_at TIMESTAMPTZ,
    error_code VARCHAR(64),
    error_message VARCHAR(1000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    CONSTRAINT uq_export_idempotency UNIQUE (requester_id, idempotency_key),
    CONSTRAINT ck_export_scope CHECK (
        (export_type = 'STUDENT_CREDENTIAL_BUNDLE' AND student_id IS NOT NULL AND activity_id IS NULL)
        OR
        (export_type = 'ORGANIZER_BONUS_LIST' AND activity_id IS NOT NULL AND student_id IS NULL)
    ),
    CONSTRAINT ck_export_success_file CHECK (
        status <> 'SUCCEEDED'
        OR (file_object_key IS NOT NULL AND file_sha256 IS NOT NULL AND expires_at IS NOT NULL)
    ),
    CONSTRAINT ck_export_failed_error CHECK (
        status <> 'FAILED' OR error_code IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_export_requester_time
    ON pod3.export_job (requester_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_export_pending
    ON pod3.export_job (created_at)
    WHERE status IN ('PENDING', 'PROCESSING');

CREATE TABLE IF NOT EXISTS pod3.audit_log (
    id BIGSERIAL PRIMARY KEY,
    request_id VARCHAR(128) NOT NULL,
    actor_id UUID,
    actor_role VARCHAR(32),
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(128) NOT NULL,
    result VARCHAR(16) NOT NULL CHECK (result IN ('SUCCESS', 'FAILURE')),
    ip_address INET,
    user_agent VARCHAR(500),
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_resource_time
    ON pod3.audit_log (resource_type, resource_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_actor_time
    ON pod3.audit_log (actor_id, created_at DESC);

COMMIT;

