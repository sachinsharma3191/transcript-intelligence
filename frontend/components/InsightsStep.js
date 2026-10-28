"use client";

import { useEffect, useState } from "react";
import { api, fmt, query } from "@/lib/api";
import Tutorial from "@/components/Tutorial";
import { logger } from "@/lib/logger";

// Each stakeholder sees a different slice of the same data.
const STAKEHOLDERS = [
  { id: "support", label: "Support lead", question: "Which accounts keep coming back?" },
  { id: "sales", label: "Account manager", question: "Who is at risk of churning?" },
  { id: "product", label: "Product manager", question: "What do customers ask for?" },
  { id: "engineering", label: "Engineering lead", question: "Did the outage hurt, and is a rival gaining ground?" },
];

const MOMENT_LABEL = { churn_signal: "churn", concern: "concern", feature_gap: "feature gap", technical_issue: "technical", positive_pivot: "positive", praise: "praise", action_item: "action", pricing_offer: "pricing" };

export default function InsightsStep({ run }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [who, setWho] = useState("sales");
  const [filter, setFilter] = useState({ call_type: "", theme: "", account: "" });
  const [calls, setCalls] = useState(null);

  useEffect(() => {
    if (run) api("/api/insights").then(setData).catch((e) => setError(e.message));
  }, [run?.run]);

  useEffect(() => {
    if (run) api(`/api/calls${query({ ...filter, limit: 12 })}`).then(setCalls).catch((e) => setError(e.message));
  }, [run?.run, filter.call_type, filter.theme, filter.account]);

  if (!run) return <div className="card muted">Run step 1 first.</div>;
  if (error) return <div className="card error">{error}</div>;
  if (!data || !calls) return <div className="muted">Loading insights…</div>;

  const drill = (patch) => {
    logger.info("insights: filter", patch);
    setFilter((f) => ({ ...f, ...patch }));
  };
  const stake = STAKEHOLDERS.find((s) => s.id === who);
  const maxWeek = Math.max(1, ...data.competitor_weekly.map((w) => w.pct || 0));

  return (
    <>
      <Tutorial
        what="Pick a stakeholder to see the question they care about. Click an account, theme or week to filter the calls on the right."
        tryIt="click an account in the churn list."
      />
    <div className="insights">
      <div>
        <div className="tabs">
          {STAKEHOLDERS.map((s) => (
            <button key={s.id} className={s.id === who ? "tab on" : "tab"}
              onClick={() => { logger.info(`insights: stakeholder ${s.id}`); setWho(s.id); }}>
              {s.label}
            </button>
          ))}
        </div>
        <div className="muted" style={{ margin: "8px 0 12px" }}>{stake.question}</div>

        {who === "support" && (
          <div className="card">
            <h2>Accounts with repeat cases</h2>
            <table>
              <thead><tr><th>Account</th><th className="num">Cases</th><th className="num">Sentiment</th></tr></thead>
              <tbody>
                {data.repeat_support.map((r) => (
                  <tr key={r.account} className="click" onClick={() => drill({ account: r.account })}>
                    <td>{r.account}</td><td className="num">{r.cases}</td><td className="num">{fmt(r.avg_sentiment)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {who === "sales" && (
          <div className="card">
            <h2>Churn early warning <span className="muted">· {data.churn.length} accounts</span></h2>
            <table>
              <thead><tr><th>Account</th><th className="num">Signals</th><th>Latest</th></tr></thead>
              <tbody>
                {data.churn.slice(0, 12).map((r) => (
                  <tr key={r.account} className="click" onClick={() => drill({ account: r.account })}>
                    <td>{r.account}{r.after_outage && <span className="tag warn">after outage</span>}</td>
                    <td className="num">{r.churn_signals}</td>
                    <td className="muted">{r.latest_signal?.slice(0, 10)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {who === "product" && (
          <div className="card">
            <h2>Feature-gap moments by theme</h2>
            <table>
              <thead><tr><th>Theme</th><th className="num">External</th><th className="num">Internal</th><th className="num">Support</th></tr></thead>
              <tbody>
                {data.feature_demand.map((r) => (
                  <tr key={r.theme} className="click" onClick={() => drill({ theme: r.theme })}>
                    <td>{r.theme}</td><td className="num">{r.external}</td><td className="num">{r.internal}</td><td className="num">{r.support}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {who === "engineering" && (
          <div className="card">
            <h2>SentinelShield mentions by week</h2>
            {data.competitor_weekly.map((w) => (
              <div key={w.week} className="sidebar">
                <div className="row between"><span className="muted">{w.week.slice(0, 10)}</span><span>{fmt(w.pct)}%</span></div>
                <div className="bar-track"><div className="bar-fill" style={{ width: `${((w.pct || 0) / maxWeek) * 100}%` }} /></div>
              </div>
            ))}
            <button className="secondary" style={{ marginTop: 12 }} onClick={() => drill({ theme: "Outage & reliability", call_type: "" })}>
              Show outage calls
            </button>
          </div>
        )}
      </div>

      <div className="card">
        <h2>Calls <span className="muted">· {calls.total} match</span></h2>
        <div className="filters">
          <select value={filter.call_type} onChange={(e) => drill({ call_type: e.target.value })}>
            <option value="">All types</option>
            <option value="support">Support</option>
            <option value="external">External</option>
            <option value="internal">Internal</option>
          </select>
          <select value={filter.theme} onChange={(e) => drill({ theme: e.target.value })}>
            <option value="">All themes</option>
            {run.themes.filter((t) => t.theme !== "Other").map((t) => (
              <option key={t.theme} value={t.theme}>{t.theme}</option>
            ))}
          </select>
          {filter.account && (
            <span className="tag" onClick={() => drill({ account: "" })} style={{ cursor: "pointer" }}>
              {filter.account} ×
            </span>
          )}
          {(filter.call_type || filter.theme || filter.account) && (
            <button className="secondary" onClick={() => { logger.info("insights: filters cleared"); setFilter({ call_type: "", theme: "", account: "" }); }}>Clear</button>
          )}
        </div>

        {calls.items.length === 0 && <div className="muted">No calls match these filters.</div>}
        <div className="calls">
          {calls.items.map((c) => (
            <div key={c.meeting_id} className="call">
              <div className="row between">
                <b>{c.title}</b>
                <span className="muted small">{c.call_type} · {c.theme}</span>
              </div>
              <div className="row small muted">
                <span>score {fmt(c.sentiment_score)}</span>
                {c.churn_signals > 0 && <span className="neg">{c.churn_signals} churn signal{c.churn_signals > 1 ? "s" : ""}</span>}
              </div>
              {c.moments.slice(0, 2).map((m, i) => (
                <div key={i} className="moment">
                  <span className="tag">{MOMENT_LABEL[m.type] || m.type}</span> {m.text}
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
    </>
  );
}
