#!/usr/bin/env bash
#
# update-vendor.sh - re-sync the vendored chatgpt2api image-gen + OAuth core.
#
# What it does:
#   1. Clones/fetches upstream into scratch/chatgpt2api-upstream.
#   2. Overwrites the VERBATIM file set under src/cgimg/_vendor/ from a target
#      upstream ref (default: the latest default-branch tip).
#   3. NEVER touches the LOCAL files (our single-account shim etc). Instead it
#      diffs them across the upstream range and warns if upstream changed them,
#      so you know when the shim might need attention.
#   4. Records the new commit SHA in VENDOR_REV.
#
# Usage:
#   bash scripts/update-vendor.sh                 # sync to latest upstream tip
#   bash scripts/update-vendor.sh <ref-or-sha>    # sync to a specific commit/tag
#
# After running: review the diff, then `uv run pytest tests/`. The contract test
# (tests/test_vendor_contract.py) fails loudly if upstream started calling a new
# account_service method that our shim does not handle explicitly.
#
set -euo pipefail

UPSTREAM_URL="https://github.com/basketikun/chatgpt2api.git"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="$REPO_ROOT/src/cgimg/_vendor"
REV_FILE="$REPO_ROOT/VENDOR_REV"
WORK="$REPO_ROOT/scratch/chatgpt2api-upstream"
TARGET_REF="${1:-origin/HEAD}"

# --- Files copied VERBATIM from upstream (same path in upstream root and in
#     _vendor/). Overwritten on every update. Keep in sync with the LOCAL list
#     below; together they must cover every .py under _vendor/. -------------
VERBATIM=(
  services/__init__.py
  services/config.py
  services/image_storage_service.py
  services/openai_backend_api.py
  services/protocol/conversation.py
  services/proxy_service.py
  services/storage/__init__.py
  services/storage/base.py
  services/storage/json_storage.py
  utils/__init__.py
  utils/helper.py
  utils/image_tokens.py
  utils/log.py
  utils/pkce.py
  utils/pow.py
  utils/sentinel.py
  utils/turnstile.py
)

# --- LOCAL adaptations - NEVER overwritten. The script diffs the upstream
#     counterpart across the update range and warns if it moved. -----------
LOCAL=(
  services/account_service.py
  services/protocol/__init__.py
  services/storage/factory.py
)

log()  { printf '%s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }

# --- read the currently-pinned SHA (last non-comment, non-empty line) -------
read_pinned_rev() {
  [ -f "$REV_FILE" ] || return 0
  grep -vE '^\s*(#|$)' "$REV_FILE" | tail -1 | tr -d '[:space:]'
}

# --- 1. clone / fetch upstream ---------------------------------------------
mkdir -p "$REPO_ROOT/scratch"
if [ -d "$WORK/.git" ]; then
  log "Fetching upstream into scratch/chatgpt2api-upstream ..."
  git -C "$WORK" fetch --quiet --tags origin
else
  log "Cloning upstream into scratch/chatgpt2api-upstream ..."
  git clone --quiet "$UPSTREAM_URL" "$WORK"
fi

NEW_REV="$(git -C "$WORK" rev-parse "$TARGET_REF")"
PREV_REV="$(read_pinned_rev)"
NEW_SHORT="$(git -C "$WORK" rev-parse --short "$NEW_REV")"
log ""
log "Pinned (old) : ${PREV_REV:-<none>}"
log "Target (new) : $NEW_REV"
log "Subject      : $(git -C "$WORK" log -1 --format=%s "$NEW_REV")"
log ""

if [ -n "$PREV_REV" ] && [ "$PREV_REV" = "$NEW_REV" ]; then
  log "Already at the target commit - nothing to sync."
  exit 0
fi

# --- 2. overwrite VERBATIM files (only when content actually differs) -------
changed=0
log "Syncing VERBATIM files:"
for f in "${VERBATIM[@]}"; do
  if ! git -C "$WORK" cat-file -e "$NEW_REV:$f" 2>/dev/null; then
    log "  skip (not in upstream): $f"
    continue
  fi
  dst="$VENDOR_DIR/$f"
  tmp="$(mktemp)"
  git -C "$WORK" show "$NEW_REV:$f" > "$tmp"
  # Compare ignoring CR so Windows CRLF working copies do not cause churn.
  if [ -f "$dst" ] && diff -q <(tr -d '\r' < "$dst") <(tr -d '\r' < "$tmp") >/dev/null 2>&1; then
    rm -f "$tmp"
    continue
  fi
  mkdir -p "$(dirname "$dst")"
  mv "$tmp" "$dst"
  log "  updated: $f"
  changed=$((changed + 1))
done
[ "$changed" -eq 0 ] && log "  (no verbatim files changed)"

# --- 3. warn on LOCAL files that upstream moved -----------------------------
log ""
log "Checking LOCAL shim files against upstream changes:"
shim_warn=0
for f in "${LOCAL[@]}"; do
  git -C "$WORK" cat-file -e "$NEW_REV:$f" 2>/dev/null || continue  # no upstream counterpart
  if [ -n "$PREV_REV" ] && ! git -C "$WORK" diff --quiet "$PREV_REV" "$NEW_REV" -- "$f" 2>/dev/null; then
    warn "upstream changed '$f' between ${PREV_REV:0:9}..$NEW_SHORT"
    warn "  -> your LOCAL shim ($f) may need review. Inspect with:"
    warn "     git -C scratch/chatgpt2api-upstream diff $PREV_REV $NEW_REV -- $f"
    shim_warn=$((shim_warn + 1))
  fi
done
[ "$shim_warn" -eq 0 ] && log "  OK - upstream did not touch any shimmed file."

# --- 4. record the new pinned SHA -------------------------------------------
cat > "$REV_FILE" <<EOF
# Upstream chatgpt2api commit that the VERBATIM files under src/cgimg/_vendor/
# are synced to. Managed by scripts/update-vendor.sh - the last non-comment,
# non-empty line is the pinned commit SHA. Do not edit by hand.
#
# Repo: https://github.com/basketikun/chatgpt2api
$NEW_REV
EOF

log ""
log "Done. VENDOR_REV -> $NEW_REV"
log "Next steps:"
log "  1. git diff src/cgimg/_vendor/        # review what changed"
log "  2. uv run pytest tests/               # MUST pass (incl. vendor contract test)"
log "  3. (optional) uv run cgimg gen \"smoke test\"   # live image-gen check"
[ "$shim_warn" -gt 0 ] && log "  4. REVIEW the shim warnings above before trusting this update."
exit 0
