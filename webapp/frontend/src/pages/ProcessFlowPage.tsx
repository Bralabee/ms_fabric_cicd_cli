import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  ArrowRight,
  Terminal,
  Container,
  GitBranch,
  Settings,
  Server,
  FileCode,
  FolderOpen,
  Shield,
  Eye,
  Trash2,
  Rocket,
  ChevronRight,
  ChevronLeft,
  Workflow as WorkflowIcon
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Flow step type
interface FlowStep {
  id: string
  label: string
  command?: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  description: string
  output?: string
}

// Workflow definition
interface WorkflowDefinition {
  id: string
  title: string
  description: string
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  estimatedTime: string
  relatedScenario: string
  steps: FlowStep[]
}

// Local Python Deployment workflow
const localDeploymentFlow: WorkflowDefinition = {
  id: 'local-deployment',
  title: 'Local Python Deployment',
  description: 'Deploy Fabric workspaces directly from your machine using conda environment and Make commands.',
  difficulty: 'beginner',
  estimatedTime: '10-15 min',
  relatedScenario: 'local-deployment',
  steps: [
    {
      id: 'activate',
      label: 'Activate Environment',
      command: 'conda activate fabric-cli-cicd',
      icon: Terminal,
      color: 'bg-blue-500',
      description: 'Activate the conda environment with all dependencies installed.',
      output: '(fabric-cli-cicd) $'
    },
    {
      id: 'generate',
      label: 'Generate Config',
      command: 'python scripts/generate_project.py "Org" "Project" --template basic_etl',
      icon: FileCode,
      color: 'bg-purple-500',
      description: 'Create a project configuration YAML from a template blueprint.',
      output: '✓ Created: config/projects/org/project.yaml'
    },
    {
      id: 'validate',
      label: 'Validate Config',
      command: 'make validate config=config/projects/org/project.yaml',
      icon: Shield,
      color: 'bg-amber-500',
      description: 'Validate YAML syntax, required fields, and environment variable references.',
      output: '✓ Configuration valid'
    },
    {
      id: 'deploy',
      label: 'Deploy Workspace',
      command: 'make deploy config=config/projects/org/project.yaml env=dev',
      icon: Rocket,
      color: 'bg-green-500',
      description: 'Create workspace, lakehouses, notebooks, and other artifacts in Microsoft Fabric.',
      output: '✓ Workspace created with 5 items'
    },
    {
      id: 'verify',
      label: 'Verify Deployment',
      command: 'python scripts/utilities/list_workspace_items.py --workspace "org-project"',
      icon: Eye,
      color: 'bg-cyan-500',
      description: 'List all items in the workspace to confirm successful deployment.',
      output: 'Lakehouse: raw_data_lakehouse\nNotebook: data_transform...'
    },
    {
      id: 'cleanup',
      label: 'Cleanup (Optional)',
      command: 'make destroy config=config/projects/org/project.yaml env=dev',
      icon: Trash2,
      color: 'bg-red-500',
      description: 'Remove the workspace and all items when no longer needed.',
      output: '✓ Workspace destroyed successfully'
    }
  ]
}

// Docker Deployment workflow
const dockerDeploymentFlow: WorkflowDefinition = {
  id: 'docker-deployment',
  title: 'Docker Containerized Deployment',
  description: 'Deploy using Docker containers for consistent, isolated, and CI/CD-ready deployments.',
  difficulty: 'intermediate',
  estimatedTime: '15-20 min',
  relatedScenario: 'docker-deployment',
  steps: [
    {
      id: 'build',
      label: 'Build Docker Image',
      command: 'make docker-build',
      icon: Container,
      color: 'bg-blue-500',
      description: 'Build the Docker image with Fabric CLI and all dependencies.',
      output: 'Successfully built fabric-cli-cicd:latest'
    },
    {
      id: 'diagnose',
      label: 'Run Diagnostics',
      command: 'make docker-diagnose ENVFILE=.env',
      icon: Settings,
      color: 'bg-amber-500',
      description: 'Verify CLI version, credentials, and capacity access inside container.',
      output: '✓ Fabric CLI: v1.3.1\n✓ Credentials: Valid\n✓ Capacity: F2 Available'
    },
    {
      id: 'generate',
      label: 'Generate Config',
      command: 'make docker-generate org="Org" project="Project" template="basic_etl"',
      icon: FileCode,
      color: 'bg-purple-500',
      description: 'Generate project configuration inside the container.',
      output: '✓ Created: config/projects/org/project.yaml'
    },
    {
      id: 'validate',
      label: 'Validate Config',
      command: 'make docker-validate config=config/projects/org/project.yaml ENVFILE=.env',
      icon: Shield,
      color: 'bg-amber-600',
      description: 'Validate configuration using container environment.',
      output: '✓ Configuration valid'
    },
    {
      id: 'deploy',
      label: 'Deploy Workspace',
      command: 'make docker-deploy config=config/projects/org/project.yaml env=dev ENVFILE=.env',
      icon: Rocket,
      color: 'bg-green-500',
      description: 'Deploy workspace from within the container.',
      output: '✓ Workspace created successfully'
    },
    {
      id: 'shell',
      label: 'Debug Shell (Optional)',
      command: 'make docker-shell ENVFILE=.env',
      icon: Terminal,
      color: 'bg-gray-600',
      description: 'Open interactive shell inside container for debugging.',
      output: 'root@container:/app# fabric-cicd --version'
    }
  ]
}

// Feature Branch workflow
const featureBranchFlow: WorkflowDefinition = {
  id: 'feature-branch',
  title: 'Feature Branch Workflow',
  description: 'Create isolated workspaces for each feature branch for safe development and testing.',
  difficulty: 'intermediate',
  estimatedTime: '10-15 min',
  relatedScenario: 'feature-branch-workflows',
  steps: [
    {
      id: 'branch',
      label: 'Create Feature Branch',
      command: 'git checkout -b feature/new-pipeline',
      icon: GitBranch,
      color: 'bg-pink-500',
      description: 'Create a new Git branch for your feature development.',
      output: "Switched to branch 'feature/new-pipeline'"
    },
    {
      id: 'modify',
      label: 'Modify Configuration',
      command: 'Edit config/projects/org/project.yaml',
      icon: FileCode,
      color: 'bg-purple-500',
      description: 'Add or modify artifacts in your configuration file.',
      output: '+ Added: new_pipeline.Pipeline'
    },
    {
      id: 'deploy-branch',
      label: 'Deploy Branch Workspace',
      command: 'make docker-feature-deploy config=... env=dev branch=feature/new-pipeline',
      icon: Rocket,
      color: 'bg-green-500',
      description: 'Deploy to an isolated workspace named after your branch.',
      output: '✓ Created: org-project-feature-new-pipeline'
    },
    {
      id: 'test',
      label: 'Test Changes',
      command: 'Navigate to workspace in Fabric portal',
      icon: Eye,
      color: 'bg-cyan-500',
      description: 'Test your changes in the isolated feature workspace.',
      output: 'Workspace: org-project-feature-new-pipeline'
    },
    {
      id: 'merge',
      label: 'Merge to Main',
      command: 'git checkout main && git merge feature/new-pipeline',
      icon: GitBranch,
      color: 'bg-blue-500',
      description: 'After testing, merge your feature branch to main.',
      output: "Merge made by the 'recursive' strategy"
    },
    {
      id: 'cleanup-branch',
      label: 'Cleanup Branch Workspace',
      command: 'make docker-destroy config=... env=dev --force',
      icon: Trash2,
      color: 'bg-red-500',
      description: 'Delete the feature branch workspace after merge.',
      output: '✓ Workspace destroyed successfully'
    }
  ]
}

// Advanced template workflow
const advancedTemplateFlow: WorkflowDefinition = {
  id: 'advanced-template',
  title: 'Advanced Analytics Deployment',
  description: 'Deploy a complex workspace with multiple lakehouses, warehouses, and ML notebooks.',
  difficulty: 'advanced',
  estimatedTime: '20-30 min',
  relatedScenario: 'project-generation',
  steps: [
    {
      id: 'choose-template',
      label: 'Choose Advanced Template',
      command: 'python scripts/generate_project.py --list',
      icon: FolderOpen,
      color: 'bg-indigo-500',
      description: 'List available templates and select advanced_analytics.',
      output: 'Available: basic_etl, advanced_analytics, realtime_streaming...'
    },
    {
      id: 'generate-advanced',
      label: 'Generate Config',
      command: 'python scripts/generate_project.py "Corp" "ML Pipeline" --template advanced_analytics',
      icon: FileCode,
      color: 'bg-purple-500',
      description: 'Generate configuration with 4 lakehouses, 2 warehouses, 6+ notebooks.',
      output: '✓ Created: config/projects/corp/ml_pipeline.yaml'
    },
    {
      id: 'review',
      label: 'Review Configuration',
      command: 'cat config/projects/corp/ml_pipeline.yaml',
      icon: Eye,
      color: 'bg-cyan-500',
      description: 'Review the generated resources before deployment.',
      output: 'lakehouses: 4\nwarehouses: 2\nnotebooks: 6\nsemanticmodels: 2'
    },
    {
      id: 'validate-advanced',
      label: 'Validate Complex Config',
      command: 'make validate config=config/projects/corp/ml_pipeline.yaml',
      icon: Shield,
      color: 'bg-amber-500',
      description: 'Validate all cross-references and dependencies.',
      output: '✓ Configuration valid (15 resources)'
    },
    {
      id: 'deploy-advanced',
      label: 'Deploy All Resources',
      command: 'make deploy config=config/projects/corp/ml_pipeline.yaml env=dev',
      icon: Rocket,
      color: 'bg-green-500',
      description: 'Deploy all 15+ artifacts to Microsoft Fabric.',
      output: '✓ Workspace created with 15 items (452 seconds)'
    },
    {
      id: 'verify-advanced',
      label: 'Verify All Items',
      command: 'fab ls "corp-ml-pipeline.Workspace"',
      icon: Server,
      color: 'bg-teal-500',
      description: 'Confirm all lakehouses, warehouses, notebooks created.',
      output: 'customer_360.Lakehouse\nanalytics_warehouse.Warehouse\nchurn_prediction.Notebook...'
    }
  ]
}

const workflows: WorkflowDefinition[] = [
  localDeploymentFlow,
  dockerDeploymentFlow,
  featureBranchFlow,
  advancedTemplateFlow
]

const difficultyColors: Record<string, string> = {
  beginner: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-100',
  intermediate: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-100',
  advanced: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-100',
}

function FlowDiagram({ workflow }: { workflow: WorkflowDefinition }) {
  const [activeStep, setActiveStep] = useState<string | null>(null)

  return (
    <Card className="overflow-hidden">
      <CardHeader className="bg-muted/30">
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-xl flex items-center gap-2">
              <WorkflowIcon className="h-5 w-5 text-primary" />
              {workflow.title}
            </CardTitle>
            <CardDescription className="mt-1">{workflow.description}</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge className={difficultyColors[workflow.difficulty]}>
              {workflow.difficulty}
            </Badge>
            <Badge variant="outline">{workflow.estimatedTime}</Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-6">
        {/* Desktop: Horizontal Flow */}
        <div className="hidden lg:block">
          <div className="flex items-start justify-between overflow-x-auto pb-4">
            {workflow.steps.map((step, index) => {
              const Icon = step.icon
              const isActive = activeStep === step.id
              return (
                <div key={step.id} className="flex items-start flex-shrink-0">
                  <div
                    className="flex flex-col items-center cursor-pointer group"
                    onMouseEnter={() => setActiveStep(step.id)}
                    onMouseLeave={() => setActiveStep(null)}
                  >
                    {/* Step Circle */}
                    <div className={cn(
                      "h-16 w-16 rounded-full flex items-center justify-center text-white shadow-lg transition-all",
                      step.color,
                      isActive && "scale-110 ring-4 ring-offset-2 ring-primary/30"
                    )}>
                      <Icon className="h-7 w-7" />
                    </div>

                    {/* Step Number */}
                    <div className="mt-2 h-6 w-6 rounded-full bg-muted flex items-center justify-center text-xs font-semibold">
                      {index + 1}
                    </div>

                    {/* Step Label */}
                    <span className={cn(
                      "mt-1 text-sm font-medium text-center max-w-[100px] transition-colors",
                      isActive && "text-primary"
                    )}>
                      {step.label}
                    </span>

                    {/* Expanded Details on Hover */}
                    {isActive && (
                      <div className="absolute top-full mt-4 z-10 w-80 p-4 bg-popover border rounded-lg shadow-xl">
                        <p className="text-sm text-muted-foreground mb-3">{step.description}</p>
                        {step.command && (
                          <div className="bg-muted rounded p-2 mb-2">
                            <code className="text-xs font-mono break-all">{step.command}</code>
                          </div>
                        )}
                        {step.output && (
                          <div className="text-xs text-muted-foreground font-mono bg-black/5 dark:bg-white/5 rounded p-2">
                            {step.output}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Arrow */}
                  {index < workflow.steps.length - 1 && (
                    <div className="flex items-center h-16 mx-2 lg:mx-4">
                      <ArrowRight className="h-6 w-6 text-muted-foreground" />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* Mobile/Tablet: Vertical Flow */}
        <div className="lg:hidden space-y-4">
          {workflow.steps.map((step, index) => {
            const Icon = step.icon
            return (
              <div key={step.id} className="relative">
                <div className="flex items-start gap-4">
                  {/* Step Indicator */}
                  <div className="flex flex-col items-center">
                    <div className={cn(
                      "h-12 w-12 rounded-full flex items-center justify-center text-white shadow-md",
                      step.color
                    )}>
                      <Icon className="h-5 w-5" />
                    </div>
                    {index < workflow.steps.length - 1 && (
                      <div className="w-0.5 h-8 bg-border mt-2" />
                    )}
                  </div>

                  {/* Step Content */}
                  <div className="flex-1 pb-4">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold text-muted-foreground">Step {index + 1}</span>
                    </div>
                    <h4 className="font-medium">{step.label}</h4>
                    <p className="text-sm text-muted-foreground mt-1">{step.description}</p>
                    {step.command && (
                      <code className="block text-xs font-mono bg-muted p-2 rounded mt-2 break-all">
                        {step.command}
                      </code>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {/* Related Scenario Link */}
        <div className="mt-6 pt-4 border-t flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Learn more in the detailed guide
          </span>
          <Link to={`/scenario/${workflow.relatedScenario}`}>
            <Button variant="outline" size="sm">
              View Full Guide
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}

export default function ProcessFlowPage() {
  return (
    <div className="container py-8 md:py-12">
      {/* Back Button */}
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6">
        <ChevronLeft className="h-4 w-4" />
        Back to Home
      </Link>

      {/* Header */}
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight mb-4">
          Deployment Workflows
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto mb-6">
          Visual guides showing the end-to-end process for each deployment approach.
          Hover over steps to see commands and expected outputs.
        </p>

        {/* Quick Legend */}
        <div className="flex flex-wrap items-center justify-center gap-4 text-sm">
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-green-500" />
            <span className="text-muted-foreground">Beginner</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-amber-500" />
            <span className="text-muted-foreground">Intermediate</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-red-500" />
            <span className="text-muted-foreground">Advanced</span>
          </div>
        </div>
      </div>

      {/* Workflow Diagrams */}
      <div className="space-y-8 max-w-6xl mx-auto">
        {workflows.map((workflow) => (
          <FlowDiagram key={workflow.id} workflow={workflow} />
        ))}
      </div>

      {/* Summary Section */}
      <div className="mt-12 bg-muted/30 rounded-xl p-6 md:p-8 max-w-4xl mx-auto">
        <h2 className="text-xl font-semibold mb-4 text-center">Choose Your Approach</h2>
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <h3 className="font-medium mb-2 flex items-center gap-2">
              <Terminal className="h-4 w-4 text-blue-500" />
              Local Python
            </h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>✓ Quick setup for development</li>
              <li>✓ Direct access to all scripts</li>
              <li>✓ Best for single-developer workflows</li>
            </ul>
          </div>
          <div>
            <h3 className="font-medium mb-2 flex items-center gap-2">
              <Container className="h-4 w-4 text-orange-500" />
              Docker Container
            </h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>✓ Consistent environment everywhere</li>
              <li>✓ CI/CD pipeline ready</li>
              <li>✓ Multi-tenant with ENVFILE switching</li>
            </ul>
          </div>
          <div>
            <h3 className="font-medium mb-2 flex items-center gap-2">
              <GitBranch className="h-4 w-4 text-pink-500" />
              Feature Branches
            </h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>✓ Isolated testing per feature</li>
              <li>✓ No impact on main workspace</li>
              <li>✓ Easy cleanup after merge</li>
            </ul>
          </div>
          <div>
            <h3 className="font-medium mb-2 flex items-center gap-2">
              <Server className="h-4 w-4 text-teal-500" />
              Advanced Templates
            </h3>
            <ul className="text-sm text-muted-foreground space-y-1">
              <li>✓ Pre-configured complex architectures</li>
              <li>✓ Data mesh, ML pipeline patterns</li>
              <li>✓ Production-ready blueprints</li>
            </ul>
          </div>
        </div>
      </div>

      {/* CTA */}
      <div className="mt-8 text-center">
        <Link to="/scenario/getting-started">
          <Button size="lg">
            <Rocket className="h-4 w-4 mr-2" />
            Start with Getting Started Guide
          </Button>
        </Link>
      </div>
    </div>
  )
}
