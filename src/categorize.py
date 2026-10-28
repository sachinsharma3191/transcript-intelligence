"""Topic categorization: rule-based scoring with a clustering cross-check.

Why rule-based first? The dataset is ~100 meetings with an LLM-written summary
and topic tags already attached, so a transparent keyword taxonomy is easy to
audit with a panel and to change when a stakeholder disagrees. An unsupervised
TF-IDF + KMeans run is used only as an independent check on whether the
taxonomy matches the structure in the text.
"""
import re

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import adjusted_rand_score

# Theme -> keyword stems. Matched as substrings of lower-cased text.
THEMES = {
    "Outage & reliability": [
        "outage", "incident", "pipeline", "downtime", "latency", "delayed",
        "failover", "reliability", "post-mortem", "postmortem", "circuit breaker",
        "visibility", "ingestion", "war room", "dashboard down", "alerts not firing",
    ],
    "Compliance & audit": [
        "soc 2", "iso 27001", "hipaa", "pci", "compliance", "audit", "evidence",
        "framework", "regulat",
    ],
    "Billing & renewals": [
        "renewal", "billing", "invoice", "overage", "pricing", "contract",
        "license", "proration", "seat", "multi-year", "renew",
    ],
    "Identity & access": [
        "sso", "saml", "scim", "mfa", "ldap", "identity", "totp", "okta",
        "access control", "privileged", "provisioning", "role management",
    ],
    "Backup & recovery": [
        "backup", "restore", "s3", "disaster recovery", "throughput",
    ],
    "Product & roadmap": [
        "roadmap", "feature", "sprint", "launch", "release", "design review",
        "planning", "retro", "backlog", "early access", "demo", "bug", "product feedback",
    ],
    "Onboarding & deployment": [
        "onboarding", "kickoff", "deployment", "setup", "implementation", "rollout",
    ],
    "Integrations & API": [
        "connector", "integration", "api", "siem", "logvault", "webhook", "rate limit",
    ],
    "Competitive intelligence": [
        "competit", "sentinelshield", "win/loss", "vendor comparison", "displacement",
    ],
}

TITLE_WEIGHT = 3  # a keyword in the title is a much stronger signal than in the summary


def _count_hits(text, keywords):
    text = text.lower()
    return sum(len(re.findall(re.escape(k), text)) for k in keywords)


def score_themes(meetings, themes=THEMES, title_weight=TITLE_WEIGHT):
    """Return a DataFrame of per-theme scores, one row per meeting."""
    scores = {}
    for theme, keywords in themes.items():
        title_hits = meetings["title"].map(lambda t: _count_hits(t, keywords))
        body = meetings["summary"] + " " + meetings["topics"].map(" ".join)
        body_hits = body.map(lambda t: _count_hits(t, keywords))
        scores[theme] = title_weight * title_hits + body_hits
    return pd.DataFrame(scores, index=meetings.index)


def categorize(meetings, themes=THEMES, title_weight=TITLE_WEIGHT):
    scores = score_themes(meetings, themes, title_weight)
    out = meetings.copy()
    best = scores.idxmax(axis=1)
    best[scores.max(axis=1) == 0] = "Other"
    out["theme"] = best
    out["theme_scores"] = scores.to_dict("records")
    # Secondary themes: any theme that scores at least 3 and is not the primary one.
    out["secondary_themes"] = [
        [t for t, v in row.items() if v >= 3 and t != primary]
        for row, primary in zip(scores.to_dict("records"), best)
    ]
    out["mentions_outage"] = scores["Outage & reliability"] >= 3
    return out


def cluster_check(meetings, k=9, seed=7):
    """Unsupervised cross-check: TF-IDF on summary text + KMeans.

    Returns the adjusted Rand index against the rule-based theme (1.0 = identical
    partition, ~0 = no better than chance) and the top terms per cluster so a
    reader can judge whether the clusters mean something.
    """
    text = meetings["summary"] + " " + meetings["topics"].map(" ".join)
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2)
    X = vec.fit_transform(text)
    labels = KMeans(n_clusters=k, random_state=seed, n_init=10).fit_predict(X)
    ari = adjusted_rand_score(meetings["theme"], labels)
    terms = vec.get_feature_names_out()
    top = {}
    km = KMeans(n_clusters=k, random_state=seed, n_init=10).fit(X)
    for c, centre in enumerate(km.cluster_centers_):
        top[c] = [terms[i] for i in centre.argsort()[::-1][:5]]
    return ari, labels, top


if __name__ == "__main__":
    from load import load_meetings

    m = categorize(load_meetings())
    print(m["theme"].value_counts())
    print(pd.crosstab(m["theme"], m["call_type"]))
    ari, _, top = cluster_check(m)
    print("ARI vs rules:", round(ari, 3))
    for c, t in top.items():
        print(c, t)
