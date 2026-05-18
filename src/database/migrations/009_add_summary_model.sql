-- Migration: 009_add_summary_model.sql
-- Add summary_model and summary_provider_id to auto_summary_settings

ALTER TABLE auto_summary_settings ADD COLUMN summary_model TEXT;
ALTER TABLE auto_summary_settings ADD COLUMN summary_provider_id INTEGER;
