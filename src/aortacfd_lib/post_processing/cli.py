"""
Command-line interface for post-processing.

Usage:
    # Full post-processing
    python -m aortacfd_lib.post_processing /path/to/case

    # With config file (JSON format, consistent with AortaCFD)
    python -m aortacfd_lib.post_processing /path/to/case --config postprocess.json

    # Hemodynamics only
    python -m aortacfd_lib.post_processing /path/to/case --hemodynamics-only

    # Visualization only (requires pvbatch for screenshots)
    pvbatch -m aortacfd_lib.post_processing.visualization /path/to/case

    # Check dependencies
    python -m aortacfd_lib.post_processing --check-deps

    # Generate config template
    python -m aortacfd_lib.post_processing --generate-config postprocess.json
"""

import argparse
import sys
from pathlib import Path


def main(argv=None):
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        prog="aortacfd-postprocess",
        description="AortaCFD Post-Processing: Visualization and Hemodynamics Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full post-processing
  python -m aortacfd_lib.post_processing /path/to/case

  # With configuration file (JSON format)
  python -m aortacfd_lib.post_processing /path/to/case -c config.json

  # Hemodynamics analysis only
  python -m aortacfd_lib.post_processing /path/to/case --hemodynamics-only

  # Check dependencies
  python -m aortacfd_lib.post_processing --check-deps

  # Generate config template (JSON)
  python -m aortacfd_lib.post_processing --generate-config postprocess.json

  # ParaView visualization (requires pvbatch)
  pvbatch -m aortacfd_lib.post_processing.visualization /path/to/case
""",
    )

    # Positional argument
    parser.add_argument("case_dir", nargs="?", default=None, help="Path to OpenFOAM case directory")

    # Configuration
    parser.add_argument("-c", "--config", help="Path to configuration file (JSON or YAML)")

    parser.add_argument("-o", "--output", help="Output directory (default: postProcessing_results)")

    # Mode selection
    mode_group = parser.add_argument_group("Processing Mode")
    mode_group.add_argument(
        "--hemodynamics-only", action="store_true", help="Run hemodynamics analysis only (no visualization)"
    )
    mode_group.add_argument(
        "--visualization-only", action="store_true", help="Run visualization only (requires ParaView)"
    )
    mode_group.add_argument(
        "--animations-only", action="store_true", help="Create animations from existing screenshots (requires ffmpeg)"
    )

    # Time step selection
    time_group = parser.add_argument_group("Time Step Selection")
    time_group.add_argument(
        "--time-steps",
        choices=["all", "last", "peak"],
        default="all",
        help="Time steps to process: all, last, or peak systole (default: all)",
    )

    # Hemodynamics options
    hemo_group = parser.add_argument_group("Hemodynamics Options")
    hemo_group.add_argument("--run-wss", action="store_true", help="Force run wallShearStress post-processing")
    hemo_group.add_argument(
        "--skip-cycles", type=int, default=2, help="Number of cardiac cycles to skip for TAWSS (default: 2)"
    )

    # Visualization options
    viz_group = parser.add_argument_group("Visualization Options")
    viz_group.add_argument(
        "--fields",
        nargs="+",
        default=["U", "p", "wallShearStress"],
        help="Fields to visualize (default: U p wallShearStress)",
    )
    viz_group.add_argument("--fps", type=int, default=30, help="Animation frame rate (default: 30)")
    viz_group.add_argument(
        "--resolution",
        nargs=2,
        type=int,
        metavar=("WIDTH", "HEIGHT"),
        default=[1600, 900],
        help="Screenshot resolution (default: 1600 900)",
    )

    # Utility options
    util_group = parser.add_argument_group("Utility Options")
    util_group.add_argument("--check-deps", action="store_true", help="Check dependencies and exit")
    util_group.add_argument("--generate-config", metavar="FILE", help="Generate configuration template and exit")
    util_group.add_argument("--status", action="store_true", help="Check case status and exit")

    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument(
        "-v", "--verbose", action="count", default=1, help="Increase verbosity (can be repeated: -v, -vv)"
    )
    output_group.add_argument("-q", "--quiet", action="store_true", help="Quiet mode (warnings only)")

    args = parser.parse_args(argv)

    # Handle quiet mode
    if args.quiet:
        args.verbose = 0

    # Utility commands that don't need case_dir
    if args.check_deps:
        from .dependencies import check_dependencies

        check_dependencies(verbose=True)
        return 0

    if args.generate_config:
        from .config import generate_config_template

        generate_config_template(args.generate_config)
        print(f"Configuration template generated: {args.generate_config}")
        return 0

    # Require case_dir for all other operations
    if not args.case_dir:
        parser.error("case_dir is required (unless using --check-deps or --generate-config)")

    # Validate case directory
    case_dir = Path(args.case_dir).resolve()
    if not case_dir.exists():
        print(f"Error: Case directory not found: {case_dir}", file=sys.stderr)
        return 1

    # Build configuration dictionary
    config_dict = {
        "case_dir": str(case_dir),
        "verbosity": args.verbose,
        "visualization": {
            "fields": args.fields,
            "time_steps": args.time_steps if args.time_steps != "all" else None,
            "resolution": args.resolution,
            "fps": args.fps,
        },
        "hemodynamics": {
            "skip_cycles": args.skip_cycles,
            "run_wss_postprocess": args.run_wss,
        },
        "output": {
            "output_dir": args.output or "postProcessing_results",
            "screenshots": not args.hemodynamics_only,
            "animations": not args.hemodynamics_only,
            "hemodynamics_report": not args.visualization_only,
        },
    }

    # Import after argument parsing for faster --help
    from .core import PostProcessor
    from .config import load_config

    # Load config file if provided
    if args.config:
        config = load_config(args.config, str(case_dir))
        # Override with CLI arguments
        config.visualization.fields = args.fields
        config.visualization.time_steps = args.time_steps if args.time_steps != "all" else None
        config.visualization.resolution = args.resolution
        config.visualization.fps = args.fps
        config.hemodynamics.skip_cycles = args.skip_cycles
        if args.output:
            config.output.output_dir = args.output
        processor = PostProcessor(case_dir, config, verbosity=args.verbose)
    else:
        processor = PostProcessor(case_dir, config_dict, verbosity=args.verbose)

    # Status check
    if args.status:
        processor.print_status()
        return 0

    # Run requested operations
    try:
        if args.hemodynamics_only:
            results = processor.run_hemodynamics()
            print("\nHemodynamics analysis complete!")
            print(f"  TAWSS mean: {results.tawss_mean:.4f} Pa")
            print(f"  OSI mean: {results.osi_mean:.4f}")
            if results.pressure_drops:
                for outlet, dp in results.pressure_drop_mmhg.items():
                    print(f"  Pressure drop ({outlet}): {dp:.2f} mmHg")

        elif args.visualization_only:
            from .dependencies import has_paraview

            if not has_paraview():
                print("Error: ParaView not available. Run with pvbatch:", file=sys.stderr)
                print("  pvbatch -m aortacfd_lib.post_processing.visualization /path/to/case", file=sys.stderr)
                return 1
            processor.run_visualization()
            print(f"\nVisualization complete! Output: {processor.output_dir}")

        elif args.animations_only:
            from .dependencies import has_ffmpeg

            if not has_ffmpeg():
                print("Error: ffmpeg not available", file=sys.stderr)
                return 1
            processor.run_animations(fps=args.fps)
            print(f"\nAnimations created! Output: {processor.output_dir}")

        else:
            # Run all
            results = processor.run_all()
            print(f"\nPost-processing complete! Output: {processor.output_dir}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose >= 2:
            import traceback

            traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
