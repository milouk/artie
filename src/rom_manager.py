"""ROM management module for Artie Scraper."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Generator, List, Set

import exceptions
from logger import LoggerSingleton as logger


@dataclass
class Rom:
    """Data class representing a ROM file."""

    name: str
    filename: str
    path: Path

    def __post_init__(self):
        """Ensure path is a Path object."""
        if not isinstance(self.path, Path):
            self.path = Path(self.path)

    def __hash__(self):
        """Make ROM objects hashable based on their path."""
        return hash(str(self.path))

    def __eq__(self, other):
        """Define equality based on path."""
        if not isinstance(other, Rom):
            return False
        return str(self.path) == str(other.path)


class RomManager:
    """Manages ROM discovery, validation, and file operations."""

    # Invalid ROM extensions that should be skipped
    INVALID_EXTENSIONS: Set[str] = {
        ".cue",
        ".m3u",
        ".jpg",
        ".png",
        ".img",
        ".sub",
        ".db",
        ".xml",
        ".txt",
        ".dat",
        ".mp4",
        ".pdf",
        ".inf",
    }

    def __init__(self, roms_base_path: str):
        """
        Initialize ROM manager.

        Args:
            roms_base_path: Base path where ROM directories are located
        """
        self.roms_base_path = Path(roms_base_path)
        self._validate_base_path()

    def _validate_base_path(self) -> None:
        """Validate that the base ROM path exists and is accessible."""
        if not self.roms_base_path.exists():
            raise exceptions.ConfigurationError(
                f"ROMs base path does not exist: {self.roms_base_path}"
            )

        if not self.roms_base_path.is_dir():
            raise exceptions.ConfigurationError(
                f"ROMs base path is not a directory: {self.roms_base_path}"
            )

    def get_available_systems(self, systems_mapping: dict) -> List[str]:
        """
        Get list of available systems based on directory structure.

        Args:
            systems_mapping: Mapping of system directories to configuration

        Returns:
            Sorted list of available system names
        """
        try:
            available_systems = [
                d.name.lower()
                for d in self.roms_base_path.iterdir()
                if d.is_dir() and not d.name.startswith(".")
            ]

            # Filter to only include configured systems
            configured_systems = [
                system for system in available_systems if system in systems_mapping
            ]

            logger.log_debug(
                f"Found {len(configured_systems)} configured systems: {configured_systems}"
            )
            return sorted(configured_systems)

        except Exception as e:
            logger.log_error(f"Error getting available systems: {e}")
            return []

    def get_roms(self, system: str) -> List[Rom]:
        """
        Get all valid ROM files for a given system.

        Args:
            system: System name (directory name)

        Returns:
            List of ROM objects
        """
        roms = []
        system_path = self.roms_base_path / system

        if not system_path.exists():
            logger.log_warning(f"System path does not exist: {system_path}")
            return roms

        try:
            for rom in self._discover_roms(system_path):
                roms.append(rom)

            logger.log_info(f"Found {len(roms)} ROMs for system '{system}'")
            return roms

        except Exception as e:
            logger.log_error(f"Error getting ROMs for system '{system}': {e}")
            return []

    def _discover_roms(self, system_path: Path) -> Generator[Rom, None, None]:
        """
        Discover ROM files in a system directory using generator for memory efficiency.

        Args:
            system_path: Path to the system directory

        Yields:
            Rom objects for valid ROM files
        """
        try:
            for root, dirs, files in os.walk(system_path):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith(".")]

                root_path = Path(root)

                for file in files:
                    if file.startswith("."):
                        continue

                    file_path = root_path / file

                    if self.is_valid_rom(file_path):
                        rom = Rom(name=file_path.stem, filename=file, path=file_path)
                        yield rom

        except Exception as e:
            logger.log_error(f"Error discovering ROMs in {system_path}: {e}")

    def is_valid_rom(self, file_path: Path) -> bool:
        """
        Check if a file is a valid ROM file.

        Args:
            file_path: Path to the file to check

        Returns:
            True if the file is a valid ROM, False otherwise
        """
        try:
            if not file_path.is_file():
                return False

            # Check file extension
            extension = file_path.suffix.lower()
            if extension in self.INVALID_EXTENSIONS:
                return False

            # Additional validation could be added here
            # (e.g., file size checks, magic number validation)

            return True

        except Exception as e:
            logger.log_debug(f"Error validating ROM {file_path}: {e}")
            return False

    def get_roms_without_files(
        self,
        enabled: bool,
        dir_path: Path,
        roms_list: List[Rom],
        get_files_func: Callable[[Path], List[str]],
    ) -> List[Rom]:
        """
        Get ROMs that are missing specific file types (box art, previews, etc.).

        Args:
            enabled: Whether this media type is enabled
            dir_path: Directory to check for existing files
            roms_list: List of all ROMs
            get_files_func: Function to get existing files without extension

        Returns:
            List of ROMs missing the specified file type
        """
        if not enabled:
            return []

        try:
            # Ensure directory exists
            if not dir_path.exists():
                dir_path.mkdir(parents=True, exist_ok=True)
                return roms_list

            # Get existing files
            existing_files = set(get_files_func(dir_path))

            # Filter ROMs that don't have corresponding files
            missing_roms = [rom for rom in roms_list if rom.name not in existing_files]

            logger.log_debug(
                f"Found {len(missing_roms)} ROMs missing files in {dir_path} "
                f"(out of {len(roms_list)} total ROMs)"
            )

            return missing_roms

        except Exception as e:
            logger.log_error(f"Error checking missing files in {dir_path}: {e}")
            return roms_list  # Return all ROMs if we can't check

    def delete_files_in_directory(
        self, filenames: List[str], directory_path: Path
    ) -> int:
        """
        Delete files in directory with proper error handling.

        Args:
            filenames: List of filenames (without extension) to delete
            directory_path: Directory containing the files

        Returns:
            Number of files successfully deleted
        """
        if not directory_path.exists():
            logger.log_warning(f"Directory does not exist: {directory_path}")
            return 0

        if not directory_path.is_dir():
            logger.log_warning(f"Path is not a directory: {directory_path}")
            return 0

        filenames_set = set(filenames)
        deleted_count = 0

        try:
            for file_path in directory_path.iterdir():
                if file_path.is_file() and file_path.stem in filenames_set:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.log_debug(f"Deleted file: {file_path}")
                    except (IOError, OSError) as e:
                        logger.log_warning(f"Error deleting file {file_path}: {e}")

            logger.log_info(f"Deleted {deleted_count} files from {directory_path}")
            return deleted_count

        except Exception as e:
            logger.log_error(f"Error deleting files in {directory_path}: {e}")
            return deleted_count

    def delete_rom_media(
        self, rom: Rom, system_config: dict, enabled_media_types: List[str]
    ) -> None:
        """
        Delete all media files for a specific ROM.

        Args:
            rom: ROM object
            system_config: System configuration containing media paths
            enabled_media_types: List of enabled media types to delete
        """
        try:
            for media_type in enabled_media_types:
                media_path_str = system_config.get(media_type, "")
                if media_path_str:
                    media_path = Path(media_path_str)
                    self.delete_files_in_directory([rom.name], media_path)

        except Exception as e:
            logger.log_error(f"Error deleting media for ROM {rom.name}: {e}")

    def delete_system_media(
        self, system: str, system_config: dict, enabled_media_types: List[str]
    ) -> None:
        """
        Delete all media files for a system.

        Args:
            system: System name
            system_config: System configuration containing media paths
            enabled_media_types: List of enabled media types to delete
        """
        try:
            roms = self.get_roms(system)
            rom_names = [rom.name for rom in roms]

            for media_type in enabled_media_types:
                media_path_str = system_config.get(media_type, "")
                if media_path_str:
                    media_path = Path(media_path_str)
                    self.delete_files_in_directory(rom_names, media_path)

        except Exception as e:
            logger.log_error(f"Error deleting system media for '{system}': {e}")

    def get_rom_statistics(self, system: str) -> dict:
        """
        Get statistics about ROMs in a system.

        Args:
            system: System name

        Returns:
            Dictionary with ROM statistics
        """
        try:
            roms = self.get_roms(system)

            # Calculate file size statistics
            total_size = 0
            file_extensions = {}

            for rom in roms:
                try:
                    size = rom.path.stat().st_size
                    total_size += size

                    ext = rom.path.suffix.lower()
                    file_extensions[ext] = file_extensions.get(ext, 0) + 1

                except Exception as e:
                    logger.log_debug(f"Error getting stats for ROM {rom.path}: {e}")

            return {
                "total_roms": len(roms),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "file_extensions": file_extensions,
                "average_size_mb": (
                    round((total_size / len(roms)) / (1024 * 1024), 2) if roms else 0
                ),
            }

        except Exception as e:
            logger.log_error(f"Error getting ROM statistics for '{system}': {e}")
            return {
                "total_roms": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "file_extensions": {},
                "average_size_mb": 0,
            }
