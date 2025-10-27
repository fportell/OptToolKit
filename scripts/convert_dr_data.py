#!/usr/bin/env python3
"""
Convert legacy DR-Tracker data files from Python to JSON format.

This script converts:
1. idc_hazards.py → idc_hazards.json
2. program_areas.py → program_areas.json

Note: The legacy .py files are actually JSON content, so we just copy and validate them.
"""

import json
from pathlib import Path

def convert_hazards():
    """Convert idc_hazards.py to JSON format."""
    print("Converting idc_hazards.py to JSON...")

    input_path = Path(__file__).parent.parent / 'legacy_code' / 'ops_toolkit' / 'src' / 'data' / 'daily_report' / 'idc_hazards.py'
    output_path = Path(__file__).parent.parent / 'app' / 'data' / 'dr_tracker' / 'idc_hazards.json'

    # Read the .py file (which contains JSON)
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse to validate it's valid JSON
    hazards_list = json.loads(content)

    # Write to new location
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(hazards_list, f, indent=2, ensure_ascii=False)

    print(f"✓ Converted {len(hazards_list)} hazards to {output_path}")
    return len(hazards_list)

def convert_program_areas():
    """Convert program_areas.py to JSON format."""
    print("Converting program_areas.py to JSON...")

    input_path = Path(__file__).parent.parent / 'legacy_code' / 'ops_toolkit' / 'src' / 'data' / 'daily_report' / 'program_areas.py'
    output_path = Path(__file__).parent.parent / 'app' / 'data' / 'dr_tracker' / 'program_areas.json'

    # Read the .py file (which contains JSON)
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse to validate it's valid JSON
    areas_list = json.loads(content)

    # Write to new location
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(areas_list, f, indent=2, ensure_ascii=False)

    print(f"✓ Converted {len(areas_list)} program areas to {output_path}")
    return len(areas_list)

def main():
    """Main conversion function."""
    print("=" * 60)
    print("DR-Tracker Data Conversion Script")
    print("=" * 60)
    print()

    try:
        hazard_count = convert_hazards()
        area_count = convert_program_areas()

        print()
        print("=" * 60)
        print("Conversion Complete!")
        print(f"  - {hazard_count} hazards converted")
        print(f"  - {area_count} program areas converted")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
