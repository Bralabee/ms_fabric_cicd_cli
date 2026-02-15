import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import ScenarioPage from './pages/ScenarioPage'
import SearchPage from './pages/SearchPage'
import ProcessFlowPage from './pages/ProcessFlowPage'
import ArchitecturePage from './pages/ArchitecturePage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="scenario/:scenarioId" element={<ScenarioPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="workflows" element={<ProcessFlowPage />} />
        <Route path="architecture" element={<ArchitecturePage />} />
      </Route>
    </Routes>
  )
}

export default App
