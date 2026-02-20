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

SDK_PKG="reversinglabs-sdk-py3"
SDK_UPGRADE_MARKER="${VENV_DIR}/.sdk_last_upgrade"
SDK_UPGRADE_INTERVAL_DAYS="${RL_UPGRADE_INTERVAL:-7}"

if [ ! -d "${VENV_DIR}" ]; then
    echo "[venv] Creating virtual environment..."
    python3 -m venv "${VENV_DIR}"
    echo "[venv] Installing ${SDK_PKG}..."
    "${VENV_DIR}/bin/pip" install --quiet "${SDK_PKG}"
    touch "${SDK_UPGRADE_MARKER}"
    echo "[venv] Ready."
elif ! "${VENV_DIR}/bin/python3" -c "import ReversingLabs.SDK.a1000" 2>/dev/null; then
    echo "[venv] SDK missing or broken, reinstalling..."
    "${VENV_DIR}/bin/pip" install --quiet "${SDK_PKG}"
    touch "${SDK_UPGRADE_MARKER}"
    echo "[venv] Ready."
else
    # Check if SDK upgrade is due
    _needs_upgrade=false
    if [ ! -f "${SDK_UPGRADE_MARKER}" ]; then
        _needs_upgrade=true
    elif [ "$(find "${SDK_UPGRADE_MARKER}" -mtime "+${SDK_UPGRADE_INTERVAL_DAYS}" 2>/dev/null)" ]; then
        _needs_upgrade=true
    fi
    if [ "${_needs_upgrade}" = true ]; then
        echo "[venv] Checking for SDK updates..."
        if "${VENV_DIR}/bin/pip" install --quiet --upgrade "${SDK_PKG}"; then
            echo "[venv] SDK is up to date."
        else
            echo "[venv] Warning: SDK upgrade check failed, continuing with current version."
        fi
        touch "${SDK_UPGRADE_MARKER}"
    fi
fi

exec "${VENV_DIR}/bin/python3" "${SCRIPT_DIR}/rl_upload.py" "$@"
