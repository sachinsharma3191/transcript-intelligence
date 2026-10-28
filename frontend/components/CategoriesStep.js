"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Tutorial from "@/components/Tutorial";
import { logger } from "@/lib/logger";

// The API stores keywords as lists; the form edits them as comma-separated text.
const toForm = (cfg) => ({
  title_weight: cfg.title_weight,
  outage_date: cfg.outage_date,
  themes: Object.fromEntries(Object.entries(cfg.themes).map(([n, k]) => [n, k.join(", ")])),
});
const toPayload = (f) => ({
  title_weight: Number(f.title_weight),
  outage_date: f.outage_date,
  themes: Object.fromEntries(
    Object.entries(f.themes).map(([n, t]) => [n, t.split(",").map((k) => k.trim()).filter(Boolean)])
  ),
});

export default function CategoriesStep({ run, runPipeline }) {
  const [cats, setCats] = useState(null);
  const [form, setForm] = useState(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/config").then((c) => setForm(toForm(c))).catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (run) api("/api/categories").then(setCats).catch((e) => setError(e.message));
  }, [run?.run]);

  async function apply(label, fn) {
    logger.info(`categories: ${label}`);
    setBusy(true);
    setError("");
    try {
      await fn();
      await runPipeline();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!run) return <div className="card muted">Run step 1 first.</div>;

  const moved = run.changes.first_run ? null : run.changes.moved_meetings.length;
  const deltas = run.changes.theme_deltas.filter((d) => d.delta !== 0);

  logger.debug(`categories render, run=${run?.run ?? "none"}`);
  return (
    <>
      <Tutorial
        what="Each call gets one main theme from keyword rules. Edit a keyword, apply it, and see which calls move."
        tryIt="open Edit keywords, add a word to Outage & reliability, then Apply and re-run."
      />
      {error && <div className="card error">{error}</div>}

      <div className="card">
        <div className="row" style={{ alignItems: "center", marginTop: 0 }}>
          <h2 style={{ margin: 0 }}>Themes</h2>
          <span className="muted">
            {moved === null
              ? "First run."
              : moved === 0
              ? "No calls changed theme."
              : `${moved} calls changed theme${deltas.length ? ": " + deltas.map((d) => `${d.theme} ${d.delta > 0 ? "+" : ""}${d.delta}`).join(", ") : ""}`}
          </span>
        </div>
        <table style={{ marginTop: 8 }}>
          <thead>
            <tr>
              <th>Theme</th>
              <th className="num">Calls</th>
              <th className="num">Support</th>
              <th className="num">External</th>
              <th className="num">Internal</th>
            </tr>
          </thead>
          <tbody>
            {(cats?.themes || []).map((t) => (
              <tr key={t.theme}>
                <td>
                  <b>{t.theme}</b>
                  {t.examples.length > 0 && (
                    <div className="muted small">e.g. {t.examples.map((e) => e.title).slice(0, 2).join(" · ")}</div>
                  )}
                </td>
                <td className="num">{t.meetings}</td>
                <td className="num">{t.by_call_type.support}</td>
                <td className="num">{t.by_call_type.external}</td>
                <td className="num">{t.by_call_type.internal}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <button className="secondary" onClick={() => setOpen(!open)}>
          {open ? "Hide" : "Edit"} keywords
        </button>
        {open && form && (
          <div style={{ marginTop: 12 }}>
            <div className="grid2">
              <div>
                <label htmlFor="weight">Title weight (1–10)</label>
                <input id="weight" type="number" min="1" max="10" value={form.title_weight}
                  onChange={(e) => setForm({ ...form, title_weight: e.target.value })} />
              </div>
              <div>
                <label htmlFor="outage">Outage date</label>
                <input id="outage" type="date" value={form.outage_date}
                  onChange={(e) => setForm({ ...form, outage_date: e.target.value })} />
              </div>
            </div>
            {Object.entries(form.themes).map(([name, text]) => (
              <div key={name}>
                <label>{name}</label>
                <textarea value={text}
                  onChange={(e) => setForm({ ...form, themes: { ...form.themes, [name]: e.target.value } })} />
              </div>
            ))}
            <div className="row">
              <button disabled={busy} onClick={() => apply("apply keywords", () => api("/api/config", { method: "PUT", body: JSON.stringify(toPayload(form)) }))}>
                {busy ? "Running…" : "Apply and re-run"}
              </button>
              <button className="secondary" disabled={busy} onClick={() => apply("reset to default", async () => setForm(toForm(await api("/api/config/reset", { method: "POST" }))))}>
                Reset to default
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
