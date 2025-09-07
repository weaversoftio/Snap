#!/usr/bin/env bash
set -Eeuo pipefail

# --- settings you asked for ---
RUNC_VERSION="1.2.4"
RUNC_URL="http://snapapi.apps-crc.testing/download/runc/${RUNC_VERSION}"
RUNC_DIR="/opt/bin"
RUNC_BIN="${RUNC_DIR}/runc"
RUNC_VER_BIN="${RUNC_DIR}/runc-${RUNC_VERSION}"

CRIO_CONF_DIR="/etc/crio/crio.conf.d"
CRIO_CRIU_DROPIN="${CRIO_CONF_DIR}/05-enable-criu.conf"
CRIO_RUNC_DROPIN="${CRIO_CONF_DIR}/06-runc-path.conf"
CRIU_CONF_DIR="/etc/criu"
CRIU_RUNC_CONF="${CRIU_CONF_DIR}/runc.conf"

changed_any=0

need_root() {
  if [[ $EUID -ne 0 ]]; then echo "ERROR: run as root"; exit 1; fi
}

have_cmd() { command -v "$1" >/dev/null 2>&1; }

ensure_prereqs() {
  have_cmd crio || { echo "ERROR: crio not found"; exit 1; }
  have_cmd curl || { echo "ERROR: curl not found"; exit 1; }
  if ! have_cmd criu; then
    echo "ERROR: CRIU not installed. Install CRIU (RHEL workers) before continuing."
    exit 1
  fi
  echo "INFO: CRIU version: $(criu --version || true)"
}

ensure_dirs() {
  mkdir -p "$CRIO_CONF_DIR" "$CRIU_CONF_DIR" "$RUNC_DIR"
}

ensure_criu_enabled() {
  # write drop-in only if missing or content differs
  desired=$'[crio.runtime]\nenable_criu_support = true\n'
  if [[ ! -f "$CRIO_CRIU_DROPIN" ]] || ! diff -q <(printf "%s" "$desired") "$CRIO_CRIU_DROPIN" >/dev/null 2>&1; then
    printf "%s" "$desired" > "$CRIO_CRIU_DROPIN"
    chmod 0644 "$CRIO_CRIU_DROPIN"
    echo "INFO: set enable_criu_support = true"
    changed_any=1
  else
    echo "SKIP: CRI-O CRIU support already enabled"
  fi

  # runc.conf for CRIU flags (matches your earlier choice)
  desired_criu_flags=$'tcp-close\n'
  if [[ ! -f "$CRIU_RUNC_CONF" ]] || ! diff -q <(printf "%s" "$desired_criu_flags") "$CRIU_RUNC_CONF" >/dev/null 2>&1; then
    printf "%s" "$desired_criu_flags" > "$CRIU_RUNC_CONF"
    chmod 0644 "$CRIU_RUNC_CONF"
    echo "INFO: wrote $CRIU_RUNC_CONF"
  else
    echo "SKIP: $CRIU_RUNC_CONF already set"
  fi
}

current_runc_version() {
  if have_cmd runc; then
    runc --version 2>/dev/null | awk '/version/ {print $3; exit}'
  else
    echo ""
  fi
}

install_runc() {
  current_ver="$(current_runc_version || true)"
  if [[ "$current_ver" == "$RUNC_VERSION" ]] && [[ -e "$RUNC_BIN" ]]; then
    echo "SKIP: runc $RUNC_VERSION already in use ($(readlink -f "$RUNC_BIN"))"
    return
  fi

  if [[ ! -f "$RUNC_VER_BIN" ]]; then
    echo "INFO: downloading runc $RUNC_VERSION from $RUNC_URL"
    # CRC routes often use self-signed certs; -k avoids TLS trust issues on the node
    curl -fLk --retry 3 --output "$RUNC_VER_BIN" "$RUNC_URL"
    chmod 0755 "$RUNC_VER_BIN"
    # quick sanity: binary?
    file "$RUNC_VER_BIN" || true
  else
    echo "SKIP: found $RUNC_VER_BIN"
  fi

  # update symlink atomically
  ln -sfn "$RUNC_VER_BIN" "$RUNC_BIN"
  echo "INFO: runc symlink now -> $(readlink -f "$RUNC_BIN")"
  echo "INFO: runc version now: $("$RUNC_BIN" --version 2>/dev/null | head -1)"
  changed_any=1
}

point_crio_to_runc_path() {
  desired=$'[crio.runtime.runtimes.runc]\nruntime_path = "/opt/bin/runc"\nruntime_type = "oci"\nruntime_root = "/run/runc"\n'
  if [[ ! -f "$CRIO_RUNC_DROPIN" ]] || ! diff -q <(printf "%s" "$desired") "$CRIO_RUNC_DROPIN" >/dev/null 2>&1; then
    printf "%s" "$desired" > "$CRIO_RUNC_DROPIN"
    chmod 0644 "$CRIO_RUNC_DROPIN"
    echo "INFO: configured CRI-O runc runtime_path = /opt/bin/runc"
    changed_any=1
  else
    echo "SKIP: CRI-O runc runtime_path already set to /opt/bin/runc"
  fi
}

maybe_restart_crio() {
  if [[ "$changed_any" -eq 1 ]]; then
    echo "INFO: restarting CRI-O..."
    systemctl restart crio
  else
    echo "SKIP: no changes; CRI-O restart not needed"
  fi
  systemctl is-active --quiet crio && echo "INFO: CRI-O is active."
}

show_effective_config() {
  echo "---- effective CRI-O runtime bits ----"
  crio config 2>/dev/null | awk '
    /^\[crio.runtime\]/ {inrt=1; next}
    /^\[/ && $0 !~ /^\[crio.runtime\]/ {inrt=0}
    inrt && /default_runtime/ {print; found=1}
    inrt && /\[crio.runtime.runtimes.runc\]/ {inrunc=1; print; next}
    inrunc && /^\[/ {inrunc=0}
    inrunc && /(runtime_path|runtime_type|runtime_root)/ {print}
  '
  echo "--------------------------------------"
}

main() {
  need_root
  echo ""
  ensure_prereqs
  echo ""
  ensure_dirs
  echo ""
  ensure_criu_enabled
  echo ""
  install_runc
  echo ""
  point_crio_to_runc_path
  echo ""
  maybe_restart_crio
  echo ""
  show_effective_config
  echo ""
  echo "DONE. You can now checkpoint containers using the Kubelet Checkpoint API."
}

main "$@"