#!/bin/zsh
set -eu
cd "$(dirname "$0")/../.."
printf 'PMS independent theme controls: http://127.0.0.1:5184\nNo backend connection; Ctrl+C stops this preview only.\n'
exec ./node_modules/.bin/vite --config prototypes/theme-controls/vite.config.mjs
