const API_BASE = '/api'

export interface Scenario {
  id: string
  title: string
  description: string
  category: string
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  estimated_duration_minutes: number  // Backend field name
  prerequisites: string[]
  learning_outcomes?: string[]
  related_scenarios?: string[]
  steps: Step[]
}

export interface Step {
  id: string
  title: string
  type: 'info' | 'command' | 'code' | 'config' | 'checkpoint' | 'warning' | 'tip'  // Backend field name
  content: string
  code?: CodeBlock  // Backend uses single object, not array
  tips?: string[]
  warnings?: string[]
  expected_output?: string
  checkpoint_question?: string
  duration_minutes?: number
}

export interface CodeBlock {
  language: string
  content: string  // Backend uses 'content', CodeBlock component expects 'code'
  code?: string    // For compatibility with CodeBlock component
  filename?: string
  description?: string
  highlight_lines?: number[]
}

export interface ScenarioSummary {
  id: string
  title: string
  description: string
  category: string
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  estimated_duration_minutes: number
  step_count: number
  tags?: string[]
  order?: number
}

export interface Category {
  id: string
  name: string
  description: string
  scenario_count: number
}

export interface SearchResult {
  scenario_id: string
  scenario_title: string
  step_id?: string
  step_title?: string
  match_type: 'title' | 'description' | 'content' | 'code'
  snippet: string
  relevance_score: number
}

export interface UserProgress {
  user_id: string
  scenario_progress: Record<string, ScenarioProgress>
  last_updated: string
}

export interface ScenarioProgress {
  scenario_id: string
  completed_steps: string[]
  current_step?: string
  started_at: string
  completed_at?: string
}

// API Functions
export async function fetchScenarios(): Promise<ScenarioSummary[]> {
  const response = await fetch(`${API_BASE}/scenarios`)
  if (!response.ok) throw new Error('Failed to fetch scenarios')
  return response.json()
}

export async function fetchCategories(): Promise<Category[]> {
  const response = await fetch(`${API_BASE}/scenarios/categories`)
  if (!response.ok) throw new Error('Failed to fetch categories')
  return response.json()
}

export async function fetchScenario(scenarioId: string): Promise<Scenario> {
  const response = await fetch(`${API_BASE}/scenarios/${scenarioId}`)
  if (!response.ok) throw new Error('Failed to fetch scenario')
  return response.json()
}

export async function fetchStep(scenarioId: string, stepId: string): Promise<Step> {
  const response = await fetch(`${API_BASE}/scenarios/${scenarioId}/steps/${stepId}`)
  if (!response.ok) throw new Error('Failed to fetch step')
  return response.json()
}

export async function searchContent(query: string, category?: string): Promise<SearchResult[]> {
  const params = new URLSearchParams({ q: query })
  if (category) params.append('category', category)
  const response = await fetch(`${API_BASE}/search/?${params}`)
  if (!response.ok) throw new Error('Search failed')
  return response.json()
}

export async function fetchProgress(userId: string): Promise<UserProgress> {
  const response = await fetch(`${API_BASE}/progress/${userId}`)
  if (!response.ok) throw new Error('Failed to fetch progress')
  return response.json()
}

export async function updateProgress(
  userId: string,
  scenarioId: string,
  stepId: string,
  completed: boolean
): Promise<UserProgress> {
  const response = await fetch(`${API_BASE}/progress/${userId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      scenario_id: scenarioId,
      step_id: stepId,
      completed,
    }),
  })
  if (!response.ok) throw new Error('Failed to update progress')
  return response.json()
}

export async function resetProgress(userId: string, scenarioId?: string): Promise<void> {
  const params = scenarioId ? `?scenario_id=${scenarioId}` : ''
  const response = await fetch(`${API_BASE}/progress/${userId}/reset${params}`, {
    method: 'POST',
  })
  if (!response.ok) throw new Error('Failed to reset progress')
}
