"""Configurable pipeline service used by the API.

The analysis modules are pure functions of their inputs. This class loads the
dataset once, keeps a mutable config (themes, keyword lists, title weight,
outage date), and re-runs categorization and sentiment on demand. Each step of
the assignment (load, categories, sentiment, insights) reads from the latest run.
"""
import copy
import logging
import time
from datetime import date

import pandas as pd

import insights
import recommendations
import sentiment
from categorize import THEMES, TITLE_WEIGHT, categorize
from load import add_speaker_side, load_meetings, load_sentences

DEFAULT_OUTAGE_DATE = sentiment.OUTAGE_DATE.date().isoformat()
CALL_TYPES = ["support", "external", "internal"]
log = logging.getLogger("pipeline")


class NoRunYet(Exception):
    """Raised when a step is requested before the pipeline has run."""


def default_config():
    return {
        "title_weight": TITLE_WEIGHT,
        "outage_date": DEFAULT_OUTAGE_DATE,
        "themes": copy.deepcopy(THEMES),
    }


def validate_config(cfg):
    """Return a cleaned config or raise ValueError with a message the UI can show."""
    weight = int(cfg["title_weight"])
    if not 1 <= weight <= 10:
        raise ValueError("title_weight must be between 1 and 10")

    outage = date.fromisoformat(cfg["outage_date"]).isoformat()

    themes = {}
    for name, keywords in cfg["themes"].items():
        name = name.strip()
        if not name:
            raise ValueError("theme names cannot be empty")
        cleaned = sorted({k.strip().lower() for k in keywords if k.strip()})
        if not cleaned:
            raise ValueError(f"theme '{name}' needs at least one keyword")
        themes[name] = cleaned
    if not themes:
        raise ValueError("at least one theme is required")
    return {"title_weight": weight, "outage_date": outage, "themes": themes}


def _num(x):
    return None if pd.isna(x) else round(float(x), 3)


def _iso(ts):
    return None if pd.isna(ts) else pd.Timestamp(ts).isoformat()


class Pipeline:
    def __init__(self):
        start = time.perf_counter()
        self.meetings = load_meetings()
        log.info("loaded %d meetings", len(self.meetings))
        sentences = sentiment.add_vader(load_sentences(self.meetings))
        self.sentences = add_speaker_side(sentences, self.meetings)
        log.info("loaded %d sentences, scored with VADER (%.0f ms)",
                 len(self.sentences), (time.perf_counter() - start) * 1000)
        self.config = default_config()
        self.latest = None  # the summary dict returned by the last run
        self.categorized = None  # meetings with theme, from the last run
        self.scored_sentences = None  # sentences with theme, from the last run
        self.run_count = 0
        self.action_status = {}  # action id -> "open" | "done", kept in memory

    # ----- config -------------------------------------------------------
    def get_config(self):
        return self.config

    def set_config(self, cfg):
        self.config = validate_config(cfg)
        return self.config

    def reset_config(self):
        self.config = default_config()
        return self.config

    # ----- step 1: load -------------------------------------------------
    def load_summary(self):
        m = self.meetings
        s = self.sentences
        return {
            "meetings": len(m),
            "sentences": len(s),
            "speakers": int(s["speaker"].nunique()),
            "date_range": [m["start"].min().date().isoformat(), m["start"].max().date().isoformat()],
            "call_types": {t: int((m["call_type"] == t).sum()) for t in CALL_TYPES},
            "external_accounts": int(
                m.loc[m["is_external"], "external_domains"].str.split(",").str[0].nunique()
            ),
            "sample": [
                {"meeting_id": r.meeting_id, "title": r.title, "call_type": r.call_type,
                 "start": _iso(r.start)}
                for r in m.head(6).itertuples()
            ],
        }

    # ----- step 2 onward: run -------------------------------------------
    def run(self):
        start = time.perf_counter()
        cfg = self.config
        meetings = categorize(self.meetings, cfg["themes"], cfg["title_weight"])
        sentences = self.sentences.merge(meetings[["meeting_id", "theme"]], on="meeting_id")
        scored = sentiment.meeting_scores(sentences, meetings)
        outage = pd.Timestamp(cfg["outage_date"], tz="UTC")
        summary = {
            "run": self.run_count + 1,
            "config": cfg,
            "totals": {t: int((meetings["call_type"] == t).sum()) for t in CALL_TYPES},
            "themes": self._themes(meetings, scored, cfg),
            "sentiment_by_call_type": self._sentiment_by_call_type(sentences),
            "outage_split": self._outage_split(meetings, outage),
            "churn_accounts": int(len(insights.churn_early_warning(meetings))),
            "meetings": self._meetings(meetings),
        }
        summary["changes"] = self._changes(summary)
        summary["duration_ms"] = round((time.perf_counter() - start) * 1000, 1)
        log.debug("run stages finished: themes=%s", {t["theme"]: t["meetings"] for t in summary["themes"]})
        self.categorized = meetings
        self.scored_sentences = sentences
        self.latest = summary
        self.run_count += 1
        return summary

    def _require_run(self):
        if self.categorized is None:
            raise NoRunYet("run the pipeline first: POST /api/runs")

    # ----- step 2: categories ------------------------------------------
    def categories(self):
        self._require_run()
        m = self.categorized
        rows = []
        for name in list(self.config["themes"]) + ["Other"]:
            g = m[m["theme"] == name]
            rows.append({
                "theme": name,
                "keywords": self.config["themes"].get(name, []),
                "meetings": int(len(g)),
                "by_call_type": {t: int((g["call_type"] == t).sum()) for t in CALL_TYPES},
                "examples": [
                    {"meeting_id": r.meeting_id, "title": r.title, "call_type": r.call_type}
                    for r in g.head(3).itertuples()
                ],
            })
        return {"themes": rows, "title_weight": self.config["title_weight"]}

    # ----- step 3: sentiment --------------------------------------------
    def sentiment_view(self):
        self._require_run()
        m = self.categorized
        s = self.scored_sentences
        weekly = sentiment.weekly_trend(m)
        return {
            "by_call_type": self.latest["sentiment_by_call_type"],
            "outage_split": self.latest["outage_split"],
            "by_theme": [
                {"theme": t["theme"], "sentiment": t["sentiment"]} for t in self.latest["themes"]
            ],
            "by_side": [
                {"call_type": ct, "side": side,
                 "negative": _num((g["sentiment_label"] == "negative").mean()),
                 "neutral": _num((g["sentiment_label"] == "neutral").mean()),
                 "positive": _num((g["sentiment_label"] == "positive").mean()),
                 "sentences": int(len(g))}
                for (ct, side), g in s.groupby(["call_type", "side"])
            ],
            "weekly": [
                {"week": _iso(r.week), "call_type": r.call_type,
                 "sentiment": _num(r.mean_sentiment_score), "meetings": int(r.meetings)}
                for r in weekly.itertuples()
            ],
            "outage_date": self.config["outage_date"],
        }

    # ----- step 4: insights ---------------------------------------------
    def insights_view(self):
        self._require_run()
        m = self.categorized
        s = self.scored_sentences
        churn = insights.churn_early_warning(m)
        demand = insights.feature_demand(m).reset_index()
        competitor = insights.competitor_pressure(s, m).reset_index()
        repeat = insights.support_repeat_accounts(m)
        return {
            "churn": [
                {"account": r.account, "churn_signals": int(r.churn_signals),
                 "touchpoints": int(r.touchpoints), "latest_signal": _iso(r.latest_signal),
                 "after_outage": bool(r.after_outage)}
                for r in churn.itertuples()
            ],
            "feature_demand": [
                {"theme": r.theme, "external": int(r.external), "internal": int(r.internal),
                 "support": int(r.support), "total": int(r.total)}
                for r in demand.itertuples()
            ],
            "competitor_weekly": [
                {"week": _iso(r.week), "meetings": int(r.meetings),
                 "meetings_mentioning": int(r.meetings_mentioning), "pct": _num(r.pct_mentioning)}
                for r in competitor.itertuples()
            ],
            "repeat_support": [
                {"account": r.account, "cases": int(r.cases), "avg_sentiment": _num(r.avg_sentiment)}
                for r in repeat.itertuples()
            ],
        }

    # ----- drill-down: calls --------------------------------------------
    def calls(self, theme=None, call_type=None, account=None, limit=50):
        self._require_run()
        m = self.categorized.assign(account=insights.account_of(self.categorized))
        if theme:
            m = m[(m["theme"] == theme) | m["secondary_themes"].map(lambda ts: theme in ts)]
        if call_type:
            m = m[m["call_type"] == call_type]
        if account:
            m = m[m["account"] == account]
        items = []
        for r in m.head(limit).itertuples():
            moments = [{"type": k["type"], "text": k["text"]} for k in r.key_moments]
            items.append({
                "meeting_id": r.meeting_id,
                "title": r.title,
                "call_type": r.call_type,
                "theme": r.theme,
                "account": r.account if isinstance(r.account, str) else None,
                "sentiment_score": _num(r.sentiment_score),
                "churn_signals": sum(1 for k in moments if k["type"] == "churn_signal"),
                "moments": moments[:4],
            })
        return {"total": int(len(m)), "items": items}

    # ----- recommendations ----------------------------------------------
    def rec_churn(self):
        self._require_run()
        return recommendations.churn(self.categorized)

    def rec_weekly(self):
        self._require_run()
        return recommendations.weekly(self.categorized)

    def rec_roadmap(self):
        self._require_run()
        return recommendations.roadmap(self.categorized)

    def rec_actions(self):
        items = recommendations.action_items(self.meetings)
        for it in items:
            it["status"] = self.action_status.get(it["id"], "open")
        done = sum(1 for it in items if it["status"] == "done")
        return {"items": items, "open": len(items) - done, "done": done}

    def set_action_status(self, action_id, status):
        ids = {it["id"] for it in recommendations.action_items(self.meetings)}
        if action_id not in ids:
            raise KeyError(action_id)
        self.action_status[action_id] = status
        log.info("action %s marked %s", action_id, status)
        return {"id": action_id, "status": status}

    # ----- comparison ---------------------------------------------------
    def _themes(self, meetings, scored, cfg):
        names = list(cfg["themes"]) + ["Other"]
        by_type = meetings.groupby(["theme", "call_type"]).size().unstack(fill_value=0)
        sent = scored.groupby("theme")["sentiment_score"].mean()
        rows = []
        for name in names:
            counts = by_type.loc[name] if name in by_type.index else pd.Series(dtype=int)
            rows.append({
                "theme": name,
                "meetings": int(counts.sum()) if len(counts) else 0,
                "by_call_type": {t: int(counts.get(t, 0)) for t in CALL_TYPES},
                "sentiment": _num(sent.get(name)),
            })
        return rows

    def _sentiment_by_call_type(self, sentences):
        out = {}
        for call_type, g in sentences.groupby("call_type"):
            out[call_type] = {
                "pct_positive": _num((g["sentiment_label"] == "positive").mean()),
                "pct_negative": _num((g["sentiment_label"] == "negative").mean()),
                "mean_vader": _num(g["vader"].mean()),
            }
        return out

    def _outage_split(self, meetings, outage):
        m = meetings.copy()
        m["after"] = m["start"] >= outage
        out = {}
        for call_type, g in m.groupby("call_type"):
            before = g[~g["after"]]["sentiment_score"]
            after = g[g["after"]]["sentiment_score"]
            out[call_type] = {
                "before": _num(before.mean()), "before_n": int(len(before)),
                "after": _num(after.mean()), "after_n": int(len(after)),
            }
        return out

    def _meetings(self, meetings):
        return [
            {
                "meeting_id": r.meeting_id,
                "title": r.title,
                "call_type": r.call_type,
                "theme": r.theme,
                "sentiment_score": _num(r.sentiment_score),
            }
            for r in meetings.itertuples()
        ]

    def _changes(self, result):
        """Compare with the previous run so a config edit shows what moved."""
        prev = self.latest
        if prev is None:
            return {"first_run": True, "theme_deltas": [], "moved_meetings": []}
        prev_counts = {t["theme"]: t["meetings"] for t in prev["themes"]}
        deltas = [
            {"theme": t["theme"], "before": prev_counts.get(t["theme"], 0),
             "after": t["meetings"], "delta": t["meetings"] - prev_counts.get(t["theme"], 0)}
            for t in result["themes"]
        ]
        prev_theme = {m["meeting_id"]: m["theme"] for m in prev["meetings"]}
        moved = [
            {"meeting_id": m["meeting_id"], "title": m["title"],
             "from": prev_theme.get(m["meeting_id"]), "to": m["theme"]}
            for m in result["meetings"]
            if prev_theme.get(m["meeting_id"]) != m["theme"]
        ]
        return {"first_run": False, "theme_deltas": deltas, "moved_meetings": moved}
