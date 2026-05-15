-- Migration: 007_last_pinned_message_id.sql
-- Track the last pinned auto-summary message so we can unpin it before pinning a new one

ALTER TABLE auto_summary_settings ADD COLUMN last_pinned_message_id INTEGER;
