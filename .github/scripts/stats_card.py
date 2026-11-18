"""Build the HUD-style SYSTEM_STATS card (stats | languages | streak) for the profile README.

Runs inside GitHub Actions with GITHUB_TOKEN. Writes profile-stats/stats.svg.
Local preview without network:  python3 stats_card.py --demo
"""
import base64, datetime as dt, json, os, sys, urllib.request

USER = os.environ.get('USERNAME', 'pirathapanakshayan')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, 'profile-stats', 'stats.svg')

Y, SIL, BLK, PNL, LINE, DIM = '#FFD600', '#C9C9C9', '#0A0A0A', '#121212', '#2A2A2A', '#6B6B6B'

QUERY = """
query($login:String!){
  user(login:$login){
    pullRequests{totalCount}
    issues{totalCount}
    repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY]){totalCount}
    contributionsCollection{
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount } } }
    }
    repositories(ownerAffiliations:OWNER,isFork:false,first:100){
      nodes{ stargazerCount languages(first:10,orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name } } } }
    }
  }
}"""


def fetch():
    req = urllib.request.Request(
        'https://api.github.com/graphql',
        data=json.dumps({'query': QUERY, 'variables': {'login': USER}}).encode(),
        headers={'Authorization': 'bearer ' + os.environ['GITHUB_TOKEN'], 'Content-Type': 'application/json'})
    data = json.load(urllib.request.urlopen(req))
    if 'errors' in data:
        raise SystemExit('GraphQL error: ' + json.dumps(data['errors']))
    u = data['data']['user']
    cc = u['contributionsCollection']
    days = [d for w in cc['contributionCalendar']['weeks'] for d in w['contributionDays']]
    langs = {}
    stars = 0
    for r in u['repositories']['nodes']:
        stars += r['stargazerCount']
        for e in r['languages']['edges']:
            langs[e['node']['name']] = langs.get(e['node']['name'], 0) + e['size']
    return {
        'stars': stars,
        'commits': cc['totalCommitContributions'] + cc['restrictedContributionsCount'],
        'prs': u['pullRequests']['totalCount'],
        'issues': u['issues']['totalCount'],
        'contributed': u['repositoriesContributedTo']['totalCount'],
        'total': cc['contributionCalendar']['totalContributions'],
        'days': [(d['date'], d['contributionCount']) for d in days],
        'langs': langs,
    }


def streaks(days):
    days = sorted(days)
    today = dt.date.today().isoformat()
    days = [d for d in days if d[0] <= today]
    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    cur = 0
    seq = list(reversed(days))
    if seq and seq[0][1] == 0:   # today not done yet -> keep yesterday's streak alive
        seq = seq[1:]
    for _, c in seq:
        if c == 0:
            break
        cur += 1
    return cur, longest


def font_face(family, filename):
    with open(os.path.join(HERE, '..', 'fonts', filename), 'rb') as fh:
        b64 = base64.b64encode(fh.read()).decode()
    return f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{b64}) format('woff2');}}"


def esc(s):
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def build(s):
    cur, longest = streaks(s['days'])
    W, H = 1200, 300

    # ---- panel A: telemetry rows
    rows = [('STARS EARNED', s['stars']), ('COMMITS // 1Y', s['commits']), ('PULL REQUESTS', s['prs']),
            ('ISSUES', s['issues']), ('CONTRIBUTED TO', s['contributed'])]
    a = ''
    for i, (k, v) in enumerate(rows):
        y = 104 + i * 34
        a += (f'<g class="row" style="animation-delay:{0.2 + i * 0.15:.2f}s">'
              f'<rect x="46" y="{y - 10}" width="6" height="6" fill="{Y if i == 1 else DIM}"/>'
              f'<text x="64" y="{y}" class="m" font-size="14" fill="{SIL}">{k}</text>'
              f'<line x1="{80 + len(k) * 7.7:.0f}" x2="420" y1="{y - 4}" y2="{y - 4}" stroke="{LINE}" stroke-dasharray="2 4"/>'
              f'<text x="470" y="{y + 2}" class="d" font-size="22" fill="{Y if i == 1 else "#FFFFFF"}" text-anchor="end">{v}</text></g>')

    # ---- panel B: languages
    total = sum(s['langs'].values()) or 1
    top = sorted(s['langs'].items(), key=lambda kv: -kv[1])[:5]
    b = ''
    if not top:
        b = f'<text x="530" y="150" class="m" font-size="13" fill="{DIM}">NO CODE DETECTED YET...</text>'
    for i, (name, size) in enumerate(top):
        pct = size * 100 / total
        y = 98 + i * 36
        w = max(4, 300 * pct / 100)
        col = Y if i == 0 else SIL
        b += (f'<text x="530" y="{y}" class="m" font-size="13" fill="{SIL}">{esc(name.upper())}</text>'
              f'<text x="836" y="{y}" class="m" font-size="13" fill="{col}" text-anchor="end">{pct:.1f}%</text>'
              f'<rect x="530" y="{y + 7}" width="306" height="6" fill="#1E1E1E"/>'
              f'<rect x="530" y="{y + 7}" width="{w * 306 / 300:.1f}" height="6" fill="{col}" class="grow" style="animation-delay:{0.3 + i * 0.15:.2f}s"/>')

    # ---- panel C: streak ring
    ring_ticks = ''.join(
        f'<line x1="1022" y1="{70 if i % 3 else 64}" x2="1022" y2="76" stroke="{Y if i % 3 == 0 else DIM}" stroke-width="2" transform="rotate({i * 10} 1022 140)"/>'
        for i in range(36))

    frame = 'M10 10H700L726 36H1190V262L1162 290H10Z'
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs><style>{font_face('HUD', 'chakra-petch-700.woff2')}{font_face('MONO', 'share-tech-mono-400.woff2')}
.d{{font-family:'HUD',sans-serif;font-weight:700}}.m{{font-family:'MONO',monospace}}
.row{{opacity:0;animation:fade .5s ease forwards}}@keyframes fade{{to{{opacity:1}}}}
.grow{{transform-box:fill-box;transform-origin:left;transform:scaleX(0);animation:grow 1.2s ease-out forwards}}@keyframes grow{{to{{transform:scaleX(1)}}}}
.spin{{transform-origin:1022px 140px;animation:spin 20s linear infinite}}@keyframes spin{{to{{transform:rotate(360deg)}}}}
.blink{{animation:blink 1.2s steps(1) infinite}}@keyframes blink{{50%{{opacity:0}}}}
.flow{{stroke-dasharray:60 1400;animation:flow 6s linear infinite}}@keyframes flow{{from{{stroke-dashoffset:1460}}to{{stroke-dashoffset:0}}}}
.pulse{{animation:pulse 2.4s ease-in-out infinite}}@keyframes pulse{{0%,100%{{opacity:.35}}50%{{opacity:1}}}}
</style>
<pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse"><rect width="1.4" height="1.4" fill="#262626"/></pattern></defs>
<path d="{frame}" fill="{PNL}" stroke="{LINE}" stroke-width="1.5"/>
<path d="{frame}" fill="url(#dots)"/>
<path d="M10 10H700L726 36H1190" fill="none" stroke="{Y}" stroke-width="1.5" class="flow"/>

<!-- A: telemetry -->
<text x="40" y="52" class="m" font-size="13" fill="{DIM}">&gt;</text>
<text x="56" y="52" class="d" font-size="16" fill="{Y}" letter-spacing="3">GITHUB_TELEMETRY</text>
<line x1="40" y1="66" x2="480" y2="66" stroke="{LINE}"/>
{a}

<line x1="505" y1="40" x2="505" y2="262" stroke="{LINE}"/>
<!-- B: languages -->
<text x="530" y="52" class="d" font-size="16" fill="{Y}" letter-spacing="3">LANG_MATRIX</text>
<line x1="530" y1="66" x2="836" y2="66" stroke="{LINE}"/>
{b}

<line x1="862" y1="40" x2="862" y2="262" stroke="{LINE}"/>
<!-- C: streak -->
<text x="886" y="52" class="d" font-size="16" fill="{Y}" letter-spacing="3">STREAK</text>
<circle cx="1160" cy="47" r="4" fill="{Y}" class="blink"/>
<g class="spin">{ring_ticks}</g>
<circle cx="1022" cy="140" r="56" fill="{BLK}" stroke="{Y}" stroke-width="2"/>
<circle cx="1022" cy="140" r="48" fill="none" stroke="{DIM}" stroke-dasharray="2 6"/>
<text x="1022" y="150" class="d" font-size="38" fill="#FFFFFF" text-anchor="middle">{cur}</text>
<text x="1022" y="168" class="m" font-size="10" fill="{Y}" text-anchor="middle">DAY{"S" if cur != 1 else ""}</text>
<text x="1022" y="242" class="m" font-size="12" fill="{Y}" text-anchor="middle">CURRENT STREAK</text>
<text x="886" y="270" class="m" font-size="11" fill="{SIL}">LONGEST : <tspan fill="#FFFFFF">{longest}</tspan></text>
<text x="1160" y="270" class="m" font-size="11" fill="{SIL}" text-anchor="end">TOTAL 1Y : <tspan fill="#FFFFFF">{s["total"]}</tspan></text>

<text x="40" y="284" class="m" font-size="10" fill="{DIM}" letter-spacing="2">SYNC // {dt.date.today().isoformat()} // AUTO-UPDATED DAILY</text>
<circle cx="1022" cy="140" r="62" fill="none" stroke="{Y}" stroke-width="1" class="pulse"/>
</svg>'''
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as fh:
        fh.write(svg)
    print('wrote', OUT, f'{len(svg) // 1024} KB | streak', cur, '| longest', longest)


if __name__ == '__main__':
    if '--demo' in sys.argv:
        today = dt.date.today()
        days = [((today - dt.timedelta(days=i)).isoformat(), 1 if i in (0, 66, 67, 68, 120) else 0) for i in range(365)]
        build({'stars': 0, 'commits': 22, 'prs': 0, 'issues': 0, 'contributed': 1, 'total': 26, 'days': days,
               'langs': {'Python': 52000, 'TypeScript': 9000, 'HTML': 6000, 'CSS': 3000, 'JavaScript': 1500}})
    else:
        build(fetch())
