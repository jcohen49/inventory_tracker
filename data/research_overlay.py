"""Merges the recorded research (research/tavily.json, research/mem0.json) into the Agentic Insights page data.

Used by build_agentic_page_data.py. Nothing here calls the network: Tavily and Mem0 were queried once by
research_tavily.py and research_mem0.py, and their raw results are read back from data/research/.

  Oct 6, 7 and 10: external-influence cards, a cited reasoning section and Mem0 memory cards come from the recorded results.
  Past days:       a calamity check from the recorded Tavily news searches (real incidents where they were found).
"""
import json, os, re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))

def load(p):
    return json.load(open(os.path.join(HERE, p)))

TAV = load('research/tavily.json')
MEM = load('research/mem0.json')
Q = {q['id']: q for q in TAV['queries']}

def pretty(iso):
    return datetime.fromisoformat(iso).strftime('%b %-d')

def dl(iso):
    return f'<<{iso}|{pretty(iso)}>>'

def clean(t):
    t = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', t or '')
    t = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', t)
    return re.sub(r'\s+', ' ', re.sub(r'[#>*]', ' ', t)).strip()

def card(qid, urlpart, find=None, n=250):
    """One recorded Tavily result, trimmed to the sentence that matters."""
    x = next(r for r in Q[qid]['results'] if urlpart in r['url'])
    text = clean(x['content'])
    m = re.search(find, text, re.I) if find else None
    if m:
        a = max(0, m.start() - 60)
        snip = ('…' if a else '') + text[a:a + n].strip() + '…'
    else:
        snip = text[:n].strip() + ('…' if len(text) > n else '')
    return {'type': 'tavily', 'query': Q[qid]['query'], 'title': clean(x['title'])[:110], 'url': x['url'],
            'domain': x['url'].split('/')[2].replace('www.', ''), 'snippet': snip, 'score': round(x['score'], 2),
            'verified': True, 'placeholder': False, 'published': x.get('published_date'), 'source_id': None}

def top_cards(qid, k=3, n=200):
    return [card(qid, r['url'], n=n) for r in Q[qid]['results'][:k]]

# ---------------------------------------------------------------- Mem0
SEARCH = {}
for s in MEM['searches']:
    for x in s['results']:
        SEARCH.setdefault((s['date'], x['id']), {**x, 'query': s['query']})

def mem_src(d, prefix, truth, labels):
    x = next(v for (dd, i), v in SEARCH.items() if dd == d and i.startswith(prefix))
    md = x['metadata'] or {}
    dates = [md['date']] if md.get('date') else list(md.get('dates', []))
    linked = [{'date': dt, 'event': labels.get(dt, 'no event'), 'actual_items': truth[dt]['actual_items'],
               'expected_items': round(truth[dt]['expected_items']), 'baseline_items': round(truth[dt]['baseline_expected_items']),
               'vs_baseline_pct': round((truth[dt]['actual_items'] / truth[dt]['baseline_expected_items'] - 1) * 100, 1),
               'revenue': truth[dt]['actual_revenue']} for dt in dates if dt in truth][:4]
    marked = re.sub(r'\d{4}-\d{2}-\d{2}', lambda m: dl(m.group(0)) if m.group(0) in truth else m.group(0), x['memory'])
    return {'type': 'mem0', 'memory_id': x['id'], 'obj_url': f"https://api.mem0.ai/v1/memories/{x['id']}/", 'query': x['query'],
            'memory': x['memory'], 'memory_marked': marked, 'relevance': x['score'], 'metadata': md, 'linked_days': linked,
            'recorded_at': x.get('created_at')}

# ---------------------------------------------------------------- the three target days
def research_day(d, day, truth, labels):
    ins = day['insight']
    adj = ins['adjustments']
    sql = next(s for s in ins['sources'] if s['type'] == 'sql')
    sources = [sql]
    def cite(c):
        c['source_id'] = len(sources) + 1
        sources.append({'id': c['source_id'], **{k: v for k, v in c.items() if k != 'source_id'}})
        return f"[{c['source_id']}]"
    def cite_mem(prefix):
        m = mem_src(d, prefix, truth, labels)
        m['id'] = len(sources) + 1
        sources.append(m)
        return f"[{m['id']}]"
    def row(eid):
        return next((r['delta'] for r in adj['rows'] if r['event_id'] == eid), 0)
    stat, fc = adj['stat'], adj['forecast']
    pct = (fc / stat - 1) * 100
    items = {i['event_id']: i for h in day['external']['hotspots'] for i in h['items']}
    items.update({i['event_id']: i for i in day['external']['other'] if i.get('event_id')})

    def give(eid, cards):
        """Attach recorded Tavily cards to an event: first is the primary source, the rest are extra evidence."""
        it = items[eid]
        it['tavily'], it['more'] = cards[0], cards[1:]
        it['source_id'] = None
        return it

    hot = {h['venue']: h for h in day['external']['hotspots']}
    other = []
    parts = []
    trace_t = 0

    if d == '2026-10-06':
        w, g = 'warriors-2026-10-06', 'gne-2026-10-06'
        c_night = card('2026-10-06:confirm0', 'nightout.com', r'start time')
        c_nba = card('2026-10-06:confirm0', 'nba.com/game/lal-vs-gsw', r'Lakers @ Warriors')
        c_gne = card('2026-10-06:moscone', 'yerbabuena.org', r'GNE 2026')
        give(w, [c_night, c_nba]); give(g, [c_gne])
        hot['Moscone Center']['verdict'] = 'GNE 2026 is on the Moscone Center calendar for Oct 6 to 8, 9am to 5pm.'
        hot['Oracle Park']['verdict'] = "No Oracle Park event found for Oct 6. The Giants' season is over; the results are off-season pages."
        hot['Chase Center']['verdict'] = 'Warriors vs Lakers preseason, Tuesday 7:00 PM PT, confirmed by two sources.'
        hot['Oracle Park']['cards'] = top_cards('2026-10-06:oracle', 2)
        hot['Moscone Center']['query'] = Q['2026-10-06:moscone']['query']; hot['Oracle Park']['query'] = Q['2026-10-06:oracle']['query']
        hot['Chase Center']['query'] = Q['2026-10-06:confirm0']['query']
        c_fleet = card('2026-10-06:other', 'city-guide/october', r'Brass Quintet')
        other.append({'event_id': None, 'name': 'Fleet Fest: Brass Quintet, 12:30 pm, Salesforce Park', 'category': 'Other event', 'venue': 'Downtown', 'miles': None,
                      'start': '', 'end': '', 'effect_pct': 0, 'direction': 'flat', 'note': 'Free, part of Fleet Week (Oct 4 to 12). Too small to move sales.', 'tavily': c_fleet, 'more': [], 'source_id': None})
        other_query = Q['2026-10-06:other']['query']
        t2, t3, t4 = cite(c_night), cite(c_nba), cite(c_gne)
        m1, m2, m3 = cite_mem('601efaef'), cite_mem('cb360c22'), cite_mem('6ee73e90')
        parts = [
            f"Statistical prediction for a Tuesday is {stat} items {cite_sql(sql)}. The agent forecasts {fc} ({pct:+.0f}%): {row(w):+d} from the Warriors game and {row(g):+d} from a Moscone conference.",
            f"Tavily confirms Warriors vs Lakers (preseason) at Chase Center, Tuesday Oct 6, 7:00 PM PT {t2} {t3}. Moscone Center lists GNE 2026 on Oct 6 to 8, 9am to 5pm {t4}. The Oracle Park search found no event that day.",
            f"Mem0 recalls that Valkyries nights at Chase Center lifted the truck +11% to +17% ({dl('2026-09-18')}, {dl('2026-09-19')}, {dl('2026-10-02')}, {dl('2026-10-04')}), with the extra sales 17:00 to 18:00 {m1}. "
            f"It also recalls that Moscone conferences such as Dreamforce ({dl('2026-09-15')} to {dl('2026-09-17')}) added about +15% to +20% at lunch {m2}.",
            f"Why the Warriors lift is {row(w):+d} items ({row(w) / stat * 100:+.0f}%), above a Valkyries night: a Warriors-Lakers game draws a bigger crowd to the same arena. Why not higher: it is preseason, a Tuesday, and a 7:00 PM tip-off puts most of the extra sales in the 16:00 to 19:00 window. "
            f"The conference adds a second hump at lunch, 11:30 to 14:00. Mem0 also warns that the lunch spikes on {dl('2026-09-09')}, {dl('2026-09-23')} and {dl('2026-09-27')} were Giants day games, not Chase Center events {m3}, so the agent does not credit lunch to the arena."]
        trace_t = 4

    elif d == '2026-10-07':
        v, r_, g = 'valkyries-2026-10-07', 'rodwave-2026-10-07', 'gne-2026-10-07'
        c_w = card('2026-10-07:confirm0', 'lva-vs-gsv-1042600212', r'Wednesday, October 7th')
        c_tn = card('2026-10-07:confirm1', 'ticketnews.com', r'Chase Center')
        c_tm = card('2026-10-07:confirm1', 'ticketmaster.com/rod-wave', r'Oct 09')
        c_bt = card('2026-10-07:confirm1', 'bandsintown.com', r'Chase Center')
        c_gne = card('2026-10-07:moscone', 'yerbabuena.org', r'GNE 2026')
        give(v, [c_w]); give(r_, [c_tn, c_tm, c_bt]); give(g, [c_gne])
        hot['Moscone Center']['verdict'] = 'GNE 2026 (day 2 of Oct 6 to 8), 9am to 5pm.'
        hot['Oracle Park']['verdict'] = 'No Oracle Park event found for Oct 7.'
        hot['Chase Center']['verdict'] = 'Two events listed for the same evening. Sources disagree on the Rod Wave date: Oct 7 (TicketNews) vs Oct 9 (Ticketmaster, Bandsintown).'
        hot['Oracle Park']['cards'] = top_cards('2026-10-07:oracle', 2)
        hot['Moscone Center']['query'] = Q['2026-10-07:moscone']['query']; hot['Oracle Park']['query'] = Q['2026-10-07:oracle']['query']
        hot['Chase Center']['query'] = Q['2026-10-07:confirm1']['query']
        c_fleet = card('2026-10-07:other', 'city-guide/october', r'USAF Band')
        other.append({'event_id': None, 'name': 'Fleet Fest: USAF Band of the Golden West, 5:00 pm, Pier 39', 'category': 'Other event', 'venue': 'Northern waterfront', 'miles': None,
                      'start': '', 'end': '', 'effect_pct': 0, 'direction': 'flat', 'note': 'Free, part of Fleet Week. Far from the truck.', 'tavily': c_fleet, 'more': [], 'source_id': None})
        other_query = Q['2026-10-07:other']['query']
        t2, t3, t4, t5 = cite(c_w), cite(c_tn), cite(c_tm), cite(c_gne)
        m1, m2, m3 = cite_mem('601efaef'), cite_mem('c6afbd11'), cite_mem('6ee73e90')
        parts = [
            f"Statistical prediction for a Wednesday is {stat} items {cite_sql(sql)}. The agent forecasts {fc} ({pct:+.0f}%): {row(v):+d} from the Valkyries game, {row(r_):+d} from Rod Wave and {row(g):+d} from a Moscone conference.",
            f"Tavily lists the Valkyries vs Aces semifinal at Chase Center on Wednesday Oct 7; wnba.com shows 9:30 PM ET, which is 6:30 PM PT {t2}. Moscone Center lists GNE 2026 day 2 {t5}.",
            f"Tavily also lists Rod Wave at Chase Center on Oct 7 {t3}, but Ticketmaster shows the same tour at Chase Center on Oct 9 {t4}. Two events cannot share the arena that evening, so the agent treats the Rod Wave date as unresolved: it keeps it on Oct 7, counts it at a reduced weight, and lowers confidence to low. "
            f"It will re-check these listings at the end of the day.",
            f"Mem0 recalls that Valkyries games lifted the truck +11% on {dl('2026-10-02')} and +17% on the semifinal opener {dl('2026-10-04')} {m1} {m2}. "
            f"The +87% on {dl('2026-09-27')} was a Giants day game, not the Valkyries {m3}, so the agent discounts it.",
            f"Why a lift of {fc - stat:+d} items: a playoff semifinal crowd arrives early, so sales build from about 15:30 and peak 17:30 to 18:30; the conference adds a lunch hump; and Rod Wave's doors push a second wave of arrivals before 20:00. "
            f"The SQL baseline says a Wednesday has been {stat} items with no events, so most of this day is event-driven and the range is wide ({day['range'][0]} to {day['range'][1]})."]
        trace_t = 5

    elif d == '2026-10-10':
        w, a = 'warriors-2026-10-10', 'fleet-2026-10-10'
        c_axs = card('2026-10-10:confirm0', 'axs.com', r'Sat Oct 10, 2026')
        c_kings = card('2026-10-10:confirm0', 'nba.com/kings', r'Saturday, October 10, 2026')
        c_sv = card('2026-10-10:confirm0', 'stubhub.com', r'October 10, 2026')
        c_fw = card('2026-10-10:other', 'city-guide/october', r'Fleet Week returns')
        c_mos = card('2026-10-10:moscone', 'portal.sftravel.com', r'Disrupt 2026')
        c_mos2 = card('2026-10-10:moscone', 'moscone.com', r'SEMICON West')
        give(w, [c_axs, c_kings, c_sv]); give(a, [c_fw])
        hot['Moscone Center']['verdict'] = 'No Moscone Center event on Oct 10. Next up: TechCrunch Disrupt and SEMICON West, Oct 12 to 15.'
        hot['Moscone Center']['cards'] = [c_mos, c_mos2]
        hot['Oracle Park']['verdict'] = 'No Oracle Park event found for Oct 10.'
        hot['Oracle Park']['cards'] = top_cards('2026-10-10:oracle', 2)
        hot['Moscone Center']['query'] = Q['2026-10-10:moscone']['query']; hot['Oracle Park']['query'] = Q['2026-10-10:oracle']['query']
        hot['Chase Center']['query'] = Q['2026-10-10:confirm0']['query']
        hot['Chase Center']['verdict'] = 'Warriors vs Kings preseason, Saturday 5:30 PM PT, confirmed by four sources.'
        c_ss = card('2026-10-10:other', 'sf.funcheap.com/2026/10/10', r'Second Saturdays')
        c_lu = card('2026-10-10:other', 'city-guide/october', r'Lunada')
        other.append({'event_id': None, 'name': 'Second Saturdays at Union Square: Bollywood Garba', 'category': 'Other event', 'venue': 'Union Square', 'miles': None, 'start': '', 'end': '',
                      'effect_pct': 0, 'direction': 'flat', 'note': 'Downtown street event, well away from the ballpark.', 'tavily': c_ss, 'more': [], 'source_id': None})
        other.append({'event_id': None, 'name': 'Lunada New Moon Fest, 5:00 to 10:00 pm', 'category': 'Other event', 'venue': 'Galería de la Raza, Mission', 'miles': None, 'start': '', 'end': '',
                      'effect_pct': 0, 'direction': 'flat', 'note': 'Neighbourhood festival in the Mission.', 'tavily': c_lu, 'more': [], 'source_id': None})
        other_query = Q['2026-10-10:other']['query']
        t2, t3, t4, t5 = cite(c_axs), cite(c_kings), cite(c_fw), cite(c_mos)
        m1, m2, m3, m4 = cite_mem('33f696ca'), cite_mem('98dc5f4a'), cite_mem('967369c1'), cite_mem('601efaef')
        parts = [
            f"Statistical prediction for a Saturday is {stat} items {cite_sql(sql)}. The agent forecasts {fc} ({pct:+.0f}%): {row(w):+d} from the Warriors game and {row(a):+d} from the Fleet Week air show.",
            f"Tavily confirms Warriors vs Kings (preseason) at Chase Center, Saturday Oct 10, 5:30 PM PT {t2} {t3}. Funcheap lists SF Fleet Week for Oct 4 to 12 {t4}. Moscone Center is quiet that day; its next events start Oct 12 {t5}.",
            f"Mem0's closest match is {dl('2026-09-19')}, a Saturday Valkyries game at the same 17:30 start: {truth['2026-09-19']['actual_items']} items, +17% over trend {m1}. "
            f"A plain Saturday with no event, {dl('2026-09-05')}, still sold {truth['2026-09-05']['actual_items']} items (+16%), so the Saturday trend already runs hot {m2}. "
            f"The Saturday Disney concert on {dl('2026-10-03')} came in at -11%, which is why the agent keeps the game lift modest {m3} {m4}.",
            f"Why this matters for the day's shape: a 17:30 tip-off pulls the pre-game rush to about 14:30 to 17:30, where it overlaps the tail of the air show, so the usual 14:00 to 16:00 lull largely disappears. "
            f"The agent counts the air show as a small spillover (+10%) because the show is up the northern waterfront."]
        trace_t = 4
    else:
        return

    hot['Chase Center'].setdefault('cards', [])
    for h in hot.values():
        h.setdefault('cards', []); h.setdefault('verdict', None)
    day['external'] = {'hotspots': list(hot.values()), 'other': [i for i in day['external']['other'] if i.get('event_id')] + other, 'other_query': other_query}
    ins['sources'] = sources
    ins['summary'] = ' '.join(parts)
    ins['trace'] = {'sql': 1, 'tavily': trace_t, 'mem0': sum(1 for s in sources if s['type'] == 'mem0')}
    ins['note'] = (f"Scheduled to run at the end of the day on {pretty(d)} (21:30); the agent will re-check these listings first. "
                   f"Research recorded {TAV['generated_at'][:10]} (Tavily) and {MEM['generated_at'][:10]} (Mem0).")
    # the cited cards on events now carry their ids (cite() sets them on the shared dicts)

def cite_sql(sql):
    return '[1]'

# ---------------------------------------------------------------- past days: calamity check
PICKS = {
    '2026-09-24': [('car-slams-into-hydrant', 'A car hit a hydrant near Oracle Park and a geyser flooded King Street', '0.2 mi')],
    '2026-09-30': [('ferry-building-power-outage', 'Power outage at the Ferry Building during the morning commute', '1.3 mi')],
    '2026-10-01': [('sf-financial-district-fire', 'Fire in Financial District vaults forced evacuations and gridlock', '1.3 mi'),
                   ('reported-vault-fires', 'Shelter-in-place order for reported vault fires and explosions in the Financial District', '1.3 mi')],
    '2026-10-03': [('soma-fire-battery', 'A bicycle-battery fire evacuated a SoMa apartment building', '1 mi')],
}

def calamity(d, day, truth):
    q = Q.get(f'{d}:calamity')
    ins = day.get('insight')
    if not q or not ins:
        return
    srcs = ins['sources']
    def add(c):
        c['source_id'] = len(srcs) + 1
        srcs.append({'id': c['source_id'], **{k: v for k, v in c.items() if k != 'source_id'}})
        return f"[{c['source_id']}]"
    t = truth[d]; actual = t['actual_items']; pct = round((actual / t['baseline_expected_items'] - 1) * 100)
    picks = PICKS.get(d, [])
    cards, tags, texts = [], [], []
    for urlpart, headline, dist in picks:
        c = card(f'{d}:calamity', urlpart, n=220)
        c['distance'] = dist
        cards.append(c); tags.append(add(c)); texts.append((headline, dist))
    if picks:
        found = '; '.join(f'{h[0].lower() + h[1:]}, about {dist} away {tg}' for (h, dist), tg in zip(texts, tags))
        tail = {'2026-09-24': f" The truck still sold {actual} items, {pct:+d}% against trend, so it does not look like it hurt sales.",
                '2026-09-30': ' With the drizzle, it fits a weak morning.',
                '2026-10-01': ' That is the likeliest source of the unexplained group orders at lunch, though nothing confirms the link (hypothesis).',
                '2026-10-03': ' No sign it affected sales.'}.get(d, '')
        ins['summary'] += f" Calamity check (Tavily news): {found}.{tail}"
        name, eff, cls = 'Calamity check: incident near the truck', 'Incident nearby', 'warn'
    else:
        c = {'type': 'tavily', 'query': q['query'], 'title': 'No incidents near the truck', 'url': '', 'domain': '',
             'snippet': f"{len(q['results'])} news results for {pretty(d)} were scanned; none concerned the Oracle Park, SoMa or South Beach area.",
             'score': None, 'verified': True, 'placeholder': False, 'published': None, 'source_id': None}
        cards.append(c)
        ins['summary'] += f" Calamity check (Tavily news): nothing reportable near Oracle Park, SoMa or South Beach {add(c)}."
        name, eff, cls = 'Calamity check: nothing found', 'None found', 'done'
    day['external']['other'].append({'event_id': None, 'name': name, 'category': 'Tavily news', 'venue': 'Oracle Park, SoMa, South Beach', 'miles': None,
                                     'start': '', 'end': '', 'effect_pct': 0, 'direction': 'flat', 'eff_label': eff, 'eff_cls': cls,
                                     'note': picks and 'Real incident found in recorded news results.' or 'Searched fires, outages, evacuations, protests and closures.',
                                     'tavily': cards[0], 'more': cards[1:], 'source_id': cards[0]['source_id']})

def apply(days, truth, events_by_day):
    labels = {}
    for d, evs in events_by_day.items():
        labels[d] = evs[0]['name'] if evs else 'no event'
    for d, day in days.items():
        if d in ('2026-10-06', '2026-10-07', '2026-10-10'):
            research_day(d, day, truth, labels)
        elif day['status'] == 'past':
            calamity(d, day, truth)
    # trace counts for every day that has an insight
    for day in days.values():
        ins = day.get('insight')
        if ins and 'trace' not in ins:
            c = lambda t: sum(1 for s in ins['sources'] if s['type'] == t)
            ins['trace'] = {'sql': c('sql'), 'tavily': c('tavily'), 'mem0': c('mem0')}
