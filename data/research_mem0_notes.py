#!/usr/bin/env python3
"""Saves the end-of-day reasoning note for each past day (Sep 5 to Oct 4) to Mem0 and records what was saved.

Each note correlates that day's external influences with how sales moved (see mem0_notes.py).
Output: data/research/mem0_notes.json (memory ids, text, metadata). The website only reads this recorded file.
The API key is read from ../.env and never written to the output.
    python3 data/research_mem0_notes.py        # skips days already saved
"""
import json, os, urllib.request, urllib.error
from datetime import datetime
import mem0_notes, research_overlay

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'research', 'mem0_notes.json')
env = dict(l.strip().split('=', 1) for l in open(os.path.join(HERE, '..', '.env')) if '=' in l and not l.startswith('#'))
HDR = {'Authorization': 'Token ' + env['MEM0_API_KEY'], 'Content-Type': 'application/json'}
USER = 'mauricios-burrito-truck'

def add(text, metadata):
    req = urllib.request.Request('https://api.mem0.ai/v1/memories/', method='POST', headers=HDR, data=json.dumps({
        'messages': [{'role': 'user', 'content': text}], 'user_id': USER, 'infer': False, 'async_mode': False, 'metadata': metadata}).encode())
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())['results'][0]['id']
    except urllib.error.HTTPError as e:
        print('failed', e.code, e.read().decode()[:200])

def main():
    rec = json.load(open(OUT)) if os.path.exists(OUT) else {'user_id': USER, 'notes': []}
    have = {n['date'] for n in rec['notes']}
    truth = {t['date']: t for t in json.load(open(os.path.join(HERE, 'ground_truth.json')))}
    events = {}
    for e in json.load(open(os.path.join(HERE, 'events.json'))):
        events.setdefault(e['date'], []).append(e)
    for d in sorted(truth):
        if d in have:
            continue
        pred = json.load(open(os.path.join(HERE, 'predictions', d + '.json')))
        picks = [(h, dist) for _, h, dist in research_overlay.PICKS.get(d, [])]
        n = mem0_notes.build(d, pred, events.get(d, []), truth[d], picks)
        mid = add(n['text'], n['metadata'])
        if mid:
            rec['notes'].append({'date': d, 'id': mid, 'text': n['text'], 'metadata': n['metadata'],
                                 'saved_at': datetime.now().astimezone().isoformat(timespec='seconds')})
            print('saved', d)
    rec['notes'].sort(key=lambda n: n['date'])
    json.dump(rec, open(OUT, 'w'), indent=1, ensure_ascii=False)
    print('recorded', len(rec['notes']), 'notes ->', OUT)

if __name__ == '__main__':
    main()
