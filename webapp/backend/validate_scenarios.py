#!/usr/bin/env python3
"""
Quick validation script for scenario YAML files.
Run with: python validate_scenarios.py
"""

from pathlib import Path

import yaml


def validate_scenarios():
    """Validate all scenario YAML files."""
    scenarios_dir = Path(__file__).parent / "app" / "content" / "scenarios"

    print(f"Looking in: {scenarios_dir.absolute()}")
    print(f"Directory exists: {scenarios_dir.exists()}")
    print()

    errors = []
    scenarios_loaded = []

    for yaml_file in sorted(scenarios_dir.glob("*.yaml")):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            # Check required fields
            required = ["id", "title", "description", "steps"]
            missing = [r for r in required if r not in data]

            if missing:
                errors.append(f"{yaml_file.name}: Missing fields: {missing}")
            else:
                step_count = len(data.get("steps", []))
                learning_outcomes = len(data.get("learning_outcomes", []))
                scenarios_loaded.append(
                    f"✓ {yaml_file.name}: {step_count} steps, {learning_outcomes} learning outcomes"
                )
        except Exception as e:
            errors.append(f"{yaml_file.name}: YAML Error: {e}")

    print("=== Scenario Validation Results ===")
    print()

    for s in scenarios_loaded:
        print(s)

    if errors:
        print()
        print("=== ERRORS ===")
        for e in errors:
            print(f"✗ {e}")
        return False
    else:
        print()
        print(f"✅ All {len(scenarios_loaded)} scenarios loaded successfully!")
        return True


if __name__ == "__main__":
    import sys

    success = validate_scenarios()
    sys.exit(0 if success else 1)
