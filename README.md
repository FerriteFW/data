# Ferrite channel-library data

Licensed land-mobile sites, split by map square, for Ferrite Console's channel library.
Served at https://data.ferritefw.dev.

## What's here

- `tafl/`: Canada, from ISED's Spectrum Management System extract (the TAFL). Licence: Open Government Licence – Canada ([tafl/LICENCE-DATA.md](tafl/LICENCE-DATA.md)).
- `fcc/`: US, from the FCC's ULS weekly files (Land Mobile – Private and Commercial). Public domain in the US ([fcc/LICENCE-DATA.md](fcc/LICENCE-DATA.md)).
- `common/`: shared code: bands, name shortening, emission modes, tiles.
- `build.py`: builds both into `out/`.
- `.github/workflows/pages.yml`: builds monthly (and by hand) and deploys `out/` to GitHub Pages.

## Rebuild

```sh
python3 build.py --cache ~/ferrite-data-cache            # reuses cached downloads
python3 build.py --cache ~/ferrite-data-cache --download # fetches fresh copies
python3 build.py --cache ~/ferrite-data-cache --only tafl
```

- Python 3.9 or newer, standard library only.
- Downloads: TAFL 64 MB, FCC 505 MB. The zips are read in place, never unzipped.
- Keep the cache outside the repository.
- About 1.5 minutes and 1.6 GB of memory (the FCC join).

## Output

- `index.json`: build date and the sources (title, source date, licence, attribution, row and tile counts).
- `<source>/index.json`: the same for one source, plus `tiles`: tile -> row count.
- Tiles are 4-character grid squares (`CN89.json`). A square over 6,000 rows (big cities) is published only as its 6-character subsquares (`CN89kg.json`) and listed in `split`.
  Empty subsquares have no file.
- `<source>.zip`: the whole source in one download (its index and every tile), for apps that keep everything offline. The top-level `index.json` gives its size and SHA-256.
- `<source>/<square>.json`: the rows in one 4-character Maidenhead square (`tafl/CN89.json`, `fcc/DM04.json`).
- A row: `{"c": name, "l": [lat, lon], "f": kHz, "m": mode, "s": "m"}`.
  - `c`: licensee, shortened to 16 characters.
  - `l`: WGS84 degrees, 5 decimals.
  - `f`: transmit frequency in kHz; half kHz kept (469.9875 MHz is `469987.5`).
  - `m`: `nfm` (analog FM under 14 kHz), `fm` (16-20 kHz), `dig` (digital or data only); missing if unknown.
  - `s`: `"m"` when the frequency is a mobile's (often a repeater input, or the centre of a mobile area); missing for bases, repeaters and fixed stations.
- Bands: 136-174 and 400-470 MHz.
- Rows are unique by name, frequency and position.

## Hosting

- GitHub Pages with the custom domain `data.ferritefw.dev` (`CNAME`).
- Pages sends `Access-Control-Allow-Origin: *`, so any site can fetch the tiles.
- Wanted later, if a proxy (e.g. Cloudflare) goes in front: allow only `https://console.ferritefw.dev`, the Tauri app (`tauri://localhost`, `http://tauri.localhost`) and `localhost` for development.
- A failed build deploys nothing: the last good copy stays up.

## Licence

- Scripts: PolyForm Noncommercial 1.0.0, Alex Harvey ([LICENSE.md](LICENSE.md)).
- Data: each source keeps its own licence (above).
