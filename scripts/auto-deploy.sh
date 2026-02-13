#!/usr/bin/env bash
################################################################################
# AUTO-DEPLOY ENTERPRISE SCRIPT - Big Tech Platform Engineering 2026
# GitOps-driven deployment with observability and self-healing
################################################################################

set -euo pipefail
IFS=$'\n\t'

# Colors and formatting
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color
readonly BOLD='\033[1m'

# Configuration
readonly PROJECT_NAME="auto-broker"
readonly GITHUB_WORKFLOW="test.yml"
readonly MAX_RETRIES=3
readonly RETRY_DELAY=5
readonly PIPELINE_TIMEOUT=300  # 5 minutes

# Logging functions
log_info() { echo -e "${BLUE}ℹ️  [INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}✅ [SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}⚠️  [WARN]${NC} $1"; }
log_error() { echo -e "${RED}❌ [ERROR]${NC} $1"; }
log_section() { echo -e "\n${CYAN}${BOLD}═══════════════════════════════════════════════════════════${NC}"; echo -e "${CYAN}${BOLD}   $1${NC}"; echo -e "${CYAN}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"; }

# Check prerequisites
check_prerequisites() {
    log_section "🔍 CHECKING PREREQUISITES"
    
    local missing=()
    
    if ! command -v git &> /dev/null; then
        missing+=("git")
    fi
    
    if ! command -v gh &> /dev/null; then
        log_warn "GitHub CLI (gh) not installed. Installing..."
        install_github_cli
    fi
    
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing prerequisites: ${missing[*]}"
        exit 1
    fi
    
    # Check git authentication
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        log_error "Not in a git repository"
        exit 1
    fi
    
    # Check GitHub CLI auth
    if ! gh auth status &> /dev/null; then
        log_warn "GitHub CLI not authenticated"
        log_info "Run: gh auth login"
        exit 1
    fi
    
    log_success "All prerequisites satisfied"
}

# Install GitHub CLI if missing
install_github_cli() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command -v brew &> /dev/null; then
            brew install gh
        else
            log_error "Homebrew not installed. Please install GitHub CLI manually"
            exit 1
        fi
    else
        log_error "Automatic install supported only on macOS. Install gh manually"
        exit 1
    fi
}

# Get repository info
get_repo_info() {
    local remote_url
    remote_url=$(git remote get-url origin 2>/dev/null || echo "")
    
    if [[ -z "$remote_url" ]]; then
        log_error "No remote origin configured"
        exit 1
    fi
    
    # Extract owner/repo from URL
    local repo
    if [[ "$remote_url" == *"github.com"* ]]; then
        repo=$(echo "$remote_url" | sed -E 's/.*github.com[:\/]//' | sed 's/\.git$//')
    else
        log_error "Not a GitHub repository"
        exit 1
    fi
    
    echo "$repo"
}

# Pre-deployment checks
pre_deployment_checks() {
    log_section "🔍 PRE-DEPLOYMENT CHECKS"
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD --; then
        log_warn "Uncommitted changes detected"
        git status --short
        
        read -p "Auto-commit changes? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            git add .
            git commit -m "chore: auto-commit before deployment [skip ci]"
            log_success "Changes committed"
        else
            log_error "Cannot deploy with uncommitted changes"
            exit 1
        fi
    fi
    
    # Check branch
    local current_branch
    current_branch=$(git branch --show-current)
    log_info "Current branch: $current_branch"
    
    if [[ "$current_branch" != "main" && "$current_branch" != "master" ]]; then
        log_warn "Not on main/master branch ($current_branch)"
        read -p "Continue anyway? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Check if tests pass locally (optional)
    log_info "Running quick validation..."
    if make test-unit > /dev/null 2>&1; then
        log_success "Unit tests pass"
    else
        log_warn "Unit tests failing - deployment may fail"
    fi
}

# Deploy with retry logic
deploy_with_retry() {
    log_section "🚀 DEPLOYMENT"
    
    local attempt=1
    local success=false
    
    while [[ $attempt -le $MAX_RETRIES ]]; do
        log_info "Push attempt $attempt/$MAX_RETRIES..."
        
        if git push origin "$(git branch --show-current)" 2>&1; then
            success=true
            break
        else
            log_warn "Push failed, retrying in ${RETRY_DELAY}s..."
            sleep $RETRY_DELAY
            ((attempt++))
        fi
    done
    
    if [[ "$success" == false ]]; then
        log_error "Deployment failed after $MAX_RETRIES attempts"
        exit 1
    fi
    
    log_success "Code pushed successfully"
}

# Monitor pipeline
monitor_pipeline() {
    log_section "⏳ MONITORING PIPELINE"
    
    local repo=$1
    local run_id
    local status=""
    local elapsed=0
    local check_interval=10
    
    log_info "Repository: $repo"
    log_info "Waiting for workflow to start..."
    
    # Wait for run to appear
    sleep 5
    
    # Get the latest run
    for i in {1..12}; do
        run_id=$(gh run list --repo "$repo" --workflow="$GITHUB_WORKFLOW" --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || echo "")
        
        if [[ -n "$run_id" ]]; then
            break
        fi
        
        log_info "Waiting for workflow to appear... ($i/12)"
        sleep 5
    done
    
    if [[ -z "$run_id" ]]; then
        log_warn "Could not find workflow run"
        return 1
    fi
    
    log_info "Found workflow run: $run_id"
    log_info "Monitoring progress (timeout: ${PIPELINE_TIMEOUT}s)..."
    
    # Monitor until completion
    while [[ $elapsed -lt $PIPELINE_TIMEOUT ]]; do
        status=$(gh run view "$run_id" --repo "$repo" --json status -q '.status' 2>/dev/null || echo "unknown")
        conclusion=$(gh run view "$run_id" --repo "$repo" --json conclusion -q '.conclusion' 2>/dev/null || echo "")
        
        case "$status" in
            "completed")
                if [[ "$conclusion" == "success" ]]; then
                    log_success "Pipeline completed successfully!"
                    return 0
                else
                    log_error "Pipeline failed with conclusion: $conclusion"
                    gh run view "$run_id" --repo "$repo" --log-failed
                    return 1
                fi
                ;;
            "in_progress"|"queued"|"waiting")
                log_info "Pipeline status: $status (${elapsed}s elapsed)"
                ;;
            *)
                log_warn "Unknown status: $status"
                ;;
        esac
        
        sleep $check_interval
        ((elapsed+=check_interval))
    done
    
    log_warn "Pipeline monitoring timed out after ${PIPELINE_TIMEOUT}s"
    log_info "Check manually: https://github.com/$repo/actions/runs/$run_id"
    
    return 1
}

# Check coverage from API
check_coverage() {
    log_section "📊 COVERAGE CHECK"
    
    local repo=$1
    local run_id=$2
    
    log_info "Fetching coverage report..."
    
    # Wait for artifacts
    sleep 10
    
    # Try to get coverage from workflow logs or artifacts
    if gh run download "$run_id" --repo "$repo" --name coverage-report -D /tmp/coverage 2>/dev/null; then
        if [[ -f "/tmp/coverage/coverage.xml" ]]; then
            local coverage_pct
            coverage_pct=$(grep -o 'line-rate="[0-9.]*"' /tmp/coverage/coverage.xml | head -1 | sed 's/line-rate="//' | sed 's/"//' | awk '{printf "%.0f", $1*100}')
            
            if [[ "$coverage_pct" -ge 100 ]]; then
                log_success "Coverage: ${coverage_pct}% 🎉"
            else
                log_warn "Coverage: ${coverage_pct}% (target: 100%)"
            fi
        fi
    else
        log_info "Coverage artifacts not available yet"
    fi
    
    # Open coverage HTML if available locally
    if [[ -f "htmlcov/index.html" ]]; then
        log_info "Opening local coverage report..."
        open htmlcov/index.html 2>/dev/null || true
    fi
}

# Generate deployment summary
generate_summary() {
    log_section "📋 DEPLOYMENT SUMMARY"
    
    local repo=$1
    local commit_sha
    commit_sha=$(git rev-parse --short HEAD)
    
    echo -e "${CYAN}Repository:${NC} $repo"
    echo -e "${CYAN}Commit:${NC} $commit_sha"
    echo -e "${CYAN}Branch:${NC} $(git branch --show-current)"
    echo -e "${CYAN}Workflow:${NC} $GITHUB_WORKFLOW"
    echo ""
    echo -e "${CYAN}Links:${NC}"
    echo -e "  • Actions: https://github.com/$repo/actions"
    echo -e "  • Pull Requests: https://github.com/$repo/pulls"
    echo ""
    
    log_success "Deployment process completed!"
}

# Main execution
main() {
    echo -e "${CYAN}${BOLD}"
    cat << 'EOF'
    _         _       _                         _   
   / \  _   _| |_ ___| |__   ___ _ __ _ __ ___ | |_ 
  / _ \| | | | __/ _ \ '_ \ / _ \ '__| '_ ` _ \| __|
 / ___ \ |_| | ||  __/ |_) |  __/ |  | | | | | | |_ 
/_/   \_\__,_|\__\___|_.__/ \___|_|  |_| |_| |_|\__|
                                                    
EOF
    echo -e "${NC}"
    
    log_section "🚀 AUTO-DEPLOY ENTERPRISE - 2026"
    
    # Check if in correct directory
    if [[ ! -f "pyproject.toml" && ! -f "setup.py" && ! -d "api" ]]; then
        log_error "Not in project root directory"
        exit 1
    fi
    
    check_prerequisites
    
    local repo
    repo=$(get_repo_info)
    log_info "Target repository: $repo"
    
    pre_deployment_checks
    deploy_with_retry
    
    # Try to monitor pipeline (optional, don't fail if it doesn't work)
    if command -v gh &> /dev/null && gh auth status &> /dev/null; then
        if monitor_pipeline "$repo"; then
            check_coverage "$repo" ""
        fi
    else
        log_info "GitHub CLI not available for pipeline monitoring"
        log_info "Check status manually: https://github.com/$repo/actions"
    fi
    
    generate_summary "$repo"
}

# Handle script interruption
trap 'log_error "Deployment interrupted"; exit 130' INT TERM

# Run main
main "$@"
