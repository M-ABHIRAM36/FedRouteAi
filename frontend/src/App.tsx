import { Routes, Route } from 'react-router-dom';
import DashboardLayout from './components/layout/DashboardLayout';

// Pages
import Dashboard from './pages/Dashboard';
import TrafficMap from './pages/TrafficMap';
import Prediction from './pages/Prediction';
import Federated from './pages/Federated';
import Training from './pages/Training';
import Analysis from './pages/Analysis';
import Results from './pages/Results';
import About from './pages/About';

function App() {
  return (
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
      </Route>
    </Routes>
  );
}

export default App;
