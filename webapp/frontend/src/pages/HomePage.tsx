import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchScenarios, fetchCategories } from '@/lib/api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { 
  Clock, 
  BookOpen, 
  Rocket, 
  Settings, 
  GitBranch, 
  AlertTriangle,
  ChevronRight,
  Layers,
  ArrowRight,
  Container,
  Workflow
} from 'lucide-react'
import { formatDuration, cn } from '@/lib/utils'

const categoryIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  'getting-started': Rocket,
  'configuration': Settings,
  'deployment': Container,
  'workflows': Workflow,
  'integration': GitBranch,
  'troubleshooting': AlertTriangle,
}

const difficultyColors: Record<string, 'success' | 'warning' | 'destructive'> = {
  beginner: 'success',
  intermediate: 'warning',
  advanced: 'destructive',
}

// Visual workflow steps for the roadmap
const workflowSteps = [
  { id: 1, label: 'Setup', scenario: 'getting-started', icon: Rocket, color: 'bg-blue-500' },
  { id: 2, label: 'Configure', scenario: 'project-generation', icon: Settings, color: 'bg-purple-500' },
  { id: 3, label: 'Deploy', scenario: 'local-deployment', icon: Container, color: 'bg-green-500' },
  { id: 4, label: 'Dockerize', scenario: 'docker-deployment', icon: Layers, color: 'bg-orange-500' },
  { id: 5, label: 'Branch', scenario: 'feature-branch-workflows', icon: GitBranch, color: 'bg-pink-500' },
  { id: 6, label: 'Integrate', scenario: 'git-integration', icon: Workflow, color: 'bg-cyan-500' },
]

export default function HomePage() {
  const { data: scenarios, isLoading: scenariosLoading } = useQuery({
    queryKey: ['scenarios'],
    queryFn: fetchScenarios,
  })

  const { data: categories, isLoading: categoriesLoading } = useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
  })

  if (scenariosLoading || categoriesLoading) {
    return (
      <div className="container py-12">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-pulse text-muted-foreground">Loading...</div>
        </div>
      </div>
    )
  }

  // Group scenarios by category
  const scenariosByCategory = scenarios?.reduce((acc, scenario) => {
    if (!acc[scenario.category]) {
      acc[scenario.category] = []
    }
    acc[scenario.category].push(scenario)
    return acc
  }, {} as Record<string, typeof scenarios>)

  return (
    <div className="container py-8 md:py-12">
      {/* Hero Section */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight mb-4">
          Fabric CLI CI/CD Guide
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-8">
          Learn Microsoft Fabric deployment automation step by step. From environment
          setup to production deployments, we've got you covered.
        </p>
        
        {/* Quick Stats */}
        <div className="flex items-center justify-center gap-8 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <BookOpen className="h-4 w-4" />
            <span>{scenarios?.length || 0} Scenarios</span>
          </div>
          <div className="flex items-center gap-2">
            <Layers className="h-4 w-4" />
            <span>{categories?.length || 0} Categories</span>
          </div>
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            <span>
              {scenarios?.reduce((sum, s) => sum + s.estimated_time_minutes, 0) || 0} min total
            </span>
          </div>
        </div>
      </div>

      {/* Visual Workflow Roadmap */}
      <div className="mb-12">
        <h2 className="text-2xl font-semibold mb-6 text-center">Your Learning Journey</h2>
        <div className="relative">
          {/* Desktop Flow - Horizontal */}
          <div className="hidden md:flex items-center justify-between max-w-4xl mx-auto">
            {workflowSteps.map((step, index) => {
              const Icon = step.icon
              return (
                <div key={step.id} className="flex items-center">
                  <Link to={`/scenario/${step.scenario}`} className="group">
                    <div className="flex flex-col items-center">
                      <div className={cn(
                        "h-14 w-14 rounded-full flex items-center justify-center text-white shadow-lg transition-transform group-hover:scale-110",
                        step.color
                      )}>
                        <Icon className="h-6 w-6" />
                      </div>
                      <span className="mt-2 text-sm font-medium group-hover:text-primary transition-colors">
                        {step.label}
                      </span>
                      <span className="text-xs text-muted-foreground">Step {step.id}</span>
                    </div>
                  </Link>
                  {index < workflowSteps.length - 1 && (
                    <ArrowRight className="h-5 w-5 text-muted-foreground mx-4 flex-shrink-0" />
                  )}
                </div>
              )
            })}
          </div>
          
          {/* Mobile Flow - Vertical */}
          <div className="md:hidden space-y-3">
            {workflowSteps.map((step) => {
              const Icon = step.icon
              return (
                <Link key={step.id} to={`/scenario/${step.scenario}`}>
                  <div className="flex items-center gap-4 p-3 rounded-lg hover:bg-muted/50 transition-colors">
                    <div className={cn(
                      "h-10 w-10 rounded-full flex items-center justify-center text-white shadow-md flex-shrink-0",
                      step.color
                    )}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="flex-1">
                      <div className="font-medium">{step.label}</div>
                      <div className="text-xs text-muted-foreground">Step {step.id}</div>
                    </div>
                    <ChevronRight className="h-5 w-5 text-muted-foreground" />
                  </div>
                </Link>
              )
            })}
          </div>
        </div>
      </div>

      {/* Typical Workflow Example */}
      <div className="mb-12 bg-muted/30 rounded-xl p-6 md:p-8">
        <h2 className="text-xl font-semibold mb-4">📋 Typical Deployment Workflow</h2>
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-medium mb-3 flex items-center gap-2">
              <span className="h-6 w-6 rounded-full bg-blue-500 text-white text-xs flex items-center justify-center">1</span>
              First Time Setup
            </h3>
            <div className="space-y-2 text-sm pl-8">
              <div className="flex items-start gap-2">
                <code className="bg-background px-2 py-1 rounded text-xs">conda activate fabric-cli-cicd</code>
              </div>
              <div className="flex items-start gap-2">
                <code className="bg-background px-2 py-1 rounded text-xs">cp .env.template .env</code>
              </div>
              <div className="flex items-start gap-2">
                <code className="bg-background px-2 py-1 rounded text-xs">make diagnose</code>
              </div>
            </div>
          </div>
          
          <div>
            <h3 className="font-medium mb-3 flex items-center gap-2">
              <span className="h-6 w-6 rounded-full bg-purple-500 text-white text-xs flex items-center justify-center">2</span>
              Generate Config
            </h3>
            <div className="space-y-2 text-sm pl-8">
              <div className="flex items-start gap-2">
                <code className="bg-background px-2 py-1 rounded text-xs whitespace-nowrap overflow-x-auto">python scripts/generate_project.py "Org" "Project" --template basic_etl</code>
              </div>
              <div className="text-muted-foreground text-xs mt-1">
                → Creates <code className="bg-background px-1 rounded">config/projects/org/project.yaml</code>
              </div>
            </div>
          </div>
          
          <div>
            <h3 className="font-medium mb-3 flex items-center gap-2">
              <span className="h-6 w-6 rounded-full bg-green-500 text-white text-xs flex items-center justify-center">3</span>
              Deploy to Fabric
            </h3>
            <div className="space-y-2 text-sm pl-8">
              <div className="flex items-start gap-2">
                <code className="bg-background px-2 py-1 rounded text-xs">make validate config=path/to/config.yaml</code>
              </div>
              <div className="flex items-start gap-2">
                <code className="bg-background px-2 py-1 rounded text-xs">make deploy config=path/to/config.yaml env=dev</code>
              </div>
            </div>
          </div>
          
          <div>
            <h3 className="font-medium mb-3 flex items-center gap-2">
              <span className="h-6 w-6 rounded-full bg-orange-500 text-white text-xs flex items-center justify-center">4</span>
              Verify in Portal
            </h3>
            <div className="space-y-2 text-sm pl-8">
              <div className="text-muted-foreground">
                ✓ Workspace created in Microsoft Fabric<br/>
                ✓ Lakehouse with Bronze/Silver/Gold folders<br/>
                ✓ Notebooks uploaded and configured<br/>
                ✓ Git connection established (if configured)
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Scenarios by Category */}
      {categories?.map((category) => {
        const categoryScenarios = scenariosByCategory?.[category.id] || []
        if (categoryScenarios.length === 0) return null

        const Icon = categoryIcons[category.id] || BookOpen

        return (
          <div key={category.id} className="mb-12">
            <div className="flex items-center gap-3 mb-6">
              <Icon className="h-6 w-6 text-primary" />
              <h2 className="text-2xl font-semibold">{category.name}</h2>
            </div>
            
            <div className="grid gap-4 md:grid-cols-2">
              {categoryScenarios.map((scenario) => (
                <Link key={scenario.id} to={`/scenario/${scenario.id}`}>
                  <Card className="h-full hover:shadow-md transition-all hover:border-primary/50 cursor-pointer group">
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <CardTitle className="text-lg group-hover:text-primary transition-colors">
                            {scenario.title}
                          </CardTitle>
                          <CardDescription className="mt-1 line-clamp-2">
                            {scenario.description}
                          </CardDescription>
                        </div>
                        <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors" />
                      </div>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="flex items-center gap-4 text-sm">
                        <Badge variant={difficultyColors[scenario.difficulty]}>
                          {scenario.difficulty}
                        </Badge>
                        <div className="flex items-center gap-1 text-muted-foreground">
                          <Clock className="h-4 w-4" />
                          <span>{formatDuration(scenario.estimated_time_minutes)}</span>
                        </div>
                        <div className="flex items-center gap-1 text-muted-foreground">
                          <BookOpen className="h-4 w-4" />
                          <span>{scenario.step_count} steps</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          </div>
        )
      })}

      {/* Getting Started CTA */}
      <div className="bg-primary/5 rounded-lg p-8 text-center">
        <h2 className="text-2xl font-semibold mb-4">Ready to Get Started?</h2>
        <p className="text-muted-foreground mb-6 max-w-lg mx-auto">
          Begin your journey with the Getting Started guide to set up your environment
          and configure credentials.
        </p>
        <Link to="/scenario/getting-started">
          <Button size="lg">
            <Rocket className="h-4 w-4 mr-2" />
            Start the Guide
          </Button>
        </Link>
      </div>
    </div>
  )
}
