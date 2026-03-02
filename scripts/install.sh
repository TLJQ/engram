#!/usr/bin/env bash
# engram one-liner installer
# Usage: curl -sSL https://raw.githubusercontent.com/TLJQ/engram/main/scripts/install.sh | bash
set -euo pipefail

REPO="TLJQ/engram"
INSTALL_DIR="$HOME/.engram"
SHELL_TYPE="$(basename "$SHELL")"

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "  ███████╗███╗   ██╗ ██████╗ ██████╗  █████╗ ███╗   ███╗"
echo "  ██╔════╝████╗  ██║██╔════╝ ██╔══██╗██╔══██╗████╗ ████║"
echo "  █████╗  ██╔██╗ ██║██║  ███╗██████╔╝███████║██╔████╔██║"
echo "  ██╔══╝  ██║╚██╗██║██║   ██║██╔══██╗██╔══██║██║╚██╔╝██║"
echo "  ███████╗██║ ╚████║╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║"
echo "  ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝"
echo ""
echo "  Eidetic memory for your terminal."
echo ""

# ── 1. Check Python 3.9+ ─────────────────────────────────────────────────────
echo "[1/4] Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "  [error] Python 3 is required."
    echo "          Install it from https://python.org or via your package manager."
    exit 1
fi

PYTHON_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
PYTHON_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
if [[ "$PYTHON_MAJOR" -lt 3 || ("$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 9) ]]; then
    echo "  [error] Python 3.9+ required (you have $(python3 --version))"
    exit 1
fi
echo "  Python $(python3 --version) ✓"

# ── 2. Install engram via pip ─────────────────────────────────────────────────
echo "[2/4] Installing engram..."
if command -v pip3 &>/dev/null; then
    pip3 install --quiet --upgrade "git+https://github.com/$REPO.git"
else
    python3 -m pip install --quiet --upgrade "git+https://github.com/$REPO.git"
fi
echo "  engram installed ✓"

# ── 3. Install shell hooks ────────────────────────────────────────────────────
echo "[3/4] Installing shell hooks to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"

_copy_hook() {
    local name="$1"
    # Try copying from installed package first, fall back to curl
    local site
    site=$(python3 -c "import engram, os; print(os.path.dirname(engram.__file__))" 2>/dev/null || echo "")
    if [[ -n "$site" && -f "$site/../shell/$name" ]]; then
        cp "$site/../shell/$name" "$INSTALL_DIR/$name"
    else
        curl -fsSL "https://raw.githubusercontent.com/$REPO/main/shell/$name" \
             -o "$INSTALL_DIR/$name"
    fi
}

_copy_hook "engram.bash"
_copy_hook "engram.zsh"
_copy_hook "engram.fish"
echo "  Shell hooks installed ✓"

# ── 4. Add hook to RC file ────────────────────────────────────────────────────
echo "[4/4] Configuring shell ($SHELL_TYPE)..."

RC_FILE=""
HOOK_FILE=""
case "$SHELL_TYPE" in
    zsh)
        RC_FILE="$HOME/.zshrc"
        HOOK_FILE="$INSTALL_DIR/engram.zsh"
        ;;
    bash)
        RC_FILE="${HOME}/.bashrc"
        # On macOS bash reads .bash_profile for login shells
        if [[ "$OSTYPE" == "darwin"* && -f "$HOME/.bash_profile" && ! -f "$HOME/.bashrc" ]]; then
            RC_FILE="$HOME/.bash_profile"
        fi
        HOOK_FILE="$INSTALL_DIR/engram.bash"
        ;;
    fish)
        RC_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/fish/config.fish"
        HOOK_FILE="$INSTALL_DIR/engram.fish"
        mkdir -p "$(dirname "$RC_FILE")"
        ;;
    *)
        echo "  [warn] Unrecognised shell: $SHELL_TYPE"
        echo "         Manually add this to your shell RC file:"
        echo "           source $INSTALL_DIR/engram.bash"
        ;;
esac

if [[ -n "$RC_FILE" ]]; then
    HOOK_LINE="source $HOOK_FILE  # engram hook"
    if grep -q "engram hook" "$RC_FILE" 2>/dev/null; then
        echo "  Hook already present in $RC_FILE — skipping."
    else
        printf '\n%s\n' "$HOOK_LINE" >> "$RC_FILE"
        echo "  Added hook to $RC_FILE ✓"
    fi
fi

# ── 5. Check Ollama ───────────────────────────────────────────────────────────
echo ""
echo "Checking for Ollama (needed for AI features)..."
if command -v ollama &>/dev/null; then
    echo "  Ollama found ✓"
    echo "  Pulling embedding model (nomic-embed-text)..."
    ollama pull nomic-embed-text 2>/dev/null || echo "  [warn] Could not pull nomic-embed-text — run: ollama pull nomic-embed-text"
    echo "  Pulling LLM (llama3)..."
    ollama pull llama3 2>/dev/null || echo "  [warn] Could not pull llama3 — run: ollama pull llama3"
else
    echo "  Ollama not found."
    echo "  Install it from https://ollama.com to enable AI search."
    echo "  (engram will still log your history without it)"
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "  ✅  engram installed!"
echo ""
if [[ -n "$HOOK_FILE" ]]; then
    echo "  Restart your terminal, or run:"
    echo "    source $HOOK_FILE"
    echo ""
fi
echo "  Then:"
echo "    engram status                           check everything is working"
echo "    engram shell                            start capturing with full output"
echo "    engram ask \"what errors did I get?\"     ask your terminal history"
echo ""
