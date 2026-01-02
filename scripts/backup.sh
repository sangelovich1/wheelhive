#!/bin/bash
# Backup WheelHive databases
# Usage: ./scripts/backup.sh [backup_dir]
#
# Environment variables:
#   BACKUP_DIR - Override default backup location
#
# Examples:
#   ./scripts/backup.sh                    # Use default ~/backups/wheelhive
#   ./scripts/backup.sh /mnt/nas/backups   # Custom location
#   BACKUP_DIR=/tmp/test ./scripts/backup.sh

set -euo pipefail

BACKUP_DIR="${1:-${BACKUP_DIR:-$HOME/backups/wheelhive}}"
DATE=$(date +%Y-%m-%d_%H%M%S)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== WheelHive Backup ==="
echo "Date: $DATE"
echo "Project: $PROJECT_DIR"
echo "Backup to: $BACKUP_DIR"
echo ""

mkdir -p "$BACKUP_DIR"

# 1. SQLite backup (using .backup for consistency during writes)
if [ -f "$PROJECT_DIR/trades.db" ]; then
    echo "Backing up trades.db..."
    sqlite3 "$PROJECT_DIR/trades.db" ".backup '$BACKUP_DIR/trades_$DATE.db'"
    SIZE=$(du -h "$BACKUP_DIR/trades_$DATE.db" | cut -f1)
    echo "  ✓ trades_$DATE.db ($SIZE)"
else
    echo "  ⚠ trades.db not found, skipping"
fi

# 2. Vector database backup (ChromaDB)
if [ -d "$PROJECT_DIR/training_materials" ]; then
    echo "Backing up vector databases..."
    tar -czf "$BACKUP_DIR/training_materials_$DATE.tar.gz" \
        -C "$PROJECT_DIR" training_materials
    SIZE=$(du -h "$BACKUP_DIR/training_materials_$DATE.tar.gz" | cut -f1)
    echo "  ✓ training_materials_$DATE.tar.gz ($SIZE)"
else
    echo "  ⚠ training_materials/ not found, skipping"
fi

# 3. Cleanup old backups (keep last 7 days)
echo ""
echo "Cleaning up backups older than 7 days..."
DELETED_COUNT=0
while IFS= read -r file; do
    rm -f "$file"
    ((DELETED_COUNT++))
done < <(find "$BACKUP_DIR" -name "trades_*.db" -mtime +7 2>/dev/null || true)
while IFS= read -r file; do
    rm -f "$file"
    ((DELETED_COUNT++))
done < <(find "$BACKUP_DIR" -name "training_materials_*.tar.gz" -mtime +7 2>/dev/null || true)
echo "  Removed $DELETED_COUNT old backup(s)"

# 4. Summary
echo ""
echo "=== Backup Complete ==="
echo "Location: $BACKUP_DIR"
echo ""
echo "Recent backups:"
ls -lht "$BACKUP_DIR" | head -10
