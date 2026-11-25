import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { FieldProvider } from './context/FieldContext';
import Layout from './components/Layout/Layout';
import Dashboard from './pages/Dashboard';
import FarmList from './pages/FarmList';
import FarmCreate from './pages/FarmCreate';
import FieldMap from './pages/FieldMap';
import HotspotDetail from './pages/HotspotDetail';
import SoilSamples from './pages/SoilSamples';
import CropRecommendation from './pages/CropRecommendation';
import Recommendations from './pages/Recommendations';
import History from './pages/History';
import Reports from './pages/Reports';

const App: React.FC = () => {
  return (
    <FieldProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="farms" element={<FarmList />} />
            <Route path="farms/new" element={<FarmCreate />} />
            <Route path="map" element={<FieldMap />} />
            <Route path="hotspots" element={<HotspotDetail />} />
            <Route path="hotspots/:id" element={<HotspotDetail />} />
            <Route path="soil" element={<SoilSamples />} />
            <Route path="crop-recommendation" element={<CropRecommendation />} />
            <Route path="recommendations" element={<Recommendations />} />
            <Route path="history" element={<History />} />
            <Route path="reports" element={<Reports />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </FieldProvider>
  );
};

export default App;
