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
    files_copied = 0
    files_skipped = 0
    errors = 0

    for system in systems:
        for media_type in ("box", "preview", "synopsis"):
            src_dir = Path(system.get(media_type, ""))
            if not src_dir.exists():
                continue

            # Mirror the catalogue structure
            # e.g. /mnt/mmc/MUOS/info/catalogue/Nintendo SNES-SFC/box/
            # becomes MUOS/backup/artie/catalogue/Nintendo SNES-SFC/box/
            try:
                # Extract catalogue-relative path
                parts = src_dir.parts
                try:
                    cat_idx = parts.index("catalogue")
                    rel_path = Path(*parts[cat_idx:])
                except ValueError:
                    # Fallback: use system dir name + media type
                    rel_path = (
                        Path("catalogue") / system.get("dir", "unknown") / media_type
                    )

                dst_dir = backup_root / rel_path
                dst_dir.mkdir(parents=True, exist_ok=True)

                for src_file in src_dir.iterdir():
                    if not src_file.is_file():
                        continue
                    dst_file = dst_dir / src_file.name

                    # Skip if destination exists and is same size (already backed up)
                    if (
                        dst_file.exists()
                        and dst_file.stat().st_size == src_file.stat().st_size
                    ):
                        files_skipped += 1
                        continue

                    try:
                        shutil.copy2(src_file, dst_file)
                        files_copied += 1
                    except OSError as e:
                        logger.log_warning(f"Failed to copy {src_file}: {e}")
                        errors += 1

            except Exception as e:
                logger.log_error(f"Error backing up {src_dir}: {e}")
                errors += 1

    logger.log_info(
        f"Backup complete: {files_copied} copied, {files_skipped} skipped, {errors} errors"
    )
    return files_copied, files_skipped, errors


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

    files_restored = 0
    files_skipped = 0
    errors = 0

    for system in systems:
        for media_type in ("box", "preview", "synopsis"):
            dst_dir = Path(system.get(media_type, ""))
            if not dst_dir.parent.exists():
                continue

            try:
                parts = dst_dir.parts
                try:
                    cat_idx = parts.index("catalogue")
                    rel_path = Path(*parts[cat_idx:])
                except ValueError:
                    rel_path = (
                        Path("catalogue") / system.get("dir", "unknown") / media_type
                    )

                src_dir = backup_root / rel_path
                if not src_dir.exists():
                    continue

                dst_dir.mkdir(parents=True, exist_ok=True)

                for src_file in src_dir.iterdir():
                    if not src_file.is_file():
                        continue
                    dst_file = dst_dir / src_file.name

                    if (
                        dst_file.exists()
                        and dst_file.stat().st_size == src_file.stat().st_size
                    ):
                        files_skipped += 1
                        continue

                    try:
                        shutil.copy2(src_file, dst_file)
                        files_restored += 1
                    except OSError as e:
                        logger.log_warning(f"Failed to restore {src_file}: {e}")
                        errors += 1

            except Exception as e:
                logger.log_error(f"Error restoring to {dst_dir}: {e}")
                errors += 1

    logger.log_info(
        f"Restore complete: {files_restored} restored, {files_skipped} skipped, {errors} errors"
    )
    return files_restored, files_skipped, errors
