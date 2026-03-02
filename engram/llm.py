# Talk to LLMs (Ollama or Anthropic) about your terminal history
# Shows a spinner so you know it's thinking and not frozen

import os
import sys
import json
import threading
import itertools
import time

import requests

OLLAMA_BASE   = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL  = os.environ.get("ENGRAM_LLM_MODEL", "llama3")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
USE_ANTHROPIC  = bool(ANTHROPIC_KEY)

SYSTEM_PROMPT = (
    "You are Engram, an AI assistant with access to the user's local terminal history. "
    "Your job is to answer questions about what the user has done in their terminal. "
    "You are given the most relevant past commands and their outputs as context. "
    "Be concise and direct. Quote exact output when it helps. "
    "If the context does not contain enough information to answer, say so honestly."
)


# Spinner stuff
class _Spinner:
    # Simple loading animation in the terminal
    _FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Thinking"):
        self._message = message
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        frames = itertools.cycle(self._FRAMES)
        while not self._stop_event.is_set():
            frame = next(frames)
            sys.stderr.write(f"\r\033[K\033[90m{frame} {self._message}...\033[0m")
            sys.stderr.flush()
            time.sleep(0.08)

    def start(self):
        if sys.stderr.isatty():
            self._thread.start()
        return self

    def stop(self):
        self._stop_event.set()
        if self._thread.is_alive():
            self._thread.join(timeout=0.5)
        if sys.stderr.isatty():
            sys.stderr.write("\r\033[K")  # clear the spinner line
            sys.stderr.flush()


# ─────────────────────────────────────────────────────────────────────────────
# Context builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_context_block(hits: list) -> str:
    lines = []
    for i, hit in enumerate(hits, 1):
        ts  = hit.get("timestamp", "unknown time")[:19].replace("T", " ")
        cwd = hit.get("cwd", "?")
        txt = hit.get("chunk_text", "").strip()
        lines.append(f"--- Context {i} | {ts} | {cwd} ---\n{txt}\n")
    return "\n".join(lines)


def _build_prompt(question: str, context_hits: list) -> str:
    context = _build_context_block(context_hits)
    return (
        f"Here is relevant terminal history from this machine:\n\n"
        f"{context}\n\n"
        f"Question: {question}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Ollama backend
# ─────────────────────────────────────────────────────────────────────────────

def ask_ollama(question: str, context_hits: list) -> str:
    prompt = _build_prompt(question, context_hits)

    spinner = _Spinner("Thinking").start()
    first_token = True

    try:
        resp = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model":  OLLAMA_MODEL,
                "system": SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": True,
            },
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        full = []
        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            try:
                chunk = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            token = chunk.get("response", "")
            if token:
                if first_token:
                    spinner.stop()
                    first_token = False
                print(token, end="", flush=True)
                full.append(token)

            if chunk.get("done"):
                break

        spinner.stop()
        print()  # final newline
        return "".join(full)

    except requests.exceptions.ConnectionError:
        spinner.stop()
        print(
            "\n[engram] Could not connect to Ollama.\n"
            "         Start it with:  ollama serve\n"
            "         Or use Anthropic: export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        sys.exit(1)
    except requests.exceptions.Timeout:
        spinner.stop()
        print(
            "\n[engram] Ollama timed out. The model may still be loading.\n"
            "         Try again in a moment, or run: ollama list",
            file=sys.stderr,
        )
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        spinner.stop()
        if e.response is not None and e.response.status_code == 404:
            print(
                f"\n[engram] Model '{OLLAMA_MODEL}' not found in Ollama.\n"
                f"         Pull it with: ollama pull {OLLAMA_MODEL}",
                file=sys.stderr,
            )
        else:
            print(f"\n[engram] Ollama HTTP error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        spinner.stop()
        print(f"\n[engram] Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Anthropic backend
# ─────────────────────────────────────────────────────────────────────────────

def ask_anthropic(question: str, context_hits: list) -> str:
    try:
        import anthropic
    except ImportError:
        print(
            "[engram] The 'anthropic' package is not installed.\n"
            "         Install it with: pip install 'engram-cli[anthropic]'",
            file=sys.stderr,
        )
        sys.exit(1)

    prompt = _build_prompt(question, context_hits)
    spinner = _Spinner("Thinking").start()
    first_token = True

    # Try multiple model versions for compatibility
    models_to_try = [
        "claude-sonnet-4-20250514",
        "claude-sonnet-4-20241022", 
        "claude-3-5-sonnet-20241022",
        "claude-3-5-sonnet-20240620",
    ]

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        
        # Try each model until one works
        last_error = None
        for model in models_to_try:
            try:
                with client.messages.stream(
                    model=model,
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                ) as stream:
                    full = []
                    for text in stream.text_stream:
                        if first_token:
                            spinner.stop()
                            first_token = False
                        print(text, end="", flush=True)
                        full.append(text)
                    spinner.stop()
                    print()
                    return "".join(full)
            except anthropic.NotFoundError as e:
                last_error = e
                continue  # Try next model
            
        # If we get here, all models failed
        spinner.stop()
        if last_error:
            print(
                f"\n[engram] All Claude models unavailable. Last error: {last_error}\n"
                f"         Your API key may not have access to these models.",
                file=sys.stderr,
            )
        sys.exit(1)

    except anthropic.AuthenticationError:
        spinner.stop()
        print(
            "\n[engram] Invalid Anthropic API key.\n"
            "         Check your ANTHROPIC_API_KEY environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        spinner.stop()
        print(f"\n[engram] Anthropic error: {e}", file=sys.stderr)
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# Router
# ─────────────────────────────────────────────────────────────────────────────

def answer(question: str, context_hits: list) -> str:
    """Route to Anthropic if ANTHROPIC_API_KEY is set, otherwise Ollama."""
    # Re-read env at call time so setting the key mid-session works
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ask_anthropic(question, context_hits)
    return ask_ollama(question, context_hits)
