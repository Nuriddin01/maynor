from __future__ import annotations

from alembic import op

revision = "20260509_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("""
    CREATE TABLE users (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      telegram_id BIGINT NOT NULL UNIQUE,
      username VARCHAR(255),
      status VARCHAR(32) NOT NULL DEFAULT 'active',
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_users_telegram_id ON users (telegram_id);

    CREATE TABLE user_profiles (
      user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
      display_name VARCHAR(255),
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE user_preferences (
      user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
      timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
      language VARCHAR(8) NOT NULL DEFAULT 'ru',
      audio_preferences JSONB NOT NULL DEFAULT '[]'::jsonb,
      disliked_audio JSONB NOT NULL DEFAULT '[]'::jsonb,
      default_nap_duration INTEGER NOT NULL DEFAULT 15,
      wake_time TIME,
      target_sleep_minutes INTEGER NOT NULL DEFAULT 480,
      dnd_window JSONB NOT NULL DEFAULT '{}'::jsonb,
      reminders_enabled BOOLEAN NOT NULL DEFAULT TRUE,
      analytics_enabled BOOLEAN NOT NULL DEFAULT TRUE
    );

    CREATE TABLE user_consents (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      consent_type VARCHAR(32) NOT NULL,
      version VARCHAR(32) NOT NULL,
      accepted BOOLEAN NOT NULL,
      accepted_at TIMESTAMPTZ,
      revoked_at TIMESTAMPTZ,
      CONSTRAINT uq_user_consent_version UNIQUE (user_id, consent_type, version)
    );
    CREATE INDEX ix_user_consents_user_id ON user_consents (user_id);

    CREATE TABLE sleep_entries (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      mode VARCHAR(64) NOT NULL,
      duration_minutes INTEGER NOT NULL,
      quality INTEGER NOT NULL CHECK (quality BETWEEN 1 AND 5),
      post_wake_feeling INTEGER NOT NULL CHECK (post_wake_feeling BETWEEN 1 AND 5),
      helpfulness INTEGER NOT NULL CHECK (helpfulness BETWEEN 1 AND 5),
      audio_used VARCHAR(64) NOT NULL,
      note TEXT,
      created_at TIMESTAMPTZ NOT NULL
    );
    CREATE INDEX ix_sleep_entries_user_id_created ON sleep_entries (user_id, created_at DESC);

    CREATE TABLE session_requests (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      mode VARCHAR(64) NOT NULL,
      payload JSONB NOT NULL,
      status VARCHAR(32) NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_session_requests_user_id ON session_requests (user_id);

    CREATE TABLE recommendations (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      session_request_id UUID REFERENCES session_requests(id) ON DELETE SET NULL,
      request_mode VARCHAR(64) NOT NULL,
      recommended_mode VARCHAR(64) NOT NULL,
      duration_minutes INTEGER NOT NULL,
      audio VARCHAR(64) NOT NULL,
      snapshot JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL
    );
    CREATE INDEX ix_recommendations_user_id_created ON recommendations (user_id, created_at DESC);

    CREATE TABLE recommendation_feedback (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      recommendation_id UUID NOT NULL REFERENCES recommendations(id) ON DELETE CASCADE,
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      helpfulness INTEGER NOT NULL CHECK (helpfulness BETWEEN 1 AND 5),
      note TEXT,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE alarms (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      due_at TIMESTAMPTZ NOT NULL,
      timezone VARCHAR(64) NOT NULL,
      status VARCHAR(32) NOT NULL,
      wake_intensity VARCHAR(32) NOT NULL,
      dismiss_code_hash VARCHAR(128) NOT NULL,
      max_repeats INTEGER NOT NULL DEFAULT 3,
      repeats_done INTEGER NOT NULL DEFAULT 0,
      idempotency_key VARCHAR(128) NOT NULL UNIQUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_alarms_due_status ON alarms (status, due_at);
    CREATE INDEX ix_alarms_user_id ON alarms (user_id);

    CREATE TABLE alarm_events (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      alarm_id UUID NOT NULL REFERENCES alarms(id) ON DELETE CASCADE,
      event_type VARCHAR(64) NOT NULL,
      payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_alarm_events_alarm_id ON alarm_events (alarm_id);

    CREATE TABLE subscriptions (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      plan_code VARCHAR(64) NOT NULL,
      status VARCHAR(32) NOT NULL,
      provider VARCHAR(64) NOT NULL,
      current_period_end TIMESTAMPTZ NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      canceled_at TIMESTAMPTZ
    );
    CREATE INDEX ix_subscriptions_user_status ON subscriptions (user_id, status);

    CREATE TABLE payments (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      subscription_id UUID REFERENCES subscriptions(id) ON DELETE SET NULL,
      provider VARCHAR(64) NOT NULL,
      amount_minor INTEGER NOT NULL,
      currency VARCHAR(8) NOT NULL,
      status VARCHAR(32) NOT NULL,
      idempotency_key VARCHAR(128) NOT NULL,
      payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      CONSTRAINT uq_payment_provider_idempotency UNIQUE (provider, idempotency_key)
    );
    CREATE INDEX ix_payments_user_status ON payments (user_id, status);

    CREATE TABLE premium_entitlements (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      feature VARCHAR(64) NOT NULL,
      valid_until TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_premium_entitlements_user_feature ON premium_entitlements (user_id, feature);

    CREATE TABLE analytics_events (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      user_id UUID REFERENCES users(id) ON DELETE SET NULL,
      name VARCHAR(64) NOT NULL,
      properties JSONB NOT NULL DEFAULT '{}'::jsonb,
      occurred_at TIMESTAMPTZ NOT NULL
    );
    CREATE INDEX ix_analytics_events_name_time ON analytics_events (name, occurred_at DESC);
    CREATE INDEX ix_analytics_events_user_id ON analytics_events (user_id);

    CREATE TABLE content_items (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      slug VARCHAR(128) NOT NULL UNIQUE,
      title VARCHAR(255) NOT NULL,
      language VARCHAR(8) NOT NULL,
      type VARCHAR(64) NOT NULL,
      body TEXT NOT NULL,
      audio_type VARCHAR(64) NOT NULL,
      premium BOOLEAN NOT NULL DEFAULT FALSE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_content_items_language ON content_items (language);

    CREATE TABLE content_tags (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      content_item_id UUID NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
      tag VARCHAR(64) NOT NULL
    );
    CREATE INDEX ix_content_tags_tag ON content_tags (tag);

    CREATE TABLE experiment_flags (
      key VARCHAR(128) PRIMARY KEY,
      enabled BOOLEAN NOT NULL DEFAULT FALSE,
      payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE admin_users (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      email VARCHAR(255) NOT NULL UNIQUE,
      password_hash VARCHAR(255) NOT NULL,
      role VARCHAR(64) NOT NULL,
      active BOOLEAN NOT NULL DEFAULT TRUE,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE audit_logs (
      id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
      actor_admin_id UUID REFERENCES admin_users(id) ON DELETE SET NULL,
      action VARCHAR(128) NOT NULL,
      entity_type VARCHAR(64) NOT NULL,
      entity_id VARCHAR(128),
      payload JSONB NOT NULL DEFAULT '{}'::jsonb,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_audit_logs_action_time ON audit_logs (action, created_at DESC);
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE IF EXISTS audit_logs;
    DROP TABLE IF EXISTS admin_users;
    DROP TABLE IF EXISTS experiment_flags;
    DROP TABLE IF EXISTS content_tags;
    DROP TABLE IF EXISTS content_items;
    DROP TABLE IF EXISTS analytics_events;
    DROP TABLE IF EXISTS premium_entitlements;
    DROP TABLE IF EXISTS payments;
    DROP TABLE IF EXISTS subscriptions;
    DROP TABLE IF EXISTS alarm_events;
    DROP TABLE IF EXISTS alarms;
    DROP TABLE IF EXISTS recommendation_feedback;
    DROP TABLE IF EXISTS recommendations;
    DROP TABLE IF EXISTS session_requests;
    DROP TABLE IF EXISTS sleep_entries;
    DROP TABLE IF EXISTS user_consents;
    DROP TABLE IF EXISTS user_preferences;
    DROP TABLE IF EXISTS user_profiles;
    DROP TABLE IF EXISTS users;
    """)
