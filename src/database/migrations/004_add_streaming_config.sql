-- Migration 004: Add streaming update interval configuration
-- Created: 2025-12-21
-- Purpose: Allow super admins to configure the interval between streaming message updates

-- Add streaming update interval to config table
ALTER TABLE config ADD COLUMN streaming_update_interval REAL DEFAULT 3.5;

-- Default: 3.5 seconds (safe for Telegram's 20 msg/min limit in groups)
-- Range: 2.0 - 10.0 seconds
-- Telegram official recommendation: ≥3 seconds for groups (20 messages/minute limit)
