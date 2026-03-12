"""Backup module - copy catalogue data to SD2 for preservation."""

import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from logger import LoggerSingleton as logger

# MuOS SD card mount points
SD2_PATHS = [
    "/run/muos/storage/sdcard",
    "/mnt/sdcard",
]

BACKUP_DIR_NAME = "MUOS/backup/artie"
MEDIA_TYPES = ("box", "preview", "synopsis")


def find_sd2() -> Optional[Path]:
    """Find the SD2 mount point."""
    for mount in SD2_PATHS:
        p = Path(mount)
        if p.exists() and p.is_mount():
            return p
    # Fallback: check if sdcard path exists even if not detected as mount
    for mount in SD2_PATHS:
        p = Path(mount)
        if p.exists():
            return p
    return None


def get_backup_path() -> Optional[Path]:
    """Get the backup destination path on SD2."""
    sd2 = find_sd2()
    if not sd2:
        return None
    return sd2 / BACKUP_DIR_NAME


def _get_catalogue_rel_path(directory: Path, system: dict, media_type: str) -> Path:
    """Extract catalogue-relative path from a media directory."""
    parts = directory.parts
    try:
        cat_idx = parts.index("catalogue")
        return Path(*parts[cat_idx:])
    except ValueError:
        return Path("catalogue") / system.get("dir", "unknown") / media_type


def _copy_files(
    src_dir: Path, dst_dir: Path, label: str
) -> Tuple[int, int, int]:
    """Copy files from src to dst, skipping same-size duplicates."""
    copied = 0
    skipped = 0
    errors = 0

    dst_dir.mkdir(parents=True, exist_ok=True)

    for src_file in src_dir.iterdir():
        if not src_file.is_file():
            continue
        dst_file = dst_dir / src_file.name

        # Skip if destination exists and is same size (already synced)
        try:
            src_stat = src_file.stat()
            if dst_file.exists() and dst_file.stat().st_size == src_stat.st_size:
                skipped += 1
                continue
        except OSError:
            pass

        try:
            shutil.copy2(src_file, dst_file)
            copied += 1
        except OSError as e:
            logger.log_warning(f"Failed to {label} {src_file}: {e}")
            errors += 1

    return copied, skipped, errors


def _sync_catalogue(
    systems: List[dict], src_key: str, dst_resolver, operation: str
) -> Tuple[int, int, int]:
    """
    Generic catalogue sync between local and backup directories.

    Args:
        systems: List of system config dicts
        src_key: Which path is the source ("local" or "backup")
        dst_resolver: Callable(system, media_type, rel_path) -> (src_dir, dst_dir)
        operation: Label for logging ("copy" or "restore")
    """
    total_copied = 0
    total_skipped = 0
    total_errors = 0

    for system in systems:
        for media_type in MEDIA_TYPES:
            local_dir = Path(system.get(media_type, ""))
            rel_path = _get_catalogue_rel_path(local_dir, system, media_type)
            src_dir, dst_dir = dst_resolver(local_dir, rel_path)

            if not src_dir.exists():
                continue

            try:
                copied, skipped, errors = _copy_files(
                    src_dir, dst_dir, operation
                )
                total_copied += copied
                total_skipped += skipped
                total_errors += errors
            except Exception as e:
                logger.log_error(f"Error during {operation} for {src_dir}: {e}")
                total_errors += 1

    logger.log_info(
        f"{operation.capitalize()} complete: {total_copied} {operation}d, "
        f"{total_skipped} skipped, {total_errors} errors"
    )
    return total_copied, total_skipped, total_errors


def backup_catalogue(systems: List[dict]) -> Tuple[int, int, int]:
    """
    Backup all catalogue data (box, preview, synopsis) to SD2.

    Args:
        systems: List of system config dicts with box/preview/synopsis paths

    Returns:
        (files_copied, files_skipped, errors) counts
    """
    backup_root = get_backup_path()
    if not backup_root:
        raise FileNotFoundError("SD2 not found - insert second SD card")

    backup_root.mkdir(parents=True, exist_ok=True)

    def resolve(local_dir, rel_path):
        return local_dir, backup_root / rel_path

    return _sync_catalogue(systems, "local", resolve, "copy")


def restore_catalogue(systems: List[dict]) -> Tuple[int, int, int]:
    """
    Restore catalogue data from SD2 backup.

    Args:
        systems: List of system config dicts

    Returns:
        (files_restored, files_skipped, errors) counts
    """
    backup_root = get_backup_path()
    if not backup_root or not backup_root.exists():
        raise FileNotFoundError("No backup found on SD2")

    def resolve(local_dir, rel_path):
        return backup_root / rel_path, local_dir

    return _sync_catalogue(systems, "backup", resolve, "restore")
