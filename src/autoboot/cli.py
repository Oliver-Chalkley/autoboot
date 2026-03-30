"""CLI entry point for autoboot."""

from pathlib import Path

import click

from autoboot import __version__
from autoboot.build import build_machine
from autoboot.config import create_config, load_config, validate_config
from autoboot.flash import flash_machine
from autoboot.iso import download_iso
from autoboot.paths import get_configs_dir, get_downloads_dir


@click.group()
@click.version_option(version=__version__, prog_name="autoboot")
def main() -> None:
    """Create bootable USBs that auto-install Linux with ansible user and SSH key."""


@main.command("list")
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None,
              help="Project root directory.")
def list_cmd(root: Path | None) -> None:
    """List all machine configs."""
    configs_dir = get_configs_dir(root)
    if not configs_dir.exists():
        click.echo("No machine configs found.")
        return
    names = sorted(
        p.parent.name for p in configs_dir.glob("*/config.yaml")
    )
    if not names:
        click.echo("No machine configs found.")
        return
    for name in names:
        click.echo(name)


@main.command()
@click.argument("name")
@click.option("--distro", required=True, help="Linux distribution (ubuntu, debian).")
@click.option("--version", "distro_version", default=None,
              help="Distro version. Defaults to latest supported.")
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None,
              help="Project root directory.")
def new(name: str, distro: str, distro_version: str | None, root: Path | None) -> None:
    """Create a new machine config."""
    configs_dir = get_configs_dir(root)
    config_path = configs_dir / name / "config.yaml"
    if config_path.exists():
        raise click.ClickException(f"Config '{name}' already exists.")

    create_config(name, distro, distro_version or "", configs_dir)
    click.echo(f"Created config: {config_path}")


@main.command()
@click.argument("name")
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None,
              help="Project root directory.")
def validate(name: str, root: Path | None) -> None:
    """Validate a machine config."""
    configs_dir = get_configs_dir(root)
    config_path = configs_dir / name / "config.yaml"
    if not config_path.exists():
        raise click.ClickException(f"Config not found: {config_path}")

    config = load_config(config_path)
    errors = validate_config(config)
    if errors:
        for err in errors:
            click.echo(f"  - {err}", err=True)
        raise click.ClickException("Validation failed.")

    click.echo(f"Config '{name}' is valid.")


@main.command()
@click.argument("name")
@click.option("--force", is_flag=True, help="Re-download even if ISO exists.")
@click.option("--local", "local_iso", type=click.Path(exists=True, path_type=Path),
              default=None, help="Copy ISO from local path instead of downloading.")
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None,
              help="Project root directory.")
def download(name: str, force: bool, local_iso: Path | None, root: Path | None) -> None:
    """Download or copy the ISO for a machine config."""
    configs_dir = get_configs_dir(root)
    config_path = configs_dir / name / "config.yaml"
    if not config_path.exists():
        raise click.ClickException(f"Config not found: {config_path}")

    config = load_config(config_path)
    downloads_dir = get_downloads_dir(root)

    result = download_iso(config, downloads_dir, local_iso=local_iso, force=force)
    click.echo(f"ISO ready: {result}")


@main.command()
@click.argument("name")
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None,
              help="Project root directory.")
def build(name: str, root: Path | None) -> None:
    """Build a customized ISO for a machine config."""
    result = build_machine(name, root=root)
    click.echo(f"Built ISO: {result}")


@main.command()
@click.argument("name")
@click.argument("device", type=click.Path(path_type=Path))
@click.option("--yes", "skip_confirm", is_flag=True,
              help="Skip confirmation prompt.")
@click.option("--root", type=click.Path(exists=True, path_type=Path), default=None,
              help="Project root directory.")
def flash(name: str, device: Path, skip_confirm: bool, root: Path | None) -> None:
    """Flash a built ISO to a USB device."""
    flash_machine(name, device, root=root, skip_confirm=skip_confirm)
    click.echo("Flash complete.")
