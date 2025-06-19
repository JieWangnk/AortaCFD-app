import os
from SCRIPTS.logger import Logger
from SCRIPTS.ofVersionAdapter import OFVersionAdapter

class FvSchemesWriter:
    def __init__(self, DIRECTORY, SIMULATIONTYPE, SIMULATIONPERFORMANCE, OPENFOAM_VERSION, log_file="numericalSetup.log"):
        self.DIRECTORY = DIRECTORY
        self.SIMULATIONTYPE = SIMULATIONTYPE
        self.SIMULATIONPERFORMANCE = SIMULATIONPERFORMANCE
        self.openfoam_version = OPENFOAM_VERSION  # Store the OpenFOAM version
        self.logger = Logger(log_file).get_logger()

        # Initialize the OFVersionAdapter
        self.version_adapter = OFVersionAdapter(OPENFOAM_VERSION)

    def write_fvSchemes_file(self):
        filepath = os.path.join(self.DIRECTORY, "system", "fvSchemes")

        try:
            with open(filepath, 'w') as f:
                if self.SIMULATIONTYPE == 'laminar':
                    if self.SIMULATIONPERFORMANCE == "high":
                        f.write(self._get_laminar_high_fvSchemes())
                    elif self.SIMULATIONPERFORMANCE == "medium":
                        f.write(self._get_laminar_medium_fvSchemes())
                    elif self.SIMULATIONPERFORMANCE == "low":
                        f.write(self._get_laminar_low_fvSchemes())
                    else:
                        self.logger.error("Invalid simulation performance for laminar.")
                        raise ValueError("Invalid simulation performance for laminar.")
                elif self.SIMULATIONTYPE == 'LES':
                    if self.SIMULATIONPERFORMANCE == "high":
                        f.write(self._get_LES_high_fvSchemes())
                    elif self.SIMULATIONPERFORMANCE == "medium":
                        f.write(self._get_LES_medium_fvSchemes())
                    elif self.SIMULATIONPERFORMANCE == "low":
                        f.write(self._get_LES_low_fvSchemes())
                    else:
                        self.logger.error("Invalid simulation performance for LES.")
                        raise ValueError("Invalid simulation performance for LES.")
                else:
                    self.logger.error("Invalid simulation type.")
                    raise ValueError("Invalid simulation type.")
        except Exception as e:
            self.logger.error(f"Failed to write fvSchemes file: {e}")
            raise

    def _get_laminar_high_fvSchemes(self):
        foam_file_header = self.version_adapter.get_foam_file_header("dictionary", "fvSchemes")
        return f"""{foam_file_header}

ddtSchemes
{{
    default         backward;
}}

gradSchemes
{{
    default         cellLimited Gauss linear 1;
    grad(p)         cellLimited Gauss linear 0.5;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss linearUpwind default;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear limited 0.5;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

// ************************************************************************* //
"""

    def _get_laminar_medium_fvSchemes(self):
        foam_file_header = self.version_adapter.get_foam_file_header("dictionary", "fvSchemes")
        return f"""{foam_file_header}

ddtSchemes
{{
    default         backward;
}}

gradSchemes
{{
    default         cellLimited Gauss linear 0.5;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss linear;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear limited 0.5;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

// ************************************************************************* //
"""

    def _get_laminar_low_fvSchemes(self):
        foam_file_header = self.version_adapter.get_foam_file_header("dictionary", "fvSchemes")
        return f"""{foam_file_header}

ddtSchemes
{{
    default         Euler;
}}

gradSchemes
{{
    default         cellLimited Gauss linear 0.5;
    grad(p)         cellLimited Gauss linear 0.25;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss upwind;
    div((nuEff*dev2(T(grad(U)))))  Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear limited 0.5;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

// ************************************************************************* //
"""

    def _get_LES_high_fvSchemes(self):
        foam_file_header = self.version_adapter.get_foam_file_header("dictionary", "fvSchemes")
        return f"""{foam_file_header}

ddtSchemes
{{
    default         backward;
}}

gradSchemes
{{
    default         cellMDLimited Gauss linear 0.5;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss linear;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear corrected;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

wallDist
{{
    method meshWave;
}}

// ************************************************************************* //
"""

    def _get_LES_medium_fvSchemes(self):
        foam_file_header = self.version_adapter.get_foam_file_header("dictionary", "fvSchemes")
        return f"""{foam_file_header}

ddtSchemes
{{
    default         backward;
}}

gradSchemes
{{
    default         cellLimited Gauss linear 1;
    grad(p)         cellLimited Gauss linear 0.5;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss linear;
    div((nuEff*dev2(T(grad(U))))) Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear corrected;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

wallDist
{{
    method meshWave;
}}

// ************************************************************************* //
"""

    def _get_LES_low_fvSchemes(self):
        foam_file_header = self.version_adapter.get_foam_file_header("dictionary", "fvSchemes")
        return f"""{foam_file_header}

ddtSchemes
{{
    default         Euler;
}}

gradSchemes
{{
    default         cellLimited Gauss linear 1;
}}

divSchemes
{{
    default         none;
    div(phi,U)      Gauss upwind;
    div((nuEff*dev2(T(grad(U)))))   Gauss linear;
}}

laplacianSchemes
{{
    default         Gauss linear corrected;
}}

interpolationSchemes
{{
    default         linear;
}}

snGradSchemes
{{
    default         corrected;
}}

wallDist
{{
    method meshWave;
}}

// ************************************************************************* //
"""

