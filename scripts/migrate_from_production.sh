#!/bin/bash
# Migrate WheelHive databases from production to this machine
# Usage: ./scripts/migrate_from_production.sh <remote_host> [remote_path]
#
# Examples:
#   ./scripts/migrate_from_production.sh prod-server
#   ./scripts/migrate_from_production.sh user@192.168.1.100 /opt/wheelhive
#   ./scripts/migrate_from_production.sh prod-server ~/code/wheelhive
#
# Prerequisites:
#   - SSH access to remote host (key-based auth recommended)
#   - rsync installed on both machines
#   - Remote database should not be actively written to during migration

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/migration_backup_$(date +%Y%m%d_%H%M%S)"
REMOTE_HOST="${1:-}"
REMOTE_PATH="${2:-~/code/wheelhive}"

# Required tables for validation
REQUIRED_TABLES=(
    "trades"
    "dividends"
    "shares"
    "deposits"
    "harvested_messages"
    "guild_channels"
    "valid_tickers"
    "system_settings"
)

usage() {
    echo "Usage: $0 <remote_host> [remote_path]"
    echo ""
    echo "Arguments:"
    echo "  remote_host   SSH host (e.g., prod-server, user@192.168.1.100)"
    echo "  remote_path   Path to wheelhive on remote (default: ~/code/wheelhive)"
    echo ""
    echo "Examples:"
    echo "  $0 prod-server"
    echo "  $0 user@192.168.1.100 /opt/wheelhive"
    exit 1
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    if [ -z "$REMOTE_HOST" ]; then
        log_error "Remote host is required"
        usage
    fi

    if ! command -v rsync &> /dev/null; then
        log_error "rsync is not installed. Install with: sudo apt install rsync"
        exit 1
    fi

    if ! command -v sqlite3 &> /dev/null; then
        log_error "sqlite3 is not installed. Install with: sudo apt install sqlite3"
        exit 1
    fi

    # Test SSH connection
    log_info "Testing SSH connection to $REMOTE_HOST..."
    if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$REMOTE_HOST" "echo 'SSH OK'" &> /dev/null; then
        log_error "Cannot connect to $REMOTE_HOST via SSH"
        log_error "Ensure SSH key is set up: ssh-copy-id $REMOTE_HOST"
        exit 1
    fi

    log_info "Prerequisites OK"
}

# Backup local database if it exists
backup_local() {
    log_info "Backing up local data..."
    mkdir -p "$BACKUP_DIR"

    if [ -f "$PROJECT_DIR/trades.db" ]; then
        cp "$PROJECT_DIR/trades.db" "$BACKUP_DIR/"
        log_info "  Backed up trades.db"
    fi

    if [ -d "$PROJECT_DIR/training_materials" ]; then
        cp -r "$PROJECT_DIR/training_materials" "$BACKUP_DIR/"
        log_info "  Backed up training_materials/"
    fi

    log_info "Local backup saved to: $BACKUP_DIR"
}

# Check remote database exists and get stats
check_remote_db() {
    log_info "Checking remote database..."

    # Check if remote database exists
    if ! ssh "$REMOTE_HOST" "test -f $REMOTE_PATH/trades.db"; then
        log_error "Remote database not found at $REMOTE_HOST:$REMOTE_PATH/trades.db"
        exit 1
    fi

    # Get remote database size
    REMOTE_SIZE=$(ssh "$REMOTE_HOST" "du -h $REMOTE_PATH/trades.db | cut -f1")
    log_info "  Remote database size: $REMOTE_SIZE"

    # Get remote table counts
    log_info "  Remote table row counts:"
    for table in "${REQUIRED_TABLES[@]}"; do
        COUNT=$(ssh "$REMOTE_HOST" "sqlite3 $REMOTE_PATH/trades.db 'SELECT COUNT(*) FROM $table' 2>/dev/null" || echo "0")
        echo "    - $table: $COUNT rows"
    done
}

# Copy database from remote
copy_database() {
    log_info "Copying database from $REMOTE_HOST..."

    # Use rsync for efficient transfer with progress
    rsync -avz --progress \
        "$REMOTE_HOST:$REMOTE_PATH/trades.db" \
        "$PROJECT_DIR/trades.db.new"

    # Also copy WAL files if they exist (for consistency)
    ssh "$REMOTE_HOST" "test -f $REMOTE_PATH/trades.db-wal" && \
        rsync -avz "$REMOTE_HOST:$REMOTE_PATH/trades.db-wal" "$PROJECT_DIR/" || true
    ssh "$REMOTE_HOST" "test -f $REMOTE_PATH/trades.db-shm" && \
        rsync -avz "$REMOTE_HOST:$REMOTE_PATH/trades.db-shm" "$PROJECT_DIR/" || true

    log_info "Database copied successfully"
}

# Copy training materials (vector database)
copy_training_materials() {
    log_info "Checking for training materials..."

    if ssh "$REMOTE_HOST" "test -d $REMOTE_PATH/training_materials"; then
        REMOTE_TM_SIZE=$(ssh "$REMOTE_HOST" "du -sh $REMOTE_PATH/training_materials | cut -f1")
        log_info "  Remote training_materials size: $REMOTE_TM_SIZE"

        log_info "Copying training materials..."
        rsync -avz --progress --delete \
            "$REMOTE_HOST:$REMOTE_PATH/training_materials/" \
            "$PROJECT_DIR/training_materials/"

        log_info "Training materials copied successfully"
    else
        log_warn "No training_materials directory found on remote"
    fi
}

# Validate the copied database
validate_database() {
    log_info "Validating copied database..."

    # Check integrity
    INTEGRITY=$(sqlite3 "$PROJECT_DIR/trades.db.new" "PRAGMA integrity_check" 2>&1)
    if [ "$INTEGRITY" != "ok" ]; then
        log_error "Database integrity check failed: $INTEGRITY"
        exit 1
    fi
    log_info "  Integrity check: OK"

    # Check required tables exist
    for table in "${REQUIRED_TABLES[@]}"; do
        if ! sqlite3 "$PROJECT_DIR/trades.db.new" "SELECT 1 FROM $table LIMIT 1" &> /dev/null; then
            log_error "Required table '$table' not found or empty"
            exit 1
        fi
    done
    log_info "  Required tables: OK"

    # Show local vs remote comparison
    log_info "  Validation row counts:"
    for table in "${REQUIRED_TABLES[@]}"; do
        COUNT=$(sqlite3 "$PROJECT_DIR/trades.db.new" "SELECT COUNT(*) FROM $table" 2>/dev/null || echo "0")
        echo "    - $table: $COUNT rows"
    done
}

# Finalize migration
finalize() {
    log_info "Finalizing migration..."

    # Replace old database with new one
    if [ -f "$PROJECT_DIR/trades.db" ]; then
        mv "$PROJECT_DIR/trades.db" "$PROJECT_DIR/trades.db.old"
    fi
    mv "$PROJECT_DIR/trades.db.new" "$PROJECT_DIR/trades.db"

    # Clean up old file
    rm -f "$PROJECT_DIR/trades.db.old"

    log_info "Migration complete!"
}

# Run post-migration tasks
post_migration() {
    log_info "Running post-migration tasks..."

    # Migrate settings if needed
    if [ -f "$PROJECT_DIR/scripts/migrate_settings_to_db.py" ]; then
        log_info "  Checking system settings..."
        SETTINGS_COUNT=$(sqlite3 "$PROJECT_DIR/trades.db" "SELECT COUNT(*) FROM system_settings" 2>/dev/null || echo "0")
        if [ "$SETTINGS_COUNT" -eq 0 ]; then
            log_info "  Running settings migration..."
            cd "$PROJECT_DIR"
            source .bot_venv/bin/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null || true
            python scripts/migrate_settings_to_db.py || log_warn "Settings migration skipped (run manually if needed)"
        else
            log_info "  System settings already populated ($SETTINGS_COUNT entries)"
        fi
    fi

    # Verify CLI works
    log_info "  Verifying CLI..."
    cd "$PROJECT_DIR"
    if python src/cli.py admin list-users &> /dev/null; then
        log_info "  CLI verification: OK"
    else
        log_warn "  CLI verification failed (check virtual environment)"
    fi
}

# Print summary
print_summary() {
    echo ""
    echo "=========================================="
    echo -e "${GREEN}Migration Complete!${NC}"
    echo "=========================================="
    echo ""
    echo "Source:      $REMOTE_HOST:$REMOTE_PATH"
    echo "Destination: $PROJECT_DIR"
    echo "Backup:      $BACKUP_DIR"
    echo ""
    echo "Next steps:"
    echo "  1. Verify data: python src/cli.py admin list-users"
    echo "  2. Test queries: python src/cli.py tx options list --username <user>"
    echo "  3. Start bot:    python src/bot.py"
    echo ""
    echo "To rollback:"
    echo "  cp $BACKUP_DIR/trades.db $PROJECT_DIR/trades.db"
    echo ""
}

# Main execution
main() {
    echo "=========================================="
    echo "WheelHive Production Migration"
    echo "=========================================="
    echo ""

    check_prerequisites
    backup_local
    check_remote_db
    copy_database
    copy_training_materials
    validate_database
    finalize
    post_migration
    print_summary
}

main
