"""
Unit tests for ConfigBuilder class.
"""
import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch, mock_open, Mock
from src.config.builder import ConfigBuilder, deep_merge


class TestDeepMerge:
    """Test the deep_merge utility function."""
    
    def test_simple_merge(self):
        """Test merging simple dictionaries."""
        dest = {"a": 1, "b": 2}
        source = {"b": 3, "c": 4}
        result = deep_merge(dest, source)
        
        assert result == {"a": 1, "b": 3, "c": 4}
        assert dest == {"a": 1, "b": 3, "c": 4}  # dest is modified in place
    
    def test_nested_merge(self):
        """Test merging nested dictionaries."""
        dest = {
            "level1": {
                "a": 1,
                "b": 2
            },
            "level2": 3
        }
        source = {
            "level1": {
                "b": 4,
                "c": 5
            },
            "level3": 6
        }
        result = deep_merge(dest, source)
        
        expected = {
            "level1": {
                "a": 1,
                "b": 4,
                "c": 5
            },
            "level2": 3,
            "level3": 6
        }
        assert result == expected
    
    def test_empty_merge(self):
        """Test merging with empty dictionaries."""
        dest = {"a": 1}
        source = {}
        result = deep_merge(dest, source)
        assert result == {"a": 1}
        
        dest = {}
        source = {"a": 1}
        result = deep_merge(dest, source)
        assert result == {"a": 1}


class TestConfigBuilder:
    """Test the ConfigBuilder class."""
    
    def test_init(self):
        """Test ConfigBuilder initialization."""
        builder = ConfigBuilder()
        assert builder is not None
    
    @patch('src.config.builder.importlib.import_module')
    def test_load_python_profile_success(self, mock_import):
        """Test successful loading of Python profile."""
        # Setup mock module
        mock_module = Mock()
        mock_module.config = {"test": "value"}
        mock_import.return_value = mock_module
        
        builder = ConfigBuilder()
        result = builder._load_python_profile('.test_profile', package='config')
        
        assert result == {"test": "value"}
        mock_import.assert_called_once_with('.test_profile', package='config')
    
    @patch('src.config.builder.importlib.import_module')
    def test_load_python_profile_import_error(self, mock_import):
        """Test ImportError handling in profile loading."""
        mock_import.side_effect = ImportError("Module not found")
        
        builder = ConfigBuilder()
        with pytest.raises(ImportError, match="Configuration profile could not be imported"):
            builder._load_python_profile('.nonexistent', package='config')
    
    @patch('src.config.builder.importlib.import_module')
    def test_load_python_profile_attribute_error(self, mock_import):
        """Test AttributeError handling when config attribute missing."""
        mock_module = Mock()
        del mock_module.config  # Remove config attribute
        mock_import.return_value = mock_module
        
        builder = ConfigBuilder()
        with pytest.raises(AttributeError, match="does not contain a 'config' dictionary"):
            builder._load_python_profile('.test_profile', package='config')
    
    def test_discover_case_config_missing_directory(self, temp_dir):
        """Test case discovery with missing directory."""
        builder = ConfigBuilder()
        
        with pytest.raises(FileNotFoundError, match="Case directory for auto-discovery not found"):
            builder._discover_case_config("nonexistent_case", str(temp_dir))
    
    def test_discover_case_config_success(self, sample_case_directory):
        """Test successful case discovery."""
        builder = ConfigBuilder()
        
        # Get the parent directory of the case (CAD directory)
        cad_dir = sample_case_directory.parent
        case_name = sample_case_directory.name
        
        result = builder._discover_case_config(case_name, str(cad_dir))
        
        # Check geometry discovery
        assert result["geometry"]["case_name"] == case_name
        assert result["geometry"]["wall_keywords_ordered"] == "wall_aorta"
        assert result["geometry"]["inlet_keywords_ordered"] == "inlet"
        assert "outlet1" in result["geometry"]["outlet_keywords_ordered"]
        assert "outlet2" in result["geometry"]["outlet_keywords_ordered"]
        
        # Check boundary conditions were loaded
        assert "boundary_conditions" in result
        assert result["boundary_conditions"]["inlet"]["type"] == "flowRateInletVelocity"
    
    def test_discover_case_config_no_boundary_file(self, temp_dir):
        """Test case discovery without boundary conditions file."""
        case_dir = temp_dir / "CAD" / "test_case"
        case_dir.mkdir(parents=True)
        
        # Create only STL files, no boundary_conditions.json
        stl_files = ["inlet.stl", "outlet1.stl", "wall_aorta.stl"]
        for stl_file in stl_files:
            (case_dir / stl_file).write_text("# Empty STL file")
        
        builder = ConfigBuilder()
        result = builder._discover_case_config("test_case", str(temp_dir / "CAD"))
        
        # Should still work, just without boundary conditions
        assert result["geometry"]["case_name"] == "test_case"
        assert "boundary_conditions" not in result or result["boundary_conditions"] == {}
    
    def test_discover_case_config_outlet_ordering(self, temp_dir):
        """Test that outlets are ordered correctly by number."""
        case_dir = temp_dir / "CAD" / "test_case"
        case_dir.mkdir(parents=True)
        
        # Create outlets in non-sequential order
        stl_files = ["inlet.stl", "outlet10.stl", "outlet2.stl", "outlet1.stl", "wall_aorta.stl"]
        for stl_file in stl_files:
            (case_dir / stl_file).write_text("# Empty STL file")
        
        builder = ConfigBuilder()
        result = builder._discover_case_config("test_case", str(temp_dir / "CAD"))
        
        # Check that outlets are sorted by number
        outlets = result["geometry"]["outlet_keywords_ordered"]
        assert outlets == ["outlet1", "outlet2", "outlet10"]
    
    @patch.object(ConfigBuilder, '_load_python_profile')
    @patch.object(ConfigBuilder, '_discover_case_config')
    def test_build_success(self, mock_discover, mock_load_profile):
        """Test successful config building."""
        # Setup mocks
        base_config = {
            "base": "config",
            "nested": {"base": "value"}
        }
        sim_config = {
            "sim": "config",
            "nested": {"sim": "value"}
        }
        case_config = {
            "case": "config",
            "nested": {"case": "value"}
        }
        
        mock_load_profile.side_effect = [base_config, sim_config]
        mock_discover.return_value = case_config
        
        builder = ConfigBuilder()
        result = builder.build("test_case", "test_profile")
        
        # Check that all configs were loaded
        mock_load_profile.assert_any_call('.base', package='config')
        mock_load_profile.assert_any_call('.profiles.test_profile', package='config')
        mock_discover.assert_called_once_with("test_case")
        
        # Check merging (later configs should override earlier ones)
        assert result["base"] == "config"
        assert result["sim"] == "config"
        assert result["case"] == "config"
        assert result["nested"]["base"] == "value"
        assert result["nested"]["sim"] == "value"
        assert result["nested"]["case"] == "value"  # Should be final value
    
    @patch.object(ConfigBuilder, '_load_python_profile')
    def test_build_profile_loading_error(self, mock_load_profile):
        """Test build failure when profile loading fails."""
        mock_load_profile.side_effect = ImportError("Profile not found")
        
        builder = ConfigBuilder()
        with pytest.raises(RuntimeError, match="Failed to load configuration files"):
            builder.build("test_case", "nonexistent_profile")
    
    @patch.object(ConfigBuilder, '_load_python_profile')
    @patch.object(ConfigBuilder, '_discover_case_config')
    def test_build_case_discovery_error(self, mock_discover, mock_load_profile):
        """Test build failure when case discovery fails."""
        mock_load_profile.return_value = {"base": "config"}
        mock_discover.side_effect = FileNotFoundError("Case not found")
        
        builder = ConfigBuilder()
        with pytest.raises(RuntimeError, match="Failed to load configuration files"):
            builder.build("nonexistent_case", "test_profile")


class TestConfigBuilderIntegration:
    """Integration tests for ConfigBuilder."""
    
    def test_json_parsing_error(self, temp_dir):
        """Test handling of malformed JSON boundary conditions."""
        case_dir = temp_dir / "CAD" / "test_case"
        case_dir.mkdir(parents=True)
        
        # Create STL files
        (case_dir / "inlet.stl").write_text("# STL")
        (case_dir / "wall_aorta.stl").write_text("# STL")
        
        # Create malformed JSON
        (case_dir / "boundary_conditions.json").write_text("{ invalid json }")
        
        builder = ConfigBuilder()
        with pytest.raises(json.JSONDecodeError):
            builder._discover_case_config("test_case", str(temp_dir / "CAD"))
    
    def test_empty_case_directory(self, temp_dir):
        """Test case discovery with empty case directory."""
        case_dir = temp_dir / "CAD" / "empty_case"
        case_dir.mkdir(parents=True)
        
        builder = ConfigBuilder()
        result = builder._discover_case_config("empty_case", str(temp_dir / "CAD"))
        
        # Should return minimal config
        assert result["geometry"]["case_name"] == "empty_case"
        assert result["geometry"]["wall_keywords_ordered"] == ""
        assert result["geometry"]["inlet_keywords_ordered"] == ""
        assert result["geometry"]["outlet_keywords_ordered"] == []