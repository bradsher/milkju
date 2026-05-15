-- File attachments for document processing
-- Migration: 002_file_attachments.sql

CREATE TABLE IF NOT EXISTS file_attachments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    file_id TEXT NOT NULL,
    file_unique_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    caption TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for file management queries
CREATE INDEX IF NOT EXISTS idx_file_attachments_chat_id ON file_attachments(chat_id);
CREATE INDEX IF NOT EXISTS idx_file_attachments_created_at ON file_attachments(created_at);
CREATE INDEX IF NOT EXISTS idx_file_attachments_file_size ON file_attachments(file_size);
CREATE INDEX IF NOT EXISTS idx_file_attachments_user_id ON file_attachments(user_id);
