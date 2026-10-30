"""out/index.html: a plain landing page for data.ferritefw.dev, written from the build's top-level index."""

import html
import os

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ferrite data</title>
<style>
:root{{--bg:#fbfaf8;--fg:#1f2328;--mut:#5f6872;--line:#e2ded8;--acc:#b8541f;--code:#f1eee9;color-scheme:light}}
@media (prefers-color-scheme:dark){{:root{{--bg:#14171b;--fg:#e4e7eb;--mut:#939ca6;--line:#2a3038;--acc:#f0874a;--code:#1d2228;color-scheme:dark}}}}
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
</style>
</head>
<body>
<main>
<h1>Ferrite data</h1>
<p class="lede">Channel data for <a href="https://ferritefw.dev">Ferrite</a> Console: licensed radio sites and airport frequencies near a place, split by grid square so an app only downloads what's around it. Built {build_date}.</p>

<h2>What's here</h2>
<div class="wrap"><table>
<tr><th>Source</th><th>Rows</th><th>Tiles</th><th>Data from</th><th>Licence</th><th>Whole source</th></tr>
{rows}
</table></div>

<h2>How it's organized</h2>
<ul>
<li><code>index.json</code>: every source, with its build date, row count, licence and its zip's size and SHA-256.</li>
<li><code>&lt;source&gt;/index.json</code>: one source's tiles and their row counts, plus <code>format</code> and <code>level</code>.</li>
<li>Tiles are Maidenhead grid locators: 4-character squares such as <code>tafl/CN89.json</code> (2&deg; by 1&deg;). A busy square (over 6,000 rows: big cities) comes as its 6-character subsquares instead (<code>tafl/CN89kg.json</code>), listed under <code>split</code>. Airports use 2-character fields (<code>airports/CN.json</code>, 20&deg; by 10&deg;).</li>
<li><code>&lt;source&gt;.zip</code>: the whole source in one download, for keeping it offline.</li>
<li>Tiles are columnar JSON (<code>columnar-1</code>): names once, then whole-number differences for position and frequency. The format is in the <a href="https://github.com/FerriteFW/data#output">repository's README</a>.</li>
</ul>

<h2>Updates</h2>
<p>Rebuilt monthly from each source's own public download. A source that can't be fetched keeps its last copy.</p>

<h2>Credits</h2>
<ul>
{credits}
</ul>
<p><small>Not an official product of ISED, the FCC or OurAirports. Never use it for navigation.</small></p>

<footer>Scripts and issues: <a href="https://github.com/FerriteFW/data">github.com/FerriteFW/data</a> · <a href="https://ferritefw.dev">ferritefw.dev</a></footer>
</main>
</body>
</html>
"""

SHORT = {"tafl": "Canada: licensed sites (ISED TAFL)", "fcc": "US: licensed sites (FCC ULS)", "airports": "World: airport frequencies (OurAirports)"}


def write(out, top):
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
    page = PAGE.format(build_date=e(top["build_date"]), rows="\n".join(rows), credits="\n".join(credits))
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
