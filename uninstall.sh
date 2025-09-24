#!/bin/bash

# This script uninstalls the 'alpm' binary by removing it from /usr/bin/alpm.
# It must be run by a normal user, and it will use 'sudo' to request
# administrator privileges for the removal command.

# --- Safety Checks ---

# 1. Ensure the script is NOT run as root.
if [ "$(id -u)" -eq 0 ]; then
   echo "Error: This script must not be run as root." >&2
   echo "Please run it as a normal user. It will ask for your password via sudo." >&2
   exit 1
fi

# 2. Check if the file exists before trying to remove it.
if [ ! -f "/usr/bin/alpm" ]; then
    echo "Info: The binary '/usr/bin/alpm' is not installed. Nothing to do."
    exit 0
fi

# --- Uninstallation ---

echo "This script needs to remove a file from a system directory."
echo "You will be prompted for your password to proceed."
echo ""

# Use sudo to remove the binary. This will trigger the password prompt.
echo "==> Removing /usr/bin/alpm..."
sudo rm /usr/bin/alpm

# Verify that the file was actually removed.
if [ ! -f "/usr/bin/alpm" ]; then
    echo ""
    echo "Uninstallation successful!"
    echo "'alpm' has been removed from your system."
else
    echo ""
    echo "Error: Uninstallation failed for an unknown reason." >&2
    echo "Please check permissions for /usr/bin/alpm" >&2
    exit 1
fi

exit 0
