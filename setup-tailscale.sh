#!/bin/bash

set -e

echo "=== macOS Tailscale + Trayscale Setup Script ==="
echo ""

# Check for and install Xcode Command Line Tools
echo "[1/6] Checking Xcode Command Line Tools..."
if xcode-select -p >/dev/null; then
    echo "  ✓ Xcode Command Line Tools already installed"
else
    echo "  Installing Xcode Command Line Tools..."
    xcode-select --install
    echo "  Waiting for Xcode Command Line Tools installation to complete..."
    echo "  Please complete the installation dialog, then press Enter to continue."
    read -r
fi

# Install Tailscale/Trayscale from Homebrew
echo ""
echo "[2/6] Installing Tailscale/Trayscale from Homebrew..."
if ! command -v brew >/dev/null; then
    echo "  Error: Homebrew is not installed. Please install it first:"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    exit 1
fi

set +e

if brew tap | grep orchard-robotics/macos-tailscale-installer >/dev/null; then
    echo "  ✓ Brew Tap already installed, reinstalling"
    brew untap --force Orchard-Robotics/macos-tailscale-installer
    brew tap Orchard-Robotics/macos-tailscale-installer
else
    brew tap Orchard-Robotics/macos-tailscale-installer
    echo "  ✓ Brew Tap (orchard-robotics/macos-tailscale-installer) installed"
fi

if brew list --formula orchard-robotics/macos-tailscale-installer/trayscale >/dev/null; then
    echo "  ✓ Trayscale already installed, reinstalling"
    brew cleanup --prune=0 -s orchard-robotics/macos-tailscale-installer/trayscale
    brew reinstall orchard-robotics/macos-tailscale-installer/trayscale
else
    brew install --formula orchard-robotics/macos-tailscale-installer/trayscale
    echo "  ✓ Trayscale installed"
fi

if brew list --formula orchard-robotics/macos-tailscale-installer/tailscale >/dev/null; then
    echo "  ✓ Tailscale already installed, reinstalling"
    brew cleanup --prune=0 -s orchard-robotics/macos-tailscale-installer/tailscale
    brew reinstall orchard-robotics/macos-tailscale-installer/tailscale
else
    brew install --formula orchard-robotics/macos-tailscale-installer/tailscale
    echo "  ✓ Tailscale installed"
fi

set -e

if brew list --formula orchard-robotics/macos-tailscale-installer/tailscale orchard-robotics/macos-tailscale-installer/trayscale >/dev/null; then
    echo "  ✓ Tailscale and Trayscale Successfully Installed"
else
    echo "  Error: Unable to install tailscale and trayscale! Try running the script again."
fi

# Start the Tailscale service
echo ""
echo "[3/6] Starting Tailscale service..."
sudo pkill -f tailscaled
sudo brew services start tailscale
echo "  ✓ Tailscale service started"

# Run tailscale up
echo ""
echo "[4/6] Connecting to Tailscale..."
sudo tailscale up
echo "  ✓ Tailscale connected"

# Set current user as operator and accept routes
echo ""
echo "[5/6] Configuring Tailscale settings..."
sudo tailscale set --operator="$USER"
echo "  ✓ $USER set as operator"
sudo tailscale set --accept-routes=true
echo "  ✓ Accept routes enabled"

# Configure DNS resolver for MagicDNS
echo ""
echo "[6/6] Configuring DNS resolver for MagicDNS..."
sudo mkdir -p /etc/resolver
DNS_DOMAIN=$(tailscale dns status | grep "Search Domains:" -A 1 | tail -n 1 | sed 's/  - //g')
echo "  Found DNS domain: $DNS_DOMAIN"

sudo tee /etc/resolver/search.tailscale > /dev/null << EOF
# Added by tailscaled
search $DNS_DOMAIN
EOF
echo "  ✓ Created /etc/resolver/search.tailscale"

sudo tee /etc/resolver/magicdns.tailscale > /dev/null << EOF
domain $DNS_DOMAIN
nameserver 100.100.100.100
EOF
echo "  ✓ Created /etc/resolver/magicdns.tailscale"

sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
echo "  ✓ DNS cache flushed"

# Create Trayscale.app in Applications
echo ""
echo "Installing Trayscale.app..."

# Create app bundle structure
APP_PATH="/Applications/Trayscale.app"
INSTALLED_BIN_PATH=$(brew list orchard-robotics/macos-tailscale-installer/trayscale | \
                     grep Trayscale.app/Contents/MacOS/trayscale | \
                     xargs -0 dirname | xargs -0 dirname | xargs -0 dirname)
sudo rm -rf "$APP_PATH"
sudo cp -r "$INSTALLED_BIN_PATH" "$APP_PATH"
sudo chown -R "$USER" "$APP_PATH"
sudo chmod -R +rwx "$APP_PATH"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "You can now:"
echo "  - Launch Trayscale from /Applications/Trayscale.app"
echo "  - Use 'tailscale' command directly (as operator)"
echo ""
