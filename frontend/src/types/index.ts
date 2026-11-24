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
  overall_health: string;
  health_score: number;
  total_hotspots: number;
  critical_hotspots: number;
  ndvi_mean?: number;
  ndmi_mean?: number;
  ndre_mean?: number;
  ndvi_trend?: 'improving' | 'stable' | 'declining';
  recent_recommendations: Recommendation[];
  highest_priority_hotspot?: Hotspot;
}

export interface HistoricalData {
  dates: string[];
  ndvi: number[];
  ndmi: number[];
  ndre: number[];
  health_scores: number[];
}

export type SeverityLevel = 'healthy' | 'mild' | 'moderate' | 'severe';
