# Airline codes

- Ferrite's own list of airline codes, for the radio's ACARS display: a flight ID like `AC0123` shows as "Air Canada".
- Written by hand, each airline checked on its own, not copied from any dataset. CC0 1.0, public domain ([LICENCE-DATA.md](LICENCE-DATA.md)).
- Currently operating airlines only. A code we weren't sure of is left out rather than guessed.
- Shared or left-out codes: [shared-codes.md](shared-codes.md).
- Wrong or missing airline? Open an issue on FerriteFW/data on GitHub with the codes and a source.

## Columns (`airlines.csv`)

- `iata`: the 2-character IATA designator (letters or digits: `AC`, `9K`). Sorted by it; each once.
- `icao`: the 3-letter ICAO designator; empty when we don't know it. Each once.
- `name`: the short name for a small screen, at most 24 ASCII characters, in the airline's own spelling.
- `country`: where the airline is based, ISO 3166-1 alpha-2.
- `note`: empty, `cargo` (freight carriers) or `regional` (flies under a mainline brand).

`check.py` and `test_airlines.py` (at the root) check all of the above.
