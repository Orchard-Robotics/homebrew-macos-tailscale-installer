# Tailscale OSS Client Setup #
This repo contains a simple script that will install and configure the open source [tailscaled](https://github.com/tailscale/tailscale) daemon and the unofficial [trayscale](https://github.com/DeedleFake/trayscale) MacOS GUI client.

It additionally installs an app file to easily run the GUI.

This avoids bugs (such as slow ssh transfers) in the proprietary MacOS GUI client.

## Installation ##

```
curl https://raw.githubusercontent.com/Orchard-Robotics/macos-tailscale-installer/refs/heads/main/setup-tailscale.py | python3
```

You can then open Trayscale from spotlight or the installed `Trayscale.app` added to `/Applications`