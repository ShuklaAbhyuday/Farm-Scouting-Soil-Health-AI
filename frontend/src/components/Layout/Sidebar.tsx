import React from 'react';
import { NavLink } from 'react-router-dom';

const Sidebar: React.FC = () => {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>🌾 FarmScout AI</h2>
        <div className="selector">
          <select aria-label="Select Farm">
            <option>Demo Farm 1</option>
          </select>
        </div>
      </div>
      <nav className="sidebar-nav">
        <NavLink to="/" className={({ isActive }) => (isActive ? 'active' : '')}>
          📊 Dashboard
        </NavLink>
        <NavLink to="/map" className={({ isActive }) => (isActive ? 'active' : '')}>
          🗺️ Farm Map
        </NavLink>
        <NavLink to="/hotspots" className={({ isActive }) => (isActive ? 'active' : '')}>
          🔥 Hotspots
        </NavLink>
        <NavLink to="/soil" className={({ isActive }) => (isActive ? 'active' : '')}>
          🧪 Soil Data
        </NavLink>
        <NavLink to="/recommendations" className={({ isActive }) => (isActive ? 'active' : '')}>
          💡 Recommendations
        </NavLink>
        <NavLink to="/history" className={({ isActive }) => (isActive ? 'active' : '')}>
          📈 History
        </NavLink>
        <NavLink to="/reports" className={({ isActive }) => (isActive ? 'active' : '')}>
          📄 Reports
        </NavLink>
      </nav>
      <div className="sidebar-footer">
        <span className="badge badge-mild">Demo Mode</span>
      </div>
    </aside>
  );
};

export default Sidebar;
