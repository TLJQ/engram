<div align="center">

# engram 🧠

**Eidetic memory for your terminal.**

[![Tests](https://github.com/TLJQ/engram/actions/workflows/test.yml/badge.svg)](https://github.com/TLJQ/engram/actions/workflows/test.yml)
[![PyPI version](https://badge.fury.io/py/engram-cli.svg)](https://badge.fury.io/py/engram-cli)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

engram silently logs every command you run — and its **output** — into a local SQLite database on your machine. When you need to remember what happened, just ask in plain English.

```
$ engram ask "what was the docker error I got yesterday building the frontend?"

The build failed at 14:32 in /home/titus/projects/acme-app with:

  Error response from daemon: failed to solve: failed to read
  dockerfile: open Dockerfile: no such file or directory

You were in the wrong directory. The Dockerfile lives one level up.
Fix: cd .. && docker build -f acme-app/Dockerfile .
```

**Everything stays on your machine. No cloud. No subscriptions. No data leaves your computer** (unless you explicitly set an Anthropic API key, in which case only the relevant context snippets are sent — never your full history).

---

## The problem

Standard terminal history (`Ctrl+R`, `history`) only saves the *commands* you typed. The **output** — the error message, the API response, the build log — disappears the moment it scrolls off screen.

engram fixes that.

---

## Features

| | |
|---|---|
| 📼 **Full capture** | Command, stdout, stderr, exit code, working directory, timestamp |
| 🤖 **AI-powered search** | Ask questions in plain English, get answers grounded in your actual history |
| 🏠 **100% local by default** | SQLite in `~/.engram/`, works with [Ollama](https://ollama.com) |
| ⚡ **Zero-latency** | Logging is async — your shell prompt never slows down |
| 🔒 **Secret redaction** | API keys, tokens, and passwords are scrubbed before storage |
| 🐚 **bash, zsh, fish** | Shell hooks for all three |
| 🖥️ **Linux + macOS** | Full support for both |

---

## How to record a demo GIF (for contributors)

> **For first-time setup:** record your own demo using `asciinema`:
> ```bash
> pip install asciinema
> asciinema rec demo.cast
> # run some commands, then: engram ask "what error did I just get?"
> # exit the recording with Ctrl+D
> # convert to GIF: npm install -g svg-term-cli && cat demo.cast | svg-term --out demo.svg
> ```
> Then add `![demo](demo.svg)` right here in the README.

---

## Quick start

### 1. Install

```bash
# One-liner (recommended):
curl -sSL https://raw.githubusercontent.com/TLJQ/engram/main/scripts/install.sh | bash
```

Or with pip:

```bash
pip install engram-cli
engram install          # adds the shell hook to your RC file automatically
```

### 2. Restart your terminal

```bash
# Or source the hook manually:
source ~/.engram/engram.zsh    # zsh
source ~/.engram/engram.bash   # bash
```

### 3. Install Ollama for local AI

```bash
# Install from https://ollama.com, then:
ollama pull nomic-embed-text   # for semantic search
ollama pull llama3             # for answering questions
ollama serve                   # start the server (or it starts automatically)
```

### 4. Start capturing

```bash
# Lightweight mode (commands only, no output):
# Just use your terminal normally — the hook is already active.

# Full mode (commands + output, including interactive programs):
engram shell
```

### 5. Ask questions

```bash
engram ask "what curl command did I use to hit the auth API last week?"
engram ask "show me the last time a pip install failed and why"
engram ask "what was the JSON response I got from the Stripe API this morning?"
engram ask "what docker containers did I start yesterday?"
```

---

## All commands

| Command | What it does |
|---|---|
| `engram shell` | Launch your shell inside the PTY wrapper — captures full output |
| `engram ask "<question>"` | Ask a natural language question about your history |
| `engram install` | Add the shell hook to your RC file |
| `engram history` | Print recent logged commands |
| `engram search "<query>"` | Full-text search across commands and output |
| `engram index` | Embed un-indexed commands (run after first install or after `ollama serve`) |
| `engram status` | Show DB stats and configuration |
| `engram clear` | Delete all stored history (with confirmation) |

### Flags

```bash
engram ask "..." --top-k 10     # use more context chunks (default: 5)
engram ask "..." --verbose      # show which context was retrieved
engram history --limit 100      # show last 100 commands (default: 50)
engram index --reindex          # re-embed everything, not just new commands
engram clear --yes              # skip the confirmation prompt
```

---

## Two capture modes

### Lightweight hook (default after `engram install`)

Captures: **commands + exit codes + working directory**.  
Does NOT capture output. Works everywhere. Zero risk of breaking interactive programs.

Add to your `~/.zshrc` / `~/.bashrc`:
```bash
source ~/.engram/engram.zsh   # or engram.bash
```

### PTY wrapper (`engram shell`) — recommended

Captures: **everything**, including stdout, stderr, and output from interactive programs.  
Uses OSC 633 shell integration (same standard as VS Code and iTerm2).

```bash
engram shell        # wraps your $SHELL
engram shell bash   # or a specific shell
```

Add this to your shell RC to always start in engram shell:
```bash
# At the bottom of ~/.zshrc — only activates in interactive shells
[[ -z "$ENGRAM_PTY" && $- == *i* ]] && exec engram shell
```

---

## Using Anthropic Claude instead of Ollama

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
engram ask "what went wrong with my deploy this morning?"
```

Only the relevant context snippets (not your full history) are sent to Anthropic. Embeddings still run locally via Ollama — only the final Q&A step uses the API.

---

## Configuration

All config via environment variables. Add to your `~/.zshrc` or `~/.bashrc`.

| Variable | Default | Description |
|---|---|---|
| `ENGRAM_DIR` | `~/.engram` | Where the database lives |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server address |
| `ENGRAM_LLM_MODEL` | `llama3` | Ollama model for answering questions |
| `ENGRAM_EMBED_MODEL` | `nomic-embed-text` | Ollama model for embeddings |
| `ANTHROPIC_API_KEY` | *(unset)* | Set to use Claude instead of Ollama |

---

## How it works

```
┌──────────────────────────────────────────────────────────────┐
│  Your terminal                                               │
│                                                              │
│  $ docker build .                                            │
│    Error: no Dockerfile found      ← output captured        │
│  $  ← prompt returns instantly (async logging)              │
└─────────────────────┬────────────────────────────────────────┘
                      │ shell hook (bash/zsh/fish)
                      │ or PTY wrapper (engram shell)
                      ▼
┌──────────────────────────────────────────────────────────────┐
│  ~/.engram/engram.db  (SQLite)                               │
│                                                              │
│  commands:   command | output | exit_code | cwd | timestamp  │
│  embeddings: vector per command+output chunk                 │
└─────────────────────┬────────────────────────────────────────┘
                      │ engram ask "..."
                      ▼
┌──────────────────────────────────────────────────────────────┐
│  1. Embed the question  (Ollama nomic-embed-text)            │
│  2. Cosine similarity search over stored embeddings          │
│     → falls back to full-text search if Ollama is offline   │
│  3. Top-K chunks → context window                            │
│  4. LLM generates answer  (Ollama llama3 or Claude)         │
│  5. Streams tokens to your terminal as they arrive           │
└──────────────────────────────────────────────────────────────┘
```

---

## Privacy

- Your terminal history **never leaves your machine** by default.
- If you set `ANTHROPIC_API_KEY`, only the top-K retrieved context snippets (not your full history) are sent to Anthropic for the final Q&A step.
- Secret redaction runs automatically before anything is stored. API keys, tokens, passwords, and connection strings are replaced with `[REDACTED]`.
- Add custom redaction patterns to `~/.engram/redact_patterns.txt` (one Python regex per line).
- The database lives at `~/.engram/engram.db`. You own it. `engram clear` deletes everything.

---

## Roadmap

- [ ] Demo GIF in README
- [ ] Fish shell full output capture
- [ ] `engram export` — export history to markdown or JSON
- [ ] `engram tui` — interactive TUI browser with fzf-style fuzzy search
- [ ] Automatic sensitive-value redaction for more patterns
- [ ] Rust PTY core for lower overhead
- [ ] Windows support (ConPTY)
- [ ] Opt-in end-to-end encrypted multi-machine sync

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). PRs and issues welcome.

```bash
git clone https://github.com/TLJQ/engram
cd engram
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Acknowledgements

Inspired by [atuin](https://github.com/atuinsh/atuin) and the frustration of watching important terminal output scroll away forever.

---

## License

MIT — see [LICENSE](LICENSE).
