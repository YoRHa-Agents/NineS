#!/usr/bin/env bash
set -euo pipefail

# NineS — One-click installation script
# Usage: curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/NineS/main/scripts/install.sh | bash
#   or:  bash scripts/install.sh [--target <cursor|claude|codex|copilot|all>] [--no-skill]

NINES_REPO="https://github.com/YoRHa-Agents/NineS.git"
NINES_MIN_PYTHON="3.12"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

TARGET="all"
NO_SKILL=false
GLOBAL_INSTALL=false

info()  { printf "${CYAN}▸${RESET} %s\n" "$*"; }
ok()    { printf "${GREEN}✓${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}⚠${RESET} %s\n" "$*"; }
err()   { printf "${RED}✗${RESET} %s\n" "$*" >&2; }

banner() {
    printf "${BOLD}${CYAN}"
    cat <<'EOF'
    _   _ _            ____
   | \ | (_)_ __   ___/ ___|
   |  \| | | '_ \ / _ \___ \
   | |\  | | | | |  __/___) |
   |_| \_|_|_| |_|\___|____/

   Self-Iterating Agent Toolflow
EOF
    printf "${RESET}\n"
}

usage() {
    cat <<EOF
Usage: install.sh [OPTIONS]

Install NineS and set up agent skill files.

Options:
  --target <RUNTIME>   Agent runtime target: cursor, claude, codex, copilot, all (default: all)
  --global             Install skill files to user-global directory
  --no-skill           Only install Python package, skip skill file generation
  --help               Show this help message

Examples:
  bash scripts/install.sh
  bash scripts/install.sh --target cursor
  curl -fsSL https://raw.githubusercontent.com/YoRHa-Agents/NineS/main/scripts/install.sh | bash
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --target)
                TARGET="${2:-}"
                if [[ -z "$TARGET" ]]; then
                    err "Missing value for --target"
                    exit 1
                fi
                shift 2
                ;;
            --global)
                GLOBAL_INSTALL=true
                shift
                ;;
            --no-skill)
                NO_SKILL=true
                shift
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                err "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    case "$TARGET" in
        cursor|claude|codex|copilot|all) ;;
        *)
            err "Invalid target: $TARGET (expected cursor, claude, codex, copilot, or all)"
            exit 1
            ;;
    esac
}

check_python() {
    local py_cmd=""

    for candidate in python3 python; do
        if command -v "$candidate" &>/dev/null; then
            py_cmd="$candidate"
            break
        fi
    done

    if [[ -z "$py_cmd" ]]; then
        err "Python not found. NineS requires Python ${NINES_MIN_PYTHON}+."
        err "Install Python from https://www.python.org/downloads/"
        exit 1
    fi

    local version
    version=$("$py_cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)

    if ! "$py_cmd" -c "
import sys
major, minor = ${NINES_MIN_PYTHON//./, }
if sys.version_info < (major, minor):
    sys.exit(1)
" 2>/dev/null; then
        err "Python ${version} found, but NineS requires ${NINES_MIN_PYTHON}+."
        exit 1
    fi

    ok "Python ${version} detected"
    PYTHON_CMD="$py_cmd"
}

install_package() {
    info "Installing NineS Python package..."

    if command -v uv &>/dev/null; then
        ok "Using uv package manager"
        uv pip install "git+${NINES_REPO}" 2>&1 | tail -1
    elif command -v pip &>/dev/null; then
        ok "Using pip"
        pip install "git+${NINES_REPO}" 2>&1 | tail -1
    elif command -v "$PYTHON_CMD" &>/dev/null; then
        "$PYTHON_CMD" -m pip install "git+${NINES_REPO}" 2>&1 | tail -1
    else
        err "Neither uv nor pip found. Install one of:"
        err "  pip:  ${PYTHON_CMD} -m ensurepip"
        err "  uv:   curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi

    if ! command -v nines &>/dev/null; then
        warn "nines CLI not on PATH. You may need to add ~/.local/bin to PATH:"
        warn '  export PATH="$HOME/.local/bin:$PATH"'
        export PATH="$HOME/.local/bin:$PATH"
    fi

    local installed_version
    installed_version=$(nines --version 2>/dev/null || echo "unknown")
    ok "NineS ${installed_version} installed"
}

install_skills() {
    if [[ "$NO_SKILL" == true ]]; then
        info "Skipping skill file generation (--no-skill)"
        return
    fi

    info "Installing agent skill files for target=${TARGET}..."

    local extra_args=""
    if [[ "$GLOBAL_INSTALL" == true ]]; then
        warn "Global install not yet supported via script; installing to current project"
    fi

    nines install --target "$TARGET"
    ok "Skill files installed for target=${TARGET}"
}

print_summary() {
    echo ""
    printf "${BOLD}${GREEN}Installation complete!${RESET}\n"
    echo ""
    info "Verify:  nines --version"
    info "Help:    nines --help"

    if [[ "$NO_SKILL" == false ]]; then
        echo ""
        case "$TARGET" in
            cursor)
                info "Cursor skill:  .cursor/skills/nines/SKILL.md"
                ;;
            claude)
                info "Claude commands: .claude/commands/nines/"
                ;;
            codex)
                info "Codex skill:   .codex/skills/nines/SKILL.md"
                ;;
            copilot)
                info "Copilot:       .github/copilot-instructions.md"
                ;;
            all)
                info "Cursor:   .cursor/skills/nines/SKILL.md"
                info "Claude:   .claude/commands/nines/"
                info "Codex:    .codex/skills/nines/SKILL.md"
                info "Copilot:  .github/copilot-instructions.md"
                ;;
        esac
    fi
    echo ""
}

main() {
    banner
    parse_args "$@"
    check_python
    install_package
    install_skills
    print_summary
}

main "$@"
