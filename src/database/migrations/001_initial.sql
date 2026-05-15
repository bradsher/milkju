-- Initial schema for TeleChat
-- Migration: 001_initial.sql

-- Config table
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    is_admin BOOLEAN DEFAULT 0
);

-- Conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    role TEXT,
    content TEXT,
    message_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Providers table
CREATE TABLE IF NOT EXISTS providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    base_url TEXT,
    is_active BOOLEAN DEFAULT 1,
    client_type TEXT DEFAULT 'openai'
);

-- Provider models table
CREATE TABLE IF NOT EXISTS provider_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER,
    model TEXT,
    FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE CASCADE,
    UNIQUE(provider_id, model)
);

-- API keys table
CREATE TABLE IF NOT EXISTS api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_id INTEGER,
    key TEXT,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE CASCADE
);

-- Chat settings table
CREATE TABLE IF NOT EXISTS chat_settings (
    chat_id INTEGER PRIMARY KEY,
    system_prompt TEXT,
    model TEXT,
    provider_id INTEGER,
    FOREIGN KEY(provider_id) REFERENCES providers(id) ON DELETE SET NULL
);

-- Auto-summary settings table
CREATE TABLE IF NOT EXISTS auto_summary_settings (
    chat_id INTEGER PRIMARY KEY,
    enabled BOOLEAN DEFAULT 0,
    hour INTEGER,
    minute INTEGER,
    language TEXT,
    last_run_date TEXT
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp);
CREATE INDEX IF NOT EXISTS idx_provider_models_provider_id ON provider_models(provider_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_provider_id ON api_keys(provider_id);
