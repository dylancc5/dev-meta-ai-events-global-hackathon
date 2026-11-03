// Mirrors the pipeline's public/data/manifest.json contract. Every field is optional
// because the viewer must render gracefully whatever the pipeline emits.
export type Clip = {
  id: string;
  label?: string;
  thumb?: string;
  duration?: number;
  aspect?: string;
};

export type ScanEntry = {
  clip: string;
  found?: boolean;
  excluded?: boolean;
  spark_rejected?: string;
  presence?: number;
  score?: number;
  track?: string;
  frames?: number;
  thumb?: string;
};

export type Shot = {
  clip: string;
  in?: number;
  out?: number;
  beats?: number;
  reason?: string;
  effect?: string;
};

export type Plan = {
  planner?: string;
  planner_label?: string;
  rejected_by_spark?: { clip: string; label?: string; why?: string }[];
  bpm?: number;
  duration?: number;
  shots?: Shot[];
};

export type Run = {
  slug: string;
  prompt?: string;
  edit?: string;
  poster?: string;
  compare?: string;
  scan?: ScanEntry[];
  plan?: Plan;
  stats?: { frames_segmented?: number; seconds?: number; model?: string };
};

export type Manifest = {
  library?: { name?: string; clips?: Clip[] };
  runs?: Run[];
};
