"use client";

import { useEffect, useState } from "react";
import { api, fmt, pct } from "@/lib/api";
import { logger } from "@/lib/logger";

export const RECOMMENDATIONS = [
  { id: "churn", label: "1. Churn list", text: "Give account managers the churn list this week, starting with the accounts that show churn signals." },
  { id: "weekly", label: "2. Weekly tracker", text: "Track external sentiment and outage mentions weekly by call type." },
  { id: "roadmap", label: "3. Roadmap", text: "Put overage alerts and compliance report formats at the top of the roadmap." },
  { id: "actions", label: "4. Action tracker", text: "Link action items to the tracker so follow-through can be measured." },
];

// Each panel loads only when chosen, and needs a run except the action tracker.
function ChurnPanel({ run }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    if (run) api("/api/recommendations/churn").then(setRows).catch(() => setRows([]));
  }, [run?.run]);
  if (!run) return <div className="muted">Run the pipeline first.</div>;
  if (!rows) return <div className="muted">Loading…</div>;
  return (
    <table>
      <thead><tr><th>Account</th><th className="num">Signals</th><th className="num">Touchpoints</th><th>Latest</th></tr></thead>
      <tbody>
        {rows.slice(0, 15).map((r) => (
          <tr key={r.account}>
            <td>{r.account}{r.after_outage && <span className="tag warn">after outage</span>}</td>
            <td className="num">{r.churn_signals}</td>
            <td className="num">{r.touchpoints}</td>
            <td className="muted">{r.latest_signal.slice(0, 10)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function WeeklyPanel({ run }) {
  const [data, setData] = useState(null);
  const [type, setType] = useState("external");
  useEffect(() => {
    if (run) api("/api/recommendations/weekly").then(setData).catch(() => setData({ rows: [] }));
  }, [run?.run]);
  if (!run) return <div className="muted">Run the pipeline first.</div>;
  if (!data) return <div className="muted">Loading…</div>;
  const rows = data.rows.filter((r) => r.call_type === type);
  const alerts = rows.filter((r) => r.alert).length;
  return (
    <>
      <div className="row between" style={{ alignItems: "center" }}>
        <span className="muted small">
          Alert when sentiment is below {data.thresholds.sentiment_below}, or outage talk is at least {pct(data.thresholds.outage_share_at_or_above)} with sentiment below {data.thresholds.outage_sentiment_below}.
        </span>
        <select value={type} onChange={(e) => { logger.info(`weekly tracker: ${e.target.value}`); setType(e.target.value); }}>
          <option value="external">External</option>
          <option value="support">Support</option>
          <option value="internal">Internal</option>
        </select>
      </div>
      <p className="small">{alerts} alert week{alerts === 1 ? "" : "s"}</p>
      <table>
        <thead><tr><th>Week</th><th className="num">Calls</th><th className="num">Sentiment</th><th className="num">Outage talk</th><th></th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.week} className={r.alert ? "alert-row" : ""}>
              <td>{r.week.slice(0, 10)}</td>
              <td className="num">{r.meetings}</td>
              <td className="num">{fmt(r.sentiment)}</td>
              <td className="num">{pct(r.outage_share)}</td>
              <td>{r.alert && <span className="tag warn">alert</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function RoadmapPanel({ run }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (run) api("/api/recommendations/roadmap").then(setData).catch(() => setData({ items: [] }));
  }, [run?.run]);
  if (!run) return <div className="muted">Run the pipeline first.</div>;
  if (!data) return <div className="muted">Loading…</div>;
  return (
    <>
      {data.items.map((it) => (
        <div key={it.title} className="call">
          <div className="row between">
            <b>{it.title}</b>
            {it.recommended && <span className="tag">recommended</span>}
          </div>
          <div className="small muted">{it.evidence} feature-gap mentions · {it.external} from external calls</div>
          {it.examples.map((e, i) => <div key={i} className="moment">“{e}”</div>)}
        </div>
      ))}
    </>
  );
}

function ActionsPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api("/api/recommendations/actions").then(setData).catch((e) => setError(e.message));
  }, []);

  async function toggle(item) {
    const next = item.status === "done" ? "open" : "done";
    logger.info(`action ${item.id}: ${next}`);
    try {
      await api(`/api/recommendations/actions/${item.id}`, { method: "PUT", body: JSON.stringify({ status: next }) });
      setData((d) => {
        const items = d.items.map((i) => (i.id === item.id ? { ...i, status: next } : i));
        const done = items.filter((i) => i.status === "done").length;
        return { items, done, open: items.length - done };
      });
    } catch (e) {
      setError(e.message);
    }
  }

  if (error) return <div className="error">{error}</div>;
  if (!data) return <div className="muted">Loading…</div>;
  return (
    <>
      <p className="small muted">{data.open} open · {data.done} done. The dataset has no completion data, so statuses start as open and last until the API restarts.</p>
      <div className="calls">
        {data.items.map((it) => (
          <div key={it.id} className="call row between" style={{ alignItems: "center" }}>
            <div>
              <div><b>{it.owner}</b>: {it.task}</div>
              <div className="small muted">{it.meeting}</div>
            </div>
            <button className={it.status === "done" ? "secondary" : ""} onClick={() => toggle(it)}>
              {it.status === "done" ? "Reopen" : "Mark done"}
            </button>
          </div>
        ))}
      </div>
    </>
  );
}

const PANELS = { churn: ChurnPanel, weekly: WeeklyPanel, roadmap: RoadmapPanel, actions: ActionsPanel };

// Radio group on the home page. Hidden until one is chosen.
export default function Recommendations({ run }) {
  const [choice, setChoice] = useState("none");
  const Panel = PANELS[choice];

  function pick(id) {
    logger.info(`recommendations: ${id}`);
    setChoice(id);
  }

  return (
    <div className="card">
      <h2>Recommendations</h2>
      <div className="radio-group" role="radiogroup" aria-label="Recommendations">
        <label><input type="radio" name="rec" value="none" checked={choice === "none"} onChange={() => pick("none")} /> Hide</label>
        {RECOMMENDATIONS.map((r) => (
          <label key={r.id}>
            <input type="radio" name="rec" value={r.id} checked={choice === r.id} onChange={() => pick(r.id)} /> {r.label}
          </label>
        ))}
      </div>
      {Panel && (
        <div style={{ marginTop: 12 }}>
          <p>{RECOMMENDATIONS.find((r) => r.id === choice).text}</p>
          <Panel run={run} />
        </div>
      )}
    </div>
  );
}
