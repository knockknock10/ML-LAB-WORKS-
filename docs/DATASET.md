# Dataset Notes

## Bundled demonstration fixture

SoundScout ships two small CSV files:

- music-recommendation/data/tracks.csv — synthetic catalogue metadata.
- music-recommendation/data/interactions.csv — synthetic listener interaction events.

The track catalogue contains 24 invented tracks distributed across Pop, Indie, Electronic, Jazz, Ambient and Hip-Hop. Track artists and albums are fictional. The audio previews are generated as original short synthesised sounds when the application starts; no commercial recording is bundled.

The interaction file contains 8 synthetic profiles with play, complete, repeat, like and skip events. The demo account username is demo, and its database user ID is demo so the account resolves to its seeded sample interaction profile.

This fixture is small enough for tests and demonstrations. Do not use its offline metrics as evidence of real recommendation performance.

## CSV schemas

### tracks.csv

| Column | Meaning |
|---|---|
| track_id | Stable application identifier |
| title, artist, album | Track metadata |
| genre, mood, tags | Text attributes for content filtering |
| energy, danceability, valence | Normalised numeric descriptors from 0 to 1 |
| tempo | Tempo in beats per minute |
| acousticness, instrumentalness | Normalised descriptors from 0 to 1 |
| audio_file | Relative filename generated in data/audio |

The six numeric descriptors are illustrative metadata values for this demo. They are not extracted from the generated preview files.

### interactions.csv

| Column | Meaning |
|---|---|
| user_id | Demo user/profile identifier |
| track_id | Track identifier present in tracks.csv |
| event_type | play, complete, repeat, like or skip |
| timestamp | UTC event timestamp in ISO-8601 format |

Real data adapters should map source event schemas into this canonical format. Ensure unknown track IDs and malformed timestamps are filtered or reported, not silently mapped to unrelated tracks.

## Real dataset options

### Million Song Dataset and Taste Profile

The Million Song Dataset provides metadata and derived audio features for a million tracks. The core dataset does not include the actual audio recordings. It also links to companion datasets, including the Taste Profile subset, which contains user-track listening count information.

Official source: https://millionsongdataset.com/

The Taste Profile subset is a reasonable first real collaborative-filtering source. Check the dataset's current terms and the terms of all companion data before use. Create a stable join between the dataset's track identifiers and the application track catalogue; unmatched records should not be guessed or joined by title alone.

### Last.fm Dataset — 1K users

The Last.fm 1K dataset contains timestamped user listening events. Its published record reports 19,150,868 event rows from 992 unique users and provides user, timestamp, artist and track fields. It is suitable for a time-ordered implicit-feedback experiment after data cleaning.

Dataset record: https://zenodo.org/records/6090214

The published dataset is made available for non-commercial use and asks users to reference Last.fm. Review the record and applicable terms before using or redistributing it; do not assume commercial reuse is permitted.

## Recommended real-data preprocessing

1. Download data directly from the official dataset source and record the version/date.
2. Preserve original identifiers, timestamps and source fields in a raw local directory; do not commit the raw dataset to Git.
3. Remove malformed rows, empty user/track identifiers and invalid timestamps.
4. Map each source record to the canonical user_id, track_id, event_type, timestamp schema.
5. Aggregate repeated user-track events with a documented rule.
6. For a Last.fm event stream, a repeated play can be represented as play or repeat; do not invent likes or completion events if the source does not contain them.
7. Use a time-ordered train/validation/test split to avoid training on events that happen after the test period.
8. Report the number of users, tracks, interactions, sparsity, time range and filters applied.
9. Keep copyrighted recordings and cover art out of the repository unless the team has documented permission to use them.

## Suggested next research step

Implement a separate adapter for the chosen real dataset and compare it with the bundled synthetic fixture. Keep the synthetic CSVs as a deterministic smoke-test dataset so tests do not require large downloads or external network access.
