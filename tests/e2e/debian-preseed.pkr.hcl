# Packer template for E2E testing Debian preseed ISOs.
#
# Prerequisites:
#   - packer (https://www.packer.io/)
#   - qemu-system-x86_64
#   - A built autoboot ISO in isos/built/
#
# Usage:
#   packer init tests/e2e/debian-preseed.pkr.hcl
#   packer build -var "iso_path=isos/built/my-server-20240328.iso" tests/e2e/debian-preseed.pkr.hcl

packer {
  required_plugins {
    qemu = {
      version = ">= 1.1.0"
      source  = "github.com/hashicorp/qemu"
    }
  }
}

variable "iso_path" {
  type        = string
  description = "Path to the built autoboot ISO."
}

variable "ssh_private_key_file" {
  type        = string
  default     = "keys/ansible"
  description = "Path to the SSH private key for the ansible user."
}

variable "vm_memory" {
  type    = number
  default = 2048
}

variable "vm_disk_size" {
  type    = string
  default = "20G"
}

variable "ssh_timeout" {
  type    = string
  default = "30m"
}

source "qemu" "debian" {
  iso_url          = var.iso_path
  iso_checksum     = "none"
  output_directory = "tests/e2e/output/debian"

  vm_name          = "autoboot-debian-test"
  headless         = true
  accelerator      = "kvm"
  memory           = var.vm_memory
  cpus             = 2
  disk_size        = var.vm_disk_size
  format           = "qcow2"

  net_device       = "virtio-net"
  disk_interface   = "virtio"

  # No boot command needed — the ISO is configured for fully unattended install
  boot_wait        = "5s"
  boot_command     = ["<enter>"]

  # SSH connection to validate the install
  ssh_username         = "ansible"
  ssh_private_key_file = var.ssh_private_key_file
  ssh_timeout          = var.ssh_timeout
  ssh_port             = 22

  shutdown_command = "sudo shutdown -P now"
}

build {
  sources = ["source.qemu.debian"]

  # Basic smoke test: verify we can connect and the system is functional
  provisioner "shell" {
    inline = [
      "echo '=== Autoboot E2E Validation (Debian) ==='",
      "",
      "# Verify ansible user",
      "echo 'Checking ansible user...'",
      "id ansible",
      "",
      "# Verify passwordless sudo",
      "echo 'Checking sudo access...'",
      "sudo whoami | grep -q root",
      "",
      "# Verify SSH authorized keys",
      "echo 'Checking SSH key...'",
      "test -f /home/ansible/.ssh/authorized_keys",
      "",
      "# Verify essential packages",
      "echo 'Checking packages...'",
      "dpkg -l python3 | grep -q '^ii'",
      "dpkg -l openssh-server | grep -q '^ii'",
      "",
      "# Verify autoinstall success marker",
      "echo 'Checking install marker...'",
      "test -f /var/log/autoinstall-success",
      "",
      "# Verify sudoers.d config",
      "echo 'Checking sudoers config...'",
      "test -f /etc/sudoers.d/ansible",
      "",
      "echo '=== All checks passed ==='",
    ]
  }

  # Run the full Ansible validation playbook
  provisioner "ansible" {
    playbook_file = "tests/e2e/validate-install.yml"
    user          = "ansible"
    extra_arguments = [
      "--private-key", var.ssh_private_key_file,
    ]
  }
}
