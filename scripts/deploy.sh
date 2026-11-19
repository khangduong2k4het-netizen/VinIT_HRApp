#!/usr/bin/env bash
# ============================================================================
# Smart deploy for VinIT HRApp on a PM2/no-Docker VPS (idempotent).
#
#   git uphra     → 1. pull code (skip everything when already up to date)
#   2. install Node deps only when frontend/package*.json changed
#      (+ Python deps only when backend/pyproject.toml changed)
#   3. stop on Supabase migration changes — this script never applies
#      supabase/migrations automatically; rerun with --migrations-verified
#      after the migration has been applied/verified outside the VPS deploy
#   4. rebuild Next only when frontend source/config/deps changed; PM2 runs
#      `next start` directly from frontend, so no standalone asset copy
#   5. pm2 restart — hra-frontend after a build; hra-backend after backend
#      Python or dependency changes; both after --force
#
# Recommended alias on a VPS shared with other projects (Git global aliases
# are per OS user, not per repository, so each project needs a unique name):
#   git config --global alias.uphra '!bash /home/ubuntu/hra/scripts/deploy.sh'
#
# Usage:
#   git uphra                                   # full smart run for HRA
#   git uphra arena/ea6e2570-vinit-hrapp        # deploy a specific HRA branch
#   bash scripts/deploy.sh                      # full smart run
#   bash scripts/deploy.sh --force              # ignore markers, do everything
#   bash scripts/deploy.sh --branch arena/ea6e2570-vinit-hrapp
#   bash scripts/deploy.sh --migrations-verified
#
# Optional env overrides:
#   DEPLOY_BRANCH=... PM2_BACKEND=hra-backend PM2_FRONTEND=hra-frontend
#   BACKEND_HEALTH_URL=http://127.0.0.1:8005/health/ready
#   FRONTEND_URL=http://127.0.0.1:3005
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."

STATE_DIR=".deploy-state"
mkdir -p "$STATE_DIR"
MARK="$STATE_DIR/last-deploy.env"
PENDING_FILE="$STATE_DIR/pending-restarts"

PM2_FRONTEND="${PM2_FRONTEND:-hra-frontend}"
PM2_BACKEND="${PM2_BACKEND:-hra-backend}"
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://127.0.0.1:8005/health/ready}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:3005}"

FORCE=0
MIGRATIONS_VERIFIED=0
BRANCH="${DEPLOY_BRANCH:-}"

usage() {
  sed -n '1,45p' "$0"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1; shift ;;
    --migrations-verified) MIGRATIONS_VERIFIED=1; shift ;;
    --branch)
      [[ $# -ge 2 ]] || { echo "--branch requires a value" >&2; exit 64; }
      BRANCH="$2"; shift 2 ;;
    --branch=*) BRANCH="${1#--branch=}"; shift ;;
    --) shift ;;
    -h|--help) usage; exit 0 ;;
    -*)
      echo "Unknown argument: $1" >&2; usage >&2; exit 64 ;;
    *)
      if [[ -z "$BRANCH" ]]; then
        BRANCH="$1"; shift
      else
        echo "Unknown argument: $1" >&2; usage >&2; exit 64
      fi
      ;;
  esac
done

if [[ -z "$BRANCH" ]]; then
  BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
fi
if [[ -z "$BRANCH" ]]; then
  echo "[deploy] Detached HEAD: set DEPLOY_BRANCH or pass --branch <branch>." >&2
  exit 2
fi

log()  { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[  ok  ]\033[0m %s\n' "$*"; }
skip() { printf '\033[2m[ skip ]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[ warn ]\033[0m %s\n' "$*"; }

pm2_restart() {
  local name="$1"
  if ! command -v pm2 >/dev/null 2>&1; then
    warn "pm2 not installed — start/reload $name manually"
    return 1
  fi
  if pm2 describe "$name" >/dev/null 2>&1; then
    if pm2 restart "$name" --update-env >/dev/null; then
      ok "pm2: $name restarted"
      return 0
    fi
    warn "pm2 restart $name failed"
    return 1
  fi
  warn "pm2 process '$name' not found — check 'pm2 list'"
  return 1
}

wait_for_url() {
  local label="$1" url="$2" tries="${3:-30}" i
  for i in $(seq 1 "$tries"); do
    if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
      ok "$label ready: $url"
      return 0
    fi
    sleep 1
  done
  warn "$label not ready after ${tries}s: $url"
  return 1
}

hash_stream() {
  sha256sum | cut -d' ' -f1
}

hash_files() {
  # Reads NUL-delimited file paths on stdin.
  LC_ALL=C sort -z | xargs -0 -r sha256sum 2>/dev/null | hash_stream
}

frontend_deps_hash() {
  printf '%s\0' frontend/package.json frontend/package-lock.json | hash_files
}

python_deps_hash() {
  printf '%s\0' backend/pyproject.toml | hash_files
}

migrations_hash() {
  find supabase/migrations -name '*.sql' -type f -print0 2>/dev/null | hash_files
}

frontend_src_hash() {
  {
    find frontend/src frontend/public -type f -print0 2>/dev/null
    for f in \
      frontend/next.config.js \
      frontend/tsconfig.json \
      frontend/package.json \
      frontend/package-lock.json \
      frontend/postcss.config.js \
      frontend/postcss.config.mjs \
      frontend/tailwind.config.js \
      frontend/tailwind.config.ts; do
      [[ -f "$f" ]] && printf '%s\0' "$f"
    done
  } | hash_files
}

backend_src_hash() {
  find backend/app -type f -name '*.py' -print0 2>/dev/null | hash_files
}

frontend_build_missing() {
  [[ ! -f frontend/.next/BUILD_ID ]]
}

frontend_node_modules_usable() {
  [[ -f frontend/node_modules/.package-lock.json ]] || return 1
  (cd frontend && npm ls --depth=0 >/dev/null 2>&1)
}

pm2_frontend_uses_standalone() {
  command -v pm2 >/dev/null 2>&1 || return 1
  command -v node >/dev/null 2>&1 || return 1
  pm2 jlist 2>/dev/null | PM2_PROCESS_NAME="$PM2_FRONTEND" node -e '
    let input = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => { input += chunk; });
    process.stdin.on("end", () => {
      try {
        const apps = JSON.parse(input);
        const app = apps.find((item) => item.name === process.env.PM2_PROCESS_NAME);
        if (!app) process.exit(1);
        const env = app.pm2_env || {};
        const args = Array.isArray(env.args) ? env.args.join(" ") : (env.args || "");
        const runtime = [env.pm_cwd, env.pm_exec_path, args].filter(Boolean).join(" ");
        process.exit(runtime.includes(".next/standalone") ? 0 : 1);
      } catch {
        process.exit(1);
      }
    });
  '
}

# ─── Load previous state ────────────────────────────────────────────────────
PREV_LOCK=""; PREV_MIG=""; PREV_SRC=""; PREV_PY_DEPS=""; PREV_PY_HASH=""; PREV_BRANCH=""
# STALE-GUARD: a build whose pm2 restart failed (or was skipped because pm2
# was momentarily unavailable) must NOT be forgotten — retry the restart on
# the very next run, even when nothing else changed.
PENDING_FRONTEND_RESTART=0
PENDING_BACKEND_RESTART=0
if [[ -f "$PENDING_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$PENDING_FILE"
fi
case "$PENDING_FRONTEND_RESTART" in 0|1) ;; *) PENDING_FRONTEND_RESTART=0 ;; esac
case "$PENDING_BACKEND_RESTART" in 0|1) ;; *) PENDING_BACKEND_RESTART=0 ;; esac

if [[ -f "$MARK" && $FORCE -eq 0 ]]; then
  # shellcheck disable=SC1090
  source "$MARK"
fi
MARK_PREV_MIG=""
if [[ -f "$MARK" ]]; then
  MARK_PREV_MIG="$(grep '^PREV_MIG=' "$MARK" 2>/dev/null | tail -1 | cut -d= -f2- || true)"
fi

STARTED=$(date +%s)
log "Smart deploy VinIT HRApp — repo: $(pwd) — branch: $BRANCH — PM2: $PM2_BACKEND/$PM2_FRONTEND"

if pm2_frontend_uses_standalone; then
  warn "PM2 process $PM2_FRONTEND still runs the Next.js standalone bundle"
  warn "switch its ecosystem entry to node_modules/next/dist/bin/next with args 'start --hostname 127.0.0.1 --port 3005', recreate only that PM2 process, then rerun git uphra"
  exit 6
fi

# ─── 1. Code: pull only if there is something new ───────────────────────────
# ecosystem.config.cjs is intentionally VPS-local and backend/build/ is a
# generated Python artifact. They may exist before the .gitignore rules are
# pulled, so those known untracked paths must not block the bootstrap pull.
# Tracked modifications and every other untracked path still stop the deploy.
WORKTREE_CHANGES="$(git status --porcelain --untracked-files=all | grep -v -E '^\?\? (ecosystem\.config\.cjs|backend/build/)' || true)"
if [[ -n "$WORKTREE_CHANGES" ]]; then
  warn "worktree has local changes — refusing to pull automatically"
  printf '%s\n' "$WORKTREE_CHANGES"
  exit 1
fi

NEED_BUILD=0; NEED_NODE_DEPS=0; NEED_PY_DEPS=0; MIGRATION_CHANGED=0; PULLED=0
FRONTEND_CHANGED=0; BACKEND_CHANGED=0
MIG_HASH_BEFORE_PULL=$(migrations_hash)

FETCH_OK=1
if ! git fetch origin "$BRANCH" --quiet; then
  FETCH_OK=0
  if [[ $FORCE -eq 1 ]]; then
    warn "git fetch failed — continuing with local code because --force was given"
  else
    warn "git fetch failed — cannot prove the VPS is up to date; aborting"
    exit 1
  fi
fi

if [[ $FETCH_OK -eq 1 ]] && ! git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
  warn "remote branch origin/$BRANCH not found"
  exit 1
fi

CURRENT_BRANCH="$(git symbolic-ref --quiet --short HEAD 2>/dev/null || true)"
if [[ "$CURRENT_BRANCH" != "$BRANCH" ]]; then
  if ! git checkout "$BRANCH"; then
    warn "cannot checkout branch $BRANCH"
    exit 1
  fi
fi

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH" 2>/dev/null || echo "$LOCAL")

if [[ "$LOCAL" != "$REMOTE" ]]; then
  AHEAD=$(git rev-list --count "origin/$BRANCH..HEAD" 2>/dev/null || echo 0)
  if [[ "$AHEAD" -gt 0 ]]; then
    warn "local has $AHEAD unpushed commit(s) — refusing fast-forward deploy"
    exit 1
  fi
  if git pull --ff-only origin "$BRANCH"; then
    PULLED=1
    ok "code updated: $(git rev-parse --short HEAD)"
  else
    warn "fast-forward failed — resolve manually before deploying"
    exit 1
  fi
else
  skip "code already up to date ($(git rev-parse --short HEAD))"
fi

if [[ -n "$PREV_BRANCH" && "$PREV_BRANCH" != "$BRANCH" ]]; then
  log "deploy branch changed: $PREV_BRANCH -> $BRANCH"
  NEED_BUILD=1
  BACKEND_CHANGED=1
fi

# ─── 2a. Node dependencies: install only when frontend lock inputs changed ──
LOCK_HASH=$(frontend_deps_hash)
if [[ $FORCE -eq 1 || "$LOCK_HASH" != "$PREV_LOCK" ]]; then
  if [[ $FORCE -eq 0 && -z "$PREV_LOCK" ]] && frontend_node_modules_usable; then
    skip "frontend Node dependencies already installed — accepting bootstrap baseline"
  else
    log "installing frontend Node dependencies (npm ci)…"
    if (cd frontend && npm ci --no-audit --no-fund); then
      ok "frontend Node dependencies ready"
      NEED_NODE_DEPS=1
      NEED_BUILD=1
    else
      warn "npm ci FAILED — marker not updated"
      exit 1
    fi
  fi
else
  skip "frontend Node dependencies unchanged"
fi

# ─── 2b. Python dependencies: install only when backend/pyproject changed ───
PY_DEPS_HASH=$(python_deps_hash)
if [[ $FORCE -eq 1 || "$PY_DEPS_HASH" != "$PREV_PY_DEPS" ]]; then
  log "installing backend Python dependencies from pyproject.toml…"
  if [[ -x backend/.venv/bin/python ]]; then
    if (cd backend && .venv/bin/python -m pip install .); then
      ok "backend Python dependencies ready"
      NEED_PY_DEPS=1
    else
      warn "backend pip install FAILED — marker not updated"
      exit 1
    fi
  else
    warn "backend/.venv/bin/python not found — cannot install backend dependencies"
    exit 1
  fi
else
  skip "backend Python dependencies unchanged"
fi

# ─── 3. Supabase migrations: detect only, never auto-apply from VPS ────────
MIG_HASH=$(migrations_hash)
if [[ "$MIG_HASH" != "$MIG_HASH_BEFORE_PULL" ]]; then
  MIGRATION_CHANGED=1
fi
if [[ -n "$MARK_PREV_MIG" && "$MIG_HASH" != "$MARK_PREV_MIG" ]]; then
  MIGRATION_CHANGED=1
fi
if [[ $MIGRATION_CHANGED -eq 1 ]]; then
  if [[ $MIGRATIONS_VERIFIED -eq 1 ]]; then
    warn "Supabase migrations changed and operator marked them verified; continuing"
    NEED_BUILD=1
    BACKEND_CHANGED=1
  else
    warn "supabase/migrations changed — this script does not apply Supabase migrations"
    warn "apply/verify migrations through the approved Supabase process, then rerun with --migrations-verified"
    exit 2
  fi
else
  skip "Supabase migrations unchanged"
fi

# ─── 4. Build: only when frontend source/config/deps changed ────────────────
SRC_HASH=$(frontend_src_hash)
if [[ $FORCE -eq 1 || "$SRC_HASH" != "$PREV_SRC" ]]; then
  NEED_BUILD=1
  FRONTEND_CHANGED=1
fi

if [[ $NEED_BUILD -eq 1 ]]; then
  log "building Next.js…"
  if (cd frontend && npm run build); then
    ok "Next.js build completed"
  else
    warn "Next.js build FAILED — keeping previous frontend runtime"
    exit 1
  fi
else
  skip "frontend build unchanged — reusing existing .next"
  if frontend_build_missing; then
    warn "frontend build output missing — rebuilding"
    if (cd frontend && npm run build); then
      NEED_BUILD=1
      FRONTEND_CHANGED=1
      ok "Next.js build completed"
    else
      warn "Next.js build FAILED — keeping previous frontend runtime"
      exit 1
    fi
  fi
fi

# ─── 5. pm2 restarts — only what actually changed ───────────────────────────
PY_HASH=$(backend_src_hash)
if [[ $FORCE -eq 1 || "$PY_HASH" != "$PREV_PY_HASH" || $NEED_PY_DEPS -eq 1 ]]; then
  BACKEND_CHANGED=1
fi

FRONTEND_RESTART_OK=1; BACKEND_RESTART_OK=1
BACKEND_RESTARTED=0; FRONTEND_RESTARTED=0

if [[ $BACKEND_CHANGED -eq 1 || $PENDING_BACKEND_RESTART -eq 1 ]]; then
  [[ $PENDING_BACKEND_RESTART -eq 1 && $BACKEND_CHANGED -eq 0 ]] && warn "retrying pending $PM2_BACKEND restart from a previous run"
  if pm2_restart "$PM2_BACKEND"; then
    BACKEND_RESTARTED=1
    wait_for_url "backend" "$BACKEND_HEALTH_URL" 30 || BACKEND_RESTART_OK=0
  else
    BACKEND_RESTART_OK=0
  fi
else
  skip "$PM2_BACKEND restart not needed (no backend change)"
fi

if [[ $NEED_BUILD -eq 1 || $PENDING_FRONTEND_RESTART -eq 1 || $FORCE -eq 1 ]]; then
  [[ $PENDING_FRONTEND_RESTART -eq 1 && $NEED_BUILD -eq 0 ]] && warn "retrying pending $PM2_FRONTEND restart from a previous run"
  if pm2_restart "$PM2_FRONTEND"; then
    FRONTEND_RESTARTED=1
    wait_for_url "frontend" "$FRONTEND_URL" 30 || FRONTEND_RESTART_OK=0
  else
    FRONTEND_RESTART_OK=0
  fi
else
  skip "$PM2_FRONTEND restart not needed (no rebuild/assets change)"
fi

# ─── 6. Smoke tests after any restart ───────────────────────────────────────
SMOKE_OK=1
if [[ $BACKEND_RESTARTED -eq 1 || $FRONTEND_RESTARTED -eq 1 || $FORCE -eq 1 ]]; then
  log "running smoke tests…"
  curl -fsS --max-time 5 "$BACKEND_HEALTH_URL" >/dev/null || { warn "backend health smoke failed"; SMOKE_OK=0; }
  curl -fsS --max-time 5 "$FRONTEND_URL/" >/dev/null || { warn "frontend root smoke failed"; SMOKE_OK=0; }
  curl -fsS --max-time 5 -I "$FRONTEND_URL/vinuni-logo.png" >/dev/null || { warn "logo smoke failed"; SMOKE_OK=0; }
  curl -fsS --max-time 5 "$FRONTEND_URL/v1/auth/bootstrap-status" >/dev/null || { warn "frontend API proxy smoke failed"; SMOKE_OK=0; }
  [[ $SMOKE_OK -eq 1 ]] && ok "smoke tests passed"
fi

# Persist pending-restart flags when a required restart did not succeed.
if [[ $FRONTEND_RESTART_OK -eq 1 && $BACKEND_RESTART_OK -eq 1 ]]; then
  rm -f "$PENDING_FILE"
else
  cat > "$PENDING_FILE" <<EOF
PENDING_FRONTEND_RESTART=$(( 1 - FRONTEND_RESTART_OK ))
PENDING_BACKEND_RESTART=$(( 1 - BACKEND_RESTART_OK ))
EOF
  warn "some pm2 restarts did not succeed — they will retry on the next 'git uphra'"
fi

# ─── Persist state ──────────────────────────────────────────────────────────
cat > "$MARK" <<EOF
PREV_COMMIT=$(git rev-parse --short HEAD)
PREV_BRANCH=$BRANCH
PREV_LOCK=$LOCK_HASH
PREV_MIG=$MIG_HASH
PREV_SRC=$SRC_HASH
PREV_PY_DEPS=$PY_DEPS_HASH
PREV_PY_HASH=$PY_HASH
LAST_RUN=$(date -Iseconds)
EOF

DUR=$(( $(date +%s) - STARTED ))
log "done in ${DUR}s — (code:$PULLED nodeDeps:$NEED_NODE_DEPS pyDeps:$NEED_PY_DEPS migrations:$MIGRATION_CHANGED build:$NEED_BUILD backendRestart:$BACKEND_RESTARTED frontendRestart:$FRONTEND_RESTARTED)"

[[ $SMOKE_OK -eq 1 ]] || exit 4
[[ $FRONTEND_RESTART_OK -eq 1 && $BACKEND_RESTART_OK -eq 1 ]] || exit 5
