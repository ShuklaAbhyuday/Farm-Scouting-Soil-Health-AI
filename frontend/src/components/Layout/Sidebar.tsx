import React from 'react';
import { NavLink } from 'react-router-dom';
import { useFieldContext } from '../../context/FieldContext';

const Sidebar: React.FC = () => {
  const { farms, selectedFarmId, selectedFieldId, setSelectedFarmId, setSelectedFieldId } = useFieldContext();
  const currentFarm = farms.find((f) => f.id === selectedFarmId) || farms[0];
  const fields = currentFarm?.fields || [];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>🌾 FarmScout AI</h2>
        <div className="selector" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <select
            aria-label="Select Farm"
            value={selectedFarmId}
            onChange={(e) => setSelectedFarmId(Number(e.target.value))}
          >
            {farms.length === 0 ? (
              <option value={1}>Demo Farm</option>
            ) : (
              farms.map((farm) => (
                <option key={farm.id} value={farm.id}>
                  {farm.name}
                </option>
              ))
            )}
          </select>

          {fields.length > 0 && (
            <select
              aria-label="Select Field"
              value={selectedFieldId}
              onChange={(e) => setSelectedFieldId(Number(e.target.value))}
            >
              {fields.map((fld) => (
                <option key={fld.id} value={fld.id}>
                  {fld.name} ({fld.crop_type || 'Crop'})
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <nav className="sidebar-nav">
        <NavLink to="/" end className={({ isActive }) => (isActive ? 'active' : '')}>
          📊 Dashboard
        </NavLink>
        <NavLink to="/farms" className={({ isActive }) => (isActive ? 'active' : '')}>
          🏡 Farms
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
        <span className="badge badge-mild">Demo Mode (Sentinel-2 Sim)</span>
      </div>
    </aside>
  );
};

export default Sidebar;
