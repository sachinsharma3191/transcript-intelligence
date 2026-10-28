"use client";

import { useEffect, useState } from "react";
import { api, API } from "@/lib/api";
import { logger } from "@/lib/logger";
import LoadStep from "@/components/LoadStep";
import CategoriesStep from "@/components/CategoriesStep";
import SentimentStep from "@/components/SentimentStep";
import InsightsStep from "@/components/InsightsStep";
import Recommendations from "@/components/Recommendations";
import Tutorial from "@/components/Tutorial";

const STEPS = [
  { id: "load", label: "Load data" },
  { id: "categories", label: "Categories" },
  { id: "sentiment", label: "Sentiment" },
  { id: "insights", label: "Insights" },
  { id: "roadmap", label: "Future roadmap" },
];

export default function Home() {
  const [step, setStep] = useState("load");
  const [health, setHealth] = useState(null);
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    logger.info(`app started, API at ${API}`);
    api("/api/health").then(setHealth).catch(() => setHealth(false));
  }, []);

  useEffect(() => {
    logger.info(`step: ${step}`);
  }, [step]);

  // Every step runs through here, so the latest run is shared by all of them.
  async function runPipeline() {
    try {
      logger.info("running pipeline");
      const r = await api("/api/runs", { method: "POST" });
      logger.info(`run #${r.run} done: ${r.changes.moved_meetings.length} calls moved theme`);
      setRun(r);
      setError("");
      return r;
    } catch (e) {
      logger.error("pipeline run failed", e.message);
      setError(e.message);
      throw e;
    }
  }

  const props = { run, runPipeline };
  const locked = (id) => id !== "load" && !run;

  return (
    <main>
      <header>
        <div>
          <h1>Transcript Intelligence</h1>
          <div className="muted">Calls → categories → sentiment → insights</div>
        </div>
        <span className={`pill ${health ? "ok" : "down"}`}>
          {health === null ? "checking API…" : health ? `API ok · ${health.meetings} meetings` : `API unreachable at ${API}`}
        </span>
      </header>

      <nav className="steps">
        {STEPS.map((s, i) => (
          <button
            key={s.id}
            className={`step ${step === s.id ? "on" : ""}`}
            disabled={locked(s.id)}
            onClick={() => setStep(s.id)}
          >
            <span className="num-badge">{i + 1}</span> {s.label}
          </button>
        ))}
      </nav>

      {error && <div className="card error">{error}</div>}

      {step === "load" && <LoadStep {...props} />}
      {step === "categories" && <CategoriesStep {...props} />}
      {step === "sentiment" && <SentimentStep {...props} />}
      {step === "insights" && <InsightsStep {...props} />}
      {step === "roadmap" && (
        <>
          <Tutorial
            what="Four recommendations from the analysis. Pick one to see it built out with live data."
            tryIt="pick 4. Action tracker and mark an item done."
          />
          <Recommendations run={run} />
        </>
      )}
    </main>
  );
}
