export function tc(sec?: number): string {
  if (sec == null || !isFinite(sec)) return "--:--";
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${m}:${s.toFixed(1).padStart(4, "0")}`;
}

export function dur(sec?: number): string {
  if (sec == null || !isFinite(sec)) return "";
  const total = Math.round(sec);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h) return `${h} h ${m} min`;
  if (m >= 10) return `${m} min`;
  if (m) return `${m}m ${String(s).padStart(2, "0")}s`;
  return `${s}s`;
}

export const nf = (n?: number) => (n == null ? "" : n.toLocaleString("en-US"));
