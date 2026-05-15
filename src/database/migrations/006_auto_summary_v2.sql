-- Migration: 006_auto_summary_v2.sql
-- Extend auto_summary_settings to support:
--   - A second time slot (time2_hour, time2_minute)
--   - Optional message pinning (pin_enabled)
--   - Slot-based run tracking (last_run_slot) to support two triggers per day

ALTER TABLE auto_summary_settings ADD COLUMN time2_hour INTEGER;
ALTER TABLE auto_summary_settings ADD COLUMN time2_minute INTEGER;
ALTER TABLE auto_summary_settings ADD COLUMN pin_enabled BOOLEAN DEFAULT 0;
ALTER TABLE auto_summary_settings ADD COLUMN last_run_slot TEXT;
