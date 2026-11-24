import React from 'react';
import { MapContainer, TileLayer, Polygon, LayersControl } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import HotspotLayer from './HotspotLayer';
import { Hotspot } from '../../types';
import { DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM } from '../../utils/constants';

interface Props {
  boundary?: any;
  hotspots?: Hotspot[];
  onHotspotClick?: (h: Hotspot) => void;
}

const FarmMap: React.FC<Props> = ({ boundary, hotspots = [], onHotspotClick }) => {
  const center = boundary?.coordinates ? [boundary.coordinates[0][0][1], boundary.coordinates[0][0][0]] : DEFAULT_MAP_CENTER;

  return (
    <div className="map-container" style={{ height: '400px', width: '100%' }}>
      <MapContainer center={center as any} zoom={DEFAULT_MAP_ZOOM} style={{ height: '100%', width: '100%' }}>
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Google Satellite">
            <TileLayer 
              url="https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}" 
              attribution="&copy; Google Maps" 
              maxZoom={20}
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="ESRI Satellite">
            <TileLayer 
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" 
              attribution="&copy; Esri" 
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="OpenStreetMap">
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
          </LayersControl.BaseLayer>
        </LayersControl>
        
        {boundary && boundary.type === 'Polygon' && (
          <Polygon positions={boundary.coordinates[0].map((c: any) => [c[1], c[0]])} pathOptions={{ color: 'white', fillOpacity: 0.1 }} />
        )}
        
        <HotspotLayer hotspots={hotspots} onClick={onHotspotClick} />
      </MapContainer>
    </div>
  );
};

export default FarmMap;
