# engram fish hook
# Source this file in your ~/.config/fish/config.fish:
#   source ~/.engram/engram.fish
#
# Or run: engram install --shell fish

set -g _engram_session (random)(date +%s)
set -g _engram_last_cmd ""
set -g _engram_tmpfile ""

function _engram_preexec --on-event fish_preexec
    set -g _engram_last_cmd $argv[1]

    # Skip engram's own log calls
    if string match -q "engram log*" $argv[1]
        return
    end
    if string match -q "engram shell*" $argv[1]
        return
    end

    set -g _engram_tmpfile (mktemp /tmp/engram_out.XXXXXX)
end

function _engram_postexec --on-event fish_postexec
    set -l exit_code $status
    set -l cmd $_engram_last_cmd
    set -l tmpfile $_engram_tmpfile

    if test -z "$cmd" -o -z "$tmpfile" -o ! -f "$tmpfile"
        return
    end

    set -l output (head -c 8192 $tmpfile 2>/dev/null)
    rm -f $tmpfile

    # Check if engram command exists
    if not command -v engram >/dev/null 2>&1
        return
    end

    # Log asynchronously
    engram log \
        --command  $cmd          \
        --output   $output       \
        --exit-code $exit_code   \
        --cwd      (pwd)         \
        --session  $_engram_session \
        &>/dev/null &

    set -g _engram_last_cmd ""
    set -g _engram_tmpfile ""
end

echo "[engram] fish hook loaded. Session: $_engram_session"
