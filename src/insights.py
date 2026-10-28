"""Bonus insights: account health, churn early warning, product demand, competitive pressure.

Each function returns a small DataFrame so the numbers used in the deck can be
regenerated from the command line (see run_analysis.py).
"""
import collections

import pandas as pd

from sentiment import OUTAGE_DATE


def _key_moments(meetings):
    rows = []
    for r in meetings.itertuples():
        for k in r.key_moments:
            rows.append({"meeting_id": r.meeting_id, "title": r.title, "call_type": r.call_type,
                         "theme": r.theme, "start": r.start, "type": k["type"],
                         "text": k["text"], "speaker": k["speaker"]})
    return pd.DataFrame(rows)


def account_of(meetings):
    """Account = the customer domain on an external or support call."""
    acc = meetings["external_domains"].str.split(",").str[0]
    return acc.where(meetings["call_type"] != "internal", None)


def churn_early_warning(meetings):
    """Accounts with churn signals, ranked by how many touchpoints show them.

    An account counts as at risk if at least one of its calls contains a
    churn_signal key moment. Column `after_outage` shows whether the signal is
    from the post-outage period, which is when the team should be reacting.
    """
    km = _key_moments(meetings)
    km = km.merge(meetings[["meeting_id"]].assign(account=account_of(meetings)), on="meeting_id")
    churn = km[(km["type"] == "churn_signal") & km["account"].notna()].copy()
    churn["after_outage"] = churn["start"] >= OUTAGE_DATE
    out = (
        churn.groupby("account")
        .agg(churn_signals=("text", "size"),
             touchpoints=("meeting_id", "nunique"),
             latest_signal=("start", "max"),
             after_outage=("after_outage", "max"))
        .sort_values(["churn_signals", "latest_signal"], ascending=False)
    )
    return out.reset_index()


def feature_demand(meetings):
    """Feature-gap moments grouped by theme: where customers and staff ask for things."""
    km = _key_moments(meetings)
    gaps = km[km["type"] == "feature_gap"]
    return (gaps.groupby(["theme", "call_type"]).size().unstack(fill_value=0)
            .assign(total=lambda d: d.sum(axis=1))
            .sort_values("total", ascending=False))


def competitor_pressure(sentences, meetings):
    """Weekly mention rate of SentinelShield in transcripts (per 100 meetings)."""
    hits = sentences[sentences["sentence"].str.contains("SentinelShield", case=False)]
    per_week = meetings.assign(week=meetings["start"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time)
    weeks = per_week.groupby("week").size().rename("meetings")
    mentioned = hits.assign(week=hits["start"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time)
    mentioned = mentioned.groupby("week")["meeting_id"].nunique().rename("meetings_mentioning")
    out = pd.concat([weeks, mentioned], axis=1).fillna(0).astype(int)
    out["pct_mentioning"] = (out["meetings_mentioning"] / out["meetings"] * 100).round(1)
    return out


def support_repeat_accounts(meetings):
    """Accounts with more than one support case: a sign that the first fix didn't hold."""
    sup = meetings[meetings["call_type"] == "support"].assign(account=lambda d: account_of(d))
    counts = sup.groupby("account").agg(cases=("meeting_id", "size"),
                                         avg_sentiment=("sentiment_score", "mean"))
    return counts[counts["cases"] > 1].sort_values("cases", ascending=False).reset_index()


def action_items(meetings):
    """Action items per call type. The dataset has no completion status, so this only sizes the load."""
    return meetings.assign(n_actions=meetings["action_items"].map(len)).groupby("call_type")["n_actions"].agg(["mean", "sum"])
