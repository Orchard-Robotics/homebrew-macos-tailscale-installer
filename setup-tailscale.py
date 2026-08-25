#!/usr/bin/env python3

import subprocess
import sys
import os
import time
import getpass
import shutil
import tempfile

TAP = "Orchard-Robotics/macos-tailscale-installer"
TAP_LOWER = TAP.lower()
# Optional tap branch to install from. None uses the tap's default branch,
# which is what you want normally; set it to a branch name to test a formula
# change before it is merged.
TAP_BRANCH = None
TRAYSCALE_FORMULA = f"orchard-robotics/macos-tailscale-installer/trayscale"
TAILSCALE_FORMULA = f"orchard-robotics/macos-tailscale-installer/tailscale"


def sudo_write(path, content):
    """Write content to a root-owned path via a temp file + sudo mv."""
    fd, tmp = tempfile.mkstemp()
    try:
        os.write(fd, content.encode())
        os.close(fd)
        run(["sudo", "mv", tmp, path])
        run(["sudo", "chmod", "755", path])
    except Exception:
        # The mv may already have consumed tmp, so removing it is best-effort.
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


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


def tailscale_bin():
    """Absolute path to tailscale, so sudo does not depend on its PATH."""
    return shutil.which("tailscale") or "tailscale"


def pin_tap_branch():
    """Check out TAP_BRANCH in the tap and confirm it stuck.

    Homebrew's auto-update runs `brew update`, which force-resets every tap
    back to its default branch. That silently undid this checkout and the
    install then built main's formulae. HOMEBREW_NO_AUTO_UPDATE (set in
    main) prevents it; re-assert the branch before each install anyway, and
    fail loudly rather than building the wrong formula.
    """
    if not TAP_BRANCH:
        return
    tap_dir = run(["brew", "--repo", TAP], capture=True).stdout.strip()
    # Check out FETCH_HEAD rather than origin/<branch>: brew may clone taps
    # single-branch, so the remote-tracking ref is not guaranteed to exist.
    run(["git", "-C", tap_dir, "fetch", "origin", TAP_BRANCH])
    run(["git", "-C", tap_dir, "checkout", "-B", TAP_BRANCH, "FETCH_HEAD"])

    head = run(["git", "-C", tap_dir, "rev-parse", "--abbrev-ref", "HEAD"],
               capture=True).stdout.strip()
    if head != TAP_BRANCH:
        print(f"  Error: tap is on '{head}', expected '{TAP_BRANCH}'")
        sys.exit(1)


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
        run(["xcode-select", "--install"], check=False)
        print("  Please complete the installation dialog. Waiting for it to finish...")
        # Do not read stdin here: when this script is piped from curl, stdin is
        # the script itself and is already at EOF, so input() would raise
        # EOFError. Poll for the tools instead.
        for _ in range(360):  # up to 30 minutes
            time.sleep(5)
            if run(["xcode-select", "-p"], check=False, capture=True).returncode == 0:
                break
        else:
            print("  Error: timed out waiting for Xcode Command Line Tools")
            sys.exit(1)
        print("  ✓ Xcode Command Line Tools installed")


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
    pin_tap_branch()
    if TAP_BRANCH:
        print(f"  ✓ Brew Tap ({TAP_LOWER}) installed, pinned to {TAP_BRANCH}")
    else:
        print(f"  ✓ Brew Tap ({TAP_LOWER}) installed")

    # Install trayscale
    pin_tap_branch()
    if is_installed(TRAYSCALE_FORMULA):
        print("  ✓ Trayscale already installed, reinstalling")
        run(["brew", "cleanup", "--prune=0", "-s", TRAYSCALE_FORMULA], check=False)
        run(["brew", "reinstall", TRAYSCALE_FORMULA])
    else:
        run(["brew", "install", "--formula", TRAYSCALE_FORMULA])
    verify_installed(TRAYSCALE_FORMULA)
    print("  ✓ Trayscale installed")

    # Install tailscale
    pin_tap_branch()
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
    run(["sudo", "brew", "services", "start", TAILSCALE_FORMULA])

    # Wait for tailscaled to be ready
    ts = tailscale_bin()
    for i in range(30):
        result = run([ts, "status"], check=False, capture=True)
        # A fresh install is not logged in yet, so tailscale status exits
        # non-zero. That still means tailscaled is up and reachable.
        if result.returncode == 0 or "Logged out" in (result.stdout or ""):
            break
        time.sleep(1)
    else:
        print("  Warning: tailscaled may not be fully ready")

    print("  ✓ Tailscale service started")


def step_connect():
    print()
    print("[4/6] Connecting to Tailscale...")
    run(["sudo", tailscale_bin(), "up"])
    print("  ✓ Tailscale connected")


def step_configure():
    print()
    print("[5/6] Configuring Tailscale settings...")
    user = getpass.getuser()
    run(["sudo", tailscale_bin(), "set", f"--operator={user}"])
    print(f"  ✓ {user} set as operator")
    run(["sudo", tailscale_bin(), "set", "--accept-routes=true"])
    print("  ✓ Accept routes enabled")


def step_dns():
    print()
    print("[6/6] Configuring DNS resolver for MagicDNS...")
    run(["sudo", "mkdir", "-p", "/etc/resolver"])

    result = run([tailscale_bin(), "dns", "status"], capture=True)
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

    sudo_write("/etc/resolver/search.tailscale",
               f"# Added by tailscaled\nsearch {dns_domain}\n")
    print("  ✓ Created /etc/resolver/search.tailscale")

    sudo_write("/etc/resolver/magicdns.tailscale",
               f"domain {dns_domain}\nnameserver 100.100.100.100\n")
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

    # brew's auto-update force-resets taps to their default branch, which
    # would undo the TAP_BRANCH pin mid-run.
    os.environ["HOMEBREW_NO_AUTO_UPDATE"] = "1"

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
