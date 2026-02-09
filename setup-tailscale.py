#!/usr/bin/env python3

import subprocess
import sys
import os
import time
import getpass
import shutil

TAP = "Orchard-Robotics/macos-tailscale-installer"
TAP_LOWER = TAP.lower()
TRAYSCALE_FORMULA = f"orchard-robotics/macos-tailscale-installer/trayscale"
TAILSCALE_FORMULA = f"orchard-robotics/macos-tailscale-installer/tailscale"


def run(cmd, check=True, sudo=False, capture=False, **kwargs):
    if sudo:
        cmd = ["sudo"] + cmd
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True if capture else None,
        check=check,
        **kwargs,
    )
    return result


def is_installed(formula):
    result = run(
        ["brew", "list", "--formula", formula],
        check=False,
        capture=True,
    )
    return result.returncode == 0


def verify_installed(formula):
    if not is_installed(formula):
        print(f"  Error: {formula} failed to install!")
        sys.exit(1)


def step_xcode():
    print("[1/6] Checking Xcode Command Line Tools...")
    result = run(["xcode-select", "-p"], check=False, capture=True)
    if result.returncode == 0:
        print("  ✓ Xcode Command Line Tools already installed")
    else:
        print("  Installing Xcode Command Line Tools...")
        run(["xcode-select", "--install"])
        print("  Please complete the installation dialog, then press Enter to continue.")
        input()


def step_brew_install():
    print()
    print("[2/6] Installing Tailscale/Trayscale from Homebrew...")

    if not shutil.which("brew"):
        print("  Error: Homebrew is not installed. Please install it first:")
        print('  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
        sys.exit(1)

    # Manage tap
    result = run(["brew", "tap"], capture=True)
    if TAP_LOWER in result.stdout:
        print("  ✓ Brew Tap already installed, reinstalling")
        run(["brew", "untap", "--force", TAP])
    run(["brew", "tap", TAP])
    print(f"  ✓ Brew Tap ({TAP_LOWER}) installed")

    # Install trayscale
    if is_installed(TRAYSCALE_FORMULA):
        print("  ✓ Trayscale already installed, reinstalling")
        run(["brew", "cleanup", "--prune=0", "-s", TRAYSCALE_FORMULA], check=False)
        run(["brew", "reinstall", TRAYSCALE_FORMULA])
    else:
        run(["brew", "install", "--formula", TRAYSCALE_FORMULA])
    verify_installed(TRAYSCALE_FORMULA)
    print("  ✓ Trayscale installed")

    # Install tailscale
    if is_installed(TAILSCALE_FORMULA):
        print("  ✓ Tailscale already installed, reinstalling"  )
        run(["brew", "cleanup", "--prune=0", "-s", TAILSCALE_FORMULA], check=False)
        run(["brew", "reinstall", TAILSCALE_FORMULA])
    else:
        run(["brew", "install", "--formula", TAILSCALE_FORMULA])
    verify_installed(TAILSCALE_FORMULA)
    print("  ✓ Tailscale installed")

    print("  ✓ Tailscale and Trayscale Successfully Installed")


def step_start_service():
    print()
    print("[3/6] Starting Tailscale service...")
    run(["sudo", "pkill", "-f", "tailscaled"], check=False)
    run(["sudo", "brew", "services", "start", "tailscale"])

    # Wait for tailscaled to be ready
    for i in range(30):
        result = run(["tailscale", "status"], check=False, capture=True)
        if result.returncode == 0:
            break
        time.sleep(1)
    else:
        print("  Warning: tailscaled may not be fully ready")

    print("  ✓ Tailscale service started")


def step_connect():
    print()
    print("[4/6] Connecting to Tailscale...")
    run(["sudo", "tailscale", "up"])
    print("  ✓ Tailscale connected")


def step_configure():
    print()
    print("[5/6] Configuring Tailscale settings...")
    user = getpass.getuser()
    run(["sudo", "tailscale", "set", f"--operator={user}"])
    print(f"  ✓ {user} set as operator")
    run(["sudo", "tailscale", "set", "--accept-routes=true"])
    print("  ✓ Accept routes enabled")


def step_dns():
    print()
    print("[6/6] Configuring DNS resolver for MagicDNS...")
    run(["sudo", "mkdir", "-p", "/etc/resolver"])

    result = run(["tailscale", "dns", "status"], capture=True)
    dns_domain = None
    capture_next = False
    for line in result.stdout.splitlines():
        if "Search Domains:" in line:
            capture_next = True
            continue
        if capture_next:
            dns_domain = line.strip().lstrip("- ")
            break

    if not dns_domain:
        print("  Error: Could not determine DNS domain from tailscale dns status")
        sys.exit(1)

    print(f"  Found DNS domain: {dns_domain}")

    search_conf = f"# Added by tailscaled\nsearch {dns_domain}\n"
    run(["sudo", "tee", "/etc/resolver/search.tailscale"],
        input=search_conf.encode(), capture=True)
    print("  ✓ Created /etc/resolver/search.tailscale")

    magicdns_conf = f"domain {dns_domain}\nnameserver 100.100.100.100\n"
    run(["sudo", "tee", "/etc/resolver/magicdns.tailscale"],
        input=magicdns_conf.encode(), capture=True)
    print("  ✓ Created /etc/resolver/magicdns.tailscale")

    run(["sudo", "dscacheutil", "-flushcache"])
    run(["sudo", "killall", "-HUP", "mDNSResponder"])
    print("  ✓ DNS cache flushed")


def step_install_app():
    print()
    print("Installing Trayscale.app...")

    result = run(
        ["brew", "list", TRAYSCALE_FORMULA],
        capture=True,
    )
    app_source = None
    for line in result.stdout.splitlines():
        if "Trayscale.app/Contents/MacOS/trayscale" in line:
            # Go up 3 directories: MacOS -> Contents -> Trayscale.app
            app_source = os.path.dirname(os.path.dirname(os.path.dirname(line.strip())))
            break

    if not app_source:
        print("  Error: Could not find Trayscale.app in brew installation")
        sys.exit(1)

    app_dest = "/Applications/Trayscale.app"
    user = getpass.getuser()
    run(["sudo", "rm", "-rf", app_dest])
    run(["sudo", "cp", "-r", app_source, app_dest])
    run(["sudo", "chown", "-R", user, app_dest])
    run(["sudo", "chmod", "-R", "+rwx", app_dest])


def main():
    print("=== macOS Tailscale + Trayscale Setup Script ===")
    print()

    step_xcode()
    step_brew_install()
    step_start_service()
    step_connect()
    step_configure()
    step_dns()
    step_install_app()

    print()
    print("=== Setup Complete ===")
    print()
    print("You can now:")
    print("  - Launch Trayscale from /Applications/Trayscale.app")
    print("  - Use 'tailscale' command directly (as operator)")
    print()


if __name__ == "__main__":
    main()
