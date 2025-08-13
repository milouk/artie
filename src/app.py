"""Main application module for Artie Scraper with optimized structure."""

import concurrent.futures
import sys
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
from cache_manager import api_cached, get_cache_manager
from config_manager import ConfigManager, ScraperConfig
from graphic import GUI
from logger import LoggerSingleton as logger
from rom_manager import Rom, RomManager
from scraper import (
    check_destination,
    check_rate_limit_cache_status,
    fetch_box,
    fetch_preview,
    fetch_synopsis,
    get_game_data,
    get_image_files_without_extension,
    get_txt_files_without_extension,
    get_user_data,
)

VERSION = "2.0.0"

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
        self.roms_without_box = roms_without_box
        self.roms_without_preview = roms_without_preview
        self.roms_without_synopsis = roms_without_synopsis
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

            # Initialize GUI
            self._initialize_gui()

            # Get user thread limits (now with proper error handling)
            self._configure_user_threads()

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
                self.gui.COLOR_PRIMARY = self.config.colors.get(
                    "primary", self.gui.COLOR_PRIMARY
                )
                self.gui.COLOR_PRIMARY_DARK = self.config.colors.get(
                    "primary_dark", self.gui.COLOR_PRIMARY_DARK
                )
                self.gui.COLOR_SECONDARY = self.config.colors.get(
                    "secondary", self.gui.COLOR_SECONDARY
                )
                self.gui.COLOR_SECONDARY_LIGHT = self.config.colors.get(
                    "secondary_light", self.gui.COLOR_SECONDARY_LIGHT
                )
                self.gui.COLOR_SECONDARY_DARK = self.config.colors.get(
                    "secondary_dark", self.gui.COLOR_SECONDARY_DARK
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

    @api_cached(ttl=300)  # Cache for 5 minutes
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
                f"PERFORMANCE STATS: Total cache entries: {stats.get('memory_cache_size', 0) + stats.get('api_cache_size', 0)}"
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

        # Draw all interface elements to buffer
        self.gui.draw_rectangle_r([10, 40, 630, 440], 15)
        self.gui.draw_text((320, 20), f"Artie Scraper v{VERSION}", anchor="mm")

        if available_systems:
            self._draw_available_systems(available_systems)
        else:
            self._draw_no_emulators_message()

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
        """Draw a single system row."""
        y_pos = 50 + (index * 35)
        self.gui.draw_rectangle_r(
            [20, y_pos, 620, y_pos + 32],
            5,
            fill=self.gui.COLOR_PRIMARY if selected else self.gui.COLOR_SECONDARY_LIGHT,
        )
        self.gui.draw_text((25, y_pos + 5), system)

    def _draw_no_emulators_message(self) -> None:
        """Draw message when no emulators are found."""
        self.gui.draw_text(
            (320, 240), f"No Emulators found in {self.config.roms_path}", anchor="mm"
        )

    def _draw_emulator_controls(self) -> None:
        """Draw control buttons for emulator screen."""
        self._draw_button_circle((30, 450), "A", "Select")
        self._draw_button_circle((170, 450), "X", "Delete")
        self._draw_button_circle((300, 450), "M", "Exit")

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
        """Clear the ROM data cache."""
        self.cached_roms_data = None
        self.cached_system = None

    def _select_system(self, available_systems: List[str]) -> None:
        """Select a system and prepare for atomic transition to ROM view with data prepared BEFORE any visual changes."""
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
                self.gui.draw_rectangle_r([10, 40, 630, 440], 15)
                self.gui.draw_text((320, 20), f"Artie Scraper v{VERSION}", anchor="mm")
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
            self.gui.draw_rectangle_r([10, 40, 630, 440], 15)
            self.gui.draw_text((320, 20), f"Artie Scraper v{VERSION}", anchor="mm")
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
            enabled_media_types = self.config_manager.get_enabled_media_types()
            self.rom_manager.delete_system_media(
                self.selected_system, system_config, enabled_media_types
            )
            # Clear cache after deleting system media
            self._clear_rom_cache()

        self.gui.draw_log(f"Deleting all enabled {self.selected_system} media...")
        self.gui.draw_paint()
        self.skip_input_check = True
        time.sleep(self.LOG_WAIT)

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
        missing_roms = set(
            roms_without_box + roms_without_preview + roms_without_synopsis
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

        rom = roms_data.roms_to_scrape[self.roms_selected_position]
        self.gui.draw_log(f"Scraping {rom.name}...")
        self.gui.draw_paint()

        # Hash preloading removed - no longer calculating hashes

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

    def _scrape_all_roms(self, roms_data: RomsData) -> None:
        """Scrape all ROMs using thread pool with performance monitoring and progress indicators."""
        if not roms_data.roms_to_scrape:
            return

        total_roms = len(roms_data.roms_to_scrape)

        # PERFORMANCE: Show initial performance info (hash stats removed)
        cache_stats = self.cache_manager.get_stats()

        self.gui.draw_log(f"Starting batch scraping of {total_roms} ROMs...")
        # API Cache popup: Shows current cache statistics to help users understand
        # performance optimizations - displays number of cached API responses and hit rate
        self.gui.draw_log(
            f"API cache: {cache_stats.get('api_cache_size', 0)} entries, "
            f"{cache_stats.get('hit_rate_percent', 0):.1f}% hit rate"
        )
        self.gui.draw_paint()

        completed = 0
        quota_exceeded = False
        start_time = time.time()
        # Hash functionality removed

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

                # Process completed tasks with performance monitoring
                for future in concurrent.futures.as_completed(future_to_rom):
                    rom = future_to_rom[future]
                    try:
                        result = future.result()
                        completed += 1

                        # Hash tracking removed

                        # Show progress with performance info
                        elapsed_time = time.time() - start_time
                        avg_time_per_rom = (
                            elapsed_time / completed if completed > 0 else 0
                        )
                        estimated_remaining = avg_time_per_rom * (
                            total_roms - completed
                        )

                        progress_msg = (
                            f"PROGRESS: {completed}/{total_roms} ROMs "
                            f"({(completed/total_roms)*100:.1f}%) - "
                            f"ETA: {estimated_remaining/60:.1f}min"
                        )

                        logger.log_info(progress_msg)

                        # Update GUI after every ROM for live progress updates
                        if True:  # Update after every ROM
                            self.gui.draw_log(progress_msg)
                            # Hash efficiency tracking removed
                            self.gui.draw_paint()

                    except exceptions.RateLimitError as e:
                        logger.log_error(
                            f"RATE_LIMIT_DEBUG: Rate limit error during batch scraping: {e}"
                        )
                        cache_status = check_rate_limit_cache_status(
                            self.config.username
                        )
                        logger.log_error(
                            f"RATE_LIMIT_DEBUG: Current cache status: {cache_status}"
                        )
                        quota_exceeded = True
                        # Cancel remaining tasks when quota is exceeded
                        for remaining_future in future_to_rom:
                            remaining_future.cancel()
                        break
                    except exceptions.ForbiddenError as e:
                        logger.log_error(
                            f"API access forbidden for ROM {rom.name}: {e}"
                        )
                    except Exception as e:
                        logger.log_error(f"Error scraping ROM {rom.name}: {e}")

            # PERFORMANCE: Show final performance statistics
            total_time = time.time() - start_time
            final_cache_stats = self.cache_manager.get_stats()

            performance_summary = [
                f"PERFORMANCE SUMMARY:",
                f"• Total time: {total_time/60:.1f} minutes",
                (
                    f"• Average time per ROM: {total_time/completed:.1f}s"
                    if completed > 0
                    else "• No ROMs completed"
                ),
                f"• API requests optimized with caching",
                f"• Network requests optimized with connection pooling",
            ]

            for msg in performance_summary:
                if msg:  # Skip empty messages
                    logger.log_info(msg)
                    self.gui.draw_log(msg)

            # Clear cache after batch scraping to ensure fresh data on next load
            if completed > 0:
                logger.log_debug(
                    "CACHE INVALIDATION: Clearing cache after batch ROM scraping"
                )
                self._clear_rom_cache()

            if quota_exceeded:
                self.gui.draw_log(
                    f"Batch stopped: API quota exceeded. Completed {completed} ROMs."
                )
            else:
                self.gui.draw_log(
                    f"Batch scraping completed: {completed}/{total_roms} ROMs"
                )

        except Exception as e:
            logger.log_error(f"Error in batch scraping: {e}")
            self.gui.draw_log(f"Batch scraping error: {str(e)[:50]}...")

        self.gui.draw_paint()
        time.sleep(self.LOG_WAIT * 3)  # Longer wait to read performance summary
        self.skip_input_check = True

    def _process_rom(self, rom: Rom, roms_data: RomsData) -> Tuple[Any, Any, Any, str]:
        """Process a single ROM (scrape and save media)."""
        try:
            scraped_box, scraped_preview, scraped_synopsis = self._scrape_rom_media(
                rom, roms_data.system_id
            )
        except (exceptions.ForbiddenError, exceptions.RateLimitError) as e:
            raise e

        # Save scraped media
        if scraped_box:
            destination = roms_data.box_dir / f"{rom.name}.png"
            self._save_file_to_disk(scraped_box, destination)

        if scraped_preview:
            destination = roms_data.preview_dir / f"{rom.name}.png"
            self._save_file_to_disk(scraped_preview, destination)

        if scraped_synopsis:
            destination = roms_data.synopsis_dir / f"{rom.name}.txt"
            self._save_file_to_disk(scraped_synopsis.encode("utf-8"), destination)

        return scraped_box, scraped_preview, scraped_synopsis, rom.name

    def _process_rom_with_monitoring(self, rom: Rom, roms_data: RomsData) -> dict:
        """Process a single ROM with performance monitoring."""
        start_time = time.time()

        # Hash functionality removed

        try:
            scraped_box, scraped_preview, scraped_synopsis, rom_name = (
                self._process_rom(rom, roms_data)
            )

            processing_time = time.time() - start_time

            return {
                "success": True,
                "rom_name": rom_name,
                "processing_time": processing_time,
                # Hash tracking removed
                "scraped_box": scraped_box is not None,
                "scraped_preview": scraped_preview is not None,
                "scraped_synopsis": scraped_synopsis is not None,
            }

        except (exceptions.ForbiddenError, exceptions.RateLimitError) as e:
            raise e
        except Exception as e:
            processing_time = time.time() - start_time
            logger.log_error(f"Error processing ROM {rom.name}: {e}")

            return {
                "success": False,
                "rom_name": rom.name,
                "processing_time": processing_time,
                # Hash tracking removed
                "error": str(e),
            }

    def _scrape_rom_media(self, rom: Rom, system_id: str) -> Tuple[Any, Any, Any]:
        """Scrape media for a ROM."""
        scraped_box = scraped_preview = scraped_synopsis = None

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
            if self.config.box_enabled:
                scraped_box = fetch_box(game, content)
            if self.config.preview_enabled:
                scraped_preview = fetch_preview(game, content)
            if self.config.synopsis_enabled:
                scraped_synopsis = fetch_synopsis(game, content)

        return scraped_box, scraped_preview, scraped_synopsis

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
        logger.log_debug(
            "=== ROM NAVIGATION DEBUG: Starting optimized ROM interface render ==="
        )

        # Create a new image buffer and prepare complete interface before painting
        logger.log_debug(
            "ROM NAVIGATION DEBUG: Creating new image buffer for complete interface"
        )
        interface_image = self.gui.create_image()
        self.gui.draw_active(interface_image)

        # Draw all interface elements to the buffer first
        logger.log_debug(
            "ROM NAVIGATION DEBUG: Drawing all interface elements to buffer"
        )
        self.gui.draw_rectangle_r([10, 40, 630, 440], 15)

        # Draw header information
        self._draw_roms_header(roms_data)

        # Draw ROM list
        self._draw_roms_list(roms_data)

        # Draw controls
        self._draw_roms_controls()

        # Paint the complete interface in one operation (no black flash)
        logger.log_debug(
            "ROM NAVIGATION DEBUG: Painting complete interface in single operation"
        )
        self.gui.draw_paint()
        logger.log_debug(
            "=== ROM NAVIGATION DEBUG: Optimized ROM interface render complete ==="
        )

    def _draw_roms_header(self, roms_data: RomsData) -> None:
        """Draw header with ROM statistics."""
        rom_text = f"{self.selected_system} - Total Roms: {len(roms_data.roms_list)}"

        missing_parts = []
        if self.config.box_enabled:
            missing_parts.append(f"No box: {len(roms_data.roms_without_box)}")
        if self.config.preview_enabled:
            missing_parts.append(f"No preview: {len(roms_data.roms_without_preview)}")
        if self.config.synopsis_enabled:
            missing_parts.append(f"No text: {len(roms_data.roms_without_synopsis)}")

        missing_text = " / ".join(missing_parts)

        self.gui.draw_text((90, 10), rom_text, anchor="mm")
        self.gui.draw_text((500, 10), missing_text, anchor="mm")

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
        """Draw a single ROM row with status information."""
        y_pos = 50 + (index * 35)

        # Determine what media already exists
        already_scraped = []
        if self.config.box_enabled and rom not in roms_data.roms_without_box:
            already_scraped.append("Box")
        if self.config.preview_enabled and rom not in roms_data.roms_without_preview:
            already_scraped.append("Preview")
        if self.config.synopsis_enabled and rom not in roms_data.roms_without_synopsis:
            already_scraped.append("Text")

        # Truncate ROM name if too long
        max_length = 48
        display_name = (
            rom.name[:max_length] + "..." if len(rom.name) > max_length else rom.name
        )

        # Draw main row
        self.gui.draw_rectangle_r(
            [20, y_pos, 620, y_pos + 32],
            5,
            fill=self.gui.COLOR_PRIMARY if selected else self.gui.COLOR_SECONDARY_LIGHT,
        )
        self.gui.draw_text((25, y_pos + 5), display_name)

        # Draw status information
        if already_scraped:
            status_text = "/".join(already_scraped)
            self.gui.draw_rectangle_r(
                [500, y_pos, 550, y_pos + 32],
                5,
                fill=(
                    self.gui.COLOR_PRIMARY
                    if selected
                    else self.gui.COLOR_SECONDARY_LIGHT
                ),
            )
            self.gui.draw_text((505, y_pos + 5), status_text)

    def _draw_roms_controls(self) -> None:
        """Draw control buttons for ROM screen."""
        self._draw_button_rectangle((30, 450), "Start", "All")
        self._draw_button_circle((140, 450), "A", "Download")
        self._draw_button_circle((250, 450), "X", "Delete")
        self._draw_button_circle((370, 450), "B", "Back")
        self._draw_button_circle((500, 450), "M", "Exit")

    def _draw_button_circle(self, pos: Tuple[int, int], button: str, text: str) -> None:
        """Draw a circular button with label."""
        self.gui.draw_circle(pos, 25)
        self.gui.draw_text((pos[0] + 12, pos[1] + 12), button, anchor="mm")
        self.gui.draw_text((pos[0] + 30, pos[1] + 12), text, font=13, anchor="lm")

    def _draw_button_rectangle(
        self, pos: Tuple[int, int], button: str, text: str
    ) -> None:
        """Draw a rectangular button with label."""
        self.gui.draw_rectangle_r(
            (pos[0], pos[1], pos[0] + 60, pos[1] + 25),
            5,
            fill=self.gui.COLOR_SECONDARY_LIGHT,
        )
        self.gui.draw_text((pos[0] + 30, pos[1] + 12), button, anchor="mm")
        self.gui.draw_text((pos[0] + 65, pos[1] + 12), text, font=13, anchor="lm")

    def _exit_roms_menu(self) -> None:
        """Exit ROM menu and return to emulator selection with atomic transition."""
        logger.log_debug(
            f"DEBUG_TRANSITION: _exit_roms_menu() called - preparing atomic transition from '{self.current_window}' to 'emulators'"
        )

        # ATOMIC TRANSITION: Change state immediately and ensure proper input reset
        self.current_window = "emulators"
        self.roms_selected_position = 0

        # Clear any pending transitions to prevent conflicts
        self.pending_transition = False
        self.transition_data = None
        self.transition_target_system = ""

        # Ensure input is properly reset to prevent race conditions
        self.skip_input_check = True

        logger.log_debug(
            f"DEBUG_TRANSITION: _exit_roms_menu() complete - current_window is now '{self.current_window}', input will be reset"
        )


if __name__ == "__main__":
    app = App()

    # Use command line argument if provided, otherwise default to config.json
    if len(sys.argv) > 1:
        config_path = f"{Path.cwd()}/{sys.argv[1]}"
    else:
        config_path = f"{Path.cwd()}/config.json"

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
