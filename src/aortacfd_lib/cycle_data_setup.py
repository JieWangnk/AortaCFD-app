import os
from .utils.logger import Logger


class CycleDataSetup:
    """
    Sets up data for multiple cardiac cycles by creating symbolic links to the
    time-step DIRECTORIES generated for the first cycle.
    """

    def __init__(self, config: dict, case_directory: str, cardiac_cycle: float):
        """
        The constructor now correctly receives the cardiac_cycle and saves it
        as an instance attribute.
        """
        self.config = config
        self.case_dir = case_directory
        self.log = Logger("cycle_data_setup").get_logger()

        # --- THIS IS THE FIX ---
        # The received cardiac_cycle value is now correctly assigned
        # to the instance attribute that the execute() method needs.
        self.cardiac_period = cardiac_cycle

        # Get other necessary parameters from the config object
        # Support both config structures: boundary_conditions.inlet or inlet
        self.config.get("boundary_conditions", {}).get("inlet") or self.config.get("inlet", {})
        geom_settings = self.config["geometry"]
        sim_control_settings = self.config.get("simulation_control", {})

        inlet_patch_name = geom_settings["inlet_keywords_ordered"]
        self.number_of_cycles = sim_control_settings.get("number_of_cycles", 1)

        self.data_directory = os.path.join(self.case_dir, "constant", "boundaryData", inlet_patch_name)

    def execute(self):
        """
        Finds the first-cycle time directories and creates relative symbolic links
        for all subsequent cycles.
        """
        self.log.info(f"Setting up {self.number_of_cycles} cardiac cycles in {self.data_directory}")
        if not os.path.isdir(self.data_directory):
            raise FileNotFoundError(f"Source data directory not found: {self.data_directory}")

        try:
            first_cycle_dirs = [
                d
                for d in os.listdir(self.data_directory)
                if os.path.isdir(os.path.join(self.data_directory, d)) and d.replace(".", "", 1).isdigit()
            ]
            first_cycle_times = sorted([float(d) for d in first_cycle_dirs])

            if not first_cycle_times:
                raise ValueError("No time step directories found in the source directory.")
        except (ValueError, IndexError) as e:
            self.log.error(f"Could not parse time values from directories in {self.data_directory}: {e}")
            raise

        self.log.debug("Removing any old symbolic links...")
        for item in os.listdir(self.data_directory):
            item_path = os.path.join(self.data_directory, item)
            if os.path.islink(item_path):
                os.unlink(item_path)

        for t in first_cycle_times:
            source_dir_name = f"{t:.6f}"

            for j in range(1, self.number_of_cycles):
                # This line will now work correctly because self.cardiac_period exists
                new_time = t + j * self.cardiac_period
                link_dir_name = f"{new_time:.6f}"
                link_path = os.path.join(self.data_directory, link_dir_name)

                if not os.path.lexists(link_path):
                    try:
                        os.symlink(source_dir_name, link_path, target_is_directory=True)
                        self.log.debug(f"Created directory symlink: {link_path} -> {source_dir_name}")
                    except Exception as e:
                        self.log.error(f"Failed to create symlink at {link_path}: {e}")
                        raise
                else:
                    self.log.debug(f"Skipping link for {link_dir_name}, as it already exists.")

        self.log.info("Symbolic links for all cycles created successfully.")
