# Fixed channel sets

Hand-written, one file per radio region in `fixed/src/<REGION>.json`. The build publishes them as `fixed/` on
data.ferritefw.dev for Ferrite Console's library (Add from library › Fixed sets). Licence: CC0 1.0 (our own
compilation of facts; every set names where its frequencies come from).

Regions are the radio's: `US`, `CA`, `UK`, `EU`, `AU`, `NZ`, `JP`, `OTHER`.
`OTHER` holds what is the same everywhere (international marine VHF, aviation emergency, satellites) and is offered
in every region beside its own sets.

## A region file

```json
{
  "region": "UK",
  "name": "United Kingdom",
  "sets": [ SET, ... ],
  "splits": [ SPLIT, ... ]
}
```

## A set (Console's `FixedSet` keys, camelCase, plus `id`, `category`, `countries`, `source`)

```json
{
  "id": "uk-2m-simplex",
  "name": "2m simplex",
  "displayName": "2 m FM simplex (UK)",
  "description": "One line: what it is and who may use it.",
  "category": "amateur",
  "countries": ["GB"],
  "defaultPower": "Low",
  "defaultBandwidth": "12.5kHz",
  "defaultMode": "Analog",
  "rxOnly": false,
  "source": [{ "title": "RSGB VHF band plan", "url": "https://...", "date": "2025-01" }],
  "frequencies": [
    { "name": "V40 Calling", "rx": 145.500, "tx": 145.500 },
    { "name": "Rpt RB0", "rx": 145.600, "tx": 145.000, "ctcss": 77.0 }
  ]
}
```

- `id`: lower case, region prefix, unique across all files.
- `name`: the zone name the set lands in: 16 characters at most, printable ASCII.
- `category`: one of `amateur`, `licence-free`, `marine`, `weather`, `aviation`, `rail`, `emergency`, `satellite`,
  `business`.
- `countries` (optional): ISO 3166-1 alpha-2 codes (`DE`), or ISO 3166-2 for part of a country (`US-AK`,
  `CA-BC`), when the set applies only there. Missing: the whole region.
- `defaultBandwidth`: `"12.5kHz"` (NFM) or `"25kHz"` (FM). `defaultMode`: `"Analog"` or `"AM"`.
- `defaultPower`: `"Low"`, `"Mid"` or `"High"` (licence-free sets: `"Low"`).
- `rxOnly`: true for services a user can't transmit on without a station licence for that service (marine,
  aviation, weather, rail, business, emergency services). Amateur and licence-free sets are false: whether to
  transmit is the user's call. Licence-free sets default to `"Low"` power (the build checks it), and their
  description says what the service asks of a radio (certified equipment, power limits).
- `source`: at least one primary source per set (a regulator's rule or a national society's band plan), with the
  date or edition read. Never copy text from a source; frequencies and channel numbers are facts.
- A frequency: `name` (16 characters at most, ASCII; channel number first where there is one: `CH16 Distress`),
  `rx` and `tx` in MHz (equal for simplex; a repeater pair has `tx` = the input), optional `ctcss` (Hz) or `dcs`
  (octal as an integer, 23 for D023), optional `rxOnly`, optional `note` (one short line).
- Frequencies the radio can tune: 18-630 MHz and 756-1300 MHz. Leave out anything else (say so in a split or note).

## A split: where a country inside the region differs

```json
{ "country": "DE", "what": "Freenet 149.025-149.1125 MHz licence-free (not elsewhere in EU)",
  "sets": ["eu-de-freenet"], "source": [{ "title": "...", "url": "...", "date": "..." }] }
```

- One entry per country that differs from the region's sets (extra services, different calling frequencies, a
  service not allowed). `sets` names the country-only sets added for it (with `countries`), or is empty when the
  difference is a note only.

## Checking and adding

- `python3 -m unittest test_fixed` (from the repository root) checks every file; `python3 -m fixed.build --format`
  rewrites them in the checked-in layout (one line per frequency).
- A set backed only by secondary sources, or whose channel spacing we chose ourselves, stays out until a primary
  source confirms it.
- Corrections and new sets: [suggest one](https://github.com/FerriteFW/data/issues/new?template=fixed-set.yml) (a short form: region, set, the change, the source).
  Console's Fixed tab links to it with the region and set filled in (`&region=CA&set=ca-2m-simplex`).
