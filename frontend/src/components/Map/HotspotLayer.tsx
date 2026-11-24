import React from 'react';
import { Polygon, Tooltip } from 'react-leaflet';
import { Hotspot } from '../../types';
import { getSeverityColor } from '../../utils/helpers';

interface Props {
  hotspots: Hotspot[];
  onClick?: (h: Hotspot) => void;
}

const parseGeometry = (geom: any) => {
  if (!geom) return null;
  if (typeof geom === 'string') {
    try {
      return JSON.parse(geom);
    } catch {
      return null;
    }
  }
  return geom;
};

const HotspotLayer: React.FC<Props> = ({ hotspots, onClick }) => {
  return (
    <>
      {hotspots.map((hotspot) => {
        const geom = parseGeometry(hotspot.geometry_geojson);
        if (!geom || geom.type !== 'Polygon' || !geom.coordinates?.[0]) return null;

        const positions = geom.coordinates[0].map((c: any) => [c[1], c[0]]);
        const color = getSeverityColor(hotspot.severity);

        return (
          <Polygon
            key={hotspot.id}
            positions={positions}
            pathOptions={{ color, fillColor: color, fillOpacity: 0.55, weight: 2 }}
            eventHandlers={{ click: () => onClick && onClick(hotspot) }}
          >
            <Tooltip>
              <div>
                <strong>{hotspot.likely_issue || 'Detected Zone'}</strong><br />
                <strong>Severity:</strong> {hotspot.severity}<br />
                <strong>Score:</strong> {hotspot.health_score}/100<br />
                {onClick && <em>Click for AI details</em>}
              </div>
            </Tooltip>
          </Polygon>
        );
      })}
    </>
  );
};

export default HotspotLayer;
