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

interface SearchSuggestion {
  place_id: number;
  display_name: string;
  lat: string;
  lon: string;
  type?: string;
  addresstype?: string;
  boundingbox?: [string, string, string, string];
}

interface InteractiveFieldMapProps {
  boundary?: any;
  hotspots?: Hotspot[];
  selectedHotspotId?: number | null;
  onHotspotClick?: (hotspot: Hotspot) => void;
  drawingMode?: boolean;
  onToggleDrawing?: (active: boolean) => void;
  onPolygonComplete?: (geojson: GeoJSON.Polygon, areaHa: number) => void;
  onDraftChange?: (pointCount: number, geojson: GeoJSON.Polygon | null, areaHa: number) => void;
  clearDraftSignal?: number;
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
  skipFit: boolean;
}> = ({ boundary, flyTarget, skipFit }) => {
  const map = useMap();

  useEffect(() => {
    if (skipFit) return;
    const geom = parseGeoJSON(boundary);
    if (geom?.type === 'Polygon' && geom.coordinates?.[0]?.length > 2) {
      const latlngs = geom.coordinates[0].map((c: number[]) => [c[1], c[0]] as [number, number]);
      const bounds = L.latLngBounds(latlngs);
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [45, 45], maxZoom: 16 });
      }
    }
  }, [boundary, map, skipFit]);

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
  onDraftChange,
  clearDraftSignal = 0,
  height = '540px',
}) => {
  const [draftPoints, setDraftPoints] = useState<LatLngPoint[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightedIdx, setHighlightedIdx] = useState<number>(-1);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [flyTarget, setFlyTarget] = useState<{ center: [number, number]; zoom: number } | null>(null);

  const parsedBoundary = useMemo(() => parseGeoJSON(boundary), [boundary]);

  const draftAreaHa = useMemo(() => computePolygonAreaHa(draftPoints), [draftPoints]);

  useEffect(() => {
    const q = searchQuery.trim();
    const isCoord = /^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/.test(q);
    if (q.length < 2 || isCoord) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const resp = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=5&q=${encodeURIComponent(q)}`,
          { signal: controller.signal }
        );
        const data: SearchSuggestion[] = await resp.json();
        setSuggestions(Array.isArray(data) ? data : []);
        setHighlightedIdx(-1);
        setShowSuggestions(Array.isArray(data) && data.length > 0);
      } catch (err: any) {
        if (err?.name !== 'AbortError') {
          setSuggestions([]);
        }
      }
    }, 280);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [searchQuery]);

  const selectSuggestion = (item: SearchSuggestion) => {
    const lat = parseFloat(item.lat);
    const lon = parseFloat(item.lon);
    const kind = item.addresstype || item.type || '';
    const zoom = ['village', 'hamlet', 'suburb', 'neighbourhood', 'farm'].includes(kind) ? 15 : 13;
    setSearchQuery(item.display_name.split(',')[0]);
    setShowSuggestions(false);
    setSearchError(null);
    setFlyTarget({ center: [lat, lon], zoom });
  };

  useEffect(() => {
    if (clearDraftSignal > 0) {
      setDraftPoints([]);
    }
  }, [clearDraftSignal]);

  useEffect(() => {
    if (!onDraftChange) return;
    if (draftPoints.length >= 3) {
      onDraftChange(draftPoints.length, pointsToGeoJSON(draftPoints), draftAreaHa);
    } else {
      onDraftChange(draftPoints.length, null, 0);
    }
  }, [draftPoints, draftAreaHa, onDraftChange]);

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
    if (highlightedIdx >= 0 && suggestions[highlightedIdx]) {
      selectSuggestion(suggestions[highlightedIdx]);
      return;
    }

    const q = searchQuery.trim();
    if (!q) return;

    // Support direct "lat, lng" input too
    const coordMatch = q.match(/^(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)$/);
    if (coordMatch) {
      setShowSuggestions(false);
      setSearchError(null);
      setFlyTarget({ center: [parseFloat(coordMatch[1]), parseFloat(coordMatch[2])], zoom: 15 });
      return;
    }

    if (suggestions.length > 0) {
      selectSuggestion(suggestions[0]);
      return;
    }

    setSearching(true);
    setSearchError(null);
    try {
      const resp = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&limit=5&q=${encodeURIComponent(q)}`
      );
      const data: SearchSuggestion[] = await resp.json();
      if (data && data.length > 0) {
        selectSuggestion(data[0]);
      } else {
        setSearchError('Location not found. Try a city, village, or "lat, lng".');
      }
    } catch {
      setSearchError('Search temporarily unavailable.');
    } finally {
      setSearching(false);
    }
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || suggestions.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIdx((prev) => (prev + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIdx((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1));
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
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
      {/* Floating Top Search + Autocomplete Suggestions */}
      <div className="map-floating-top" onClick={(e) => e.stopPropagation()}>
        <form onSubmit={handleSearch} className="map-search-bar">
          <input
            type="text"
            placeholder="Search city, village, or lat, lng..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setSearchError(null);
            }}
            onFocus={() => {
              if (suggestions.length > 0) setShowSuggestions(true);
            }}
            onBlur={() => {
              setTimeout(() => setShowSuggestions(false), 180);
            }}
            onKeyDown={handleSearchKeyDown}
            aria-label="Search map location"
            autoComplete="off"
          />
          <button type="submit" disabled={searching}>
            {searching ? '...' : 'Go'}
          </button>
          <button type="button" onClick={handleLocateMe} title="Use my current location" className="btn-ghost-sm">
            📍
          </button>
        </form>

        {showSuggestions && suggestions.length > 0 && (
          <div className="map-suggestions" role="listbox" aria-label="Place suggestions">
            {suggestions.map((item, idx) => {
              const parts = item.display_name.split(',');
              const title = parts[0]?.trim();
              const subtitle = parts.slice(1).join(',').trim();
              const kind = item.addresstype || item.type || 'place';
              return (
                <button
                  key={item.place_id}
                  type="button"
                  className={`map-suggestion-item ${idx === highlightedIdx ? 'highlighted' : ''}`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    selectSuggestion(item);
                  }}
                >
                  <div className="map-suggestion-title">
                    <span>{title}</span>
                    <span className="map-suggestion-type">{kind}</span>
                  </div>
                  {subtitle && <div className="map-suggestion-sub">{subtitle}</div>}
                </button>
              );
            })}
          </div>
        )}

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

        <MapController boundary={parsedBoundary} flyTarget={flyTarget} skipFit={drawingMode && draftPoints.length > 0} />
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
