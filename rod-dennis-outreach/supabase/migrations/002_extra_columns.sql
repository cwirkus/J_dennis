-- Add columns to inbound_messages for email reply thread context
ALTER TABLE inbound_messages
  ADD COLUMN IF NOT EXISTS high_priority    boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS prospect_org     text,
  ADD COLUMN IF NOT EXISTS original_subject text,
  ADD COLUMN IF NOT EXISTS original_body    text;

-- Widen social_drafts platform constraint to include instagram
ALTER TABLE social_drafts
  DROP CONSTRAINT IF EXISTS social_drafts_platform_check;

ALTER TABLE social_drafts
  ADD CONSTRAINT social_drafts_platform_check
  CHECK (platform IN ('linkedin', 'twitter', 'instagram'));
