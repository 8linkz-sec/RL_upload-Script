#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONF="${SCRIPT_DIR}/rl_upload.conf"
VENV_DIR="${SCRIPT_DIR}/.venv"

# Load config (sets RL_HOST, RL_TOKEN, RL_PATH, etc.)
if [ -f "${CONF}" ]; then
    # shellcheck source=/dev/null
    . "${CONF}"
elif [ -z "${RL_HOST:-}" ]; then
    echo "ERROR: ${CONF} not found."
    echo "       Run: mv rl_upload.conf.example rl_upload.conf && edit rl_upload.conf"
    exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
    echo "[venv] Creating virtual environment..."
    python3 -m venv "${VENV_DIR}"
    echo "[venv] Installing reversinglabs-sdk-py3..."
    "${VENV_DIR}/bin/pip" install --quiet reversinglabs-sdk-py3
    echo "[venv] Ready."
elif ! "${VENV_DIR}/bin/python3" -c "import ReversingLabs.SDK.a1000" 2>/dev/null; then
    echo "[venv] SDK missing or broken, reinstalling..."
    "${VENV_DIR}/bin/pip" install --quiet reversinglabs-sdk-py3
    echo "[venv] Ready."
fi

exec "${VENV_DIR}/bin/python3" "${SCRIPT_DIR}/rl_upload.py" "$@"
