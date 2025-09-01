"""
Infrastructure validation tests to ensure testing setup works correctly.
"""
import pytest
import json
from pathlib import Path


def test_pytest_working():
    """Test that pytest is working correctly."""
    assert True


def test_pytest_markers():
    """Test that custom pytest markers are configured."""
    # This is a basic validation that pytest markers can be used
    # The actual marker validation happens when pytest runs with --strict-markers
    assert True


@pytest.mark.unit
def test_unit_marker():
    """Test unit marker works."""
    assert True


@pytest.mark.integration
def test_integration_marker():
    """Test integration marker works."""
    assert True


@pytest.mark.slow
def test_slow_marker():
    """Test slow marker works."""
    assert True


def test_fixtures_available(temp_dir, sample_config, sample_rom_data):
    """Test that shared fixtures are available and working."""
    # Test temp_dir fixture
    assert temp_dir.exists()
    assert temp_dir.is_dir()
    
    # Test sample_config fixture
    assert isinstance(sample_config, dict)
    assert "roms" in sample_config
    assert "screenscraper" in sample_config
    
    # Test sample_rom_data fixture
    assert isinstance(sample_rom_data, dict)
    assert "name" in sample_rom_data
    assert "system" in sample_rom_data


def test_config_file_fixture(config_file, sample_config):
    """Test that config file fixture creates valid JSON."""
    assert config_file.exists()
    
    with open(config_file, 'r') as f:
        loaded_config = json.load(f)
    
    assert loaded_config == sample_config


def test_mock_rom_files(mock_rom_files):
    """Test that mock ROM files are created."""
    assert mock_rom_files.exists()
    assert mock_rom_files.is_dir()
    
    rom_files = list(mock_rom_files.glob("*.z64"))
    assert len(rom_files) == 3
    
    expected_files = [
        "Super Mario 64.z64",
        "The Legend of Zelda - Ocarina of Time.z64", 
        "Super Mario Kart 64.z64"
    ]
    
    actual_files = [f.name for f in rom_files]
    for expected in expected_files:
        assert expected in actual_files


def test_sample_image(sample_image):
    """Test that sample image fixture works."""
    assert sample_image.size == (256, 256)
    assert sample_image.mode == 'RGB'


def test_project_structure():
    """Test that project structure is correct."""
    project_root = Path(__file__).parent.parent
    
    # Check that main directories exist
    assert (project_root / "src").exists()
    assert (project_root / "tests").exists()
    assert (project_root / "tests" / "unit").exists()
    assert (project_root / "tests" / "integration").exists()
    
    # Check that config files exist
    assert (project_root / "pyproject.toml").exists()
    assert (project_root / "requirements.txt").exists()


def test_pyproject_config():
    """Test that pyproject.toml is correctly configured."""
    project_root = Path(__file__).parent.parent
    pyproject_path = project_root / "pyproject.toml"
    
    assert pyproject_path.exists()
    
    # Read and basic validation that it's valid TOML
    try:
        import tomllib
        with open(pyproject_path, 'rb') as f:
            config = tomllib.load(f)
    except ImportError:
        # Python < 3.11 fallback
        import toml
        with open(pyproject_path, 'r') as f:
            config = toml.load(f)
    
    # Check that key sections exist
    assert "tool" in config
    assert "poetry" in config["tool"]
    assert "pytest" in config["tool"]
    assert "coverage" in config["tool"]
    
    # Check pytest configuration
    pytest_config = config["tool"]["pytest"]["ini_options"]
    assert "testpaths" in pytest_config
    assert pytest_config["testpaths"] == ["tests"]
    
    # Check coverage configuration
    coverage_config = config["tool"]["coverage"]
    assert "run" in coverage_config
    assert "report" in coverage_config
    assert coverage_config["run"]["source"] == ["src"]