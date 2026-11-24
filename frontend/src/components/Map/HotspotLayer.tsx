import React from 'react';
import { Polygon, Tooltip } from 'react-leaflet';
import { Hotspot } from '../../types';
import { getSeverityColor } from '../../utils/helpers';

interface Props {
  hotspots: Hotspot[];
  onClick?: (h: Hotspot) => void;
}

const HotspotLayer: React.FC<Props> = ({ hotspots, onClick }) => {
  return (
    <>
      {hotspots.map((hotspot) => {
        if (!hotspot.geometry_geojson || hotspot.geometry_geojson.type !== 'Polygon') return null;
        
        const positions = hotspot.geometry_geojson.coordinates[0].map((c: any) => [c[1], c[0]]);
        const color = getSeverityColor(hotspot.severity);
        
        return (
          <Polygon 
            key={hotspot.id} 
            positions={positions} 
            pathOptions={{ color, fillColor: color, fillOpacity: 0.6 }}
            eventHandlers={{ click: () => onClick && onClick(hotspot) }}
          >
            <Tooltip>
              <div>
                <strong>Severity:</strong> {hotspot.severity}<br />
                <strong>Score:</strong> {hotspot.health_score}
              </div>
            </Tooltip>
          </Polygon>
        );
      })}
    </>
  );
};

export default HotspotLayer;
