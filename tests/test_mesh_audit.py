"""Tests for mesh_audit module."""

import sys
import tempfile
import os
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


SAMPLE_CHECKMESH_LOG = """
/*---------------------------------------------------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  12                                    |
\\\\*---------------------------------------------------------------------------*/
Checking geometry...
    Overall domain bounding box (-0.028 -0.029 -0.076) (0.008 0.011 0.036)
    Mesh has 3 geometric (non-empty/wedge) directions (1 1 1)

Checking topology...
    Boundary definition OK.
    Cell to face addressing OK.
    Point usage OK.
    Upper triangular ordering OK.
    Face vertices OK.
    Number of regions: 1 (OK).

Checking patch topology for multiply connected surfaces...
    Patch               Faces    Points
    wall_aorta          25432    25890
    inlet               312      180
    outlet1             156      93
    outlet2             98       60

Checking basic cellZone addressing...
    OK.

Checking geometry...
    This is a 3-D mesh
    Boundary openness (3.2e-16 -1.1e-16 2.8e-17) OK.
    Max cell openness = 4.5e-16 OK.
    Max aspect ratio = 5.21 OK.
    Minimum face area = 1.2e-09. Maximum face area = 3.8e-07. Face area magnitudes OK.
    Min volume = 2.1e-13. Max volume = 5.6e-10. Cell volumes OK.
    Mesh non-orthogonality Max: 58.3 average: 8.2
    Non-orthogonality check OK.
    Face pyramids OK.
    Max skewness = 2.45 OK.
    Coupled point location match (average 0) OK.

Mesh OK.

    cells:            318759
    faces:            1013040
    points:           382781
"""


SAMPLE_BLOCKMESH_LOG = """
Creating block mesh topology

Check topology

    Basic statistics
        Number of internal faces:  0
        Number of boundary faces:  6
        Number of defined boundary faces:  6
        Number of undefined boundary faces:  0
    Checking patch -> block consistency

Creating block mesh...

    nCells: 371159
"""


class TestExtractCellCounts:
    """Test cell count extraction from logs."""

    def test_extract_from_logs(self):
        from aortacfd_lib.mesh_audit import _extract_cell_counts

        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir()

            (logs_dir / "log.blockMesh").write_text(SAMPLE_BLOCKMESH_LOG)
            (logs_dir / "log.checkMesh").write_text(SAMPLE_CHECKMESH_LOG)

            counts = _extract_cell_counts(tmpdir)

            assert counts["blockmesh_cells"] == 371159
            assert counts["final_cells"] == 318759
            assert 0 < counts["retained_fraction"] < 1

    def test_missing_logs(self):
        from aortacfd_lib.mesh_audit import _extract_cell_counts

        with tempfile.TemporaryDirectory() as tmpdir:
            counts = _extract_cell_counts(tmpdir)
            assert counts == {}


class TestDetermineVerdict:
    """Test verdict logic."""

    def test_pass(self):
        from aortacfd_lib.mesh_audit import _determine_verdict

        report = {
            "quality": {
                "status": "good",
                "metrics": {"max_non_orthogonality": 55, "max_skewness": 2.0},
            },
            "resolution_proxy": {},
            "requested_cells_across_span": None,
        }
        verdict, warnings = _determine_verdict(report)
        assert verdict == "pass"

    def test_warn_high_ortho(self):
        from aortacfd_lib.mesh_audit import _determine_verdict

        report = {
            "quality": {
                "status": "good",
                "metrics": {"max_non_orthogonality": 67, "max_skewness": 2.0},
            },
            "resolution_proxy": {},
            "requested_cells_across_span": None,
        }
        verdict, warnings = _determine_verdict(report)
        assert verdict == "warn"
        assert any("maxNonOrtho" in w for w in warnings)

    def test_fail_extreme_ortho(self):
        from aortacfd_lib.mesh_audit import _determine_verdict

        report = {
            "quality": {
                "status": "good",
                "metrics": {"max_non_orthogonality": 75, "max_skewness": 2.0},
            },
            "resolution_proxy": {},
            "requested_cells_across_span": None,
        }
        verdict, warnings = _determine_verdict(report)
        assert verdict == "fail"

    def test_fail_checkmesh_failed(self):
        from aortacfd_lib.mesh_audit import _determine_verdict

        report = {
            "quality": {
                "status": "failed",
                "metrics": {"max_non_orthogonality": 50, "max_skewness": 1.5},
            },
            "resolution_proxy": {},
            "requested_cells_across_span": None,
        }
        verdict, warnings = _determine_verdict(report)
        assert verdict == "fail"

    def test_warn_underresolved_patch(self):
        from aortacfd_lib.mesh_audit import _determine_verdict

        report = {
            "quality": {
                "status": "good",
                "metrics": {"max_non_orthogonality": 50, "max_skewness": 1.5},
            },
            "resolution_proxy": {
                "outlet1": {"cells_across_proxy": 5.0},
            },
            "requested_cells_across_span": 16,
        }
        verdict, warnings = _determine_verdict(report)
        assert verdict == "warn"
        assert any("outlet1" in w for w in warnings)


class TestPolyMeshReaders:
    """Test OpenFOAM polyMesh file readers."""

    def test_read_points(self):
        from aortacfd_lib.mesh_audit import _read_openfoam_points

        content = """FoamFile
{
    format      ascii;
    class       vectorField;
    object      points;
}
4
(
(0 0 0)
(1 0 0)
(1 1 0)
(0 1 0)
)
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()
            points = _read_openfoam_points(Path(f.name))

        os.unlink(f.name)
        assert points.shape == (4, 3)
        assert np.allclose(points[1], [1, 0, 0])

    def test_read_faces(self):
        from aortacfd_lib.mesh_audit import _read_openfoam_faces

        content = """FoamFile
{
    format      ascii;
    class       faceList;
    object      faces;
}
2
(
4(0 1 2 3)
3(0 1 3)
)
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()
            faces = _read_openfoam_faces(Path(f.name))

        os.unlink(f.name)
        assert len(faces) == 2
        assert faces[0] == [0, 1, 2, 3]
        assert faces[1] == [0, 1, 3]

    def test_read_boundary(self):
        from aortacfd_lib.mesh_audit import _read_openfoam_boundary

        content = """FoamFile
{
    format      ascii;
    class       polyBoundaryMesh;
    object      boundary;
}
2
(
    inlet
    {
        type            patch;
        nFaces          100;
        startFace       50000;
    }
    wall
    {
        type            wall;
        nFaces          5000;
        startFace       50100;
    }
)
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(content)
            f.flush()
            boundary = _read_openfoam_boundary(Path(f.name))

        os.unlink(f.name)
        assert "inlet" in boundary
        assert boundary["inlet"]["nFaces"] == 100
        assert boundary["inlet"]["startFace"] == 50000
        assert boundary["wall"]["type"] == "wall"


class TestEstimatePatchResolution:
    """Test resolution proxy estimation from synthetic polyMesh data."""

    def test_square_faces(self):
        """A patch of uniform square faces should give correct cell size."""
        from aortacfd_lib.mesh_audit import estimate_patch_resolution

        with tempfile.TemporaryDirectory() as tmpdir:
            poly_dir = Path(tmpdir) / "constant" / "polyMesh"
            poly_dir.mkdir(parents=True)

            # 4 square faces of 1mm x 1mm each, arranged in a 2x2 grid
            # Points: 9 points for a 2x2 grid of quads
            cell_size = 0.001  # 1mm in meters
            points_data = "FoamFile\n{\n    class vectorField;\n    object points;\n}\n9\n(\n"
            pts = []
            for j in range(3):
                for i in range(3):
                    x = i * cell_size
                    y = j * cell_size
                    pts.append(f"({x} {y} 0)")
            points_data += "\n".join(pts) + "\n)\n"
            (poly_dir / "points").write_text(points_data)

            # 4 quad faces: (0,1,4,3), (1,2,5,4), (3,4,7,6), (4,5,8,7)
            # Plus some internal faces before these (startFace offset)
            faces_data = "FoamFile\n{\n    class faceList;\n    object faces;\n}\n4\n(\n"
            faces_data += "4(0 1 4 3)\n4(1 2 5 4)\n4(3 4 7 6)\n4(4 5 8 7)\n)\n"
            (poly_dir / "faces").write_text(faces_data)

            # Boundary: one patch "test_patch" with all 4 faces
            boundary_data = """FoamFile
{
    class polyBoundaryMesh;
    object boundary;
}
1
(
    test_patch
    {
        type            patch;
        nFaces          4;
        startFace       0;
    }
)
"""
            (poly_dir / "boundary").write_text(boundary_data)

            # Patch diameter = 2mm = 0.002m
            result = estimate_patch_resolution(tmpdir, "test_patch", 0.002)

            assert result is not None
            assert result["n_faces"] == 4
            # Each face is 1mm x 1mm = 1e-6 m², sqrt = 0.001m = 1mm
            assert abs(result["cell_size_proxy_mm"] - 1.0) < 0.1
            # 2mm diameter / 1mm cell = 2 cells across
            assert abs(result["cells_across_proxy"] - 2.0) < 0.5

    def test_missing_patch(self):
        """Non-existent patch returns None."""
        from aortacfd_lib.mesh_audit import estimate_patch_resolution

        with tempfile.TemporaryDirectory() as tmpdir:
            poly_dir = Path(tmpdir) / "constant" / "polyMesh"
            poly_dir.mkdir(parents=True)

            (poly_dir / "points").write_text("FoamFile\n{}\n0\n(\n)\n")
            (poly_dir / "faces").write_text("FoamFile\n{}\n0\n(\n)\n")
            (poly_dir / "boundary").write_text("FoamFile\n{}\n0\n(\n)\n")

            result = estimate_patch_resolution(tmpdir, "nonexistent", 0.01)
            assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
