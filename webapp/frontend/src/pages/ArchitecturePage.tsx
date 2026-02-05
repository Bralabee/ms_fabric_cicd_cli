import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
    ArrowRight,
    Terminal,
    GitBranch,
    Server,
    FileCode,
    Shield,
    Rocket,
    ChevronLeft,
    Layers,
    Link2,
    Database,
    Cloud,
    CheckCircle2,
    XCircle,
    Settings,
    RefreshCw,
    GitMerge,
    Workflow as WorkflowIcon
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ============================================================================
// TYPES
// ============================================================================

interface FlowStep {
    id: string
    label: string
    command?: string
    icon: React.ComponentType<{ className?: string }>
    color: string
    description: string
    output?: string
}

interface ComparisonRow {
    operation: string
    cliNative: 'supported' | 'limited' | 'none'
    restApi: 'supported' | 'limited' | 'none'
    notes?: string
}

// ============================================================================
// DATA
// ============================================================================

const onboardingFlowSteps: FlowStep[] = [
    {
        id: 'config-gen',
        label: 'Config Generation',
        command: 'python scripts/dev/onboard.py --org "Org" --project "Project"',
        icon: FileCode,
        color: 'bg-purple-500',
        description: 'Generates a YAML configuration file from a blueprint template (e.g., medallion.yaml). Variables are placeholders resolved at runtime.',
        output: '✓ Created: config/projects/org/project.yaml'
    },
    {
        id: 'git-branch',
        label: 'Git Branch Creation',
        command: 'git checkout -b feature/data-product-name',
        icon: GitBranch,
        color: 'bg-pink-500',
        description: 'Creates a feature branch locally and pushes it to the remote origin. Fabric requires the branch to exist on the remote to complete Git connection.',
        output: "Switched to branch 'feature/data-product-name'\n→ git push -u origin feature/data-product-name"
    },
    {
        id: 'workspace-provision',
        label: 'Workspace Provisioning',
        command: 'python -m usf_fabric_cli.cli deploy --force-branch-workspace',
        icon: Server,
        color: 'bg-blue-500',
        description: 'Creates a new Fabric Workspace named after the branch (Force-Branch-Workspace pattern). Deploys Lakehouses, Notebooks, and other items from the YAML config.',
        output: '✓ Workspace "feature_data_product_name" created\n✓ 5 items deployed'
    },
    {
        id: 'git-connect',
        label: 'Git Connection (REST API)',
        command: 'FabricGitAPI.connect_workspace_to_git(workspace_id, branch)',
        icon: Link2,
        color: 'bg-green-500',
        description: 'Uses the Fabric REST API (not native CLI) to connect the newly created workspace to the remote GitHub branch. Creates a "GitHub Connection" object using the GITHUB_TOKEN.',
        output: '✓ Workspace connected to origin/feature/data-product-name'
    },
    {
        id: 'initial-sync',
        label: 'Initial Sync',
        command: 'FabricGitAPI.update_from_git(workspace_id)',
        icon: RefreshCw,
        color: 'bg-cyan-500',
        description: 'Performs an initial "Update from Git" to pull any existing item definitions from the repository into the workspace.',
        output: '✓ Workspace synchronized with Git'
    }
]

const githubGapComparison: ComparisonRow[] = [
    { operation: 'Connect to Azure DevOps', cliNative: 'supported', restApi: 'supported', notes: 'Native CLI optimized for ADO' },
    { operation: 'Connect to GitHub', cliNative: 'limited', restApi: 'supported', notes: 'CLI lacks explicit GitHub commands' },
    { operation: 'Configure Credentials', cliNative: 'limited', restApi: 'supported', notes: 'REST uses /connections endpoint' },
    { operation: 'Initialize Git Connection', cliNative: 'supported', restApi: 'supported', notes: 'fab git init vs. /git/initializeConnection' },
    { operation: 'Sync (Pull from Git)', cliNative: 'supported', restApi: 'supported', notes: 'fab git sync vs. /git/updateFromGit' },
    { operation: 'Service Principal Auth', cliNative: 'supported', restApi: 'supported', notes: 'ADO-optimized for SPN' },
    { operation: 'PAT-based Auth (GitHub)', cliNative: 'none', restApi: 'supported', notes: 'REST API required for GitHub PAT' },
]

// ============================================================================
// COMPONENTS
// ============================================================================

function StatusIcon({ status }: { status: 'supported' | 'limited' | 'none' }) {
    if (status === 'supported') {
        return <CheckCircle2 className="h-5 w-5 text-green-500" />
    }
    if (status === 'limited') {
        return <Settings className="h-5 w-5 text-amber-500" />
    }
    return <XCircle className="h-5 w-5 text-red-400" />
}

function OnboardingFlowDiagram() {
    const [activeStep, setActiveStep] = useState<string | null>(null)

    return (
        <Card className="overflow-hidden">
            <CardHeader className="bg-muted/30">
                <CardTitle className="text-xl flex items-center gap-2">
                    <Rocket className="h-5 w-5 text-primary" />
                    Onboarding Workflow: <code className="text-base bg-muted px-2 py-1 rounded">make onboard</code>
                </CardTitle>
                <CardDescription>
                    The unified onboarding orchestrator reduces "Time-to-Code" by automating config generation, Git branching, and Fabric provisioning in a single command.
                </CardDescription>
            </CardHeader>
            <CardContent className="p-6">
                {/* Desktop: Horizontal Flow */}
                <div className="hidden lg:block">
                    <div className="flex items-start justify-between overflow-x-auto pb-4">
                        {onboardingFlowSteps.map((step, index) => {
                            const Icon = step.icon
                            const isActive = activeStep === step.id
                            return (
                                <div key={step.id} className="flex items-start flex-shrink-0 relative">
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
                                                    <div className="text-xs text-muted-foreground font-mono bg-black/5 dark:bg-white/5 rounded p-2 whitespace-pre-line">
                                                        {step.output}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    {/* Arrow */}
                                    {index < onboardingFlowSteps.length - 1 && (
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
                    {onboardingFlowSteps.map((step, index) => {
                        const Icon = step.icon
                        return (
                            <div key={step.id} className="relative">
                                <div className="flex items-start gap-4">
                                    <div className="flex flex-col items-center">
                                        <div className={cn(
                                            "h-12 w-12 rounded-full flex items-center justify-center text-white shadow-md",
                                            step.color
                                        )}>
                                            <Icon className="h-5 w-5" />
                                        </div>
                                        {index < onboardingFlowSteps.length - 1 && (
                                            <div className="w-0.5 h-8 bg-border mt-2" />
                                        )}
                                    </div>

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
            </CardContent>
        </Card>
    )
}

function GitHubGapSection() {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-xl flex items-center gap-2">
                    <GitBranch className="h-5 w-5 text-pink-500" />
                    The "GitHub Gap"
                </CardTitle>
                <CardDescription>
                    The native Fabric CLI is optimized for Azure DevOps. This project bridges the gap for GitHub users by calling the Fabric REST API directly.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                        <thead>
                            <tr className="border-b">
                                <th className="text-left py-3 px-4 font-semibold">Operation</th>
                                <th className="text-center py-3 px-4 font-semibold">Fabric CLI (Native)</th>
                                <th className="text-center py-3 px-4 font-semibold">Fabric REST API</th>
                                <th className="text-left py-3 px-4 font-semibold text-muted-foreground">Notes</th>
                            </tr>
                        </thead>
                        <tbody>
                            {githubGapComparison.map((row, index) => (
                                <tr key={index} className="border-b last:border-b-0 hover:bg-muted/30 transition-colors">
                                    <td className="py-3 px-4 font-medium">{row.operation}</td>
                                    <td className="py-3 px-4 text-center">
                                        <div className="flex justify-center">
                                            <StatusIcon status={row.cliNative} />
                                        </div>
                                    </td>
                                    <td className="py-3 px-4 text-center">
                                        <div className="flex justify-center">
                                            <StatusIcon status={row.restApi} />
                                        </div>
                                    </td>
                                    <td className="py-3 px-4 text-muted-foreground text-xs">{row.notes}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-950/30 rounded-lg border border-blue-200 dark:border-blue-800">
                    <h4 className="font-semibold text-blue-700 dark:text-blue-300 mb-2">How This Project Solves It</h4>
                    <p className="text-sm text-blue-600 dark:text-blue-400">
                        The <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">FabricGitAPI</code> class in <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">fabric_git_api.py</code> acts as a middleware layer. It uses your <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">GITHUB_TOKEN</code> to create a "Cloud Connection" object in Fabric via the REST API, then calls <code className="bg-blue-100 dark:bg-blue-900 px-1 rounded">/git/connect</code> to link the workspace to your GitHub branch.
                    </p>
                </div>
            </CardContent>
        </Card>
    )
}

function DeploymentPipelinesSection() {
    const [activeTab, setActiveTab] = useState<'git-centric' | 'alm-pipelines'>('git-centric')

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-xl flex items-center gap-2">
                    <WorkflowIcon className="h-5 w-5 text-fabric-primary" />
                    Git-Centric CI/CD vs. Fabric Deployment Pipelines
                </CardTitle>
                <CardDescription>
                    Microsoft Fabric offers two lifecycle management approaches. This project implements the "Git-Centric" model.
                </CardDescription>
            </CardHeader>
            <CardContent>
                {/* Tab Buttons */}
                <div className="flex gap-2 mb-6">
                    <Button
                        variant={activeTab === 'git-centric' ? 'default' : 'outline'}
                        onClick={() => setActiveTab('git-centric')}
                        className="flex-1"
                    >
                        <GitMerge className="h-4 w-4 mr-2" />
                        Git-Centric (This Project)
                    </Button>
                    <Button
                        variant={activeTab === 'alm-pipelines' ? 'default' : 'outline'}
                        onClick={() => setActiveTab('alm-pipelines')}
                        className="flex-1"
                    >
                        <Cloud className="h-4 w-4 mr-2" />
                        Fabric Deployment Pipelines
                    </Button>
                </div>

                {/* Git-Centric Tab */}
                {activeTab === 'git-centric' && (
                    <div className="space-y-4">
                        <div className="grid md:grid-cols-3 gap-4">
                            <div className="p-4 bg-muted/30 rounded-lg border">
                                <div className="flex items-center gap-2 mb-2">
                                    <GitBranch className="h-5 w-5 text-pink-500" />
                                    <span className="font-semibold">Feature Branch</span>
                                </div>
                                <p className="text-sm text-muted-foreground">
                                    Each feature branch gets an isolated Fabric workspace. Developers work independently without collisions.
                                </p>
                            </div>
                            <div className="p-4 bg-muted/30 rounded-lg border">
                                <div className="flex items-center gap-2 mb-2">
                                    <GitMerge className="h-5 w-5 text-green-500" />
                                    <span className="font-semibold">Merge to Main</span>
                                </div>
                                <p className="text-sm text-muted-foreground">
                                    When ready, the feature branch is merged to <code>main</code>. This acts as the "promotion" trigger.
                                </p>
                            </div>
                            <div className="p-4 bg-muted/30 rounded-lg border">
                                <div className="flex items-center gap-2 mb-2">
                                    <Rocket className="h-5 w-5 text-blue-500" />
                                    <span className="font-semibold">CI/CD Automation</span>
                                </div>
                                <p className="text-sm text-muted-foreground">
                                    GitHub Actions (or similar) triggers deployment to a "Production Workspace" based on branch rules.
                                </p>
                            </div>
                        </div>

                        <div className="p-4 bg-green-50 dark:bg-green-950/30 rounded-lg border border-green-200 dark:border-green-800">
                            <h4 className="font-semibold text-green-700 dark:text-green-300 mb-2 flex items-center gap-2">
                                <CheckCircle2 className="h-4 w-4" />
                                Best For
                            </h4>
                            <ul className="text-sm text-green-600 dark:text-green-400 space-y-1">
                                <li>• Teams preferring "Infrastructure as Code"</li>
                                <li>• GitHub-centric organizations</li>
                                <li>• Developers who want isolated testing environments per feature</li>
                                <li>• Projects requiring automated rollback via Git history</li>
                            </ul>
                        </div>
                    </div>
                )}

                {/* ALM Pipelines Tab */}
                {activeTab === 'alm-pipelines' && (
                    <div className="space-y-4">
                        <div className="grid md:grid-cols-3 gap-4">
                            <div className="p-4 bg-muted/30 rounded-lg border">
                                <div className="flex items-center gap-2 mb-2">
                                    <Database className="h-5 w-5 text-amber-500" />
                                    <span className="font-semibold">Dev Workspace</span>
                                </div>
                                <p className="text-sm text-muted-foreground">
                                    A dedicated workspace for development. Content is edited directly in Fabric.
                                </p>
                            </div>
                            <div className="p-4 bg-muted/30 rounded-lg border">
                                <div className="flex items-center gap-2 mb-2">
                                    <Shield className="h-5 w-5 text-blue-500" />
                                    <span className="font-semibold">Test Workspace</span>
                                </div>
                                <p className="text-sm text-muted-foreground">
                                    Content is promoted from Dev to Test via the "Deploy" button in the Fabric UI pipeline.
                                </p>
                            </div>
                            <div className="p-4 bg-muted/30 rounded-lg border">
                                <div className="flex items-center gap-2 mb-2">
                                    <Cloud className="h-5 w-5 text-green-500" />
                                    <span className="font-semibold">Prod Workspace</span>
                                </div>
                                <p className="text-sm text-muted-foreground">
                                    Final production environment. Promoted from Test after validation.
                                </p>
                            </div>
                        </div>

                        <div className="p-4 bg-amber-50 dark:bg-amber-950/30 rounded-lg border border-amber-200 dark:border-amber-800">
                            <h4 className="font-semibold text-amber-700 dark:text-amber-300 mb-2 flex items-center gap-2">
                                <Settings className="h-4 w-4" />
                                Best For
                            </h4>
                            <ul className="text-sm text-amber-600 dark:text-amber-400 space-y-1">
                                <li>• Organizations using the Fabric UI primarily</li>
                                <li>• Teams with clear Dev/Test/Prod stage separation</li>
                                <li>• Projects where manual promotion approval is required</li>
                                <li>• Premium capacity workspaces (required for Deployment Pipelines)</li>
                            </ul>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}

function ComponentArchitectureSection() {
    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-xl flex items-center gap-2">
                    <Layers className="h-5 w-5 text-fabric-accent" />
                    Key Components
                </CardTitle>
                <CardDescription>
                    The orchestration layer that powers the onboarding automation.
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="grid md:grid-cols-2 gap-4">
                    <div className="p-4 border rounded-lg hover:border-primary/50 transition-colors">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="h-10 w-10 rounded-lg bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center">
                                <Terminal className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                            </div>
                            <div>
                                <h4 className="font-semibold">onboard.py</h4>
                                <p className="text-xs text-muted-foreground">scripts/dev/onboard.py</p>
                            </div>
                        </div>
                        <p className="text-sm text-muted-foreground">
                            The main orchestrator script. Coordinates config generation, git branching, and deployment in sequence.
                        </p>
                    </div>

                    <div className="p-4 border rounded-lg hover:border-primary/50 transition-colors">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="h-10 w-10 rounded-lg bg-green-100 dark:bg-green-900/50 flex items-center justify-center">
                                <Link2 className="h-5 w-5 text-green-600 dark:text-green-400" />
                            </div>
                            <div>
                                <h4 className="font-semibold">FabricGitAPI</h4>
                                <p className="text-xs text-muted-foreground">services/fabric_git_api.py</p>
                            </div>
                        </div>
                        <p className="text-sm text-muted-foreground">
                            REST API wrapper for Git operations. Bridges the "GitHub Gap" by handling PAT-based authentication and workspace connections.
                        </p>
                    </div>

                    <div className="p-4 border rounded-lg hover:border-primary/50 transition-colors">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="h-10 w-10 rounded-lg bg-pink-100 dark:bg-pink-900/50 flex items-center justify-center">
                                <GitBranch className="h-5 w-5 text-pink-600 dark:text-pink-400" />
                            </div>
                            <div>
                                <h4 className="font-semibold">GitFabricIntegration</h4>
                                <p className="text-xs text-muted-foreground">services/git_integration.py</p>
                            </div>
                        </div>
                        <p className="text-sm text-muted-foreground">
                            Local Git choreography. Manages branch creation, workspace-branch mapping, and remote push verification.
                        </p>
                    </div>

                    <div className="p-4 border rounded-lg hover:border-primary/50 transition-colors">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="h-10 w-10 rounded-lg bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center">
                                <Rocket className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                            </div>
                            <div>
                                <h4 className="font-semibold">FabricDeployer</h4>
                                <p className="text-xs text-muted-foreground">services/deployer.py</p>
                            </div>
                        </div>
                        <p className="text-sm text-muted-foreground">
                            Handles Fabric resource creation. Creates workspaces, lakehouses, notebooks, and manages atomic rollback on failure.
                        </p>
                    </div>
                </div>
            </CardContent>
        </Card>
    )
}

// ============================================================================
// MAIN PAGE
// ============================================================================

export default function ArchitecturePage() {
    return (
        <div className="container py-8 md:py-12">
            {/* Back Button */}
            <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6">
                <ChevronLeft className="h-4 w-4" />
                Back to Home
            </Link>

            {/* Header */}
            <div className="text-center mb-12">
                <Badge className="mb-4" variant="outline">Technical Deep Dive</Badge>
                <h1 className="text-4xl font-bold tracking-tight mb-4">
                    System Architecture
                </h1>
                <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
                    Understand how workspace creation, Git integration, and CI/CD coordination work together in the Fabric CLI CICD project.
                </p>
            </div>

            {/* Sections */}
            <div className="space-y-8 max-w-5xl mx-auto">
                {/* Section 1: Onboarding Flow */}
                <OnboardingFlowDiagram />

                {/* Section 2: GitHub Gap */}
                <GitHubGapSection />

                {/* Section 3: Deployment Pipelines Comparison */}
                <DeploymentPipelinesSection />

                {/* Section 4: Component Architecture */}
                <ComponentArchitectureSection />
            </div>

            {/* CTA */}
            <div className="mt-12 text-center">
                <Link to="/workflows">
                    <Button size="lg">
                        <WorkflowIcon className="h-4 w-4 mr-2" />
                        View Deployment Workflows
                    </Button>
                </Link>
            </div>
        </div>
    )
}
