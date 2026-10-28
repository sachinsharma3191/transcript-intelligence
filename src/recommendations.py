"""The four recommendations, each as something the app can show.

1. Churn list for account managers        -> churn()
2. Weekly external sentiment + outage mentions by call type -> weekly()
3. Roadmap priorities from feature-gap evidence             -> roadmap()
4. Action-item tracker (open / done)                        -> actions()

Pure functions over the categorized meetings, so the pipeline can call them
for the latest run. Action status is kept by the caller, because the dataset
has no completion data.
"""
import pandas as pd

import insights

OUTAGE_THEME = "Outage & reliability"
# A week is flagged when external sentiment drops below SENTIMENT_ALERT, or when
# outage talk is at least OUTAGE_SHARE_ALERT of external calls and sentiment is
# below OUTAGE_SENTIMENT_ALERT. The second rule needs both, so busy outage weeks
# with healthy sentiment are not flagged.
SENTIMENT_ALERT = 3.5
OUTAGE_SHARE_ALERT = 0.5
OUTAGE_SENTIMENT_ALERT = 4.0

# Roadmap groups, matched against feature-gap moment text in this order.
ROADMAP_GROUPS = [
    ("Proactive overage alerts", ["overage", "seat", "threshold", "alert"]),
    ("Compliance report formats", ["report", "format", "soc 2", "hipaa", "iso", "pci", "template", "compliance"]),
]


def churn(meetings):
    df = insights.churn_early_warning(meetings)
    return [
        {"account": r.account, "churn_signals": int(r.churn_signals),
         "touchpoints": int(r.touchpoints), "after_outage": bool(r.after_outage),
         "latest_signal": pd.Timestamp(r.latest_signal).isoformat()}
        for r in df.itertuples()
    ]


def weekly(meetings):
    m = meetings.assign(
        week=meetings["start"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time,
        touches_outage=meetings.apply(
            lambda r: r["theme"] == OUTAGE_THEME or OUTAGE_THEME in r["secondary_themes"], axis=1),
    )
    rows = []
    for (week, call_type), g in m.groupby(["week", "call_type"]):
        sentiment = round(float(g["sentiment_score"].mean()), 2)
        outage_share = round(float(g["touches_outage"].mean()), 2)
        alert = call_type == "external" and (
            sentiment < SENTIMENT_ALERT
            or (outage_share >= OUTAGE_SHARE_ALERT and sentiment < OUTAGE_SENTIMENT_ALERT)
        )
        rows.append({
            "week": pd.Timestamp(week).isoformat(), "call_type": call_type,
            "meetings": int(len(g)), "sentiment": sentiment,
            "outage_share": outage_share, "alert": bool(alert),
        })
    return {
        "thresholds": {
            "sentiment_below": SENTIMENT_ALERT,
            "outage_share_at_or_above": OUTAGE_SHARE_ALERT,
            "outage_sentiment_below": OUTAGE_SENTIMENT_ALERT,
        },
        "rows": sorted(rows, key=lambda r: (r["week"], r["call_type"])),
    }


def roadmap(meetings):
    moments = []
    for r in meetings.itertuples():
        for k in r.key_moments:
            if k["type"] == "feature_gap":
                moments.append({"text": k["text"], "call_type": r.call_type, "theme": r.theme})

    buckets = {name: [] for name, _ in ROADMAP_GROUPS}
    other = {}
    for mo in moments:
        text = mo["text"].lower()
        for name, words in ROADMAP_GROUPS:
            if any(w in text for w in words):
                buckets[name].append(mo)
                break
        else:
            other.setdefault(mo["theme"], []).append(mo)

    items = [_item(name, rows, recommended=True) for name, rows in buckets.items()]
    items += [_item(theme, rows, recommended=False) for theme, rows in other.items()]
    items.sort(key=lambda i: (-i["recommended"], -i["evidence"]))
    return {"items": items}


def _item(title, rows, recommended):
    return {
        "title": title,
        "recommended": recommended,
        "evidence": len(rows),
        "external": sum(1 for r in rows if r["call_type"] == "external"),
        "examples": [r["text"] for r in rows[:3]],
    }


def action_items(meetings):
    out = []
    for r in meetings.itertuples():
        for i, text in enumerate(r.action_items):
            owner, _, task = text.partition(":")
            if not task or len(owner.split()) > 4:
                owner, task = "Unassigned", text
            out.append({
                "id": f"{r.meeting_id[:10]}-{i}",
                "owner": owner.strip(),
                "task": task.strip(),
                "meeting": r.title,
                "call_type": r.call_type,
            })
    return out
