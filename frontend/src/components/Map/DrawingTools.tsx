import React from 'react';
import { FeatureGroup } from 'react-leaflet';
import { EditControl } from 'react-leaflet-draw';
import 'leaflet-draw/dist/leaflet.draw.css';

interface Props {
  onCreated: (geojson: any) => void;
}

const DrawingTools: React.FC<Props> = ({ onCreated }) => {
  const _onCreated = (e: any) => {
    const layer = e.layer;
    onCreated(layer.toGeoJSON().geometry);
  };

  return (
    <FeatureGroup>
      <EditControl
        position="topright"
        onCreated={_onCreated}
        draw={{
          rectangle: false,
          circle: false,
          circlemarker: false,
          marker: false,
          polyline: false,
          polygon: {
            allowIntersection: false,
            drawError: { color: '#e1e100', message: '<strong>Oh snap!<strong> you can\'t draw that!' },
            shapeOptions: { color: '#97009c' }
          }
        } as any}
      />
    </FeatureGroup>
  );
};

export default DrawingTools;

