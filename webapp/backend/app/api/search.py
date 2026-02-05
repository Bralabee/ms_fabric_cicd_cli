"""
Search API Router

Endpoints for searching scenario content.
"""

from typing import List
from fastapi import APIRouter, Request, Query

from app.models import SearchResult

router = APIRouter()


def calculate_relevance(query: str, text: str) -> float:
    """Calculate simple relevance score based on query matches."""
    query_lower = query.lower()
    text_lower = text.lower()

    # Exact match gets highest score
    if query_lower == text_lower:
        return 1.0

    # Title/word match
    if query_lower in text_lower:
        # Earlier position = higher relevance
        position = text_lower.index(query_lower)
        position_score = max(0, 1 - (position / len(text_lower)))
        return 0.7 + (0.3 * position_score)

    # Word-level matching
    query_words = set(query_lower.split())
    text_words = set(text_lower.split())
    matching_words = query_words.intersection(text_words)

    if matching_words:
        return 0.3 * (len(matching_words) / len(query_words))

    return 0.0


def get_snippet(text: str, query: str, max_length: int = 150) -> str:
    """Extract a relevant snippet containing the query."""
    query_lower = query.lower()
    text_lower = text.lower()

    if query_lower in text_lower:
        start = text_lower.index(query_lower)
        # Expand to include surrounding context
        snippet_start = max(0, start - 50)
        snippet_end = min(len(text), start + len(query) + 100)

        snippet = text[snippet_start:snippet_end]
        if snippet_start > 0:
            snippet = "..." + snippet
        if snippet_end < len(text):
            snippet = snippet + "..."

        return snippet

    # Return first part of text if no match found
    return text[:max_length] + ("..." if len(text) > max_length else "")


@router.get("/", response_model=List[SearchResult])
async def search(
    request: Request,
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
):
    """
    Search across all scenarios and steps.

    Searches in:
    - Scenario titles and descriptions
    - Step titles and content
    - Tags
    """
    scenarios = request.app.state.scenarios
    results = []

    for scenario in scenarios.values():
        # Search in scenario title
        title_relevance = calculate_relevance(q, scenario.title)
        if title_relevance > 0:
            results.append(
                SearchResult(
                    scenario_id=scenario.id,
                    scenario_title=scenario.title,
                    match_type="title",
                    snippet=scenario.description[:150],
                    relevance_score=title_relevance,
                )
            )

        # Search in scenario description
        desc_relevance = calculate_relevance(q, scenario.description)
        if desc_relevance > 0 and title_relevance == 0:
            results.append(
                SearchResult(
                    scenario_id=scenario.id,
                    scenario_title=scenario.title,
                    match_type="content",
                    snippet=get_snippet(scenario.description, q),
                    relevance_score=desc_relevance * 0.9,
                )
            )

        # Search in tags
        for tag in scenario.tags:
            tag_relevance = calculate_relevance(q, tag)
            if tag_relevance > 0.5:
                results.append(
                    SearchResult(
                        scenario_id=scenario.id,
                        scenario_title=scenario.title,
                        match_type="tag",
                        snippet=f"Tagged: {tag}",
                        relevance_score=tag_relevance * 0.8,
                    )
                )
                break  # Only one tag match per scenario

        # Search in steps
        for step in scenario.steps:
            step_title_relevance = calculate_relevance(q, step.title)
            if step_title_relevance > 0:
                results.append(
                    SearchResult(
                        scenario_id=scenario.id,
                        scenario_title=scenario.title,
                        step_id=step.id,
                        step_title=step.title,
                        match_type="title",
                        snippet=step.content[:150] if step.content else "",
                        relevance_score=step_title_relevance * 0.85,
                    )
                )

            step_content_relevance = calculate_relevance(q, step.content)
            if step_content_relevance > 0 and step_title_relevance == 0:
                results.append(
                    SearchResult(
                        scenario_id=scenario.id,
                        scenario_title=scenario.title,
                        step_id=step.id,
                        step_title=step.title,
                        match_type="content",
                        snippet=get_snippet(step.content, q),
                        relevance_score=step_content_relevance * 0.7,
                    )
                )

    # Sort by relevance and limit
    results.sort(key=lambda x: x.relevance_score, reverse=True)
    return results[:limit]
