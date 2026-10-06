#!/usr/bin/env python3
"""Runs the Tavily searches behind the Agentic Insights page and records the raw results.

  Future days (Oct 6, 7, 10): Moscone Center events, Oracle Park events, other events in San Francisco,
                              plus one check per event listed by the user.
  Past days (Sep 5 - Oct 4):  a calamity check (fires, outages, protests, closures, emergencies near the ballpark).

Output: data/research/tavily.json. The website never calls Tavily; it only reads this recorded file.
The API key is read from ../.env and is never written to the output.
    python3 data/research_tavily.py            # skips queries already recorded
"""
import json, os, time, urllib.request, urllib.error
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'research', 'tavily.json')
env = dict(l.strip().split('=', 1) for l in open(os.path.join(HERE, '..', '.env')) if '=' in l and not l.startswith('#'))

FUTURE = {
    '2026-10-06': ['Golden State Warriors vs Los Angeles Lakers preseason October 6 2026 Chase Center'],
    '2026-10-07': ['Golden State Valkyries vs Las Vegas Aces WNBA playoffs October 7 2026',
                   'Rod Wave concert October 7 2026 venue San Francisco Bay Area'],
    '2026-10-10': ['Golden State Warriors vs Sacramento Kings preseason October 10 2026 Chase Center'],
}
PAST_FROM, PAST_TO = date(2026, 9, 5), date(2026, 10, 4)

def nice(iso):
    d = datetime.fromisoformat(iso)
    return f'{d.strftime("%B")} {d.day}, {d.year}'

def search(query, **extra):
    body = {'query': query, 'search_depth': 'basic', 'max_results': 5, 'include_answer': False, **extra}
    req = urllib.request.Request('https://api.tavily.com/search', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + env['TAVILY_KEY']})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.loads(r.read())
        return {'ok': True, 'seconds': round(time.time() - t, 2), 'results': [
            {k: x.get(k) for k in ('title', 'url', 'content', 'score', 'published_date')} for x in res.get('results', [])]}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'error': f'HTTP {e.code}: {e.read().decode()[:200]}', 'results': []}

def main():
    rec = json.load(open(OUT)) if os.path.exists(OUT) else {'queries': []}
    have = {q['id'] for q in rec['queries']}
    jobs = []
    for d, confirms in FUTURE.items():
        jobs += [(f'{d}:moscone', d, 'moscone', f'Moscone Center events {nice(d)}', {}),
                 (f'{d}:oracle', d, 'oracle', f'Oracle Park San Francisco events {nice(d)}', {}),
                 (f'{d}:other', d, 'other', f'events happening in San Francisco on {nice(d)}', {})]
        jobs += [(f'{d}:confirm{i}', d, 'confirm', q, {}) for i, q in enumerate(confirms)]
    d = PAST_FROM
    while d <= PAST_TO:
        iso = d.isoformat()
        jobs.append((f'{iso}:calamity', iso, 'calamity',
                     f'San Francisco {nice(iso)} fire OR power outage OR evacuation OR protest OR road closure OR emergency near Oracle Park South Beach SoMa',
                     {'topic': 'news', 'start_date': iso, 'end_date': (d + timedelta(days=1)).isoformat()}))
        d += timedelta(days=1)
    for qid, d, kind, query, extra in jobs:
        if qid in have:
            continue
        r = search(query, **extra)
        if not r['ok'] and extra:                       # news filter rejected: retry as a plain search
            r = search(query)
            extra = {'fallback': 'plain search'}
        rec['queries'].append({'id': qid, 'date': d, 'kind': kind, 'query': query, 'params': extra, **r})
        print(f"{qid:24} {len(r['results'])} results {'' if r['ok'] else r['error']}")
    rec['generated_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
    rec['queries'].sort(key=lambda q: (q['date'], q['kind']))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rec, open(OUT, 'w'), indent=1, ensure_ascii=False)
    print('recorded', len(rec['queries']), 'queries ->', OUT)

if __name__ == '__main__':
    main()
