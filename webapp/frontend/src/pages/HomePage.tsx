import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchScenarios, fetchCategories } from '@/lib/api'
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import { 
  Clock, 
  BookOpen, 
  Rocket, 
  Settings, 
  GitBranch, 
  AlertTriangle,
  ChevronRight,
  Layers
} from 'lucide-react'
import { formatDuration, cn } from '@/lib/utils'

const categoryIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  'getting-started': Rocket,
  'configuration': Settings,
  'deployment': Layers,
  'workflows': GitBranch,
  'integration': GitBranch,
  'troubleshooting': AlertTriangle,
}

const difficultyColors: Record<string, 'success' | 'warning' | 'destructive'> = {
  beginner: 'success',
  intermediate: 'warning',
  advanced: 'destructive',
}

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

      {/* Categories Overview */}
      <div className="mb-12">
        <h2 className="text-2xl font-semibold mb-6">Learning Path</h2>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {categories?.map((category, index) => {
            const Icon = categoryIcons[category.id] || BookOpen
            return (
              <Card key={category.id} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{category.name}</CardTitle>
                      <CardDescription className="text-xs">
                        {category.scenario_count} scenario{category.scenario_count !== 1 ? 's' : ''}
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{category.description}</p>
                </CardContent>
                <CardFooter>
                  <Badge variant="outline" className="text-xs">
                    Step {index + 1}
                  </Badge>
                </CardFooter>
              </Card>
            )
          })}
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
