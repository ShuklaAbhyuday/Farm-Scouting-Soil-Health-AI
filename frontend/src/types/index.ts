export interface User {
  id: number;
  email: string;
  name: string;
  created_at: string;
}

export interface Farm {
  id: number;
  user_id: number;
  name: string;
  location_description?: string;
  center_lat: number;
  center_lng: number;
  total_area_ha?: number;
  created_at: string;
  fields?: Field[];
}

export interface FarmCreate {
  name: string;
  location_description?: string;
  center_lat: number;
  center_lng: number;
  total_area_ha?: number;
}

export interface Field {
  id: number;
  farm_id: number;
  name: string;
  boundary_geojson: GeoJSON.Polygon | GeoJSON.MultiPolygon;
  crop_type?: string;
  growth_stage?: string;
  area_ha?: number;
  created_at: string;
}

export interface FieldCreate {
  name: string;
  boundary_geojson: any;
  crop_type?: string;
  growth_stage?: string;
}

export interface SatelliteObservation {
  id: number;
  field_id: number;
  source: string;
  collection_id: string;
  image_id: string;
  acquisition_date: string;
  cloud_cover_pct: number;
  status: 'pending' | 'completed' | 'failed';
  processed_at?: string;
  created_at: string;
  indices?: IndexResult[];
}

export interface IndexResult {
  id: number;
  observation_id: number;
  index_type: 'ndvi' | 'ndmi' | 'ndre';
  mean_value: number;
  min_value: number;
  max_value: number;
  std_value: number;
  statistics?: Record<string, any>;
  created_at: string;
}

export interface AnalysisRequest {
  start_date: string;
  end_date: string;
  cloud_max?: number;
}

export interface Hotspot {
  id: number;
  field_id: number;
  observation_id: number;
  geometry_geojson: any;
  center_lat: number;
  center_lng: number;
  area_ha: number;
  severity: 'healthy' | 'mild' | 'moderate' | 'severe';
  health_score: number;
  ndvi_value: number;
  ndmi_value: number;
  ndre_value: number;
  ndvi_deviation: number;
  ndmi_deviation: number;
  ndre_deviation: number;
  likely_issue: string;
  explanation: string;
  detection_method: 'baseline_heuristic' | 'isolation_forest';
  persistence_count: number;
  first_detected: string;
  created_at: string;
}

export interface CropRecommendationItem {
  crop: string;
  emoji: string;
  season: string;
  suitability_score: number;
  match_label: string;
  nitrogen_fixer: boolean;
  reasons: string[];
  care_notes: string;
}

export interface CropRecommendationResponse {
  field_id: number;
  field_name: string;
  current_crop?: string;
  source_mode: 'validated_soil_sample' | 'unvalidated_soil_sample' | 'manual_or_satellite_estimate';
  has_soil_sample: boolean;
  is_validated: boolean;
  inputs_used: {
    nitrogen_value?: number | null;
    nitrogen_level?: string;
    phosphorus_value?: number | null;
    phosphorus_level?: string;
    potassium_value?: number | null;
    potassium_level?: string;
    ph_value: number;
    moisture_level: string;
    soil_texture: string;
    season: string;
    ndmi_mean?: number | null;
  };
  recommendations: CropRecommendationItem[];
}

export interface SoilSampleAnalysis {
  fertility_score: number;
  verdict: string;
  ph_status: string;
  nutrient_status: {
    nitrogen: { level: string; value: number; is_measured: boolean };
    phosphorus: { level: string; value: number; is_measured: boolean };
    potassium: { level: string; value: number; is_measured: boolean };
  };
  actions: string[];
  top_crops: CropRecommendationItem[];
}

export interface SoilSample {
  id: number;
  field_id: number;
  hotspot_id?: number;
  latitude: number;
  longitude: number;
  nitrogen_level?: 'low' | 'medium' | 'high';
  nitrogen_value?: number;
  phosphorus_level?: 'low' | 'medium' | 'high';
  phosphorus_value?: number;
  potassium_level?: 'low' | 'medium' | 'high';
  potassium_value?: number;
  ph_value?: number;
  moisture_level?: 'low' | 'medium' | 'high';
  moisture_value?: number;
  soil_texture?: string;
  sample_date: string;
  source: 'manual' | 'lab' | 'sensor';
  is_validated: boolean;
  notes?: string;
  created_at: string;
  analysis?: SoilSampleAnalysis;
}

export interface SoilSampleCreate {
  hotspot_id?: number;
  latitude: number;
  longitude: number;
  nitrogen_level?: string;
  nitrogen_value?: number;
  phosphorus_level?: string;
  phosphorus_value?: number;
  potassium_level?: string;
  potassium_value?: number;
  ph_value?: number;
  moisture_level?: string;
  moisture_value?: number;
  soil_texture?: string;
  sample_date: string;
  source: string;
  is_validated?: boolean;
  notes?: string;
}

export interface Recommendation {
  id: number;
  field_id: number;
  hotspot_id?: number;
  category: 'fertilizer' | 'irrigation' | 'crop' | 'soil';
  title: string;
  description: string;
  reasoning: string;
  satellite_evidence?: Record<string, any>;
  ground_truth_evidence?: Record<string, any>;
  confidence: 'low' | 'medium' | 'high';
  priority: 'low' | 'medium' | 'high' | 'critical';
  requires_ground_truth: boolean;
  created_at: string;
}

export interface DashboardSummary {
  field_name: string;
  crop_type?: string;
  growth_stage?: string;
  area_ha?: number;
  latest_observation_date?: string;
  optical_timestamp_precision?: 'exact' | 'approximate' | 'composite_window' | 'simulated' | 'unavailable';
  radar_observation_date?: string | null;
  radar_timestamp_precision?: 'exact' | 'approximate' | 'composite_window' | 'simulated' | 'unavailable';
  is_demo?: boolean | null;
  optical_source?: string | null;
  radar_source?: string | null;
  optical_quality?: {
    available: boolean;
    source?: string | null;
    collection_id?: string | null;
    image_id?: string | null;
    acquisition_date?: string | null;
    timestamp_precision: string;
    timestamp_note?: string;
    cloud_cover_pct?: number | null;
    valid_pixel_pct?: number | null;
    observation_count?: number | null;
    composite_method?: string | null;
    spatial_scale_m?: number | null;
  };
  radar_quality?: {
    available: boolean;
    source?: string | null;
    collection_id?: string | null;
    image_id?: string | null;
    acquisition_date?: string | null;
    timestamp_precision: string;
    timestamp_note?: string;
    orbit_pass?: string | null;
    relative_orbit?: number | null;
    incidence_angle_deg?: number | null;
    baseline_vv_db?: number | null;
    delta_vv_db?: number | null;
    baseline_obs_count?: number;
    orbit_consistent?: boolean;
    averaging_domain?: string | null;
    rvi_formula?: string | null;
    rvi_expected_range?: string | null;
    spatial_scale_m?: number | null;
    limitation?: string;
  };
  radar_wetness_assessment?: {
    status: string;
    method: string;
    delta_vv_db?: number | null;
    baseline_obs_count: number;
    orbit_consistent: boolean;
    limitation: string;
  };
  scientific_provenance?: Record<string, any>;
  overall_health: string;
  health_score: number;
  total_hotspots: number;
  critical_hotspots: number;
  ndvi_mean?: number | null;
  evi_mean?: number | null;
  savi_mean?: number | null;
  gndvi_mean?: number | null;
  ndmi_mean?: number | null;
  ndre_mean?: number | null;
  s1_vv?: number | null;
  s1_vh?: number | null;
  s1_rvi?: number | null;
  surface_wetness_status?: string;
  phenology?: {
    stage: string;
    stage_confidence?: string;
    land_status: string;
    peak_ndvi?: number | null;
    peak_date?: string | null;
    latest_date?: string | null;
    season_start_date?: string | null;
    season_span_days?: number;
    observation_count: number;
    total_archive_observations?: number;
    season_count?: number;
    previous_seasons?: Array<Record<string, any>>;
    ndvi_change?: number | null;
    ndvi_change_per_week?: number | null;
    elapsed_days_since_prev?: number | null;
    consecutive_declines?: number;
    crop_calendar_context?: Record<string, any>;
    limitation?: string;
  };
  ndvi_trend?: 'improving' | 'stable' | 'declining';
  recent_recommendations: Recommendation[];
  highest_priority_hotspot?: Hotspot;
}

export interface HistoricalData {
  dates: string[];
  ndvi: Array<number | null>;
  evi?: Array<number | null>;
  savi?: Array<number | null>;
  gndvi?: Array<number | null>;
  ndmi: Array<number | null>;
  ndre: Array<number | null>;
  health_scores: Array<number | null>;
  observations?: Array<Record<string, any>>;
  missing_gap_periods?: Array<Record<string, any>>;
}

export type SeverityLevel = 'healthy' | 'mild' | 'moderate' | 'severe';

export interface SoilPdfParseResponse {
  filename?: string;
  page_count: number;
  extraction_success: boolean;
  detected_keys: string[];
  missing_keys: string[];
  unit_conversions: string[];
  text_preview: string;
  warning?: string;
  parsed_fields: {
    nitrogen_level?: string | null;
    nitrogen_value?: number | null;
    phosphorus_level?: string | null;
    phosphorus_value?: number | null;
    potassium_level?: string | null;
    potassium_value?: number | null;
    ph_value?: number | null;
    moisture_level?: string | null;
    moisture_value?: number | null;
    soil_texture?: string | null;
    source?: string;
    is_validated?: boolean;
  };
}

export interface FertilizerRecommendationItem {
  nutrient: string;
  product: string;
  soil_level: string;
  measured_mg_kg?: number | null;
  action: string;
  priority: 'low' | 'medium' | 'high';
  rate_kg_ha?: number | null;
  total_field_kg?: number | null;
  timing: string;
  reasoning: string;
}

export interface FertilizerRecommendationResponse {
  status: 'lab_verified_plan' | 'unvalidated_estimate' | 'soil_sample_required';
  can_prescribe_dosage: boolean;
  is_validated: boolean;
  sample_id?: number;
  sample_source?: string;
  crop_type: string;
  area_ha: number;
  soil_texture?: string;
  ph_value?: number;
  summary: string;
  recommendations: FertilizerRecommendationItem[];
  ph_amendment?: {
    status: string;
    title: string;
    rate_kg_ha?: number | null;
    total_field_kg?: number | null;
    timing: string;
    reasoning: string;
  } | null;
  total_field_materials: Array<{
    product: string;
    rate_kg_ha: number;
    total_kg: number;
    bags_50kg: number;
  }>;
  application_tips: string[];
  satellite_context: string[];
  limitation: string;
}
