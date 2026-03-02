# Changelog

All notable changes to engram will be documented here.

Format: [Semantic Versioning](https://semver.org). Types: `Added`, `Fixed`, `Changed`, `Removed`.

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
