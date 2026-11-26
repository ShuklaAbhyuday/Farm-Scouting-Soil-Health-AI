import React from 'react';
import { Outlet } from 'react-router-dom';

const Layout: React.FC = () => {
  return (
    <div className="app-shell">
      <div className="noise-overlay" aria-hidden="true" />
      <Outlet />
    </div>
  );
};

export default Layout;
