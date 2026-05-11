"""
Performance optimization module for AortaCFD.
Provides intelligent performance tuning and resource management.
"""

import psutil
import time
import numpy as np
from typing import Dict, List
from dataclasses import dataclass
from .utils.logger import Logger

logger = Logger("performance_optimizer").get_logger()


@dataclass
class SystemResources:
    """System resource information"""

    cpu_cores: int
    memory_gb: float
    available_memory_gb: float
    cpu_usage_percent: float
    disk_space_gb: float


@dataclass
class SimulationProfile:
    """Simulation performance profile"""

    case_name: str
    mesh_size: int
    time_steps: int
    convergence_time: float
    memory_usage_gb: float
    cpu_efficiency: float
    success_rate: float


class PerformanceOptimizer:
    """
    Intelligent performance optimization for AortaCFD simulations.
    Automatically tunes parameters based on system resources and simulation history.
    """

    def __init__(self, config: dict):
        self.config = config
        self.log = logger
        self.simulation_history: List[SimulationProfile] = []
        self.resource_monitor = ResourceMonitor()

    def analyze_system_resources(self) -> SystemResources:
        """Analyze current system resources"""
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        resources = SystemResources(
            cpu_cores=psutil.cpu_count(),
            memory_gb=memory.total / (1024**3),
            available_memory_gb=memory.available / (1024**3),
            cpu_usage_percent=psutil.cpu_percent(interval=1),
            disk_space_gb=disk.free / (1024**3),
        )

        self.log.info(
            f"System resources: {resources.cpu_cores} cores, "
            f"{resources.memory_gb:.1f}GB RAM, "
            f"{resources.available_memory_gb:.1f}GB available"
        )

        return resources

    def optimize_mesh_parameters(self, geometry_complexity: float) -> Dict:
        """Optimize mesh parameters based on system resources and geometry"""
        resources = self.analyze_system_resources()

        # Calculate optimal refinement levels based on available resources
        memory_factor = min(resources.available_memory_gb / 8.0, 2.0)  # Scale based on 8GB baseline
        cpu_factor = min(resources.cpu_cores / 4.0, 4.0)  # Scale based on 4-core baseline

        # Base refinement levels
        base_refinement = 2
        surface_refinement = base_refinement + int(memory_factor)
        region_refinement = max(1, surface_refinement - 1)

        # Adjust for geometry complexity
        if geometry_complexity > 0.8:  # Complex geometry
            surface_refinement += 1
            region_refinement += 1
        elif geometry_complexity < 0.3:  # Simple geometry
            surface_refinement = max(1, surface_refinement - 1)

        optimized_params = {
            "regionRefinementLevel": region_refinement,
            "surfaceRefinementLevels": [region_refinement, surface_refinement],
            "featureLevel": surface_refinement,
            "nCellsBetweenLevels": max(2, int(cpu_factor)),
            "parallel": resources.cpu_cores > 2,
            "nProcessors": min(resources.cpu_cores, max(2, int(cpu_factor * 2))),
        }

        self.log.info(f"Optimized mesh parameters: {optimized_params}")
        return optimized_params

    def optimize_solver_parameters(self, case_size: str = "medium") -> Dict:
        """Optimize solver parameters for convergence and stability"""
        resources = self.analyze_system_resources()

        # Memory-based optimization
        if resources.available_memory_gb < 4:
            # Low memory - prioritize stability
            params = {
                "nOuterCorrectors": 2,
                "nCorrectors": 1,
                "nNonOrthogonalCorrectors": 0,
                "relaxationFactors": {"p": 0.3, "U": 0.5, "k": 0.6, "omega": 0.6},
            }
        elif resources.available_memory_gb > 16:
            # High memory - prioritize accuracy
            params = {
                "nOuterCorrectors": 5,
                "nCorrectors": 3,
                "nNonOrthogonalCorrectors": 2,
                "relaxationFactors": {"p": 0.7, "U": 0.8, "k": 0.8, "omega": 0.8},
            }
        else:
            # Medium memory - balanced approach
            params = {
                "nOuterCorrectors": 3,
                "nCorrectors": 2,
                "nNonOrthogonalCorrectors": 1,
                "relaxationFactors": {"p": 0.5, "U": 0.7, "k": 0.7, "omega": 0.7},
            }

        # Adjust time step based on case size
        time_step_factors = {"coarse": 0.001, "medium": 0.0005, "fine": 0.0001}
        params["deltaT"] = time_step_factors.get(case_size, 0.0005)

        self.log.info(f"Optimized solver parameters for {case_size} case: {params}")
        return params

    def predict_simulation_time(self, mesh_size: int, time_steps: int) -> float:
        """Predict simulation time based on historical data and current resources"""
        if not self.simulation_history:
            # No history - use conservative estimate
            base_time_per_cell_per_step = 1e-6  # seconds
            return mesh_size * time_steps * base_time_per_cell_per_step

        # Use machine learning-like approach with historical data
        similar_cases = [case for case in self.simulation_history if abs(case.mesh_size - mesh_size) / mesh_size < 0.5]

        if similar_cases:
            avg_efficiency = np.mean([case.cpu_efficiency for case in similar_cases])
            time_per_step = np.mean([case.convergence_time / case.time_steps for case in similar_cases])
            predicted_time = time_steps * time_per_step / avg_efficiency
        else:
            # Fallback to simple scaling
            predicted_time = mesh_size * time_steps * 1e-6

        self.log.info(f"Predicted simulation time: {predicted_time:.1f} seconds")
        return predicted_time

    def optimize_parallelization(self, mesh_size: int) -> Dict:
        """Optimize parallel decomposition strategy"""
        resources = self.analyze_system_resources()

        # Calculate optimal number of processors
        cells_per_processor = 50000  # Target cells per processor
        optimal_processors = max(1, min(resources.cpu_cores, mesh_size // cells_per_processor))

        # Choose decomposition method
        if optimal_processors <= 4:
            method = "simple"
            coeffs = [optimal_processors, 1, 1]
        elif optimal_processors <= 16:
            method = "hierarchical"
            # Try to make a roughly cubic decomposition
            n = int(np.ceil(optimal_processors ** (1 / 3)))
            coeffs = [n, n, max(1, optimal_processors // (n * n))]
        else:
            method = "scotch"  # Let scotch handle complex decompositions
            coeffs = None

        decomposition = {
            "numberOfSubdomains": optimal_processors,
            "method": method,
            "coeffs": coeffs if coeffs else [1, 1, optimal_processors],
            "distributed": optimal_processors > resources.cpu_cores // 2,
        }

        self.log.info(f"Optimized parallelization: {decomposition}")
        return decomposition


class ResourceMonitor:
    """Real-time resource monitoring during simulation"""

    def __init__(self):
        self.log = logger
        self.monitoring = False

    def start_monitoring(self, interval: float = 30.0):
        """Start resource monitoring with specified interval"""
        self.monitoring = True
        self.log.info(f"Starting resource monitoring (interval: {interval}s)")

    def stop_monitoring(self):
        """Stop resource monitoring"""
        self.monitoring = False
        self.log.info("Stopped resource monitoring")

    def get_current_usage(self) -> Dict:
        """Get current resource usage"""
        memory = psutil.virtual_memory()

        usage = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": memory.percent,
            "memory_used_gb": (memory.total - memory.available) / (1024**3),
            "disk_io": psutil.disk_io_counters()._asdict() if psutil.disk_io_counters() else {},
            "network_io": psutil.net_io_counters()._asdict() if psutil.net_io_counters() else {},
            "timestamp": time.time(),
        }

        return usage

    def check_resource_limits(self, thresholds: Dict) -> List[str]:
        """Check if resource usage exceeds thresholds"""
        usage = self.get_current_usage()
        warnings = []

        if usage["cpu_percent"] > thresholds.get("cpu_percent", 90):
            warnings.append(f"High CPU usage: {usage['cpu_percent']:.1f}%")

        if usage["memory_percent"] > thresholds.get("memory_percent", 85):
            warnings.append(f"High memory usage: {usage['memory_percent']:.1f}%")

        return warnings


class AdaptiveTimestepping:
    """Adaptive time stepping for improved convergence"""

    def __init__(self, initial_dt: float = 0.001):
        self.dt = initial_dt
        self.dt_min = initial_dt * 0.1
        self.dt_max = initial_dt * 10.0
        self.convergence_history = []
        self.log = logger

    def adjust_timestep(self, residuals: Dict[str, float]) -> float:
        """Adjust time step based on convergence behavior"""
        max_residual = max(residuals.values())

        # Record convergence history
        self.convergence_history.append(max_residual)

        # Keep only last 10 iterations
        if len(self.convergence_history) > 10:
            self.convergence_history.pop(0)

        # Adjust time step based on convergence trend
        if len(self.convergence_history) >= 3:
            recent_trend = np.polyfit(range(3), self.convergence_history[-3:], 1)[0]

            if recent_trend < -0.1:  # Good convergence
                self.dt = min(self.dt * 1.1, self.dt_max)
            elif recent_trend > 0.1:  # Poor convergence
                self.dt = max(self.dt * 0.8, self.dt_min)

        self.log.debug(f"Adjusted time step to: {self.dt}")
        return self.dt


def create_performance_report(
    optimizer: PerformanceOptimizer, simulation_time: float, final_residuals: Dict[str, float]
) -> Dict:
    """Create a comprehensive performance report"""
    resources = optimizer.analyze_system_resources()

    report = {
        "simulation_time": simulation_time,
        "final_residuals": final_residuals,
        "system_resources": resources.__dict__,
        "resource_efficiency": {
            "cpu_utilization": 100 - resources.cpu_usage_percent,
            "memory_utilization": resources.memory_gb - resources.available_memory_gb,
            "convergence_quality": min(final_residuals.values()) if final_residuals else 1.0,
        },
        "recommendations": [],
    }

    # Generate recommendations
    if resources.available_memory_gb < 2:
        report["recommendations"].append("Consider increasing system memory for better performance")

    if resources.cpu_usage_percent < 50:
        report["recommendations"].append("CPU underutilized - consider increasing mesh resolution")

    if final_residuals and min(final_residuals.values()) > 1e-4:
        report["recommendations"].append("Poor convergence - consider adjusting solver parameters")

    return report
