# src/writers/header.py
"""
OpenFOAM file header generator.

Provides consistent header formatting for all OpenFOAM dictionary files.
"""

from typing import Optional


def openfoam_header(
    class_name: str,
    object_name: str,
    location: str = "system",
    version: str = "2.0",
    format_type: str = "ascii",
    note: Optional[str] = None,
) -> str:
    """
    Generate OpenFOAM file header.

    Args:
        class_name: OpenFOAM class (e.g., 'dictionary', 'volScalarField')
        object_name: Object name (e.g., 'fvSchemes', 'U')
        location: File location (e.g., 'system', 'constant', '0')
        version: Format version (default: '2.0')
        format_type: Format type (default: 'ascii')
        note: Optional note to include in header

    Returns:
        Formatted header string

    Example:
        >>> header = openfoam_header('dictionary', 'fvSchemes')
        >>> print(header)
        FoamFile
        {
            version     2.0;
            format      ascii;
            class       dictionary;
            location    "system";
            object      fvSchemes;
        }
    """
    lines = [
        "/*--------------------------------*- C++ -*----------------------------------*\\",
        "| =========                 |                                                 |",
        "| \\\\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox           |",
        "|  \\\\    /   O peration     | Version:  12                                    |",
        "|   \\\\  /    A nd           | Website:  www.openfoam.org                      |",
        "|    \\\\/     M anipulation  |                                                 |",
        "\\*---------------------------------------------------------------------------*/",
    ]

    if note:
        lines.append(f"// Note: {note}")
        lines.append("")

    lines.extend([
        "FoamFile",
        "{",
        f"    version     {version};",
        f"    format      {format_type};",
        f"    class       {class_name};",
        f'    location    "{location}";',
        f"    object      {object_name};",
        "}",
        "// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //",
        "",
    ])

    return "\n".join(lines)


def format_dict_entry(key: str, value, indent: int = 4) -> str:
    """
    Format a dictionary entry with proper spacing.

    Args:
        key: Entry key
        value: Entry value
        indent: Number of spaces for indentation

    Returns:
        Formatted entry string
    """
    spaces = " " * indent
    # Align values at column 20
    key_width = max(16, len(key) + 1)
    return f"{spaces}{key:<{key_width}}{value};"


def format_sub_dict(name: str, entries: dict, indent: int = 4) -> str:
    """
    Format a sub-dictionary.

    Args:
        name: Dictionary name
        entries: Dictionary entries
        indent: Base indentation

    Returns:
        Formatted sub-dictionary string
    """
    spaces = " " * indent
    lines = [f"{spaces}{name}", f"{spaces}{{"]

    for key, value in entries.items():
        if isinstance(value, dict):
            # Nested dict
            lines.append(format_sub_dict(key, value, indent + 4))
        else:
            lines.append(format_dict_entry(key, value, indent + 4))

    lines.append(f"{spaces}}}")
    return "\n".join(lines)


def format_value(value) -> str:
    """
    Format a value for OpenFOAM output.

    Args:
        value: Value to format

    Returns:
        Formatted string
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, float):
        # Scientific notation for very small/large numbers
        if abs(value) < 1e-4 or abs(value) > 1e6:
            return f"{value:.6e}"
        else:
            return str(value)
    elif isinstance(value, str):
        return value
    else:
        return str(value)
