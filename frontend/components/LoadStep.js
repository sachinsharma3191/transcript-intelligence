"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import Tutorial from "@/components/Tutorial";

export default function LoadStep({ run, runPipeline }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api("/api/data").then(setData).catch(() => setData(false));
  }, []);

  async function load() {
    setBusy(true);
    try {
      await runPipeline();
    } finally {
      setBusy(false);
    }
  }

  if (data === null) return <div className="muted">Loading dataset…</div>;
  if (data === false) return <div className="card error">Could not read the dataset from the API.</div>;

  return (
    <>
      <Tutorial
        what="Loads the 100 call transcripts and their summaries. Running the pipeline scores every call."
        tryIt="press Run pipeline, then open step 2."
      />
      <div className="card">
        <div className="stats">
          <div className="stat"><span className="muted">Meetings</span><b>{data.meetings}</b></div>
          <div className="stat"><span className="muted">Sentences</span><b>{data.sentences.toLocaleString()}</b></div>
          <div className="stat"><span className="muted">Speakers</span><b>{data.speakers}</b></div>
          <div className="stat"><span className="muted">External accounts</span><b>{data.external_accounts}</b></div>
          <div className="stat"><span className="muted">Dates</span><b className="small">{data.date_range[0]} → {data.date_range[1]}</b></div>
        </div>
        <div className="row" style={{ marginTop: 14, alignItems: "center" }}>
          <span className="muted">Call types:</span>
          <span className="tag">support {data.call_types.support}</span>
          <span className="tag">external {data.call_types.external}</span>
          <span className="tag">internal {data.call_types.internal}</span>
        </div>
      </div>

      <div className="card">
        <h2>Sample</h2>
        <table>
          <thead><tr><th>Date</th><th>Type</th><th>Title</th></tr></thead>
          <tbody>
            {data.sample.map((m) => (
              <tr key={m.meeting_id}>
                <td className="muted">{m.start?.slice(0, 10)}</td>
                <td>{m.call_type}</td>
                <td>{m.title}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="row">
        <button onClick={load} disabled={busy}>
          {busy ? "Running…" : run ? `Run again (run #${run.run + 1})` : "Run pipeline"}
        </button>
        {run && <span className="muted" style={{ alignSelf: "center" }}>Run #{run.run} ready.</span>}
      </div>
    </>
  );
}
