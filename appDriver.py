import sys
from userParameter_HL import * 
from SCRIPTS.meshSetup import *
from SCRIPTS.boundaryConditionSetup import *
from SCRIPTS.physicalProperitesSetup import *
from SCRIPTS.numericalSetup import *
from SCRIPTS.solverSetup import *
from SCRIPTS.simulationSetup import *
from SCRIPTS.inletMapping import *
from SCRIPTS.inletDataSetup import *
from SCRIPTS.solnTypeSetup import *
from SCRIPTS.wkSetup import *
import shutil
import time

class OpenFOAMCase:

    def __init__(self, geometry_case, refinement, directory, bc_inlet, bc_outlet, initial_condition_U, initial_condition_p, initial_condition_K, initial_condition_omega, nu, rho, simulation_type, simulation_control, soln_type, subdomains, decomposition_method, wk_setting):
        self.geometry_case = geometry_case
        self.refinement = refinement
        self.directory = directory
        self.BC_INLET = bc_inlet
        self.BC_OUTLET = bc_outlet
        self.initial_condition_U = initial_condition_U
        self.initial_condition_p = initial_condition_p
        self.initial_condition_K = initial_condition_K
        self.initial_condition_omega = initial_condition_omega
        self.nu = nu
        self.rho = rho
        self.simulation_type = simulation_type
        self.simulation_control = simulation_control
        self.soln_type = soln_type
        self.subdomains = subdomains
        self.decomposition_method = decomposition_method
        self.wk_setting = wk_setting
            
        self.__create_OFcase()

        self.geometry_analyzer = GeometryAnalyzer(self.directory,self.geometry_case, self.refinement)
        self.boundary_condition = BoundaryConditionSetup(self.directory,self.geometry_analyzer.stl_files,self.BC_INLET, self.BC_OUTLET, self.initial_condition_U, self.initial_condition_p, self.initial_condition_K, self.initial_condition_omega, self.simulation_type)
        self.physical_condition = PhysicalPropertiesWriter(self.directory, self.nu, self.rho, self.simulation_type)
        self.numericalSetup = FvSchemesWriter(self.directory,self.simulation_type)
        self.solverSetup = FvSolutionWriter(self.directory,self.simulation_type)
        self.simulationSetup = SimulationSetup(self.directory,self.simulation_control)
        self.solnType = SolnType(self.directory,soln_type,subdomains,decomposition_method)
        if self.BC_OUTLET == "3EWINDKESSEL":
            self.wk_Setup = wk_Setup(self.directory,self.geometry_analyzer.stl_files,self.wk_setting)

       

    def __create_OFcase(self):
        if not os.path.exists(self.directory):
            os.makedirs(self.directory)
        else:
            # remove and create new one 
            shutil.rmtree(self.directory)
            os.makedirs(self.directory)
        print("Directory ", self.directory, " Created ")
           
        # create system  constant 0 folder 
        for f in ["system","constant","0"]:
            directory = os.path.join(self.directory,f)
            os.makedirs(directory)
        # create contsant/triSurface folder
        directory_con_tri = os.path.join(self.directory,"constant","triSurface")
        os.makedirs(directory_con_tri)
        # create constant/boundary folder
        directory_con_bd = os.path.join(self.directory,"constant","boundaryData")
        os.makedirs(directory_con_bd)
        # copy stl files to constant/triSurface folder
        CADfolder = os.path.join("CAD",self.geometry_case)
        for f in os.listdir(CADfolder):
            # copy stl files to constant/triSurface folder
            shutil.copy(os.path.join(CADfolder,f),directory_con_tri)
            # if f conatins inlet 
            if "inlet" in f:
                inletBoundary = os.path.join(self.directory,"constant","boundaryData",f.split(".")[0])
                os.makedirs(inletBoundary)
                # copy the INLET_DATA_FILE to constant/boundaryData/*inlet*/ folder
                shutil.copy(os.path.join("INLET",INLET_DATA_FILE),inletBoundary)
        
    def write_geometry_files(self):
        self.geometry_analyzer.write_blockMeshDict()
        self.geometry_analyzer.write_snappyHexMeshDict()
        self.geometry_analyzer.write_surfaceFeaturesDict()

    def write_boundary_conditions(self):
        self.boundary_condition.write_U_file()
        self.boundary_condition.write_p_file()
        if self.simulation_type in ["RAS", "LES"]:
            self.boundary_condition.write_nut_file()
        if self.simulation_type == "RAS":
            self.boundary_condition.write_k_file()
            self.boundary_condition.write_omega_file()
        self.boundary_condition.write_sampleDict_file()   # for inlet extraction

    def write_physical_properties(self):
        self.physical_condition.write_transportProperties_file()
        self.physical_condition.write_momentumProperties_file()

    def write_numericalSetup(self):
        self.numericalSetup.write_fvSchemes_file()

    def write_solverSetup(self):
        self.solverSetup.write_fvSolution_file()
    
    def write_simulationSetup(self):
        self.simulationSetup.write_controlDict()
    
    def write_decomposeParDict(self):
        self.solnType.write_decomposeParDict()
        
    def write_WK_Setup(self):
        if self.BC_OUTLET == "3EWINDKESSEL":
            self.wk_Setup.write_WK_Setup()       

    def casePoilt(self):
        self.write_geometry_files()
        self.write_boundary_conditions()
        self.write_physical_properties()
        self.write_numericalSetup()
        self.write_solverSetup()
        self.write_simulationSetup()
        self.write_decomposeParDict()
        self.write_WK_Setup()

def create_openfoam_case():
    my_case = OpenFOAMCase(
        geometry_case=GEOMETRY_CASE, 
        refinement=REFINEMENT,
        directory=os.path.join(os.getcwd(), "OPENFOAM", GEOMETRY_CASE + "_" + REFINEMENT),
        bc_inlet=BC_INLET,
        bc_outlet=BC_OUTLET,
        initial_condition_U=INITIAL_CONDITION_U,
        initial_condition_p = INITIAL_CONDITION_P,
        initial_condition_K = INITIAL_CONDITION_K,
        initial_condition_omega = INITIAL_CONDITION_OMEGA,
        nu=NU,
        rho=RHO,
        simulation_type=SIMULATIONTYPE,
        simulation_control=SIMULATION_CONTROL,
        soln_type=SOLN_TYPE,
        subdomains=SUBDOMAINS,
        decomposition_method=DECOMPOSITION_METHOD,
        wk_setting=WK_SETTING
    )
    my_case.casePoilt()
    print("OpenFOAM case created")

def run_mesh():
    start_time = time.time()
    # Run blockMesh
    os.system("blockMesh")
    # Run surfaceFeatureExtract
    os.system("surfaceFeatures")
    # Run snappyHexMesh
    os.system("snappyHexMesh -overwrite")
    # run checkMesh
    os.system("checkMesh > checkMesh.log")
    # transfer mesh scale based on GEOMETRY_SCALE
    # openfoam8
    os.system("transformPoints -scale '{} {} {}'".format(GEOMETRY_SCALE,GEOMETRY_SCALE,GEOMETRY_SCALE))
    
    #####for scaling in openfoam11 use
    os.system("transformPoints 'scale=({} {} {})'".format(GEOMETRY_SCALE, GEOMETRY_SCALE, GEOMETRY_SCALE))
 
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    print("Mesh created in {:.2f} minutes.".format(elapsed_time / 60))


def run_bc():
    
    start_time = time.time()
    # create sampleDict file for inlet extraction, this can be done only after meshing
    #os.system("postProcess -func sampleDict")
    
    #to perform triSurfaceSmapling in openfoam11 use the following command
    #os.system("surfaceMeshTriangulate inlet.stl -patches "(inlet)"")
    # cp the points file to INLET folder
    # os.system("cp postProcessing/sampleDict/0/triSurfaceSampling/points constant/boundaryData/{}/points".format(inlet_stl))
    
    # for opfnoam11
    #os.system("mv postProcessing/sampleDict/0/points.xy postProcessing/sampleDict/0/points")
    #os.system("cp postProcessing/sampleDict/0/points constant/boundaryData/{}/points".format(inlet_stl))
    
     # get inlet stl file name
    inlet_stl = [f for f in os.listdir(os.path.join("constant", "triSurface")) if "inlet" in f][0].split(".")[0] 
    
	# another option is to run "writeMeshObj", then rename the "patch_inlet_0.obj" to be "points-new", copy this to "/OPENFOAM/geometry1-dania-new_coarse/constant/boundaryData/inlet" directory then run the python script named to porduced the required format, then rm -r mesh* patch*
	
    # write the inlet cell centers to map the inlet velocity
    os.system("writeMeshObj")
    os.system("mv patch_inlet_0.obj points-new")
    os.system("rm -r mesh* patch*")
    os.system("cp ../../SCRIPTS/change_format0.py .")
    os.system("cp ../../SCRIPTS/change_format1.py .")
    os.system("python3 change_format0.py")
    os.system("rm change_format0.py")
    os.system("cp points constant/boundaryData/{}/".format(inlet_stl))
    os.system("rm points*")
      
    # run inletMapping 
    processor = InletMapping(center = eval(INLET_CENTER), radius = eval(INLET_RADIUS))
    #processor.run(INLET_DATA_FILE, inlet_stl, scale=GEOMETRY_SCALE)
    processor.run(INLET_DATA_FILE, inlet_stl)
    
    # copy the content of "INLET_DATA_FILE" directory to "INLET_DATA_BPM" directory
      
    os.system("mkdir constant/boundaryData/inlet/InletBCs_" + str(INLET_DATA))
    os.system("cp -r constant/boundaryData/inlet/{0}/* constant/boundaryData/inlet/InletBCs_{1}".format(INLET_DATA_FILE.split('.')[0], INLET_DATA))
    
    # run inletDataSetup
    inletProfile = InletVelocityProfile(BPM = eval(INLET_DATA), numberOfCycle  = eval(NUMBER_OF_CYCLES), baseDir=None)
    inletProfile.execute()
    
    # change the format of "points" file to match the timeVaryingMappedFixedValue BC requirements
    os.system("python3 change_format1.py")
    os.system("rm change_format1.py")
    os.system("cp points constant/boundaryData/{}/".format(inlet_stl))
    end_time = time.time()
    elapsed_time = end_time - start_time

    print("Boundary condition set in {:.2f} minutes.".format(elapsed_time / 60))


def run_simulation():
    start_time = time.time()
    # Logic to run simulation
    if SOLN_TYPE == "serial":
        # For serial solution
        os.system("foamRun -solver incompressibleFluid > log.log")
    elif SOLN_TYPE == "parallel":
        # For parallel solution
        os.system("decomposePar > decompose.log")
        os.system("renumberMesh > renumberMesh.log")
        # for OF11
        #os.system("mpirun -np {} foamRun -parallel -solver incompressibleFluid > log.log".format(SUBDOMAINS))
        # for OF10
        if BC_OUTLET == "3EWINDKESSEL":
           os.system("mpirun -np {} pimpleFoam_WK_2.1 > log.log".format(SUBDOMAINS))
        else:
            os.system("mpirun -np {} pimpleFoam > log.log".format(SUBDOMAINS))     
        os.system("reconstructPar > reconstruct.log")
        os.system("rm -r processor*")
        os.system("foamLog log.log") #extract residuals from log file
    else:
        print("Invalid solution mode. Please specify either 'serial' or 'parallel'.")
    end_time = time.time()
    elapsed_time = end_time - start_time

    print("Simulation run in {:.2f} minutes.".format(elapsed_time / 60))

def run_postprocessing():
    start_time = time.time()
    # plot residuals
    os.system("gnuplot -e \"set terminal jpeg size 1400,700; set output 'Residuals.jpeg'; set logscale y; plot 'logs/Ux_0' u 1:2 w l title 'Ux','logs/Uy_0' u 1:2 w l title 'Uy','logs/Uz_0' u 1:2 w l title 'Uz','logs/pFinalRes_0' u 1:2 w l title 'p','logs/CourantMax_0' u 1:2 w l title 'Co','logs/k_0' u 1:2 w l title 'k','logs/omega_0' u 1:2 w l title 'omega'\"")
     
    # Logic to run post-processing
    end_time = time.time()
    elapsed_time = end_time - start_time

    print("Post-processing done in {:.2f} minutes.".format(elapsed_time / 60))


def run_all():
    # Run all functions
    run_mesh()
    run_bc()
    run_simulation()
    run_postprocessing()


if __name__ == "__main__":
    # Check if additional arguments are provided
    if len(sys.argv) > 1:
        # change the directory to OPENFOAM case directory
        os.chdir(os.path.join(os.getcwd(), "OPENFOAM", GEOMETRY_CASE + "_" + REFINEMENT))
        command = sys.argv[1]
        if command == "runMesh":
            run_mesh()
        elif command == "runBC":
            run_bc()
        elif command == "runSimulation":
            run_simulation()
        elif command == "runPost":
            run_postprocessing()
        elif command == "runAll":
            run_all()
    else:
        create_openfoam_case()
