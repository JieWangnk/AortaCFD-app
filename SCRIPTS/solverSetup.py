import os
from SCRIPTS.logger import Logger

class FvSolutionWriter:
    def __init__(self, DIRECTORY, SIMULATIONTYPE, SIMULATIONPERFORMANCE, OUTTER_CORR, OPENFOAM_VERSION, log_file="solverSetup.log"):
        self.DIRECTORY = DIRECTORY
        self.SIMULATIONTYPE = SIMULATIONTYPE
        self.SIMULATIONPERFORMANCE = SIMULATIONPERFORMANCE
        self.OUTTER_CORR = OUTTER_CORR
        self.openfoam_version = OPENFOAM_VERSION  # Store the OpenFOAM version
        self.logger = Logger(log_file).get_logger()

    def write_fvSolution_file(self):
        filepath = os.path.join(self.DIRECTORY, "system", "fvSolution")

        try:
            with open(filepath, 'w') as f:
                if self.SIMULATIONTYPE == 'laminar':
                    if self.SIMULATIONPERFORMANCE == "high":
                        f.write(self._get_laminar_high_fvSolution())
                    elif self.SIMULATIONPERFORMANCE == "medium":
                        f.write(self._get_laminar_medium_fvSolution())
                    elif self.SIMULATIONPERFORMANCE == "low":
                        f.write(self._get_laminar_low_fvSolution())
                    else:
                        self.logger.error("Invalid simulation performance for laminar.")
                        raise ValueError("Invalid simulation performance.")
                elif self.SIMULATIONTYPE == 'LES':
                    if self.SIMULATIONPERFORMANCE == "high":
                        f.write(self._get_LES_high_fvSolution())
                    elif self.SIMULATIONPERFORMANCE == "medium":
                        f.write(self._get_LES_medium_fvSolution())
                    elif self.SIMULATIONPERFORMANCE == "low":
                        f.write(self._get_LES_low_fvSolution())
                    else:
                        self.logger.error("Invalid simulation performance for LES.")
                        raise ValueError("Invalid simulation performance.")
                elif self.SIMULATIONTYPE == 'RAS':
                    f.write(self._get_RAS_fvSolution())
                else:
                    self.logger.error("Invalid simulation type.")
                    raise ValueError("Invalid simulation type.")
        except Exception as e:
            self.logger.error(f"Failed to write fvSolution file: {e}")
            raise

    def _get_foam_file_header(self):
        """
        Generate the FoamFile header dynamically based on the OpenFOAM version.
        """
        return f"""/*--------------------------------*- C++ -*----------------------------------*\\
| =========                 |                                                 |
| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |
|  \\\\    /   O peration     | Version:  {self.openfoam_version}                              |
|   \\\\  /    A nd           | Web:      www.OpenFOAM.org                      |
|    \\\\/     M anipulation  |                                                 |
\\*---------------------------------------------------------------------------*/
FoamFile
{{
    version     2.0;
    format      ascii;
    class       dictionary;
    location    "system";
    object      fvSolution;
}}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
"""

    def _get_laminar_high_fvSolution(self):
        return f"""{self._get_foam_file_header()}

// High-performance: fine mesh, full robustness and accuracy
solvers
{{
    p
    {{
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-6;
        relTol          0.1;
    }}
    pFinal
    {{
        $p;
        tolerance       1e-6;
        relTol          0;
    }}
    U
    {{
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-6;
        relTol          0.1;
    }}
    UFinal
    {{
        $U;
        tolerance       1e-6;
        relTol          0;
    }}
}}

PIMPLE
{{
    nOuterCorrectors     {self.OUTTER_CORR};
    nCorrectors          3;
    nNonOrthogonalCorrectors 1;
    pRefCell             0;
    pRefValue            0;
    outerCorrectorResidualControl
    {{
        U
        {{
            tolerance   1e-5;
            relTol      0;
        }}
        p
        {{
            tolerance   1e-6;
            relTol      0;
        }}
    }}
}}

relaxationFactors
{{
    fields
    {{
        p               0.3;
        pFinal          1.0;
    }}
    equations
    {{
        U               0.3;
        UFinal          1.0;
    }}
}}
"""

    def _get_laminar_medium_fvSolution(self):
        return f"""{self._get_foam_file_header()}

// Medium-performance: balanced accuracy and stability
solvers
{{
    p
    {{
        solver          GAMG;
        tolerance       1e-6;
        relTol          0.1;
    }}
    pFinal
    {{
        $p;
        tolerance       1e-7;
        relTol          0;
    }}
    U
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-6;
        relTol          0.1;
    }}
    UFinal
    {{
        $U;
        tolerance       1e-6;
        relTol          0;
    }}
}}

PIMPLE
{{
    nOuterCorrectors     {self.OUTTER_CORR};
    nCorrectors          2;
    nNonOrthogonalCorrectors 1;
    pRefCell             0;
    pRefValue            0;
    outerCorrectorResidualControl
    {{
        U
        {{
            tolerance   1e-4;
            relTol      0;
        }}
        p
        {{
            tolerance   1e-5;
            relTol      0;
        }}
    }}
}}

relaxationFactors
{{
    fields
    {{
        p               0.7;
        pFinal          1.0;
    }}
    equations
    {{
        U               0.7;
        UFinal          1.0;
    }}
}}
"""

    def _get_laminar_low_fvSolution(self):
        return f"""{self._get_foam_file_header()}

// Low-performance: coarse mesh, efficient but less accurate
solvers
{{
    p
    {{
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-5;
        relTol          0.1;
    }}
    pFinal
    {{
        $p;
        tolerance       1e-5;
        relTol          0;
    }}
    U
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-5;
        relTol          0.1;
    }}
    UFinal
    {{
        $U;
        tolerance       1e-5;
        relTol          0;
    }}
}}

PIMPLE
{{
    nOuterCorrectors     {self.OUTTER_CORR};
    nCorrectors          2;
    nNonOrthogonalCorrectors 1;
    pRefCell             0;
    pRefValue            0;
    outerCorrectorResidualControl
    {{
        U
        {{
            tolerance   1e-4;
            relTol      0;
        }}
        p
        {{
            tolerance   1e-4;
            relTol      0;
        }}
    }}
}}

relaxationFactors
{{
    fields
    {{
        p               1.0;
    }}
    equations
    {{
        U               1.0;
    }}
}}
"""

    def _get_LES_low_fvSolution(self):
        return f"""{self._get_foam_file_header()}

// Low-performance (coarse mesh) LES PIMPLE solver settings
solvers
{{
    p
    {{
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-5;
        relTol          0.1;
    }}
    pFinal
    {{
        $p;
        tolerance       1e-5;
        relTol          0;
    }}
    U
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-5;
        relTol          0.1;
    }}
    UFinal
    {{
        $U;
        tolerance       1e-5;
        relTol          0;
    }}
}}

PIMPLE
{{
    nOuterCorrectors     {self.OUTTER_CORR};
    nCorrectors          2;
    nNonOrthogonalCorrectors 1;
    pRefCell             0;
    pRefValue            0;
    outerCorrectorResidualControl
    {{
        U
        {{
            tolerance   1e-4;
            relTol      0;
        }}
        p
        {{
            tolerance   1e-4;
            relTol      0;
        }}
    }}
}}

relaxationFactors
{{
    fields
    {{
        p                1.0;
    }}
    equations
    {{
        U                1.0;
    }}
}}
"""

    def _get_LES_medium_fvSolution(self):
        return f"""{self._get_foam_file_header()}

// Medium-performance (moderate mesh) LES PIMPLE solver settings
solvers
{{
    p
    {{
        solver          GAMG;
        smoother        DIC;
        tolerance       1e-6;
        relTol          0.1;
    }}
    pFinal
    {{
        $p;
        tolerance       1e-7;
        relTol          0;
    }}
    U
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-6;
        relTol          0.1;
    }}
    UFinal
    {{
        $U;
        tolerance       1e-6;
        relTol          0;
    }}
    "(nuTilda|k|omega)"
    {{
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-6;
        relTol          0.1;
    }}
    "(nuTilda|k|omega)Final"
    {{
        $nuTilda;
        tolerance       1e-6;
        relTol          0;
    }}
}}

PIMPLE
{{
    nOuterCorrectors     {self.OUTTER_CORR};
    nCorrectors          2;
    nNonOrthogonalCorrectors 1;
    pRefCell             0;
    pRefValue            0;
    outerCorrectorResidualControl
    {{
        p
        {{
            tolerance   1e-4;
            relTol      0;
        }}
        U
        {{
            tolerance   1e-5;
            relTol      0;
        }}
    }}
}}

relaxationFactors
{{
    fields
    {{
        p                0.7;
        pFinal           1.0;
    }}
    equations
    {{
        U                0.7;
        UFinal           1.0;
    }}
}}
"""

    def _get_LES_high_fvSolution(self):
        return f"""{self._get_foam_file_header()}

// High-performance (fine mesh) LES PIMPLE solver settings
solvers
{{
    p
    {{
        solver          GAMG;
        smoother        GaussSeidel;
        tolerance       1e-7;
        relTol          0.1;
        nPreSweeps      0;
        nPostSweeps     2;
        nFinestSweeps   2;
    }}
    pFinal
    {{
        $p;
        tolerance       1e-6;
        relTol          0;
    }}
    U
    {{
        solver          smoothSolver;
        smoother        GaussSeidel;
        tolerance       1e-6;
        relTol          0.1;
        nSweeps         1;
    }}
    UFinal
    {{
        $U;
        tolerance       1e-6;
        relTol          0;
    }}
}}

PIMPLE
{{
    nOuterCorrectors     {self.OUTTER_CORR};
    nCorrectors          2;
    nNonOrthogonalCorrectors 1;
    pRefCell             0;
    pRefValue            0;
    outerCorrectorResidualControl
    {{
        p
        {{
            tolerance   1e-5;
            relTol      0;
        }}
        U
        {{
            tolerance   1e-6;
            relTol      0;
        }}
    }}
}}

relaxationFactors
{{
    fields
    {{
        p                0.3;
        pFinal           1.0;
    }}
    equations
    {{
        U                0.3;
        UFinal           1.0;
    }}
}}
"""