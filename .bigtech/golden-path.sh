#!/usr/bin/env bash
################################################################################
# GOLDEN PATH DEPLOYMENT - Big Tech Platform Engineering 2026
# Netflix + Spotify + Google Developer Experience Pattern
# 
# Philosophy: "Make the easy path the right path"
# One command to rule them all: ./ship
################################################################################

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & THEMING
# ═══════════════════════════════════════════════════════════════════════════════

readonly APP_NAME="🚀 AUTO-BROKER"
readonly VERSION="2026.1"
readonly CHECKMARK="✅"
readonly ROCKET="🚀"
readonly SPARKLES="✨"
readonly WARNING="⚠️"
readonly ERROR="❌"
readonly INFO="ℹ️"
readonly CLOCK="⏱️"
readonly TEST_TUBE="🧪"
readonly CHART="📊"
readonly LOCK="🔒"

# Colors
readonly RESET='\033[0m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly GREEN='\033[32m'
readonly YELLOW='\033[33m'
readonly RED='\033[31m'
readonly BLUE='\033[34m'
readonly CYAN='\033[36m'
readonly MAGENTA='\033[35m'

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

print_header() {
    echo -e "${CYAN}${BOLD}"
    cat << 'EOF'
    ___    __  _____________  _______  ________  ________
   /   |  /  |/  /  _/ __  \/ ___/\ \/ / ____/ / ____/ /
  / /| | / /|_/ // // /_/ /\__ \  \  / / __   / __/ / /
 / ___ |/ /  / // // ____/___/ /  / / /_/ /  / /___/ /___
/_/  |_/_/  /_/___/_/    /____/  /_/\____/  /_____/_____/

EOF
    echo -e "${RESET}"
    echo -e "${DIM}         Platform Engineering • Golden Path • 2026${RESET}\n"
}

log() { echo -e "${BLUE}${INFO}${RESET} $1"; }
success() { echo -e "${GREEN}${CHECKMARK}${RESET} $1"; }
warn() { echo -e "${YELLOW}${WARNING}${RESET} $1"; }
error() { echo -e "${RED}${ERROR}${RESET} $1"; }
step() { echo -e "\n${MAGENTA}${BOLD}▶ $1${RESET}"; }
metric() { echo -e "${DIM}${CLOCK}${RESET} $1: ${BOLD}$2${RESET}"; }

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1: PRE-FLIGHT CHECKS (Guardrails)
# ═══════════════════════════════════════════════════════════════════════════════

phase_preflight() {
    step "${LOCK} PHASE 1: Pre-flight Checks"
    
    local start_time=$(date +%s)
    
    # Check 1: Git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        error "Not in a git repository"
        exit 1
    fi
    success "Git repository verified"
    
    # Check 2: Git remote
    if ! git remote get-url origin > /dev/null 2>&1; then
        error "No remote origin configured"
        exit 1
    fi
    success "Remote origin configured"
    
    # Check 3: GitHub CLI (optional but recommended)
    if command -v gh &> /dev/null; then
        if gh auth status &> /dev/null; then
            success "GitHub CLI authenticated"
            export GH_AVAILABLE=true
        else
            warn "GitHub CLI not authenticated (run: gh auth login)"
            export GH_AVAILABLE=false
        fi
    else
        warn "GitHub CLI not installed (brew install gh)"
        export GH_AVAILABLE=false
    fi
    
    # Check 4: Working directory clean?
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        warn "Uncommitted changes detected"
        git status --short
        echo ""
        read -p "Auto-commit changes? [Y/n]: " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            git add .
            git commit -m "chore: auto-commit before ship [skip ci]"
            success "Changes auto-committed"
        fi
    else
        success "Working directory clean"
    fi
    
    local end_time=$(date +%s)
    metric "Pre-flight duration" "$((end_time - start_time))s"
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2: VALIDATION (Quality Gates)
# ═══════════════════════════════════════════════════════════════════════════════

phase_validation() {
    step "${TEST_TUBE} PHASE 2: Quality Gates"
    
    local start_time=$(date +%s)
    
    # Quick syntax check
    log "Running syntax validation..."
    if python3 -m py_compile api/main.py 2>/dev/null; then
        success "Python syntax valid"
    else
        error "Python syntax errors detected"
        exit 1
    fi
    
    # Fast unit tests (fail fast)
    if [[ -f "pytest.ini" ]]; then
        log "Running fast unit tests..."
        if python3 -m pytest tests/unit/ -x -q --tb=no > /tmp/test_output.log 2>&1; then
            success "Unit tests pass"
        else
            error "Unit tests failing"
            cat /tmp/test_output.log | tail -20
            echo ""
            warn "Fix tests before shipping or use --force to skip"
            read -p "Continue anyway? [y/N]: " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
    
    local end_time=$(date +%s)
    metric "Validation duration" "$((end_time - start_time))s"
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3: DEPLOYMENT (The Golden Path)
# ═══════════════════════════════════════════════════════════════════════════════

phase_deploy() {
    step "${ROCKET} PHASE 3: Deployment"
    
    local start_time=$(date +%s)
    local retry_count=0
    local max_retries=3
    
    log "Pushing to origin..."
    
    while [[ $retry_count -lt $max_retries ]]; do
        if git push origin "$(git branch --show-current)" 2>&1 | grep -q "Everything up-to-date"; then
            success "Already up to date"
            break
        elif git push origin "$(git branch --show-current)" 2>&1; then
            success "Code shipped successfully"
            break
        else
            ((retry_count++))
            if [[ $retry_count -lt $max_retries ]]; then
                warn "Push failed, retrying ($retry_count/$max_retries)..."
                sleep 2
            else
                error "Deployment failed after $max_retries attempts"
                exit 1
            fi
        fi
    done
    
    local end_time=$(date +%s)
    metric "Deployment duration" "$((end_time - start_time))s"
}

# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 4: OBSERVABILITY (Monitoring)
# ═══════════════════════════════════════════════════════════════════════════════

phase_observability() {
    step "${CHART} PHASE 4: Observability"
    
    local repo_url=$(git remote get-url origin 2>/dev/null | sed 's/.*github.com\///' | sed 's/\.git$//')
    local commit_sha=$(git rev-parse --short HEAD)
    local branch=$(git branch --show-current)
    
    echo ""
    echo -e "${DIM}Deployment Manifest:${RESET}"
    echo -e "  ${DIM}Repository:${RESET}  $repo_url"
    echo -e "  ${DIM}Branch:${RESET}      $branch"
    echo -e "  ${DIM}Commit:${RESET}      $commit_sha"
    echo -e "  ${DIM}Timestamp:${RESET}   $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo ""
    
    if [[ "$GH_AVAILABLE" == "true" ]]; then
        log "Monitoring CI/CD pipeline..."
        echo ""
        echo -e "${CYAN}Open in browser:${RESET}"
        echo -e "  ${BLUE}https://github.com/$repo_url/actions${RESET}"
        echo ""
        
        # Try to get the workflow URL
        local run_id=$(gh run list --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || echo "")
        if [[ -n "$run_id" ]]; then
            echo -e "  ${BLUE}https://github.com/$repo_url/actions/runs/$run_id${RESET}"
        fi
        
        # Auto-open browser on macOS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            read -p "Open GitHub Actions in browser? [Y/n]: " -n 1 -r
            echo ""
            if [[ ! $REPLY =~ ^[Nn]$ ]]; then
                open "https://github.com/$repo_url/actions"
            fi
        fi
    else
        log "GitHub CLI not available"
        echo ""
        echo -e "${CYAN}Manual check:${RESET}"
        echo -e "  ${BLUE}https://github.com/$repo_url/actions${RESET}"
    fi
}

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

main() {
    print_header
    
    local total_start=$(date +%s)
    
    # Check if in project root
    if [[ ! -d "api" || ! -f "pytest.ini" ]]; then
        error "Not in project root. Run from ~/Desktop/auto-broker"
        exit 1
    fi
    
    # Run all phases
    phase_preflight
    phase_validation
    phase_deploy
    phase_observability
    
    # Summary
    local total_end=$(date +%s)
    local total_duration=$((total_end - total_start))
    
    echo ""
    echo -e "${GREEN}${SPARKLES}${BOLD} SUCCESS! ${RESET}${GREEN}Shipped in ${total_duration}s${RESET}"
    echo ""
    echo -e "${DIM}Remember: The best deployment is the one you don't have to worry about.${RESET}"
    echo ""
}

# Handle interruptions
trap 'echo -e "\n${ERROR} Deployment cancelled"; exit 130' INT

# Run
main "$@"
