-- Candidate Isolation Implementation Migration
-- Date: 2026-08-16
-- Purpose: Add candidate BU isolation columns for zero-hardcoding compliance

-- Add isolation columns to candidates table
ALTER TABLE candidates ADD COLUMN (
    submission_bu_id VARCHAR(36) REFERENCES business_units(id) ON DELETE SET NULL,
    associated_bu_id VARCHAR(36) REFERENCES business_units(id) ON DELETE SET NULL,
    submission_timestamp TIMESTAMP DEFAULT NULL
);

-- Create indexes for fast queries
CREATE INDEX idx_candidates_submission_bu ON candidates(submission_bu_id);
CREATE INDEX idx_candidates_associated_bu ON candidates(associated_bu_id);
CREATE INDEX idx_candidates_isolation_status ON candidates(associated_bu_id, submission_timestamp DESC);

-- Migration strategy for existing candidates:
-- - All existing candidates start as UNASSOCIATED (NULL values)
-- - They remain visible to all HR users until explicitly submitted to a BU
-- - Once submitted, they are LOCKED to that BU permanently
-- - This preserves existing behavior while enabling new isolation rules

-- Verification query (run after migration):
-- SELECT
--   COUNT(*) as total_candidates,
--   COUNT(CASE WHEN associated_bu_id IS NULL THEN 1 END) as unassociated,
--   COUNT(CASE WHEN associated_bu_id IS NOT NULL THEN 1 END) as associated
-- FROM candidates;

-- Expected output after migration:
-- total_candidates | unassociated | associated
-- ALL_ROWS         | ALL_ROWS     | 0

-- This confirms all existing candidates start unassociated and visible to all HR
