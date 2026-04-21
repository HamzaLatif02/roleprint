import { Routes, Route, Navigate } from 'react-router-dom'
import { AppProvider } from './context/AppContext'
import { Layout } from './components/Layout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { lazy, Suspense } from 'react'
import { SkeletonChart } from './components/Skeleton'

const Overview = lazy(() => import('./pages/Overview'))
const Trends = lazy(() => import('./pages/Trends'))
const Comparison = lazy(() => import('./pages/Comparison'))
const Sentiment = lazy(() => import('./pages/Sentiment'))
const SkillGap = lazy(() => import('./pages/SkillGap'))
const Postings = lazy(() => import('./pages/Postings'))

function PageFallback() {
  return (
    <div className="p-7 space-y-4">
      <div className="skeleton h-8 w-48 rounded" />
      <div className="grid grid-cols-4 gap-3">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="skeleton h-24 rounded-xl" />
        ))}
      </div>
      <SkeletonChart height={280} />
    </div>
  )
}

export default function App() {
  return (
    <AppProvider>
      <ErrorBoundary>
        <Layout>
          <Suspense fallback={<PageFallback />}>
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/trends" element={<Trends />} />
              <Route path="/compare" element={<Comparison />} />
              <Route path="/sentiment" element={<Sentiment />} />
              <Route path="/postings" element={<Postings />} />
              <Route path="/skill-gap" element={<SkillGap />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </Layout>
      </ErrorBoundary>
    </AppProvider>
  )
}
