-- Author presets for NovelAI image generation
-- Migration: 005_author_presets.sql
-- Stores author strings (artist tags, styles) as named presets.
-- Only the preset creator can view the actual content.

CREATE TABLE IF NOT EXISTS author_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    content TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_author_presets_name ON author_presets(name);
CREATE INDEX IF NOT EXISTS idx_author_presets_created_by ON author_presets(created_by);
