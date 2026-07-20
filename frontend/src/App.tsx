import { Suspense, lazy } from 'react';
import { Routes, Route } from 'react-router-dom';
import DashboardLayout from './components/layout/DashboardLayout';
import { LoadingScreen } from './components/common/LoadingScreen';

// Lazy loaded Pages
const Dashboard = lazy(() => import('./pages/Dashboard'));
const TrafficMap = lazy(() => import('./pages/TrafficMap'));
const Prediction = lazy(() => import('./pages/Prediction'));
const Federated = lazy(() => import('./pages/Federated'));
const Training = lazy(() => import('./pages/Training'));
const Analysis = lazy(() => import('./pages/Analysis'));
const Results = lazy(() => import('./pages/Results'));
const About = lazy(() => import('./pages/About'));
const NotFound = lazy(() => import('./pages/NotFound'));

function App() {
  return (
    <Suspense fallback={<LoadingScreen fullScreen message="Loading FedRouteAI Dashboard..." />}>
      <Routes>
      <Route path="/" element={<DashboardLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="map" element={<TrafficMap />} />
        <Route path="prediction" element={<Prediction />} />
        <Route path="federated" element={<Federated />} />
        <Route path="training" element={<Training />} />
        <Route path="analysis" element={<Analysis />} />
        <Route path="results" element={<Results />} />
        <Route path="about" element={<About />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      </Routes>
    </Suspense>
  );
}

export default App;
