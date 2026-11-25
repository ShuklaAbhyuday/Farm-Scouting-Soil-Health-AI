import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { FieldProvider } from './context/FieldContext';
import Layout from './components/Layout/Layout';
import Workspace from './pages/Workspace';

const App: React.FC = () => {
  return (
    <FieldProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Workspace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </FieldProvider>
  );
};

export default App;
