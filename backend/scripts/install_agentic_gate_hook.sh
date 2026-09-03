#!/bin/bash
# Install the agentic code gate as a pre-commit hook
# Run this ONCE: bash backend/scripts/install_agentic_gate_hook.sh

HOOK_DIR="$(git rev-parse --show-toplevel)/.git/hooks"
HOOK_FILE="$HOOK_DIR/pre-commit"

mkdir -p "$HOOK_DIR"

cat > "$HOOK_FILE" <<'EOF'
#!/bin/bash
# Agentic Code Review Gate - Runs on every commit
# Learns from violations and improves detection patterns over time

cd "$(git rev-parse --show-toplevel)"
python3 backend/scripts/agentic_code_gate.py
exit $?
EOF

chmod +x "$HOOK_FILE"
echo "✅ Agentic code gate installed as pre-commit hook"
echo "   It will run on every commit and learn from violations"
