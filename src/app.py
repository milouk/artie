"""Main application module for Artie Scraper with optimized structure."""

import concurrent.futures
import sys
import threading
import time
from pathlib import Path
from typing import Any, List, Optional, Tuple

# Add current directory to Python path to ensure module resolution
# This fixes the ModuleNotFoundError when running from different directories
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

import exceptions
import input
from backup import backup_catalogue
from cache_manager import get_cache_manager
from config_manager import ConfigManager, ScraperConfig
from graphic import GUI
from image_processor import get_image_processor
from logger import LoggerSingleton as logger
from rom_manager import Rom, RomManager
from scraper import (
    check_destination,
    fetch_box,
    fetch_metadata,
    fetch_preview,
    fetch_synopsis,
    get_game_data,
    get_image_files_without_extension,
    get_txt_files_without_extension,
    get_user_data,
)
from updater import check_for_update, download_and_apply_update

VERSION = "3.0.0"


class _ScrapeCancelledError(Exception):
    """Raised inside worker threads when scraping is cancelled."""

    pass


# Constants
DEFAULT_MAX_ELEMENTS = 11
DEFAULT_LOG_WAIT_TIME = 2
LARGE_NAVIGATION_STEP = 100


class RomsData:
    """Data container for ROM-related information."""

    def __init__(
        self,
        roms_list: List[Rom],
        roms_to_scrape: List[Rom],
        roms_without_box: List[Rom],
        roms_without_preview: List[Rom],
        roms_without_synopsis: List[Rom],
        system_config: dict,
        system_id: str,
    ):
        self.roms_list = roms_list
        self.roms_to_scrape = roms_to_scrape
        self.roms_without_box = set(roms_without_box)
        self.roms_without_preview = set(roms_without_preview)
        self.roms_without_synopsis = set(roms_without_synopsis)
        self.system_config = system_config
        self.system_id = system_id

        # Derived properties
        self.box_dir = Path(system_config["box"])
        self.preview_dir = Path(system_config["preview"])
        self.synopsis_dir = Path(system_config["synopsis"])


class App:
    """
    Main application class with proper separation of concerns and optimized structure.

    This class orchestrates the application flow using specialized managers for
    configuration, ROM management, and caching.
    """

    LOG_WAIT = DEFAULT_LOG_WAIT_TIME

    def __init__(self):
        """Initialize application with managers and state."""
        # Managers
        self.config_manager = ConfigManager()
        self.rom_manager: Optional[RomManager] = None
        self.cache_manager = get_cache_manager()

        # Configuration
        self.config: Optional[ScraperConfig] = None

        # Application state
        self.selected_position = 0
        self.roms_selected_position = 0
        self.selected_system = ""
        self.current_window = "emulators"
        self.max_elem = DEFAULT_MAX_ELEMENTS
        self.skip_input_check = False

        # Transition state management for atomic transitions
        self.pending_transition = False
        self.transition_data: Optional[RomsData] = None
        self.transition_target_system = ""

        # ROM data caching
        self.cached_roms_data: Optional[RomsData] = None
        self.cached_system: Optional[str] = None

        # Scraping cancellation
        self._scrape_cancelled = threading.Event()

        # OTA update state
        self._update_available = False
        self._update_version: Optional[str] = None
        self._update_url: Optional[str] = None

        # GUI
        self.gui: Optional[GUI] = None

        logger.log_info(f"Artie Scraper v{VERSION} initialized")

    def start(self, config_file: str) -> None:
        """
        Start the application with the given configuration file.

        Args:
            config_file: Path to the configuration file
        """
        try:
            # Load configuration
            self.config = self.config_manager.load_config(config_file)
            self.config_manager.setup_logging()

            # Validate API credentials early - fail fast if invalid
            logger.log_info("Validating API credentials before starting application...")
            try:
                self.config_manager.validate_credentials()
                logger.log_info("API credentials validated successfully")
            except exceptions.ConfigurationError as e:
                logger.log_error(f"API credential validation failed: {e}")
                logger.log_warning(
                    "Continuing despite invalid credentials - application may not function properly"
                )

            # Initialize managers
            self.rom_manager = RomManager(self.config.roms_path)

            # Validate configuration
            self.config_manager.validate_paths()

            # Validate mask settings
            self.config_manager.validate_mask_settings()

            # Initialize GUI
            self._initialize_gui()

            # Get user thread limits (now with proper error handling)
            self._configure_user_threads()

            # Check for updates (non-blocking, don't fail startup)
            self._check_for_updates()

            # Start main interface
            self._start_main_interface()

        except exceptions.ConfigurationError as e:
            logger.log_error(f"Configuration error: {e}")
            sys.exit(1)
        except Exception as e:
            logger.log_error(f"Failed to start application: {e}")
            sys.exit(1)

    def _initialize_gui(self) -> None:
        """Initialize GUI with proper error handling."""
        try:
            self.gui = GUI()

            # Apply color configuration
            if self.config and self.config.colors:
                color_map = {
                    "primary": "COLOR_PRIMARY",
                    "primary_dark": "COLOR_PRIMARY_DARK",
                    "secondary": "COLOR_SECONDARY",
                    "secondary_light": "COLOR_SECONDARY_LIGHT",
                    "secondary_dark": "COLOR_SECONDARY_DARK",
                    "accent_bar": "COLOR_ACCENT_BAR",
                    "muted": "COLOR_MUTED",
                    "header_bg": "COLOR_HEADER_BG",
                    "row_hover": "COLOR_ROW_HOVER",
                    "success": "COLOR_SUCCESS",
                }
                for key, attr in color_map.items():
                    if key in self.config.colors:
                        setattr(
                            self.gui,
                            attr,
                            self.config.colors[key],
                        )

        except Exception as e:
            logger.log_error(f"Failed to initialize GUI: {e}")
            raise exceptions.ScraperError(f"GUI initialization failed: {e}")

    def _start_main_interface(self) -> None:
        """Start the main GUI interface."""
        try:
            self.gui.draw_start()
            self.gui.screen_reset()
            main_gui = self.gui.create_image()
            self.gui.draw_active(main_gui)
            self.load_emulators()
        except Exception as e:
            logger.log_error(f"Failed to start main interface: {e}")
            raise

    def _configure_user_threads(self) -> None:
        """Configure thread count based on user's API limits and server capacity with proper error handling."""
        try:
            user_info = get_user_data(
                self.config.dev_id,
                self.config.dev_password,
                self.config.username,
                self.config.password,
            )

            # Validate response structure
            if not user_info or "response" not in user_info:
                logger.log_error("Invalid API response when getting user thread limits")
                raise exceptions.ScraperError("Invalid API response structure")

            response = user_info.get("response", {})

            # Check for API errors
            if "erreur" in response:
                error_msg = response["erreur"]
                logger.log_error(
                    f"API error when getting user thread limits: {error_msg}"
                )
                raise exceptions.ScraperError(f"API error: {error_msg}")

            ssuser = response.get("ssuser", {})
            if not ssuser:
                logger.log_error("No user information in API response")
                raise exceptions.ScraperError("No user information returned by API")

            max_threads = int(ssuser.get("maxthreads", 10))
            user_level = ssuser.get("niveau", "Unknown")

            logger.log_info(
                f"User level: {user_level}, Max threads allowed: {max_threads}"
            )

            # Use configured thread count directly - no server optimization
            self.config.threads = min(self.config.threads, max_threads)
            logger.log_info(
                f"Using configured thread count: {self.config.threads} threads"
            )

            logger.log_info(
                f"Final thread configuration: {self.config.threads} threads for scraping"
            )

        except exceptions.ForbiddenError as e:
            logger.log_error(f"API access forbidden when configuring threads: {e}")
            logger.log_error("This indicates invalid or expired credentials")
            raise exceptions.ConfigurationError(
                "Invalid API credentials - access forbidden"
            )

        except exceptions.RateLimitError as e:
            logger.log_error(f"API rate limit exceeded when configuring threads: {e}")
            logger.log_error("Please reduce thread count or wait before retrying")
            raise exceptions.ConfigurationError(
                "API rate limit exceeded during startup"
            )

        except exceptions.NetworkError as e:
            logger.log_warning(f"Network error when getting user thread limits: {e}")
            logger.log_warning(
                "Using configured thread count, but API limits may not be enforced"
            )
            # Don't fail startup for network errors, but warn user

        except exceptions.ScraperError as e:
            logger.log_error(f"API error when getting user thread limits: {e}")
            logger.log_warning("Using default thread configuration due to API issues")
            logger.log_info(
                f"Using default thread configuration: {self.config.threads} threads"
            )

        except Exception as e:
            logger.log_error(f"Unexpected error when configuring threads: {e}")
            logger.log_warning(
                "Using default thread configuration due to unexpected error"
            )
            logger.log_info(
                f"Using default thread configuration: {self.config.threads} threads"
            )

    def _check_for_updates(self) -> None:
        """Check for OTA updates on startup (non-blocking)."""

        def _check():
            try:
                available, version, url = check_for_update(VERSION)
                if available:
                    self._update_available = True
                    self._update_version = version
                    self._update_url = url
                    logger.log_info(f"Update available: v{version}")
            except Exception as e:
                logger.log_warning(f"Update check failed: {e}")

        threading.Thread(target=_check, daemon=True).start()

    def _apply_update(self) -> None:
        """Download and apply an OTA update."""
        if not self._update_url:
            self.gui.draw_log("No download URL available for update")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
            return

        self.gui.draw_log(f"Downloading v{self._update_version}...")
        self.gui.draw_paint()

        success = download_and_apply_update(self._update_url)
        if success:
            self.gui.draw_log(f"Updated to v{self._update_version}! Restarting...")
            self.gui.draw_paint()
            time.sleep(1)
            self.gui.draw_end()
            sys.exit(42)  # Signal mux_launch.sh to restart
        else:
            self.gui.draw_log("Update failed. Check logs for details.")
        self.gui.draw_paint()
        time.sleep(self.LOG_WAIT * 2)
        self.skip_input_check = True

    def _backup_catalogue(self) -> None:
        """Backup catalogue data to SD2."""
        self.gui.draw_log("Backing up to SD2...")
        self.gui.draw_paint()

        try:
            systems = list(self.config.systems_mapping.values())
            copied, skipped, errors = backup_catalogue(systems)
            err_str = f", {errors} errors" if errors else ""
            self.gui.draw_log(
                f"Backup done: {copied} copied, {skipped} unchanged{err_str}"
            )
        except FileNotFoundError as e:
            self.gui.draw_log(str(e))
        except Exception as e:
            logger.log_error(f"Backup failed: {e}")
            self.gui.draw_log(f"Backup failed: {str(e)[:40]}")

        self.gui.draw_paint()
        time.sleep(self.LOG_WAIT * 2)
        self.skip_input_check = True

    def update(self) -> None:
        """Main update loop with atomic transition handling and proper state management."""
        try:
            # ATOMIC TRANSITION HANDLING: Check for pending transitions FIRST
            if self.pending_transition:
                self._handle_pending_transition()
                return  # Skip normal processing during transition

            self._handle_input_state()

            if input.key_pressed("MENUF"):
                self._cleanup_and_exit()

            if self.current_window == "emulators":
                self.load_emulators()
            elif self.current_window == "roms":
                self.load_roms()
            else:
                logger.log_error(
                    f"Unknown current_window state: '{self.current_window}'"
                )

        except Exception as e:
            logger.log_error(f"Error in update loop: {e}")
            self._show_error_and_exit(f"Application error: {e}")

    def _handle_pending_transition(self) -> None:
        """Handle pending transition atomically with single paint operation."""
        if not self.transition_data:
            logger.log_error(
                "No transition data available, clearing pending transition"
            )
            self.pending_transition = False
            return

        try:
            # ATOMIC STATE CHANGE: Change state and cache data in one operation
            self.current_window = "roms"
            self.cached_roms_data = self.transition_data
            self.cached_system = self.transition_target_system
            self.roms_selected_position = 0  # Reset ROM selection position

            # SINGLE PAINT OPERATION: Render ROM interface directly
            self._render_roms_interface(self.transition_data)

            # Clear transition state
            self.pending_transition = False
            self.transition_data = None
            self.transition_target_system = ""

            # Ensure input is properly reset after transition
            self.skip_input_check = True

        except Exception as e:
            logger.log_error(f"Error during atomic transition: {e}")
            # On error, revert to emulator view and clear transition state
            self.current_window = "emulators"
            self.pending_transition = False
            self.transition_data = None
            self.transition_target_system = ""
            self.skip_input_check = True

    def _handle_input_state(self) -> None:
        """Handle input state management with simple full reset."""
        if self.skip_input_check:
            input.reset_input()
            self.skip_input_check = False
        else:
            input.check_input()

    def _cleanup_and_exit(self) -> None:
        """Clean up resources and exit application."""
        try:
            # PERFORMANCE: Save all caches to disk for persistence
            logger.log_info("PERFORMANCE: Saving caches for next application run...")
            self.cache_manager.save_all_caches()

            # Show cache statistics (hash stats removed)
            stats = self.cache_manager.get_stats()
            logger.log_info(
                f"PERFORMANCE STATS: API cache hit rate: {stats.get('hit_rate_percent', 0):.1f}%"
            )
            logger.log_info(
                "PERFORMANCE STATS: Total cache entries: "
                f"{stats.get('memory_cache_size', 0) + stats.get('api_cache_size', 0)}"
            )

            logger.log_info("Application cleanup complete")

            # Cleanup network resources
            from scraper import cleanup_network_resources

            cleanup_network_resources()

            # Cleanup GUI
            if self.gui:
                self.gui.draw_end()

            logger.log_info("Application shutdown complete")
        except Exception as e:
            logger.log_warning(f"Error during cleanup: {e}")
        finally:
            sys.exit(0)

    def _show_error_and_exit(self, message: str) -> None:
        """Show error message and exit application."""
        logger.log_error(message)
        if self.gui:
            self.gui.draw_log(message)
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)
        sys.exit(1)

    def load_emulators(self) -> None:
        """Load and display emulator selection screen with optimized rendering."""
        try:
            available_systems = self.rom_manager.get_available_systems(
                self.config.systems_mapping
            )

            # Handle input first
            if available_systems:
                self._handle_emulator_input(available_systems)

            # Create complete emulator interface using double-buffering
            self._render_complete_emulator_interface(available_systems)

        except Exception as e:
            logger.log_error(f"Error in load_emulators: {e}")
            self._show_error_and_exit(f"Failed to load emulators: {e}")

    def _render_complete_emulator_interface(self, available_systems: List[str]) -> None:
        """Render complete emulator interface with double-buffering to prevent flashing."""
        # Create new image buffer for complete interface
        screen_image = self.gui.create_image()
        self.gui.draw_active(screen_image)

        # Header bar
        self.gui.draw_rectangle_r([0, 0, 640, 36], 0, fill=self.gui.COLOR_HEADER_BG)
        self.gui.draw_text(
            (20, 18),
            "ARTIE SCRAPER",
            font=18,
            color=self.gui.COLOR_PRIMARY,
            anchor="lm",
        )
        # Version badge
        self.gui.draw_rectangle_r(
            [160, 8, 220, 28], 10, fill=self.gui.COLOR_SECONDARY_LIGHT
        )
        self.gui.draw_text(
            (190, 18), f"v{VERSION}", font=11, color=self.gui.COLOR_MUTED, anchor="mm"
        )

        # Update available indicator
        if self._update_available:
            self.gui.draw_rectangle_r(
                [226, 8, 330, 28], 10, fill=self.gui.COLOR_SUCCESS
            )
            self.gui.draw_text(
                (278, 18),
                f"v{self._update_version} available",
                font=10,
                color=self.gui.COLOR_WHITE,
                anchor="mm",
            )

        # Content area
        self.gui.draw_rectangle_r(
            [10, 42, 630, 438], 10, fill=self.gui.COLOR_SECONDARY_DARK
        )

        if available_systems:
            self._draw_available_systems(available_systems)
            # Page indicator
            total_pages = (len(available_systems) + self.max_elem - 1) // self.max_elem
            current_page = (self.selected_position // self.max_elem) + 1
            self.gui.draw_text(
                (620, 18),
                f"{current_page}/{total_pages}",
                font=11,
                color=self.gui.COLOR_MUTED,
                anchor="rm",
            )
        else:
            self._draw_no_emulators_message()

        # Separator line above controls
        self.gui.draw_line(
            (10, 443), (630, 443), fill=self.gui.COLOR_SECONDARY_LIGHT, width=1
        )

        self._draw_emulator_controls()

        # Paint complete interface in single operation
        self.gui.draw_paint()

    def _draw_available_systems(self, available_systems: List[str]) -> None:
        """Draw the list of available systems with pagination."""
        start_idx = (self.selected_position // self.max_elem) * self.max_elem
        end_idx = start_idx + self.max_elem

        for i, system in enumerate(available_systems[start_idx:end_idx]):
            is_selected = i == (self.selected_position % self.max_elem)
            self._draw_system_row(system, i, is_selected)

    def _draw_system_row(self, system: str, index: int, selected: bool) -> None:
        """Draw a single system row with accent bar and optional logo."""
        y_pos = 50 + (index * 35)

        # Row background
        row_fill = (
            self.gui.COLOR_ROW_HOVER if selected else self.gui.COLOR_SECONDARY_DARK
        )
        self.gui.draw_rectangle_r(
            [20, y_pos, 620, y_pos + 32],
            6,
            fill=row_fill,
        )

        # Left accent bar for selected row
        if selected:
            self.gui.draw_rectangle_r(
                [20, y_pos, 24, y_pos + 32],
                2,
                fill=self.gui.COLOR_ACCENT_BAR,
            )

        # Try to show system logo if enabled
        LOGO_AREA_W = 170  # Fixed width reserved for logos
        show_logos = (
            self.config and self.config.show_logos and self.config.systems_logo_path
        )
        if show_logos:
            logo_path = f"{self.config.systems_logo_path}/" f"{system.upper()}.png"
            logo = self.gui.load_logo(logo_path, max_height=20)
            if logo:
                max_logo_w = LOGO_AREA_W - 10
                logo_y = y_pos + (32 - logo.height) // 2
                self.gui.draw_image_at(
                    (30, logo_y),
                    logo,
                    max_logo_w,
                    20,
                )

        # Text always starts at a fixed column
        text_x = 30 + LOGO_AREA_W if show_logos else 30

        self.gui.draw_text(
            (text_x, y_pos + 16),
            system,
            font=14 if selected else 13,
            color=(self.gui.COLOR_WHITE if selected else self.gui.COLOR_MUTED),
            anchor="lm",
        )

    def _draw_no_emulators_message(self) -> None:
        """Draw message when no emulators are found."""
        self.gui.draw_text(
            (320, 220),
            "No Emulators Found",
            font=18,
            color=self.gui.COLOR_MUTED,
            anchor="mm",
        )
        self.gui.draw_text(
            (320, 250),
            f"Check path: {self.config.roms_path}",
            font=11,
            color=self.gui.COLOR_MUTED,
            anchor="mm",
        )

    def _draw_emulator_controls(self) -> None:
        """Draw control buttons for emulator screen."""
        y = 453
        self._draw_button_pill((15, y), "ST", "All")
        self._draw_button_pill((95, y), "A", "Select")
        self._draw_button_pill((200, y), "X", "Delete")
        self._draw_button_pill((300, y), "SE", "Backup")
        if self._update_available:
            self._draw_button_pill((420, y), "Y", "Update")
        self._draw_button_pill((540, y), "M", "Exit")

    def _handle_emulator_input(self, available_systems: List[str]) -> None:
        """Handle input for emulator selection screen."""
        if self.current_window != "emulators":
            return

        if input.key_pressed("DY"):
            self._handle_vertical_navigation(len(available_systems))
        elif input.key_pressed("A"):
            self._select_system(available_systems)
        elif input.key_pressed("X"):
            self._delete_system_media(available_systems)
        elif input.key_pressed("L1"):
            self._handle_page_navigation(len(available_systems), -self.max_elem)
        elif input.key_pressed("R1"):
            self._handle_page_navigation(len(available_systems), self.max_elem)
        elif input.key_pressed("L2"):
            self._handle_page_navigation(len(available_systems), -LARGE_NAVIGATION_STEP)
        elif input.key_pressed("R2"):
            self._handle_page_navigation(len(available_systems), LARGE_NAVIGATION_STEP)
        elif input.key_pressed("START"):
            self._scrape_all_systems(available_systems)
        elif input.key_pressed("SELECT"):
            self._backup_catalogue()
        elif input.key_pressed("Y"):
            if self._update_available:
                self._apply_update()

    def _handle_vertical_navigation(self, max_items: int) -> None:
        """Handle up/down navigation."""
        if input.current_value == 1 and self.selected_position < max_items - 1:
            self.selected_position += 1
        elif input.current_value == -1 and self.selected_position > 0:
            self.selected_position -= 1

    def _handle_page_navigation(self, max_items: int, step: int) -> None:
        """Handle page-based navigation for emulator selection."""
        if step > 0 and self.selected_position < max_items - 1:
            self.selected_position = min(max_items - 1, self.selected_position + step)
        elif step < 0 and self.selected_position > 0:
            self.selected_position = max(0, self.selected_position + step)

    def _handle_roms_page_navigation(self, max_items: int, step: int) -> None:
        """Handle page-based navigation for ROM selection."""
        if step > 0 and self.roms_selected_position < max_items - 1:
            self.roms_selected_position = min(
                max_items - 1, self.roms_selected_position + step
            )
        elif step < 0 and self.roms_selected_position > 0:
            self.roms_selected_position = max(0, self.roms_selected_position + step)

    def _clear_rom_cache(self) -> None:
        """Clear the ROM data cache and image cache."""
        self.cached_roms_data = None
        self.cached_system = None
        if self.gui:
            self.gui.clear_image_cache()

    def _select_system(self, available_systems: List[str]) -> None:
        """Select a system and prepare for atomic transition to ROM view."""
        new_system = available_systems[self.selected_position]

        # Clear cache if system is changing
        if self.selected_system != new_system:
            self._clear_rom_cache()

        self.selected_system = new_system

        try:
            # Prepare ROM data synchronously - this is the blocking operation
            roms_data = self._prepare_roms_data()

            if roms_data is None:
                # ROM loading failed - show error and stay in emulator view
                loading_image = self.gui.create_image()
                self.gui.draw_active(loading_image)
                self.gui.draw_log(f"Failed to load ROMs for {self.selected_system}")
                self.gui.draw_paint()
                time.sleep(self.LOG_WAIT)
                self.skip_input_check = True
                return

            # ATOMIC TRANSITION: ROM data is prepared, now set up for immediate transition
            self.pending_transition = True
            self.transition_data = roms_data
            self.transition_target_system = self.selected_system

        except Exception as e:
            logger.log_error(
                f"Exception in ROM transition preparation for '{self.selected_system}': {e}"
            )
            # On error, show error message and stay in emulator view
            loading_image = self.gui.create_image()
            self.gui.draw_active(loading_image)
            self.gui.draw_log(f"Error loading ROMs: {str(e)[:50]}...")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)

        # Use simple full reset to eliminate race conditions
        self.skip_input_check = True

    def _delete_system_media(self, available_systems: List[str]) -> None:
        """Delete all media for selected system."""
        self.selected_system = available_systems[self.selected_position]
        system_config = self.config.systems_mapping.get(self.selected_system)

        if system_config:
            self.gui.draw_log(f"Deleting all {self.selected_system} media...")
            self.gui.draw_paint()

            enabled_media_types = self.config_manager.get_enabled_media_types()
            self.rom_manager.delete_system_media(
                self.selected_system, system_config, enabled_media_types
            )
            # Clear cache after deleting system media
            self._clear_rom_cache()

            self.gui.draw_log(f"Deleted all {self.selected_system} media")
        else:
            self.gui.draw_log(f"Unknown system: {self.selected_system}")

        self.gui.draw_paint()
        self.skip_input_check = True
        time.sleep(self.LOG_WAIT)

    def _show_overlay(self, message: str) -> None:
        """Draw a message on a fresh screen to prevent popup stacking."""
        screen = self.gui.create_image()
        self.gui.draw_active(screen)
        self.gui.draw_log(message)
        self.gui.draw_paint()

    def _scrape_all_systems(self, available_systems: List[str]) -> None:
        """Scrape all ROMs across all available systems sequentially."""
        if not available_systems:
            return

        total_systems = len(available_systems)
        self._show_overlay(f"Scraping all {total_systems} systems...")

        systems_completed = 0
        systems_skipped = 0

        for i, system_name in enumerate(available_systems):
            # Check for cancellation between systems
            if input.check_input_nonblocking() and input.key_pressed("B"):
                self._show_overlay(
                    f"Cancelled after {systems_completed}/{total_systems} systems."
                )
                time.sleep(2)
                break

            self.selected_system = system_name
            self._clear_rom_cache()

            self._show_overlay(f"[{i + 1}/{total_systems}] Loading {system_name}...")

            roms_data = self._prepare_roms_data()
            if roms_data is None or not roms_data.roms_to_scrape:
                logger.log_info(f"Skipping {system_name}: no ROMs to scrape")
                systems_skipped += 1
                continue

            self._show_overlay(
                f"[{i + 1}/{total_systems}] Scraping {system_name} "
                f"({len(roms_data.roms_to_scrape)} ROMs)..."
            )

            self._scrape_all_roms(roms_data)

            if self._scrape_cancelled.is_set():
                systems_completed += 1
                self._show_overlay(
                    f"Cancelled during {system_name}. "
                    f"Completed {systems_completed}/{total_systems} systems."
                )
                time.sleep(2)
                break

            systems_completed += 1

        else:
            self._show_overlay(
                f"All systems done! {systems_completed} scraped, "
                f"{systems_skipped} skipped."
            )
            time.sleep(2)

        self._clear_rom_cache()
        self.skip_input_check = True

    def load_roms(self) -> None:
        """Load and display ROM selection screen with optimized structure and caching."""
        try:
            # Validate we should be in ROM view
            if self.current_window != "roms":
                return

            # Check if we can use cached ROM data
            if (
                self.cached_system == self.selected_system
                and self.cached_roms_data is not None
            ):
                roms_data = self.cached_roms_data
            else:
                roms_data = self._prepare_roms_data()

                # Cache the prepared data if successful
                if roms_data is not None:
                    self.cached_roms_data = roms_data
                    self.cached_system = self.selected_system

            if roms_data is None:
                self._exit_roms_menu()
                return

            # Handle input
            if self._handle_roms_input(roms_data):
                self._exit_roms_menu()
                return

            # Render interface
            self._render_roms_interface(roms_data)

        except Exception as e:
            logger.log_error(f"Error in load_roms: {e}")
            # On error, revert to emulator view
            self.current_window = "emulators"
            self.gui.draw_log(f"ROM loading error: {str(e)[:50]}...")
            self.gui.draw_paint()
            time.sleep(self.LOG_WAIT)

    def _prepare_roms_data(self) -> Optional[RomsData]:
        """Prepare all ROM-related data for the interface."""
        try:
            # Get ROM list
            roms_list = self.rom_manager.get_roms(self.selected_system)
            if not roms_list:
                self.gui.draw_log(f"No roms found in {self.selected_system}...")
                self.gui.draw_paint()
                time.sleep(self.LOG_WAIT)
                self.gui.draw_clear()
                return None

            # Get system configuration
            system_config = self.config.systems_mapping.get(self.selected_system)
            if not system_config:
                self.gui.draw_log("System is unknown...")
                self.gui.draw_paint()
                time.sleep(self.LOG_WAIT)
                self.gui.draw_clear()
                return None

            # Get ROMs missing different media types
            roms_without_box = self._get_roms_missing_media(
                roms_list, system_config, "box", self.config.box_enabled
            )
            roms_without_preview = self._get_roms_missing_media(
                roms_list, system_config, "preview", self.config.preview_enabled
            )
            roms_without_synopsis = self._get_roms_missing_media(
                roms_list, system_config, "synopsis", self.config.synopsis_enabled
            )

            # Determine ROMs to scrape
            roms_to_scrape = self._determine_roms_to_scrape(
                roms_list, roms_without_box, roms_without_preview, roms_without_synopsis
            )

            if not roms_to_scrape and not self.config.show_scraped_roms:
                self.gui.draw_log("No roms with missing media found...")
                self.gui.draw_paint()
                time.sleep(self.LOG_WAIT)
                self.gui.draw_clear()
                return None

            return RomsData(
                roms_list=roms_list,
                roms_to_scrape=roms_to_scrape,
                roms_without_box=roms_without_box,
                roms_without_preview=roms_without_preview,
                roms_without_synopsis=roms_without_synopsis,
                system_config=system_config,
                system_id=system_config["id"],
            )

        except Exception as e:
            logger.log_error(f"Exception in _prepare_roms_data(): {e}")
            return None

    def _get_roms_missing_media(
        self, roms_list: List[Rom], system_config: dict, media_type: str, enabled: bool
    ) -> List[Rom]:
        """Get ROMs missing a specific media type."""
        if not enabled:
            return []

        media_path = Path(system_config.get(media_type, ""))

        if media_type == "synopsis":
            get_files_func = get_txt_files_without_extension
        else:
            get_files_func = get_image_files_without_extension

        return self.rom_manager.get_roms_without_files(
            enabled, media_path, roms_list, get_files_func
        )

    def _determine_roms_to_scrape(
        self,
        roms_list: List[Rom],
        roms_without_box: List[Rom],
        roms_without_preview: List[Rom],
        roms_without_synopsis: List[Rom],
    ) -> List[Rom]:
        """Determine which ROMs need to be scraped."""
        if self.config.show_scraped_roms:
            return roms_list

        # Combine all ROMs missing any media type
        missing_roms = (
            set(roms_without_box)
            | set(roms_without_preview)
            | set(roms_without_synopsis)
        )
        return sorted(list(missing_roms), key=lambda rom: rom.name)

    def _handle_roms_input(self, roms_data: RomsData) -> bool:
        """
        Handle input for ROM selection screen.

        Returns:
            True if should exit ROM menu, False otherwise
        """
        if self.current_window != "roms":
            return False

        if input.key_pressed("DY"):
            # Use roms_selected_position for ROM navigation, not selected_position
            if (
                input.current_value == 1
                and self.roms_selected_position < len(roms_data.roms_to_scrape) - 1
            ):
                self.roms_selected_position += 1
            elif input.current_value == -1 and self.roms_selected_position > 0:
                self.roms_selected_position -= 1
        elif input.key_pressed("A"):
            self._scrape_single_rom(roms_data)
        elif input.key_pressed("X"):
            self._delete_single_rom_media(roms_data)
        elif input.key_pressed("Y"):
            self._show_rom_detail(roms_data)
        elif input.key_pressed("B"):
            return True  # Exit to emulator menu
        elif input.key_pressed("START"):
            self._scrape_all_roms(roms_data)
        elif input.key_pressed("L1"):
            self._handle_roms_page_navigation(
                len(roms_data.roms_to_scrape), -self.max_elem
            )
        elif input.key_pressed("R1"):
            self._handle_roms_page_navigation(
                len(roms_data.roms_to_scrape), self.max_elem
            )
        elif input.key_pressed("L2"):
            self._handle_roms_page_navigation(
                len(roms_data.roms_to_scrape), -LARGE_NAVIGATION_STEP
            )
        elif input.key_pressed("R2"):
            self._handle_roms_page_navigation(
                len(roms_data.roms_to_scrape), LARGE_NAVIGATION_STEP
            )

        return False

    def _scrape_single_rom(self, roms_data: RomsData) -> None:
        """Scrape a single ROM with proper error handling."""
        if not roms_data.roms_to_scrape:
            return

        self._scrape_cancelled.clear()
        rom = roms_data.roms_to_scrape[self.roms_selected_position]
        self.gui.draw_log(f"Scraping {rom.name}...")
        self.gui.draw_paint()

        try:
            self._process_rom(rom, roms_data)
            self.gui.draw_log(f"Completed scraping {rom.name}")
            # Clear cache after scraping to ensure fresh data on next load
            self._clear_rom_cache()
        except exceptions.RateLimitError as e:
            logger.log_error(f"Rate limit error for ROM {rom.name}: {e}")
            self.gui.draw_log("API Rate limit exceeded. Check logs for details.")
        except exceptions.ForbiddenError as e:
            logger.log_error(f"API access forbidden for ROM {rom.name}: {e}")
            self.gui.draw_log("API access forbidden. Check your credentials.")
        except Exception as e:
            logger.log_error(f"Error scraping ROM {rom.name}: {e}")
            self.gui.draw_log(f"Error scraping {rom.name}: {str(e)[:50]}...")

        self.gui.draw_paint()
        time.sleep(self.LOG_WAIT)
        self.skip_input_check = True

    def _delete_single_rom_media(self, roms_data: RomsData) -> None:
        """Delete media for a single ROM."""
        if not roms_data.roms_to_scrape:
            return

        rom = roms_data.roms_to_scrape[self.roms_selected_position]
        enabled_media_types = self.config_manager.get_enabled_media_types()

        self.rom_manager.delete_rom_media(
            rom, roms_data.system_config, enabled_media_types
        )

        # Clear cache after deleting media to ensure fresh data on next load
        self._clear_rom_cache()

        self.gui.draw_log(f"Deleted media for {rom.name}")
        self.gui.draw_paint()
        time.sleep(self.LOG_WAIT)
        self.skip_input_check = True

    def _check_scrape_cancelled(self) -> bool:
        """Poll for B button press to cancel scraping (non-blocking)."""
        if input.check_input_nonblocking() and input.key_pressed("B"):
            self._scrape_cancelled.set()
            return True
        return self._scrape_cancelled.is_set()

    def _scrape_all_roms(self, roms_data: RomsData) -> None:
        """Scrape all ROMs using thread pool with performance monitoring and progress indicators."""
        if not roms_data.roms_to_scrape:
            return

        total_roms = len(roms_data.roms_to_scrape)
        self._scrape_cancelled.clear()

        # Keep a persistent input fd open so B presses are queued by the
        # kernel between polls (evdev queues events per open fd).
        input.start_nonblocking()

        cache_stats = self.cache_manager.get_stats()

        self.gui.draw_log(f"Starting batch scraping of {total_roms} ROMs...")
        self.gui.draw_log(
            f"API cache: {cache_stats.get('api_cache_size', 0)} entries, "
            f"{cache_stats.get('hit_rate_percent', 0):.1f}% hit rate"
        )
        self.gui.draw_paint()

        completed = 0
        failed = 0
        cancelled = False
        quota_exceeded = False
        start_time = time.time()

        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.config.threads
            ) as executor:
                # Submit all ROM processing tasks
                future_to_rom = {
                    executor.submit(
                        self._process_rom_with_monitoring, rom, roms_data
                    ): rom
                    for rom in roms_data.roms_to_scrape
                }

                # Process completed tasks with cancellation polling
                pending = set(future_to_rom.keys())
                while pending:
                    # Check for user cancellation
                    if self._check_scrape_cancelled():
                        cancelled = True
                        logger.log_info("Batch scraping cancelled by user")
                        self.gui.draw_log("Cancelling... waiting for active threads")
                        self.gui.draw_paint()
                        for f in pending:
                            f.cancel()
                        break

                    # Wait for next completion with short timeout
                    # so we can poll for cancellation regularly
                    done, pending = concurrent.futures.wait(
                        pending,
                        timeout=0.3,
                        return_when=concurrent.futures.FIRST_COMPLETED,
                    )

                    for future in done:
                        rom = future_to_rom[future]
                        try:
                            result = future.result()
                            if result.get("success"):
                                completed += 1
                            else:
                                failed += 1
                        except exceptions.RateLimitError as e:
                            logger.log_error(
                                f"Rate limit error during batch scraping: {e}"
                            )
                            quota_exceeded = True
                            for rf in pending:
                                rf.cancel()
                            pending = set()
                            break
                        except exceptions.ForbiddenError as e:
                            logger.log_error(
                                f"API access forbidden for ROM {rom.name}: {e}"
                            )
                            failed += 1
                        except Exception as e:
                            logger.log_error(f"Error scraping ROM {rom.name}: {e}")
                            failed += 1

                    if quota_exceeded:
                        break

                    # Show progress after processing completed batch
                    processed = completed + failed
                    if processed > 0:
                        elapsed_time = time.time() - start_time
                        avg_time_per_rom = elapsed_time / processed
                        estimated_remaining = avg_time_per_rom * (
                            total_roms - processed
                        )
                        progress_msg = (
                            f"{processed}/{total_roms} ROMs "
                            f"- ETA: {estimated_remaining/60:.1f}min "
                            f"[B] Cancel"
                        )
                        logger.log_info(progress_msg)
                        progress = processed / total_roms
                        self.gui.draw_log_with_progress(
                            progress_msg,
                            progress,
                        )
                        self.gui.draw_paint()

            total_time = time.time() - start_time
            performance_summary = [
                "PERFORMANCE SUMMARY:",
                f"• Total time: {total_time/60:.1f} minutes",
                (
                    f"• Average time per ROM: {total_time/completed:.1f}s"
                    if completed > 0
                    else "• No ROMs completed"
                ),
            ]

            for msg in performance_summary:
                logger.log_info(msg)

            # Clear cache after batch scraping to ensure fresh data on next load
            if completed > 0:
                self._clear_rom_cache()

            # Build summary string
            time_str = (
                f"{total_time:.0f}s" if total_time < 60 else f"{total_time/60:.1f}m"
            )
            fail_str = f", {failed} failed" if failed else ""

            if cancelled:
                self._show_overlay(
                    f"Cancelled: {completed}/{total_roms} scraped{fail_str} in {time_str}"
                )
            elif quota_exceeded:
                self._show_overlay(
                    f"Quota hit: {completed} scraped{fail_str} in {time_str}"
                )
            else:
                self._show_overlay(
                    f"Done: {completed}/{total_roms} scraped{fail_str} in {time_str}"
                )

        except Exception as e:
            logger.log_error(f"Error in batch scraping: {e}")
            self._show_overlay(f"Batch scraping error: {str(e)[:50]}...")

        input.stop_nonblocking()
        time.sleep(1)
        self.skip_input_check = True

    def _process_rom(self, rom: Rom, roms_data: RomsData) -> Tuple[Any, Any, Any, str]:
        """Process a single ROM (scrape and save media)."""
        scraped_box, scraped_preview, scraped_synopsis, scraped_metadata = (
            self._scrape_rom_media(rom, roms_data.system_id)
        )

        # Apply mask processing to images before saving
        image_processor = get_image_processor()

        # Save scraped media with optional mask processing
        if scraped_box:
            processed_box = image_processor.process_image_with_mask(
                scraped_box, self.config.content.get("box", {})
            )
            destination = roms_data.box_dir / f"{rom.name}.png"
            self._save_file_to_disk(processed_box, destination)

        if scraped_preview:
            processed_preview = image_processor.process_image_with_mask(
                scraped_preview, self.config.content.get("preview", {})
            )
            destination = roms_data.preview_dir / f"{rom.name}.png"
            self._save_file_to_disk(processed_preview, destination)

        if scraped_synopsis or scraped_metadata:
            # Combine synopsis text with metadata
            parts = []
            if scraped_synopsis:
                parts.append(scraped_synopsis)
            if scraped_metadata:
                parts.append("")  # blank line separator
                for key, value in scraped_metadata.items():
                    parts.append(f"{key}: {value}")
            text = "\n".join(parts)
            destination = roms_data.synopsis_dir / f"{rom.name}.txt"
            self._save_file_to_disk(text.encode("utf-8"), destination)

        return scraped_box, scraped_preview, scraped_synopsis, rom.name

    def _process_rom_with_monitoring(self, rom: Rom, roms_data: RomsData) -> dict:
        """Process a single ROM with performance monitoring."""
        if self._scrape_cancelled.is_set():
            return {"success": False, "rom_name": rom.name, "skipped": True}

        start_time = time.time()

        try:
            scraped_box, scraped_preview, scraped_synopsis, rom_name = (
                self._process_rom(rom, roms_data)
            )

            processing_time = time.time() - start_time

            return {
                "success": True,
                "rom_name": rom_name,
                "processing_time": processing_time,
                "scraped_box": scraped_box is not None,
                "scraped_preview": scraped_preview is not None,
                "scraped_synopsis": scraped_synopsis is not None,
            }

        except _ScrapeCancelledError:
            return {"success": False, "rom_name": rom.name, "skipped": True}
        except (exceptions.ForbiddenError, exceptions.RateLimitError) as e:
            raise e
        except Exception as e:
            processing_time = time.time() - start_time
            logger.log_error(f"Error processing ROM {rom.name}: {e}")

            return {
                "success": False,
                "rom_name": rom.name,
                "processing_time": processing_time,
                "error": str(e),
            }

    def _scrape_rom_media(
        self, rom: Rom, system_id: str
    ) -> Tuple[Any, Any, Any, Optional[dict]]:
        """Scrape media for a ROM. Raises _ScrapeCancelledError if cancelled."""
        scraped_box = scraped_preview = scraped_synopsis = None
        scraped_metadata = None

        if self._scrape_cancelled.is_set():
            raise _ScrapeCancelledError()

        game = get_game_data(
            system_id,
            str(rom.path),
            self.config.dev_id,
            self.config.dev_password,
            self.config.username,
            self.config.password,
        )

        if game:
            content = self.config.content
            if self._scrape_cancelled.is_set():
                raise _ScrapeCancelledError()
            if self.config.box_enabled:
                scraped_box = fetch_box(game, content)
            if self._scrape_cancelled.is_set():
                raise _ScrapeCancelledError()
            if self.config.preview_enabled:
                scraped_preview = fetch_preview(game, content)
            if self._scrape_cancelled.is_set():
                raise _ScrapeCancelledError()
            if self.config.synopsis_enabled:
                scraped_synopsis = fetch_synopsis(game, content)
                scraped_metadata = fetch_metadata(game, content)

        return scraped_box, scraped_preview, scraped_synopsis, scraped_metadata

    def _save_file_to_disk(self, data: bytes, destination: Path) -> bool:
        """Save data to disk with comprehensive error handling."""
        try:
            check_destination(str(destination))
            destination.write_bytes(data)
            logger.log_debug(f"Saved file to {destination}")
            return True
        except Exception as e:
            raise exceptions.MediaProcessingError(
                f"Error saving file {destination}: {e}"
            )

    def _render_roms_interface(self, roms_data: RomsData) -> None:
        """Render the ROM selection interface with optimized double-buffering."""
        interface_image = self.gui.create_image()
        self.gui.draw_active(interface_image)

        # Header bar
        self.gui.draw_rectangle_r(
            [0, 0, 640, 36],
            0,
            fill=self.gui.COLOR_HEADER_BG,
        )

        # Draw header information
        self._draw_roms_header(roms_data)

        # Content area
        self.gui.draw_rectangle_r(
            [10, 42, 630, 438],
            10,
            fill=self.gui.COLOR_SECONDARY_DARK,
        )

        # Draw ROM list
        self._draw_roms_list(roms_data)

        # Separator line above controls
        self.gui.draw_line(
            (10, 443),
            (630, 443),
            fill=self.gui.COLOR_SECONDARY_LIGHT,
            width=1,
        )

        # Draw controls
        self._draw_roms_controls()

        # Paint complete interface in single operation
        self.gui.draw_paint()

    def _draw_roms_header(self, roms_data: RomsData) -> None:
        """Draw header with ROM statistics."""
        # System name
        self.gui.draw_text(
            (20, 18),
            self.selected_system.upper(),
            font=18,
            color=self.gui.COLOR_PRIMARY,
            anchor="lm",
        )

        # Total ROMs badge
        total = len(roms_data.roms_list)
        self.gui.draw_rectangle_r(
            [160, 8, 230, 28],
            10,
            fill=self.gui.COLOR_SECONDARY_LIGHT,
        )
        self.gui.draw_text(
            (195, 18),
            f"{total} ROMs",
            font=11,
            color=self.gui.COLOR_MUTED,
            anchor="mm",
        )

        # Missing media stats on the right
        stats = []
        if self.config.box_enabled and roms_data.roms_without_box:
            stats.append(f"B:{len(roms_data.roms_without_box)}")
        if self.config.preview_enabled and roms_data.roms_without_preview:
            stats.append(f"P:{len(roms_data.roms_without_preview)}")
        if self.config.synopsis_enabled and roms_data.roms_without_synopsis:
            stats.append(f"T:{len(roms_data.roms_without_synopsis)}")

        if stats:
            missing_text = "  ".join(stats)
            self.gui.draw_text(
                (620, 18),
                missing_text,
                font=11,
                color=self.gui.COLOR_MUTED,
                anchor="rm",
            )

        # Page indicator
        total_pages = max(
            1,
            (len(roms_data.roms_to_scrape) + self.max_elem - 1) // self.max_elem,
        )
        current_page = (self.roms_selected_position // self.max_elem) + 1
        self.gui.draw_text(
            (400, 18),
            f"{current_page}/{total_pages}",
            font=11,
            color=self.gui.COLOR_MUTED,
            anchor="mm",
        )

    def _draw_roms_list(self, roms_data: RomsData) -> None:
        """Draw the list of ROMs with pagination."""
        start_idx = (self.roms_selected_position // self.max_elem) * self.max_elem
        end_idx = start_idx + self.max_elem

        for i, rom in enumerate(roms_data.roms_to_scrape[start_idx:end_idx]):
            is_selected = i == (self.roms_selected_position % self.max_elem)
            self._draw_rom_row(rom, i, is_selected, roms_data)

    def _draw_rom_row(
        self, rom: Rom, index: int, selected: bool, roms_data: RomsData
    ) -> None:
        """Draw a single ROM row with status badges."""
        y_pos = 50 + (index * 35)

        # Determine what media already exists
        has_box = self.config.box_enabled and rom not in roms_data.roms_without_box
        has_preview = (
            self.config.preview_enabled and rom not in roms_data.roms_without_preview
        )
        has_text = (
            self.config.synopsis_enabled and rom not in roms_data.roms_without_synopsis
        )

        # Truncate ROM name if too long
        max_length = 45
        display_name = (
            rom.name[:max_length] + "..." if len(rom.name) > max_length else rom.name
        )

        # Row background
        row_fill = (
            self.gui.COLOR_ROW_HOVER if selected else self.gui.COLOR_SECONDARY_DARK
        )
        self.gui.draw_rectangle_r(
            [20, y_pos, 620, y_pos + 32],
            6,
            fill=row_fill,
        )

        # Left accent bar for selected
        if selected:
            self.gui.draw_rectangle_r(
                [20, y_pos, 24, y_pos + 32],
                2,
                fill=self.gui.COLOR_ACCENT_BAR,
            )

        # ROM name
        self.gui.draw_text(
            (30, y_pos + 16),
            display_name,
            font=14 if selected else 13,
            color=(self.gui.COLOR_WHITE if selected else self.gui.COLOR_MUTED),
            anchor="lm",
        )

        # Status badges (small colored dots/pills)
        badge_x = 615
        badges = []
        if self.config.box_enabled:
            badges.append(("B", has_box))
        if self.config.preview_enabled:
            badges.append(("P", has_preview))
        if self.config.synopsis_enabled:
            badges.append(("T", has_text))

        for label, has_it in reversed(badges):
            color = self.gui.COLOR_SUCCESS if has_it else self.gui.COLOR_SECONDARY_LIGHT
            self.gui.draw_rectangle_r(
                [badge_x - 18, y_pos + 8, badge_x, y_pos + 24],
                4,
                fill=color,
            )
            self.gui.draw_text(
                (badge_x - 9, y_pos + 16),
                label,
                font=10,
                color=self.gui.COLOR_WHITE if has_it else "#555555",
                anchor="mm",
            )
            badge_x -= 22

    def _draw_roms_controls(self) -> None:
        """Draw control buttons for ROM screen."""
        y = 453
        self._draw_button_pill((15, y), "ST", "All")
        self._draw_button_pill((95, y), "A", "Get")
        self._draw_button_pill((170, y), "X", "Del")
        self._draw_button_pill((245, y), "Y", "View")
        self._draw_button_pill((340, y), "B", "Back")
        self._draw_button_pill((440, y), "M", "Exit")

    def _draw_button_pill(self, pos: Tuple[int, int], button: str, text: str) -> None:
        """Draw a modern pill-shaped button with label."""
        # Button key circle/pill
        btn_w = max(22, len(button) * 11 + 8)
        self.gui.draw_rectangle_r(
            (pos[0], pos[1], pos[0] + btn_w, pos[1] + 22),
            11,
            fill=self.gui.COLOR_PRIMARY_DARK,
        )
        self.gui.draw_text(
            (pos[0] + btn_w // 2, pos[1] + 11),
            button,
            font=12,
            anchor="mm",
        )
        # Label text
        self.gui.draw_text(
            (pos[0] + btn_w + 5, pos[1] + 11),
            text,
            font=13,
            color=self.gui.COLOR_MUTED,
            anchor="lm",
        )

    def _show_rom_detail(self, roms_data: RomsData) -> None:
        """Show detailed view of selected ROM with scraped media previews."""
        if not roms_data.roms_to_scrape:
            return

        rom = roms_data.roms_to_scrape[self.roms_selected_position]

        has_box = self.config.box_enabled and rom not in roms_data.roms_without_box
        has_preview = (
            self.config.preview_enabled and rom not in roms_data.roms_without_preview
        )
        has_text = (
            self.config.synopsis_enabled and rom not in roms_data.roms_without_synopsis
        )

        self._render_rom_detail(rom, roms_data, has_box, has_preview, has_text)

        # Blocking input loop — wait for user action
        while True:
            input.check_input()
            if input.key_pressed("B") or input.key_pressed("MENUF"):
                break
            elif input.key_pressed("A"):
                self._scrape_single_rom(roms_data)
                # Refresh detail view after scraping
                self._clear_rom_cache()
                roms_data = self._prepare_roms_data()
                if roms_data is None:
                    break
                self.cached_roms_data = roms_data
                self.cached_system = self.selected_system
                has_box = (
                    self.config.box_enabled and rom not in roms_data.roms_without_box
                )
                has_preview = (
                    self.config.preview_enabled
                    and rom not in roms_data.roms_without_preview
                )
                has_text = (
                    self.config.synopsis_enabled
                    and rom not in roms_data.roms_without_synopsis
                )
                self._render_rom_detail(rom, roms_data, has_box, has_preview, has_text)

        self.skip_input_check = True

    def _render_rom_detail(
        self,
        rom: Rom,
        roms_data: RomsData,
        has_box: bool,
        has_preview: bool,
        has_text: bool,
    ) -> None:
        """Render the ROM detail screen."""
        interface_image = self.gui.create_image()
        self.gui.draw_active(interface_image)

        # Header bar
        self.gui.draw_rectangle_r([0, 0, 640, 36], 0, fill=self.gui.COLOR_HEADER_BG)
        display_name = rom.name[:50] + "..." if len(rom.name) > 50 else rom.name
        self.gui.draw_text(
            (20, 18),
            display_name,
            font=18,
            color=self.gui.COLOR_PRIMARY,
            anchor="lm",
        )

        # Status badges in header
        badge_x = 620
        badges = []
        if self.config.box_enabled:
            badges.append(("BOX", has_box))
        if self.config.preview_enabled:
            badges.append(("PRV", has_preview))
        if self.config.synopsis_enabled:
            badges.append(("TXT", has_text))
        for label, has_it in reversed(badges):
            color = self.gui.COLOR_SUCCESS if has_it else self.gui.COLOR_SECONDARY_LIGHT
            w = len(label) * 8 + 10
            self.gui.draw_rectangle_r([badge_x - w, 8, badge_x, 28], 10, fill=color)
            self.gui.draw_text(
                (badge_x - w // 2, 18),
                label,
                font=10,
                color=self.gui.COLOR_WHITE if has_it else "#555555",
                anchor="mm",
            )
            badge_x -= w + 6

        # Content area
        self.gui.draw_rectangle_r(
            [10, 42, 630, 438], 10, fill=self.gui.COLOR_SECONDARY_DARK
        )

        # Determine layout based on what's enabled
        show_box = self.config.box_enabled
        show_preview = self.config.preview_enabled
        img_y = 52
        img_max_h = 180
        synopsis_y = img_y + img_max_h + 25

        if show_box and show_preview:
            # Side by side: box left, preview right
            self._draw_detail_media(
                roms_data.box_dir,
                rom.name,
                has_box,
                "Box Art",
                20,
                img_y,
                285,
                img_max_h,
            )
            self._draw_detail_media(
                roms_data.preview_dir,
                rom.name,
                has_preview,
                "Preview",
                325,
                img_y,
                295,
                img_max_h,
            )
        elif show_box:
            # Box only, centered larger
            self._draw_detail_media(
                roms_data.box_dir,
                rom.name,
                has_box,
                "Box Art",
                120,
                img_y,
                400,
                img_max_h,
            )
        elif show_preview:
            # Preview only, centered larger
            self._draw_detail_media(
                roms_data.preview_dir,
                rom.name,
                has_preview,
                "Preview",
                80,
                img_y,
                480,
                img_max_h,
            )
        else:
            synopsis_y = img_y

        # Synopsis section
        if self.config.synopsis_enabled:
            self.gui.draw_text(
                (25, synopsis_y),
                "Synopsis",
                font=14,
                color=self.gui.COLOR_PRIMARY,
            )
            self.gui.draw_line(
                (25, synopsis_y + 18),
                (120, synopsis_y + 18),
                fill=self.gui.COLOR_PRIMARY_DARK,
                width=1,
            )
            if has_text:
                synopsis_path = roms_data.synopsis_dir / f"{rom.name}.txt"
                try:
                    text = synopsis_path.read_text(encoding="utf-8").strip()
                    self._draw_wrapped_text(text, 25, synopsis_y + 25, 590, max_lines=7)
                except Exception:
                    self.gui.draw_text(
                        (25, synopsis_y + 25),
                        "Error reading synopsis",
                        font=11,
                        color=self.gui.COLOR_MUTED,
                    )
            else:
                self.gui.draw_text(
                    (25, synopsis_y + 25),
                    "Not yet scraped",
                    font=11,
                    color=self.gui.COLOR_MUTED,
                )

        # Separator line above controls
        self.gui.draw_line(
            (10, 443), (630, 443), fill=self.gui.COLOR_SECONDARY_LIGHT, width=1
        )

        # Controls
        y = 453
        self._draw_button_pill((15, y), "A", "Get")
        self._draw_button_pill((110, y), "B", "Back")

        self.gui.draw_paint()

    def _draw_detail_media(
        self,
        media_dir: Path,
        rom_name: str,
        has_media: bool,
        label: str,
        x: int,
        y: int,
        max_w: int,
        max_h: int,
    ) -> None:
        """Draw a media thumbnail or placeholder in the detail view."""
        # Background panel
        self.gui.draw_rectangle_r(
            [x, y, x + max_w, y + max_h],
            6,
            fill=self.gui.COLOR_SECONDARY_LIGHT,
        )

        if has_media:
            media_path = media_dir / f"{rom_name}.png"
            pad = 4
            img = self.gui.load_image_cached(
                str(media_path), max_w - pad * 2, max_h - pad * 2
            )
            if img:
                # Center within panel
                cx = x + (max_w - img.width) // 2
                cy = y + (max_h - img.height) // 2
                if img.mode == "RGBA":
                    self.gui.activeImage.paste(img, (cx, cy), img)
                else:
                    self.gui.activeImage.paste(img, (cx, cy))
            else:
                self.gui.draw_text(
                    (x + max_w // 2, y + max_h // 2),
                    "Load error",
                    font=11,
                    color=self.gui.COLOR_MUTED,
                    anchor="mm",
                )
        else:
            self.gui.draw_text(
                (x + max_w // 2, y + max_h // 2),
                f"No {label}",
                font=13,
                color=self.gui.COLOR_MUTED,
                anchor="mm",
            )

        # Label below panel
        self.gui.draw_text(
            (x + max_w // 2, y + max_h + 4),
            label,
            font=10,
            color=self.gui.COLOR_MUTED,
            anchor="mt",
        )

    def _draw_wrapped_text(
        self, text: str, x: int, y: int, max_x: int, max_lines: int = 5
    ) -> None:
        """Draw word-wrapped text within bounds."""
        chars_per_line = (max_x - x) // 6  # ~6px per char at font 11
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test = f"{current_line} {word}".strip()
            if len(test) > chars_per_line:
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test
        if current_line:
            lines.append(current_line)

        for i, line in enumerate(lines[:max_lines]):
            if i == max_lines - 1 and len(lines) > max_lines:
                line = line[: chars_per_line - 3] + "..."
            self.gui.draw_text(
                (x, y + i * 16), line, font=11, color=self.gui.COLOR_WHITE
            )

    def _exit_roms_menu(self) -> None:
        """Exit ROM menu and return to emulator selection."""
        self.current_window = "emulators"
        self.roms_selected_position = 0

        # Clear any pending transitions to prevent conflicts
        self.pending_transition = False
        self.transition_data = None
        self.transition_target_system = ""

        self.skip_input_check = True


if __name__ == "__main__":
    app = App()

    # Use command line argument if provided, otherwise default to config.json
    if len(sys.argv) > 1:
        arg = Path(sys.argv[1])
        config_path = str(arg if arg.is_absolute() else Path.cwd() / arg)
    else:
        config_path = str(Path.cwd() / "config.json")

    logger.log_info(f"Starting application with config path: {config_path}")
    logger.log_info(f"Current working directory: {Path.cwd()}")
    logger.log_info(f"Config file exists: {Path(config_path).exists()}")

    app.start(config_path)

    while True:
        try:
            app.update()
        except KeyboardInterrupt:
            logger.log_info("KeyboardInterrupt received, exiting...")
            break
        except Exception as e:
            logger.log_error(f"Exception in main loop: {e}")
            logger.log_error("Application will exit due to unhandled exception")
            break
