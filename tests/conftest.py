"""
Shared pytest fixtures for Artie testing.
"""
import json
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock, patch

import pytest
from PIL import Image


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "roms": "/test/roms",
        "screenscraper": {
            "username": "test_user",
            "password": "test_pass"
        },
        "apply_mask": False,
        "mask_path": "assets/masks/",
        "mask_settings": {
            "box_art_mask": "box_mask.png",
            "preview_mask": "preview_mask.png",
            "opacity": 1.0,
            "blend_mode": "overlay"
        },
        "systems": {
            "nintendo64": {
                "path": "/test/roms/n64",
                "enabled": True
            },
            "snes": {
                "path": "/test/roms/snes", 
                "enabled": True
            }
        }
    }


@pytest.fixture
def config_file(temp_dir, sample_config):
    """Create a temporary config.json file."""
    config_path = temp_dir / "config.json"
    with open(config_path, 'w') as f:
        json.dump(sample_config, f, indent=2)
    return config_path


@pytest.fixture
def sample_rom_data():
    """Sample ROM metadata for testing."""
    return {
        "name": "Super Mario 64",
        "system": "nintendo64",
        "filename": "Super Mario 64.z64",
        "path": "/test/roms/n64/Super Mario 64.z64",
        "media": {
            "box-2D": "https://example.com/box.jpg",
            "ss": "https://example.com/screenshot.jpg"
        }
    }


@pytest.fixture
def mock_rom_files(temp_dir):
    """Create mock ROM files for testing."""
    roms_dir = temp_dir / "roms" / "n64"
    roms_dir.mkdir(parents=True)
    
    rom_files = [
        "Super Mario 64.z64",
        "The Legend of Zelda - Ocarina of Time.z64",
        "Super Mario Kart 64.z64"
    ]
    
    for rom_file in rom_files:
        (roms_dir / rom_file).touch()
    
    return roms_dir


@pytest.fixture
def sample_image():
    """Create a sample PIL Image for testing."""
    image = Image.new('RGB', (256, 256), color='red')
    return image


@pytest.fixture
def mock_requests_session():
    """Mock requests session for API testing."""
    with patch('requests.Session') as mock_session:
        mock_instance = Mock()
        mock_session.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_api_response():
    """Mock API response data."""
    return {
        "response": {
            "games": [{
                "id": "12345",
                "names": [{"text": "Super Mario 64"}],
                "medias": [{
                    "type": "box-2D",
                    "url": "https://example.com/box.jpg"
                }]
            }]
        }
    }


@pytest.fixture
def mock_cache_manager():
    """Mock cache manager for testing."""
    with patch('src.cache_manager.CacheManager') as mock_cache:
        mock_instance = Mock()
        mock_cache.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    with patch('src.logger.setup_logger') as mock_setup:
        mock_logger_instance = Mock()
        mock_setup.return_value = mock_logger_instance
        yield mock_logger_instance


@pytest.fixture
def mock_config_manager(sample_config):
    """Mock config manager with sample configuration."""
    with patch('src.config_manager.ConfigManager') as mock_config:
        mock_instance = Mock()
        mock_instance.config = sample_config
        mock_config.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_image_processor():
    """Mock image processor for testing."""
    with patch('src.image_processor.ImageProcessor') as mock_processor:
        mock_instance = Mock()
        mock_processor.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_rom_manager():
    """Mock ROM manager for testing."""
    with patch('src.rom_manager.ROMManager') as mock_rom:
        mock_instance = Mock()
        mock_rom.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_scraper():
    """Mock scraper for testing."""
    with patch('src.scraper.Scraper') as mock_scraper:
        mock_instance = Mock()
        mock_scraper.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_mask_image(temp_dir):
    """Create a sample mask image for testing."""
    mask_dir = temp_dir / "masks"
    mask_dir.mkdir(parents=True)
    
    # Create a simple mask image
    mask = Image.new('RGBA', (256, 256), (0, 0, 0, 128))
    mask_path = mask_dir / "test_mask.png"
    mask.save(mask_path)
    
    return mask_path


@pytest.fixture
def mock_system_info():
    """Mock system information for testing."""
    return {
        "nintendo64": {
            "name": "Nintendo 64",
            "extensions": [".z64", ".n64", ".v64"],
            "path": "/test/roms/n64"
        },
        "snes": {
            "name": "Super Nintendo",
            "extensions": [".sfc", ".smc"],
            "path": "/test/roms/snes"
        }
    }


# pytest_configure is handled automatically by pytest via pyproject.toml markers configuration


@pytest.fixture
def captured_logs():
    """Capture log output for testing."""
    import logging
    from io import StringIO
    
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    yield log_capture
    
    logger.removeHandler(handler)


@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment variables and state before each test."""
    import os
    original_env = os.environ.copy()
    yield
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)