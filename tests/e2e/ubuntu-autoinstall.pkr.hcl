# Packer template for E2E testing Ubuntu autoinstall ISOs.
#
# Prerequisites:
#   - packer (https://www.packer.io/)
#   - qemu-system-x86_64
#   - A built autoboot ISO in isos/built/
#
# Usage:
#   packer init tests/e2e/ubuntu-autoinstall.pkr.hcl
#   packer build -var "iso_path=isos/built/my-server-20240328.iso" tests/e2e/ubuntu-autoinstall.pkr.hcl

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
  default = "15m"
}

source "qemu" "ubuntu" {
  iso_url          = var.iso_path
  iso_checksum     = "none"
  output_directory = "tests/e2e/output/ubuntu"

  vm_name          = "autoboot-ubuntu-test"
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
  sources = ["source.qemu.ubuntu"]

  provisioner "shell" {
    inline = [
      "echo '=== Autoboot E2E Validation ==='",
      "",
      "echo 'Checking ansible user...'",
      "id ansible",
      "",
      "echo 'Checking passwordless sudo...'",
      "sudo -n whoami | grep -q root",
      "",
      "echo 'Checking SSH authorized_keys...'",
      "test -f /home/ansible/.ssh/authorized_keys",
      "echo \"  keys: $(wc -l < /home/ansible/.ssh/authorized_keys)\"",
      "",
      "echo 'Checking packages...'",
      "dpkg -l python3 | grep -q '^ii'",
      "dpkg -l openssh-server | grep -q '^ii'",
      "echo '  python3 and openssh-server installed'",
      "",
      "echo 'Checking autoinstall marker...'",
      "test -f /var/log/autoinstall-success",
      "",
      "echo 'Checking sudoers NOPASSWD...'",
      "sudo -n true && echo '  NOPASSWD sudo works'",
      "",
      "echo 'System info:'",
      "echo \"  hostname: $(hostname)\"",
      "echo \"  os: $(lsb_release -ds 2>/dev/null || cat /etc/os-release | head -1)\"",
      "",
      "echo '=== All checks passed ==='",
    ]
  }
}
