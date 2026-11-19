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
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoryContributions
      hasAnyRestrictedContributions
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
        headers={'Authorization': 'bearer ' + (os.environ.get('STATS_TOKEN') or os.environ['GITHUB_TOKEN']), 'Content-Type': 'application/json'})
    data = json.load(urllib.request.urlopen(req))
    if 'errors' in data:
        raise SystemExit('GraphQL error: ' + json.dumps(data['errors']))
    u = data['data']['user']
    cc = u['contributionsCollection']
    print('DEBUG token:', 'STATS_TOKEN' if os.environ.get('STATS_TOKEN') else 'GITHUB_TOKEN',
          {k: v for k, v in cc.items() if k != 'contributionCalendar'},
          'calendar total:', cc['contributionCalendar']['totalContributions'])
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


LEVELS = ['#1C1C1C', '#4A3E00', '#8A7200', '#C9A600', '#FFD600']


def level(c, mx):
    if c <= 0:
        return 0
    if mx <= 4:
        return min(4, c)
    return min(4, 1 + int((c - 1) * 4 / mx))


def build_calendar(s):
    """GitHub-style contribution grid in the HUD theme -> profile-stats/calendar.svg"""
    days = sorted(s['days'])
    first = dt.date.fromisoformat(days[0][0])
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)   # back to Sunday
    mx = max([c for _, c in days] + [1])
    today = dt.date.today().isoformat()
    cell, gap, x0, y0 = 16, 4, 84, 92
    step = cell + gap
    cells, months, last_month, last_label_col = '', '', None, -10
    ncols = 0
    for d, c in days:
        date = dt.date.fromisoformat(d)
        col = (date - start).days // 7
        row = (date.weekday() + 1) % 7
        ncols = max(ncols, col + 1)
        x, y = x0 + col * step, y0 + row * step
        lv = level(c, mx)
        extra = ''
        if d == today:
            extra = f'<rect x="{x - 2.5}" y="{y - 2.5}" width="{cell + 5}" height="{cell + 5}" fill="none" stroke="#FFFFFF" stroke-width="1.2" class="blink"/>'
        cls = ' class="c"' if lv else ''
        cells += (f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{LEVELS[lv]}"'
                  f'{cls} style="animation-delay:{col * 0.025:.2f}s"><title>{c} on {d}</title></rect>{extra}')
        if row == 0 and date.month != last_month:
            if col - last_label_col >= 3 and col < 52:
                months += f'<text x="{x}" y="{y0 - 14}" class="m" font-size="12" fill="{SIL}">{date.strftime("%b").upper()}</text>'
                last_label_col = col
            last_month = date.month
    gx1 = x0 + ncols * step
    days_lbl = ''.join(f'<text x="{x0 - 12}" y="{y0 + r * step + 12}" class="m" font-size="11" fill="{DIM}" text-anchor="end">{n}</text>'
                       for r, n in ((1, 'MON'), (3, 'WED'), (5, 'FRI')))
    legend_x = gx1 - 5 * step - 44
    legend = ''.join(f'<rect x="{legend_x + 40 + i * step}" y="250" width="{cell}" height="{cell}" rx="2" fill="{c}"/>' for i, c in enumerate(LEVELS))
    W, H = 1200, 300
    frame = 'M10 10H700L726 36H1190V262L1162 290H10Z'
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs><style>{font_face('HUD', 'chakra-petch-700.woff2')}{font_face('MONO', 'share-tech-mono-400.woff2')}
.d{{font-family:'HUD',sans-serif;font-weight:700}}.m{{font-family:'MONO',monospace}}
.c{{animation:pop .6s ease-out both}}@keyframes pop{{from{{opacity:0}}to{{opacity:1}}}}
.blink{{animation:blink 1.2s steps(1) infinite}}@keyframes blink{{50%{{opacity:0}}}}
.scan{{animation:scan 6s linear infinite}}@keyframes scan{{from{{transform:translateX(0)}}to{{transform:translateX({gx1 - x0}px)}}}}
.flow{{stroke-dasharray:60 1400;animation:flow 6s linear infinite}}@keyframes flow{{from{{stroke-dashoffset:1460}}to{{stroke-dashoffset:0}}}}
</style>
<pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse"><rect width="1.4" height="1.4" fill="#262626"/></pattern>
<linearGradient id="sg" x1="0" x2="1"><stop offset="0" stop-color="{Y}" stop-opacity="0"/><stop offset="1" stop-color="{Y}" stop-opacity=".25"/></linearGradient>
<clipPath id="gc"><rect x="{x0}" y="{y0}" width="{gx1 - x0}" height="{7 * step}"/></clipPath></defs>
<path d="{frame}" fill="{PNL}" stroke="{LINE}" stroke-width="1.5"/>
<path d="{frame}" fill="url(#dots)"/>
<path d="M10 10H700L726 36H1190" fill="none" stroke="{Y}" stroke-width="1.5" class="flow"/>
<text x="40" y="52" class="m" font-size="13" fill="{DIM}">&gt;</text>
<text x="56" y="52" class="d" font-size="16" fill="{Y}" letter-spacing="3">CONTRIBUTION_MATRIX</text>
<text x="1160" y="56" class="d" font-size="22" fill="#FFFFFF" text-anchor="end">{s["total"]}<tspan class="m" font-size="12" fill="{SIL}" dx="8">CONTRIBUTIONS // LAST YEAR</tspan></text>
{months}{days_lbl}
{cells}
<g clip-path="url(#gc)"><rect class="scan" x="{x0 - 60}" y="{y0}" width="60" height="{7 * step}" fill="url(#sg)"/></g>
<text x="40" y="262" class="m" font-size="10" fill="{DIM}" letter-spacing="2">SYNC // {dt.date.today().isoformat()} // AUTO-UPDATED DAILY</text>
<text x="{legend_x}" y="262" class="m" font-size="11" fill="{DIM}">LESS</text>{legend}
<text x="{legend_x + 44 + 5 * step}" y="262" class="m" font-size="11" fill="{DIM}">MORE</text>
</svg>'''
    out = os.path.join(ROOT, 'profile-stats', 'calendar.svg')
    with open(out, 'w') as fh:
        fh.write(svg)
    print('wrote', out, f'{len(svg) // 1024} KB')


def build_activity(s):
    """Animated 31-day activity line chart -> profile-stats/activity.svg"""
    today = dt.date.today().isoformat()
    days = [d for d in sorted(s['days']) if d[0] <= today][-31:]
    counts = [c for _, c in days]
    peak = max(counts + [0])
    top = max(4, peak + (4 - peak % 4) % 4)          # nice y max (multiple of 4)
    X0, X1, Y0, Y1 = 90, 1150, 92, 236                 # plot box
    n = len(days)
    xs = [X0 + i * (X1 - X0) / (n - 1) for i in range(n)]
    ys = [Y1 - c * (Y1 - Y0) / top for c in counts]

    # smooth path (Catmull-Rom -> cubic Bezier), control points clamped inside the box
    def clamp(v):
        return max(Y0, min(Y1, v))
    d = f'M{xs[0]:.1f} {ys[0]:.1f}'
    for i in range(n - 1):
        p0 = (xs[i - 1], ys[i - 1]) if i else (xs[i], ys[i])
        p1, p2 = (xs[i], ys[i]), (xs[i + 1], ys[i + 1])
        p3 = (xs[i + 2], ys[i + 2]) if i + 2 < n else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, clamp(p1[1] + (p2[1] - p0[1]) / 6))
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, clamp(p2[1] - (p3[1] - p1[1]) / 6))
        d += f' C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}'
    area = d + f' L{xs[-1]:.1f} {Y1} L{xs[0]:.1f} {Y1} Z'

    grid = ''
    for k in range(5):
        v = top * k / 4
        y = Y1 - k * (Y1 - Y0) / 4
        grid += (f'<line x1="{X0}" x2="{X1}" y1="{y:.1f}" y2="{y:.1f}" stroke="{LINE}" stroke-dasharray="{"0" if k == 0 else "2 6"}"/>'
                 f'<text x="{X0 - 14}" y="{y + 4:.1f}" class="m" font-size="11" fill="{DIM}" text-anchor="end">{v:g}</text>')
    xl = ''
    for i, (date, c) in enumerate(days):
        dd = dt.date.fromisoformat(date)
        hi = dd.day == 1 or i == 0
        lbl = dd.strftime('%b').upper() if hi else str(dd.day)
        xl += (f'<line x1="{xs[i]:.1f}" x2="{xs[i]:.1f}" y1="{Y1}" y2="{Y1 + 5}" stroke="{Y if hi else DIM}"/>'
               f'<text x="{xs[i]:.1f}" y="{Y1 + 20}" class="m" font-size="{11 if hi else 10}" fill="{Y if hi else DIM}" text-anchor="middle">{lbl}</text>')
    dots = ''
    for i, c in enumerate(counts):
        delay = 0.3 + 1.8 * i / (n - 1)
        if c > 0:
            dots += (f'<g class="pop" style="animation-delay:{delay:.2f}s;transform-origin:{xs[i]:.1f}px {ys[i]:.1f}px">'
                     f'<circle cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="5.5" fill="{BLK}" stroke="{Y}" stroke-width="2"/>'
                     f'<text x="{xs[i]:.1f}" y="{ys[i] - 13:.1f}" class="d" font-size="13" fill="#FFFFFF" text-anchor="middle">{c}</text>'
                     f'<title>{c} on {days[i][0]}</title></g>')
        else:
            dots += f'<circle cx="{xs[i]:.1f}" cy="{ys[i]:.1f}" r="2.5" fill="{DIM}" class="pop" style="animation-delay:{delay:.2f}s;transform-origin:{xs[i]:.1f}px {ys[i]:.1f}px"><title>0 on {days[i][0]}</title></circle>'
    # pulsing marker on today
    dots += (f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="10" fill="none" stroke="{Y}" class="ping" '
             f'style="transform-origin:{xs[-1]:.1f}px {ys[-1]:.1f}px"/>')

    total = sum(counts)
    active = sum(1 for c in counts if c)
    frame = 'M10 10H700L726 36H1190V262L1162 290H10Z'
    W, H = 1200, 300
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs><style>{font_face('HUD', 'chakra-petch-700.woff2')}{font_face('MONO', 'share-tech-mono-400.woff2')}
.d{{font-family:'HUD',sans-serif;font-weight:700}}.m{{font-family:'MONO',monospace}}
.line{{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 2.2s ease-out .3s forwards}}@keyframes draw{{to{{stroke-dashoffset:0}}}}
.area{{opacity:0;animation:fade 1s ease 1.6s forwards}}@keyframes fade{{to{{opacity:1}}}}
.pop{{opacity:0;animation:pop .35s ease-out forwards}}@keyframes pop{{from{{opacity:0;transform:scale(0)}}to{{opacity:1;transform:scale(1)}}}}
.ping{{opacity:0;animation:ping 1.8s ease-out 2.6s infinite}}@keyframes ping{{0%{{opacity:.9;transform:scale(.5)}}100%{{opacity:0;transform:scale(2)}}}}
.scan{{animation:scan 5s linear infinite}}@keyframes scan{{from{{transform:translateX(0)}}to{{transform:translateX({X1 - X0}px)}}}}
.blink{{animation:blink 1.2s steps(1) infinite}}@keyframes blink{{50%{{opacity:0}}}}
.flow{{stroke-dasharray:60 1400;animation:flow 6s linear infinite}}@keyframes flow{{from{{stroke-dashoffset:1460}}to{{stroke-dashoffset:0}}}}
</style>
<pattern id="dots" width="18" height="18" patternUnits="userSpaceOnUse"><rect width="1.4" height="1.4" fill="#262626"/></pattern>
<linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{Y}" stop-opacity=".35"/><stop offset="1" stop-color="{Y}" stop-opacity="0"/></linearGradient>
<linearGradient id="sg" x1="0" x2="1"><stop offset="0" stop-color="{Y}" stop-opacity="0"/><stop offset="1" stop-color="{Y}" stop-opacity=".18"/></linearGradient>
<filter id="glow" x="-5%" y="-30%" width="110%" height="160%"><feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="pc"><rect x="{X0}" y="{Y0 - 30}" width="{X1 - X0}" height="{Y1 - Y0 + 30}"/></clipPath></defs>
<path d="{frame}" fill="{PNL}" stroke="{LINE}" stroke-width="1.5"/>
<path d="{frame}" fill="url(#dots)"/>
<path d="M10 10H700L726 36H1190" fill="none" stroke="{Y}" stroke-width="1.5" class="flow"/>
<text x="40" y="52" class="m" font-size="13" fill="{DIM}">&gt;</text>
<text x="56" y="52" class="d" font-size="16" fill="{Y}" letter-spacing="3">ACTIVITY_LOG</text>
<text x="250" y="52" class="m" font-size="12" fill="{SIL}">// LAST 31 DAYS</text>
<circle cx="372" cy="48" r="4" fill="{Y}" class="blink"/>
<text x="1160" y="56" class="m" font-size="12" fill="{SIL}" text-anchor="end">TOTAL <tspan class="d" font-size="18" fill="#FFFFFF">{total}</tspan>  ·  PEAK <tspan class="d" font-size="18" fill="{Y}">{peak}</tspan>  ·  ACTIVE <tspan class="d" font-size="18" fill="#FFFFFF">{active}</tspan>D</text>
{grid}{xl}
<g clip-path="url(#pc)"><rect class="scan" x="{X0 - 50}" y="{Y0 - 30}" width="50" height="{Y1 - Y0 + 30}" fill="url(#sg)"/></g>
<path d="{area}" fill="url(#ag)" class="area"/>
<path d="{d}" fill="none" stroke="{Y}" stroke-width="3" stroke-linecap="round" pathLength="1" class="line" filter="url(#glow)"/>
{dots}
<text x="40" y="280" class="m" font-size="10" fill="{DIM}" letter-spacing="2">SYNC // {today} // AUTO-UPDATED DAILY</text>
</svg>'''
    out = os.path.join(ROOT, 'profile-stats', 'activity.svg')
    with open(out, 'w') as fh:
        fh.write(svg)
    print('wrote', out, f'{len(svg) // 1024} KB')


if __name__ == '__main__':
    if '--demo' in sys.argv:
        today = dt.date.today()
        days = [((today - dt.timedelta(days=i)).isoformat(), {0: 2, 1: 6, 2: 3, 30: 4, 66: 1, 67: 1, 68: 2, 120: 1, 200: 1, 250: 1}.get(i, 0)) for i in range(366)]
        data = {'stars': 0, 'commits': 22, 'prs': 0, 'issues': 0, 'contributed': 1, 'total': 26, 'days': days,
                'langs': {'Python': 52000, 'TypeScript': 9000, 'HTML': 6000, 'CSS': 3000, 'JavaScript': 1500}}
    else:
        data = fetch()
    build(data)
    build_calendar(data)
    build_activity(data)
