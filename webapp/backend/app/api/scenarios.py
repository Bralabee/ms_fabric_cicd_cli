"""
Scenarios API Router

Endpoints for retrieving and navigating scenario content.
"""

from typing import List, Optional

from app.models import Category, Scenario, ScenarioSummary
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("", response_model=List[ScenarioSummary])
async def list_scenarios(
    request: Request,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    tag: Optional[str] = None,
):
    """
    List all available scenarios with optional filtering.

    - **category**: Filter by category (e.g., "getting-started", "deployment")
    - **difficulty**: Filter by difficulty level
    - **tag**: Filter by tag
    """
    scenarios = request.app.state.scenarios

    summaries = []
    for scenario in scenarios.values():
        # Apply filters
        if category and scenario.category != category:
            continue
        if difficulty and scenario.difficulty.value != difficulty:
            continue
        if tag and tag not in scenario.tags:
            continue

        summaries.append(
            ScenarioSummary(
                id=scenario.id,
                title=scenario.title,
                description=scenario.description,
                difficulty=scenario.difficulty,
                estimated_duration_minutes=scenario.estimated_duration_minutes,
                tags=scenario.tags,
                category=scenario.category,
                order=scenario.order,
                step_count=len(scenario.steps),
            )
        )

    # Sort by order, then by title
    summaries.sort(key=lambda x: (x.order, x.title))
    return summaries


@router.get("/categories", response_model=List[Category])
async def list_categories(request: Request):
    """
    List all scenario categories with their scenarios.
    """
    scenarios = request.app.state.scenarios

    # Define category metadata
    category_meta = {
        "getting-started": {
            "title": "Getting Started",
            "description": "Prerequisites, installation, and initial setup",
            "icon": "rocket",
            "order": 1,
        },
        "configuration": {
            "title": "Configuration",
            "description": "Blueprint templates and YAML configuration patterns",
            "icon": "settings",
            "order": 2,
        },
        "deployment": {
            "title": "Deployment",
            "description": "Local and Docker deployment workflows",
            "icon": "cloud-arrow-up",
            "order": 3,
        },
        "workflows": {
            "title": "Workflows",
            "description": "Feature branches and development patterns",
            "icon": "git-branch",
            "order": 4,
        },
        "integration": {
            "title": "Integration",
            "description": "Git integration and CI/CD pipelines",
            "icon": "plug",
            "order": 5,
        },
        "troubleshooting": {
            "title": "Troubleshooting",
            "description": "Common issues and solutions",
            "icon": "wrench",
            "order": 6,
        },
    }

    # Group scenarios by category
    categories_dict = {}
    for scenario in scenarios.values():
        cat_id = scenario.category
        if cat_id not in categories_dict:
            meta = category_meta.get(
                cat_id,
                {
                    "title": cat_id.replace("-", " ").title(),
                    "description": f"Scenarios for {cat_id}",
                    "icon": "folder",
                    "order": 99,
                },
            )
            categories_dict[cat_id] = Category(
                id=cat_id,
                title=meta["title"],
                description=meta["description"],
                icon=meta["icon"],
                order=meta["order"],
                scenarios=[],
            )

        categories_dict[cat_id].scenarios.append(
            ScenarioSummary(
                id=scenario.id,
                title=scenario.title,
                description=scenario.description,
                difficulty=scenario.difficulty,
                estimated_duration_minutes=scenario.estimated_duration_minutes,
                tags=scenario.tags,
                category=scenario.category,
                order=scenario.order,
                step_count=len(scenario.steps),
            )
        )

    # Sort scenarios within each category
    for category in categories_dict.values():
        category.scenarios.sort(key=lambda x: (x.order, x.title))

    # Sort categories by order
    result = sorted(categories_dict.values(), key=lambda x: x.order)
    return result


@router.get("/{scenario_id}", response_model=Scenario)
async def get_scenario(request: Request, scenario_id: str):
    """
    Get detailed information about a specific scenario.
    """
    scenarios = request.app.state.scenarios

    if scenario_id not in scenarios:
        raise HTTPException(
            status_code=404, detail=f"Scenario '{scenario_id}' not found"
        )

    return scenarios[scenario_id]


@router.get("/{scenario_id}/steps/{step_id}")
async def get_step(request: Request, scenario_id: str, step_id: str):
    """
    Get a specific step from a scenario.
    """
    scenarios = request.app.state.scenarios

    if scenario_id not in scenarios:
        raise HTTPException(
            status_code=404, detail=f"Scenario '{scenario_id}' not found"
        )

    scenario = scenarios[scenario_id]
    for step in scenario.steps:
        if step.id == step_id:
            return step

    raise HTTPException(
        status_code=404,
        detail=f"Step '{step_id}' not found in scenario '{scenario_id}'",
    )
