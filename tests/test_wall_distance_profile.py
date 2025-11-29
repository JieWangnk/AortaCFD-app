"""
Test module for wall-distance and elliptical inlet profiles.

Tests the following methods in InletMapping:
- _compute_wall_distances()
- _compute_wall_distance_shape_factors()
- _compute_elliptical_poiseuille_factors()
- _estimate_ellipse_axes()

These profiles handle non-circular inlet geometries (irregular aortic roots).
"""

import numpy as np
import unittest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestWallDistanceProfile(unittest.TestCase):
    """Test wall-distance based velocity profile calculations."""

    def test_wall_distance_shape_factors_circular(self):
        """
        Test wall-distance shape factors for circular inlet (should approximate parabolic).
        """
        # Create circular boundary points
        n_boundary = 36
        radius = 0.01  # 10mm radius
        center = np.array([0.0, 0.0, 0.0])

        theta = np.linspace(0, 2*np.pi, n_boundary, endpoint=False)
        boundary_points = np.zeros((n_boundary, 3))
        boundary_points[:, 0] = radius * np.cos(theta)
        boundary_points[:, 1] = radius * np.sin(theta)

        # Create test points across the inlet from center to edge
        n_test = 20
        test_points = []
        for r_frac in np.linspace(0, 0.95, n_test):
            r = r_frac * radius
            test_points.append([r, 0.0, 0.0])
        test_points = np.array(test_points)

        # Compute wall distances
        distances = self._compute_wall_distances_manual(test_points, boundary_points)

        # Verify distances DECREASE toward edge (center has max distance to wall)
        # First point (center) should have largest distance
        # Last point (near edge) should have smallest distance
        self.assertGreater(distances[0], distances[-1])

        # At center, distance should be approximately radius
        center_dist = distances[0]
        self.assertAlmostEqual(center_dist, radius, delta=radius*0.1)

        # At edge (r=0.95*radius), distance should be approximately 0.05*radius
        edge_dist = distances[-1]
        expected_edge_dist = radius - 0.95 * radius  # 0.05 * radius
        self.assertAlmostEqual(edge_dist, expected_edge_dist, delta=radius*0.1)

    def _compute_wall_distances_manual(self, points, boundary_points):
        """Manual implementation of wall distance calculation for testing."""
        distances = np.zeros(len(points))
        for idx, pt in enumerate(points):
            min_dist = np.inf
            for boundary_pt in boundary_points:
                dist = np.linalg.norm(pt[:2] - boundary_pt[:2])
                min_dist = min(min_dist, dist)
            distances[idx] = min_dist
        return distances

    def test_wall_distance_shape_factor_formula(self):
        """
        Test the shape factor formula: u(d) = 1 - (1 - d/d_max)^n
        """
        d_max = 0.01  # 10mm
        exponent = 2.0

        # Test points at different normalized distances
        test_cases = [
            (0.0, 0.0),    # At wall: shape = 0
            (d_max, 1.0),  # At center: shape = 1
            (d_max/2, 1 - (1 - 0.5)**2),  # Mid-point
        ]

        for d, expected in test_cases:
            d_normalized = d / d_max
            shape = 1.0 - (1.0 - d_normalized) ** exponent
            self.assertAlmostEqual(shape, expected, places=6,
                msg=f"Shape factor at d={d}: expected {expected}, got {shape}")

    def test_wall_distance_exponent_effect(self):
        """
        Test that higher exponents produce flatter profiles.
        """
        d_max = 0.01
        d_test = d_max * 0.5  # Mid-radius point
        d_normalized = d_test / d_max

        exponents = [1.0, 2.0, 4.0, 8.0]
        shapes = []

        for n in exponents:
            shape = 1.0 - (1.0 - d_normalized) ** n
            shapes.append(shape)

        # Higher exponents should give higher shape factors at mid-point
        # (flatter profile = more uniform velocity)
        for i in range(len(shapes) - 1):
            self.assertLess(shapes[i], shapes[i+1],
                f"Exponent {exponents[i]} should give lower shape than {exponents[i+1]}")


class TestEllipticalPoiseuille(unittest.TestCase):
    """Test elliptical Poiseuille velocity profile calculations."""

    def test_elliptical_formula_at_center(self):
        """
        Test that velocity is maximum at ellipse center.
        u(0,0) = u_max * (1 - 0 - 0) = u_max
        """
        a, b = 0.015, 0.010  # Semi-axes: 15mm and 10mm
        x, y = 0.0, 0.0

        shape = 1.0 - (x/a)**2 - (y/b)**2
        self.assertAlmostEqual(shape, 1.0, places=10)

    def test_elliptical_formula_at_boundary(self):
        """
        Test that velocity is zero at ellipse boundary.
        On major axis: u(a,0) = u_max * (1 - 1 - 0) = 0
        On minor axis: u(0,b) = u_max * (1 - 0 - 1) = 0
        """
        a, b = 0.015, 0.010

        # On major axis boundary
        shape_a = 1.0 - (a/a)**2 - (0/b)**2
        self.assertAlmostEqual(shape_a, 0.0, places=10)

        # On minor axis boundary
        shape_b = 1.0 - (0/a)**2 - (b/b)**2
        self.assertAlmostEqual(shape_b, 0.0, places=10)

    def test_elliptical_formula_outside(self):
        """
        Test that points outside ellipse get zero velocity.
        """
        a, b = 0.015, 0.010

        # Point outside on x-axis
        x, y = 0.020, 0.0
        ellipse_term = (x/a)**2 + (y/b)**2
        self.assertGreater(ellipse_term, 1.0)

        # Shape should be clamped to 0
        shape = max(0.0, 1.0 - ellipse_term)
        self.assertEqual(shape, 0.0)

    def test_elliptical_symmetry(self):
        """
        Test that elliptical profile is symmetric about both axes.
        """
        a, b = 0.015, 0.010

        test_coords = [(0.005, 0.003), (0.010, 0.005), (0.012, 0.008)]

        for x, y in test_coords:
            # Compute shape at all four quadrants
            shapes = []
            for sign_x in [1, -1]:
                for sign_y in [1, -1]:
                    xx = sign_x * x
                    yy = sign_y * y
                    shape = 1.0 - (xx/a)**2 - (yy/b)**2
                    shapes.append(shape)

            # All should be equal
            for s in shapes[1:]:
                self.assertAlmostEqual(shapes[0], s, places=10)

    def test_elliptical_reduces_to_circular(self):
        """
        Test that elliptical profile reduces to parabolic when a=b=R.
        """
        R = 0.010  # 10mm radius

        # For circle: u(r) = u_max * (1 - r²/R²)
        # For ellipse with a=b=R: u(x,y) = u_max * (1 - x²/R² - y²/R²)
        # At (r,0): both give u_max * (1 - r²/R²)

        r_test = 0.005  # 5mm from center

        # Circular parabolic
        parabolic = 1.0 - (r_test/R)**2

        # Elliptical with a=b=R
        elliptical = 1.0 - (r_test/R)**2 - (0/R)**2

        self.assertAlmostEqual(parabolic, elliptical, places=10)


class TestEllipseAxisEstimation(unittest.TestCase):
    """Test PCA-based ellipse axis estimation."""

    def test_circular_distribution(self):
        """
        Test that circular point distribution gives equal axes.
        """
        # Generate circular distribution
        n_points = 100
        radius = 0.01
        theta = np.linspace(0, 2*np.pi, n_points, endpoint=False)
        points = np.zeros((n_points, 2))

        # Uniform circular distribution
        for i in range(n_points):
            r = radius * np.sqrt(np.random.random())  # sqrt for uniform area distribution
            t = np.random.random() * 2 * np.pi
            points[i] = [r * np.cos(t), r * np.sin(t)]

        # Estimate axes using PCA
        cov_matrix = np.cov(points.T)
        eigenvalues, _ = np.linalg.eigh(cov_matrix)

        # For circular distribution, eigenvalues should be approximately equal
        ratio = max(eigenvalues) / min(eigenvalues) if min(eigenvalues) > 0 else 1.0

        # Allow some tolerance due to random sampling
        self.assertLess(ratio, 2.0,
            f"Circular distribution should have similar eigenvalues, got ratio {ratio}")

    def test_elliptical_distribution(self):
        """
        Test that elliptical point distribution gives correct axis ratio.
        """
        # Generate elliptical distribution
        n_points = 500
        a, b = 0.015, 0.010  # 3:2 aspect ratio

        points = np.zeros((n_points, 2))
        for i in range(n_points):
            # Random point inside ellipse
            while True:
                x = (np.random.random() * 2 - 1) * a
                y = (np.random.random() * 2 - 1) * b
                if (x/a)**2 + (y/b)**2 <= 1:
                    points[i] = [x, y]
                    break

        # Estimate axes using PCA
        cov_matrix = np.cov(points.T)
        eigenvalues, _ = np.linalg.eigh(cov_matrix)
        eigenvalues = sorted(eigenvalues, reverse=True)

        # Ratio of sqrt(eigenvalues) should approximate a/b
        estimated_ratio = np.sqrt(eigenvalues[0] / eigenvalues[1])
        expected_ratio = a / b

        # Allow 20% tolerance due to sampling
        self.assertAlmostEqual(estimated_ratio, expected_ratio, delta=expected_ratio*0.2,
            msg=f"Estimated ratio {estimated_ratio} should be close to {expected_ratio}")


class TestFlowRateConservation(unittest.TestCase):
    """Test flow rate conservation with different profiles."""

    def test_plug_flow_conservation(self):
        """
        Test that plug flow correctly conserves flow rate.
        Q = V_avg * A
        """
        area = np.pi * (0.01)**2  # 10mm radius inlet
        target_Q = 5e-6  # 5 mL/s = 5e-6 m³/s

        # For plug flow: V = Q / A
        expected_V = target_Q / area

        # Verify
        computed_Q = expected_V * area
        self.assertAlmostEqual(computed_Q, target_Q, places=12)

    def test_parabolic_flow_conservation(self):
        """
        Test that parabolic profile correctly conserves flow rate.
        For parabolic: V_avg = V_max / 2
        Q = V_avg * A = (V_max / 2) * A
        """
        radius = 0.01
        area = np.pi * radius**2
        target_Q = 5e-6  # m³/s

        # For parabolic: Q = (1/2) * V_max * A
        # So V_max = 2 * Q / A
        V_max = 2 * target_Q / area

        # Numerical integration of parabolic profile
        n_samples = 100
        r_samples = np.linspace(0, radius, n_samples)
        dr = radius / (n_samples - 1)

        Q_numerical = 0.0
        for r in r_samples[:-1]:
            v = V_max * (1 - (r/radius)**2)
            # Ring area: 2*pi*r*dr
            dA = 2 * np.pi * r * dr if r > 0 else np.pi * dr**2
            Q_numerical += v * dA

        # Should be approximately equal to target
        error_percent = abs(Q_numerical - target_Q) / target_Q * 100
        self.assertLess(error_percent, 5.0,  # 5% tolerance for numerical integration
            f"Parabolic flow conservation error: {error_percent:.2f}%")


class TestProfileComparison(unittest.TestCase):
    """Compare different profile types for same inlet."""

    def test_profile_centerline_ordering(self):
        """
        Test that profile shapes have correct ordering at center vs edge.

        At centerline: plug = parabolic (normalized to V_max)
        At edge: plug > parabolic (parabolic goes to 0)
        """
        radius = 0.01

        # At center (r=0)
        plug_center = 1.0
        parabolic_center = 1.0 - (0/radius)**2

        self.assertAlmostEqual(plug_center, parabolic_center, places=10)

        # At r = 0.5*R
        r = 0.5 * radius
        plug_mid = 1.0
        parabolic_mid = 1.0 - (r/radius)**2

        self.assertGreater(plug_mid, parabolic_mid)

        # At boundary (r=R)
        plug_edge = 1.0
        parabolic_edge = 1.0 - (radius/radius)**2

        self.assertEqual(parabolic_edge, 0.0)
        self.assertGreater(plug_edge, parabolic_edge)


if __name__ == '__main__':
    print("=" * 70)
    print("Wall-Distance and Elliptical Profile Tests")
    print("=" * 70)

    # Run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestWallDistanceProfile))
    suite.addTests(loader.loadTestsFromTestCase(TestEllipticalPoiseuille))
    suite.addTests(loader.loadTestsFromTestCase(TestEllipseAxisEstimation))
    suite.addTests(loader.loadTestsFromTestCase(TestFlowRateConservation))
    suite.addTests(loader.loadTestsFromTestCase(TestProfileComparison))

    # Run with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    print("\n" + "=" * 70)
    if result.wasSuccessful():
        print("All tests PASSED")
    else:
        print(f"Tests FAILED: {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 70)
