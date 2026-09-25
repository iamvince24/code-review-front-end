#!/bin/sh
set -eu

skill_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
target=${CURSOR_AGENT_DIR:-"$HOME/.cursor/agents"}
mkdir -p "$target"

for old in a11y architecture codebase naming security spec state types verifier; do
  rm -f "$target/fe-review-$old.md"
done

for name in correctness risk maintainability; do
  destination="$target/fe-review-$name.md"
  rm -f "$destination"
  ln -s "$skill_dir/agents/fe-review-$name.md" "$destination"
done

printf 'Installed frontend review agents in %s\n' "$target"
