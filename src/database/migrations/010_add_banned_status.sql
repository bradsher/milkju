-- Add is_banned column to users table
ALTER TABLE users ADD COLUMN is_banned BOOLEAN DEFAULT 0;
