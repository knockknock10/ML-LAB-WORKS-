"""Convert the public Last.fm 1K TSV into SoundScout's canonical CSV schema.

The source data is not bundled. Download it from its official record and
review its non-commercial-use terms before running this importer.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
SOURCE_COLUMNS = [
    "source_user_id",
    "timestamp",
    "artist_mbid",
    "artist_name",
    "source_track_id",
    "track_name",
]
TRACK_COLUMNS = [
    "track_id", "title", "artist", "album", "genre", "mood", "tags",
    "energy", "danceability", "valence", "tempo", "acousticness",
    "instrumentalness", "audio_file",
]


def _clean(value: object) -> str:
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null", "\\n"} or text == r"\N" else text


def _track_id(track_mbid: str, artist: str, title: str) -> str:
    if track_mbid:
        identity = "mbid:" + track_mbid.casefold()
    else:
        identity = "fallback:" + artist.casefold() + "\0" + title.casefold()
    return "lfm_" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:20]


def import_lastfm(
    source: Path,
    output_dir: Path,
    *,
    max_users: int = 150,
    max_events: int = 250_000,
    chunksize: int = 100_000,
    min_track_plays: int = 2,
    demo_source_user_id: str = "",
) -> dict[str, int]:
    if not source.is_file():
        raise FileNotFoundError("Input TSV file not found: " + str(source))
    if max_users < 0 or max_events < 0 or chunksize < 1 or min_track_plays < 1:
        raise ValueError("Limits must be non-negative and chunksize/min_track_plays must be positive.")

    output_dir.mkdir(parents=True, exist_ok=True)
    selected_users: set[str] = set()
    tracks: dict[str, dict[str, str | float]] = {}
    events: list[tuple[str, str, str, str]] = []
    track_counts: Counter[str] = Counter()

    reader = pd.read_csv(
        source,
        sep="\t",
        header=None,
        names=SOURCE_COLUMNS,
        dtype=str,
        keep_default_na=False,
        chunksize=chunksize,
        quoting=csv.QUOTE_NONE,
        on_bad_lines="skip",
    )

    for chunk in reader:
        for column in SOURCE_COLUMNS:
            if column not in chunk.columns:
                chunk[column] = ""
        for column in SOURCE_COLUMNS:
            chunk[column] = chunk[column].map(_clean)

        chunk = chunk[
            (chunk["source_user_id"] != "")
            & (chunk["artist_name"] != "")
            & (chunk["track_name"] != "")
            & (chunk["timestamp"] != "")
        ]
        if chunk.empty:
            continue

        if max_users:
            for candidate in chunk["source_user_id"].drop_duplicates().tolist():
                if candidate not in selected_users and len(selected_users) < max_users:
                    selected_users.add(candidate)
            chunk = chunk[chunk["source_user_id"].isin(selected_users)]
            if chunk.empty:
                continue

        parsed_times = pd.to_datetime(chunk["timestamp"], utc=True, errors="coerce")
        chunk = chunk[parsed_times.notna()].copy()
        if chunk.empty:
            continue
        chunk["timestamp"] = parsed_times.loc[chunk.index].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        remaining = max_events - len(events) if max_events else len(chunk)
        if remaining <= 0:
            break
        if max_events:
            chunk = chunk.head(remaining)

        for row in chunk.itertuples(index=False):
            source_user_id = _clean(row.source_user_id)
            artist = _clean(row.artist_name)
            title = _clean(row.track_name)
            source_track_id = _clean(row.source_track_id)
            track_id = _track_id(source_track_id, artist, title)
            user_id = (
                "demo"
                if demo_source_user_id and source_user_id == demo_source_user_id
                else source_user_id
            )
            if track_id not in tracks:
                tracks[track_id] = {
                    "track_id": track_id,
                    "title": title,
                    "artist": artist,
                    "album": "",
                    "genre": "Unknown",
                    "mood": "",
                    "tags": "",
                    "energy": 0.0,
                    "danceability": 0.0,
                    "valence": 0.0,
                    "tempo": 0.0,
                    "acousticness": 0.0,
                    "instrumentalness": 0.0,
                    "audio_file": "",
                }
            events.append((user_id, track_id, "play", row.timestamp))
            track_counts[track_id] += 1

        if max_events and len(events) >= max_events:
            break

    keep_tracks = {
        track_id for track_id, count in track_counts.items()
        if count >= min_track_plays
    }
    events = [event for event in events if event[1] in keep_tracks]
    tracks = {track_id: track for track_id, track in tracks.items() if track_id in keep_tracks}

    if not events or not tracks:
        raise ValueError(
            "No usable listening events remained. Check the TSV format and lower --min-track-plays."
        )

    tracks_path = output_dir / "tracks.csv"
    interactions_path = output_dir / "interactions.csv"
    with tracks_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TRACK_COLUMNS)
        writer.writeheader()
        writer.writerows(tracks[track_id] for track_id in sorted(tracks))

    with interactions_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["user_id", "track_id", "event_type", "timestamp"])
        writer.writerows(events)

    return {
        "users": len({event[0] for event in events}),
        "tracks": len(tracks),
        "events": len(events),
        "track_csv_rows": len(tracks),
        "interaction_csv_rows": len(events),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tsv", type=Path, help="Extracted Last.fm 1K listening TSV file")
    parser.add_argument("--output-dir", type=Path, default=PROJECT_DIR / "data")
    parser.add_argument("--max-users", type=int, default=150, help="0 means no user limit (default: 150)")
    parser.add_argument("--max-events", type=int, default=250_000, help="0 means no event limit (default: 250000)")
    parser.add_argument("--chunksize", type=int, default=100_000)
    parser.add_argument("--min-track-plays", type=int, default=2)
    parser.add_argument(
        "--demo-source-user-id",
        default="",
        help="Optional Last.fm source user ID whose events should be mapped to the local demo account ID.",
    )
    args = parser.parse_args()

    try:
        stats = import_lastfm(
            args.tsv,
            args.output_dir,
            max_users=args.max_users,
            max_events=args.max_events,
            chunksize=args.chunksize,
            min_track_plays=args.min_track_plays,
            demo_source_user_id=args.demo_source_user_id,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))
    print("Created " + str(args.output_dir.resolve()))
    for key, value in stats.items():
        print(key + ": " + str(value))
    print("The imported catalogue has metadata only; add licensed audio separately if playback is required.")


if __name__ == "__main__":
    main()
