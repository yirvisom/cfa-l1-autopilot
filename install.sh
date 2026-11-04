#!/usr/bin/env bash
# CFA Level I autopilot - installer for Linux, macOS and WSL/Git Bash.
#
# What it does:
#   1. checks Python 3.9+
#   2. creates profile.json from profile.example.json if you have not edited one
#   3. creates ~/.config/cfa/env for the optional model key
#   4. puts a `cfa` launcher in ~/.local/bin
#   5. adds that folder to your shell PATH once
#   6. installs four systemd user timers when systemd is available
#
# Usage:
#   bash install.sh              # normal install, timers if systemd exists
#   bash install.sh --no-timers  # skip the timers
#   bash install.sh --no-shell   # do not edit your shell rc file
set -euo pipefail

if [ -n "${BASH_SOURCE:-}" ]; then
  SRC="${BASH_SOURCE[0]}"
else
  SRC="$0"
fi
DIR="$(cd "$(dirname "$SRC")" && pwd)"
ENVF="$HOME/.config/cfa/env"
BIN="$HOME/.local/bin"
WITH_TIMERS=1
WITH_SHELL=1

for arg in "$@"; do
  case "$arg" in
    --no-timers) WITH_TIMERS=0 ;;
    --no-shell)  WITH_SHELL=0 ;;
    -h|--help)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '%s\n' "$*"; }
fail() { printf 'error: %s\n' "$*" >&2; exit 1; }

# ---------- python ----------
PY=""
for candidate in "${PYTHON:-}" python3 python; do
  [ -n "$candidate" ] || continue
  if command -v "$candidate" >/dev/null 2>&1 \
     && "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
[ -n "$PY" ] || fail "Python 3.9+ is required. Install python3 and run this again."

chmod +x "$DIR/cfa.py" 2>/dev/null || true
mkdir -p "$DIR/plan/weeks" "$DIR/plan/reviews" "$(dirname "$ENVF")" "$BIN"

# ---------- profile ----------
if [ ! -f "$DIR/profile.json" ]; then
  cp "$DIR/profile.example.json" "$DIR/profile.json"
  say "Created profile.json from profile.example.json. Edit it with your dates."
else
  say "Keeping the existing profile.json."
fi

# ---------- key file ----------
if [ ! -f "$ENVF" ]; then
  cat > "$ENVF" <<'EOF'
# Optional: only used by `cfa master` and `cfa week`.
# Get a key from your model provider. Any OpenAI-compatible endpoint works.
DEEPSEEK_API_KEY=paste-your-key-here
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# DEEPSEEK_MODEL=deepseek-flash

# Optional phone push through ntfy (use a long random topic):
# NTFY_TOPIC=cfa-pick-a-long-random-string
EOF
  chmod 600 "$ENVF" 2>/dev/null || true
  say "Created $ENVF. Paste your key there if you want model-written weeks."
else
  say "Keeping the existing $ENVF."
fi

# ---------- launcher ----------
cat > "$BIN/cfa" <<EOF
#!/usr/bin/env sh
exec "$PY" "$DIR/cfa.py" "\$@"
EOF
chmod +x "$BIN/cfa"
say "Launcher installed: $BIN/cfa"

# ---------- PATH ----------
if [ "$WITH_SHELL" -eq 1 ]; then
  case "${SHELL:-}" in
    *zsh)  RC="$HOME/.zshrc" ;;
    *bash) RC="$HOME/.bashrc" ;;
    *)     RC="$HOME/.profile" ;;
  esac
  touch "$RC"
  if ! grep -q 'cfa-l1-autopilot' "$RC"; then
    {
      printf '\n# cfa-l1-autopilot\n'
      printf 'export PATH="%s:$PATH"\n' "$BIN"
    } >> "$RC"
    say "Added $BIN to PATH in $RC. Open a new terminal (or source it)."
  else
    say "$BIN is already referenced in $RC."
  fi
fi

# ---------- timers ----------
install_timers() {
  command -v systemctl >/dev/null 2>&1 || {
    say "No systemd here. Skipping timers; run 'cfa today' by hand or use cron."
    return
  }
  systemctl --user show-environment >/dev/null 2>&1 || {
    say "No systemd user session. Skipping timers; run 'cfa today' by hand or use cron."
    return
  }

  UNITS="$HOME/.config/systemd/user"
  mkdir -p "$UNITS"

  make_unit() { # name, description, OnCalendar, command tail
    cat > "$UNITS/cfa-$1.service" <<EOF
[Unit]
Description=$2

[Service]
Type=oneshot
EnvironmentFile=$ENVF
Environment=CFA_HOME=$DIR
WorkingDirectory=$DIR
ExecStart="$PY" "$DIR/cfa.py" $4
TimeoutStartSec=1800
EOF
    cat > "$UNITS/cfa-$1.timer" <<EOF
[Unit]
Description=$2 (timer)

[Timer]
OnCalendar=$3
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF
  }

  make_unit daily  "CFA daily brief"            "*-*-* 07:30:00"   "today --notify"
  make_unit nudge  "CFA evening check-in"       "*-*-* 21:30:00"   "nudge"
  make_unit final  "CFA end-of-day close"       "*-*-* 22:30:00"   "nudge --final"

  # The weekly unit runs two commands. A tiny wrapper avoids quoting games
  # in the unit file and works if the checkout path contains spaces.
  cat > "$UNITS/cfa-weekly.sh" <<EOF
#!/bin/sh
"$PY" "$DIR/cfa.py" review
"$PY" "$DIR/cfa.py" week --next
EOF
  chmod +x "$UNITS/cfa-weekly.sh"

  cat > "$UNITS/cfa-weekly.service" <<EOF
[Unit]
Description=CFA weekly review and plan

[Service]
Type=oneshot
EnvironmentFile=$ENVF
Environment=CFA_HOME=$DIR
WorkingDirectory=$DIR
ExecStart="$UNITS/cfa-weekly.sh"
TimeoutStartSec=1800
EOF

  cat > "$UNITS/cfa-weekly.timer" <<EOF
[Unit]
Description=CFA weekly review and plan (timer)

[Timer]
OnCalendar=Sun *-*-* 19:00:00
Persistent=true
AccuracySec=1min

[Install]
WantedBy=timers.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable --now cfa-daily.timer cfa-nudge.timer cfa-final.timer cfa-weekly.timer
  loginctl enable-linger "$USER" 2>/dev/null \
    || say "Could not enable linger (sudo loginctl enable-linger $USER). Timers still run while you are logged in."

  say "Timers installed:"
  systemctl --user list-timers 'cfa-*' --no-pager || true
}

if [ "$WITH_TIMERS" -eq 1 ]; then
  install_timers
else
  say "Timers skipped (--no-timers)."
fi

# ---------- done ----------
say ""
say "CFA autopilot installed in: $DIR"
say ""
say "Next:"
say "  1. Edit $ENVF if you want model-written weeks (optional)."
say "  2. cfa doctor"
say "  3. cfa today"
say ""
say "The plan is a template. Edit profile.json and plan/curriculum.json for your own dates."
