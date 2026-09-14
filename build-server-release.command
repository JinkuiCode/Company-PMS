#!/bin/zsh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="$ROOT_DIR/release"

usage() {
  printf '用法：%s [--output-dir 目录]\n' "$(basename "$0")"
}

while (( $# > 0 )); do
  case "$1" in
    --output-dir)
      if (( $# < 2 )); then
        usage >&2
        exit 2
      fi
      OUTPUT_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf '未知参数：%s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

cd "$ROOT_DIR"

for command_name in git tar zip shasum npm; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf '缺少构建命令：%s\n' "$command_name" >&2
    exit 1
  fi
done

DEPLOYMENT_PATHS=(
  backend/app
  backend/main.py
  backend/requirements.txt
  backend/scripts
  backend/vendor
  backend/.env.kingdee.example
  frontend
  build-server-release.command
  docs/PMS服务器发布与回退说明.md
)

if [[ -n "$(git status --porcelain -- "${DEPLOYMENT_PATHS[@]}")" ]]; then
  printf '部署相关源码存在未提交改动，请先完成审查和提交。\n' >&2
  exit 1
fi

COMMIT="$(git rev-parse HEAD)"
SHORT_COMMIT="$(git rev-parse --short=8 HEAD)"
BUILD_DATE="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
RELEASE_DATE="$(date '+%Y%m%d')"
RELEASE_NAME="pms-server-${SHORT_COMMIT}-${RELEASE_DATE}"

STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/pms-release.XXXXXX")"
trap 'rm -rf "$STAGING_DIR"' EXIT
BUILD_SOURCE="$STAGING_DIR/source"
mkdir -p "$BUILD_SOURCE"
# Build only the pinned commit, never the developer's existing dist directory.
git archive --format=tar "$COMMIT" frontend | tar -xf - -C "$BUILD_SOURCE"
if [[ ! -d "$ROOT_DIR/frontend/node_modules" ]]; then
  printf '缺少前端依赖，请先按 lockfile 安装依赖。\n' >&2
  exit 1
fi
ln -s "$ROOT_DIR/frontend/node_modules" "$BUILD_SOURCE/frontend/node_modules"
printf '从提交 %s 构建前端生产文件...\n' "$SHORT_COMMIT"
(cd "$BUILD_SOURCE/frontend" && npm run build)
if [[ ! -f "$BUILD_SOURCE/frontend/dist/index.html" ]]; then
  printf '前端构建未生成 index.html。\n' >&2
  exit 1
fi

BUNDLE_DIR="$STAGING_DIR/$RELEASE_NAME"
mkdir -p "$BUNDLE_DIR/frontend"

git archive --format=tar "$COMMIT" \
  backend/app \
  backend/main.py \
  backend/requirements.txt \
  backend/scripts \
  backend/vendor \
  backend/.env.kingdee.example \
  | tar -xf - -C "$BUNDLE_DIR"
cp -R "$BUILD_SOURCE/frontend/dist" "$BUNDLE_DIR/frontend/dist"
git show "$COMMIT:docs/PMS服务器发布与回退说明.md" > "$BUNDLE_DIR/SERVER-DEPLOYMENT.md"

{
  printf 'PMS server release candidate\n'
  printf 'Git commit: %s\n' "$COMMIT"
  printf 'Build time (UTC): %s\n' "$BUILD_DATE"
  printf 'Frontend: rebuilt from Git commit %s\n' "$COMMIT"
  printf 'Backend: source and pinned requirements included\n'
  printf 'ERP write mode: preserve the approved server configuration; pause writes only for the agreed maintenance window\n'
  printf 'Protected configuration: excluded\n'
  printf 'Database and runtime data: excluded\n'
  printf 'Server deployment: pending live directory and service verification\n'
} > "$BUNDLE_DIR/RELEASE-MANIFEST.txt"

(
  cd "$BUNDLE_DIR"
  find backend frontend RELEASE-MANIFEST.txt SERVER-DEPLOYMENT.md -type f -print \
    | LC_ALL=C sort \
    | while IFS= read -r file_path; do
        shasum -a 256 "$file_path"
      done > SHA256SUMS
)

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
ARCHIVE_PATH="$OUTPUT_DIR/$RELEASE_NAME.zip"
CHECKSUM_PATH="$ARCHIVE_PATH.sha256"
rm -f "$ARCHIVE_PATH" "$CHECKSUM_PATH"
(
  cd "$STAGING_DIR"
  zip -qr "$ARCHIVE_PATH" "$RELEASE_NAME"
)
shasum -a 256 "$ARCHIVE_PATH" > "$CHECKSUM_PATH"

printf '发布包：%s\n' "$ARCHIVE_PATH"
printf '校验文件：%s\n' "$CHECKSUM_PATH"
