#!/bin/bash
# =============================================================================
# Auto-Broker Backup Script
# Oracle Cloud - Backup to Oracle Object Storage or Local
# =============================================================================

set -euo pipefail

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# Configurazione
COMPOSE_FILE="docker-compose.oracle.enterprise.yml"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_USER="${DB_USER:-autobroker}"

# Oracle Object Storage (opzionale)
OCI_BUCKET="${OCI_BUCKET:-}"
OCI_NAMESPACE="${OCI_NAMESPACE:-}"

# Crea directory backup
mkdir -p "$BACKUP_DIR"

log_info "Starting backup process..."
log_info "Backup directory: $BACKUP_DIR"

# =============================================================================
# DATABASE BACKUP
# =============================================================================
log_info "Creating database backup..."

DB_BACKUP_FILE="${BACKUP_DIR}/autobroker_db_${TIMESTAMP}.sql"

# Dump database
docker-compose -f "$COMPOSE_FILE" exec -T postgres pg_dumpall -c -U "$DB_USER" > "$DB_BACKUP_FILE" || {
    log_error "Database backup failed"
    exit 1
}

# Comprimi
gzip -f "$DB_BACKUP_FILE"
DB_BACKUP_FILE="${DB_BACKUP_FILE}.gz"
DB_SIZE=$(du -h "$DB_BACKUP_FILE" | cut -f1)

log_success "Database backup created: $DB_BACKUP_FILE ($DB_SIZE)"

# =============================================================================
# REDIS BACKUP (se persistenza attiva)
# =============================================================================
log_info "Creating Redis backup..."

REDIS_BACKUP_FILE="${BACKUP_DIR}/autobroker_redis_${TIMESTAMP}.rdb"
docker-compose -f "$COMPOSE_FILE" exec -T redis cat /data/dump.rdb > "$REDIS_BACKUP_FILE" 2>/dev/null || {
    log_warn "Redis backup skipped (no persistence file)"
    REDIS_BACKUP_FILE=""
}

if [[ -n "$REDIS_BACKUP_FILE" && -s "$REDIS_BACKUP_FILE" ]]; then
    gzip -f "$REDIS_BACKUP_FILE"
    REDIS_BACKUP_FILE="${REDIS_BACKUP_FILE}.gz"
    REDIS_SIZE=$(du -h "$REDIS_BACKUP_FILE" | cut -f1)
    log_success "Redis backup created: $REDIS_BACKUP_FILE ($REDIS_SIZE)"
fi

# =============================================================================
# ENVIRONMENT BACKUP
# =============================================================================
log_info "Backing up environment configuration..."

ENV_BACKUP_FILE="${BACKUP_DIR}/autobroker_env_${TIMESTAMP}.tar.gz"
tar -czf "$ENV_BACKUP_FILE" .env.oracle nginx/ssl 2>/dev/null || {
    tar -czf "$ENV_BACKUP_FILE" .env.oracle 2>/dev/null || {
        log_warn "Environment backup skipped (no .env.oracle found)"
        ENV_BACKUP_FILE=""
    }
}

if [[ -n "$ENV_BACKUP_FILE" && -f "$ENV_BACKUP_FILE" ]]; then
    ENV_SIZE=$(du -h "$ENV_BACKUP_FILE" | cut -f1)
    log_success "Environment backup created: $ENV_BACKUP_FILE ($ENV_SIZE)"
fi

# =============================================================================
# UPLOAD TO ORACLE OBJECT STORAGE (se configurato)
# =============================================================================
if [[ -n "$OCI_BUCKET" && -n "$OCI_NAMESPACE" ]]; then
    log_info "Uploading to Oracle Object Storage..."
    
    for file in "$DB_BACKUP_FILE" ${REDIS_BACKUP_FILE:+$REDIS_BACKUP_FILE} ${ENV_BACKUP_FILE:+$ENV_BACKUP_FILE}; do
        if [[ -f "$file" ]]; then
            oci os object put --bucket-name "$OCI_BUCKET" --namespace-name "$OCI_NAMESPACE" --file "$file" --force 2>/dev/null && {
                log_success "Uploaded: $(basename "$file")"
            } || {
                log_warn "Failed to upload: $(basename "$file")"
            }
        fi
    done
fi

# =============================================================================
# CLEANUP OLD BACKUPS
# =============================================================================
log_info "Cleaning up old backups (retention: $RETENTION_DAYS days)..."

find "$BACKUP_DIR" -name "autobroker_*.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null && {
    log_success "Old backups cleaned"
} || {
    log_warn "No old backups to clean"
}

# =============================================================================
# BACKUP SUMMARY
# =============================================================================
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "                     📦 BACKUP COMPLETE                         "
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  Backup files:"
[[ -f "$DB_BACKUP_FILE" ]] && echo "    • Database: $DB_BACKUP_FILE ($DB_SIZE)"
[[ -n "$REDIS_BACKUP_FILE" && -f "$REDIS_BACKUP_FILE" ]] && echo "    • Redis:    $REDIS_BACKUP_FILE ($REDIS_SIZE)"
[[ -n "$ENV_BACKUP_FILE" && -f "$ENV_BACKUP_FILE" ]] && echo "    • Config:   $ENV_BACKUP_FILE ($ENV_SIZE)"
echo ""
echo "  Location: $BACKUP_DIR"
echo "  Timestamp: $(date)"
echo ""
echo "═══════════════════════════════════════════════════════════════"

log_success "Backup process completed successfully!"
