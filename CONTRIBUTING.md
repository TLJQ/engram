# Contributing to engram

Thanks for your interest in contributing! engram is an early project and contributions of all kinds are welcome.

---

## Quick start

```bash
git clone https://github.com/TLJQ/engram
cd engram
python -m pip install -e ".[dev]"
pytest tests/ -v
```

That's it. All tests should pass before you open a PR.

---

## Project structure

```
engram/
├── engram/
│   ├── cli.py          ← all CLI commands (start here)
│   ├── db.py           ← SQLite storage layer
│   ├── embeddings.py   ← vector search via Ollama
│   ├── llm.py          ← LLM backends (Ollama + Anthropic)
│   ├── pty_wrapper.py  ← PTY wrapper for full output capture
│   └── redact.py       ← secret scrubbing before storage
├── shell/
│   ├── engram.bash     ← bash hook (lightweight mode)
│   ├── engram.zsh      ← zsh hook (lightweight mode)
│   └── engram.fish     ← fish hook
├── tests/              ← pytest tests (one file per module)
└── scripts/
    └── install.sh      ← one-liner curl installer
```

---

## Ways to contribute

### Good first issues

- **Fish shell hook** — the current fish hook logs commands but not output. Improving it to capture output would be great.
- **`engram export`** — add a command to export history to markdown or JSON.
- **Better ANSI stripping** — the current regex in `pty_wrapper.py` misses some edge cases.
- **Windows support** — engram currently only works on Linux and macOS (PTY is Unix-only). A Windows-native implementation using ConPTY would be a significant contribution.
- **Tests** — more test coverage is always welcome, especially for `llm.py` and `pty_wrapper.py`.

### Bigger projects

- **Rust PTY core** — rewrite `pty_wrapper.py` in Rust for lower overhead and better compatibility.
- **TUI history browser** — `engram tui` using `textual` or `rich`.
- **Opt-in encrypted sync** — sync history across machines with end-to-end encryption.
- **Automatic model selection** — detect which Ollama models are installed and pick the best available one.

---

## Guidelines

**Code style** — we use `black` for formatting and `ruff` for linting. Run both before committing:

```bash
black engram/ tests/
ruff check engram/ tests/
```

**Tests** — every new feature or bug fix should come with a test. We use `pytest`. Tests live in `tests/` and mirror the module structure (`test_db.py` tests `db.py`, etc.).

**Commits** — use plain English commit messages. No need for a specific convention, but be descriptive:
- ✅ `fix: handle OSError when pty master closes on macOS`
- ✅ `feat: add engram export command`
- ❌ `update stuff`

**Pull requests** — keep PRs focused on one thing. A PR that fixes a bug and adds a new feature is harder to review than two separate PRs.

**Breaking changes** — if your change modifies the DB schema or breaks existing CLI flags, note it clearly in the PR description.

---

## Running specific tests

```bash
pytest tests/test_db.py -v                  # just DB tests
pytest tests/test_redact.py -v              # just redaction tests
pytest tests/ -k "test_search" -v           # tests matching a name pattern
pytest tests/ --cov=engram -v               # with coverage report
```

---

## Reporting bugs

Open an issue at https://github.com/TLJQ/engram/issues with:
1. Your OS and shell (`uname -a`, `echo $SHELL`)
2. Your Python version (`python3 --version`)
3. The exact command you ran
4. The full error output

---

## Questions

Open a GitHub Discussion or an issue tagged `question`. There are no stupid questions.
