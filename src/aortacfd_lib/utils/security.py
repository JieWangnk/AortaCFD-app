"""
Security and validation utilities for AortaCFD.
"""

import os
import shutil
import psutil
from pathlib import Path
from typing import Dict, List, Optional


class SecurityValidator:
    """Security validation utilities."""
    
    @staticmethod
    def validate_file_path(file_path: Path, allowed_extensions: List[str] = None) -> bool:
        """
        Validate that a file path is safe to use.
        
        Args:
            file_path: Path to validate
            allowed_extensions: List of allowed file extensions
            
        Returns:
            True if path is safe, False otherwise
        """
        try:
            # Resolve path to catch any traversal attempts
            resolved_path = file_path.resolve()
            
            # Check for dangerous path components
            path_str = str(resolved_path)
            dangerous_patterns = ['..', '~', '$', '|', ';', '&', '`', '\n', '\r']
            if any(pattern in path_str for pattern in dangerous_patterns):
                return False
                
            # Check file extension if specified
            if allowed_extensions:
                if file_path.suffix.lower() not in [ext.lower() for ext in allowed_extensions]:
                    return False
                    
            # Check file size (max 100MB for safety)
            if file_path.exists() and file_path.stat().st_size > 100 * 1024 * 1024:
                return False
                
            return True
            
        except (OSError, ValueError):
            return False
    
    @staticmethod
    def validate_directory_path(dir_path: Path) -> bool:
        """
        Validate that a directory path is safe to use.
        
        Args:
            dir_path: Directory path to validate
            
        Returns:
            True if path is safe, False otherwise
        """
        try:
            # Resolve path to catch any traversal attempts
            resolved_path = dir_path.resolve()
            
            # Check for dangerous path components
            path_str = str(resolved_path)
            dangerous_patterns = ['..', '$', '|', ';', '&', '`', '\n', '\r']
            if any(pattern in path_str for pattern in dangerous_patterns):
                return False
                
            # Ensure path doesn't escape reasonable bounds
            allowed_prefixes = ['/tmp', '/home', '/opt', str(Path.cwd())]
            if resolved_path.is_absolute():
                if not any(path_str.startswith(prefix) for prefix in allowed_prefixes):
                    return False
                    
            return True
            
        except (OSError, ValueError):
            return False


class ResourceValidator:
    """System resource validation utilities."""
    
    def __init__(self):
        self.min_memory_gb = 2.0
        self.min_disk_space_gb = 5.0
        self.max_mesh_cells = 10_000_000
        
    def check_system_resources(self) -> Dict[str, any]:
        """
        Check available system resources.
        
        Returns:
            Dictionary with resource information and validation status
        """
        try:
            # Memory check
            memory = psutil.virtual_memory()
            memory_gb = memory.total / (1024**3)
            memory_available_gb = memory.available / (1024**3)
            
            # Disk space check
            disk = shutil.disk_usage(Path.cwd())
            disk_free_gb = disk.free / (1024**3)
            
            # CPU check
            cpu_count = psutil.cpu_count()
            cpu_percent = psutil.cpu_percent(interval=1)
            
            return {
                'memory_total_gb': memory_gb,
                'memory_available_gb': memory_available_gb,
                'memory_sufficient': memory_available_gb >= self.min_memory_gb,
                'disk_free_gb': disk_free_gb,
                'disk_sufficient': disk_free_gb >= self.min_disk_space_gb,
                'cpu_count': cpu_count,
                'cpu_usage_percent': cpu_percent,
                'system_ready': (
                    memory_available_gb >= self.min_memory_gb and 
                    disk_free_gb >= self.min_disk_space_gb and
                    cpu_percent < 90
                )
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'system_ready': False
            }
    
    def validate_mesh_size(self, estimated_cells: int) -> bool:
        """
        Validate that mesh size is within reasonable bounds.
        
        Args:
            estimated_cells: Estimated number of mesh cells
            
        Returns:
            True if mesh size is acceptable, False otherwise
        """
        return estimated_cells <= self.max_mesh_cells
    
    def estimate_memory_usage(self, mesh_cells: int) -> float:
        """
        Estimate memory usage for a given mesh size.
        
        Args:
            mesh_cells: Number of mesh cells
            
        Returns:
            Estimated memory usage in GB
        """
        # Rough estimation: ~1KB per cell for basic variables
        # Plus overhead for solver matrices
        base_memory = mesh_cells * 1024  # bytes
        solver_overhead = base_memory * 2  # matrices and solver data
        total_bytes = base_memory + solver_overhead
        
        return total_bytes / (1024**3)  # Convert to GB


class ConfigurationValidator:
    """Configuration validation utilities."""
    
    @staticmethod
    def validate_simulation_config(config: Dict) -> Dict[str, any]:
        """
        Validate simulation configuration.
        
        Args:
            config: Simulation configuration dictionary
            
        Returns:
            Validation result with errors if any
        """
        errors = []
        warnings = []
        
        # Check required top-level keys
        required_keys = ['geometry', 'physics', 'mesh', 'solver']
        for key in required_keys:
            if key not in config:
                errors.append(f"Missing required configuration key: {key}")
        
        # Validate geometry settings
        if 'geometry' in config:
            geometry = config['geometry']
            if 'case_name' not in geometry:
                errors.append("Missing case_name in geometry configuration")
        
        # Validate physics settings
        if 'physics' in config:
            physics = config['physics']
            if 'nu' in physics:
                try:
                    nu = float(physics['nu'])
                    if nu <= 0 or nu > 1:
                        warnings.append(f"Unusual kinematic viscosity value: {nu}")
                except (ValueError, TypeError):
                    errors.append("Invalid kinematic viscosity value")
        
        # Validate mesh settings
        if 'mesh' in config:
            mesh = config['mesh']
            resolution_value = None
            mesh_resolution = mesh.get('mesh_resolution')
            if isinstance(mesh_resolution, dict):
                resolution_value = mesh_resolution.get('blockmesh_resolution') or mesh_resolution.get('blockMesh_resolution')

            if resolution_value is None and 'BLOCKMESH_SETTINGS' in mesh:
                blockmesh = mesh['BLOCKMESH_SETTINGS']
                resolution_value = blockmesh.get('resolution')

            if resolution_value is not None:
                try:
                    res = int(resolution_value)
                    if res < 10 or res > 200:
                        warnings.append(f"Unusual mesh resolution: {res}")
                except (ValueError, TypeError):
                    errors.append("Invalid mesh resolution value")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }