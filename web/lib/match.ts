import type { Run } from "./types";

const STOP = new Set(["the", "a", "an", "with", "in", "of", "and", "on", "who", "is", "my", "our", "this", "that", "video", "about", "wearing"]);

const tokens = (s: string) =>
  s.toLowerCase().replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter((t) => t && !STOP.has(t));

/** Map free text to the best cached run: exact > substring > token overlap > first run. */
export function matchRun(text: string, runs: Run[]): Run | undefined {
  if (!runs.length) return undefined;
  const q = text.trim().toLowerCase();
  if (!q) return runs[0];
  const exact = runs.find((r) => (r.prompt ?? "").toLowerCase() === q || r.slug.toLowerCase() === q);
  if (exact) return exact;
  const sub = runs.find((r) => {
    const p = (r.prompt ?? "").toLowerCase();
    return p && (p.includes(q) || q.includes(p));
  });
  if (sub) return sub;
  const qt = tokens(q);
  let best = runs[0];
  let bestScore = -1;
  for (const r of runs) {
    const pt = tokens(`${r.prompt ?? ""} ${r.slug}`);
    let score = 0;
    for (const t of qt) {
      if (pt.includes(t)) score += 2;
      else if (pt.some((p) => p.startsWith(t.slice(0, 4)) || t.startsWith(p.slice(0, 4)))) score += 1;
    }
    if (score > bestScore) {
      bestScore = score;
      best = r;
    }
  }
  return best;
}
