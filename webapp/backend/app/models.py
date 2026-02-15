"""
Pydantic models for the Guide API.
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DifficultyLevel(str, Enum):
    """Difficulty level for a scenario or step."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class StepType(str, Enum):
    """Type of step in a scenario."""

    INFO = "info"
    COMMAND = "command"
    CODE = "code"
    CONFIG = "config"
    CHECKPOINT = "checkpoint"
    WARNING = "warning"
    TIP = "tip"


class CodeBlock(BaseModel):
    """A code block with language and content."""

    language: str = "bash"
    content: str
    filename: Optional[str] = None
    highlight_lines: Optional[List[int]] = None


class Step(BaseModel):
    """A single step in a scenario."""

    id: str
    title: str
    type: StepType = StepType.INFO
    content: str
    code: Optional[CodeBlock] = None
    expected_output: Optional[str] = None
    tips: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    duration_minutes: Optional[int] = None
    checkpoint_question: Optional[str] = None


class Scenario(BaseModel):
    """A complete scenario with metadata and steps."""

    id: str
    title: str
    description: str
    difficulty: DifficultyLevel = DifficultyLevel.BEGINNER
    estimated_duration_minutes: int
    prerequisites: List[str] = Field(default_factory=list)
    learning_outcomes: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    steps: List[Step]
    related_scenarios: List[str] = Field(default_factory=list)
    category: str = "general"
    order: int = 0


class ScenarioSummary(BaseModel):
    """Summary of a scenario for listing."""

    id: str
    title: str
    description: str
    difficulty: DifficultyLevel
    estimated_duration_minutes: int
    tags: List[str]
    category: str
    order: int
    step_count: int


class Category(BaseModel):
    """A category grouping scenarios."""

    id: str
    title: str
    description: str
    icon: str
    order: int
    scenarios: List[ScenarioSummary]


class SearchResult(BaseModel):
    """A search result item."""

    scenario_id: str
    scenario_title: str
    step_id: Optional[str] = None
    step_title: Optional[str] = None
    match_type: str  # "title", "content", "tag"
    snippet: str
    relevance_score: float


class UserProgress(BaseModel):
    """User progress for a scenario."""

    scenario_id: str
    completed_steps: List[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    last_updated: Optional[str] = None


class ProgressUpdate(BaseModel):
    """Request to update progress."""

    step_id: str
    completed: bool = True
