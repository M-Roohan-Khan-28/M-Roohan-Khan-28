#!/usr/bin/env python3
"""Render genuine GitHub activity; no third-party statistics endpoint or invented counts."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

QUERY = '''query($login:String!){user(login:$login){
  login followers{totalCount}
  repositories(privacy:PUBLIC,ownerAffiliations:[OWNER],isFork:false){totalCount}
  contributionsCollection{startedAt endedAt contributionCalendar{
    totalContributions weeks{contributionDays{date contributionCount}}
  }}
}}'''

def fetch_user(owner: str, token: str) -> dict:
    data = json.dumps({'query': QUERY, 'variables': {'login': owner}}).encode()
    req = urllib.request.Request('https://api.github.com/graphql', data=data, headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
        'User-Agent': 'roohan-profile-activity'})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            payload = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'GitHub API returned HTTP {e.code}; existing card was not overwritten.') from e
    if payload.get('errors'):
        raise RuntimeError('GitHub GraphQL errors: ' + json.dumps(payload['errors']))
    user = payload.get('data', {}).get('user')
    if not user:
        raise RuntimeError('GitHub returned no user. Check PROFILE_OWNER and token permissions.')
    return user

def render(user: dict, stamp: str) -> str:
    esc = html.escape
    coll = user['contributionsCollection']; cal = coll['contributionCalendar']
    months: dict[str, int] = defaultdict(int)
    for week in cal['weeks']:
        for day in week['contributionDays']:
            months[day['date'][:7]] += int(day['contributionCount'])
    buckets = sorted(months.items())[-12:]
    vals = [int(cal['totalContributions']), int(user['repositories']['totalCount']),
            int(user['followers']['totalCount'])]
    if any(v < 0 for v in vals):
        raise ValueError('Negative GitHub counts rejected.')
    labels = ['RECORDED CONTRIBUTIONS', 'PUBLIC NON-FORK REPOSITORIES', 'FOLLOWERS']
    s = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 420" role="img">',
         '<title>GitHub activity, generated from actual GitHub API data</title>',
         '<rect width="1200" height="420" rx="16" fill="#13121C"/>',
         '<g font-family="Arial,Helvetica,sans-serif">']
    for i, (label, n) in enumerate(zip(labels, vals)):
        x = 34 + i * 390
        s.extend([f'<rect x="{x}" y="25" width="365" height="100" rx="10" fill="#211C30"/>',
            f'<text x="{x+20}" y="54" font-size="12" fill="#BFB6CD">{label}</text>',
            f'<text x="{x+20}" y="102" font-size="35" font-weight="700" fill="#C4AFF8">{n:,}</text>'])
    s.append('<text x="35" y="165" font-size="16" fill="#F0B06A">MONTHLY CONTRIBUTIONS · NOT PROFILE VIEWS</text>')
    high = max([n for _, n in buckets] + [1])
    for i, (month, count) in enumerate(buckets):
        x = 43 + i * 95; height = 120 * count / high
        s.append(f'<rect x="{x}" y="{310-height:.2f}" width="60" height="{height:.2f}" rx="4" fill="#946BDB"/>')
        s.append(f'<text x="{x+30}" y="{302-height:.2f}" text-anchor="middle" font-size="12" fill="#F4F0FA">{count}</text>')
        s.append(f'<text x="{x+30}" y="334" text-anchor="middle" font-size="11" fill="#BFB6CD">{month}</text>')
    a = str(coll['startedAt'])[:10]; b = str(coll['endedAt'])[:10]
    s.append(f'<text x="35" y="374" font-size="12" fill="#BFB6CD">Period: {esc(a)} to {esc(b)} · Boundary months may be partial · Updated {esc(stamp)}</text>')
    s.append('<text x="35" y="398" font-size="12" fill="#BFB6CD">GitHub activity is not a score of skill, proficiency, or client delivery.</text></g></svg>')
    return ''.join(s)

def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument('--fixture', type=Path)
    ap.add_argument('--output', type=Path, default=Path('assets/activity.svg'))
    args = ap.parse_args()
    if args.fixture:
        user = json.loads(args.fixture.read_text())
        stamp = 'LOCAL TEST FIXTURE — NOT LIVE DATA'
    else:
        token = os.environ.get('GH_TOKEN', ''); owner = os.environ.get('PROFILE_OWNER', '')
        if not token or not owner:
            raise SystemExit('Set GH_TOKEN and PROFILE_OWNER. Never put tokens in repository files.')
        user = fetch_user(owner, token)
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d UTC')
    text = render(user, stamp)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix('.tmp.svg'); tmp.write_text(text, encoding='utf-8'); tmp.replace(args.output)

if __name__ == '__main__':
    main()
