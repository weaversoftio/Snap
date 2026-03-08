#!/bin/bash
# =============================================================================
# replace-crio.sh - Safely extract and replace crio binary from RPM
# Usage: ./replace-crio.sh <path-to-rpm>
# =============================================================================

set -euo pipefail

# --- Colors ------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()   { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()  { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }
header() { echo -e "\n${CYAN}==> $*${NC}"; }

# --- Args --------------------------------------------------------------------
RPM_FILE="${1:-}"
CRIO_BIN="/usr/bin/crio"
EXTRACT_DIR="$(mktemp -d /tmp/crio-extract.XXXXXX)"
BACKUP_SUFFIX="bak.$(date +%Y%m%d_%H%M%S)"

cleanup() {
  log "Cleaning up temp dir: $EXTRACT_DIR"
  rm -rf "$EXTRACT_DIR"
}
trap cleanup EXIT

# =============================================================================
# PREFLIGHT CHECKS
# =============================================================================
header "Preflight checks"

# 1. RPM file provided
[[ -z "$RPM_FILE" ]] && error "No RPM file specified. Usage: $0 <path-to-rpm>"

# 2. RPM file exists
[[ -f "$RPM_FILE" ]] || error "RPM file not found: $RPM_FILE"
log "RPM file found: $RPM_FILE"

# 3. Required tools
for tool in rpm2cpio cpio file sudo systemctl; do
  command -v "$tool" &>/dev/null || error "Required tool not found: $tool"
done
log "Required tools present: rpm2cpio, cpio, file, sudo, systemctl"

# 4. Current crio binary exists
[[ -f "$CRIO_BIN" ]] || error "Current crio binary not found at $CRIO_BIN"
log "Current crio binary: $CRIO_BIN"

# 5. Show current version
CURRENT_VERSION=$(${CRIO_BIN} --version 2>&1 | head -1 || echo "unknown")
log "Current crio version: $CURRENT_VERSION"

# =============================================================================
# EXTRACT BINARY FROM RPM
# =============================================================================
header "Extracting crio binary from RPM"

cd "$EXTRACT_DIR"
rpm2cpio "$OLDPWD/$RPM_FILE" | cpio -idm ./usr/bin/crio 2>/dev/null \
  || rpm2cpio "$RPM_FILE" | cpio -idm ./usr/bin/crio 2>/dev/null \
  || error "Failed to extract crio from RPM"

NEW_BIN="$EXTRACT_DIR/usr/bin/crio"
[[ -f "$NEW_BIN" ]] || error "crio binary not found in RPM at ./usr/bin/crio"
log "Extracted to: $NEW_BIN"

# Validate it's actually an ELF binary
file "$NEW_BIN" | grep -q "ELF" || error "Extracted file is not a valid ELF binary"
log "Binary type: $(file "$NEW_BIN" | cut -d: -f2 | xargs)"

# Show new version (dry run)
NEW_VERSION=$("$NEW_BIN" --version 2>&1 | head -1 || echo "unknown")
log "New crio version:     $NEW_VERSION"

# Warn if same version
if [[ "$CURRENT_VERSION" == "$NEW_VERSION" ]]; then
  warn "New binary version matches current version — continuing anyway"
fi

# =============================================================================
# CONFIRM
# =============================================================================
header "Summary"
echo "  RPM file    : $RPM_FILE"
echo "  Target      : $CRIO_BIN"
echo "  Backup      : ${CRIO_BIN}.${BACKUP_SUFFIX}"
echo "  Current ver : $CURRENT_VERSION"
echo "  New ver     : $NEW_VERSION"
echo ""
read -r -p "Proceed with replacement? [y/N] " confirm
[[ "${confirm,,}" == "y" ]] || { log "Aborted by user."; exit 0; }

# =============================================================================
# STOP SERVICES
# =============================================================================
header "Stopping services"

for svc in kubelet crio; do
  if systemctl is-active --quiet "$svc"; then
    log "Stopping $svc..."
    sudo systemctl stop "$svc" || error "Failed to stop $svc"
    log "$svc stopped"
  else
    warn "$svc is not running — skipping stop"
  fi
done

# =============================================================================
# REMOUNT /usr AS READ-WRITE
# =============================================================================
header "Checking filesystem writability"

USR_MOUNT=$(findmnt -n -o TARGET /usr 2>/dev/null || echo "/")
log "Mount point covering /usr: $USR_MOUNT"

if touch /usr/bin/.crio-write-test 2>/dev/null; then
  rm -f /usr/bin/.crio-write-test
  log "/usr is already writable"
else
  log "Remounting $USR_MOUNT as read-write..."
  sudo mount -o remount,rw "$USR_MOUNT" || error "Failed to remount $USR_MOUNT as rw"
  log "Remounted $USR_MOUNT rw"
fi

# =============================================================================
# BACKUP + REPLACE
# =============================================================================
header "Backing up existing binary"

sudo cp -v "$CRIO_BIN" "${CRIO_BIN}.${BACKUP_SUFFIX}" \
  || error "Failed to create backup"
log "Backup created: ${CRIO_BIN}.${BACKUP_SUFFIX}"

header "Installing new binary"

sudo cp -v "$NEW_BIN" "$CRIO_BIN"        || error "Failed to copy new binary"
sudo chmod 755 "$CRIO_BIN"               || error "Failed to set permissions"
sudo chown root:root "$CRIO_BIN"         || error "Failed to set ownership"
log "Binary replaced successfully"

# =============================================================================
# START SERVICES
# =============================================================================
header "Starting services"

for svc in crio kubelet; do
  log "Starting $svc..."
  sudo systemctl start "$svc" || error "Failed to start $svc"
  sleep 2
  if systemctl is-active --quiet "$svc"; then
    log "$svc is active"
  else
    error "$svc failed to start — check: journalctl -u $svc --no-pager -n 50"
  fi
done

# =============================================================================
# VERIFY
# =============================================================================
header "Verification"

INSTALLED_VERSION=$("$CRIO_BIN" --version 2>&1 | head -1 || echo "unknown")
log "Installed version: $INSTALLED_VERSION"
log "crio  status: $(systemctl is-active crio)"
log "kubelet status: $(systemctl is-active kubelet)"

echo ""
log "Done. Rollback command if needed:"
echo -e "  ${YELLOW}sudo systemctl stop kubelet crio && sudo cp ${CRIO_BIN}.${BACKUP_SUFFIX} ${CRIO_BIN} && sudo systemctl start crio kubelet${NC}"