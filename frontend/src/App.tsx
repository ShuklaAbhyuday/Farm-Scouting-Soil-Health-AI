import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import FarmList from './pages/FarmList';
import FarmCreate from './pages/FarmCreate';
import FieldMap from './pages/FieldMap';
import HotspotDetail from './pages/HotspotDetail';
import SoilSamples from './pages/SoilSamples';
import Recommendations from './pages/Recommendations';
import History from './pages/History';
import Reports from './pages/Reports';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="farms" element={<FarmList />} />
          <Route path="farms/new" element={<FarmCreate />} />
          <Route path="map" element={<FieldMap />} />
          <Route path="hotspots" element={<Navigate to="/map" />} />
          <Route path="hotspots/:id" element={<HotspotDetail />} />
          <Route path="soil" element={<SoilSamples />} />
          <Route path="recommendations" element={<Recommendations />} />
          <Route path="history" element={<History />} />
          <Route path="reports" element={<Reports />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
