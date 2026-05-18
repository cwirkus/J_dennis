-- Rod Dennis Outreach System — Initial Schema

CREATE TABLE prospects (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text,
  organization    text,
  category        text,
  country         text,
  email           text,
  phone           text,
  website         text,
  priority        int DEFAULT 2,
  status          text DEFAULT 'not_contacted',
  notes           text,
  date_contacted  timestamptz,
  last_activity   timestamptz,
  source          text DEFAULT 'master_import',
  hunter_source   text,
  created_at      timestamptz DEFAULT now()
);

CREATE TABLE outreach_drafts (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  prospect_id  uuid REFERENCES prospects(id) ON DELETE CASCADE,
  subject      text,
  body         text,
  status       text DEFAULT 'pending',
  approved_at  timestamptz,
  sent_at      timestamptz,
  opened       bool DEFAULT false,
  replied      bool DEFAULT false,
  created_at   timestamptz DEFAULT now()
);

CREATE TABLE social_drafts (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  platform       text CHECK (platform IN ('linkedin', 'twitter')),
  content        text,
  trigger_event  text,
  status         text DEFAULT 'pending',
  approved_at    timestamptz,
  created_at     timestamptz DEFAULT now()
);

CREATE TABLE inbound_messages (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sender_name    text,
  sender_email   text,
  channel        text,
  message        text,
  draft_response text,
  status         text DEFAULT 'pending',
  sent_at        timestamptz,
  created_at     timestamptz DEFAULT now()
);

CREATE TABLE discovery_log (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source           text,
  prospects_found  int,
  prospects_added  int,
  run_at           timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX idx_prospects_status      ON prospects(status);
CREATE INDEX idx_prospects_priority    ON prospects(priority);
CREATE INDEX idx_prospects_country     ON prospects(country);
CREATE INDEX idx_outreach_drafts_status       ON outreach_drafts(status);
CREATE INDEX idx_outreach_drafts_prospect_id  ON outreach_drafts(prospect_id);
