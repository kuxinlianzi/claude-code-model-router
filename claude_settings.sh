#!/bin/bash
# Switch .claude/settings.json between backup profiles

CLAUDE_DIR="$HOME/.claude"
SETTINGS="$CLAUDE_DIR/settings.json"

case "$1" in
    bklocal)
        src="$CLAUDE_DIR/settings.json.bklocal.json"
        ;;
    bkgood)
        src="$CLAUDE_DIR/settings.json.bkgood.json"
        ;;
    *)
        echo "Usage: $0 {bklocal|bkgood}"
        exit 1
        ;;
esac

if [ ! -f "$src" ]; then
    echo "Error: $src not found"
    exit 1
fi

cp "$src" "$SETTINGS"
echo "Switched to $1: $(basename "$src") -> settings.json"
