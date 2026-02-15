import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  fetchScenario,
  fetchProgress,
  updateProgress
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { CodeBlock } from '@/components/CodeBlock'
import { MarkdownContent } from '@/components/MarkdownContent'
import {
  ChevronLeft,
  ChevronRight,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Lightbulb,
  BookOpen,
  Play,
  CheckSquare,
  Wrench,
  Home,
  Terminal,
  ArrowRight,
  HelpCircle
} from 'lucide-react'
import { formatDuration, cn } from '@/lib/utils'

// Simple user ID for demo (in production, use auth)
const USER_ID = 'demo-user'

// Map backend step types to icons
const stepTypeIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  info: BookOpen,
  command: Play,
  code: Play,
  config: CheckSquare,
  checkpoint: CheckSquare,
  warning: AlertTriangle,
  tip: Lightbulb,
  // Legacy mappings for compatibility
  concept: BookOpen,
  action: Play,
  verification: CheckSquare,
  troubleshooting: Wrench,
}

// Map backend step types to colors
const stepTypeColors: Record<string, string> = {
  info: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100',
  command: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100',
  code: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100',
  config: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100',
  checkpoint: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100',
  warning: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100',
  tip: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-100',
  // Legacy mappings
  concept: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-100',
  action: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100',
  verification: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-100',
  troubleshooting: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-100',
}

export default function ScenarioPage() {
  const { scenarioId } = useParams<{ scenarioId: string }>()
  const queryClient = useQueryClient()
  const [currentStepIndex, setCurrentStepIndex] = useState(0)

  const { data: scenario, isLoading, error } = useQuery({
    queryKey: ['scenario', scenarioId],
    queryFn: () => fetchScenario(scenarioId!),
    enabled: !!scenarioId,
  })

  const { data: progress } = useQuery({
    queryKey: ['progress', USER_ID],
    queryFn: () => fetchProgress(USER_ID),
  })

  const updateProgressMutation = useMutation({
    mutationFn: (params: { stepId: string; completed: boolean }) =>
      updateProgress(USER_ID, scenarioId!, params.stepId, params.completed),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['progress', USER_ID] })
    },
  })

  // Get current step
  const currentStep = scenario?.steps[currentStepIndex]

  // Calculate progress
  const completedSteps = progress?.scenario_progress[scenarioId!]?.completed_steps || []
  const progressPercent = scenario
    ? (completedSteps.length / scenario.steps.length) * 100
    : 0

  const isStepCompleted = (stepId: string) => completedSteps.includes(stepId)

  const handleStepComplete = () => {
    if (currentStep && !isStepCompleted(currentStep.id)) {
      updateProgressMutation.mutate({ stepId: currentStep.id, completed: true })
    }

    // Auto-advance to next step
    if (currentStepIndex < (scenario?.steps.length || 0) - 1) {
      setCurrentStepIndex(prev => prev + 1)
    }
  }

  const handlePrevStep = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(prev => prev - 1)
    }
  }

  if (isLoading) {
    return (
      <div className="container py-12">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-pulse text-muted-foreground">Loading scenario...</div>
        </div>
      </div>
    )
  }

  if (error || !scenario) {
    return (
      <div className="container py-12">
        <Card className="max-w-lg mx-auto">
          <CardContent className="pt-6 text-center">
            <AlertTriangle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Scenario Not Found</h2>
            <p className="text-muted-foreground mb-4">
              The scenario you're looking for doesn't exist or couldn't be loaded.
            </p>
            <Link to="/">
              <Button>
                <Home className="h-4 w-4 mr-2" />
                Back to Home
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  const StepIcon = currentStep ? stepTypeIcons[currentStep.type] || BookOpen : BookOpen

  return (
    <div className="min-h-screen flex">
      {/* Sidebar - Step Navigation */}
      <aside className="hidden lg:flex w-80 flex-col border-r bg-muted/30">
        <div className="p-4 border-b">
          <Link to="/" className="text-sm text-muted-foreground hover:text-foreground flex items-center gap-1 mb-3">
            <ChevronLeft className="h-4 w-4" />
            Back to Guides
          </Link>
          <h2 className="font-semibold text-lg line-clamp-2">{scenario.title}</h2>
          <div className="flex items-center gap-2 mt-2 text-sm text-muted-foreground">
            <Clock className="h-4 w-4" />
            <span>{formatDuration(scenario.estimated_duration_minutes)}</span>
          </div>
        </div>

        {/* Progress */}
        <div className="p-4 border-b">
          <div className="flex items-center justify-between text-sm mb-2">
            <span className="text-muted-foreground">Progress</span>
            <span className="font-medium">{Math.round(progressPercent)}%</span>
          </div>
          <Progress value={progressPercent} className="h-2" />
        </div>

        {/* Learning Outcomes */}
        {scenario.learning_outcomes && scenario.learning_outcomes.length > 0 && (
          <div className="p-4 border-b">
            <h3 className="text-sm font-medium mb-2 flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />
              You'll Learn
            </h3>
            <ul className="space-y-1">
              {scenario.learning_outcomes.slice(0, 4).map((outcome, index) => (
                <li key={index} className="text-xs text-muted-foreground flex items-start gap-1.5">
                  <span className="text-green-500 mt-0.5">✓</span>
                  <span className="line-clamp-2">{outcome}</span>
                </li>
              ))}
              {scenario.learning_outcomes.length > 4 && (
                <li className="text-xs text-muted-foreground italic">
                  +{scenario.learning_outcomes.length - 4} more...
                </li>
              )}
            </ul>
          </div>
        )}

        {/* Step List */}
        <ScrollArea className="flex-1">
          <div className="p-2">
            {scenario.steps.map((step, index) => {
              const isActive = index === currentStepIndex
              const isCompleted = isStepCompleted(step.id)
              const StepTypeIcon = stepTypeIcons[step.type] || BookOpen

              return (
                <button
                  key={step.id}
                  onClick={() => setCurrentStepIndex(index)}
                  className={cn(
                    'w-full text-left p-3 rounded-lg mb-1 transition-all',
                    'hover:bg-accent',
                    isActive && 'bg-accent border border-primary/20'
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className={cn(
                      'mt-0.5 h-6 w-6 rounded-full flex items-center justify-center flex-shrink-0',
                      isCompleted ? 'bg-green-100 text-green-600' : 'bg-muted'
                    )}>
                      {isCompleted ? (
                        <CheckCircle2 className="h-4 w-4" />
                      ) : (
                        <span className="text-xs font-medium">{index + 1}</span>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium line-clamp-2">{step.title}</div>
                      <div className="flex items-center gap-1 mt-1">
                        <StepTypeIcon className="h-3 w-3 text-muted-foreground" />
                        <span className="text-xs text-muted-foreground capitalize">
                          {step.type}
                        </span>
                      </div>
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        </ScrollArea>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-4xl mx-auto p-6 md:p-8">
          {/* Mobile Progress */}
          <div className="lg:hidden mb-6">
            <div className="flex items-center justify-between text-sm mb-2">
              <span className="text-muted-foreground">
                Step {currentStepIndex + 1} of {scenario.steps.length}
              </span>
              <span className="font-medium">{Math.round(progressPercent)}% complete</span>
            </div>
            <Progress value={progressPercent} className="h-2" />
          </div>

          {/* Step Header */}
          {currentStep && (
            <>
              <div className="mb-8">
                <div className="flex items-center gap-2 mb-3">
                  <Badge className={stepTypeColors[currentStep.type]}>
                    <StepIcon className="h-3 w-3 mr-1" />
                    {currentStep.type}
                  </Badge>
                  <span className="text-sm text-muted-foreground">
                    Step {currentStepIndex + 1} of {scenario.steps.length}
                  </span>
                </div>
                <h1 className="text-3xl font-bold">{currentStep.title}</h1>
              </div>

              {/* Step Content */}
              <div className="space-y-6">
                {/* Main Content */}
                <MarkdownContent content={currentStep.content} />

                {/* Tips */}
                {currentStep.tips && currentStep.tips.length > 0 && (
                  <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/50">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg flex items-center gap-2 text-blue-700 dark:text-blue-300">
                        <Lightbulb className="h-5 w-5" />
                        Tips
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2">
                        {currentStep.tips.map((tip, index) => (
                          <li key={index} className="flex items-start gap-2 text-sm">
                            <span className="text-blue-500 mt-1">•</span>
                            <MarkdownContent content={tip} className="flex-1 [&>p]:my-0 [&>p]:leading-normal" />
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}

                {/* Warnings */}
                {currentStep.warnings && currentStep.warnings.length > 0 && (
                  <Card className="border-amber-200 bg-amber-50/50 dark:border-amber-900 dark:bg-amber-950/50">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg flex items-center gap-2 text-amber-700 dark:text-amber-300">
                        <AlertTriangle className="h-5 w-5" />
                        Warnings
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <ul className="space-y-2">
                        {currentStep.warnings.map((warning, index) => (
                          <li key={index} className="flex items-start gap-2 text-sm">
                            <span className="text-amber-500 mt-1">⚠</span>
                            <MarkdownContent content={warning} className="flex-1 [&>p]:my-0 [&>p]:leading-normal" />
                          </li>
                        ))}
                      </ul>
                    </CardContent>
                  </Card>
                )}

                {/* Code Block - backend returns single code object */}
                {currentStep.code && (
                  <CodeBlock codeBlock={currentStep.code} />
                )}

                {/* Expected Output */}
                {currentStep.expected_output && (
                  <Card className="border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/50">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg flex items-center gap-2 text-green-700 dark:text-green-300">
                        <Terminal className="h-5 w-5" />
                        Expected Output
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <pre className="text-sm font-mono whitespace-pre-wrap bg-black/5 dark:bg-white/5 p-3 rounded-lg overflow-x-auto">
                        {currentStep.expected_output}
                      </pre>
                    </CardContent>
                  </Card>
                )}

                {/* Checkpoint Question */}
                {currentStep.checkpoint_question && (
                  <Card className="border-purple-200 bg-purple-50/50 dark:border-purple-900 dark:bg-purple-950/50">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg flex items-center gap-2 text-purple-700 dark:text-purple-300">
                        <HelpCircle className="h-5 w-5" />
                        Checkpoint
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm">{currentStep.checkpoint_question}</p>
                    </CardContent>
                  </Card>
                )}
              </div>

              {/* Navigation */}
              <div className="flex items-center justify-between mt-12 pt-8 border-t">
                <Button
                  variant="outline"
                  onClick={handlePrevStep}
                  disabled={currentStepIndex === 0}
                >
                  <ChevronLeft className="h-4 w-4 mr-2" />
                  Previous
                </Button>

                <div className="flex items-center gap-3">
                  {!isStepCompleted(currentStep.id) && (
                    <Button
                      variant="secondary"
                      onClick={() => updateProgressMutation.mutate({
                        stepId: currentStep.id,
                        completed: true
                      })}
                    >
                      <CheckCircle2 className="h-4 w-4 mr-2" />
                      Mark Complete
                    </Button>
                  )}

                  {currentStepIndex < scenario.steps.length - 1 ? (
                    <Button onClick={handleStepComplete}>
                      Next Step
                      <ChevronRight className="h-4 w-4 ml-2" />
                    </Button>
                  ) : (
                    <Link to="/">
                      <Button variant="default">
                        <CheckCircle2 className="h-4 w-4 mr-2" />
                        Complete Scenario
                      </Button>
                    </Link>
                  )}
                </div>
              </div>

              {/* Related Scenarios - show on last step */}
              {currentStepIndex === scenario.steps.length - 1 && scenario.related_scenarios && scenario.related_scenarios.length > 0 && (
                <div className="mt-8 pt-6 border-t">
                  <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                    <ArrowRight className="h-5 w-5 text-primary" />
                    Continue Learning
                  </h3>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {scenario.related_scenarios.map((relatedId) => (
                      <Link key={relatedId} to={`/scenario/${relatedId}`}>
                        <Card className="hover:shadow-md transition-all hover:border-primary/50 cursor-pointer h-full">
                          <CardContent className="p-4">
                            <div className="flex items-center justify-between">
                              <span className="font-medium capitalize">
                                {relatedId.replace(/-/g, ' ')}
                              </span>
                              <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            </div>
                          </CardContent>
                        </Card>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  )
}
