# engram zsh hook
# Add to ~/.zshrc:  source ~/.engram/engram.zsh
# Or run:           engram install --shell zsh
#
# NOTE: For the most robust capture (interactive programs like vim, htop),
#       use `engram shell` instead, which uses a PTY wrapper.
#       This hook is the lightweight alternative for simple commands.

_ENGRAM_SESSION="${ENGRAM_SESSION:-$(uuidgen 2>/dev/null || date +%s$$)}"
_ENGRAM_LAST_CMD=""
_ENGRAM_EXIT_CODE=0

# preexec: called by zsh just before a command runs
_engram_preexec() {
    local cmd="$1"
    [[ -z "$cmd" ]]              && return
    [[ "$cmd" == engram\ log* ]] && return
    [[ "$cmd" == engram\ shell* ]] && return
    _ENGRAM_LAST_CMD="$cmd"
}

# precmd: called just before each prompt
_engram_precmd() {
    _ENGRAM_EXIT_CODE=$?

    [[ -z "$_ENGRAM_LAST_CMD" ]] && return

    local cmd="$_ENGRAM_LAST_CMD"
    _ENGRAM_LAST_CMD=""

    # Check if engram command exists
    if ! command -v engram &>/dev/null; then
        return
    fi

    # Log asynchronously (no output capture in hook mode — use `engram shell` for that)
    engram log \
        --command   "$cmd"              \
        --output    ""                  \
        --exit-code "$_ENGRAM_EXIT_CODE" \
        --cwd       "$(pwd)"            \
        --session   "$_ENGRAM_SESSION"  \
        &>/dev/null &!
}

autoload -Uz add-zsh-hook
add-zsh-hook preexec _engram_preexec
add-zsh-hook precmd  _engram_precmd

print "[engram] zsh hook loaded (lightweight mode). For full output capture run: engram shell"
print "[engram] Session: $_ENGRAM_SESSION"
