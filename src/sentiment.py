"""Sentiment analysis across call types and over time.

Two signals per sentence:
  1. The label shipped with the transcript (`sentiment_label`), which the
     dataset's producer generated.
  2. VADER compound score, computed here, as an independent check on (1).
Meeting-level score = mean VADER compound of its sentences, and we also keep
the share of negative sentences, which is easier to read than a mean.
"""
import pandas as pd
from sklearn.metrics import cohen_kappa_score
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

OUTAGE_DATE = pd.Timestamp("2026-03-10", tz="UTC")  # six-hour Detect outage starts here


def add_vader(sentences):
    analyzer = SentimentIntensityAnalyzer()
    s = sentences.copy()
    s["vader"] = s["sentence"].map(lambda t: analyzer.polarity_scores(t)["compound"])
    # Map the compound score onto the same three labels VADER's own docs use.
    s["vader_label"] = pd.cut(
        s["vader"], bins=[-1.01, -0.05, 0.05, 1.01], labels=["negative", "neutral", "positive"]
    ).astype(str)
    return s


def agreement(sentences):
    """Cohen's kappa between the shipped labels and VADER labels."""
    return cohen_kappa_score(sentences["sentiment_label"], sentences["vader_label"])


def by_call_type(sentences):
    g = sentences.groupby("call_type")
    return pd.DataFrame(
        {
            "sentences": g.size(),
            "pct_positive": g["sentiment_label"].apply(lambda x: (x == "positive").mean()),
            "pct_negative": g["sentiment_label"].apply(lambda x: (x == "negative").mean()),
            "mean_vader": g["vader"].mean(),
        }
    )


def meeting_scores(sentences, meetings):
    g = sentences.groupby("meeting_id")
    scores = pd.DataFrame(
        {
            "mean_vader": g["vader"].mean(),
            "pct_negative": g["sentiment_label"].apply(lambda x: (x == "negative").mean()),
        }
    ).reset_index()
    return meetings.merge(scores, on="meeting_id")


def outage_split(meetings):
    """Compare each call type before and after the March 10 outage."""
    m = meetings.copy()
    m["period"] = (m["start"] >= OUTAGE_DATE).map({True: "after outage", False: "before outage"})
    return (
        m.groupby(["call_type", "period"])
        .agg(meetings=("meeting_id", "size"), sentiment=("sentiment_score", "mean"))
        .round(2)
    )


def weekly_trend(meetings):
    m = meetings.copy()
    m["week"] = m["start"].dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    return (
        m.groupby(["week", "call_type"])["sentiment_score"]
        .agg(["mean", "size"])
        .reset_index()
        .rename(columns={"mean": "mean_sentiment_score", "size": "meetings"})
    )


if __name__ == "__main__":
    from categorize import categorize
    from load import load_meetings, load_sentences

    meetings = categorize(load_meetings())
    sentences = load_sentences(meetings)
    sentences = add_vader(sentences)
    sentences = sentences.merge(meetings[["meeting_id", "theme"]], on="meeting_id")
    print("kappa shipped vs VADER:", round(agreement(sentences), 3))
    print(by_call_type(sentences).round(3))
    print(outage_split(meetings))
    print(weekly_trend(meetings).head(12))
    ms = meeting_scores(sentences, meetings)
    print(ms.groupby("theme")[["sentiment_score", "mean_vader", "pct_negative"]].mean().round(2))
