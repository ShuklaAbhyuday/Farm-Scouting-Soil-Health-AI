import React, { useCallback, useEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';
import {
  ArrowRight,
  ArrowUpRight,
  Compass,
  Download,
  FileText,
  FlaskConical,
  Layers,
  MapPin,
  Play,
  Radar,
  RefreshCw,
  Satellite,
  Sparkles,
  Sprout,
  Trash2,
  Upload,
} from 'lucide-react';
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
  parseSoilReportPdf,
  updateSoilSample,
} from '../services/soilService';
import {
  computeCropRecommendations,
  getCropRecommendations,
  getFertilizerRecommendations,
} from '../services/recommendationService';
import { downloadReport, generateReport } from '../services/reportService';
import { CROP_TYPES, SOIL_TEXTURES } from '../utils/constants';
import {
  CropRecommendationResponse,
  DashboardSummary,
  FertilizerRecommendationResponse,
  Hotspot,
  SoilPdfParseResponse,
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
  const [endDate, setEndDate] = useState<string>(() => new Date().toISOString().slice(0, 10));

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
  const [soilInputMode, setSoilInputMode] = useState<'manual' | 'pdf'>('manual');
  const [uploadingPdf, setUploadingPdf] = useState<boolean>(false);
  const [pdfParseResult, setPdfParseResult] = useState<SoilPdfParseResponse | null>(null);
  const [pdfParseError, setPdfParseError] = useState<string | null>(null);

  const [cropRecs, setCropRecs] = useState<CropRecommendationResponse | null>(null);
  const [fertilizerPlan, setFertilizerPlan] = useState<FertilizerRecommendationResponse | null>(null);
  const [seasonFilter, setSeasonFilter] = useState<string>('All');
  const [loadingCrops, setLoadingCrops] = useState<boolean>(false);
  const [downloadingPdf, setDownloadingPdf] = useState<boolean>(false);
  const heroRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      gsap.from('.hero-meta', { y: 18, opacity: 0, duration: 0.7, delay: 0.08, ease: 'power3.out' });
      gsap.from('.hero-line-1', { y: 28, opacity: 0, duration: 0.85, delay: 0.18, ease: 'power3.out' });
      gsap.from('.hero-line-2', { y: 34, opacity: 0, duration: 0.95, delay: 0.3, ease: 'power3.out' });
      gsap.from('.hero-cta', { y: 18, opacity: 0, duration: 0.7, delay: 0.42, stagger: 0.1, ease: 'power3.out' });
    }, heroRef);
    return () => ctx.revert();
  }, []);

  const allFields = farms.flatMap((f) => f.fields || []);

  const loadFieldData = useCallback(async (fldId: number) => {
    try {
      const [fldRes, dashRes, hsRes, histRes, soilRes, cropRes, fertRes] = await Promise.all([
        getField(fldId).catch(() => null),
        getDashboard(fldId).catch(() => null),
        getHotspots(fldId).catch(() => ({ data: [] })),
        api.get(`/fields/${fldId}/history`).catch(() => ({ data: { observations: [] } })),
        getSoilSamples(fldId).catch(() => ({ data: [] })),
        getCropRecommendations(fldId).catch(() => null),
        getFertilizerRecommendations(fldId).catch(() => null),
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
      if (fertRes?.data) setFertilizerPlan(fertRes.data);
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

      const [samplesRes, cropRes, fertRes] = await Promise.all([
        getSoilSamples(selectedFieldId),
        computeCropRecommendations(selectedFieldId, {
          season: seasonFilter,
          use_latest_sample: true,
        }),
        getFertilizerRecommendations(selectedFieldId, createdSample.id),
      ]);
      setSoilSamples(samplesRes.data || []);
      setCropRecs(cropRes.data);
      setFertilizerPlan(fertRes.data);
    } catch (err) {
      console.error('Soil submission failed:', err);
      setSoilStatus('Failed to save soil sample. Check backend connection.');
    } finally {
      setSubmittingSoil(false);
    }
  };

  const processSoilPdfFile = async (file: File) => {
    setUploadingPdf(true);
    setPdfParseError(null);
    setPdfParseResult(null);
    setSoilStatus(null);
    try {
      const res = await parseSoilReportPdf(file);
      const data = res.data;
      setPdfParseResult(data);
      if (data.extraction_success && data.parsed_fields) {
        const p = data.parsed_fields;
        const nextForm = {
          ...soilForm,
          nitrogen_level: p.nitrogen_level || soilForm.nitrogen_level,
          nitrogen_value: p.nitrogen_value != null ? String(p.nitrogen_value) : '',
          phosphorus_level: p.phosphorus_level || soilForm.phosphorus_level,
          phosphorus_value: p.phosphorus_value != null ? String(p.phosphorus_value) : '',
          potassium_level: p.potassium_level || soilForm.potassium_level,
          potassium_value: p.potassium_value != null ? String(p.potassium_value) : '',
          ph_value: p.ph_value != null ? p.ph_value : soilForm.ph_value,
          moisture_level: p.moisture_level || soilForm.moisture_level,
          soil_texture: p.soil_texture || soilForm.soil_texture,
          source: p.source || 'lab',
          is_validated: p.is_validated ?? true,
          notes: `Extracted from PDF: ${data.filename || file.name}`,
        };
        setSoilForm(nextForm);

        // Immediately save extracted sample & compute Soil Result, Crop Recommendation, and Fertilizer Plan
        setSubmittingSoil(true);
        const createdRes = await createSoilSample(selectedFieldId, {
          latitude: 23.0775,
          longitude: 76.8513,
          nitrogen_level: nextForm.nitrogen_level,
          nitrogen_value: nextForm.nitrogen_value ? parseFloat(nextForm.nitrogen_value) : undefined,
          phosphorus_level: nextForm.phosphorus_level,
          phosphorus_value: nextForm.phosphorus_value ? parseFloat(nextForm.phosphorus_value) : undefined,
          potassium_level: nextForm.potassium_level,
          potassium_value: nextForm.potassium_value ? parseFloat(nextForm.potassium_value) : undefined,
          ph_value: nextForm.ph_value,
          moisture_level: nextForm.moisture_level,
          soil_texture: nextForm.soil_texture,
          sample_date: new Date().toISOString(),
          source: nextForm.source,
          is_validated: nextForm.is_validated,
          notes: nextForm.notes,
        });
        const createdSample: SoilSample = createdRes.data;
        setActiveSoilSample(createdSample);

        const [samplesRes, cropRes, fertRes] = await Promise.all([
          getSoilSamples(selectedFieldId),
          computeCropRecommendations(selectedFieldId, {
            season: seasonFilter,
            use_latest_sample: true,
          }),
          getFertilizerRecommendations(selectedFieldId, createdSample.id),
        ]);
        setSoilSamples(samplesRes.data || []);
        setCropRecs(cropRes.data);
        setFertilizerPlan(fertRes.data);
        setSoilStatus(`Processed "${data.filename || file.name}" and updated soil, crop, and fertilizer results.`);
      } else {
        setPdfParseError(
          data.warning || 'Could not detect soil values automatically from this PDF. Check preview below or enter manually.'
        );
      }
    } catch (err: any) {
      setPdfParseError(err?.response?.data?.detail || 'Failed to upload or process soil PDF.');
    } finally {
      setUploadingPdf(false);
      setSubmittingSoil(false);
    }
  };

  const handleUploadSoilPdf = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (file) await processSoilPdfFile(file);
  };

  const handleSelectSample = async (s: SoilSample) => {
    setActiveSoilSample(s);
    try {
      const fertRes = await getFertilizerRecommendations(selectedFieldId, s.id);
      setFertilizerPlan(fertRes.data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleToggleValidate = async (s: SoilSample) => {
    try {
      const res = await updateSoilSample(s.id, { is_validated: !s.is_validated });
      if (activeSoilSample?.id === s.id) setActiveSoilSample(res.data);
      const [samplesRes, cropRes, fertRes] = await Promise.all([
        getSoilSamples(selectedFieldId),
        computeCropRecommendations(selectedFieldId, { season: seasonFilter, use_latest_sample: true }),
        getFertilizerRecommendations(selectedFieldId, activeSoilSample?.id ?? s.id),
      ]);
      setSoilSamples(samplesRes.data || []);
      setCropRecs(cropRes.data);
      setFertilizerPlan(fertRes.data);
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
      const [cropRes, fertRes] = await Promise.all([
        getCropRecommendations(selectedFieldId),
        getFertilizerRecommendations(selectedFieldId),
      ]);
      setCropRecs(cropRes.data);
      setFertilizerPlan(fertRes.data);
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
      a.download = `croppulse_field_${selectedFieldId}_report.pdf`;
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
            <Sprout size={19} strokeWidth={2.3} />
          </div>
          <span>CropPulse</span>
        </div>

        <nav className="stepper-rail" aria-label="Workflow steps">
          <button
            type="button"
            className={`step-pill ${stage === 1 ? 'active' : ''}`}
            onClick={() => setStage(1)}
          >
            <MapPin size={14} strokeWidth={2.3} />
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
            <Satellite size={14} strokeWidth={2.3} />
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
            <FlaskConical size={14} strokeWidth={2.3} />
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
              className="btn btn-sm btn-topbar-ghost"
              onClick={handleDeleteCurrentField}
              title="Delete currently selected field"
            >
              <Trash2 size={13} strokeWidth={2.2} /> Delete
            </button>
          )}
          <button type="button" className="btn-gold-pill magnetic-btn" onClick={handleStartNewField}>
            + Draw New Field <ArrowUpRight size={15} strokeWidth={2.4} />
          </button>
        </div>
      </header>

      {/* EDITORIAL AERIAL HERO BANNER */}
      <section ref={heroRef} className="hero-banner" aria-label="CropPulse Agricultural Overview">
        <div className="hero-particles" aria-hidden="true">
          {[0, 1, 2, 3, 4].map((n) => (
            <Sprout
              key={n}
              size={14 + (n % 2) * 3}
              className="hero-particle"
              style={{
                left: `${12 + n * 20}%`,
                animationDuration: `${4.6 + n * 0.7}s`,
                animationDelay: `${n * 0.8}s`,
              }}
            />
          ))}
        </div>
        <div className="hero-inner">
          <div className="hero-meta-chip hero-meta">
            <span className="ring-pulse" />
            <span>Sentinel-2 Optical · Sentinel-1 SAR · Lab Soil Verified</span>
          </div>
          <h1 className="hero-title">
            <span className="hero-line-1" style={{ display: 'block' }}>Precision satellite &amp;</span>
            <span className="hero-line-2 serif-italic" style={{ display: 'block' }}>smart field scouting</span>
          </h1>
          <p className="hero-sub hero-meta">
            Dual-sensor satellite monitoring grounded with verified laboratory soil reports, crop suitability, and field-scaled fertilizer schedules.
          </p>
          <div className="hero-actions">
            <button
              type="button"
              className="hero-btn-white hero-cta magnetic-btn"
              onClick={() => {
                handleStartNewField();
                document.getElementById('workspace-stage')?.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              Outline Field <ArrowRight size={15} strokeWidth={2.4} />
            </button>
            <button
              type="button"
              className="hero-btn-secondary hero-cta"
              onClick={() => {
                setDrawingMode(false);
                setStage(2);
                document.getElementById('workspace-stage')?.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              <span className="hero-lime-circle" aria-hidden="true">
                <Play size={13} fill="currentColor" strokeWidth={2} />
              </span>
              Explore Satellite Insights
            </button>
          </div>
        </div>
      </section>

      {/* SUBTLE SCIENTIFIC TELEMETRY STRIP */}
      <div className="telemetry-strip grid-bg">
        <div className="telemetry-strip-inner">
          <div className="telemetry-item">
            <Layers size={14} strokeWidth={2.3} color="var(--accent)" />
            <span>20 m Harmonized Optical Composites (NDVI · NDMI · NDRE)</span>
          </div>
          <div className="telemetry-item">
            <Radar size={14} strokeWidth={2.3} color="var(--accent)" />
            <span>10 m Linear-Power SAR Backscatter &amp; Orbit Filtering</span>
          </div>
          <div className="telemetry-item">
            <Compass size={14} strokeWidth={2.3} color="var(--accent)" />
            <span>Active Field: <strong>{dashboard?.field_name || 'Select or draw plot'}</strong></span>
          </div>
        </div>
      </div>

      <main id="workspace-stage" className="main-stage">
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
              <div className="card-header-flex">
                <div className="icon-box">
                  <MapPin size={19} strokeWidth={2.3} />
                </div>
                <div>
                  <div className="eyebrow-mono">STEP 1 OF 3 · FIELD BOUNDARY</div>
                  <h2 style={{ marginTop: '0.2rem', fontSize: '1.28rem' }}>Outline your field on the map</h2>
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.86rem', marginTop: '0.2rem' }}>
                    Search your location on the map, click at least 3 corners around your plot, and click <strong>Save &amp; Analyze</strong> below (no extra click needed).
                  </p>
                </div>
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.6rem' }}>
                  <div className="card-header-flex">
                    <div className="icon-box">
                      <Satellite size={19} strokeWidth={2.3} />
                    </div>
                    <div>
                      <div className="eyebrow-mono">STEP 2 OF 3 · SATELLITE COMPONENT</div>
                      <h2 style={{ marginTop: '0.18rem', fontSize: '1.25rem' }}>
                        {dashboard?.field_name || 'Field Satellite Scan'}
                      </h2>
                      <div style={{ fontSize: '0.79rem', color: 'var(--text-secondary)' }}>
                        {dashboard?.latest_observation_date
                          ? `Latest optical: ${new Date(dashboard.latest_observation_date).toLocaleDateString()} (${dashboard?.optical_timestamp_precision ?? 'exact'}) · ${dashboard.area_ha ?? '—'} ha`
                          : 'No satellite observation recorded yet'}
                        {dashboard?.optical_quality?.valid_pixel_pct != null && (
                          <> · Clear pixels: {dashboard.optical_quality.valid_pixel_pct}%</>
                        )}
                      </div>
                    </div>
                  </div>
                  <button type="button" className="btn btn-sm" onClick={handleRescanOnly} disabled={scanning}>
                    <RefreshCw size={13} strokeWidth={2.3} /> {scanning ? 'Scanning...' : 'Re-scan'}
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
                        backgroundColor: (dashboard?.health_score ?? 0) >= 80 ? 'var(--green)' : (dashboard?.health_score ?? 0) >= 60 ? 'var(--yellow)' : 'var(--orange)',
                      }}
                    />
                  </div>
                </div>

                {/* Spectral Optical Indices (Sentinel-2) */}
                <div>
                  <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                    SENTINEL-2 OPTICAL PROXIES (10m–20m)
                  </div>
                  <div className="metric-grid-3">
                    <div className="metric-tile">
                      <div className="metric-tile-label">NDVI</div>
                      <div className="metric-tile-value">{dashboard?.ndvi_mean ?? '—'}</div>
                      <div className="metric-tile-sub">Vegetation vigor</div>
                    </div>
                    <div className="metric-tile">
                      <div className="metric-tile-label">EVI</div>
                      <div className="metric-tile-value">{dashboard?.evi_mean ?? '—'}</div>
                      <div className="metric-tile-sub">Dense canopy</div>
                    </div>
                    <div className="metric-tile">
                      <div className="metric-tile-label">SAVI</div>
                      <div className="metric-tile-value">{dashboard?.savi_mean ?? '—'}</div>
                      <div className="metric-tile-sub">Soil-adjusted</div>
                    </div>
                    <div className="metric-tile">
                      <div className="metric-tile-label">GNDVI</div>
                      <div className="metric-tile-value">{dashboard?.gndvi_mean ?? '—'}</div>
                      <div className="metric-tile-sub">Green density</div>
                    </div>
                    <div className="metric-tile">
                      <div className="metric-tile-label">NDMI</div>
                      <div className="metric-tile-value">{dashboard?.ndmi_mean ?? '—'}</div>
                      <div className="metric-tile-sub">Leaf moisture</div>
                    </div>
                    <div className="metric-tile">
                      <div className="metric-tile-label">NDRE</div>
                      <div className="metric-tile-value">{dashboard?.ndre_mean ?? '—'}</div>
                      <div className="metric-tile-sub">Chlorophyll proxy</div>
                    </div>
                  </div>
                </div>

                {/* Sentinel-1 SAR Radar (Cloud-Independent Moisture & Structure) */}
                <div style={{ padding: '0.75rem', borderRadius: '8px', background: 'var(--bg-page)', border: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                      SENTINEL-1 SAR RADAR ({dashboard?.radar_timestamp_precision === 'approximate' ? 'APPROX. MIGRATED DATE' : 'CLOUD-PROOF'})
                    </span>
                    <span className="badge badge-neutral">
                      {dashboard?.surface_wetness_status || 'Radar Moisture Proxy'}
                    </span>
                  </div>
                  {(dashboard?.radar_observation_date || dashboard?.radar_quality?.orbit_pass) && (
                    <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', marginBottom: '0.45rem' }}>
                      {dashboard?.radar_observation_date && `Radar date: ${new Date(dashboard.radar_observation_date).toLocaleDateString()} (${dashboard?.radar_timestamp_precision ?? 'exact'})`}
                      {dashboard?.radar_quality?.orbit_pass && ` · ${dashboard.radar_quality.orbit_pass} orbit ${dashboard.radar_quality.relative_orbit ?? ''}`}
                      {dashboard?.radar_quality?.incidence_angle_deg != null && ` · ${dashboard.radar_quality.incidence_angle_deg}° inc.`}
                    </div>
                  )}
                  <div className="metric-grid-3">
                    <div className="metric-tile" style={{ background: 'var(--bg-surface)' }}>
                      <div className="metric-tile-label">S1 VV (dB)</div>
                      <div className="metric-tile-value">{dashboard?.s1_vv ?? '—'}</div>
                      <div className="metric-tile-sub">Surface wetness</div>
                    </div>
                    <div className="metric-tile" style={{ background: 'var(--bg-surface)' }}>
                      <div className="metric-tile-label">S1 VH (dB)</div>
                      <div className="metric-tile-value">{dashboard?.s1_vh ?? '—'}</div>
                      <div className="metric-tile-sub">Canopy structure</div>
                    </div>
                    <div className="metric-tile" style={{ background: 'var(--bg-surface)' }}>
                      <div className="metric-tile-label">Radar RVI</div>
                      <div className="metric-tile-value">{dashboard?.s1_rvi ?? '—'}</div>
                      <div className="metric-tile-sub">0–1 biomass index</div>
                    </div>
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
                <div className="card" style={{ display: 'grid', gap: '0.65rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div>
                      <h4 style={{ fontSize: '0.92rem' }}>
                        Crop Growth &amp; Phenology ({historyObs.length} dates)
                      </h4>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        {dashboard?.phenology?.land_status || 'Seasonal curve'}
                        {dashboard?.phenology?.peak_ndvi != null && (
                          <> · Season peak NDVI <span className="mono">{dashboard.phenology.peak_ndvi}</span> ({dashboard.phenology.peak_date})</>
                        )}
                        {dashboard?.phenology?.ndvi_change_per_week != null && (
                          <> · {dashboard.phenology.ndvi_change_per_week >= 0 ? '+' : ''}{dashboard.phenology.ndvi_change_per_week}/wk</>
                        )}
                      </div>
                    </div>
                    {dashboard?.phenology?.stage && (
                      <span className="badge badge-healthy">{dashboard.phenology.stage}</span>
                    )}
                  </div>
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
                <div className="card-header-flex">
                  <div className="icon-box-gold">
                    <FlaskConical size={19} strokeWidth={2.3} />
                  </div>
                  <div>
                    <div className="eyebrow-mono">STEP 3 OF 3 · GROUND TRUTH SOIL INPUT</div>
                    <h2 style={{ marginTop: '0.18rem', fontSize: '1.25rem' }}>Submit Soil Sample</h2>
                    <p style={{ fontSize: '0.83rem', color: 'var(--text-secondary)', marginTop: '0.18rem' }}>
                      Choose manual entry or upload your soil lab PDF for <strong>{dashboard?.field_name || 'your field'}</strong> to unlock soil results, crop rankings, and fertilizer guidance.
                    </p>
                  </div>
                </div>

                <div className="mode-toggle-rail" role="tablist" aria-label="Soil input method">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={soilInputMode === 'manual'}
                    className={`mode-toggle-btn ${soilInputMode === 'manual' ? 'active' : ''}`}
                    onClick={() => setSoilInputMode('manual')}
                  >
                    <FileText size={14} strokeWidth={2.2} /> Manual Soil Entry
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={soilInputMode === 'pdf'}
                    className={`mode-toggle-btn ${soilInputMode === 'pdf' ? 'active' : ''}`}
                    onClick={() => setSoilInputMode('pdf')}
                  >
                    <Upload size={14} strokeWidth={2.2} /> Upload Soil Report PDF
                  </button>
                </div>

                {soilStatus && <div className="banner-info">{soilStatus}</div>}

                {soilInputMode === 'pdf' && (
                  <div style={{ display: 'grid', gap: '0.75rem' }}>
                    <div
                      className="pdf-dropzone"
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault();
                        const f = e.dataTransfer.files?.[0];
                        if (f) processSoilPdfFile(f);
                      }}
                    >
                      <strong style={{ fontSize: '0.9rem' }}>Drop or Upload Lab Soil Report (.pdf)</strong>
                      <p style={{ fontSize: '0.79rem', color: 'var(--text-secondary)', maxWidth: '320px' }}>
                        Extracts N, P, K (mg/kg or kg/ha), pH, moisture, and texture and immediately computes your soil, crop, and fertilizer results.
                      </p>
                      <label className="btn btn-primary btn-sm magnetic-btn" style={{ cursor: 'pointer' }}>
                        {uploadingPdf || submittingSoil ? 'Processing PDF...' : 'Choose Soil PDF File'}
                        <input
                          type="file"
                          accept=".pdf,application/pdf"
                          onChange={handleUploadSoilPdf}
                          disabled={uploadingPdf || submittingSoil}
                          style={{ display: 'none' }}
                        />
                      </label>
                    </div>

                    {pdfParseError && (
                      <div className="banner-err" style={{ display: 'grid', gap: '0.45rem' }}>
                        <div>{pdfParseError}</div>
                        {pdfParseResult?.text_preview && (
                          <div className="mono" style={{ fontSize: '0.72rem', background: 'rgba(255,255,255,0.7)', padding: '0.45rem', borderRadius: '6px', maxHeight: '90px', overflowY: 'auto' }}>
                            {pdfParseResult.text_preview}
                          </div>
                        )}
                        <div>
                          <button type="button" className="btn btn-sm" onClick={() => setSoilInputMode('manual')}>
                            Enter Values Manually
                          </button>
                        </div>
                      </div>
                    )}

                    {pdfParseResult && pdfParseResult.extraction_success && (
                      <div className="banner-info" style={{ display: 'grid', gap: '0.45rem' }}>
                        <div>
                          <strong>Processed from {pdfParseResult.filename || 'PDF'}:</strong>{' '}
                          <span className="mono">
                            N: {pdfParseResult.parsed_fields.nitrogen_value ?? pdfParseResult.parsed_fields.nitrogen_level ?? '—'} ·
                            P: {pdfParseResult.parsed_fields.phosphorus_value ?? pdfParseResult.parsed_fields.phosphorus_level ?? '—'} ·
                            K: {pdfParseResult.parsed_fields.potassium_value ?? pdfParseResult.parsed_fields.potassium_level ?? '—'} ·
                            pH: {pdfParseResult.parsed_fields.ph_value ?? '—'}
                            {pdfParseResult.parsed_fields.soil_texture ? ` · ${pdfParseResult.parsed_fields.soil_texture}` : ''}
                          </span>
                        </div>
                        {pdfParseResult.unit_conversions.length > 0 && (
                          <div style={{ fontSize: '0.76rem' }}>
                            {pdfParseResult.unit_conversions.join(' · ')}
                          </div>
                        )}
                        {pdfParseResult.missing_keys.length > 0 && (
                          <div style={{ fontSize: '0.76rem', color: '#7d5406' }}>
                            Not detected in PDF (retained form defaults): {pdfParseResult.missing_keys.join(', ')}
                          </div>
                        )}
                        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.2rem' }}>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => setSoilInputMode('manual')}
                          >
                            Edit / Adjust Extracted Values
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {soilInputMode === 'manual' && (
                <>

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
                </>
                )}
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
                          <button type="button" className="btn btn-sm btn-primary" onClick={() => handleSelectSample(s)}>
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
                              backgroundColor: c.suitability_score >= 82 ? 'var(--green)' : c.suitability_score >= 68 ? 'var(--yellow)' : 'var(--text-muted)',
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
                  <button type="button" className="btn btn-primary magnetic-btn" onClick={handleDownloadPdf} disabled={downloadingPdf}>
                    <Download size={14} strokeWidth={2.2} /> {downloadingPdf ? 'Generating PDF...' : 'Download Full Field PDF Report'}
                  </button>
                </div>
              </div>

              {/* 3. FERTILIZER RECOMMENDATION SYSTEM (BELOW CROP RECOMMENDATION) */}
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.8rem' }}>
                  <div className="card-header-flex">
                    <div className="icon-box">
                      <Sparkles size={18} strokeWidth={2.3} />
                    </div>
                    <div>
                      <h3>Fertilizer Recommendation System</h3>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {fertilizerPlan
                          ? `${fertilizerPlan.crop_type} · ${fertilizerPlan.area_ha} ha (${fertilizerPlan.soil_texture || 'Loamy'})`
                          : 'Nutrient application schedule scaled to your field'}
                      </div>
                    </div>
                  </div>
                  {fertilizerPlan && (
                    <span className={`badge ${fertilizerPlan.can_prescribe_dosage ? 'badge-healthy' : fertilizerPlan.status === 'unvalidated_estimate' ? 'badge-mild' : 'badge-neutral'}`}>
                      {fertilizerPlan.can_prescribe_dosage
                        ? 'Lab-Verified Dosage'
                        : fertilizerPlan.status === 'unvalidated_estimate'
                          ? 'Unvalidated Estimate'
                          : 'Soil Test Required'}
                    </span>
                  )}
                </div>

                {!fertilizerPlan || fertilizerPlan.status === 'soil_sample_required' ? (
                  <div className="banner-warn">
                    {fertilizerPlan?.summary || 'Submit manual soil inputs or upload a soil lab PDF on the left to generate NPK and pH fertilizer recommendations.'}
                  </div>
                ) : (
                  <div style={{ display: 'grid', gap: '0.8rem' }}>
                    <div className={fertilizerPlan.can_prescribe_dosage ? 'banner-info' : 'banner-warn'}>
                      {fertilizerPlan.summary}
                    </div>

                    <div style={{ display: 'grid', gap: '0.6rem' }}>
                      {fertilizerPlan.recommendations.map((item) => (
                        <div
                          key={item.nutrient}
                          className={`fert-nutrient-card priority-${item.priority}`}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <div>
                              <strong>{item.nutrient}</strong>{' '}
                              <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                · {item.product}
                              </span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                              <span className={`badge ${levelBadge(item.soil_level)}`}>
                                Soil {item.soil_level.toUpperCase()}
                                {item.measured_mg_kg != null ? ` (${item.measured_mg_kg} mg/kg)` : ''}
                              </span>
                              {item.rate_kg_ha != null ? (
                                <span className="badge badge-healthy mono">
                                  {item.rate_kg_ha > 0 ? `${item.rate_kg_ha} kg/ha` : '0 kg/ha (Skip)'}
                                </span>
                              ) : (
                                <span className="badge badge-neutral">Verify sample for kg/ha</span>
                              )}
                            </div>
                          </div>

                          <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                            {item.action}
                            {item.total_field_kg != null && item.total_field_kg > 0 && (
                              <span className="mono" style={{ fontWeight: 500, color: 'var(--accent)', marginLeft: '0.45rem' }}>
                                (Total for field: {item.total_field_kg} kg)
                              </span>
                            )}
                          </div>

                          <div style={{ fontSize: '0.79rem', color: 'var(--text-secondary)' }}>
                            <strong>Schedule:</strong> {item.timing}
                          </div>
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                            {item.reasoning}
                          </div>
                        </div>
                      ))}
                    </div>

                    {fertilizerPlan.ph_amendment && (
                      <div className="banner-warn" style={{ display: 'grid', gap: '0.25rem' }}>
                        <strong>
                          {fertilizerPlan.ph_amendment.title}
                          {fertilizerPlan.ph_amendment.rate_kg_ha != null && (
                            <span className="mono"> · {fertilizerPlan.ph_amendment.rate_kg_ha} kg/ha ({fertilizerPlan.ph_amendment.total_field_kg} kg total)</span>
                          )}
                        </strong>
                        <span style={{ fontSize: '0.8rem' }}>
                          <strong>Timing:</strong> {fertilizerPlan.ph_amendment.timing} — {fertilizerPlan.ph_amendment.reasoning}
                        </span>
                      </div>
                    )}

                    {fertilizerPlan.total_field_materials.length > 0 && (
                      <div style={{ padding: '0.75rem', borderRadius: '10px', background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
                        <div className="metric-tile-label" style={{ marginBottom: '0.4rem' }}>
                          TOTAL FIELD MATERIAL ESTIMATE ({fertilizerPlan.area_ha} HA)
                        </div>
                        <div style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap' }}>
                          {fertilizerPlan.total_field_materials.map((m) => (
                            <div key={m.product} className="badge badge-neutral mono" style={{ background: 'var(--bg-surface)', color: 'var(--text-primary)', border: '1px solid var(--border)' }}>
                              {m.product.split(' ')[0]}: {m.total_kg} kg ({m.bags_50kg} × 50kg bags)
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                      {fertilizerPlan.application_tips.join(' ')} {fertilizerPlan.satellite_context.join(' ')} {fertilizerPlan.limitation}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </>
  );
};

export default Workspace;
