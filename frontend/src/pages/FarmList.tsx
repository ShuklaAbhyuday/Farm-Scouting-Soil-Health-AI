import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useFieldContext } from '../context/FieldContext';

const FarmList: React.FC = () => {
  const navigate = useNavigate();
  const { farms, setSelectedFarmId, setSelectedFieldId, loadingFarms } = useFieldContext();

  const handleOpenFarm = (farmId: number, firstFieldId?: number) => {
    setSelectedFarmId(farmId);
    if (firstFieldId) setSelectedFieldId(firstFieldId);
    navigate('/');
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h2>My Farms</h2>
        <Link to="/farms/new" className="btn btn-primary">+ Create New Farm</Link>
      </div>

      {loadingFarms ? (
        <p>Loading farms...</p>
      ) : farms.length === 0 ? (
        <div className="card">
          <p>No farms found yet. Click <strong>Create New Farm</strong> above.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '1rem' }}>
          {farms.map((farm) => (
            <div key={farm.id} className="card">
              <h3>{farm.name}</h3>
              <p>Location: {farm.location_description || `${farm.center_lat.toFixed(3)}, ${farm.center_lng.toFixed(3)}`}</p>
              <p>Fields: {farm.fields?.length ?? 0}</p>
              <p>Area: {farm.total_area_ha ? `${farm.total_area_ha} ha` : 'N/A'}</p>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                <button
                  className="btn btn-primary"
                  onClick={() => handleOpenFarm(farm.id, farm.fields?.[0]?.id)}
                >
                  View Dashboard
                </button>
                <button
                  className="btn"
                  onClick={() => {
                    setSelectedFarmId(farm.id);
                    if (farm.fields?.[0]?.id) setSelectedFieldId(farm.fields[0].id);
                    navigate('/map');
                  }}
                >
                  Open Map
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FarmList;
