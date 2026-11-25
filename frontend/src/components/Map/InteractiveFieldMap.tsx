import React, { useEffect, useMemo, useState } from 'react';
import {
  CircleMarker,
  LayersControl,
  MapContainer,
  Polygon,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
  useMapEvents,
} from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import { Hotspot } from '../../types';
import { DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM, SEVERITY_COLORS } from '../../utils/constants';

export interface LatLngPoint {
  lat: number;
  lng: number;
}

interface InteractiveFieldMapProps {
  boundary?: any;
  hotspots?: Hotspot[];
  selectedHotspotId?: number | null;
  onHotspotClick?: (hotspot: Hotspot) => void;
  drawingMode?: boolean;
  onToggleDrawing?: (active: boolean) => void;
  onPolygonComplete?: (geojson: GeoJSON.Polygon, areaHa: number) => void;
  height?: string;
}

export function parseGeoJSON(geom: any): any {
  if (!geom) return null;
  if (typeof geom === 'string') {
    try {
      return JSON.parse(geom);
    } catch {
      return null;
    }
  }
  return geom;
}

export function computePolygonAreaHa(points: LatLngPoint[]): number {
  if (points.length < 3) return 0;
  const R = 6378137;
  let area = 0;
  for (let i = 0; i < points.length; i++) {
    const p1 = points[i];
    const p2 = points[(i + 1) % points.length];
    const lat1 = (p1.lat * Math.PI) / 180;
    const lat2 = (p2.lat * Math.PI) / 180;
    const dLng = ((p2.lng - p1.lng) * Math.PI) / 180;
    area += dLng * (2 + Math.sin(lat1) + Math.sin(lat2));
  }
  const sqMeters = Math.abs((area * R * R) / 2);
  return Math.round((sqMeters / 10000) * 100) / 100;
}

export function pointsToGeoJSON(points: LatLngPoint[]): GeoJSON.Polygon {
  const ring = points.map((p) => [Number(p.lng.toFixed(6)), Number(p.lat.toFixed(6))]);
  ring.push(ring[0]);
  return {
    type: 'Polygon',
    coordinates: [ring],
  };
}

const MapController: React.FC<{
  boundary: any;
  flyTarget: { center: [number, number]; zoom: number } | null;
}> = ({ boundary, flyTarget }) => {
  const map = useMap();

  useEffect(() => {
    const geom = parseGeoJSON(boundary);
    if (geom?.type === 'Polygon' && geom.coordinates?.[0]?.length > 2) {
      const latlngs = geom.coordinates[0].map((c: number[]) => [c[1], c[0]] as [number, number]);
      const bounds = L.latLngBounds(latlngs);
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [45, 45], maxZoom: 16 });
      }
    }
  }, [boundary, map]);

  useEffect(() => {
    if (flyTarget) {
      map.flyTo(flyTarget.center, flyTarget.zoom, { duration: 1.0 });
    }
  }, [flyTarget, map]);

  return null;
};

const DrawClickCapture: React.FC<{
  active: boolean;
  onAddPoint: (pt: LatLngPoint) => void;
}> = ({ active, onAddPoint }) => {
  useMapEvents({
    click(e) {
      if (!active) return;
      onAddPoint({ lat: e.latlng.lat, lng: e.latlng.lng });
    },
  });
  return null;
};

const InteractiveFieldMap: React.FC<InteractiveFieldMapProps> = ({
  boundary,
  hotspots = [],
  selectedHotspotId = null,
  onHotspotClick,
  drawingMode = false,
  onToggleDrawing,
  onPolygonComplete,
  height = '540px',
}) => {
  const [draftPoints, setDraftPoints] = useState<LatLngPoint[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [flyTarget, setFlyTarget] = useState<{ center: [number, number]; zoom: number } | null>(null);

  const parsedBoundary = useMemo(() => parseGeoJSON(boundary), [boundary]);

  const draftAreaHa = useMemo(() => computePolygonAreaHa(draftPoints), [draftPoints]);

  const handleFinishPolygon = (pts = draftPoints) => {
    if (pts.length < 3 || !onPolygonComplete) return;
    const geo = pointsToGeoJSON(pts);
    const area = computePolygonAreaHa(pts);
    onPolygonComplete(geo, area);
    setDraftPoints([]);
    if (onToggleDrawing) onToggleDrawing(false);
  };

  const handleUndo = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDraftPoints((prev) => prev.slice(0, -1));
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    setDraftPoints([]);
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;

    // Support direct "lat, lng" input too
    const coordMatch = q.match(/^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/);
    if (coordMatch) {
      setSearchError(null);
      setFlyTarget({ center: [parseFloat(coordMatch[1]), parseFloat(coordMatch[2])], zoom: 15 });
      return;
    }

    setSearching(true);
    setSearchError(null);
    try {
      const resp = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(q)}`
      );
      const data = await resp.json();
      if (data && data.length > 0) {
        setFlyTarget({
          center: [parseFloat(data[0].lat), parseFloat(data[0].lon)],
          zoom: 15,
        });
      } else {
        setSearchError('Location not found. Try a city, village, or "lat, lng".');
      }
    } catch {
      setSearchError('Search temporarily unavailable.');
    } finally {
      setSearching(false);
    }
  };

  const handleLocateMe = () => {
    if (!navigator.geolocation) {
      setSearchError('Geolocation is not supported by your browser.');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setSearchError(null);
        setFlyTarget({ center: [pos.coords.latitude, pos.coords.longitude], zoom: 16 });
      },
      () => {
        setSearchError('Location permission denied. Search by city or area instead.');
      }
    );
  };

  return (
    <div className={`map-shell ${drawingMode ? 'is-drawing' : ''}`} style={{ height }}>
      {/* Floating Top Search + Quick Map Actions */}
      <div className="map-floating-top">
        <form onSubmit={handleSearch} className="map-search-bar">
          <input
            type="text"
            placeholder="Jump to city, village, or lat, lng..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            aria-label="Search map location"
          />
          <button type="submit" disabled={searching}>
            {searching ? '...' : 'Go'}
          </button>
          <button type="button" onClick={handleLocateMe} title="Use my current location" className="btn-ghost-sm">
            📍
          </button>
        </form>
        {searchError && <div className="map-toast-err">{searchError}</div>}
      </div>

      {/* Floating Bottom Drawing Controls */}
      {onPolygonComplete && (
        <div className="map-floating-bottom">
          {!drawingMode ? (
            <button
              type="button"
              className="map-pill-btn primary"
              onClick={() => {
                setDraftPoints([]);
                if (onToggleDrawing) onToggleDrawing(true);
              }}
            >
              ✏️ {parsedBoundary ? 'Redraw Field Boundary' : 'Start Drawing Field'}
            </button>
          ) : (
            <div className="map-draw-toolbar">
              <span className="draw-status-chip">
                {draftPoints.length === 0
                  ? 'Click map corners to trace boundary'
                  : `${draftPoints.length} pts${draftPoints.length >= 3 ? ` · ~${draftAreaHa} ha` : ' (need ≥ 3)'}`}
              </span>
              {draftPoints.length > 0 && (
                <button type="button" className="map-pill-btn" onClick={handleUndo}>
                  ↩ Undo
                </button>
              )}
              {draftPoints.length > 0 && (
                <button type="button" className="map-pill-btn" onClick={handleClear}>
                  Clear
                </button>
              )}
              {draftPoints.length >= 3 && (
                <button
                  type="button"
                  className="map-pill-btn primary"
                  onClick={() => handleFinishPolygon()}
                >
                  ✓ Finish Field
                </button>
              )}
              {onToggleDrawing && (
                <button
                  type="button"
                  className="map-pill-btn"
                  onClick={() => {
                    setDraftPoints([]);
                    onToggleDrawing(false);
                  }}
                >
                  Cancel
                </button>
              )}
            </div>
          )}
        </div>
      )}

      <MapContainer
        center={DEFAULT_MAP_CENTER}
        zoom={DEFAULT_MAP_ZOOM}
        style={{ height: '100%', width: '100%' }}
      >
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Satellite Hybrid">
            <TileLayer
              url="https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}"
              attribution="&copy; Google"
              maxZoom={20}
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="ESRI World Imagery">
            <TileLayer
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
              attribution="&copy; Esri"
            />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Street Map">
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution="&copy; OpenStreetMap"
            />
          </LayersControl.BaseLayer>
        </LayersControl>

        <MapController boundary={parsedBoundary} flyTarget={flyTarget} />
        <DrawClickCapture
          active={drawingMode}
          onAddPoint={(pt) => setDraftPoints((prev) => [...prev, pt])}
        />

        {/* Saved / Completed Field Polygon */}
        {parsedBoundary?.type === 'Polygon' && parsedBoundary.coordinates?.[0] && (
          <Polygon
            positions={parsedBoundary.coordinates[0].map((c: number[]) => [c[1], c[0]])}
            pathOptions={{
              color: '#ffffff',
              weight: 2.5,
              fillColor: '#0f766e',
              fillOpacity: hotspots.length > 0 ? 0.05 : 0.18,
            }}
          />
        )}

        {/* Live Draft Polygon while Drawing */}
        {drawingMode && draftPoints.length >= 2 && (
          <Polyline
            positions={draftPoints.map((p) => [p.lat, p.lng])}
            pathOptions={{ color: '#2dd4bf', weight: 2.5, dashArray: '6 5' }}
          />
        )}
        {drawingMode && draftPoints.length >= 3 && (
          <Polygon
            positions={draftPoints.map((p) => [p.lat, p.lng])}
            pathOptions={{ color: '#2dd4bf', weight: 2, fillColor: '#14b8a6', fillOpacity: 0.22 }}
          />
        )}
        {drawingMode &&
          draftPoints.map((pt, idx) => {
            const isFirstCloseable = idx === 0 && draftPoints.length >= 3;
            return (
              <CircleMarker
                key={`${pt.lat}-${pt.lng}-${idx}`}
                center={[pt.lat, pt.lng]}
                radius={isFirstCloseable ? 8 : 5}
                pathOptions={{
                  color: '#ffffff',
                  weight: 2,
                  fillColor: isFirstCloseable ? '#22c55e' : '#0d9488',
                  fillOpacity: 1,
                }}
                eventHandlers={
                  isFirstCloseable
                    ? {
                        click: (e) => {
                          L.DomEvent.stopPropagation(e.originalEvent);
                          handleFinishPolygon(draftPoints);
                        },
                      }
                    : undefined
                }
              >
                {isFirstCloseable && <Tooltip permanent direction="top">Click to close polygon</Tooltip>}
              </CircleMarker>
            );
          })}

        {/* Stress Hotspot Zones Overlay */}
        {hotspots.map((hotspot) => {
          const geom = parseGeoJSON(hotspot.geometry_geojson);
          if (!geom || geom.type !== 'Polygon' || !geom.coordinates?.[0]) return null;
          const color = SEVERITY_COLORS[hotspot.severity] || '#22c55e';
          const isSelected = selectedHotspotId === hotspot.id;

          return (
            <Polygon
              key={hotspot.id}
              positions={geom.coordinates[0].map((c: number[]) => [c[1], c[0]])}
              pathOptions={{
                color: isSelected ? '#ffffff' : color,
                weight: isSelected ? 3 : 1.5,
                fillColor: color,
                fillOpacity: isSelected ? 0.68 : 0.45,
              }}
              eventHandlers={{
                click: () => onHotspotClick && onHotspotClick(hotspot),
              }}
            >
              <Tooltip>
                <div style={{ fontSize: '12px' }}>
                  <strong>{hotspot.likely_issue || 'Zone'}</strong> ({hotspot.severity})<br />
                  Health Score: {hotspot.health_score}/100 · NDVI {hotspot.ndvi_value?.toFixed(2)}
                </div>
              </Tooltip>
            </Polygon>
          );
        })}
      </MapContainer>
    </div>
  );
};

export default InteractiveFieldMap;
