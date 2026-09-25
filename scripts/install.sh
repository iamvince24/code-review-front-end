#!/bin/sh
set -eu

skill_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
name=code-review-front-end
failed=0

install_one() {
  root=$1
  dest=$root/$name
  source=$(CDPATH= cd -- "$skill_dir" && pwd -P)
  mkdir -p "$root"
  if [ -e "$dest" ] || [ -L "$dest" ]; then
    current=$(CDPATH= cd -- "$dest" && pwd -P)
    if [ "$current" = "$source" ]; then
      printf 'ok %s\n' "$dest"
      return
    fi
    if [ -L "$dest" ]; then
      rm -f "$dest"
    else
      printf 'skip %s (exists, not a symlink)\n' "$dest" >&2
      failed=1
      return
    fi
  fi
  ln -s "$skill_dir" "$dest"
  printf 'linked %s\n' "$dest"
}

install_one "$HOME/.cursor/skills"
install_one "$HOME/.claude/skills"
install_one "$HOME/.agents/skills"

exit "$failed"
