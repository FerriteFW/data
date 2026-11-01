"""out/index.html: a plain landing page for data.ferritefw.dev, written from the build's top-level index and
stats.csv's lines (each source's history as small inline SVG charts: no scripts)."""

import datetime
import html
import os

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ferrite data</title>
<style>
:root{{--bg:#fbfaf8;--fg:#1f2328;--mut:#5f6872;--line:#e2ded8;--acc:#b8541f;--code:#f1eee9;--add:#2f7d4f;--rem:#b83a3a;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14171b;--fg:#e4e7eb;--mut:#939ca6;--line:#2a3038;--acc:#f0874a;--code:#1d2228;--add:#5cc28a;--rem:#ef7070;color-scheme:dark}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;padding:40px max(16px,env(safe-area-inset-left))}}
main{{max-width:760px;margin:0 auto}}
h1{{font-size:28px;margin:0 0 4px}}
h2{{font-size:18px;margin:32px 0 8px}}
p{{margin:0 0 12px}}
.lede{{color:var(--mut)}}
a{{color:var(--acc)}}
code{{font:14px ui-monospace,Menlo,monospace;background:var(--code);padding:1px 5px;border-radius:4px}}
table{{border-collapse:collapse;width:100%;font-size:15px}}
th,td{{text-align:left;padding:8px 10px 8px 0;border-bottom:1px solid var(--line);vertical-align:top}}
th{{color:var(--mut);font-weight:600;font-size:13px;text-transform:uppercase;letter-spacing:.04em}}
td.n{{font-variant-numeric:tabular-nums;white-space:nowrap}}
.wrap{{overflow-x:auto}}
ul{{padding-left:20px;margin:0 0 12px}}
small{{color:var(--mut)}}
footer{{margin-top:40px;color:var(--mut);font-size:14px}}
.hist{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:16px;margin:8px 0 12px}}
.card{{border:1px solid var(--line);border-radius:8px;padding:12px 14px;min-width:0}}
.card h3{{font-size:15px;margin:0 0 2px}}
.card p{{font-size:13px;color:var(--mut);margin:0 0 8px}}
.card svg{{display:block;width:100%;height:auto}}
.lbl{{font:11px ui-monospace,Menlo,monospace;fill:var(--mut)}}
.k{{display:inline-block;width:9px;height:9px;border-radius:2px;margin:0 4px 0 10px;vertical-align:0}}
</style>
</head>
<body>
<main>
<h1>Ferrite data</h1>
<p class="lede">Channel data for <a href="https://ferritefw.dev">Ferrite</a> Console: licensed radio sites, airport frequencies and amateur repeaters near a place, split by grid square so an app only downloads what's around it, and the amateur satellites a handheld can work. Built {build_date}.</p>

<h2>What's here</h2>
<div class="wrap"><table>
<tr><th>Source</th><th>Rows</th><th>Tiles</th><th>Data from</th><th>Licence</th><th>Whole source</th></tr>
{rows}
</table></div>

<h2>Changes</h2>
<p>Each source's rows at every build, and the rows added (<span class="k" style="background:var(--add)"></span>) and removed (<span class="k" style="background:var(--rem)"></span>) against the copy before. From <a href="stats.csv"><code>stats.csv</code></a>.</p>
<div class="hist">
{history}
</div>

<h2>How it's organized</h2>
<ul>
<li><code>index.json</code>: every source, with its build date, row count, licence and its zip's size and SHA-256.</li>
<li><code>&lt;source&gt;/index.json</code>: one source's tiles and their row counts, plus <code>format</code> and <code>level</code>.</li>
<li>Tiles are Maidenhead grid locators: 4-character squares such as <code>tafl/CN89.json</code> (2&deg; by 1&deg;). A busy square (over 6,000 rows: big cities) comes as its 6-character subsquares instead (<code>tafl/CN89kg.json</code>), listed under <code>split</code>. Airports and repeaters use 2-character fields (<code>airports/CN.json</code>, 20&deg; by 10&deg;).</li>
<li><code>satellites/sats.json</code>: not tiles, one small file: each satellite's orbit elements and FM or APRS transponders (<code>satellites-1</code>, in the repository's README).</li>
<li><code>&lt;source&gt;.zip</code>: the whole source in one download, for keeping it offline.</li>
<li><code>stats.csv</code>: a line per source each time it's built (row count, rows added and removed, and for repeaters HearHam's own counts), kept from build to build.</li>
<li>Tiles are columnar JSON (<code>columnar-1</code>): names once, then whole-number differences for position and frequency. The format is in the <a href="https://github.com/FerriteFW/data#output">repository's README</a>.</li>
</ul>

<h2>Updates</h2>
<p>Rebuilt daily from each source's own public download: HearHam, OurAirports, CelesTrak and SatNOGS every day, the TAFL and the FCC when they publish new files. A source that can't be fetched keeps its last copy.</p>

<h2>Credits</h2>
<ul>
{credits}
</ul>
<p><small>Not an official product of ISED, the FCC, OurAirports, HearHam, CelesTrak or SatNOGS. For finding frequencies, not runways: never use it for navigation. Satellite elements age within days: refresh them.</small></p>

<footer>Scripts and issues: <a href="https://github.com/FerriteFW/data">github.com/FerriteFW/data</a> · <a href="https://ferritefw.dev">ferritefw.dev</a></footer>
</main>
</body>
</html>
"""

SHORT = {"tafl": "Canada: licensed sites (ISED TAFL)", "fcc": "US: licensed sites (FCC ULS)", "airports": "World: airport frequencies (OurAirports)",
         "repeaters": "World: amateur repeaters (HearHam)",
         "satellites": "World: amateur FM satellites (CelesTrak, SatNOGS)"}


W, TOP, H, GAP, BARS = 320, 14, 56, 10, 34  # width, label strip, rows chart, gap, changes chart (SVG units)


def _num(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _short(n):
    return f"{n / 1e6:.2f}M" if n >= 1e6 else f"{n / 1e3:.1f}k" if n >= 1e4 else f"{n:,}"


def chart(lines):
    """One source's history as SVG: rows as a line over the builds, and each build's rows added (up) and removed
    (down) as bars below. Builds sit by date, so the gaps show how often a source changes."""
    days = [datetime.date.fromisoformat(ln["build_date"]) for ln in lines]
    span = max((days[-1] - days[0]).days, 1)
    x = [round(8 + (d - days[0]).days / span * (W - 16), 1) for d in days]
    rows = [_num(ln["rows"]) or 0 for ln in lines]
    lo, hi = min(rows), max(rows)
    pad = max((hi - lo) * 0.15, hi * 0.002, 1)
    lo, hi = lo - pad, hi + pad
    y = [round(TOP + 4 + (hi - r) / (hi - lo) * (H - 8), 1) for r in rows]
    pts = " ".join(f"{a},{b}" for a, b in zip(x, y))
    dots = "".join(f'<circle cx="{a}" cy="{b}" r="2.2" fill="var(--acc)"/>' for a, b in zip(x, y))
    adds = [_num(ln.get("added")) for ln in lines]
    rems = [_num(ln.get("removed")) for ln in lines]
    big = max([v for v in adds + rems if v] or [1])
    mid = TOP + H + GAP + BARS / 2
    bars = []
    for a, ad, rm in zip(x, adds, rems):
        for v, sign, col in ((ad, -1, "var(--add)"), (rm, 1, "var(--rem)")):
            if v:
                h = max(1.5, v / big * (BARS / 2 - 1))
                top = mid - h if sign < 0 else mid
                bars.append(f'<rect x="{a - 2}" y="{round(top, 1)}" width="4" height="{round(h, 1)}" fill="{col}">'
                            f'<title>{v:,} {"added" if sign < 0 else "removed"}</title></rect>')
    total_h = TOP + H + GAP + BARS + 14
    return (f'<svg viewBox="0 0 {W} {total_h}" role="img" aria-label="Rows and changes per build">'
            f'<line x1="0" x2="{W}" y1="{mid}" y2="{mid}" stroke="var(--line)"/>'
            f'<polyline points="{pts}" fill="none" stroke="var(--acc)" stroke-width="1.6"/>{dots}{"".join(bars)}'
            f'<text class="lbl" x="0" y="{total_h - 2}">{days[0].isoformat()}</text>'
            f'<text class="lbl" x="{W}" y="{total_h - 2}" text-anchor="end">{days[-1].isoformat()}</text>'
            f'<text class="lbl" x="{W}" y="10" text-anchor="end">{_short(max(rows))} rows</text></svg>')


def history(top, stats):
    e = html.escape
    cards = []
    for s in top["sources"]:
        name = s["source"]
        lines = [ln for ln in stats if ln.get("source") == name and ln.get("build_date")]
        if not lines:
            continue
        last = lines[-1]
        ad, rm = _num(last.get("added")), _num(last.get("removed"))
        change = f" · last change +{ad:,} −{rm:,}" if ad is not None and rm is not None else ""
        recent = sum(1 for ln in lines if (datetime.date.fromisoformat(top["build_date"])
                                          - datetime.date.fromisoformat(ln["build_date"])).days < 30)
        summary = (f"{len(lines)} builds since {e(lines[0]['build_date'])} · {recent} in the last 30 days{change}"
                   if len(lines) > 1 else f"History starts with this build ({e(last['build_date'])}).")
        cards.append(f'<div class="card"><h3>{e(SHORT.get(name, name))}</h3><p>{summary}</p>'
                     f'{chart(lines) if len(lines) > 1 else ""}</div>')
    return "\n".join(cards)


def write(out, top, stats=()):
    e = html.escape
    rows, credits = [], []
    for s in top["sources"]:
        name = s["source"]
        zip_mb = s.get("bundle_bytes", 0) / 1e6
        rows.append(
            f'<tr><td>{e(SHORT.get(name, s.get("title", name)))}<br><small><code>{e(name)}/</code></small></td>'
            f'<td class="n">{s["rows"]:,}</td><td class="n">{s.get("tiles", 0):,}</td>'
            f'<td class="n">{e(s.get("source_date", ""))}</td>'
            f'<td><a href="{e(s.get("licence_url", ""))}">{e(s.get("licence", ""))}</a></td>'
            f'<td class="n"><a href="{e(s.get("bundle", ""))}">{e(s.get("bundle", ""))}</a> {zip_mb:.1f} MB</td></tr>')
        credits.append(f"<li>{e(s.get('attribution', ''))}</li>")
    page = PAGE.format(build_date=e(top["build_date"]), rows="\n".join(rows), credits="\n".join(credits),
                       history=history(top, stats))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
