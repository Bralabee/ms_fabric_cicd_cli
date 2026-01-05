"""
Content Loader

Loads scenario definitions from YAML files.
"""

import yaml
from pathlib import Path
from typing import Dict

from app.models import Scenario, Step, CodeBlock, DifficultyLevel, StepType


def load_scenario_from_yaml(file_path: Path) -> Scenario:
    """Load a single scenario from a YAML file."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    # Parse steps
    steps = []
    for step_data in data.get("steps", []):
        code = None
        if "code" in step_data:
            code_data = step_data["code"]
            code = CodeBlock(
                language=code_data.get("language", "bash"),
                content=code_data.get("content", ""),
                filename=code_data.get("filename"),
                highlight_lines=code_data.get("highlight_lines"),
            )
        
        step = Step(
            id=step_data["id"],
            title=step_data["title"],
            type=StepType(step_data.get("type", "info")),
            content=step_data.get("content", ""),
            code=code,
            expected_output=step_data.get("expected_output"),
            tips=step_data.get("tips"),
            warnings=step_data.get("warnings"),
            duration_minutes=step_data.get("duration_minutes"),
            checkpoint_question=step_data.get("checkpoint_question"),
        )
        steps.append(step)
    
    return Scenario(
        id=data["id"],
        title=data["title"],
        description=data["description"],
        difficulty=DifficultyLevel(data.get("difficulty", "beginner")),
        estimated_duration_minutes=data.get("estimated_duration_minutes", 15),
        prerequisites=data.get("prerequisites", []),
        learning_outcomes=data.get("learning_outcomes", []),
        tags=data.get("tags", []),
        steps=steps,
        related_scenarios=data.get("related_scenarios", []),
        category=data.get("category", "general"),
        order=data.get("order", 0),
    )


def load_all_scenarios() -> Dict[str, Scenario]:
    """Load all scenarios from the content/scenarios directory."""
    scenarios = {}
    content_dir = Path(__file__).parent / "scenarios"
    
    if not content_dir.exists():
        print(f"Warning: Scenarios directory not found at {content_dir}")
        return scenarios
    
    for yaml_file in sorted(content_dir.glob("*.yaml")):
        try:
            scenario = load_scenario_from_yaml(yaml_file)
            scenarios[scenario.id] = scenario
            print(f"Loaded scenario: {scenario.id} ({len(scenario.steps)} steps)")
        except Exception as e:
            print(f"Error loading {yaml_file}: {e}")
    
    print(f"Loaded {len(scenarios)} scenarios total")
    return scenarios
