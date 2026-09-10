-- Migration: Add CYCLE 19 Queue Handler Columns
-- Purpose: Add 4 new columns to ChannelQueueItem for delayed messages, handler timing, and deduplication
-- Execution: psql -U app_user -d wros_dev -f migrate_add_queue_columns.sql
-- Rollback: See end of file

-- Add columns if they don't exist (PostgreSQL 9.6+)
ALTER TABLE channel_queue_item
  ADD COLUMN IF NOT EXISTS last_attempted_at TIMESTAMP NULL DEFAULT NULL;

ALTER TABLE channel_queue_item
  ADD COLUMN IF NOT EXISTS scheduled_for TIMESTAMP NULL DEFAULT NULL;

ALTER TABLE channel_queue_item
  ADD COLUMN IF NOT EXISTS handler_duration_ms INTEGER NULL DEFAULT NULL;

ALTER TABLE channel_queue_item
  ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255) NULL DEFAULT NULL;

-- Create index on scheduled_for for efficient delayed message queries
-- Used by queue processor: SELECT ... WHERE status='SCHEDULED' AND scheduled_for <= NOW()
CREATE INDEX IF NOT EXISTS idx_channel_queue_scheduled_for
  ON channel_queue_item (scheduled_for)
  WHERE status = 'SCHEDULED';

-- Create index on idempotency_key for deduplication queries
-- Used by job_creation_flash_handler: SELECT ... WHERE idempotency_key = ?
CREATE INDEX IF NOT EXISTS idx_channel_queue_idempotency_key
  ON channel_queue_item (idempotency_key)
  WHERE idempotency_key IS NOT NULL;

-- Create index on last_attempted_at for handler monitoring
-- Used by metrics and alerting: SELECT ... WHERE last_attempted_at > ?
CREATE INDEX IF NOT EXISTS idx_channel_queue_last_attempted_at
  ON channel_queue_item (last_attempted_at)
  WHERE last_attempted_at IS NOT NULL;

-- Verify migration
SELECT
  column_name,
  data_type,
  is_nullable
FROM information_schema.columns
WHERE table_name = 'channel_queue_item'
  AND column_name IN ('last_attempted_at', 'scheduled_for', 'handler_duration_ms', 'idempotency_key')
ORDER BY ordinal_position;

-- ROLLBACK SCRIPT (if needed):
-- Run this to undo the migration:
--
-- DROP INDEX IF EXISTS idx_channel_queue_scheduled_for;
-- DROP INDEX IF EXISTS idx_channel_queue_idempotency_key;
-- DROP INDEX IF EXISTS idx_channel_queue_last_attempted_at;
-- ALTER TABLE channel_queue_item DROP COLUMN IF EXISTS last_attempted_at;
-- ALTER TABLE channel_queue_item DROP COLUMN IF EXISTS scheduled_for;
-- ALTER TABLE channel_queue_item DROP COLUMN IF EXISTS handler_duration_ms;
-- ALTER TABLE channel_queue_item DROP COLUMN IF EXISTS idempotency_key;
