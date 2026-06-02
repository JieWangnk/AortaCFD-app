import math
import os

from .constants import DEFAULT_NUMBER_OF_CYCLES
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
        self.number_of_cycles = self._resolve_number_of_cycles(sim_control_settings)

        self.data_directory = os.path.join(self.case_dir, "constant", "boundaryData", inlet_patch_name)

    def _resolve_number_of_cycles(self, sim_control_settings: dict) -> int:
        """Determine how many cardiac cycles of inlet data to lay down.

        Priority — deliberately ``end_time`` first, to match how
        ``GenerateControlDictTask`` resolves the solver ``endTime`` (it uses an
        explicit ``end_time`` over ``number_of_cycles``). Keeping the same order
        here guarantees the tiled inlet data covers exactly the interval the
        solver runs; the two must not diverge.

          1. Derived from ``end_time`` and the detected cardiac cycle:
             ``ceil(end_time / cardiac_cycle)``. Without this the inlet
             boundaryData spans only one cycle and the
             ``timeVaryingMappedFixedValue`` BC (which is NOT periodic) holds its
             last value, silently flat-lining the inflow after cycle 1. If
             ``number_of_cycles`` is also set but implies a different count, a
             warning is logged and ``end_time`` wins.
          2. Explicit ``number_of_cycles`` when no usable ``end_time`` is given.
          3. Fallback: the pipeline default (``DEFAULT_NUMBER_OF_CYCLES`` = 3).

        Returns an int >= 1.
        """
        explicit = sim_control_settings.get("number_of_cycles")
        end_time = sim_control_settings.get("end_time")

        if end_time not in (None, "auto") and self.cardiac_period and self.cardiac_period > 0:
            # Subtract a small epsilon so an exact integer multiple (e.g.
            # 1.5 / 0.5 = 3.0) is not pushed up to 4 by floating-point noise.
            n = max(1, math.ceil(float(end_time) / float(self.cardiac_period) - 1e-9))
            if explicit is not None and max(1, int(explicit)) != n:
                self.log.warning(
                    f"simulation_control sets both end_time={end_time}s and number_of_cycles={explicit}, "
                    f"which imply different cycle counts; end_time wins (matches solver endTime). "
                    f"Tiling {n} cycles."
                )
            else:
                self.log.info(
                    f"Inlet cycles: {n} (derived from end_time={end_time}s / "
                    f"cardiac_cycle={self.cardiac_period:.4f}s) — tiling boundaryData to cover the full run"
                )
            return n

        if explicit is not None:
            n = max(1, int(explicit))
            self.log.info(f"Inlet cycles: {n} (explicit number_of_cycles)")
            return n

        self.log.info(
            f"Inlet cycles: {DEFAULT_NUMBER_OF_CYCLES} (no number_of_cycles or end_time given; pipeline default)"
        )
        return DEFAULT_NUMBER_OF_CYCLES

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
        self._verify_coverage()

    def _verify_coverage(self) -> None:
        """Assert the laid-down inlet data actually reaches the solver's end_time.

        ``timeVaryingMappedFixedValue`` is not periodic: if the newest
        boundaryData time directory is earlier than ``end_time``, the inflow
        silently holds its last value for the rest of the run. We catch that
        here, at setup time (seconds in), instead of discovering a flat-lined
        inflow part-way through a multi-minute solve.

        This is the guard that would have caught the ub_* batch: a config with
        ``end_time`` but a ``number_of_cycles`` too small to cover it.

        No-ops (returns quietly) when there is nothing to check against, e.g.
        ``end_time`` is absent or ``"auto"`` (derived downstream from cycles).
        """
        end_time = self.config.get("simulation_control", {}).get("end_time")
        if end_time in (None, "auto"):
            return
        try:
            end_time = float(end_time)
        except (TypeError, ValueError):
            return

        times = sorted(
            float(d)
            for d in os.listdir(self.data_directory)
            if os.path.lexists(os.path.join(self.data_directory, d)) and d.replace(".", "", 1).isdigit()
        )
        if not times:
            return

        max_time = times[-1]
        if max_time + 1e-9 < end_time:
            raise ValueError(
                f"Inlet boundaryData spans only [{times[0]:.4f}, {max_time:.4f}]s but the "
                f"simulation end_time is {end_time:.4f}s. timeVaryingMappedFixedValue is not "
                f"periodic, so the inflow would flat-line (hold its last value) after "
                f"{max_time:.4f}s. Increase number_of_cycles, set end_time consistently, or "
                f"check inlet CSV / cardiac-cycle detection (detected cycle = {self.cardiac_period}s)."
            )
        self.log.info(f"Inlet data coverage OK: [{times[0]:.4f}, {max_time:.4f}]s covers end_time={end_time:.4f}s")
