"""Load the transcript dataset into flat pandas tables.

One row per meeting (metadata + summary) and one row per sentence (transcript).
Call type is derived from who was on the call: any attendee outside the
aegiscloud.com domain makes it an external call, and the title prefix
"Support Case #" marks the support queue.
"""
import json
import os
from pathlib import Path

import pandas as pd

# DATASET_DIR lets Docker point at a mounted copy; locally it is the sibling dataset/ folder.
DATASET = Path(os.environ.get("DATASET_DIR", Path(__file__).resolve().parents[1] / "dataset"))
INTERNAL_DOMAIN = "aegiscloud.com"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_meetings(dataset=DATASET):
    rows = []
    for folder in sorted(p for p in dataset.iterdir() if p.is_dir()):
        info = _read(folder / "meeting-info.json")
        summary = _read(folder / "summary.json")
        emails = info["allEmails"]
        external_domains = sorted(
            {e.split("@", 1)[1] for e in emails if not e.endswith("@" + INTERNAL_DOMAIN)}
        )
        rows.append(
            {
                "meeting_id": info["meetingId"],
                "title": info["title"],
                "start": pd.to_datetime(info["startTime"]),
                "duration_min": info["duration"],
                "n_attendees": len(emails),
                "external_domains": ",".join(external_domains),
                "is_external": bool(external_domains),
                "summary": summary["summary"],
                "topics": summary["topics"],
                "action_items": summary["actionItems"],
                "key_moments": summary["keyMoments"],
                "overall_sentiment": summary["overallSentiment"],
                "sentiment_score": summary["sentimentScore"],
            }
        )
    meetings = pd.DataFrame(rows)
    meetings["call_type"] = meetings.apply(classify_call_type, axis=1)
    return meetings


def classify_call_type(row):
    if row["title"].startswith("Support Case #"):
        return "support"
    if row["is_external"]:
        return "external"
    return "internal"


def load_sentences(meetings, dataset=DATASET):
    frames = []
    for mid in meetings["meeting_id"]:
        data = _read(dataset / mid / "transcript.json")["data"]
        df = pd.DataFrame(data)
        df["meeting_id"] = mid
        frames.append(df)
    sentences = pd.concat(frames, ignore_index=True)
    sentences = sentences.merge(
        meetings[["meeting_id", "title", "call_type", "start"]], on="meeting_id"
    )
    return sentences.rename(columns={"sentimentType": "sentiment_label", "speaker_name": "speaker"})


if __name__ == "__main__":
    m = load_meetings()
    s = load_sentences(m)
    print(m["call_type"].value_counts())
    print(len(s), "sentences")
    print(s["sentiment_label"].value_counts())


def add_speaker_side(sentences, meetings, dataset=DATASET):
    """Label each sentence's speaker as vendor (Aegis employee), customer, or internal.

    Attendee emails give us the vendor names per meeting. In an external meeting,
    any speaker who is not a vendor attendee is treated as the customer side.
    """
    vendors = {}
    for mid in meetings["meeting_id"]:
        info = _read(dataset / mid / "meeting-info.json")
        vendors[mid] = {
            " ".join(p.capitalize() for p in e.split("@")[0].split("."))
            for e in info["allEmails"]
            if e.endswith("@" + INTERNAL_DOMAIN)
        }
    external = dict(zip(meetings["meeting_id"], meetings["is_external"]))

    def side(row):
        if row["speaker"] in vendors[row["meeting_id"]]:
            return "vendor"
        return "customer" if external[row["meeting_id"]] else "internal"

    sentences = sentences.copy()
    sentences["side"] = sentences.apply(side, axis=1)
    return sentences
