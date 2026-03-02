# Changelog

All notable changes to engram will be documented here.

Format: [Semantic Versioning](https://semver.org). Types: `Added`, `Fixed`, `Changed`, `Removed`.

---

## [0.1.1] — 2026-03-03

### Fixed
- **Critical:** Fixed package name mismatch in version check (`engram-cli` → `engram-shell`)
- **Critical:** Fixed zsh hook syntax error (missing space before `]]`)
- **Critical:** Fixed shell argument handling when no shell specified
- Fixed database connection handling with proper context managers and automatic commit/rollback
- Fixed potential data loss in PTY wrapper by using non-daemon threads with graceful shutdown
- Fixed connection string redaction to properly preserve URL structure
- Fixed bare `passwd` command not being detected as sensitive
- Fixed GitHub token redaction in git clone URLs
- Fixed silent pip install failures in install script

### Added
- Database connection timeout (10 seconds) to prevent lockups
- Database indexes on `exit_code` and `command` columns for faster queries
- Configuration validation on startup (checks OLLAMA_HOST format and directory permissions)
- Error handling in all shell hooks (checks if `engram` command exists)
- Comprehensive error messages for embedding failures (connection, timeout, model not found)
- Detailed logging for corrupted embeddings with repair suggestions
- 11 additional redaction patterns: Slack tokens/webhooks, Stripe keys, JWT tokens, Heroku keys, Mailgun keys, Twilio keys, Square tokens, PayPal tokens, DigitalOcean tokens, Docker tokens, NPM tokens
- Type hints and docstrings for all CLI commands and core functions
- Automatic Claude model fallback (tries multiple versions for compatibility)
- MANIFEST.in for proper package distribution

### Changed
- Improved LLM max_tokens from 1024 to 2048 for better responses
- Enhanced database connection pooling with context managers
- Better error messages throughout with actionable guidance
- Shell hooks now fail gracefully if engram command is not available

---

## [0.1.0] — 2025-06-01

### Added
- Initial release
- Shell hooks for bash, zsh, and fish (lightweight command logging)
- `engram shell` — PTY wrapper for full command + output capture, including interactive programs
- `engram ask` — natural language Q&A over your terminal history via local Ollama or Anthropic API
- `engram install` — automatically adds the shell hook to your RC file
- `engram history` — pretty-print recent logged commands
- `engram search` — full-text search across commands and output
- `engram index` — embed un-indexed commands into vector store for semantic search
- `engram status` — show DB stats, Ollama health, and current config
- `engram clear` — delete all stored history with confirmation prompt
- SQLite storage with vector embeddings via Ollama `nomic-embed-text`
- Cosine similarity search with graceful fallback to full-text search when Ollama is unavailable
- Automatic secret redaction (API keys, tokens, passwords, connection strings) before storage
- Support for Ollama (local, default) and Anthropic Claude (via `ANTHROPIC_API_KEY`)
- Streaming LLM responses for both backends
- macOS and Linux support
- MIT license
