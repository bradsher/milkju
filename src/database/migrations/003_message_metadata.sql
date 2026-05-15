-- Add message metadata for better tracking and URL generation
-- Migration: 003_message_metadata.sql

-- Add new columns to conversations table
ALTER TABLE conversations ADD COLUMN sender_id INTEGER;           -- 发送者的Telegram数字ID
ALTER TABLE conversations ADD COLUMN sender_username TEXT;        -- 发送者的@username（可选）
ALTER TABLE conversations ADD COLUMN sender_first_name TEXT;      -- 发送者的名字（快照）
ALTER TABLE conversations ADD COLUMN sender_full_name TEXT;       -- 发送者的全名（快照）

ALTER TABLE conversations ADD COLUMN chat_id INTEGER;             -- 消息所属的chat_id
ALTER TABLE conversations ADD COLUMN chat_type TEXT;              -- 聊天类型：private/group/supergroup/channel
ALTER TABLE conversations ADD COLUMN chat_username TEXT;          -- 公开群组/频道的@username

ALTER TABLE conversations ADD COLUMN is_forwarded BOOLEAN DEFAULT 0;         -- 是否为转发消息
ALTER TABLE conversations ADD COLUMN forward_from_id INTEGER;                -- 原始发送者ID
ALTER TABLE conversations ADD COLUMN forward_from_username TEXT;             -- 原始发送者username
ALTER TABLE conversations ADD COLUMN forward_from_name TEXT;                 -- 原始发送者名字
ALTER TABLE conversations ADD COLUMN forward_date DATETIME;                  -- 原始消息的发送时间

ALTER TABLE conversations ADD COLUMN reply_to_message_id INTEGER;            -- 回复的消息ID（Telegram message_id）
ALTER TABLE conversations ADD COLUMN reply_to_user_id INTEGER;               -- 被回复消息的发送者ID

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_conversations_sender_id ON conversations(sender_id);
CREATE INDEX IF NOT EXISTS idx_conversations_chat_id ON conversations(chat_id);
CREATE INDEX IF NOT EXISTS idx_conversations_is_forwarded ON conversations(is_forwarded);
CREATE INDEX IF NOT EXISTS idx_conversations_reply_to_message_id ON conversations(reply_to_message_id);
