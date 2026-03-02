# engram CLI - your terminal's memory interface

import argparse
import sys
import os
from pathlib import Path

from engram.db import (
    init_db,
    log_command,
    get_recent_commands,
    search_fulltext,
    DB_PATH,
    ENGRAM_DIR,
)
from engram.embeddings import search_similar, index_command
from engram.llm import answer


def validate_config() -> None:
    # Quick sanity check on config before doing anything
    import re
    
    # Validate OLLAMA_HOST format if set
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if not re.match(r'^https?://.+', ollama_host):
        print(f"[engram] OLLAMA_HOST looks weird: '{ollama_host}'", file=sys.stderr)
    
    # Check if ENGRAM_DIR is writable
    try:
        ENGRAM_DIR.mkdir(parents=True, exist_ok=True)
        test_file = ENGRAM_DIR / ".test_write"
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        print(f"[engram] Can't write to {ENGRAM_DIR}: {e}", file=sys.stderr)


def cmd_ask(args) -> None:
    # Ask the AI about your terminal history
    question = " ".join(args.question)
    if not question:
        print("[engram] Need a question! Try: engram ask 'what was that docker error?'")
        sys.exit(1)

    print("[engram] Searching history...", end="\r", flush=True)
    hits = search_similar(question, top_k=args.top_k)
    print(" " * 40, end="\r")

    if not hits:
        print("[engram] Nothing found. Try running some commands first, then `engram index`.")
        sys.exit(0)

    if args.verbose:
        print(f"\n[engram] Top {len(hits)} context chunks:\n")
        for h in hits:
            score = f"{h['score']:.3f}" if h.get("score") is not None else "N/A (text search)"
            print(f"  [{score}] {h.get('timestamp', '')[:19]}  {h.get('cwd', '')}")
            print(f"           {h['chunk_text'][:120].strip()}...")
        print()

    answer(question, hits)


def cmd_log(args) -> None:
    # Internal - called by shell hooks to save commands
    from engram.redact import redact, is_sensitive_command

    cmd = args.command.strip()
    if not cmd:
        return
    if cmd.startswith("engram log") or cmd.startswith("engram shell"):
        return
    if is_sensitive_command(cmd):
        return

    cmd    = redact(cmd)
    output = redact(args.output or "")

    row_id = log_command(
        command=cmd,
        output=output,
        exit_code=args.exit_code,
        cwd=args.cwd,
        session_id=args.session,
    )
    index_command(row_id, cmd, output)


def cmd_shell(args) -> None:
    # Wrap your shell to capture full command output
    from engram.pty_wrapper import PtyWrapper
    shell_cmd = args.shell if args.shell and len(args.shell) > 0 else None
    wrapper = PtyWrapper(shell=shell_cmd)
    sys.exit(wrapper.run())


def cmd_install(args) -> None:
    # Add hooks to your shell config automatically
    import shutil

    ENGRAM_DIR.mkdir(parents=True, exist_ok=True)
    pkg_dir  = Path(__file__).parent
    hook_src = pkg_dir.parent / "shell"

    for fname in ("engram.bash", "engram.zsh", "engram.fish"):
        src = hook_src / fname
        if src.exists():
            dst = ENGRAM_DIR / fname
            shutil.copy(src, dst)
            print(f"[engram] Copied {fname} → {dst}")

    shell = args.shell or os.path.basename(os.environ.get("SHELL", "bash"))

    rc_map = {
        "bash": (Path.home() / ".bashrc",
                 "source ~/.engram/engram.bash  # engram hook"),
        "zsh":  (Path.home() / ".zshrc",
                 "source ~/.engram/engram.zsh   # engram hook"),
        "fish": (Path.home() / ".config" / "fish" / "config.fish",
                 "source ~/.engram/engram.fish  # engram hook"),
    }

    if shell not in rc_map:
        print(f"[engram] Unknown shell: {shell}. Supported: bash, zsh, fish")
        return

    rc_file, hook_line = rc_map[shell]
    rc_file.parent.mkdir(parents=True, exist_ok=True)
    existing = rc_file.read_text() if rc_file.exists() else ""

    if "engram hook" in existing:
        print(f"[engram] Hook already in {rc_file}, looks good.")
    else:
        with open(rc_file, "a") as f:
            f.write(f"\n{hook_line}\n")
        print(f"[engram] Added hook to {rc_file}")

    print(f"\n[engram] Done! Restart your terminal or run:")
    print(f"           source {rc_file}")


def cmd_history(args) -> None:
    # Show recent command history
    rows = get_recent_commands(limit=args.limit)
    if not rows:
        print("[engram] No history yet.")
        return

    try:
        col_w = os.get_terminal_size().columns
    except Exception:
        col_w = 120

    for row in reversed(rows):
        ts  = row["timestamp"][:19].replace("T", " ")
        ec  = row["exit_code"]
        cwd = row["cwd"] or ""
        cmd = row["command"]
        ok  = "✓" if ec == 0 else f"✗({ec})"
        line = f"{ts}  {ok}  {cwd}  {cmd}"
        if len(line) > col_w:
            line = line[:col_w - 3] + "..."
        print(line)


def cmd_search(args) -> None:
    """Execute the 'search' command - full-text search over history."""
    query = " ".join(args.query)
    rows  = search_fulltext(query, limit=args.limit)
    if not rows:
        print(f"[engram] No results for: {query}")
        return
    for row in rows:
        ts  = row["timestamp"][:19].replace("T", " ")
        cmd = row["command"]
        out = (row["output"] or "")[:300].strip()
        ec  = row["exit_code"]
        ok  = "✓" if ec == 0 else f"✗({ec})"
        print(f"\n{ts}  {ok}  {cmd}")
        if out:
            for line in out.splitlines()[:6]:
                print(f"    {line}")


def cmd_index(args) -> None:
    """Execute the 'index' command - generate embeddings for un-indexed commands."""
    from engram.db import get_connection

    conn = get_connection()
    rows = conn.execute("SELECT id, command, output FROM commands").fetchall()

    if not args.reindex:
        indexed_ids = set(
            r[0] for r in conn.execute("SELECT DISTINCT command_id FROM embeddings").fetchall()
        )
        rows = [r for r in rows if r["id"] not in indexed_ids]
    conn.close()

    if not rows:
        print("[engram] Everything is already indexed.")
        return

    print(f"[engram] Indexing {len(rows)} commands...")
    ok = 0
    for i, row in enumerate(rows, 1):
        vec = index_command(row["id"], row["command"], row["output"] or "")
        if vec is not False:
            ok += 1
        if i % 10 == 0 or i == len(rows):
            print(f"  {i}/{len(rows)}", end="\r", flush=True)

    print(f"\n[engram] Done. {ok}/{len(rows)} commands indexed.")
    if ok < len(rows):
        print("  Some failed — is Ollama running? Try: ollama serve")


def cmd_status(args) -> None:
    """Execute the 'status' command - show DB stats and system configuration."""
    from engram.db import get_connection
    import requests

    conn = get_connection()
    n_cmds  = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    n_embs  = conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
    n_unidx = conn.execute(
        "SELECT COUNT(*) FROM commands WHERE id NOT IN "
        "(SELECT DISTINCT command_id FROM embeddings)"
    ).fetchone()[0]
    conn.close()

    db_size = DB_PATH.stat().st_size / 1024 if DB_PATH.exists() else 0
    ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    try:
        r = requests.get(f"{ollama_host}/api/tags", timeout=2)
        models = [m["name"] for m in r.json().get("models", [])]
        ollama_ok = f"✓ running  ({len(models)} models loaded)"
    except Exception:
        ollama_ok = "✗ not reachable — run: ollama serve"

    backend = "Anthropic (Claude)" if os.environ.get("ANTHROPIC_API_KEY") else "Ollama (local)"

    print(f"engram {_version()} — status")
    print(f"  DB path        : {DB_PATH}")
    print(f"  DB size        : {db_size:.1f} KB")
    print(f"  Commands       : {n_cmds:,}")
    print(f"  Indexed        : {n_embs:,}  ({n_unidx:,} awaiting indexing)")
    print(f"  LLM backend    : {backend}")
    print(f"  Ollama         : {ollama_ok}")
    print(f"  Ollama host    : {ollama_host}")
    print(f"  LLM model      : {os.environ.get('ENGRAM_LLM_MODEL', 'llama3')}")
    print(f"  Embed model    : {os.environ.get('ENGRAM_EMBED_MODEL', 'nomic-embed-text')}")
    if n_unidx > 0:
        print(f"\n  Tip: run `engram index` to index {n_unidx:,} un-indexed commands.")


def cmd_clear(args) -> None:
    """Execute the 'clear' command - delete all stored history with confirmation."""
    from engram.db import get_connection

    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
    conn.close()

    if n == 0:
        print("[engram] Nothing to clear.")
        return

    if not args.yes:
        ans = input(f"[engram] Delete all {n:,} stored commands? This cannot be undone. [y/N] ")
        if ans.strip().lower() not in ("y", "yes"):
            print("[engram] Aborted.")
            return

    conn = get_connection()
    conn.execute("DELETE FROM embeddings")
    conn.execute("DELETE FROM commands")
    conn.commit()
    conn.close()
    print(f"[engram] Cleared {n:,} commands.")


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("engram-shell")
    except Exception:
        return "dev"


def main():
    init_db()
    validate_config()

    parser = argparse.ArgumentParser(
        prog="engram",
        description="Eidetic memory for your terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  engram shell                              start your shell with full capture
  engram ask "what docker error did I get?" ask a question about your history
  engram search "connection refused"        full-text search
  engram history -n 100                     show last 100 commands
  engram install                            add hook to your shell RC file
  engram index                              index new commands into embeddings
  engram status                             show config and DB stats
  engram clear                              delete all stored history
""",
    )
    parser.add_argument("--version", action="version", version=f"engram {_version()}")
    sub = parser.add_subparsers(dest="cmd", metavar="<command>")

    p_sh = sub.add_parser("shell", help="Launch your shell inside the PTY wrapper (recommended)")
    p_sh.add_argument("shell", nargs="*", help="Shell to launch (default: $SHELL)")

    p_ask = sub.add_parser("ask", help="Ask a question about your terminal history")
    p_ask.add_argument("question", nargs="+")
    p_ask.add_argument("--top-k", type=int, default=5, dest="top_k")
    p_ask.add_argument("--verbose", "-v", action="store_true")

    p_log = sub.add_parser("log", help=argparse.SUPPRESS)
    p_log.add_argument("--command", required=True)
    p_log.add_argument("--output", default="")
    p_log.add_argument("--exit-code", type=int, default=0, dest="exit_code")
    p_log.add_argument("--cwd", default="")
    p_log.add_argument("--session", default="default")

    p_inst = sub.add_parser("install", help="Add the shell hook to your RC file")
    p_inst.add_argument("--shell", choices=["bash", "zsh", "fish"])

    p_hist = sub.add_parser("history", help="Print recent commands")
    p_hist.add_argument("--limit", "-n", type=int, default=50)

    p_srch = sub.add_parser("search", help="Full-text search across commands and output")
    p_srch.add_argument("query", nargs="+")
    p_srch.add_argument("--limit", "-n", type=int, default=20)

    p_idx = sub.add_parser("index", help="Embed un-indexed commands")
    p_idx.add_argument("--reindex", action="store_true",
                       help="Re-embed all commands, not just new ones")

    sub.add_parser("status", help="Show configuration and DB stats")

    p_clr = sub.add_parser("clear", help="Delete all stored history")
    p_clr.add_argument("--yes", "-y", action="store_true")

    args = parser.parse_args()

    dispatch = {
        "shell":   cmd_shell,
        "ask":     cmd_ask,
        "log":     cmd_log,
        "install": cmd_install,
        "history": cmd_history,
        "search":  cmd_search,
        "index":   cmd_index,
        "status":  cmd_status,
        "clear":   cmd_clear,
    }

    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
