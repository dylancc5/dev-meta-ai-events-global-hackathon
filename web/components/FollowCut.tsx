"use client";
/* eslint-disable @next/next/no-img-element -- static export, plain <img> is intentional */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { Clip, Manifest, Run, ScanEntry, Shot } from "@/lib/types";
import { isCached, matchRun } from "@/lib/match";
import { dur, nf, tc } from "@/lib/format";

const BASE = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

type Phase = "idle" | "scanning" | "result";

const INTRO_MS = 900;
const HOLD_MS = 1000;

export default function FollowCut() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [prompt, setPrompt] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [nonce, setNonce] = useState(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [revealed, setRevealed] = useState(0);
  const [scanDone, setScanDone] = useState(false);
  const [ready, setReady] = useState(false);
  const [compare, setCompare] = useState(false);
  const [activeShot, setActiveShot] = useState(-1);
  const timers = useRef<number[]>([]);
  const [miss, setMiss] = useState<{ typed: string; shown: string } | null>(null);
  // The layout is composed for a 1920x1080 stage; on smaller screens scale the whole stage down instead of reflowing.
  const [zoom, setZoom] = useState(1);
  useEffect(() => {
    const fit = () => setZoom(Math.min(1, window.innerWidth / 1920, window.innerHeight / 1080));
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, []);

  useEffect(() => {
    let alive = true;
    fetch(`${BASE}/data/manifest.json`, { cache: "no-store" })
      .then((r) => (r.ok ? r.text() : Promise.reject(r.status)))
      // static host may serve under a sub-path (GitHub Pages): prefix every /data/ media path
      .then((t) => JSON.parse(BASE ? t.replaceAll('"/data/', `"${BASE}/data/`) : t) as Manifest)
      .then((m: Manifest) => alive && setManifest(m))
      .catch(() => alive && setLoadError(true));
    return () => {
      alive = false;
    };
  }, []);

  const clips = useMemo(() => manifest?.library?.clips ?? [], [manifest]);
  const runs = useMemo(() => manifest?.runs ?? [], [manifest]);
  const clipById = useMemo(() => new Map(clips.map((c) => [c.id, c])), [clips]);
  const scanById = useMemo(() => new Map((run?.scan ?? []).map((s) => [s.clip, s])), [run]);

  const clearTimers = () => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  };
  const later = (ms: number, fn: () => void) => {
    timers.current.push(window.setTimeout(fn, ms));
  };
  useEffect(() => clearTimers, []);

  const start = useCallback(
    (r: Run | undefined) => {
      if (!r) return;
      clearTimers();
      setRun(r);
      setNonce((n) => n + 1);
      setPhase("scanning");
      setRevealed(0);
      setScanDone(false);
      setReady(false);
      setCompare(false);
      setActiveShot(-1);
      const n = Math.max(clips.length, 1);
      const stagger = Math.min(250, 4200 / n);
      for (let i = 0; i < clips.length; i++) later(INTRO_MS + i * stagger, () => setRevealed(i + 1));
      later(INTRO_MS + clips.length * stagger + HOLD_MS, () => {
        setScanDone(true);
        setPhase("result");
      });
    },
    [clips.length],
  );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const r = matchRun(prompt, runs);
    setMiss(r && !isCached(prompt, r) ? { typed: prompt.trim(), shown: r.prompt ?? r.slug } : null);
    start(r);
  };

  const markReady = useCallback(() => setReady(true), []);

  // Fallback: never let the demo stall on a slow or undecodable video.
  useEffect(() => {
    if (phase !== "result") return;
    const t = window.setTimeout(markReady, run?.edit ? 3000 : 500);
    return () => window.clearTimeout(t);
  }, [phase, nonce, run?.edit, markReady]);

  const shots = run?.plan?.shots ?? [];
  const activeClip = phase === "result" && activeShot >= 0 ? shots[activeShot]?.clip : undefined;

  const framesSoFar = useMemo(() => {
    if (!run) return 0;
    if (scanDone && run.stats?.frames_segmented != null) return run.stats.frames_segmented;
    let total = 0;
    clips.slice(0, revealed).forEach((c) => (total += scanById.get(c.id)?.frames ?? 0));
    return total;
  }, [run, scanDone, clips, revealed, scanById]);

  const foundCount = clips.filter((c) => scanById.get(c.id)?.found).length;
  const totalSec = clips.reduce((a, c) => a + (c.duration ?? 0), 0);

  return (
    <div
      className={`relative flex flex-col px-12 pt-7 pb-4 ${zoom < 1 ? "" : "h-screen"}`}
      style={zoom < 1 ? { width: 1920, height: 1080, zoom, marginInline: "auto" } : undefined}
    >
      <Header />

      <main className="mt-6 flex min-h-0 flex-1 gap-10">
        {/* ---------------- left: prompt + library ---------------- */}
        <section className="flex min-w-0 flex-1 flex-col">
          <form onSubmit={onSubmit} className="group relative">
            <div className="flex items-center gap-3 rounded-2xl border border-line bg-panel/90 p-2 pl-6 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.8)] transition focus-within:border-amber/50 focus-within:shadow-[0_0_0_4px_rgba(255,169,77,0.08)]">
              <FrameIcon />
              <input
                id="prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Who is this video about?"
                autoComplete="off"
                spellCheck={false}
                className="min-w-0 flex-1 bg-transparent py-3 font-serif text-[34px] leading-none tracking-[-0.01em] text-paper outline-none placeholder:text-dim placeholder:italic"
              />
              <button
                id="follow"
                type="submit"
                disabled={!manifest}
                className="flex items-center gap-2 rounded-xl bg-amber px-7 py-4 text-[17px] font-semibold text-ink transition hover:bg-[#ffb766] active:scale-[0.98] disabled:opacity-40"
              >
                Follow
                <span aria-hidden className="text-[19px]">→</span>
              </button>
            </div>
            <div className="mt-3.5 flex flex-wrap items-center gap-2 pl-1">
              <span className="mr-1 text-[12px] uppercase tracking-[0.18em] text-dim">Try</span>
              {runs.map((r) => (
                <button
                  key={r.slug}
                  type="button"
                  data-run={r.slug}
                  onClick={() => {
                    setMiss(null);
                    setPrompt(r.prompt ?? r.slug);
                    start(r);
                  }}
                  className={`rounded-full border px-3.5 py-1.5 text-[14px] transition ${
                    run?.slug === r.slug && phase !== "idle"
                      ? "border-amber/60 bg-amber/10 text-amber"
                      : "border-line bg-white/[0.02] text-mute hover:border-amber/40 hover:text-paper"
                  }`}
                >
                  {r.prompt ?? r.slug}
                </button>
              ))}
            </div>
            {miss && (
              <p className="fade-up mt-3 rounded-xl border border-amber/30 bg-amber/[0.06] px-4 py-2.5 text-[13.5px] leading-snug text-paper/85">
                No cached run for <span className="text-amber">“{miss.typed}”</span>. SAM 3.1 runs on-device (about 6 min per
                prompt), so this hosted replay shows the closest cached run, <span className="text-amber">“{miss.shown}”</span>.
                Clone the repo to cut any prompt.
              </p>
            )}
          </form>

          <div className="mt-6 flex min-h-0 flex-1 flex-col rounded-2xl border border-line bg-panel/60 p-5">
            <div className="flex items-baseline justify-between gap-6">
              <div className="flex items-baseline gap-3">
                <span className="text-[11px] uppercase tracking-[0.2em] text-dim">Library</span>
                <h2 className="font-serif text-[26px] leading-none">{manifest?.library?.name ?? "Your footage"}</h2>
              </div>
              <span className="font-mono text-[13px] text-mute">
                {clips.length} clips{totalSec ? ` · ${dur(totalSec)}` : ""}
              </span>
            </div>

            <ScanLine
              phase={phase}
              run={run}
              frames={framesSoFar}
              revealed={revealed}
              total={clips.length}
              found={foundCount}
              done={scanDone}
            />

            <ClipGrid
              key={nonce}
              clips={clips}
              scanById={scanById}
              revealed={phase === "idle" ? 0 : revealed}
              scanning={phase === "scanning" && !scanDone}
              activeClip={activeClip}
            />
            {loadError && (
              <p className="mt-4 text-[14px] text-ember">Couldn’t load /data/manifest.json. Run the pipeline export first.</p>
            )}
          </div>
        </section>

        {/* ---------------- right: stage ---------------- */}
        <section className="flex w-[884px] flex-none flex-col">
          <div className="mb-3 flex h-8 items-center justify-between">
            <div className="flex items-baseline gap-3">
              <span className="text-[11px] uppercase tracking-[0.2em] text-dim">The edit</span>
              <span className="font-serif text-[22px] italic leading-none text-paper/90">
                {run && phase !== "idle" ? `“${run.prompt ?? run.slug}”` : "9:16 · follow-cam"}
              </span>
            </div>
            {phase === "result" && run?.compare && (
              <button
                id="compare-toggle"
                type="button"
                aria-pressed={compare}
                onClick={() => setCompare((c) => !c)}
                className="fade-up flex items-center gap-2 rounded-full border border-line bg-white/[0.03] px-4 py-1.5 text-[13px] text-mute transition hover:border-amber/50 hover:text-paper aria-pressed:border-amber/60 aria-pressed:text-amber"
              >
                <span className="inline-block h-2.5 w-4 rounded-[2px] border border-current" />
                {compare ? "Back to edit" : "Raw vs. edit"}
              </button>
            )}
          </div>

          <div
            className={`flex min-h-0 flex-1 gap-6 ${compare ? "flex-col" : "flex-row"} ${
              phase === "result" && ready ? "result-ready" : ""
            }`}
          >
            {compare && run?.compare ? (
              <CompareVideo key={`c${nonce}`} src={run.compare} />
            ) : (
              <Phone
                phase={phase}
                run={run}
                nonce={nonce}
                ready={ready}
                onReady={markReady}
                onTime={(frac) => {
                  if (!shots.length) return;
                  const lens = shots.map((s) => Math.max(0.01, (s.out ?? 0) - (s.in ?? 0)));
                  const total = lens.reduce((a, b) => a + b, 0);
                  let acc = 0;
                  const t = frac * total;
                  let idx = lens.length - 1;
                  for (let i = 0; i < lens.length; i++) {
                    acc += lens[i];
                    if (t < acc) {
                      idx = i;
                      break;
                    }
                  }
                  setActiveShot(idx);
                }}
              />
            )}
            <PlanPanel
              phase={phase}
              run={run}
              clipById={clipById}
              activeShot={activeShot}
              wide={compare}
              nonce={nonce}
            />
          </div>
        </section>
      </main>

      <footer className="mt-4 flex items-center justify-between text-[12px] text-dim">
        <span>Built for the Meta Global AI Developer Hackathon 2026 · Built with AI assistance (Claude Code)</span>
        <span className="font-mono">Replay of cached on-device runs · SAM runs locally on Apple silicon</span>
      </footer>
    </div>
  );
}

/* ====================================================================== */

function Header() {
  return (
    <header className="flex items-end justify-between">
      <div className="flex items-end gap-7">
        <div className="flex items-center gap-3">
          <Logo />
          <h1 className="font-serif text-[46px] leading-[0.9] tracking-[-0.02em]">
            Follow<span className="italic text-amber">Cut</span>
          </h1>
        </div>
        <p className="mb-1 max-w-[720px] text-[16px] text-mute">
          Hours of trip footage <span className="text-amber">→</span> the moments worth reliving, centered on the people
          you love.
        </p>
      </div>
      <div className="mb-1 flex items-center gap-2 text-[12px]">
        <span className="mr-1 uppercase tracking-[0.18em] text-dim">Powered by</span>
        <Chip dot="#ffa94d">SAM 3.1</Chip>
        <Chip dot="#7aa7ff">Muse Spark</Chip>
      </div>
    </header>
  );
}

function Chip({ children, dot }: { children: React.ReactNode; dot: string }) {
  return (
    <span className="flex items-center gap-2 rounded-full border border-line bg-white/[0.03] px-3 py-1 text-paper/80">
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: dot }} />
      {children}
    </span>
  );
}

function Logo() {
  return (
    <svg width="34" height="34" viewBox="0 0 34 34" fill="none" aria-hidden>
      <path d="M3 11V3h8M23 3h8v8M31 23v8h-8M11 31H3v-8" stroke="#ffa94d" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="17" cy="13" r="4" fill="#f1e9dc" />
      <path d="M9.5 26c1.2-4.4 4.2-6.6 7.5-6.6s6.3 2.2 7.5 6.6" stroke="#f1e9dc" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

function FrameIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden className="flex-none text-amber">
      <path d="M2 7V2h5M15 2h5v5M20 15v5h-5M7 20H2v-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="11" cy="11" r="2.4" fill="currentColor" />
    </svg>
  );
}

/* ---------------------------------------------------------------------- */

function ScanLine(props: {
  phase: Phase;
  run: Run | null;
  frames: number;
  revealed: number;
  total: number;
  found: number;
  done: boolean;
}) {
  const { phase, run, frames, revealed, total, found, done } = props;
  const pct = total ? (revealed / total) * 100 : 0;
  const subject = run?.prompt ?? run?.slug ?? "";
  return (
    <div className="mt-4 mb-4">
      <div className="flex h-6 items-center gap-3 font-mono text-[13px]">
        {phase === "idle" ? (
          <span className="text-dim">Raw clips, untouched. Tell FollowCut who to follow.</span>
        ) : done ? (
          <span className="scan-done fade-up flex items-center gap-2 text-paper/90">
            <span className="h-2 w-2 rounded-full bg-amber" />
            SAM 3.1 · found <span className="text-amber">‘{subject}’</span> in {found} of {total} clips ·{" "}
            {nf(frames)} frames
          </span>
        ) : (
          <span className="flex items-center gap-2 text-paper/80">
            <span className="pulse-dot h-2 w-2 rounded-full bg-amber" />
            SAM 3.1 · segmenting <span className="text-amber">‘{subject}’</span> · {nf(frames)} frames
            <span className="text-dim">
              · clip {Math.min(revealed + 1, total)}/{total}
            </span>
          </span>
        )}
      </div>
      <div className="mt-2 h-px w-full bg-line">
        <div
          className="h-px bg-amber transition-[width] duration-300 ease-out"
          style={{ width: phase === "idle" ? "0%" : `${done ? 100 : pct}%` }}
        />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */

const GAP = 10;

function ClipGrid(props: {
  clips: Clip[];
  scanById: Map<string, ScanEntry>;
  revealed: number;
  scanning: boolean;
  activeClip?: string;
}) {
  const { clips, scanById, revealed, scanning, activeClip } = props;
  const ref = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ w: 0, h: 0 });

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setBox({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Choose the column count that gives the biggest 16:9 tiles that fit without scrolling.
  const layout = useMemo(() => {
    const n = clips.length;
    if (!n || !box.w || !box.h) return { cols: 4, w: 0 };
    let best = { cols: 1, w: 0 };
    for (let cols = 1; cols <= n; cols++) {
      const rows = Math.ceil(n / cols);
      const wByWidth = (box.w - GAP * (cols - 1)) / cols;
      const wByHeight = ((box.h - GAP * (rows - 1)) / rows) * (16 / 9);
      const w = Math.min(wByWidth, wByHeight);
      if (w > best.w) best = { cols, w };
    }
    return { cols: best.cols, w: Math.floor(best.w) };
  }, [clips.length, box]);

  return (
    <div ref={ref} className="relative min-h-0 flex-1">
      <div
        className="grid content-start justify-center"
        style={{ gridTemplateColumns: `repeat(${layout.cols}, ${layout.w}px)`, gap: GAP }}
      >
        {layout.w > 0 &&
          clips.map((c, i) => (
            <Tile
              key={c.id}
              clip={c}
              scan={scanById.get(c.id)}
              flipped={i < revealed}
              scanningNow={scanning && i === revealed - 1}
              active={activeClip === c.id}
              width={layout.w}
            />
          ))}
      </div>
    </div>
  );
}

function Tile(props: {
  clip: Clip;
  scan?: ScanEntry;
  flipped: boolean;
  scanningNow: boolean;
  active: boolean;
  width: number;
}) {
  const { clip, scan, flipped, scanningNow, active, width } = props;
  const found = !!scan?.found;
  const conf = scan?.score ?? scan?.presence;
  const small = width < 190;
  return (
    <div
      className={`tile ${flipped ? "flipped" : ""} ${flipped && !found ? "missing" : ""} ${
        scanningNow ? "scanning-now" : ""
      } ${active ? "active" : ""}`}
      style={{ width, height: Math.round((width * 9) / 16) }}
      data-clip={clip.id}
    >
      <div className="tile-inner">
        {/* front: raw library thumb */}
        <div className={`tile-face bg-panel2 ${scanningNow ? "sweep" : ""}`}>
          <Thumb src={clip.thumb} alt={clip.label ?? clip.id} />
          <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent" />
          <TileCaption clip={clip} small={small} />
        </div>
        {/* back: SAM result */}
        <div className="tile-face tile-back bg-panel2">
          {found ? (
            <>
              <Thumb src={scan?.thumb ?? clip.thumb} alt={`${clip.label ?? clip.id} mask`} />
              {!scan?.thumb && <div className="absolute inset-2 rounded border-2 border-amber/80" />}
              <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-transparent to-transparent" />
              <div className="absolute top-1.5 left-1.5 flex items-center gap-1.5 rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[11px] text-amber backdrop-blur">
                <span className="h-1.5 w-1.5 rounded-full bg-amber" />
                {scan?.track ?? "T1"}
                {conf != null && <span className="text-paper/80">{conf.toFixed(2)}</span>}
              </div>
              {scan?.spark_rejected && !scan?.excluded && (
                <>
                  <div className="absolute inset-0 bg-black/55" />
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-1 px-2 text-center">
                    <span className="rounded-full border border-amber/50 bg-black/60 px-2.5 py-0.5 font-mono text-[11px] text-amber">
                      ✕ Muse Spark: not them
                    </span>
                    {!small && <span className="line-clamp-2 text-[11px] leading-tight text-paper/85">{scan.spark_rejected}</span>}
                  </div>
                </>
              )}
              {scan?.excluded && (
                <>
                  <div className="absolute inset-0 bg-black/55" />
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className="rounded-full border border-amber/50 bg-black/60 px-2.5 py-0.5 font-mono text-[11px] text-amber">
                      ✕ not them · excluded
                    </span>
                  </div>
                </>
              )}
              <TileCaption clip={clip} small={small} />
            </>
          ) : (
            <>
              <div className="absolute inset-0 grayscale">
                <Thumb src={clip.thumb} alt={clip.label ?? clip.id} />
              </div>
              <div className="absolute inset-0 bg-black/40" />
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="rounded-full border border-white/20 px-2.5 py-0.5 font-mono text-[11px] text-paper/80">
                  not in frame
                </span>
              </div>
              <TileCaption clip={clip} small={small} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function TileCaption({ clip, small }: { clip: Clip; small: boolean }) {
  return (
    <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-2 px-2 pb-1.5">
      <span className={`truncate font-medium text-paper ${small ? "text-[11px]" : "text-[13px]"}`}>
        {clip.label ?? clip.id}
      </span>
      {clip.duration != null && (
        <span className="flex-none font-mono text-[10.5px] text-paper/70">{tc(clip.duration).replace(/\.\d$/, "")}</span>
      )}
    </div>
  );
}

function Thumb({ src, alt }: { src?: string; alt: string }) {
  if (!src) return <div className="absolute inset-0 bg-gradient-to-br from-[#2a241e] to-[#14110e]" />;
  return <img src={src} alt={alt} className="absolute inset-0 h-full w-full object-cover" draggable={false} />;
}

/* ---------------------------------------------------------------------- */

function Phone(props: {
  phase: Phase;
  run: Run | null;
  nonce: number;
  ready: boolean;
  onReady: () => void;
  onTime: (frac: number) => void;
}) {
  const { phase, run, nonce, ready, onReady, onTime } = props;
  return (
    <div className="relative h-full flex-none" style={{ aspectRatio: "9 / 16.25" }}>
      {/* device body */}
      <div className="absolute inset-0 rounded-[44px] border border-white/10 bg-[#0a0908] p-[10px] shadow-[0_40px_120px_-30px_rgba(255,140,60,0.25),0_0_0_1px_rgba(0,0,0,0.6)_inset]">
        <div className="relative flex h-full w-full items-center justify-center overflow-hidden rounded-[35px] bg-black">
          <div className="absolute top-2.5 left-1/2 z-20 h-[22px] w-[92px] -translate-x-1/2 rounded-full bg-black" />
          <div className="absolute inset-0">
            {phase === "result" && run ? (
              run.edit ? (
                <EditVideo key={nonce} run={run} onReady={onReady} onTime={onTime} />
              ) : run.poster ? (
                <img src={run.poster} alt="" className="absolute inset-0 h-full w-full object-cover" />
              ) : (
                <div className="absolute inset-0 bg-panel2" />
              )
            ) : (
              <PhoneEmpty phase={phase} run={run} />
            )}
            {phase === "result" && !ready && run?.poster && (
              <img src={run.poster} alt="" className="absolute inset-0 h-full w-full object-cover" />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function PhoneEmpty({ phase, run }: { phase: Phase; run: Run | null }) {
  if (phase === "scanning") {
    return (
      <div className="shimmer absolute inset-0 flex flex-col items-center justify-center gap-4 px-8 text-center">
        <span className="pulse-dot h-2.5 w-2.5 rounded-full bg-amber" />
        <div className="font-serif text-[28px] italic leading-tight text-paper/90">Finding them in every clip…</div>
        <div className="font-mono text-[12px] text-mute">
          then cutting on the beat{run?.plan?.bpm ? ` · ${run.plan.bpm} BPM` : ""}
        </div>
      </div>
    );
  }
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-5 bg-[radial-gradient(circle_at_50%_40%,#1f1a15,#0b0a09)] px-9 text-center">
      <svg width="64" height="64" viewBox="0 0 34 34" fill="none" aria-hidden className="opacity-70">
        <path d="M3 11V3h8M23 3h8v8M31 23v8h-8M11 31H3v-8" stroke="#ffa94d" strokeWidth="1.4" strokeLinecap="round" />
        <circle cx="17" cy="13" r="4" stroke="#f1e9dc" strokeWidth="1.4" />
        <path d="M9.5 26c1.2-4.4 4.2-6.6 7.5-6.6s6.3 2.2 7.5 6.6" stroke="#f1e9dc" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
      <div className="font-serif text-[30px] leading-tight text-paper/85">
        Same footage.
        <br />
        <span className="italic text-amber">Your person</span> in the frame.
      </div>
      <div className="text-[13px] leading-relaxed text-mute">
        Name who the video is about. FollowCut finds them in every clip and cuts a vertical edit that follows them.
      </div>
    </div>
  );
}

function EditVideo({ run, onReady, onTime }: { run: Run; onReady: () => void; onTime: (f: number) => void }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    v.muted = true;
    v.play().catch(() => {});
  }, []);
  return (
    <video
      id="edit"
      ref={ref}
      src={run.edit}
      poster={run.poster || undefined}
      autoPlay
      muted
      loop
      playsInline
      preload="auto"
      onPlaying={onReady}
      onLoadedData={onReady}
      onError={onReady}
      onTimeUpdate={(e) => {
        const v = e.currentTarget;
        if (v.duration > 0) onTime(v.currentTime / v.duration);
      }}
      className="fade-up absolute inset-0 h-full w-full object-cover"
    />
  );
}

function CompareVideo({ src }: { src: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    v.muted = true;
    v.play().catch(() => {});
  }, []);
  return (
    <div className="fade-up relative w-full flex-none overflow-hidden rounded-2xl border border-line bg-black shadow-[0_40px_120px_-40px_rgba(255,140,60,0.3)]">
      <video
        id="compare"
        ref={ref}
        src={src}
        autoPlay
        muted
        loop
        playsInline
        className="block aspect-video w-full object-contain"
      />
      <div className="pointer-events-none absolute inset-x-0 top-0 flex justify-between p-3 font-mono text-[11px] uppercase tracking-[0.15em]">
        <span className="rounded bg-black/60 px-2 py-0.5 text-paper/70">Raw clip</span>
        <span className="rounded bg-black/60 px-2 py-0.5 text-amber">FollowCut</span>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */

function PlanPanel(props: {
  phase: Phase;
  run: Run | null;
  clipById: Map<string, Clip>;
  activeShot: number;
  wide: boolean;
  nonce: number;
}) {
  const { phase, run, clipById, activeShot, wide, nonce } = props;
  const plan = run?.plan;
  const shots = plan?.shots ?? [];
  const isStub = (plan?.planner ?? "").toLowerCase().includes("stub");
  const isSpark = (plan?.planner ?? "").startsWith("muse-spark");
  const rejectedN = plan?.rejected_by_spark?.length ?? 0;
  const showing = phase === "result" && !!run;

  return (
    <aside className="plan flex min-h-0 min-w-0 flex-1 flex-col rounded-2xl border border-line bg-panel/70 p-5">
      <div className="flex items-baseline justify-between">
        <div className="flex items-baseline gap-3">
          <span className="text-[11px] uppercase tracking-[0.2em] text-dim">The plan</span>
          {showing && <span className="font-serif text-[22px] leading-none">{shots.length} shots</span>}
        </div>
        {showing && (
          <span className="font-mono text-[12px] text-mute">
            {plan?.bpm ? `${plan.bpm} BPM` : ""}
            {plan?.bpm && plan?.duration ? " · " : ""}
            {plan?.duration ? `${plan.duration.toFixed(1)}s` : ""}
          </span>
        )}
      </div>

      {showing && plan?.planner_label && (
        <div className="mt-3 flex items-start gap-2 text-[12px] leading-snug">
          {isStub && (
            <span className="flex-none rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider text-amber">
              stub
            </span>
          )}
          {isSpark && (
            <span className="flex-none rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider text-amber">
              Muse Spark
            </span>
          )}
          <span className="text-mute">
            {plan.planner_label}
            {rejectedN > 0 && ` · rejected ${rejectedN} look-alike clip${rejectedN > 1 ? "s" : ""}`}
          </span>
        </div>
      )}

      <div
        className={`scrollbar-none mt-4 min-h-0 flex-1 overflow-y-auto ${
          wide ? "grid grid-cols-3 content-start gap-x-3 gap-y-2" : "flex flex-col gap-2"
        }`}
      >
        {showing
          ? shots.map((s, i) => (
              <ShotRow
                key={`${nonce}-${i}`}
                i={i}
                shot={s}
                clip={clipById.get(s.clip)}
                active={i === activeShot}
                compact={wide}
              />
            ))
          : Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className={`h-[66px] flex-none rounded-xl border border-line ${phase === "scanning" ? "shimmer" : "bg-white/[0.015]"}`}
              />
            ))}
        {phase === "idle" && (
          <p className="mt-2 text-[13px] leading-relaxed text-dim">
            The planner picks the moments where they’re in frame and cuts them to the beat.
          </p>
        )}
      </div>

      {showing && run?.stats && <Stats stats={run.stats} compact={wide} />}
    </aside>
  );
}

function ShotRow({ i, shot, clip, active, compact }: { i: number; shot: Shot; clip?: Clip; active: boolean; compact: boolean }) {
  return (
    <div
      className={`fade-up flex-none rounded-xl border px-3.5 py-2.5 transition-colors ${
        active ? "border-amber/50 bg-amber/[0.07]" : "border-line bg-white/[0.015]"
      }`}
      style={{ animationDelay: `${i * 70}ms` }}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div className="flex min-w-0 items-baseline gap-2.5">
          <span className={`font-mono text-[11px] ${active ? "text-amber" : "text-dim"}`}>{String(i + 1).padStart(2, "0")}</span>
          <span className="truncate font-serif text-[19px] leading-none text-paper">{clip?.label ?? shot.clip}</span>
        </div>
        <span className="flex-none font-mono text-[11.5px] text-paper/70">
          {tc(shot.in)} → {tc(shot.out)}
        </span>
      </div>
      <div className="mt-1.5 flex items-center gap-2 pl-[26px]">
        {shot.beats != null && (
          <span className="flex-none font-mono text-[11px] text-mute">
            {shot.beats} beat{shot.beats === 1 ? "" : "s"}
          </span>
        )}
        {shot.effect && (
          <span className="flex-none rounded border border-line px-1.5 font-mono text-[10.5px] text-amber/90">{shot.effect}</span>
        )}
      </div>
      {shot.reason && !compact && <div className="mt-1 truncate pl-[26px] text-[12.5px] text-mute">{shot.reason}</div>}
    </div>
  );
}

function Stats({ stats, compact }: { stats: NonNullable<Run["stats"]>; compact: boolean }) {
  return (
    <div className={`mt-4 border-t border-line pt-4 ${compact ? "flex items-center gap-8" : ""}`}>
      <div className="flex gap-8">
        {stats.frames_segmented != null && (
          <div>
            <div className="font-serif text-[28px] leading-none text-paper">{nf(stats.frames_segmented)}</div>
            <div className="mt-1 text-[11px] uppercase tracking-[0.14em] text-dim">frames segmented</div>
          </div>
        )}
        {stats.seconds != null && (
          <div>
            <div className="font-serif text-[28px] leading-none text-paper">{dur(stats.seconds)}</div>
            <div className="mt-1 text-[11px] uppercase tracking-[0.14em] text-dim">wall time</div>
          </div>
        )}
      </div>
      {stats.model && <div className={`${compact ? "" : "mt-3"} font-mono text-[11px] leading-snug text-mute`}>{stats.model}</div>}
    </div>
  );
}
