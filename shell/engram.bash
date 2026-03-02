#!/usr/bin/env bash
# engram bash hook
# Add to ~/.bashrc:  source ~/.engram/engram.bash
# Or run:            engram install --shell bash
#
# NOTE: For the most robust capture (interactive programs like vim, htop),
#       use `engram shell` instead, which uses a PTY wrapper.
#       This hook is the lightweight alternative for simple commands.

_ENGRAM_SESSION="${ENGRAM_SESSION:-$(cat /proc/sys/kernel/random/uuid 2>/dev/null || date +%s$$)}"
_ENGRAM_LAST_CMD=""
_ENGRAM_CMD_ACTIVE=0

# preexec equivalent via DEBUG trap
_engram_preexec() {
    # Only fire on actual command execution, not on every line
    [[ "$BASH_COMMAND" == "_engram_precmd"* ]] && return
    [[ "$BASH_COMMAND" == "engram log"* ]]     && return

    # Record the command
    _ENGRAM_LAST_CMD="$BASH_COMMAND"
    _ENGRAM_CMD_ACTIVE=1
}

# Called before each prompt
_engram_precmd() {
    local exit_code=$?

    [[ "$_ENGRAM_CMD_ACTIVE" -eq 0 ]] && return
    [[ -z "$_ENGRAM_LAST_CMD" ]]       && return

    _ENGRAM_CMD_ACTIVE=0

    local cmd="$_ENGRAM_LAST_CMD"
    _ENGRAM_LAST_CMD=""

    # Skip if it looks like an internal/empty command
    [[ "$cmd" == _engram_* ]] && return

    # Check if engram command exists
    if ! command -v engram &>/dev/null; then
        return
    fi

    # Log asynchronously (no output capture in hook mode — use `engram shell` for that)
    engram log \
        --command  "$cmd"       \
        --output   ""           \
        --exit-code "$exit_code" \
        --cwd      "$(pwd)"     \
        --session  "$_ENGRAM_SESSION" \
        &>/dev/null &

    disown %% 2>/dev/null || true
}

trap '_engram_preexec' DEBUG
PROMPT_COMMAND="_engram_precmd${PROMPT_COMMAND:+; $PROMPT_COMMAND}"

echo "[engram] bash hook loaded (lightweight mode). For full output capture run: engram shell"
echo "[engram] Session: $_ENGRAM_SESSION"
