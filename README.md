# Ferrite channel-library data

Licensed land-mobile sites, airport frequencies and amateur repeaters, split by map square, for Ferrite Console's channel library.
Served at https://data.ferritefw.dev.

## What's here

- `tafl/`: Canada, from ISED's Spectrum Management System extract (the TAFL). Licence: Open Government Licence – Canada ([tafl/LICENCE-DATA.md](tafl/LICENCE-DATA.md)).
- `fcc/`: US, from the FCC's ULS weekly files (Land Mobile – Private and Commercial). Public domain in the US ([fcc/LICENCE-DATA.md](fcc/LICENCE-DATA.md)).
- `airports/`: the world's airport frequencies (108-137 MHz), from OurAirports. Public domain ([airports/LICENCE-DATA.md](airports/LICENCE-DATA.md)).
- `repeaters/`: the world's operational analog FM amateur repeaters on 2 m, 1.25 m and 70 cm, from HearHam (user-contributed). Free to use in applications, per HearHam.com; no formal data licence ([repeaters/LICENCE-DATA.md](repeaters/LICENCE-DATA.md)).
- `common/`: shared code: bands, name shortening, emission modes, categories, tiles. Tests: `python3 -m unittest`.
- `build.py`: builds every source into `out/`.
- `.forgejo/workflows/publish.yml`: the monthly build, on Forgejo's runner at home (the FCC refuses GitHub's runners). Force-pushes `out/` to the `gh-pages` branch here.
- `.github/workflows/pages.yml`: the same by hand on GitHub, as a fallback (Canada and airports refresh; the FCC keeps its last copy).
- `landing.py`: writes the landing page (`index.html`) from the build's index.
- `check.py`: both workflows' check that each source looks whole before publishing.

## Rebuild

```sh
python3 build.py --cache ~/ferrite-data-cache            # reuses cached downloads
python3 build.py --cache ~/ferrite-data-cache --download # fetches fresh copies
python3 build.py --cache ~/ferrite-data-cache --only tafl
```

- Python 3.9 or newer, standard library only.
- Downloads: TAFL 64 MB, FCC 505 MB (zips read in place, never unzipped), OurAirports about 15 MB of CSV, HearHam about 10 MB of JSON.
- Keep the cache outside the repository.
- About 1.5 minutes and 1.6 GB of memory (the FCC join).
- A source that fails to build (a refused download) keeps its last published copy from data.ferritefw.dev, or is left out if there is none; the others still deploy.

## Output

- `index.json`: build date and the sources (title, source date, licence, attribution, row and tile counts).
- `<source>/index.json`: the same for one source, plus `format`, `level` (2 or 4: the tiles' grid size), and `tiles`: tile -> row count.
- Airports' and repeaters' tiles are 2-character fields (`airports/CN.json`, 20 x 10 degrees): the data is small.
- The other sources' tiles are 4-character grid squares (`CN89.json`). A square over 6,000 rows (big cities) is published only as its 6-character subsquares (`CN89kg.json`) and listed in `split`.
  Empty subsquares have no file.
- `<source>.zip`: the whole source in one download (its index and every tile), for apps that keep everything offline. The top-level `index.json` gives its size and SHA-256.
- A tile (`format`: `columnar-1`) is columns, one entry per row, in latitude, longitude, frequency order:
  - `n`: the tile's licensee names, each once, shortened to 16 characters.
  - `c`: the row's name, as an index into `n`.
  - `a`, `o`: latitude and longitude in 1/100,000 degree (WGS84), each the difference from the row before (the first from 0).
  - `f`: transmit frequency in half kHz (469.9875 MHz is 939975), the difference from the row before.
  - `m`: mode: 0 analog FM under 14 kHz (NFM), 1 analog FM 16-20 kHz, 3 unknown. Missing when every row is unknown (airports: airband is AM).
    2 (digital or data only) is reserved: digital-only licences are left out, as Ferrite has no digital modes.
  - `s`: 1 when the frequency is a mobile's (often a repeater input, or the centre of a mobile area); 0 for bases, repeaters and fixed stations. Missing when every row is 0.
  - `k`: the licensee's category: 0 business or other, 1 public safety, 2 transit and rail, 3 utilities, 4 marine and ports, 5 schools, 6 government.
    From the FCC radio service where it decides (the Public Safety Pool), else keywords in the licensee's full name (`common.category`).
    Missing when every row is 0 (airports never have it).
  - `d`: repeaters only: the offset, input minus output, in half kHz (-600 kHz is -1200; 0 simplex). Not a difference: each row's own value.
    The radio transmits on `f + d`.
  - `pn`, `pe`, `pd`: repeaters only: tones. `pn` lists the tile's tones once; `pe` (encode: the tone to transmit to open the repeater) and `pd` (decode: the tone it sends, for tone squelch) index it (-1: none).
    A tone is CTCSS in Hz with one decimal (`100.0`), or DCS as `D` and three octal digits (`D023`; `D023I` inverted).
    HearHam's own spellings (`100`, `151.4*`, `DCS 43`, `NAC293/100.0`) are read into these forms (`common.tone`); a value that's no standard tone is none.
    Missing when a tile has no tones.
  - `tn`, `t`: the frequency's use (airports: `TWR`, `GND`, `ATIS`, `CTAF`, ...), as OurAirports writes it: `tn` lists the tile's uses once, `t` indexes it (-1: none). Missing when a source has none.
- To read a tile: keep running sums of `a`, `o` and `f`; latitude = a / 1e5, longitude = o / 1e5, MHz = f / 2000.
- Bands: 136-174 and 400-470 MHz; airports 108-137 MHz; repeaters 136-174, 219-225 and 400-470 MHz (output and input both).
- Repeaters' `m` is 0 where HearHam says NFM, else unknown: its FM doesn't say how wide (12.5 kHz in Europe, 20 in North America).
- `stats.csv` (at the root): one line per source per build: `build_date`, `source`, `rows`, and for repeaters the raw feed's `feed_operational` (entries marked operational), `feed_max_id` (its highest id) and `feed_entries` (every entry); empty for the others.
  Each build carries the live site's earlier lines forward and adds its own (a rebuild the same day replaces that day's).
- Rows are unique by name, frequency and position.

## Hosting

- GitHub Pages from the `gh-pages` branch (one fresh commit per build), custom domain `data.ferritefw.dev` (`CNAME`).
- The repository is on GitHub (FerriteFW/data) and Forgejo (ferrite/data); push to both.
- Pages sends `Access-Control-Allow-Origin: *`, so any site can fetch the tiles.
- Wanted later, if a proxy (e.g. Cloudflare) goes in front: allow only `https://console.ferritefw.dev`, the Tauri app (`tauri://localhost`, `http://tauri.localhost`) and `localhost` for development.
- A failed build deploys nothing: the last good copy stays up.

## Licence

- Scripts: PolyForm Noncommercial 1.0.0, Alex Harvey ([LICENSE.md](LICENSE.md)).
- Data: each source keeps its own licence (above).
