export type Beach = {
  slug: string;
  name: string;
  state: string;
  region: string;
  lat: number;
  lon: number;
  description?: string | null;
  tags?: string[];
  tide_station?: string | null;
};

export type WavesData = {
  available: boolean;
  wave_height_ft?: number;
  wave_period_s?: number;
  wave_direction?: string;
  swell_height_ft?: number;
  swell_period_s?: number;
  swell_direction?: string;
  size_label?: string;
  as_of?: string;
  timezone?: string;
  note?: string;
  error?: string;
};

export type RipData = {
  available: boolean;
  risk: string;
  office?: string;
  zone?: string;
  source?: string;
  note?: string;
  error?: string;
};

export type AlertItem = {
  event: string;
  severity?: string;
  headline?: string;
  description?: string;
  instruction?: string | null;
  effective?: string;
  ends?: string;
  sender?: string;
};

export type AlertsData = {
  count: number;
  all_clear: boolean;
  alerts: AlertItem[];
  error?: string;
};

export type TidesData = {
  available: boolean;
  station?: string;
  next_events: { type: "high" | "low"; time: string; height_ft: number }[];
  water_temperature?: { value_f: number; as_of?: string } | null;
  note?: string;
};

export type WaterQualityData = {
  available: boolean;
  status?: string;
  sample_date?: string;
  site?: string;
  source?: string;
  note?: string;
  external_url?: string;
};

export type SharksData = {
  available: boolean;
  total_recorded_incidents?: number;
  fatal_incidents?: number;
  incidents_since_2010?: number;
  most_recent?: { year: number; location: string; activity: string; fatal: boolean; species: string }[];
  risk_label?: string;
  radius_miles?: number;
  note?: string;
};

export type AmenitiesData = {
  available: boolean;
  search_radius_m?: number;
  counts?: Record<string, number>;
  examples?: Record<string, string[]>;
  summary?: string;
  error?: string;
};

export type BeachReport = {
  beach: Beach;
  waves: WavesData;
  rip_currents: RipData;
  alerts: AlertsData;
  tides: TidesData;
  water_quality: WaterQualityData;
  sharks: SharksData;
  amenities: AmenitiesData;
  blurb?: string;
};

export type ChatEvent =
  | { type: "status"; message: string }
  | { type: "tool_call"; name: string; arguments: Record<string, unknown> | string }
  | { type: "tool_result"; name: string; preview: string }
  | { type: "delta"; content: string }
  | { type: "done" }
  | { type: "error"; message: string };
