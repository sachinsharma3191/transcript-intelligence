"""Run the full pipeline end to end and write tables and charts to outputs/.

    ./.venv/bin/python src/run_analysis.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

import insights  # noqa: E402
import sentiment  # noqa: E402
from categorize import categorize, cluster_check  # noqa: E402
from load import add_speaker_side, load_meetings, load_sentences  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "outputs"
CHARTS = OUT / "charts"


def save(df, name, index=True):
    df.to_csv(OUT / f"{name}.csv", index=index)
    return df


def bar_chart(df, title, path, **kwargs):
    ax = df.plot(kind="bar", figsize=(9, 4.8), **kwargs)
    ax.set_title(title, loc="left", fontsize=12, weight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def main():
    OUT.mkdir(exist_ok=True)
    CHARTS.mkdir(exist_ok=True)

    meetings = categorize(load_meetings())
    sentences = sentiment.add_vader(load_sentences(meetings))
    sentences = add_speaker_side(sentences, meetings)
    sentences = sentences.merge(meetings[["meeting_id", "theme"]], on="meeting_id")
    meetings_scored = sentiment.meeting_scores(sentences, meetings)

    # 1. Categorization
    ari, labels, top_terms = cluster_check(meetings)
    cat_table = meetings[["meeting_id", "title", "call_type", "theme", "secondary_themes"]]
    save(cat_table, "categories_by_meeting", index=False)
    save(pd.crosstab(meetings["theme"], meetings["call_type"], margins=True), "theme_by_call_type")
    print(f"Clustering agreement with rule-based themes (ARI): {ari:.3f}")
    print(pd.crosstab(meetings["theme"], meetings["call_type"], margins=True))

    # 2. Sentiment
    print("Kappa shipped labels vs VADER:", round(sentiment.agreement(sentences), 3))
    corr = meetings_scored["sentiment_score"].corr(meetings_scored["mean_vader"])
    print("Meeting-level correlation, sentiment_score vs VADER mean:", round(corr, 3))
    save(sentiment.by_call_type(sentences), "sentiment_by_call_type")
    save(sentiment.outage_split(meetings), "sentiment_before_after_outage")
    save(sentiment.weekly_trend(meetings), "sentiment_weekly", index=False)
    save(meetings_scored.groupby("theme")[["sentiment_score", "mean_vader", "pct_negative"]].mean().round(3),
         "sentiment_by_theme")
    side = (sentences.groupby(["call_type", "side"])["sentiment_label"]
            .value_counts(normalize=True).unstack().round(3))
    save(side, "sentiment_by_side")

    # 3. Bonus insights
    churn = insights.churn_early_warning(meetings)
    save(churn, "churn_early_warning", index=False)
    save(insights.feature_demand(meetings), "feature_demand")
    save(insights.competitor_pressure(sentences, meetings), "competitor_pressure_weekly")
    save(insights.support_repeat_accounts(meetings), "support_repeat_accounts", index=False)
    save(insights.action_items(meetings), "action_items_by_call_type")

    # Charts
    by_type = sentiment.by_call_type(sentences)[["pct_positive", "pct_negative"]]
    bar_chart(by_type, "Sentence sentiment by call type", CHARTS / "sentiment_by_call_type.png",
              color=["#2a9d8f", "#e76f51"])

    before_after = sentiment.outage_split(meetings)["sentiment"].unstack()
    bar_chart(before_after, "Average sentiment score before/after the March 10 outage",
              CHARTS / "outage_before_after.png", color=["#8ab17d", "#e63946"])

    theme_scores = meetings_scored.groupby("theme")["sentiment_score"].mean().sort_values()
    bar_chart(theme_scores.to_frame("mean sentiment score"), "Sentiment score by theme",
              CHARTS / "sentiment_by_theme.png", color="#457b9d", legend=False)

    weekly = sentiment.weekly_trend(meetings).pivot(index="week", columns="call_type",
                                                    values="mean_sentiment_score")
    ax = weekly.plot(figsize=(9, 4.8), marker="o")
    ax.axvline(sentiment.OUTAGE_DATE.tz_localize(None), color="#e63946", linestyle="--")
    ax.set_title("Weekly sentiment score by call type (dashed = outage)", loc="left", weight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(CHARTS / "weekly_sentiment.png", dpi=150)
    plt.close()

    demand = insights.feature_demand(meetings).drop(columns="total")
    bar_chart(demand, "Feature-gap moments by theme", CHARTS / "feature_demand.png", stacked=True)


if __name__ == "__main__":
    main()
