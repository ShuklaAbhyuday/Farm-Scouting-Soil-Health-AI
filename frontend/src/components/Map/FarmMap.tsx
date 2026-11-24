import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Polygon, LayersControl, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import HotspotLayer from './HotspotLayer';
import DrawingTools from './DrawingTools';
import { Hotspot } from '../../types';
import { DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM } from '../../utils/constants';

interface Props {
  boundary?: any;
  hotspots?: Hotspot[];
  onHotspotClick?: (h: Hotspot) => void;
  editable?: boolean;
  onBoundaryCreated?: (geojson: any) => void;
  height?: string;
}

const parseGeo = (geom: any) => {
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

const FitBoundsToBoundary: React.FC<{ boundary: any }> = ({ boundary }) => {
  const map = useMap();

  useEffect(() => {
    const geom = parseGeo(boundary);
    if (geom?.type === 'Polygon' && geom.coordinates?.[0]?.length > 0) {
      const latlngs = geom.coordinates[0].map((c: any) => [c[1], c[0]] as [number, number]);
      const bounds = L.latLngBounds(latlngs);
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
      }
    }
  }, [boundary, map]);

  return null;
};

const FarmMap: React.FC<Props> = ({
  boundary,
  hotspots = [],
  onHotspotClick,
  editable = false,
  onBoundaryCreated,
  height = '400px',
}) => {
  const parsedBoundary = parseGeo(boundary);
  const center =
    parsedBoundary?.coordinates?.[0]?.[0]
      ? [parsedBoundary.coordinates[0][0][1], parsedBoundary.coordinates[0][0][0]]
      : DEFAULT_MAP_CENTER;

  return (
    <div className="map-container" style={{ height, width: '100%' }}>
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

        <FitBoundsToBoundary boundary={parsedBoundary} />

        {parsedBoundary && parsedBoundary.type === 'Polygon' && parsedBoundary.coordinates?.[0] && (
          <Polygon
            positions={parsedBoundary.coordinates[0].map((c: any) => [c[1], c[0]])}
            pathOptions={{ color: '#ffffff', weight: 2.5, fillOpacity: 0.08 }}
          />
        )}

        <HotspotLayer hotspots={hotspots} onClick={onHotspotClick} />

        {editable && onBoundaryCreated && <DrawingTools onCreated={onBoundaryCreated} />}
      </MapContainer>
    </div>
  );
};

export default FarmMap;
