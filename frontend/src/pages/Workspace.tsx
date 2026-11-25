import React, { useCallback, useEffect, useState } from 'react';
import InteractiveFieldMap, { computePolygonAreaHa } from '../components/Map/InteractiveFieldMap';
import TimeSeriesChart from '../components/Charts/TimeSeriesChart';
import api from '../services/api';
import { useFieldContext } from '../context/FieldContext';
import { createField, deleteField, getField } from '../services/fieldService';
import { analyzeField } from '../services/satelliteService';
import { getDashboard } from '../services/dashboardService';
import { getHotspots } from '../services/hotspotService';
import {
  createSoilSample,
  deleteSoilSample,
  getSoilSamples,
  updateSoilSample,
} from '../services/soilService';
import {
  computeCropRecommendations,
  getCropRecommendations,
} from '../services/recommendationService';
import { downloadReport, generateReport } from '../services/reportService';
import { CROP_TYPES, SOIL_TEXTURES } from '../utils/constants';
import {
  CropRecommendationResponse,
  DashboardSummary,
  Hotspot,
  SoilSample,
} from '../types';

type Stage = 1 | 2 | 3;

const DEMO_SAMPLE_POLYGON: GeoJSON.Polygon = {
  type: 'Polygon',
  coordinates: [
    [
      [76.8485, 23.0755],
      [76.8535, 23.0755],
      [76.8535, 23.0795],
      [76.8485, 23.0795],
      [76.8485, 23.0755],
    ],
  ],
};

const Workspace: React.FC = () => {
  const {
    farms,
    selectedFarmId,
    selectedFieldId,
    setSelectedFieldId,
    refreshFarms,
  } = useFieldContext();

  const [stage, setStage] = useState<Stage>(1);

  // Stage 1: Field Drawing State
  const [drawingMode, setDrawingMode] = useState<boolean>(true);
  const [drawnPolygon, setDrawnPolygon] = useState<GeoJSON.Polygon | null>(null);
  const [drawnAreaHa, setDrawnAreaHa] = useState<number>(0);
  const [draftPointCount, setDraftPointCount] = useState<number>(0);
  const [draftPolygon, setDraftPolygon] = useState<GeoJSON.Polygon | null>(null);
  const [draftAreaHa, setDraftAreaHa] = useState<number>(0);
  const [clearDraftSignal, setClearDraftSignal] = useState<number>(0);
  const [fieldName, setFieldName] = useState<string>('My Field Plot');
  const [cropType, setCropType] = useState<string>('Wheat');
  const [startDate] = useState<string>('2023-01-01');
  const [endDate, setEndDate] = useState<string>('2024-12-31');

  // Stage 2: Satellite Data State
  const [activeBoundary, setActiveBoundary] = useState<any>(null);
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [selectedHotspot, setSelectedHotspot] = useState<Hotspot | null>(null);
  const [historyObs, setHistoryObs] = useState<any[]>([]);
  const [scanning, setScanning] = useState<boolean>(false);
  const [scanProgress, setScanProgress] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  // Stage 3: Soil Samples + Soil Result + Crop Recommendation State
  const [soilSamples, setSoilSamples] = useState<SoilSample[]>([]);
  const [activeSoilSample, setActiveSoilSample] = useState<SoilSample | null>(null);
  const [soilForm, setSoilForm] = useState({
    nitrogen_level: 'low',
    nitrogen_value: '',
    phosphorus_level: 'medium',
    phosphorus_value: '',
    potassium_level: 'medium',
    potassium_value: '',
    ph_value: 6.8,
    moisture_level: 'medium',
    soil_texture: 'Loamy',
    source: 'lab',
    is_validated: true,
    notes: '',
  });
  const [submittingSoil, setSubmittingSoil] = useState<boolean>(false);
  const [soilStatus, setSoilStatus] = useState<string | null>(null);

  const [cropRecs, setCropRecs] = useState<CropRecommendationResponse | null>(null);
  const [seasonFilter, setSeasonFilter] = useState<string>('All');
  const [loadingCrops, setLoadingCrops] = useState<boolean>(false);
  const [downloadingPdf, setDownloadingPdf] = useState<boolean>(false);

  const allFields = farms.flatMap((f) => f.fields || []);

  const loadFieldData = useCallback(async (fldId: number) => {
    try {
      const [fldRes, dashRes, hsRes, histRes, soilRes, cropRes] = await Promise.all([
        getField(fldId).catch(() => null),
        getDashboard(fldId).catch(() => null),
        getHotspots(fldId).catch(() => ({ data: [] })),
        api.get(`/fields/${fldId}/history`).catch(() => ({ data: { observations: [] } })),
        getSoilSamples(fldId).catch(() => ({ data: [] })),
        getCropRecommendations(fldId).catch(() => null),
      ]);

      if (fldRes?.data?.boundary_geojson) {
        setActiveBoundary(fldRes.data.boundary_geojson);
      }
      if (dashRes?.data) setDashboard(dashRes.data);
      const hsList: Hotspot[] = hsRes.data || [];
      setHotspots(hsList);
      setSelectedHotspot(hsList[0] || null);
      setHistoryObs(histRes.data?.observations || []);

      const samples: SoilSample[] = soilRes.data || [];
      setSoilSamples(samples);
      setActiveSoilSample(samples[0] || null);

      if (cropRes?.data) setCropRecs(cropRes.data);
    } catch (err) {
      console.error('Failed loading field state:', err);
    }
  }, []);

  useEffect(() => {
    if (selectedFieldId) {
      loadFieldData(selectedFieldId);
    }
  }, [selectedFieldId, loadFieldData]);

  // Handlers
  const handleDraftChange = useCallback((count: number, geojson: GeoJSON.Polygon | null, areaHa: number) => {
    setDraftPointCount(count);
    setDraftPolygon(geojson);
    setDraftAreaHa(areaHa);
  }, []);

  const handlePolygonComplete = (geojson: GeoJSON.Polygon, areaHa: number) => {
    setDrawnPolygon(geojson);
    setDrawnAreaHa(areaHa);
    setDraftPointCount(0);
    setDraftPolygon(null);
    setActiveBoundary(geojson);
    setHotspots([]);
    setScanError(null);
  };

  const handleLoadDemoPolygon = () => {
    const pts = DEMO_SAMPLE_POLYGON.coordinates[0].slice(0, -1).map((c) => ({ lat: c[1], lng: c[0] }));
    const area = computePolygonAreaHa(pts);
    setDrawnPolygon(DEMO_SAMPLE_POLYGON);
    setDrawnAreaHa(area);
    setDraftPointCount(0);
    setDraftPolygon(null);
    setClearDraftSignal((n) => n + 1);
    setActiveBoundary(DEMO_SAMPLE_POLYGON);
    setDrawingMode(false);
    setHotspots([]);
    setScanError(null);
  };

  const handleStartNewField = () => {
    setDrawnPolygon(null);
    setDrawnAreaHa(0);
    setDraftPointCount(0);
    setDraftPolygon(null);
    setClearDraftSignal((n) => n + 1);
    setActiveBoundary(null);
    setHotspots([]);
    setFieldName(`Field ${allFields.length + 1}`);
    setDrawingMode(true);
    setScanError(null);
    setStage(1);
  };

  const pendingNewPolygon = drawnPolygon || draftPolygon;
  const pendingAreaHa = drawnPolygon ? drawnAreaHa : draftAreaHa;

  const handleSaveOnly = async () => {
    if (!pendingNewPolygon) return;
    setScanning(true);
    setScanError(null);
    setScanProgress('Saving field boundary...');
    try {
      const created = await createField(selectedFarmId || 1, {
        name: fieldName.trim() || `Field ${allFields.length + 1}`,
        boundary_geojson: pendingNewPolygon,
        crop_type: cropType,
        growth_stage: 'Vegetative',
      });
      const targetFieldId = created.data.id;
      setDrawnPolygon(null);
      setDraftPolygon(null);
      setDraftPointCount(0);
      setClearDraftSignal((n) => n + 1);
      setDrawingMode(false);
      await refreshFarms(targetFieldId);
      await loadFieldData(targetFieldId);
      setScanProgress(`Saved "${created.data.name}" (${created.data.area_ha} ha)!`);
    } catch (err: any) {
      setScanError(err?.response?.data?.detail || 'Failed to save field boundary.');
      setScanProgress(null);
    } finally {
      setScanning(false);
    }
  };

  const handleRunSatellitePipeline = async () => {
    setScanning(true);
    setScanError(null);
    try {
      let targetFieldId = selectedFieldId;

      if (pendingNewPolygon) {
        setScanProgress('1/2 Saving your drawn field boundary...');
        const created = await createField(selectedFarmId || 1, {
          name: fieldName.trim() || `Field ${allFields.length + 1}`,
          boundary_geojson: pendingNewPolygon,
          crop_type: cropType,
          growth_stage: 'Vegetative',
        });
        targetFieldId = created.data.id;
        setDrawnPolygon(null);
        setDraftPolygon(null);
        setDraftPointCount(0);
        setClearDraftSignal((n) => n + 1);
        setDrawingMode(false);
        await refreshFarms(targetFieldId);
      }

      setScanProgress('2/2 Fetching Sentinel-2 imagery & running Isolation Forest ML scan...');
      await analyzeField(targetFieldId, {
        start_date: startDate,
        end_date: endDate,
      });

      await loadFieldData(targetFieldId);
      setDrawingMode(false);
      setScanProgress(null);
      setStage(2);
    } catch (err: any) {
      console.error('Satellite pipeline failed:', err);
      const detail = err?.response?.data?.detail;
      setScanProgress(null);
      setScanError(
        detail
          ? `Satellite scan error: ${detail}`
          : 'Could not reach backend or find clear Sentinel-2 imagery in date range. Try widening dates or wait a few seconds if server is waking up.'
      );
    } finally {
      setScanning(false);
    }
  };

  const handleRescanOnly = async () => {
    setScanning(true);
    setScanError(null);
    try {
      await analyzeField(selectedFieldId, { start_date: startDate, end_date: endDate });
      await loadFieldData(selectedFieldId);
    } catch (err: any) {
      setScanError(err?.response?.data?.detail || 'Re-scan failed.');
    } finally {
      setScanning(false);
    }
  };

  const handleSubmitSoil = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingSoil(true);
    setSoilStatus(null);
    try {
      const res = await createSoilSample(selectedFieldId, {
        latitude: 23.0775,
        longitude: 76.8513,
        nitrogen_level: soilForm.nitrogen_level,
        nitrogen_value: soilForm.nitrogen_value ? parseFloat(soilForm.nitrogen_value) : undefined,
        phosphorus_level: soilForm.phosphorus_level,
        phosphorus_value: soilForm.phosphorus_value ? parseFloat(soilForm.phosphorus_value) : undefined,
        potassium_level: soilForm.potassium_level,
        potassium_value: soilForm.potassium_value ? parseFloat(soilForm.potassium_value) : undefined,
        ph_value: soilForm.ph_value,
        moisture_level: soilForm.moisture_level,
        soil_texture: soilForm.soil_texture,
        sample_date: new Date().toISOString(),
        source: soilForm.source,
        is_validated: soilForm.is_validated,
        notes: soilForm.notes,
      });

      const createdSample: SoilSample = res.data;
      setActiveSoilSample(createdSample);
      setSoilStatus('Soil sample analyzed and saved.');

      const [samplesRes, cropRes] = await Promise.all([
        getSoilSamples(selectedFieldId),
        computeCropRecommendations(selectedFieldId, {
          season: seasonFilter,
          use_latest_sample: true,
        }),
      ]);
      setSoilSamples(samplesRes.data || []);
      setCropRecs(cropRes.data);
    } catch (err) {
      console.error('Soil submission failed:', err);
      setSoilStatus('Failed to save soil sample. Check backend connection.');
    } finally {
      setSubmittingSoil(false);
    }
  };

  const handleToggleValidate = async (s: SoilSample) => {
    try {
      const res = await updateSoilSample(s.id, { is_validated: !s.is_validated });
      if (activeSoilSample?.id === s.id) setActiveSoilSample(res.data);
      const [samplesRes, cropRes] = await Promise.all([
        getSoilSamples(selectedFieldId),
        computeCropRecommendations(selectedFieldId, { season: seasonFilter, use_latest_sample: true }),
      ]);
      setSoilSamples(samplesRes.data || []);
      setCropRecs(cropRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteSample = async (id: number) => {
    try {
      await deleteSoilSample(id);
      const samplesRes = await getSoilSamples(selectedFieldId);
      const next = samplesRes.data || [];
      setSoilSamples(next);
      if (activeSoilSample?.id === id) setActiveSoilSample(next[0] || null);
      const cropRes = await getCropRecommendations(selectedFieldId);
      setCropRecs(cropRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleSeasonChange = async (newSeason: string) => {
    setSeasonFilter(newSeason);
    setLoadingCrops(true);
    try {
      const res = await computeCropRecommendations(selectedFieldId, {
        season: newSeason,
        use_latest_sample: true,
      });
      setCropRecs(res.data);
    } finally {
      setLoadingCrops(false);
    }
  };

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      const created = await generateReport(selectedFieldId, { report_type: 'field_summary' });
      const dl = await downloadReport(created.data.id);
      const blob = new Blob([dl.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `terrascan_field_${selectedFieldId}_report.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('PDF export failed:', err);
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleDeleteCurrentField = async () => {
    if (allFields.length <= 1) return;
    try {
      await deleteField(selectedFieldId);
      const remaining = allFields.find((f) => f.id !== selectedFieldId);
      await refreshFarms(remaining?.id);
    } catch (err) {
      console.error('Failed to delete field:', err);
    }
  };

  const levelBadge = (lvl: string) => {
    if (lvl === 'low') return 'badge-severe';
    if (lvl === 'medium') return 'badge-healthy';
    return 'badge-mild';
  };

  const analysis = activeSoilSample?.analysis;

  return (
    <>
      {/* TOP NAVIGATION & STEPPER */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <polygon points="3 6 12 2 21 6 18 18 6 21 3 6" />
              <circle cx="12" cy="12" r="2.5" fill="currentColor" />
            </svg>
          </div>
          <span>TerraScan</span>
        </div>

        <nav className="stepper-rail" aria-label="Workflow steps">
          <button
            type="button"
            className={`step-pill ${stage === 1 ? 'active' : ''}`}
            onClick={() => setStage(1)}
          >
            <span className="step-num">01</span> Draw Field
          </button>
          <button
            type="button"
            className={`step-pill ${stage === 2 ? 'active' : ''}`}
            onClick={() => {
              setDrawingMode(false);
              setStage(2);
            }}
          >
            <span className="step-num">02</span> Satellite Analysis
          </button>
          <button
            type="button"
            className={`step-pill ${stage === 3 ? 'active' : ''}`}
            onClick={() => {
              setDrawingMode(false);
              setStage(3);
            }}
          >
            <span className="step-num">03</span> Soil &amp; Crop Results
          </button>
        </nav>

        <div className="topbar-right">
          {allFields.length > 0 && (
            <select
              className="field-select"
              aria-label="Saved Fields"
              value={selectedFieldId}
              onChange={(e) => {
                setDrawnPolygon(null);
                setDrawingMode(false);
                setSelectedFieldId(Number(e.target.value));
              }}
            >
              {allFields.map((fld) => (
                <option key={fld.id} value={fld.id}>
                  {fld.name} ({fld.area_ha ? `${fld.area_ha} ha` : 'Plot'})
                </option>
              ))}
            </select>
          )}
          {allFields.length > 1 && (
            <button
              type="button"
              className="btn btn-sm"
              style={{ color: 'var(--red)' }}
              onClick={handleDeleteCurrentField}
              title="Delete currently selected field"
            >
              Delete
            </button>
          )}
          <button type="button" className="btn btn-sm" onClick={handleStartNewField}>
            + Draw New Field
          </button>
        </div>
      </header>

      <main className="main-stage">
        {/* ================= STAGE 1: DRAW FIELD ================= */}
        {stage === 1 && (
          <div className="split-workspace">
            <InteractiveFieldMap
              boundary={activeBoundary}
              hotspots={[]}
              drawingMode={drawingMode}
              onToggleDrawing={setDrawingMode}
              onPolygonComplete={handlePolygonComplete}
              onDraftChange={handleDraftChange}
              clearDraftSignal={clearDraftSignal}
              height="calc(100vh - 115px)"
            />

            <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <span className="badge badge-neutral">STEP 1 OF 3 · FIELD BOUNDARY</span>
                <h2 style={{ marginTop: '0.5rem', fontSize: '1.3rem' }}>Outline your field on the map</h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', marginTop: '0.25rem' }}>
                  Search your location on the map, click at least 3 corners around your plot, and click <strong>Save &amp; Analyze</strong> below (no extra click needed).
                </p>
              </div>

              <div className={pendingNewPolygon ? 'banner-info' : 'banner-warn'}>
                {pendingNewPolygon ? (
                  <>
                    <strong>Drawn boundary ready:</strong> {drawnPolygon ? 'Completed polygon' : `${draftPointCount} corners placed`} (<span className="mono">~{pendingAreaHa} ha</span>) — click below to save &amp; scan!
                  </>
                ) : drawingMode ? (
                  <>
                    <strong>Drawing mode active:</strong>{' '}
                    {draftPointCount === 0
                      ? 'Click corners directly on the satellite map to trace your field.'
                      : `${draftPointCount} corner(s) placed — click ${3 - draftPointCount} more corner(s) to form a polygon.`}
                  </>
                ) : activeBoundary ? (
                  <>
                    <strong>Loaded saved field:</strong> {dashboard?.field_name || 'Selected field'} — click <strong>Draw Custom Polygon</strong> to trace a new field, or analyze this saved plot.
                  </>
                ) : (
                  <>Click <strong>Draw Custom Polygon</strong> to trace your field boundary.</>
                )}
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={() => {
                    setDrawnPolygon(null);
                    setDraftPolygon(null);
                    setDraftPointCount(0);
                    setClearDraftSignal((n) => n + 1);
                    setDrawingMode(true);
                  }}
                >
                  ✏️ {drawingMode ? 'Restart Drawing' : 'Draw Custom Polygon'}
                </button>
                <button type="button" className="btn btn-sm" onClick={handleLoadDemoPolygon}>
                  Load Sample Plot
                </button>
              </div>

              <div style={{ display: 'grid', gap: '0.75rem', borderTop: '1px solid var(--border)', paddingTop: '0.9rem' }}>
                <label className="field-label">
                  Field Name
                  <input
                    className="input"
                    type="text"
                    value={fieldName}
                    onChange={(e) => setFieldName(e.target.value)}
                    placeholder="e.g. North Plot A"
                  />
                </label>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
                  <label className="field-label">
                    Current / Target Crop
                    <select className="input" value={cropType} onChange={(e) => setCropType(e.target.value)}>
                      {CROP_TYPES.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field-label">
                    Imagery End Date
                    <input
                      className="input"
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                    />
                  </label>
                </div>
              </div>

              {scanProgress && <div className="banner-info">{scanProgress}</div>}
              {scanError && <div className="banner-err">{scanError}</div>}

              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                {pendingNewPolygon && (
                  <button
                    type="button"
                    className="btn"
                    disabled={scanning}
                    onClick={handleSaveOnly}
                  >
                    Save Only
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn-primary"
                  style={{ flex: 1, padding: '0.75rem 1rem', fontSize: '0.95rem' }}
                  disabled={scanning || (!pendingNewPolygon && !activeBoundary)}
                  onClick={handleRunSatellitePipeline}
                >
                  {scanning
                    ? 'Scanning Satellite Imagery...'
                    : pendingNewPolygon
                      ? 'Save Drawn Field & Analyze Satellite →'
                      : 'Analyze Saved Field from Satellite →'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================= STAGE 2: SATELLITE ANALYSIS ================= */}
        {stage === 2 && (
          <div className="split-workspace">
            <InteractiveFieldMap
              boundary={activeBoundary}
              hotspots={hotspots}
              selectedHotspotId={selectedHotspot?.id ?? null}
              onHotspotClick={(h) => setSelectedHotspot(h)}
              drawingMode={false}
              height="calc(100vh - 115px)"
            />

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                  <div>
                    <span className="badge badge-neutral">STEP 2 OF 3 · SATELLITE COMPONENT</span>
                    <h2 style={{ marginTop: '0.4rem', fontSize: '1.25rem' }}>
                      {dashboard?.field_name || 'Field Satellite Scan'}
                    </h2>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      {dashboard?.latest_observation_date
                        ? `Latest scene: ${new Date(dashboard.latest_observation_date).toLocaleDateString()} · ${dashboard.area_ha ?? '—'} ha`
                        : 'No satellite observation recorded yet'}
                    </div>
                  </div>
                  <button type="button" className="btn btn-sm" onClick={handleRescanOnly} disabled={scanning}>
                    {scanning ? 'Scanning...' : '↻ Re-scan'}
                  </button>
                </div>

                {scanError && <div className="banner-err">{scanError}</div>}

                {/* Health Score Summary */}
                <div style={{ padding: '0.85rem', borderRadius: '8px', background: 'var(--bg-page)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.45rem' }}>
                    <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>OVERALL CANOPY HEALTH</span>
                    <span className={`badge ${(dashboard?.health_score ?? 0) >= 80 ? 'badge-healthy' : (dashboard?.health_score ?? 0) >= 60 ? 'badge-mild' : 'badge-moderate'}`}>
                      {dashboard?.overall_health || 'Pending'} · <span className="mono">{dashboard?.health_score ?? '—'}/100</span>
                    </span>
                  </div>
                  <div className="score-bar-track">
                    <div
                      className="score-bar-fill"
                      style={{
                        width: `${Math.min(100, Math.max(0, dashboard?.health_score ?? 0))}%`,
                        backgroundColor: (dashboard?.health_score ?? 0) >= 80 ? '#16a34a' : (dashboard?.health_score ?? 0) >= 60 ? '#ca8a04' : '#ea580c',
                      }}
                    />
                  </div>
                </div>

                {/* Spectral Indices */}
                <div className="metric-grid-3">
                  <div className="metric-tile">
                    <div className="metric-tile-label">NDVI</div>
                    <div className="metric-tile-value">{dashboard?.ndvi_mean ?? '—'}</div>
                    <div className="metric-tile-sub">Vegetation vigor</div>
                  </div>
                  <div className="metric-tile">
                    <div className="metric-tile-label">NDMI</div>
                    <div className="metric-tile-value">{dashboard?.ndmi_mean ?? '—'}</div>
                    <div className="metric-tile-sub">Canopy moisture</div>
                  </div>
                  <div className="metric-tile">
                    <div className="metric-tile-label">NDRE</div>
                    <div className="metric-tile-value">{dashboard?.ndre_mean ?? '—'}</div>
                    <div className="metric-tile-sub">Chlorophyll proxy</div>
                  </div>
                </div>

                {/* Detected ML Anomaly Zones */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <strong style={{ fontSize: '0.88rem' }}>
                      Detected Sub-Field Zones ({hotspots.length})
                    </strong>
                    <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>Click a zone to inspect</span>
                  </div>

                  {hotspots.length === 0 ? (
                    <div className="banner-warn">
                      No scan results yet for this field. Click <strong>↻ Re-scan</strong> above.
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gap: '0.45rem', maxHeight: '190px', overflowY: 'auto' }}>
                      {hotspots.slice(0, 6).map((h) => (
                        <div
                          key={h.id}
                          className={`hotspot-row ${selectedHotspot?.id === h.id ? 'selected' : ''}`}
                          onClick={() => setSelectedHotspot(h)}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <strong style={{ fontSize: '0.85rem' }}>{h.likely_issue || 'Zone Anomaly'}</strong>
                            <span className={`badge badge-${h.severity}`}>
                              {h.severity} · {h.health_score}
                            </span>
                          </div>
                          {selectedHotspot?.id === h.id && (
                            <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
                              {h.explanation}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="banner-info" style={{ fontSize: '0.8rem' }}>
                  Satellite imagery reveals where vegetation or moisture stress exists, but cannot directly measure soil N, P, K, or pH.
                </div>

                <div style={{ display: 'flex', gap: '0.6rem' }}>
                  <button type="button" className="btn" onClick={() => { setDrawingMode(true); setStage(1); }}>
                    ← Edit Field
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ flex: 1 }}
                    onClick={() => setStage(3)}
                  >
                    Next: Enter Soil Sample &amp; Get Results →
                  </button>
                </div>
              </div>

              {historyObs.length > 0 && (
                <div className="card">
                  <h4 style={{ fontSize: '0.9rem', marginBottom: '0.5rem' }}>Spectral Index History ({historyObs.length} scan{historyObs.length > 1 ? 's' : ''})</h4>
                  <TimeSeriesChart data={historyObs} />
                </div>
              )}
            </div>
          </div>
        )}

        {/* ================= STAGE 3: SOIL SAMPLES + RESULTS + CROP RECOMMENDATION ================= */}
        {stage === 3 && (
          <div className="soil-workspace">
            {/* LEFT: SUBMIT SOIL SAMPLE */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <form onSubmit={handleSubmitSoil} className="card" style={{ display: 'grid', gap: '0.85rem' }}>
                <div>
                  <span className="badge badge-neutral">STEP 3 OF 3 · GROUND TRUTH SOIL INPUT</span>
                  <h2 style={{ marginTop: '0.4rem', fontSize: '1.25rem' }}>Submit Soil Sample</h2>
                  <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                    Enter soil test values for <strong>{dashboard?.field_name || 'your field'}</strong> to generate your soil verdict, fertilizer guidance, and crop recommendations.
                  </p>
                </div>

                {soilStatus && <div className="banner-info">{soilStatus}</div>}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem' }}>
                  <label className="field-label">
                    Nitrogen (N) Level
                    <select className="input" value={soilForm.nitrogen_level} onChange={(e) => setSoilForm({ ...soilForm, nitrogen_level: e.target.value })}>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                    </select>
                  </label>
                  <label className="field-label">
                    Nitrogen (mg/kg, optional)
                    <input className="input" type="number" step="0.1" placeholder="e.g. 14" value={soilForm.nitrogen_value} onChange={(e) => setSoilForm({ ...soilForm, nitrogen_value: e.target.value })} />
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem' }}>
                  <label className="field-label">
                    Phosphorus (P) Level
                    <select className="input" value={soilForm.phosphorus_level} onChange={(e) => setSoilForm({ ...soilForm, phosphorus_level: e.target.value })}>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                    </select>
                  </label>
                  <label className="field-label">
                    Phosphorus (mg/kg, optional)
                    <input className="input" type="number" step="0.1" placeholder="e.g. 30" value={soilForm.phosphorus_value} onChange={(e) => setSoilForm({ ...soilForm, phosphorus_value: e.target.value })} />
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.65rem' }}>
                  <label className="field-label">
                    Potassium (K) Level
                    <select className="input" value={soilForm.potassium_level} onChange={(e) => setSoilForm({ ...soilForm, potassium_level: e.target.value })}>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                    </select>
                  </label>
                  <label className="field-label">
                    Potassium (mg/kg, optional)
                    <input className="input" type="number" step="0.1" placeholder="e.g. 145" value={soilForm.potassium_value} onChange={(e) => setSoilForm({ ...soilForm, potassium_value: e.target.value })} />
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0.65rem' }}>
                  <label className="field-label">
                    Soil pH
                    <input className="input" type="number" step="0.1" min="3.5" max="9.5" value={soilForm.ph_value} onChange={(e) => setSoilForm({ ...soilForm, ph_value: parseFloat(e.target.value) })} />
                  </label>
                  <label className="field-label">
                    Moisture
                    <select className="input" value={soilForm.moisture_level} onChange={(e) => setSoilForm({ ...soilForm, moisture_level: e.target.value })}>
                      <option value="low">Low</option>
                      <option value="medium">Medium</option>
                      <option value="high">High</option>
                    </select>
                  </label>
                  <label className="field-label">
                    Texture
                    <select className="input" value={soilForm.soil_texture} onChange={(e) => setSoilForm({ ...soilForm, soil_texture: e.target.value })}>
                      {SOIL_TEXTURES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </label>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: '0.65rem' }}>
                  <label className="field-label">
                    Test Source
                    <select className="input" value={soilForm.source} onChange={(e) => setSoilForm({ ...soilForm, source: e.target.value })}>
                      <option value="lab">Lab Report</option>
                      <option value="sensor">Soil Sensor</option>
                      <option value="manual">Field Test Kit</option>
                    </select>
                  </label>
                  <label className="field-label">
                    Notes
                    <input className="input" type="text" placeholder="Optional sample notes..." value={soilForm.notes} onChange={(e) => setSoilForm({ ...soilForm, notes: e.target.value })} />
                  </label>
                </div>

                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.84rem', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={soilForm.is_validated} onChange={(e) => setSoilForm({ ...soilForm, is_validated: e.target.checked })} />
                  Verified lab/sensor measurement (unlocks exact treatment quantities)
                </label>

                <button type="submit" className="btn btn-primary" disabled={submittingSoil} style={{ padding: '0.7rem 1rem' }}>
                  {submittingSoil ? 'Analyzing Soil Sample...' : 'Submit Soil Sample & Compute Results'}
                </button>
              </form>

              {/* Submitted Soil Samples History */}
              {soilSamples.length > 0 && (
                <div className="card">
                  <h4 style={{ fontSize: '0.92rem', marginBottom: '0.6rem' }}>Saved Soil Samples ({soilSamples.length})</h4>
                  <div style={{ display: 'grid', gap: '0.5rem' }}>
                    {soilSamples.map((s) => (
                      <div
                        key={s.id}
                        style={{
                          padding: '0.65rem 0.75rem',
                          borderRadius: '8px',
                          border: activeSoilSample?.id === s.id ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                          background: 'var(--bg-page)',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.83rem', fontWeight: 600 }}>
                            {s.source.toUpperCase()} · {new Date(s.sample_date).toLocaleDateString()}
                          </span>
                          <span className={`badge ${s.is_validated ? 'badge-healthy' : 'badge-mild'}`}>
                            {s.is_validated ? 'Validated' : 'Unvalidated'}
                          </span>
                        </div>
                        <div className="mono" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                          N:{s.nitrogen_value ?? s.nitrogen_level} · P:{s.phosphorus_value ?? s.phosphorus_level} · K:{s.potassium_value ?? s.potassium_level} · pH {s.ph_value} ({s.soil_texture})
                        </div>
                        <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.45rem' }}>
                          <button type="button" className="btn btn-sm btn-primary" onClick={() => setActiveSoilSample(s)}>
                            View Result
                          </button>
                          <button type="button" className="btn btn-sm" onClick={() => handleToggleValidate(s)}>
                            {s.is_validated ? 'Unverify' : 'Verify'}
                          </button>
                          <button type="button" className="btn btn-sm" style={{ color: 'var(--red)' }} onClick={() => handleDeleteSample(s.id)}>
                            Delete
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* RIGHT: SOIL RESULT + CROP RECOMMENDATION + PDF REPORT */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* 1. SOIL SAMPLE RESULT */}
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                  <h3>Soil Sample Result</h3>
                  {activeSoilSample && (
                    <span className={`badge ${activeSoilSample.is_validated ? 'badge-healthy' : 'badge-mild'}`}>
                      {activeSoilSample.is_validated ? 'Verified Sample' : 'Needs Lab Verification'}
                    </span>
                  )}
                </div>

                {!activeSoilSample || !analysis ? (
                  <div className="banner-warn">
                    No soil sample submitted yet. Fill out the form on the left and click <strong>Submit Soil Sample &amp; Compute Results</strong>.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gap: '0.85rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.8rem', borderRadius: '8px', background: 'var(--bg-page)', border: '1px solid var(--border)' }}>
                      <div>
                        <div className="metric-tile-label">SOIL VERDICT</div>
                        <strong style={{ fontSize: '1rem' }}>{analysis.verdict}</strong>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div className="metric-tile-label">FERTILITY</div>
                        <span className="mono" style={{ fontSize: '1.25rem', fontWeight: 700, color: analysis.fertility_score >= 75 ? 'var(--green)' : 'var(--yellow)' }}>
                          {analysis.fertility_score}/100
                        </span>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
                      {(['nitrogen', 'phosphorus', 'potassium'] as const).map((k) => {
                        const item = analysis.nutrient_status[k];
                        return (
                          <div key={k} className="metric-tile" style={{ textAlign: 'center' }}>
                            <div className="metric-tile-label">{k}</div>
                            <div style={{ marginTop: '0.25rem' }}>
                              <span className={`badge ${levelBadge(item.level)}`}>{item.level.toUpperCase()}</span>
                            </div>
                            {item.is_measured && (
                              <div className="mono metric-tile-sub">{item.value} mg/kg</div>
                            )}
                          </div>
                        );
                      })}
                      <div className="metric-tile" style={{ textAlign: 'center' }}>
                        <div className="metric-tile-label">pH</div>
                        <div className="mono metric-tile-value">{activeSoilSample.ph_value ?? 7.0}</div>
                        <div className="metric-tile-sub">{analysis.ph_status}</div>
                      </div>
                    </div>

                    <div>
                      <strong style={{ fontSize: '0.86rem' }}>Recommended Soil Action</strong>
                      <ul style={{ marginTop: '0.35rem', paddingLeft: '1.2rem', fontSize: '0.86rem', color: 'var(--text-secondary)', display: 'grid', gap: '0.25rem' }}>
                        {analysis.actions.map((a, idx) => (
                          <li key={idx}>{a}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                )}
              </div>

              {/* 2. CROP RECOMMENDATION */}
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <div>
                    <h3>Crop Recommendation</h3>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      Ranked from your {cropRecs?.has_soil_sample ? 'submitted soil profile' : 'estimated soil profile'} + satellite moisture
                    </div>
                  </div>
                  <select
                    className="field-select"
                    value={seasonFilter}
                    onChange={(e) => handleSeasonChange(e.target.value)}
                    aria-label="Filter by season"
                  >
                    <option value="All">All Seasons</option>
                    <option value="Rabi">Rabi (Winter)</option>
                    <option value="Kharif">Kharif (Monsoon)</option>
                  </select>
                </div>

                {loadingCrops ? (
                  <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>Updating crop rankings...</p>
                ) : (
                  <div style={{ display: 'grid', gap: '0.65rem' }}>
                    {(cropRecs?.recommendations || []).slice(0, 5).map((c, idx) => (
                      <div
                        key={c.crop}
                        style={{
                          padding: '0.75rem',
                          borderRadius: '8px',
                          border: '1px solid var(--border)',
                          background: 'var(--bg-page)',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                          <div>
                            <strong>#{idx + 1} {c.crop}</strong>{' '}
                            <span style={{ fontSize: '0.76rem', color: 'var(--text-muted)' }}>
                              · {c.season}{c.nitrogen_fixer ? ' · N-Fixing' : ''}
                            </span>
                          </div>
                          <span className={`badge ${c.suitability_score >= 82 ? 'badge-healthy' : c.suitability_score >= 68 ? 'badge-mild' : 'badge-neutral'}`}>
                            <span className="mono">{c.suitability_score}%</span>&nbsp;Match
                          </span>
                        </div>
                        <div className="score-bar-track" style={{ marginTop: '0.45rem' }}>
                          <div
                            className="score-bar-fill"
                            style={{
                              width: `${c.suitability_score}%`,
                              backgroundColor: c.suitability_score >= 82 ? '#16a34a' : c.suitability_score >= 68 ? '#ca8a04' : '#64748b',
                            }}
                          />
                        </div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '0.4rem' }}>
                          {c.reasons.join(' · ')}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', paddingTop: '0.85rem', borderTop: '1px solid var(--border)', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <button type="button" className="btn" onClick={() => setStage(2)}>
                    ← Back to Satellite Scan
                  </button>
                  <button type="button" className="btn btn-primary" onClick={handleDownloadPdf} disabled={downloadingPdf}>
                    {downloadingPdf ? 'Generating PDF...' : 'Download Full Field PDF Report'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </>
  );
};

export default Workspace;
