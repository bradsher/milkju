-- Migration: 008_add_message_ids.sql
ALTER TABLE conversations ADD COLUMN message_ids TEXT;
