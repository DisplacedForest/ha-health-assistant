#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
src="$repo_root/custom_components/health_assistant"
config_dir="${HA_CONFIG_DIR:-$HOME/ha}"
dest="$config_dir/custom_components/health_assistant_dev"

if [ ! -d "$src" ]; then
  echo "missing $src" >&2
  exit 1
fi
if [ ! -d "$config_dir" ]; then
  echo "missing HA config dir $config_dir" >&2
  exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/health_assistant_dev"
cp -R "$src/." "$tmp/health_assistant_dev/"

find "$tmp/health_assistant_dev" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$tmp/health_assistant_dev" -type f \( -name '*.pyc' -o -name '.DS_Store' \) -delete

find "$tmp/health_assistant_dev" -type f \( -name '*.py' -o -name '*.json' -o -name '*.yaml' \) -print0 |
  xargs -0 perl -pi -e 's/health_assistant(?!\.sparse_record\b)/health_assistant_dev/g; s/Health Assistant(?! \(Dev\))/Health Assistant (Dev)/g'

mkdir -p "$config_dir/custom_components"
rm -rf "$dest"
mv "$tmp/health_assistant_dev" "$dest"

echo "installed $dest"
