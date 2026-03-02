"""
engram/pty_wrapper.py

A PTY (pseudoterminal) wrapper that launches your shell inside a pty,
transparently forwards all I/O to your real terminal, and captures
every command + its output — including from interactive programs
like vim, htop, fzf, and ssh.

Works on Linux and macOS.

How it works:
  1. Fork a child process running your shell inside a pty
  2. The parent reads from the pty master, writes to your real terminal
     (so you see output), AND tees output into a per-command buffer
  3. We detect command boundaries via OSC 633 shell integration signals
     (same standard used by VS Code, iTerm2, and Warp)
  4. On each boundary we flush the buffer to engram's DB asynchronously
"""

import os
import platform
import pty
import sys
import tty
import termios
import select
import signal
import fcntl
import struct
import re
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path

MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB per command
_IS_MACOS = platform.system() == "Darwin"


def _get_child_cwd(pid: int) -> str:
    """
    Get the current working directory of a child process.
    Works on both Linux (/proc) and macOS (lsof/libproc).
    """
    if not _IS_MACOS:
        # Linux: fast /proc path
        try:
            return os.readlink(f"/proc/{pid}/cwd")
        except Exception:
            return ""
    else:
        # macOS: use lsof (available by default on all macOS)
        try:
            import subprocess
            result = subprocess.run(
                ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                capture_output=True, text=True, timeout=2
            )
            for line in result.stdout.splitlines():
                if line.startswith("n"):
                    return line[1:].strip()
        except Exception:
            pass
        return ""


class PtyWrapper:
    def __init__(self, shell: list | None = None, session_id: str | None = None):
        self.shell = shell or [os.environ.get("SHELL", "/bin/bash")]
        self.session_id = session_id or str(uuid.uuid4())[:8]

        self._master_fd: int = -1
        self._child_pid: int = -1
        self._saved_tty = None

        # Per-command state
        self._current_cmd: str = ""
        self._output_buf: bytearray = bytearray()
        self._cmd_start_time: str = ""
        self._exit_code: int = 0

    # ------------------------------------------------------------------ #
    # Shell init script injected via environment                          #
    # ------------------------------------------------------------------ #

    def _shell_init(self) -> str:
        """
        POSIX shell snippet that installs OSC 633 hooks into the user's shell.
        Both bash and zsh detect and install the right hooks automatically.
        We guard against re-sourcing with ENGRAM_PTY so BASH_ENV doesn't fire
        on every sub-shell invocation.
        """
        return r"""
# engram PTY integration — only run inside the engram PTY wrapper
[ -z "$ENGRAM_PTY" ] && return

__engram_last_cmd=""
__engram_exit_code=0

__engram_preexec() {
    __engram_last_cmd="$1"
    printf '\033]633;A\007'
}

__engram_precmd() {
    __engram_exit_code=$?
    printf '\033]633;B;cmd=%s;exit=%d\007' "$__engram_last_cmd" "$__engram_exit_code"
    printf '\033]633;C\007'
    __engram_last_cmd=""
}

if [ -n "$ZSH_VERSION" ]; then
    autoload -Uz add-zsh-hook
    add-zsh-hook preexec __engram_preexec
    add-zsh-hook precmd  __engram_precmd
elif [ -n "$BASH_VERSION" ]; then
    trap '__engram_preexec "$BASH_COMMAND"' DEBUG
    PROMPT_COMMAND="__engram_precmd${PROMPT_COMMAND:+; $PROMPT_COMMAND}"
fi
"""

    # ------------------------------------------------------------------ #
    # Terminal resize                                                      #
    # ------------------------------------------------------------------ #

    def _set_pty_winsize(self):
        try:
            rows, cols = os.get_terminal_size(sys.stdout.fileno())
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    # OSC 633 parsing                                                      #
    # ------------------------------------------------------------------ #

    # Match OSC sequences: ESC ] <payload> BEL  or  ESC ] <payload> ST
    _OSC_RE = re.compile(rb"\x1b\]633;([^\x07\x1b]*)\x07")

    def _strip_and_parse_osc(self, data: bytes) -> bytes:
        """
        Strip OSC 633 control sequences from data so they don't appear on
        screen, and parse B-type markers to detect command boundaries.
        Returns the cleaned bytes to write to the real terminal.
        """
        cleaned = bytearray()
        pos = 0
        for m in self._OSC_RE.finditer(data):
            cleaned.extend(data[pos:m.start()])
            pos = m.end()

            try:
                payload = m.group(1).decode(errors="replace")
            except Exception:
                continue

            if payload.startswith("B;"):
                # B;cmd=<text>;exit=<n>
                parts = {}
                for part in payload[2:].split(";"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        parts[k] = v

                cmd = parts.get("cmd", "").strip()
                try:
                    exit_code = int(parts.get("exit", "0"))
                except ValueError:
                    exit_code = 0

                if cmd:
                    self._flush_command()
                    self._current_cmd    = cmd
                    self._exit_code      = exit_code
                    self._cmd_start_time = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
                    self._output_buf     = bytearray()
                else:
                    # Same command, just updating exit code
                    self._exit_code = exit_code

            # A / C markers — just strip them, no action needed

        cleaned.extend(data[pos:])
        return bytes(cleaned)

    # ------------------------------------------------------------------ #
    # Flush one command to the DB                                         #
    # ------------------------------------------------------------------ #

    # Compiled once for ANSI stripping
    _ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mABCDEFGHJKLMPSTfhinrsu]|\x1b\][^\x07]*\x07")

    def _flush_command(self):
        """Write the current buffered command + output to engram's DB."""
        if not self._current_cmd:
            return

        from engram.redact import redact, is_sensitive_command
        from engram.db import log_command
        from engram.embeddings import index_command

        cmd = self._current_cmd.strip()
        self._current_cmd = ""

        # Never store engram's own internal calls or sensitive commands
        if not cmd:
            return
        if cmd.startswith("engram log") or cmd.startswith("engram shell"):
            return
        if is_sensitive_command(cmd):
            return

        raw_output  = self._output_buf.decode(errors="replace")
        clean_output = self._ANSI_RE.sub("", raw_output)

        cmd    = redact(cmd)
        output = redact(clean_output[:MAX_OUTPUT_BYTES])

        cwd = _get_child_cwd(self._child_pid)

        row_id = log_command(
            command=cmd,
            output=output,
            exit_code=self._exit_code,
            cwd=cwd,
            session_id=self.session_id,
            timestamp=self._cmd_start_time,
        )

        # Index in a daemon thread — never blocks the shell prompt
        t = threading.Thread(
            target=index_command,
            args=(row_id, cmd, output),
            daemon=True,
        )
        t.start()

    # ------------------------------------------------------------------ #
    # Main entry point                                                     #
    # ------------------------------------------------------------------ #

    def run(self) -> int:
        """
        Spawn the shell inside a pty and enter the I/O forwarding loop.
        Returns the shell's exit code.
        """
        from engram.db import init_db
        init_db()

        # Write init script to a temp file
        import tempfile
        init_fd, init_path = tempfile.mkstemp(suffix=".sh", prefix="engram_init_")
        try:
            os.write(init_fd, self._shell_init().encode())
            os.close(init_fd)
        except Exception:
            os.close(init_fd)

        env = os.environ.copy()
        env["ENGRAM_SESSION"] = self.session_id
        env["ENGRAM_PTY"]     = "1"

        # bash: BASH_ENV is sourced for interactive shells
        env["BASH_ENV"] = init_path

        # zsh: inject via ZDOTDIR so we layer on top of user's existing .zshrc
        zdotdir = Path(tempfile.mkdtemp(prefix="engram_zdot_"))
        real_zshrc = Path.home() / ".zshrc"
        zshrc_lines = []
        # Re-export ZDOTDIR to nothing so nested zsh instances use real dotfiles
        zshrc_lines.append("unset ZDOTDIR")
        if real_zshrc.exists():
            zshrc_lines.append(f"source {real_zshrc}")
        zshrc_lines.append(f"source {init_path}")
        (zdotdir / ".zshrc").write_text("\n".join(zshrc_lines) + "\n")
        env["ZDOTDIR"] = str(zdotdir)

        # Save real terminal attrs before going raw
        stdin_fd = sys.stdin.fileno()
        if sys.stdin.isatty():
            self._saved_tty = termios.tcgetattr(stdin_fd)

        # Fork
        self._child_pid, self._master_fd = pty.fork()

        if self._child_pid == 0:
            # ── Child process ──────────────────────────────────────────
            os.execvpe(self.shell[0], self.shell, env)
            os._exit(1)  # unreachable

        # ── Parent process ─────────────────────────────────────────────
        self._set_pty_winsize()

        if sys.stdin.isatty():
            tty.setraw(stdin_fd)

        def _sigwinch(signum, frame):
            self._set_pty_winsize()

        old_sigwinch = signal.signal(signal.SIGWINCH, _sigwinch)

        try:
            exit_code = self._io_loop()
        finally:
            # Always restore the terminal, even if we crash
            signal.signal(signal.SIGWINCH, old_sigwinch)
            if self._saved_tty is not None:
                try:
                    termios.tcsetattr(stdin_fd, termios.TCSAFLUSH, self._saved_tty)
                except Exception:
                    pass

            # Clean up temp files
            try:
                os.unlink(init_path)
            except Exception:
                pass
            try:
                for f in zdotdir.iterdir():
                    f.unlink(missing_ok=True)
                zdotdir.rmdir()
            except Exception:
                pass

        return exit_code

    # ------------------------------------------------------------------ #
    # I/O forwarding loop                                                 #
    # ------------------------------------------------------------------ #

    def _io_loop(self) -> int:
        stdin_fd  = sys.stdin.fileno()
        stdout_fd = sys.stdout.fileno()

        while True:
            try:
                rlist, _, _ = select.select([self._master_fd, stdin_fd], [], [], 0.05)
            except (select.error, ValueError, OSError):
                break

            # Data from the child shell → write to user's terminal
            if self._master_fd in rlist:
                try:
                    data = os.read(self._master_fd, 4096)
                except OSError:
                    break

                if not data:
                    break

                visible = self._strip_and_parse_osc(data)

                # Accumulate into per-command output buffer
                self._output_buf.extend(visible)
                if len(self._output_buf) > MAX_OUTPUT_BYTES:
                    # Keep the tail — most recent output is more useful
                    self._output_buf = self._output_buf[-MAX_OUTPUT_BYTES:]

                try:
                    os.write(stdout_fd, visible)
                except OSError:
                    break

            # Data from user's keyboard → forward to child shell
            if stdin_fd in rlist:
                try:
                    data = os.read(stdin_fd, 4096)
                except OSError:
                    break
                if not data:
                    break
                try:
                    os.write(self._master_fd, data)
                except OSError:
                    break

        # Flush whatever was in progress when the shell exited
        self._flush_command()

        # Reap the child process
        try:
            _, status = os.waitpid(self._child_pid, 0)
            if os.WIFEXITED(status):
                return os.WEXITSTATUS(status)
            if os.WIFSIGNALED(status):
                return 128 + os.WTERMSIG(status)
        except ChildProcessError:
            pass
        return 0
