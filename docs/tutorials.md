# Tutorials

Step-by-step guides that walk through real use cases, from simple to advanced.

**Prerequisites**: You've followed the [Quick Start](../README.md#quick-start) to install dependencies and run `uv sync`.

---

## Tutorial 1: Recreate a USB for an existing machine

You have a server already running Ubuntu 24.04.3. You know its hostname, admin user, and network setup. You want a bootable USB that can recreate it identically.

### 1. Add your SSH key

Copy the public key your Ansible controller uses:

```bash
cp ~/.ssh/ansible.pub keys/ansible.pub
```

This key gets baked into every ISO so the `ansible` user is accessible via SSH immediately after install.

### 2. Create the config

```bash
uv run autoboot new lounge --distro ubuntu
```

This creates `configs/lounge/config.yaml` with sensible defaults.

### 3. Edit the config to match your existing server

```bash
nano configs/lounge/config.yaml
```

Fill in the values you know from the running machine:

```yaml
machine_name: lounge
distro: ubuntu
distro_version: "24.04.3"
hostname: lounge
locale: en_US.UTF-8
keyboard_layout: us
timezone: Europe/London

network:
  type: dhcp

storage:
  layout: lvm
  match: largest

admin:
  username: admin
  password_hash: "$6$rounds=4096$..."
  real_name: Administrator
```

Generate the password hash with:

```bash
mkpasswd -m sha-512
```

### 4. Validate

```bash
uv run autoboot validate lounge
```

Fix any errors before proceeding.

### 5. Download the official ISO

```bash
uv run autoboot download lounge
```

This downloads the Ubuntu 24.04.3 server ISO and verifies its checksum. If you have the ISO on a NAS, skip the download:

```bash
uv run autoboot download lounge --local /mnt/nas/ubuntu-24.04.3-live-server-amd64.iso
```

### 6. Build the customized ISO

```bash
uv run autoboot build lounge
```

This injects your config and SSH key into the ISO so it installs unattended.

### 7. Flash to USB

```bash
sudo uv run autoboot flash lounge /dev/sdb
```

**Warning**: Double-check the device path. This overwrites the entire device. Use `lsblk` to identify the correct USB stick.

You now have a USB that will install an identical copy of your server, with the `ansible` user ready for remote management.

---

## Tutorial 2: Test before you flash

Before wasting a USB stick (or worse, flashing the wrong device), verify the ISO works by booting it in a VM.

### Prerequisites

Install Packer and QEMU:

```bash
# Packer: https://www.packer.io/
# QEMU:
sudo apt install qemu-system-x86
```

KVM is strongly recommended — without it the VM test takes hours instead of minutes. Check if KVM is available:

```bash
ls /dev/kvm
```

### Run the test

Using the `lounge` config from Tutorial 1:

```bash
uv run autoboot test lounge
```

This:
1. Boots the built ISO in a QEMU VM
2. Waits for the unattended install to complete (~10-20 min with KVM)
3. Connects via SSH as the `ansible` user
4. Validates: user exists, SSH key works, passwordless sudo, packages installed

### Watch the install live

The output includes a VNC command:

```
  [test] To watch the install: vncviewer 127.0.0.1::5941
```

Open it in a VNC viewer to see the install happening in real time. Useful for debugging if the test hangs.

### Interpret the result

- **Passed**: The ISO installs correctly. Safe to flash.
- **Failed**: Check the output for what went wrong. Common issues:
  - Bad password hash format
  - Network config preventing package downloads
  - Missing packages in the distro's default repos

Fix the config, rebuild, and test again:

```bash
uv run autoboot build lounge
uv run autoboot test lounge
```

---

## Tutorial 3: Upgrade the OS version

Six months later, Ubuntu 24.04.3 is out and you want your `lounge` USB updated.

### 1. Update the version

```bash
nano configs/lounge/config.yaml
```

Change:

```yaml
distro_version: "24.04.3"
```

Everything else stays the same — same hostname, same network, same admin user.

### 2. Download the new ISO

```bash
uv run autoboot download lounge
```

This downloads the new version. If you already have the old version cached, it fetches the new one alongside it. To force a re-download:

```bash
uv run autoboot download lounge --force
```

### 3. Build and test

```bash
uv run autoboot build lounge
uv run autoboot test lounge
```

Testing is especially important after a version bump — distro changes occasionally break autoinstall configs.

### 4. Flash

Once the test passes:

```bash
sudo uv run autoboot flash lounge /dev/sdb
```

---

## Tutorial 4: Same machine, different distro

You've been running Ubuntu on `lounge` but want to try Debian instead. The machine's role and config stay the same.

### 1. Create a Debian config

```bash
uv run autoboot new lounge-debian --distro debian
```

### 2. Copy your settings across

```bash
nano configs/lounge-debian/config.yaml
```

```yaml
machine_name: lounge-debian
distro: debian
distro_version: "12.10"
hostname: lounge
locale: en_US.UTF-8
keyboard_layout: us
timezone: Europe/London

network:
  type: dhcp

storage:
  layout: lvm
  match: largest

admin:
  username: admin
  password_hash: "$6$rounds=4096$..."
  real_name: Administrator
```

The config format is identical — autoboot handles the translation to Debian preseed format internally.

### 3. Download, build, test

```bash
uv run autoboot download lounge-debian
uv run autoboot build lounge-debian
uv run autoboot test lounge-debian
```

Testing is critical here. Ubuntu autoinstall and Debian preseed work differently under the hood. The test confirms that the Debian translation produces a working install.

### 4. Compare both

You now have two configs:

```bash
uv run autoboot list
```

```
lounge
lounge-debian
```

Keep both around. If you decide to switch, flash the Debian USB. If it doesn't work out, the Ubuntu USB config is still there.

### 5. Try Fedora too

The same approach works for Fedora (which uses kickstart for unattended installs):

```bash
uv run autoboot new lounge-fedora --distro fedora
```

Edit the config (same format — just change `distro` and `distro_version`):

```yaml
machine_name: lounge-fedora
distro: fedora
distro_version: "43"
hostname: lounge
# ... rest of config identical
```

```bash
uv run autoboot download lounge-fedora
uv run autoboot build lounge-fedora
uv run autoboot test lounge-fedora
```

Autoboot translates the same simple YAML config into kickstart format automatically. Note that Fedora uses `wheel` instead of `sudo` for admin group membership — autoboot handles this for you.

---

## Tutorial 5: Customize for a new machine

A new server arrives with specific requirements: static IP, extra packages, and a post-install script that joins it to your monitoring system.

### 1. Create the config

```bash
uv run autoboot new monitoring --distro ubuntu
```

### 2. Configure static networking

```bash
nano configs/monitoring/config.yaml
```

```yaml
machine_name: monitoring
distro: ubuntu
distro_version: "24.04.3"
hostname: monitoring
locale: en_US.UTF-8
keyboard_layout: us
timezone: Europe/London

network:
  type: static
  interface: eth0
  address: 192.168.1.50/24
  gateway: 192.168.1.1
  dns:
    - 1.1.1.1
    - 8.8.8.8

storage:
  layout: lvm
  match: largest

admin:
  username: admin
  password_hash: "$6$rounds=4096$..."
  real_name: Administrator
```

### 3. Add extra packages

```yaml
packages:
  - curl
  - jq
  - docker.io
```

These are installed during the unattended install, on top of the defaults (`python3`, `openssh-server`).

### 4. Add post-install commands

```yaml
extra_late_commands:
  - "systemctl enable docker"
  - "mkdir -p /home/admin/.config"
```

These run at the end of installation, after all packages are installed. Use them for anything the config options don't cover.

### 5. Validate, build, test, flash

```bash
uv run autoboot validate monitoring
uv run autoboot download monitoring
uv run autoboot build monitoring
uv run autoboot test monitoring
sudo uv run autoboot flash monitoring /dev/sdb
```

Always validate before building — it catches config mistakes early (bad version numbers, missing required fields, invalid network config).

---

## Tutorial 6: Managing a fleet

You now have several machines. Here's how to keep things organized.

### List all configs

```bash
uv run autoboot list
```

```
lounge
lounge-debian
monitoring
db-01
web-01
web-02
```

### Validate everything

Check all configs are still valid before a rebuild cycle:

```bash
for name in $(uv run autoboot list); do
    echo "--- $name ---"
    uv run autoboot validate "$name"
done
```

### Rebuild after a key change

If you rotate your SSH key:

```bash
cp ~/.ssh/new_ansible.pub keys/ansible.pub

for name in $(uv run autoboot list); do
    uv run autoboot build "$name"
done
```

Every ISO needs rebuilding because the SSH key is baked in at build time.

### Naming conventions

A pattern that works well:

- `lounge` — machine name matches hostname
- `lounge-debian` — variant of same machine with different distro
- `web-01`, `web-02` — numbered machines with the same role

Configs are just directories under `configs/`, so use whatever naming scheme fits your environment.

### Version control

Configs are plain YAML files designed to be committed to Git. The ISOs themselves are gitignored — they're large and reproducible from the configs.

Your Git history becomes the changelog: when you changed a password hash, when you bumped a distro version, when you added a new machine.
