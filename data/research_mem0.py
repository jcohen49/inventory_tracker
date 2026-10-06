#!/usr/bin/env python3
"""Seeds Mem0 with what the truck sold on past days, then records the retrievals the page cites.

  1. Seeds one memory per past event day, per event-free day, and a few lessons (stored verbatim, infer=false).
  2. Searches Mem0 for each target day (Oct 6, 7, 10) and records the memories returned.

Output: data/research/mem0.json. The website never calls Mem0; it only reads this recorded file.
The API key is read from ../.env and is never written to the output.
    python3 data/research_mem0.py              # skips memories already seeded
"""
import json, os, time, urllib.request, urllib.error
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'research', 'mem0.json')
env = dict(l.strip().split('=', 1) for l in open(os.path.join(HERE, '..', '.env')) if '=' in l and not l.startswith('#'))
HDR = {'Authorization': 'Token ' + env['MEM0_API_KEY'], 'Content-Type': 'application/json'}
USER = 'mauricios-burrito-truck'
TEST_MEMORY = '7c1d915b-341f-4814-9d28-f02766c83410'      # connectivity check created while building this; safe to delete

def call(url, body=None, method='POST'):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

def load(p):
    return json.load(open(os.path.join(HERE, p)))

def seeds():
    truth = {t['date']: t for t in load('ground_truth.json')}
    events = load('events.json')
    by_day = {}
    for e in events:
        by_day.setdefault(e['date'], []).append(e)
    out = []
    for d, t in sorted(truth.items()):
        evs = [e for e in by_day.get(d, []) if e['date'] <= '2026-10-04']
        dow = t['day_of_week']; base = round(t['baseline_expected_items']); act = t['actual_items']
        pct = round((act / t['baseline_expected_items'] - 1) * 100)
        what = '; '.join(f"{e['name']} at {e['venue']} ({e['distance_from_oracle_park_miles']} mi from the truck, starts {e['start_time']})" for e in evs) or 'no events nearby'
        text = (f"{d} ({dow}): {what}. The truck sold {act} items vs a {dow} trend of {base} ({pct:+d}%), "
                f"revenue ${t['actual_revenue']:,.2f}, {t['actual_orders']} orders.")
        out.append({'key': 'day:' + d, 'text': text, 'metadata': {
            'type': 'sales_day', 'date': d, 'day_of_week': dow, 'actual_items': act, 'baseline_items': base, 'vs_baseline_pct': pct,
            'event_ids': [e['event_id'] for e in evs], 'venues': sorted({e['venue'] for e in evs}), 'revenue': t['actual_revenue']}})
    lessons = [
        ('lesson:giants-day-games', 'Lesson: lunch spikes on 2026-09-09, 2026-09-23 and 2026-09-27 came from Giants day games at Oracle Park (0.1 mi away), not from the Chase Center evening events the same days. Isolated Chase Center evening lift was only +5 to +11 items an hour.',
         {'type': 'lesson', 'dates': ['2026-09-09', '2026-09-23', '2026-09-27'], 'venues': ['Oracle Park', 'Chase Center']}),
        ('lesson:chase-basketball', 'Lesson: Valkyries nights at Chase Center (0.9 mi) lift the truck +11% to +17% on a normal weekday or Saturday, with the extra sales 17:00 to 18:00, about 90 minutes before the game.',
         {'type': 'lesson', 'dates': ['2026-09-18', '2026-09-19', '2026-10-02', '2026-10-04'], 'venues': ['Chase Center']}),
        ('lesson:oracle-strongest', 'Lesson: Oracle Park games (0.1 mi) are the biggest driver, +85% to +150% on Dodgers weekend games, with a rush from 2.5 hours before first pitch.',
         {'type': 'lesson', 'dates': ['2026-09-25', '2026-09-26', '2026-09-27'], 'venues': ['Oracle Park']}),
        ('lesson:rain-fog', 'Lesson: rain, drizzle and cold fog cut sales 15% to 30%, and can erase an expected game-night lift (2026-09-22, 2026-09-29, 2026-09-30).',
         {'type': 'lesson', 'dates': ['2026-09-22', '2026-09-29', '2026-09-30'], 'venues': []}),
        ('lesson:moscone', 'Lesson: Moscone Center conferences (0.9 mi), such as Dreamforce on 2026-09-15 to 2026-09-17, add a lunch lift of about +15% to +20%.',
         {'type': 'lesson', 'dates': ['2026-09-15', '2026-09-16', '2026-09-17'], 'venues': ['Moscone Center']}),
    ]
    out += [{'key': k, 'text': t, 'metadata': m} for k, t, m in lessons]
    return out

QUERIES = {
    '2026-10-06': ['past sales on basketball nights at Chase Center', 'sales when a Moscone Center conference is on', 'concerts at Chase Center on weeknights'],
    '2026-10-07': ['past sales on Valkyries playoff games', 'sales on days with an event far from the ballpark', 'sales when a Moscone Center conference is on'],
    '2026-10-10': ['Saturday early evening game at Chase Center', 'Saturday sales with no event nearby', 'bayfront festival or air show crowds'],
}

def main():
    rec = json.load(open(OUT)) if os.path.exists(OUT) else {'user_id': USER, 'seeded': [], 'searches': []}
    if TEST_MEMORY and call(f'https://api.mem0.ai/v1/memories/{TEST_MEMORY}/', method='DELETE')[0] == 200:
        print('deleted connectivity-test memory')
    have = {s['key'] for s in rec['seeded']}
    for s in seeds():
        if s['key'] in have:
            continue
        st, r = call('https://api.mem0.ai/v1/memories/', {'messages': [{'role': 'user', 'content': s['text']}], 'user_id': USER,
                                                         'infer': False, 'async_mode': False, 'metadata': s['metadata']})
        if st != 200 or not r.get('results'):
            print('seed failed', s['key'], st, r); continue
        rec['seeded'].append({'key': s['key'], 'id': r['results'][0]['id'], 'text': s['text'], 'metadata': s['metadata']})
        print('seeded', s['key'])
    time.sleep(2)
    rec['searches'] = []
    for d, qs in QUERIES.items():
        for q in qs:
            st, r = call('https://api.mem0.ai/v2/memories/search/', {'query': q, 'filters': {'user_id': USER}, 'top_k': 4})
            res = [{k: x.get(k) for k in ('id', 'memory', 'score', 'metadata', 'created_at')} for x in r] if st == 200 and isinstance(r, list) else []
            rec['searches'].append({'date': d, 'query': q, 'status': st, 'results': res})
            print(d, q[:50], len(res), 'memories')
    rec['generated_at'] = datetime.now().astimezone().isoformat(timespec='seconds')
    json.dump(rec, open(OUT, 'w'), indent=1, ensure_ascii=False)
    print('recorded', len(rec['seeded']), 'memories,', len(rec['searches']), 'searches ->', OUT)

if __name__ == '__main__':
    main()
