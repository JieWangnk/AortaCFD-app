"""
Y+ Estimator for Boundary Layer Mesh Generation

This module provides utilities to estimate the first layer thickness (finalLayerThickness)
required to achieve a target y+ value in OpenFOAM simulations.

The estimator uses empirical correlations to predict wall shear stress before simulation,
allowing for appropriate boundary layer mesh sizing during the mesh generation phase.
"""

import math
import logging
from typing import Dict, Optional, Literal

logger = logging.getLogger(__name__)


class YPlusEstimator:
    """
    Estimates first layer thickness for boundary layer mesh generation based on target y+.

    The estimation uses pipe flow correlations to predict wall shear stress:
    - Laminar flow: f = 64/Re
    - Turbulent flow: f = 0.316/Re^0.25 (Blasius correlation)

    Where:
        y+ = (Δy × u_τ) / ν
        u_τ = U_mean × √(f/8)  (friction velocity)
        f = friction factor

    Therefore:
        Δy = y+_target × ν / u_τ
    """

    def __init__(
        self,
        density: float,
        viscosity: float,
        flow_regime: Literal['auto', 'laminar', 'turbulent'] = 'auto'
    ):
        """
        Initialize the Y+ estimator.

        Args:
            density: Fluid density (kg/m³), typically 1060 for blood
            viscosity: Dynamic viscosity (Pa·s), typically 0.004 for blood
            flow_regime: Flow regime assumption ('auto', 'laminar', 'turbulent')
        """
        self.rho = density
        self.mu = viscosity
        self.nu = viscosity / density  # Kinematic viscosity
        self.flow_regime = flow_regime

    def estimate_first_layer_thickness(
        self,
        target_yplus: float,
        mean_velocity: float,
        characteristic_length: float,
        n_layers: int = 5,
        expansion_ratio: float = 1.2
    ) -> Dict[str, float]:
        """
        Estimate the first layer thickness to achieve target y+.

        Args:
            target_yplus: Target y+ value (e.g., 1.0 for RANS, 30 for wall functions)
            mean_velocity: Characteristic velocity (m/s), e.g., mean inlet velocity
            characteristic_length: Characteristic length (m), e.g., hydraulic diameter
            n_layers: Number of boundary layers (default: 5)
            expansion_ratio: Layer expansion ratio (default: 1.2)

        Returns:
            Dictionary containing:
                - finalLayerThickness: Recommended value for snappyHexMesh
                - estimated_yplus: Expected y+ with this layer thickness
                - reynolds_number: Flow Reynolds number
                - friction_velocity: Estimated u_τ (m/s)
                - total_layer_thickness: Total boundary layer thickness (m)
                - flow_regime: Detected flow regime ('laminar' or 'turbulent')
                - friction_factor: Estimated friction factor
        """
        # Calculate Reynolds number
        Re = self.rho * mean_velocity * characteristic_length / self.mu

        # Determine flow regime
        if self.flow_regime == 'auto':
            if Re < 2300:
                regime = 'laminar'
            elif Re > 4000:
                regime = 'turbulent'
            else:
                regime = 'transitional'
                logger.warning(
                    f"Flow is transitional (Re={Re:.0f}). "
                    f"Results may be less accurate. Consider explicit regime specification."
                )
        else:
            regime = self.flow_regime

        # Calculate friction factor using empirical correlations
        if regime == 'laminar':
            f = 64.0 / Re
        else:  # turbulent or transitional
            # Blasius correlation for smooth pipes (valid for Re < 100,000)
            if Re < 100000:
                f = 0.316 / (Re ** 0.25)
            else:
                # Prandtl-Karman correlation for higher Re
                f = 0.0032 + 0.221 / (Re ** 0.237)

        # Calculate friction velocity
        u_tau = mean_velocity * math.sqrt(f / 8.0)

        # Calculate first layer thickness for target y+
        # y+ = (Δy × u_τ) / ν  →  Δy = y+ × ν / u_τ
        delta_y1 = target_yplus * self.nu / u_tau

        # Calculate total boundary layer thickness
        # Δ_total = Δy₁ × (r^n - 1) / (r - 1)
        if expansion_ratio > 1.0:
            total_bl_thickness = delta_y1 * (expansion_ratio**n_layers - 1) / (expansion_ratio - 1)
        else:
            total_bl_thickness = delta_y1 * n_layers

        # Verify the calculation (should return target_yplus)
        estimated_yplus = delta_y1 * u_tau / self.nu

        return {
            'firstLayerThickness': delta_y1,  # CORRECT: innermost layer (wall-adjacent) for y+ control
            'estimated_yplus': estimated_yplus,
            'reynolds_number': Re,
            'friction_velocity': u_tau,
            'total_layer_thickness': total_bl_thickness,
            'flow_regime': regime,
            'friction_factor': f
        }

    def validate_settings(
        self,
        first_layer_thickness: float,
        total_layer_thickness: float,
        characteristic_length: float,
        solver_type: str,
        reynolds_number: float
    ) -> Dict[str, list]:
        """
        Validate boundary layer settings and provide warnings if needed.

        Args:
            first_layer_thickness: Calculated Δy₁
            total_layer_thickness: Total BL thickness
            characteristic_length: Vessel diameter/hydraulic diameter
            solver_type: Solver type ('laminar', 'RANS', 'LES')
            reynolds_number: Flow Reynolds number

        Returns:
            Dictionary with 'warnings' and 'recommendations' lists
        """
        warnings = []
        recommendations = []

        # Check if total BL thickness is too large relative to vessel size
        bl_ratio = total_layer_thickness / characteristic_length
        if bl_ratio > 0.5:
            warnings.append(
                f"Total boundary layer thickness ({total_layer_thickness*1000:.2f} mm) is "
                f"{bl_ratio*100:.1f}% of characteristic length. "
                f"Consider reducing nSurfaceLayers or expansionRatio."
            )

        # Check solver type vs Reynolds number
        if solver_type.lower() == 'laminar' and reynolds_number > 4000:
            warnings.append(
                f"Using laminar solver with Re={reynolds_number:.0f} (turbulent regime). "
                f"Consider using RANS or LES solver."
            )

        if solver_type.upper() in ['RANS', 'LES'] and reynolds_number < 2300:
            warnings.append(
                f"Using {solver_type} solver with Re={reynolds_number:.0f} (laminar regime). "
                f"Consider using laminar solver."
            )

        # Recommend layer settings based on first layer thickness
        if first_layer_thickness < 1e-5:  # < 0.01 mm
            warnings.append(
                f"First layer thickness ({first_layer_thickness*1e6:.1f} µm) is very small. "
                f"This may cause mesh quality issues or require very fine background mesh."
            )
            recommendations.append("Consider using wall functions (y+ ~ 30-100) instead")

        if first_layer_thickness > 1e-3:  # > 1 mm
            warnings.append(
                f"First layer thickness ({first_layer_thickness*1000:.2f} mm) is large. "
                f"May not resolve near-wall gradients adequately."
            )

        return {
            'warnings': warnings,
            'recommendations': recommendations
        }

    def print_report(
        self,
        results: Dict[str, float],
        target_yplus: float,
        n_layers: int = 5,
        expansion_ratio: float = 1.2,
        solver_type: str = 'RANS',
        characteristic_length: Optional[float] = None
    ) -> None:
        """
        Print a formatted report of the y+ estimation results.

        Args:
            results: Output from estimate_first_layer_thickness()
            target_yplus: Target y+ value used
            n_layers: Number of boundary layers
            expansion_ratio: Layer expansion ratio
            solver_type: Solver type for validation
            characteristic_length: For validation warnings
        """
        print("\n" + "="*60)
        print("Y+ ESTIMATOR RESULTS")
        print("="*60)
        print(f"Target y+:                  {target_yplus:.2f}")
        print(f"Estimated mean velocity:    {results['reynolds_number']*self.nu/characteristic_length:.3f} m/s" if characteristic_length else "")
        print(f"Reynolds number:            {results['reynolds_number']:.0f} ({results['flow_regime'].capitalize()})")
        print(f"Friction factor (f):        {results['friction_factor']:.6f}")
        print(f"Friction velocity (u_τ):    {results['friction_velocity']:.4f} m/s")
        print("-"*60)
        print("RECOMMENDED MESH SETTINGS:")
        print("-"*60)
        print(f"  finalLayerThickness:      {results['finalLayerThickness']:.6f}  ({results['finalLayerThickness']*1000:.4f} mm)")
        print(f"  nSurfaceLayers:           {n_layers}")
        print(f"  expansionRatio:           {expansion_ratio}")
        print(f"  Total BL thickness:       {results['total_layer_thickness']*1000:.4f} mm")
        print(f"  Estimated y+:             {results['estimated_yplus']:.2f}")
        print("-"*60)

        # Validation
        if characteristic_length:
            validation = self.validate_settings(
                results['finalLayerThickness'],
                results['total_layer_thickness'],
                characteristic_length,
                solver_type,
                results['reynolds_number']
            )

            if validation['warnings']:
                print("⚠️  WARNINGS:")
                for warning in validation['warnings']:
                    print(f"  - {warning}")
            else:
                print("✓ Settings appear reasonable for", solver_type)

            if validation['recommendations']:
                print("\n💡 RECOMMENDATIONS:")
                for rec in validation['recommendations']:
                    print(f"  - {rec}")

        print("="*60)
        print("Note: These estimates use pipe flow correlations.")
        print("Verify actual y+ using post-processing after simulation.")
        print("="*60 + "\n")


def estimate_from_config(config: dict, target_yplus: float) -> Dict[str, float]:
    """
    Convenience function to estimate y+ parameters directly from config dict.

    Args:
        config: Configuration dictionary with physics and boundary_conditions
        target_yplus: Target y+ value

    Returns:
        Estimation results dictionary
    """
    # Extract fluid properties
    density = config['physics']['blood_density']
    viscosity = config['physics']['blood_viscosity']

    # Determine solver type
    solver_type = config.get('simulation_settings', {}).get('solver_type', 'laminar')

    # Create estimator
    estimator = YPlusEstimator(
        density=density,
        viscosity=viscosity,
        flow_regime='auto'
    )

    # For now, use typical aortic values if not specified
    # TODO: Extract from actual geometry/inlet conditions
    mean_velocity = config.get('estimation_params', {}).get('characteristic_velocity', 0.5)
    char_length = config.get('estimation_params', {}).get('characteristic_length', 0.025)

    # Get layer settings
    mesh_config = config.get('mesh', {}).get('SNAPPY_SETTINGS', {})
    n_layers = mesh_config.get('addLayer', 5)
    expansion_ratio = mesh_config.get('expansionRatio', 1.2)

    results = estimator.estimate_first_layer_thickness(
        target_yplus=target_yplus,
        mean_velocity=mean_velocity,
        characteristic_length=char_length,
        n_layers=n_layers,
        expansion_ratio=expansion_ratio
    )

    return results


if __name__ == '__main__':
    """
    CLI utility for manual y+ calculations.

    Example:
        python -m src.aortacfd_lib.yplus_estimator --target-yplus 1.0 --velocity 0.5 --diameter 0.025
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Estimate first layer thickness for target y+ value',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('--target-yplus', type=float, required=True,
                        help='Target y+ value (e.g., 1.0 for RANS, 30 for wall functions)')
    parser.add_argument('--velocity', type=float, required=True,
                        help='Characteristic velocity in m/s (e.g., mean inlet velocity)')
    parser.add_argument('--diameter', type=float, required=True,
                        help='Characteristic length in m (e.g., hydraulic diameter)')
    parser.add_argument('--density', type=float, default=1060.0,
                        help='Fluid density in kg/m³')
    parser.add_argument('--viscosity', type=float, default=0.004,
                        help='Dynamic viscosity in Pa·s')
    parser.add_argument('--n-layers', type=int, default=5,
                        help='Number of boundary layers')
    parser.add_argument('--expansion-ratio', type=float, default=1.2,
                        help='Layer expansion ratio')
    parser.add_argument('--solver-type', type=str, default='RANS',
                        choices=['laminar', 'RANS', 'LES'],
                        help='Solver type for validation')
    parser.add_argument('--regime', type=str, default='auto',
                        choices=['auto', 'laminar', 'turbulent'],
                        help='Flow regime (auto-detect by default)')

    args = parser.parse_args()

    # Create estimator
    estimator = YPlusEstimator(
        density=args.density,
        viscosity=args.viscosity,
        flow_regime=args.regime
    )

    # Estimate
    results = estimator.estimate_first_layer_thickness(
        target_yplus=args.target_yplus,
        mean_velocity=args.velocity,
        characteristic_length=args.diameter,
        n_layers=args.n_layers,
        expansion_ratio=args.expansion_ratio
    )

    # Print report
    estimator.print_report(
        results=results,
        target_yplus=args.target_yplus,
        n_layers=args.n_layers,
        expansion_ratio=args.expansion_ratio,
        solver_type=args.solver_type,
        characteristic_length=args.diameter
    )
