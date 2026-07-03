#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GIT_BIN="/usr/bin/git"
if [[ ! -x "$GIT_BIN" ]]; then
  GIT_BIN="$(command -v git)"
fi

REMOTE="${1:-origin}"
BRANCH="$("$GIT_BIN" branch --show-current)"

if [[ -z "$BRANCH" ]]; then
  echo "未检测到当前 Git 分支，请先切换到要推送的分支。"
  exit 1
fi

REMOTE_URL="$("$GIT_BIN" remote get-url "$REMOTE")"
if [[ "$REMOTE_URL" != https://github.com/* ]]; then
  echo "当前脚本用于 GitHub HTTPS 远端。当前 $REMOTE 远端为：$REMOTE_URL"
  echo "如需 SSH 推送，请先配置 SSH key。"
  exit 1
fi

echo "仓库：$SCRIPT_DIR"
echo "远端：$REMOTE_URL"
echo "分支：$BRANCH"
echo

credential_payload() {
  local username="${1:-}"
  printf "protocol=https\nhost=github.com\n"
  if [[ -n "$username" ]]; then
    printf "username=%s\n" "$username"
  fi
  printf "\n"
}

clear_github_credential() {
  local username="${1:-}"
  credential_payload "$username" | "$GIT_BIN" credential reject >/dev/null 2>&1 || true
}

push_branch() {
  GIT_TERMINAL_PROMPT=0 "$GIT_BIN" push -u "$REMOTE" "$BRANCH"
}

echo "先尝试使用现有 GitHub 凭据推送..."
if push_branch; then
  echo
  echo "推送成功。之后可继续使用："
  echo "  git push"
  exit 0
fi

echo
echo "现有凭据不可用，需要录入 GitHub 凭据。"
clear_github_credential
echo "建议使用 GitHub Personal Access Token，不要使用账号密码。"
echo "Classic token 需要 repo 权限；Fine-grained token 需要本仓库 Contents 读写权限。"
echo

read -r -p "GitHub 用户名: " GITHUB_USERNAME
if [[ -z "$GITHUB_USERNAME" ]]; then
  echo "用户名不能为空。"
  exit 1
fi

read -r -s -p "GitHub Token（输入时不会显示）: " GITHUB_TOKEN
echo
if [[ -z "$GITHUB_TOKEN" ]]; then
  echo "Token 不能为空。"
  exit 1
fi

echo
echo "清理旧 GitHub 凭据并写入 macOS Keychain..."
"$GIT_BIN" config --global credential.helper osxkeychain
clear_github_credential "$GITHUB_USERNAME"
printf "protocol=https\nhost=github.com\nusername=%s\npassword=%s\n\n" "$GITHUB_USERNAME" "$GITHUB_TOKEN" | "$GIT_BIN" credential approve
unset GITHUB_TOKEN

echo "再次推送..."
if ! push_branch; then
  clear_github_credential "$GITHUB_USERNAME"
  echo
  echo "推送仍然失败，已清理刚录入的无效凭据。"
  echo "请确认 Token 没有复制空格、没有过期，并具备 repo 权限或本仓库 Contents 读写权限。"
  exit 1
fi

echo
echo "推送成功。凭据已存入 macOS Keychain，以后在本机推送 GitHub HTTPS 仓库会自动复用。"
