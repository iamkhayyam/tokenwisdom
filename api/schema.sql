-- Token Wisdom corpus schema

CREATE TABLE IF NOT EXISTS tags (
  id VARCHAR(32) PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL UNIQUE,
  description TEXT,
  feature_image TEXT,
  accent_color VARCHAR(16),
  url TEXT
);

CREATE TABLE IF NOT EXISTS posts (
  id VARCHAR(32) PRIMARY KEY,
  uuid VARCHAR(36),
  title VARCHAR(512) NOT NULL,
  slug VARCHAR(512) NOT NULL UNIQUE,
  html LONGTEXT,
  plaintext LONGTEXT,
  excerpt TEXT,
  custom_excerpt TEXT,
  feature_image TEXT,
  featured TINYINT(1) DEFAULT 0,
  visibility VARCHAR(32) DEFAULT 'public',
  reading_time INT,
  published_at DATETIME,
  created_at DATETIME,
  updated_at DATETIME,
  url TEXT,
  meta_title VARCHAR(512),
  meta_description TEXT
);

CREATE TABLE IF NOT EXISTS post_tags (
  post_id VARCHAR(32) NOT NULL,
  tag_id VARCHAR(32) NOT NULL,
  sort_order INT DEFAULT 0,
  PRIMARY KEY (post_id, tag_id),
  FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
  FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS terms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255) NOT NULL UNIQUE,
  category VARCHAR(128),
  color VARCHAR(64),
  definition TEXT,
  edition_count INT DEFAULT 0,
  first_edition INT,
  first_date DATE,
  first_slug VARCHAR(512),
  latest_edition INT,
  latest_date DATE,
  latest_slug VARCHAR(512)
);

CREATE TABLE IF NOT EXISTS term_definition_history (
  id INT AUTO_INCREMENT PRIMARY KEY,
  term_id INT NOT NULL,
  text TEXT NOT NULL,
  edition INT NOT NULL,
  date DATE,
  slug VARCHAR(512),
  FOREIGN KEY (term_id) REFERENCES terms(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS term_editions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  term_id INT NOT NULL,
  edition INT NOT NULL,
  week INT,
  date DATE,
  slug VARCHAR(512),
  title VARCHAR(512),
  source VARCHAR(64),
  FOREIGN KEY (term_id) REFERENCES terms(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS term_timeline (
  id INT AUTO_INCREMENT PRIMARY KEY,
  term_id INT NOT NULL,
  period VARCHAR(16) NOT NULL,
  count INT DEFAULT 0,
  FOREIGN KEY (term_id) REFERENCES terms(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS term_related (
  id INT AUTO_INCREMENT PRIMARY KEY,
  term_id INT NOT NULL,
  related_slug VARCHAR(255) NOT NULL,
  related_name VARCHAR(255),
  related_color VARCHAR(64),
  shared_count INT DEFAULT 0,
  FOREIGN KEY (term_id) REFERENCES terms(id) ON DELETE CASCADE
);

CREATE INDEX idx_terms_category ON terms(category);
CREATE INDEX idx_terms_color ON terms(color);
CREATE INDEX idx_term_editions_edition ON term_editions(edition);
CREATE INDEX idx_posts_published ON posts(published_at);
CREATE INDEX idx_term_related_slug ON term_related(related_slug);

-- ============================================================
-- Community layer: members, magic-link auth, annotations
-- (highlights, private notes, public responses) — self-hosted.
-- ============================================================

CREATE TABLE IF NOT EXISTS members (
  id           VARCHAR(36) PRIMARY KEY,
  email        VARCHAR(320) NOT NULL UNIQUE,
  display_name VARCHAR(120),
  avatar_color VARCHAR(16),
  role         ENUM('member','admin') NOT NULL DEFAULT 'member',
  status       ENUM('active','blocked') NOT NULL DEFAULT 'active',
  trust        ENUM('new','trusted') NOT NULL DEFAULT 'new',
  created_at   DATETIME NOT NULL,
  verified_at  DATETIME
);

-- Single-use magic links. We store only a SHA-256 hash of the token.
CREATE TABLE IF NOT EXISTS auth_tokens (
  token_hash CHAR(64) PRIMARY KEY,
  member_id  VARCHAR(36) NOT NULL,
  expires_at DATETIME NOT NULL,
  used_at    DATETIME,
  FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

-- Bearer sessions. Client holds the raw token; we store its hash.
CREATE TABLE IF NOT EXISTS sessions (
  token_hash CHAR(64) PRIMARY KEY,
  member_id  VARCHAR(36) NOT NULL,
  created_at DATETIME NOT NULL,
  expires_at DATETIME NOT NULL,
  last_seen  DATETIME,
  FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS annotations (
  id         VARCHAR(36) PRIMARY KEY,
  post_slug  VARCHAR(512) NOT NULL,
  member_id  VARCHAR(36) NOT NULL,
  kind       ENUM('highlight','note','response','article_response','question') NOT NULL,
  body       TEXT,
  privacy    ENUM('private','public') NOT NULL DEFAULT 'private',
  parent_id  VARCHAR(36),
  anchor     JSON,
  status     ENUM('visible','pending','hidden','spam') NOT NULL DEFAULT 'visible',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_id) REFERENCES annotations(id) ON DELETE CASCADE
);

CREATE INDEX idx_annotations_post   ON annotations(post_slug, status);
CREATE INDEX idx_annotations_member ON annotations(member_id);
CREATE INDEX idx_annotations_parent ON annotations(parent_id);
CREATE INDEX idx_sessions_member    ON sessions(member_id);
CREATE INDEX idx_auth_tokens_member ON auth_tokens(member_id);

-- Idempotent: adds the 'question' kind (AMA) to any pre-existing annotations
-- table. Re-running is a harmless no-op once the enum already matches.
ALTER TABLE annotations
  MODIFY COLUMN kind ENUM('highlight','note','response','article_response','question') NOT NULL;
