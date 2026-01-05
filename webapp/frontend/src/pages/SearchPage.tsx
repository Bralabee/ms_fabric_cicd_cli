import { useState, useEffect } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { searchContent, fetchCategories, type SearchResult } from '@/lib/api'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { 
  Search, 
  FileText, 
  Code, 
  BookOpen,
  ChevronRight,
  Filter,
  X
} from 'lucide-react'
import { cn } from '@/lib/utils'

const matchTypeIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  title: BookOpen,
  description: FileText,
  content: FileText,
  code: Code,
}

export default function SearchPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialQuery = searchParams.get('q') || ''
  const initialCategory = searchParams.get('category') || ''
  
  const [query, setQuery] = useState(initialQuery)
  const [selectedCategory, setSelectedCategory] = useState(initialCategory)
  const [debouncedQuery, setDebouncedQuery] = useState(initialQuery)

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
      // Update URL params
      const params = new URLSearchParams()
      if (query) params.set('q', query)
      if (selectedCategory) params.set('category', selectedCategory)
      setSearchParams(params, { replace: true })
    }, 300)
    return () => clearTimeout(timer)
  }, [query, selectedCategory, setSearchParams])

  const { data: categories } = useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
  })

  const { data: results, isLoading, isFetching } = useQuery({
    queryKey: ['search', debouncedQuery, selectedCategory],
    queryFn: () => searchContent(debouncedQuery, selectedCategory || undefined),
    enabled: debouncedQuery.length >= 2,
  })

  const handleCategoryToggle = (categoryId: string) => {
    setSelectedCategory(prev => prev === categoryId ? '' : categoryId)
  }

  const clearFilters = () => {
    setSelectedCategory('')
    setQuery('')
  }

  return (
    <div className="container py-8 md:py-12">
      {/* Search Header */}
      <div className="max-w-3xl mx-auto mb-8">
        <h1 className="text-3xl font-bold mb-4">Search Guides</h1>
        <p className="text-muted-foreground mb-6">
          Find specific topics, commands, or troubleshooting steps across all scenarios.
        </p>

        {/* Search Input */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
          <Input
            type="search"
            placeholder="Search for topics, commands, blueprints..."
            className="pl-10 h-12 text-lg"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          {(query || selectedCategory) && (
            <Button
              variant="ghost"
              size="sm"
              className="absolute right-2 top-1/2 -translate-y-1/2"
              onClick={clearFilters}
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>

        {/* Category Filters */}
        <div className="flex flex-wrap items-center gap-2 mt-4">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground mr-2">Filter by:</span>
          {categories?.map((category) => (
            <Badge
              key={category.id}
              variant={selectedCategory === category.id ? 'default' : 'outline'}
              className="cursor-pointer"
              onClick={() => handleCategoryToggle(category.id)}
            >
              {category.name}
            </Badge>
          ))}
        </div>
      </div>

      {/* Results */}
      <div className="max-w-3xl mx-auto">
        {/* Loading State */}
        {isFetching && (
          <div className="text-center py-8 text-muted-foreground">
            Searching...
          </div>
        )}

        {/* Empty State - No Query */}
        {!debouncedQuery && !isFetching && (
          <div className="text-center py-12">
            <Search className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">Start searching</h2>
            <p className="text-muted-foreground">
              Type at least 2 characters to search across all guides.
            </p>
          </div>
        )}

        {/* Empty State - No Results */}
        {debouncedQuery && !isFetching && results?.length === 0 && (
          <div className="text-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-xl font-semibold mb-2">No results found</h2>
            <p className="text-muted-foreground mb-4">
              Try different keywords or remove filters.
            </p>
            <Button variant="outline" onClick={clearFilters}>
              Clear filters
            </Button>
          </div>
        )}

        {/* Results List */}
        {results && results.length > 0 && (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground mb-4">
              Found {results.length} result{results.length !== 1 ? 's' : ''} for "{debouncedQuery}"
            </p>
            
            {results.map((result, index) => {
              const MatchIcon = matchTypeIcons[result.match_type] || FileText
              
              return (
                <Link 
                  key={`${result.scenario_id}-${result.step_id}-${index}`}
                  to={`/scenario/${result.scenario_id}`}
                >
                  <Card className="hover:shadow-md transition-all hover:border-primary/50 cursor-pointer group">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          {/* Title */}
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-semibold group-hover:text-primary transition-colors">
                              {result.scenario_title}
                            </h3>
                            <Badge variant="outline" className="text-xs">
                              <MatchIcon className="h-3 w-3 mr-1" />
                              {result.match_type}
                            </Badge>
                          </div>

                          {/* Step Title (if applicable) */}
                          {result.step_title && (
                            <p className="text-sm text-primary/80 mb-2">
                              → {result.step_title}
                            </p>
                          )}

                          {/* Snippet */}
                          <p className="text-sm text-muted-foreground line-clamp-2">
                            {result.snippet}
                          </p>

                          {/* Relevance Score */}
                          <div className="flex items-center gap-2 mt-2">
                            <div className="h-1.5 w-24 bg-muted rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-primary rounded-full"
                                style={{ width: `${result.relevance_score * 100}%` }}
                              />
                            </div>
                            <span className="text-xs text-muted-foreground">
                              {Math.round(result.relevance_score * 100)}% match
                            </span>
                          </div>
                        </div>

                        <ChevronRight className="h-5 w-5 text-muted-foreground group-hover:text-primary flex-shrink-0" />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              )
            })}
          </div>
        )}

        {/* Quick Links */}
        {!debouncedQuery && (
          <div className="mt-12">
            <h2 className="text-xl font-semibold mb-4">Popular Topics</h2>
            <div className="grid gap-2 sm:grid-cols-2">
              {[
                'conda environment',
                'service principal',
                'blueprint templates',
                'docker deployment',
                'git integration',
                'azure devops',
                'workspace creation',
                'troubleshooting',
              ].map((topic) => (
                <Button
                  key={topic}
                  variant="outline"
                  className="justify-start"
                  onClick={() => setQuery(topic)}
                >
                  <Search className="h-4 w-4 mr-2" />
                  {topic}
                </Button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
