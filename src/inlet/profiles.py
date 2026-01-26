# src/inlet/profiles.py
"""
Velocity profile calculations for inlet boundary conditions.

Supported profiles:
- Plug (uniform): U(r) = U_mean
- Parabolic: U(r) = 2 * U_mean * (1 - (r/R)^2)
- Womersley: Analytical solution for pulsatile flow

Usage:
    from src.inlet.profiles import create_profile, ParabolicProfile

    # Create profile
    profile = create_profile('parabolic', center, radius, normal)

    # Calculate velocity at a point
    velocity = profile.calculate(point, mean_velocity)
"""

import numpy as np
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Union
import logging

logger = logging.getLogger(__name__)


class VelocityProfile(ABC):
    """
    Base class for inlet velocity profiles.

    Attributes:
        center: Inlet center point (x, y, z)
        radius: Inlet radius (m)
        normal: Inlet normal vector (pointing inward)
    """

    def __init__(
        self,
        center: np.ndarray,
        radius: float,
        normal: np.ndarray,
    ):
        """
        Initialize velocity profile.

        Args:
            center: Inlet center point (x, y, z)
            radius: Inlet radius (m)
            normal: Inlet normal vector (should point INTO domain)
        """
        self.center = np.asarray(center)
        self.radius = radius
        self.normal = np.asarray(normal)

        # Normalize the normal vector
        norm = np.linalg.norm(self.normal)
        if norm > 0:
            self.normal = self.normal / norm

    @abstractmethod
    def calculate(
        self,
        point: np.ndarray,
        mean_velocity: float,
    ) -> np.ndarray:
        """
        Calculate velocity vector at a point.

        Args:
            point: Position (x, y, z)
            mean_velocity: Mean inlet velocity (m/s)

        Returns:
            Velocity vector (vx, vy, vz)
        """
        pass

    def calculate_batch(
        self,
        points: np.ndarray,
        mean_velocity: float,
    ) -> np.ndarray:
        """
        Calculate velocity vectors for multiple points.

        Args:
            points: Array of positions (N, 3)
            mean_velocity: Mean inlet velocity (m/s)

        Returns:
            Array of velocity vectors (N, 3)
        """
        return np.array([
            self.calculate(point, mean_velocity)
            for point in points
        ])

    def get_radial_distance(self, point: np.ndarray) -> float:
        """
        Calculate radial distance from center to point.

        Args:
            point: Position (x, y, z)

        Returns:
            Radial distance (m)
        """
        # Vector from center to point
        r_vec = np.asarray(point) - self.center

        # Remove component along normal (project onto inlet plane)
        r_vec = r_vec - np.dot(r_vec, self.normal) * self.normal

        return np.linalg.norm(r_vec)

    def get_normalized_radius(self, point: np.ndarray) -> float:
        """
        Get normalized radial position (r/R).

        Args:
            point: Position (x, y, z)

        Returns:
            Normalized radius (0 at center, 1 at wall)
        """
        r = self.get_radial_distance(point)
        return min(r / self.radius, 1.0)


class PlugProfile(VelocityProfile):
    """
    Uniform (plug) velocity profile.

    U(r) = U_mean in direction of normal

    Simple flat profile, good for:
    - Quick tests
    - When inlet profile doesn't matter much
    - Far from region of interest
    """

    def calculate(
        self,
        point: np.ndarray,
        mean_velocity: float,
    ) -> np.ndarray:
        """Calculate uniform velocity."""
        return mean_velocity * self.normal


class ParabolicProfile(VelocityProfile):
    """
    Parabolic (Poiseuille) velocity profile.

    U(r) = 2 * U_mean * (1 - (r/R)^2)

    Analytical solution for fully-developed laminar pipe flow.
    Peak velocity at center = 2 * mean velocity.
    """

    def calculate(
        self,
        point: np.ndarray,
        mean_velocity: float,
    ) -> np.ndarray:
        """Calculate parabolic velocity."""
        # Normalized radial position
        r_norm = self.get_normalized_radius(point)

        # Parabolic profile: U = 2 * U_mean * (1 - (r/R)^2)
        # Factor of 2 ensures mean velocity is preserved
        velocity_magnitude = 2.0 * mean_velocity * (1.0 - r_norm ** 2)

        return velocity_magnitude * self.normal


class WomersleyProfile(VelocityProfile):
    """
    Womersley velocity profile for pulsatile flow.

    Analytical solution for oscillatory flow in a rigid tube.
    Uses Bessel functions to compute velocity distribution.

    The profile depends on:
    - Womersley number: alpha = R * sqrt(omega / nu)
    - Oscillation frequency: omega = 2*pi/T

    For low alpha (< 1): profile is quasi-parabolic
    For high alpha (> 10): profile is nearly flat (plug-like)
    """

    def __init__(
        self,
        center: np.ndarray,
        radius: float,
        normal: np.ndarray,
        nu: float = 3.774e-6,
        cardiac_cycle: float = 1.0,
    ):
        """
        Initialize Womersley profile.

        Args:
            center: Inlet center point
            radius: Inlet radius (m)
            normal: Inlet normal vector
            nu: Kinematic viscosity (m²/s)
            cardiac_cycle: Cardiac cycle period (s)
        """
        super().__init__(center, radius, normal)
        self.nu = nu
        self.cardiac_cycle = cardiac_cycle

        # Calculate Womersley number
        omega = 2 * np.pi / cardiac_cycle
        self.alpha = radius * np.sqrt(omega / nu)

        logger.debug(f"Womersley number: {self.alpha:.2f}")

    def calculate(
        self,
        point: np.ndarray,
        mean_velocity: float,
        phase: float = 0.0,
    ) -> np.ndarray:
        """
        Calculate Womersley velocity.

        For simplicity, this returns a modified parabolic profile
        that approximates Womersley behavior. For full Womersley,
        use calculate_full().

        Args:
            point: Position (x, y, z)
            mean_velocity: Instantaneous mean velocity (m/s)
            phase: Phase angle (radians), not used in simplified version

        Returns:
            Velocity vector (vx, vy, vz)
        """
        # Normalized radial position
        r_norm = self.get_normalized_radius(point)

        # Modified parabolic that accounts for Womersley number
        # For low alpha: behaves like parabolic
        # For high alpha: behaves like plug
        if self.alpha < 2:
            # Quasi-parabolic regime
            velocity_magnitude = 2.0 * mean_velocity * (1.0 - r_norm ** 2)
        elif self.alpha > 10:
            # Plug-like regime
            velocity_magnitude = mean_velocity
        else:
            # Transition: blend between parabolic and plug
            blend = (self.alpha - 2) / 8  # 0 at alpha=2, 1 at alpha=10
            parabolic = 2.0 * mean_velocity * (1.0 - r_norm ** 2)
            plug = mean_velocity
            velocity_magnitude = (1 - blend) * parabolic + blend * plug

        return velocity_magnitude * self.normal

    def calculate_full(
        self,
        point: np.ndarray,
        flow_harmonics: np.ndarray,
        time: float,
    ) -> np.ndarray:
        """
        Calculate full Womersley velocity using Fourier decomposition.

        This uses the full analytical Womersley solution with Bessel functions.

        Args:
            point: Position (x, y, z)
            flow_harmonics: Complex Fourier coefficients of flow waveform
            time: Current time (s)

        Returns:
            Velocity vector (vx, vy, vz)
        """
        try:
            from scipy.special import jv  # Bessel function
        except ImportError:
            logger.warning("scipy not available, using simplified Womersley")
            return self.calculate(point, np.abs(flow_harmonics[0]))

        r_norm = self.get_normalized_radius(point)
        eta = r_norm  # Normalized radius

        omega = 2 * np.pi / self.cardiac_cycle
        velocity = 0.0

        for n, Q_n in enumerate(flow_harmonics):
            if n == 0:
                # Steady component (parabolic)
                velocity += 2.0 * np.real(Q_n) * (1.0 - eta ** 2)
            else:
                # Oscillatory components
                omega_n = n * omega
                alpha_n = self.radius * np.sqrt(omega_n / self.nu)

                # Bessel function argument
                i_sqrt = np.sqrt(1j)
                arg_R = alpha_n * i_sqrt
                arg_r = alpha_n * i_sqrt * eta

                # Womersley velocity profile
                J0_R = jv(0, arg_R)
                J0_r = jv(0, arg_r)

                if np.abs(J0_R) > 1e-10:
                    profile = 1.0 - J0_r / J0_R
                    velocity += np.real(Q_n * profile * np.exp(1j * n * omega * time))

        return velocity * self.normal


class WallDistanceProfile(VelocityProfile):
    """
    Wall-distance-based velocity profile.

    Velocity varies based on distance from the wall, useful for
    non-circular inlets or when wall-bounded behavior is important.

    U(d) = U_max * f(d/d_max)

    where d is distance from nearest wall and f is a shape function.
    """

    def __init__(
        self,
        center: np.ndarray,
        radius: float,
        normal: np.ndarray,
        wall_distances: Optional[np.ndarray] = None,
        points: Optional[np.ndarray] = None,
    ):
        """
        Initialize wall-distance profile.

        Args:
            center: Inlet center point
            radius: Characteristic radius
            normal: Inlet normal vector
            wall_distances: Pre-computed wall distances for each point
            points: Corresponding point coordinates
        """
        super().__init__(center, radius, normal)
        self.wall_distances = wall_distances
        self.points = points
        self._distance_map = None

        if wall_distances is not None and points is not None:
            self._build_distance_map()

    def _build_distance_map(self):
        """Build lookup for wall distances."""
        if self.points is None or self.wall_distances is None:
            return

        from scipy.spatial import KDTree
        self._kdtree = KDTree(self.points)
        self._distance_map = dict(zip(
            [tuple(p) for p in self.points],
            self.wall_distances
        ))

    def calculate(
        self,
        point: np.ndarray,
        mean_velocity: float,
    ) -> np.ndarray:
        """Calculate wall-distance-based velocity."""
        point_tuple = tuple(point)

        if self._distance_map and point_tuple in self._distance_map:
            wall_dist = self._distance_map[point_tuple]
        elif hasattr(self, '_kdtree'):
            # Find nearest point
            _, idx = self._kdtree.query(point)
            wall_dist = self.wall_distances[idx]
        else:
            # Fall back to radial distance approximation
            wall_dist = self.radius - self.get_radial_distance(point)

        # Normalize wall distance
        max_dist = self.radius  # Approximate max distance
        d_norm = min(wall_dist / max_dist, 1.0)

        # Profile shape: parabolic-like based on wall distance
        # U = 2 * U_mean * d_norm * (2 - d_norm)
        # This gives U=0 at wall (d_norm=0), U_max at center
        velocity_magnitude = 2.0 * mean_velocity * d_norm * (2.0 - d_norm)

        return velocity_magnitude * self.normal


def create_profile(
    profile_type: str,
    center: np.ndarray,
    radius: float,
    normal: np.ndarray,
    **kwargs,
) -> VelocityProfile:
    """
    Factory function to create velocity profile.

    Args:
        profile_type: Profile type ('plug', 'parabolic', 'womersley', 'wall_distance')
        center: Inlet center point
        radius: Inlet radius
        normal: Inlet normal vector
        **kwargs: Additional arguments for specific profiles

    Returns:
        VelocityProfile instance
    """
    profile_type = profile_type.lower()

    if profile_type in ['plug', 'uniform', 'flat']:
        return PlugProfile(center, radius, normal)

    elif profile_type in ['parabolic', 'poiseuille', 'laminar']:
        return ParabolicProfile(center, radius, normal)

    elif profile_type in ['womersley', 'pulsatile']:
        nu = kwargs.get('nu', 3.774e-6)
        cardiac_cycle = kwargs.get('cardiac_cycle', 1.0)
        return WomersleyProfile(center, radius, normal, nu, cardiac_cycle)

    elif profile_type in ['wall_distance', 'wall']:
        wall_distances = kwargs.get('wall_distances')
        points = kwargs.get('points')
        return WallDistanceProfile(center, radius, normal, wall_distances, points)

    else:
        logger.warning(f"Unknown profile type '{profile_type}', using plug")
        return PlugProfile(center, radius, normal)
