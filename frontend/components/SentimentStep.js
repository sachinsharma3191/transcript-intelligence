"use client";

import { useEffect, useState } from "react";
import { api, fmt, pct, CALL_TYPES } from "@/lib/api";
import Tutorial from "@/components/Tutorial";

const COLORS = { support: "#E76F51", external: "#2A9D8F", internal: "#457B9D" };

// Weekly mean sentiment per call type, drawn as one SVG polyline each.
function WeeklyChart({ weekly, outageDate }) {
  const W = 640, H = 200, P = 28;
  const weeks = [...new Set(weekly.map((w) => w.week))].sort();
  if (weeks.length < 2) return null;
  const x = (wk) => P + (weeks.indexOf(wk) / (weeks.length - 1)) * (W - 2 * P);
  const y = (v) => H - P - ((v - 1) / 4) * (H - 2 * P); // scale 1..5
  const outageIdx = weeks.findIndex((w) => w >= outageDate);
  const outageX = outageIdx < 0 ? null : x(weeks[outageIdx]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Weekly sentiment by call type">
      {[1, 2, 3, 4, 5].map((v) => (
        <g key={v}>
          <line x1={P} x2={W - P} y1={y(v)} y2={y(v)} stroke="var(--line)" />
          <text x={4} y={y(v) + 4} fontSize="11" fill="var(--muted)">{v}</text>
        </g>
      ))}
      {outageX !== null && (
        <g>
          <line x1={outageX} x2={outageX} y1={P} y2={H - P} stroke="#C44536" strokeDasharray="4 4" />
          <text x={outageX + 4} y={P + 10} fontSize="11" fill="#C44536">outage</text>
        </g>
      )}
      {CALL_TYPES.map((t) => {
        const pts = weeks
          .map((wk) => weekly.find((w) => w.week === wk && w.call_type === t))
          .filter(Boolean)
          .map((w) => `${x(w.week)},${y(w.sentiment)}`)
          .join(" ");
        return <polyline key={t} points={pts} fill="none" stroke={COLORS[t]} strokeWidth="2.5" />;
      })}
    </svg>
  );
}

export default function SentimentStep({ run }) {
  const [s, setS] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (run) api("/api/sentiment").then(setS).catch((e) => setError(e.message));
  }, [run?.run]);

  if (!run) return <div className="card muted">Run step 1 first.</div>;
  if (error) return <div className="card error">{error}</div>;
  if (!s) return <div className="muted">Loading sentiment…</div>;

  const sides = s.by_side.filter((r) => r.side !== "internal");

  return (
    <>
      <Tutorial
        what="Each sentence is labelled positive, neutral or negative. The chart tracks the average score per week; the dashed line is the outage."
        tryIt="compare the lines before and after the dashed outage line."
      />
      <div className="card">
        <h2>Sentiment by call type</h2>
        <table>
          <thead>
            <tr><th>Call type</th><th className="num">Positive</th><th className="num">Negative</th><th className="num">Score (VADER)</th></tr>
          </thead>
          <tbody>
            {CALL_TYPES.map((t) => {
              const r = s.by_call_type[t] || {};
              return (
                <tr key={t}>
                  <td><span className="dot" style={{ background: COLORS[t] }} />{t}</td>
                  <td className="num pos">{pct(r.pct_positive)}</td>
                  <td className="num neg">{pct(r.pct_negative)}</td>
                  <td className="num">{fmt(r.mean_vader)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Weekly trend <span className="muted">· meeting score, 1 to 5</span></h2>
        <WeeklyChart weekly={s.weekly} outageDate={s.outage_date} />
        <div className="row" style={{ marginTop: 6 }}>
          {CALL_TYPES.map((t) => (
            <span key={t} className="legend"><span className="dot" style={{ background: COLORS[t] }} />{t}</span>
          ))}
        </div>
      </div>

      <div className="grid2">
        <div className="card">
          <h2>Before and after {s.outage_date}</h2>
          <table>
            <thead><tr><th>Type</th><th className="num">Before</th><th className="num">After</th><th className="num">Change</th></tr></thead>
            <tbody>
              {CALL_TYPES.map((t) => {
                const o = s.outage_split[t];
                if (!o) return null;
                const change = o.before !== null && o.after !== null ? o.after - o.before : null;
                return (
                  <tr key={t}>
                    <td>{t}</td>
                    <td className="num">{fmt(o.before)}</td>
                    <td className="num">{fmt(o.after)}</td>
                    <td className={`num ${change < 0 ? "neg" : "pos"}`}>{change === null ? "–" : change.toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h2>Negative share: customer vs Aegis staff</h2>
          {sides.map((r) => (
            <div key={`${r.call_type}-${r.side}`} className="sidebar">
              <div className="row between"><span>{r.call_type} · {r.side}</span><span className="neg">{pct(r.negative)}</span></div>
              <div className="bar-track"><div className="bar-fill" style={{ width: `${(r.negative || 0) * 100}%`, background: "#C44536" }} /></div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2>What this means</h2>
        <ul className="takeaways">
          <li>External sentiment falls most after the outage: the relationship risk.</li>
          <li>Customers are negative far more often than our staff: track customer sentiment.</li>
        </ul>
        <div className="muted small">Written for the default data.</div>
      </div>
    </>
  );
}
