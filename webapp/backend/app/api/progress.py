"""
Progress API Router

Endpoints for tracking user progress through scenarios.
Note: This is a simple in-memory implementation.
For production, replace with a proper database.
"""

from typing import Dict
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException

from app.models import UserProgress, ProgressUpdate

router = APIRouter()

# In-memory storage (replace with database for production)
_progress_store: Dict[str, UserProgress] = {}


@router.get("/{scenario_id}", response_model=UserProgress)
async def get_progress(request: Request, scenario_id: str):
    """
    Get user progress for a specific scenario.
    """
    scenarios = request.app.state.scenarios

    if scenario_id not in scenarios:
        raise HTTPException(
            status_code=404, detail=f"Scenario '{scenario_id}' not found"
        )

    if scenario_id not in _progress_store:
        _progress_store[scenario_id] = UserProgress(
            scenario_id=scenario_id,
            completed_steps=[],
            started_at=None,
            last_updated=None,
        )

    return _progress_store[scenario_id]


@router.post("/{scenario_id}", response_model=UserProgress)
async def update_progress(
    request: Request,
    scenario_id: str,
    update: ProgressUpdate,
):
    """
    Update progress for a scenario.
    """
    scenarios = request.app.state.scenarios

    if scenario_id not in scenarios:
        raise HTTPException(
            status_code=404, detail=f"Scenario '{scenario_id}' not found"
        )

    scenario = scenarios[scenario_id]

    # Verify step exists
    step_ids = [step.id for step in scenario.steps]
    if update.step_id not in step_ids:
        raise HTTPException(
            status_code=404,
            detail=f"Step '{update.step_id}' not found in scenario '{scenario_id}'",
        )

    # Get or create progress
    if scenario_id not in _progress_store:
        _progress_store[scenario_id] = UserProgress(
            scenario_id=scenario_id,
            completed_steps=[],
            started_at=datetime.utcnow().isoformat(),
            last_updated=None,
        )

    progress = _progress_store[scenario_id]

    # Update progress
    if update.completed:
        if update.step_id not in progress.completed_steps:
            progress.completed_steps.append(update.step_id)
    else:
        if update.step_id in progress.completed_steps:
            progress.completed_steps.remove(update.step_id)

    progress.last_updated = datetime.utcnow().isoformat()

    return progress


@router.delete("/{scenario_id}")
async def reset_progress(request: Request, scenario_id: str):
    """
    Reset progress for a specific scenario.
    """
    if scenario_id in _progress_store:
        del _progress_store[scenario_id]

    return {"message": f"Progress reset for scenario '{scenario_id}'"}


@router.get("/")
async def get_all_progress():
    """
    Get progress for all scenarios.
    """
    return list(_progress_store.values())
