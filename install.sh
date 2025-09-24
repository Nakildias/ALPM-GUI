#!/bin/bash

# This script installs the 'alpm' binary and its dependencies.
# - It checks for and installs dependencies: 'tk' and 'wget'.
# - If './alpm' is not found locally, it downloads it from GitHub.
# - It must be run as a normal user and will use 'sudo' for admin tasks.

# --- Configuration ---
ALPM_BINARY_NAME="alpm"
ALPM_LOCAL_PATH="./${ALPM_BINARY_NAME}"
ALPM_INSTALL_PATH="/usr/bin/${ALPM_BINARY_NAME}"
ALPM_DOWNLOAD_URL="https://github.com/Nakildias/ALPM-GUI/releases/download/Release/alpm"

# --- Safety Checks ---

# 1. Ensure the script is NOT run as root.
if [ "$(id -u)" -eq 0 ]; then
   echo "Error: This script must not be run as root." >&2
   echo "Please run it as a normal user. It will ask for your password via sudo." >&2
   exit 1
fi

# --- Installation Process ---

echo "This script needs to perform administrative tasks to install software."
echo "You will be prompted for your password."
echo ""

# 1. Install dependencies (tk, wget) and update system.
# The 'sudo' command will trigger the password prompt.
echo "==> Updating system packages and installing dependencies (tk, wget)..."
# Using --noconfirm to prevent prompts during script execution for dependencies.
if ! sudo pacman -Syu --noconfirm tk wget; then
    echo "Error: Failed to install dependencies. Please check your pacman configuration." >&2
    exit 1
fi

# 2. Check for the alpm binary and download if it's missing.
echo ""
echo "==> Checking for the '${ALPM_BINARY_NAME}' binary..."
if [ ! -f "${ALPM_LOCAL_PATH}" ]; then
    echo "==> '${ALPM_LOCAL_PATH}' not found. Downloading from GitHub..."
    if ! wget -O "${ALPM_LOCAL_PATH}" "${ALPM_DOWNLOAD_URL}"; then
        echo "Error: Failed to download '${ALPM_BINARY_NAME}'. Please check your internet connection or the URL." >&2
        exit 1
    fi
    echo "==> Download complete."
else
    echo "==> Found '${ALPM_LOCAL_PATH}' in the current directory."
fi

# 3. Copy the binary to a system path and make it executable.
echo ""
echo "==> Installing '${ALPM_LOCAL_PATH}' to '${ALPM_INSTALL_PATH}'..."
# 'install -m 755' copies the file and sets its permissions in one step.
if ! sudo install -m 755 "${ALPM_LOCAL_PATH}" "${ALPM_INSTALL_PATH}"; then
    echo "Error: Failed to install the binary to ${ALPM_INSTALL_PATH}." >&2
    exit 1
fi

# 4. Clean up the downloaded/local binary.
echo "==> Cleaning up..."
rm "${ALPM_LOCAL_PATH}"

echo ""
echo "Installation successful!"
echo "'${ALPM_BINARY_NAME}' has been installed to ${ALPM_INSTALL_PATH}"

exit 0
