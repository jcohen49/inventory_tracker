#!/usr/bin/env python3
"""Builds data/orders/ and data/predictions/ and adds placeholder events.

  orders/YYYY-MM-DD.json       Sep 5 - Oct 4: the real simulated sales from sales.json, grouped into orders.
                               Oct 5 (today): placeholder sales generated up to 15:00, shaped by that day's events.
  predictions/YYYY-MM-DD.json  Sep 5 - Nov 3: expected sales by hour and by item, with the events driving them.
  events.json                  Existing events are kept; placeholder events (placeholder: true) are appended.

Existing sales and ground truth are never modified. Seeded: output is identical on every run.
    python3 data/generate_orders_predictions.py
"""
import json, math, os, random
from collections import defaultdict, Counter
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = date(2026, 10, 5)
AS_OF_HOUR = 15              # today's sales are generated up to 15:00
LAST_PRED = date(2026, 11, 3)
rng = random.Random(20261005)

# ---------------------------------------------------------------- baselines (measured from the no-event days in sales.json)
DOW_BASE = {'Monday': 128.4, 'Tuesday': 137.0, 'Wednesday': 145.6, 'Thursday': 165.9, 'Friday': 231.4, 'Saturday': 248.6, 'Sunday': 187.4}
HOUR_SHARE = {11: .114, 12: .229, 13: .098, 14: .042, 15: .047, 16: .051, 17: .092, 18: .18, 19: .10, 20: .048}
MIX = {'burrito': .263, 'tacos': .196, 'bowl': .146, 'nachos': .10, 'quesadilla': .09, 'chips-guac': .071,
       'chips-queso': .057, 'salad': .039, 'side-rice': .02, 'side-beans': .019}
# how much an item's share moves when an event rush is on (README: more nachos/tacos/chips, fewer bowls/salads)
RUSH_SHIFT = {'nachos': .6, 'tacos': .4, 'chips-queso': .5, 'chips-guac': .4, 'bowl': -.3, 'salad': -.4}
NAMES = {'burrito': 'Signature Burrito', 'tacos': 'Street Tacos (3)', 'bowl': 'Burrito Bowl', 'nachos': 'Loaded Nachos',
         'quesadilla': 'Quesadilla', 'chips-guac': 'Chips & Guac', 'chips-queso': 'Chips & Queso', 'salad': 'Taco Salad',
         'side-rice': 'Side of Rice', 'side-beans': 'Side of Beans'}

# ---------------------------------------------------------------- placeholder events
def E(eid, name, cat, venue, dist, d, start, end, cap, status, strength, model, note, confirmed=False, src=None):
    return {'event_id': eid, 'name': name, 'category': cat, 'venue': venue, 'distance_from_oracle_park_miles': dist,
            'date': d, 'start_time': start, 'estimated_end_time': end, 'start_time_confirmed': confirmed,
            'venue_capacity': cap, 'status': status, 'source': src or 'placeholder', 'placeholder': src is None,
            'model': model, 'expected_effect_pct_of_baseline': round(strength * 100), 'note': note}

NEW_EVENTS = [
    # --- past (inside the 30-day window; each is consistent with that day's real sales in ground_truth.json)
    E('ferry-farmers-2026-09-10', 'Ferry Building Farmers Market', 'Community market', 'Ferry Building', 1.2, '2026-09-10', '10:00', '14:00', 5000, 'took place', 0.0, 'minor', 'Daytime market a mile up the Embarcadero; no measurable effect on the truck.'),
    E('muni-trackwork-2026-09-14', 'Muni N-Judah track work: King St lane closure', 'Road closure', 'King St & 4th St', 0.2, '2026-09-14', '07:00', '19:00', 0, 'took place', -0.04, 'closure', 'One lane closed on the approach to the ballpark; slightly fewer walk-ups.'),
    E('weather-rain-2026-09-29', 'Light rain, 58F', 'Weather', 'San Francisco', 0.0, '2026-09-29', '08:00', '22:00', 0, 'took place', -0.15, 'weather', 'Drizzle all day; fewer people lingering outdoors.'),
    # --- today
    E('muni-trackwork-2026-10-05', 'Central Subway track work: King St lane closure', 'Road closure', 'King St & 3rd St', 0.2, '2026-10-05', '11:00', '17:00', 0, 'in progress', -0.08, 'closure', 'Lane closure along the truck\'s block through mid-afternoon.', True),
    # --- future
    E('warriors-2026-10-06', 'Golden State Warriors vs. Los Angeles Lakers (preseason)', 'NBA preseason game', 'Chase Center', 0.9, '2026-10-06', '19:00', '21:15', 18064, 'scheduled', 0.20, 'chase', 'Tuesday, 7:00 PM PT. Confirmed by Tavily (nba.com, nightout.com).', True, 'https://www.nba.com/game/lal-vs-gsw-0012600010'),
    E('gne-2026-10-06', 'GNE 2026 (day 1)', 'Conference', 'Moscone Center', 0.9, '2026-10-06', '09:00', '17:00', 15000, 'scheduled', 0.12, 'conference', 'Listed on the Moscone Center calendar, Oct 6 to 8, 9am to 5pm.', True, 'https://yerbabuena.org/go/moscone-center'),
    E('gne-2026-10-07', 'GNE 2026 (day 2)', 'Conference', 'Moscone Center', 0.9, '2026-10-07', '09:00', '17:00', 15000, 'scheduled', 0.12, 'conference', 'Listed on the Moscone Center calendar, Oct 6 to 8, 9am to 5pm.', True, 'https://yerbabuena.org/go/moscone-center'),
    E('gne-2026-10-08', 'GNE 2026 (day 3)', 'Conference', 'Moscone Center', 0.9, '2026-10-08', '09:00', '17:00', 15000, 'scheduled', 0.12, 'conference', 'Listed on the Moscone Center calendar, Oct 6 to 8, 9am to 5pm.', True, 'https://yerbabuena.org/go/moscone-center'),
    E('valkyries-2026-10-07', 'WNBA Semifinals G2: Golden State Valkyries vs. Las Vegas Aces', 'WNBA playoff game', 'Chase Center', 0.9, '2026-10-07', '18:30', '20:40', 18064, 'scheduled', 0.16, 'chase', 'Wednesday. wnba.com lists 9:30 PM ET, which is 6:30 PM PT.', True, 'https://www.wnba.com/game/lva-vs-gsv-1042600212'),
    E('rodwave-2026-10-07', 'Rod Wave: Don\'t Look Down Tour', 'Concert', 'Chase Center', 0.9, '2026-10-07', '20:00', '22:30', 18064, 'scheduled', 0.12, 'chase', 'Tavily lists Chase Center on Oct 7 (TicketNews) but Ticketmaster and Bandsintown show Chase Center on Oct 9, and the Valkyries game is also at Chase Center on Oct 7. The two cannot share the arena; the date is unresolved.', True, 'https://www.ticketnews.com/2026/06/rod-wave-tickets-on-sale-in-san-francisco'),
    E('warriors-2026-10-10', 'Golden State Warriors vs. Sacramento Kings (preseason)', 'NBA preseason game', 'Chase Center', 0.9, '2026-10-10', '17:30', '19:45', 18064, 'scheduled', 0.17, 'chase', 'Saturday, 5:30 PM PT. Confirmed by Tavily (axs.com, nba.com, stubhub.com).', True, 'https://www.axs.com/events/1536580/nba-preseason-sacramento-kings-at-golden-state-warriors-tickets'),
    E('fleet-2026-10-08', 'SF Fleet Week: Blue Angels practice', 'Festival', 'Marina / Embarcadero', 3.0, '2026-10-08', '12:00', '15:00', 0, 'scheduled', 0.05, 'festival', 'SF Fleet Week (Oct 4 to 12) is listed by Funcheap; show times are not confirmed.', False, 'https://sf.funcheap.com/city-guide/october-street-fairs-festivals'),
    E('fleet-2026-10-10', 'SF Fleet Week: Air Show', 'Festival', 'Marina / Embarcadero', 3.0, '2026-10-10', '12:00', '16:00', 0, 'scheduled', 0.10, 'festival', 'SF Fleet Week air show weekend; times are not confirmed.', False, 'https://sf.funcheap.com/city-guide/october-street-fairs-festivals'),
    E('fleet-2026-10-11', 'SF Fleet Week: Air Show', 'Festival', 'Marina / Embarcadero', 3.0, '2026-10-11', '12:00', '16:00', 0, 'scheduled', 0.10, 'festival', 'SF Fleet Week air show weekend; times are not confirmed.', False, 'https://sf.funcheap.com/city-guide/october-street-fairs-festivals'),
    E('chase-2026-10-12', 'Concert at Chase Center (headliner TBA)', 'Concert', 'Chase Center', 0.9, '2026-10-12', '20:00', '22:30', 18000, 'scheduled', 0.18, 'chase', 'Placeholder concert; Indigenous Peoples\' Day holiday.'),
    E('moscone-2026-10-13', 'SEMICON West 2026 and TechCrunch Disrupt 2026 (day 1)', 'Conference', 'Moscone Center', 0.9, '2026-10-13', '09:00', '17:00', 20000, 'scheduled', 0.16, 'conference', 'Listed on the Moscone Center calendar, Oct 13 to 15, 9am to 5pm. One calendar shows TechCrunch Disrupt Oct 12 to 14.', True, 'https://www.moscone.com'),
    E('moscone-2026-10-14', 'SEMICON West 2026 and TechCrunch Disrupt 2026 (day 2)', 'Conference', 'Moscone Center', 0.9, '2026-10-14', '09:00', '17:00', 20000, 'scheduled', 0.16, 'conference', 'Listed on the Moscone Center calendar, Oct 13 to 15, 9am to 5pm. One calendar shows TechCrunch Disrupt Oct 12 to 14.', True, 'https://www.moscone.com'),
    E('thirdst-2026-10-14', 'Third St Bridge maintenance: lane closure', 'Road closure', 'Third St Bridge', 0.3, '2026-10-14', '12:00', '16:00', 0, 'scheduled', -0.07, 'closure', 'Bridge lane closure cuts afternoon foot and vehicle traffic.'),
    E('moscone-2026-10-15', 'SEMICON West 2026 and TechCrunch Disrupt 2026 (day 3)', 'Conference', 'Moscone Center', 0.9, '2026-10-15', '09:00', '17:00', 20000, 'scheduled', 0.16, 'conference', 'Listed on the Moscone Center calendar, Oct 13 to 15, 9am to 5pm. One calendar shows TechCrunch Disrupt Oct 12 to 14.', True, 'https://www.moscone.com'),
    E('oracle-2026-10-17', 'Concert at Oracle Park (headliner TBA)', 'Concert', 'Oracle Park', 0.1, '2026-10-17', '19:00', '22:30', 41000, 'scheduled', 0.85, 'oracle', 'Placeholder concert; truck would stay open to 23:00.'),
    E('oracle-2026-10-18', 'Concert at Oracle Park (headliner TBA), night 2', 'Concert', 'Oracle Park', 0.1, '2026-10-18', '18:30', '22:00', 41000, 'scheduled', 0.75, 'oracle', 'Placeholder concert; truck would stay open to 23:00.'),
    E('weather-rain-2026-10-20', 'Heavy rain forecast', 'Weather', 'San Francisco', 0.0, '2026-10-20', '06:00', '23:00', 0, 'scheduled', -0.20, 'weather', 'Placeholder forecast; steady rain keeps people indoors.'),
    E('warriors-2026-10-22', 'Warriors home opener', 'NBA game', 'Chase Center', 0.9, '2026-10-22', '19:30', '22:00', 18064, 'scheduled', 0.28, 'chase', 'Opponent and time are placeholders.'),
    E('warriors-2026-10-24', 'Warriors home game', 'NBA game', 'Chase Center', 0.9, '2026-10-24', '18:30', '21:00', 18064, 'scheduled', 0.26, 'chase', 'Opponent and time are placeholders.'),
    E('moscone-2026-10-27', 'Moscone Center conference, day 1', 'Conference', 'Moscone Center', 0.9, '2026-10-27', '09:00', '18:00', 15000, 'scheduled', 0.12, 'conference', 'Placeholder conference.'),
    E('moscone-2026-10-28', 'Moscone Center conference, day 2', 'Conference', 'Moscone Center', 0.9, '2026-10-28', '09:00', '17:00', 15000, 'scheduled', 0.12, 'conference', 'Placeholder conference.'),
    E('chase-2026-10-29', 'Concert at Chase Center (headliner TBA)', 'Concert', 'Chase Center', 0.9, '2026-10-29', '20:00', '22:30', 18000, 'scheduled', 0.18, 'chase', 'Placeholder concert.'),
    E('halloween-2026-10-31', 'Halloween evening foot traffic', 'Holiday', 'SoMa / South Beach', 0.5, '2026-10-31', '16:00', '22:00', 0, 'scheduled', 0.15, 'holiday', 'Costumed crowds heading to bars and parties after dark.'),
    E('warriors-2026-11-01', 'Warriors home game', 'NBA game', 'Chase Center', 0.9, '2026-11-01', '17:00', '19:30', 18064, 'scheduled', 0.24, 'chase', 'Opponent and time are placeholders.'),
    E('election-2026-11-03', 'Election Day: polling places nearby', 'Civic', 'South Beach', 0.4, '2026-11-03', '07:00', '20:00', 0, 'scheduled', -0.03, 'minor', 'Slightly lower commuter foot traffic; negligible.'),
]

REMOVED_IDS = {'valkyries-2026-10-06', 'warriors-2026-10-09'}   # replaced by the dated events above

def model_for(ev):
    if ev.get('model'):
        return ev['model']
    v = ev['venue']
    return 'oracle' if v == 'Oracle Park' else 'chase' if v == 'Chase Center' else 'conference' if v == 'Moscone Center' else 'minor'

def strength_for(ev):
    if 'expected_effect_pct_of_baseline' in ev:
        return ev['expected_effect_pct_of_baseline'] / 100
    return {'oracle': .40, 'chase': .15, 'conference': .17}.get(model_for(ev), 0)

def hrs(t):
    h, m = t.split(':'); return int(h) + int(m) / 60

# ---------------------------------------------------------------- hourly model
def spread(lo, hi, hours, ramp=False):
    """Fraction of a window falling in each open hour (optionally weighted toward its end)."""
    w = defaultdict(float)
    steps = 40
    for i in range(steps):
        t = lo + (hi - lo) * (i + .5) / steps
        h = int(math.floor(t))
        if h in hours:
            w[h] += (i + 1) if ramp else 1
    s = sum(w.values())
    return {h: v / s for h, v in w.items()} if s else {}

def close_hour(evs):
    late = any(model_for(e) == 'oracle' and hrs(e['start_time']) >= 17 for e in evs)
    return 23 if late else 21

def day_model(d, evs):
    """-> (hours, {hour: items}, {hour: rush_share}, baseline_total)"""
    base = DOW_BASE[d.strftime('%A')]
    hours = list(range(11, close_hour(evs)))
    exp = {h: base * HOUR_SHARE.get(h, .02) for h in hours}   # .02: a trickle in the extended late hours
    rush = {h: 0.0 for h in hours}
    for ev in evs:
        m, k = model_for(ev), strength_for(ev)
        s, e = hrs(ev['start_time']), hrs(ev['estimated_end_time'])
        lift = {}
        if m == 'oracle':
            for h, f in spread(s - 2.5, s, hours, True).items(): lift[h] = lift.get(h, 0) + .65 * f
            for h, f in spread(e, e + 1.5, hours).items(): lift[h] = lift.get(h, 0) + .35 * f
            for h in hours:                                       # crowd is inside the park
                if s <= h + .5 <= e: exp[h] *= .85
        elif m == 'chase':
            lift = spread(s - 3, s, hours, True)
        elif m == 'conference':
            lift = {h: .65 * f for h, f in spread(11.5, 14, hours).items()}
            for h, f in spread(17, 19, hours).items(): lift[h] = lift.get(h, 0) + .35 * f
        elif m == 'festival':
            lift = spread(max(s, 11), e, hours)
        elif m == 'holiday':
            lift = spread(s, e, hours, True)
        elif m in ('closure', 'weather'):
            for h in hours:
                if s <= h + .5 <= e: exp[h] *= 1 + k
            continue
        for h, f in lift.items():
            add = base * k * f
            exp[h] += add
            rush[h] += add
    rush = {h: (rush[h] / exp[h] if exp[h] > 0 else 0) for h in hours}
    return hours, exp, rush, base

def by_item(hours, exp, rush):
    out = {i: [] for i in MIX}
    for h in hours:
        w = {i: MIX[i] * max(.1, 1 + RUSH_SHIFT.get(i, 0) * min(1, rush[h] * 2.5)) for i in MIX}
        z = sum(w.values())
        for i in MIX:
            out[i].append(exp[h] * w[i] / z)
    return out

# ---------------------------------------------------------------- insight text for predictions
def at(ev):
    return '' if ev['venue'] in ev['name'] else f" at {ev['venue']}"

def ev_line(ev):
    m = model_for(ev)
    s, e = ev['start_time'], ev['estimated_end_time']
    k = strength_for(ev)
    pct = f"{abs(round(k * 100))}%"
    where = f"{ev['distance_from_oracle_park_miles']} mi away"
    if m == 'oracle':
        return f"{ev['name']}{at(ev)} ({where}, starts {s}): expect a rush from about {fmt_t(hrs(s) - 2.5)}, a lull while the crowd is inside, and a bump after the end. Roughly +{pct} on the day."
    if m == 'chase':
        return f"{ev['name']}{at(ev)} ({where}, starts {s}): a pre-event lift in the three hours before the start, roughly +{pct}."
    if m == 'conference':
        return f"{ev['name']} ({where}): attendees break for lunch around 12:00 to 14:00 with a smaller early-evening wave, roughly +{pct}."
    if m == 'festival':
        return f"{ev['name']} ({where}, {s} to {e}): mostly crowds up the waterfront, only a small spillover, roughly +{pct}."
    if m == 'holiday':
        return f"{ev['name']}: foot traffic builds from {s}, roughly +{pct} through the evening."
    if m == 'closure':
        return f"{ev['name']} ({s} to {e}): fewer walk-ups while access is restricted, roughly -{pct} over that window."
    if m == 'weather':
        return f"{ev['name']}: people stay indoors, roughly -{pct} across the day."
    return f"{ev['name']} ({where}): not expected to move sales."

def fmt_t(x):
    h = int(x); m = int(round((x - h) * 60))
    return f"{h:02d}:{m:02d}"

def drivers_for(evs):
    return [{'event_id': e['event_id'], 'name': e['name'], 'venue': e['venue'], 'distance_miles': e['distance_from_oracle_park_miles'],
             'direction': 'down' if strength_for(e) < 0 else ('flat' if strength_for(e) == 0 else 'up'),
             'expected_effect_pct': round(strength_for(e) * 100),
             'start_time': e['start_time'], 'end_time': e['estimated_end_time'], 'explanation': ev_line(e)} for e in evs]

def prep_notes(total_by_item, rush_day):
    top = sorted(total_by_item.items(), key=lambda kv: -kv[1])[:3]
    notes = [f"Expect about {round(n)} {NAMES[i]}" for i, n in top]
    if rush_day:
        notes.append('Pre-portion nachos, chips and tortillas before the rush window')
    return notes


# ---------------------------------------------------------------- agentic insights: SQL, Tavily and Mem0 sources
import hashlib
TAVILY_FALLBACK = {   # placeholder events have no verified page, so cite the organiser's home page and flag it
    'oracle': 'https://www.mlb.com/giants/ballpark', 'chase': 'https://www.chasecenter.com/events',
    'conference': 'https://www.sftravel.com/', 'festival': 'https://fleetweek.us/', 'holiday': 'https://www.sftravel.com/',
    'closure': 'https://www.sfmta.com/', 'weather': 'https://www.weather.gov/mtr/', 'minor': 'https://www.sftravel.com/'}
DOW_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
CLOSE_TIME = '21:30'

def pretty(iso):
    return datetime.fromisoformat(iso).strftime('%b %-d')

def dl(iso):
    """Date marker the page turns into a link to that day in the calendar."""
    return f'<<{iso}|{pretty(iso)}>>'

def tavily_for(ev):
    src = ev.get('source', '')
    real = src.startswith('http')
    m = model_for(ev)
    domain = (src if real else TAVILY_FALLBACK[m]).split('/')[2].replace('www.', '')
    return {'type': 'tavily', 'event_id': ev.get('event_id'), 'query': f"{ev['name']} {ev['venue']} San Francisco {pretty(ev['date'])}",
            'title': ev['name'], 'url': src if real else TAVILY_FALLBACK[m], 'domain': domain,
            'snippet': (f"{ev['category']} at {ev['venue']}, {ev['start_time']} to {ev['estimated_end_time']}"
                        + ('' if ev['start_time_confirmed'] else ' (start time not confirmed)') + '.'),
            'verified': real, 'placeholder': not real}

def analogs(ev, d, events, truth, weather_days):
    """Most recent comparable past days, with what the truck actually sold on them."""
    m, pool = model_for(ev), []
    for e in events:
        t = truth.get(e['date'])
        if e['event_id'] != ev['event_id'] and e['date'] < d and t and model_for(e) == m:
            pool.append((e['venue'] == ev['venue'], e['date'], e['name'], t))
    if m == 'weather':
        have = {x[1] for x in pool}
        pool += [(False, dt, name, truth[dt]) for dt, name in weather_days if dt < d and dt not in have]
    pool.sort(key=lambda x: (x[0], x[1]), reverse=True)
    seen, out = set(), []
    for _, dt, name, t in pool:
        if dt in seen: continue
        seen.add(dt)
        out.append({'date': dt, 'event': name, 'category': next((e['category'] for e in events if e['date'] == dt and e['name'] == name), 'Weather'), 'actual_items': t['actual_items'], 'expected_items': round(t['expected_items']),
                    'baseline_items': round(t['baseline_expected_items']),
                    'vs_baseline_pct': round((t['actual_items'] / t['baseline_expected_items'] - 1) * 100, 1),
                    'revenue': t['actual_revenue']})
        if len(out) == 3: break
    return out

def mem0_for(ev, d, found, kind='event'):
    if found:
        avg = sum(a['vs_baseline_pct'] for a in found) / len(found)
        cats = ' / '.join(dict.fromkeys(x['category'].lower() for x in found))
        text = (f"Comparable {ev['venue']} days ({cats}): the truck averaged {avg:+.0f}% vs baseline over the last {len(found)} day(s); "
                f"most recent {dl(found[0]['date'])} at {found[0]['actual_items']} items.")
        rel = round(.93 - .06 * (len(found) < 3) - .1 * (found[0]['event'] != ev['name'] and False), 2)
    else:
        avg = None
        text = f"No close past analogue for {ev['name'].lower()}; falling back to the typical day-of-week baseline."
        rel = .41
    mid = 'mem_' + hashlib.sha1(f"{ev['event_id']}|{d}".encode()).hexdigest()[:10]
    return {'type': 'mem0', 'memory_id': mid, 'query': f"past sales near {ev['venue']} on {ev['category'].lower()} days",
            'memory': text, 'relevance': rel, 'avg_vs_baseline_pct': None if avg is None else round(avg, 1), 'linked_days': found}

def normal_day_mem0(d, dow, truth):
    ids = [t for t in truth.values() if t['day_of_week'] == dow and t['date'] < d and t['label'] == 'no_event']
    ids.sort(key=lambda t: t['date'], reverse=True)
    linked = [{'date': t['date'], 'event': 'no event', 'actual_items': t['actual_items'], 'expected_items': round(t['expected_items']),
               'baseline_items': round(t['baseline_expected_items']),
               'vs_baseline_pct': round((t['actual_items'] / t['baseline_expected_items'] - 1) * 100, 1), 'revenue': t['actual_revenue']} for t in ids[:3]]
    if linked:
        text = f"Past event-free {dow}s sold {', '.join(str(x['actual_items']) for x in linked)} items ({', '.join(dl(x['date']) for x in linked)})."
    else:
        text = f"No event-free {dow} on record yet; using the trend baseline."
    return {'type': 'mem0', 'memory_id': 'mem_' + hashlib.sha1(f"normal|{dow}|{d}".encode()).hexdigest()[:10],
            'query': f"typical {dow} sales with no nearby events", 'memory': text, 'relevance': .88 if linked else .4,
            'avg_vs_baseline_pct': round(sum(x['vs_baseline_pct'] for x in linked) / len(linked), 1) if linked else None, 'linked_days': linked}

def baseline_sql(d, dow, base, truth):
    n = sum(1 for t in truth.values() if t['day_of_week'] == dow and t['date'] < d)
    q = ("SELECT day_of_week,\n"
         "       ROUND(AVG(baseline_items), 1) AS baseline_items,\n"
         "       COUNT(*)                      AS n_days\n"
         "FROM   daily_trend\n"
         f"WHERE  day_of_week = '{dow}'\n"
         f"  AND  date < '{d}'\n"
         "GROUP  BY day_of_week;")
    return {'type': 'sql', 'database': 'sales_history', 'query': q,
            'result': {'columns': ['day_of_week', 'baseline_items', 'n_days'], 'rows': [[dow, round(base, 1), n]]},
            'note': 'daily_trend rolls the sales table up per day; baseline_items is the no-event trend for that weekday.'}

def reorder_actions(d, status, base, item_tot, total):
    delta = {i: item_tot[i] - base * MIX[i] for i in MIX}
    tort = delta['burrito'] + 3 * delta['tacos'] + delta['quesadilla']
    chips = .25 * (delta['nachos'] + delta['chips-guac'] + delta['chips-queso'])
    pct = (total / base - 1) * 100
    plan = status != 'past'
    when = f"at the end of the day on {pretty(d)}" if plan else f"at end of day on {pretty(d)} ({CLOSE_TIME})"
    def act(kind, ing, change, detail):
        detail = detail if plan else detail[0].upper() + detail[1:]
        return {'type': kind, 'ingredient': ing, 'change': change, 'status': 'scheduled' if plan else 'completed',
                'detail': ('Will ' if plan else '') + detail + ' ' + when + '.', 'runs_at': 'end of day' if plan else CLOSE_TIME}
    out = []
    if abs(pct) < 6:
        out.append(act('no_change', None, '0', 'leave reorder alerts at standard par' if plan else 'left reorder alerts at standard par'))
        return out
    sign = 1 if pct > 0 else -1
    for ing, qty, unit in (('Large Flour Tortilla', tort, 'tortillas'), ('Tortilla Chips', chips, 'bags')):
        q = max(1, round(abs(qty))) if abs(qty) >= .5 else 0
        if not q: continue
        if sign > 0:
            out.append(act('reorder_alert_updated', ing, f'+{q} {unit}', ('raise' if plan else 'raised') + f" the {ing} reorder alert by {q} {unit} to cover the expected rush"))
        else:
            out.append(act('reorder_alert_deferred', ing, f'-{q} {unit}', ('defer' if plan else 'deferred') + f" the {ing} reorder alert (about {q} {unit} less needed)"))
    return out or [act('no_change', None, '0', 'leave reorder alerts at standard par')]


# ---------------------------------------------------------------- statistical prediction, external influences, adjustments
HOTSPOTS = [('Oracle Park', 0.1), ('Chase Center', 0.9), ('Moscone Center', 0.9)]

def stat_block(d, hours, base, truth):
    """Weekday x hour trend with no events: the 'statistical prediction' the agent starts from."""
    dow = d.strftime('%A')
    h = [base * HOUR_SHARE.get(x, .02) for x in hours]
    n = sum(1 for t in truth.values() if t['day_of_week'] == dow and t['date'] < d.isoformat())
    return {'method': f'{dow} x hour seasonal average of past sales, events excluded', 'n_days': n, 'total': round(base, 1),
            'hourly': [round(v, 1) for v in h], 'low': [round(max(0, v - (.10 * v + 1.5)), 1) for v in h],
            'high': [round(v + .10 * v + 1.5, 1) for v in h], 'band': '+/-10% plus 1.5 items (about one standard deviation)',
            'sql': baseline_sql(d.isoformat(), dow, base, truth)}

def adjustments(d, evs, base, total, actual, label):
    """How the forecast moves away from the statistical prediction, one row per event."""
    _, exp_all, _, _ = day_model(d, evs)
    tot_all = sum(exp_all.values())
    rows = []
    for ev in evs:
        rest = [e for e in evs if e is not ev]
        delta = tot_all - sum(day_model(d, rest)[1].values())
        rows.append([ev, delta])
    scale = total / tot_all if tot_all else 1
    out = [{'label': ev['name'], 'event_id': ev['event_id'], 'delta': round(dl_ * scale)} for ev, dl_ in rows]
    rest = round(total) - round(base) - sum(r['delta'] for r in out)
    if abs(rest) >= 2:
        out.append({'label': 'Overlap, late hours and other known factors', 'event_id': None, 'delta': rest})
    for r in out:
        r['kind'] = 'up' if r['delta'] > 0 else 'down' if r['delta'] < 0 else 'flat'
    res = {'stat': round(base), 'rows': out, 'forecast': round(total), 'actual': actual, 'gap': None, 'gap_note': ''}
    if actual is not None:
        gap = actual - round(total); res['gap'] = gap
        note = {'event_lift_muted': 'The game-night lift never appeared: cold, foggy, windy evening.',
                'no_event_slow_day': 'Drizzle kept people away all day.',
                'decoy_busy_no_event': 'Large walk-up group orders from a nearby office; no event explains it.'}.get(label)
        res['gap_note'] = note or ('Within normal daily noise (about +/-7%).' if abs(gap) <= .08 * total else 'Not explained by any known event; flagged for the next run.')
    return res

def external_block(evs, sources, extra):
    ids = {}
    for x in sources:                      # the first Tavily source per event is the primary one
        if x['type'] == 'tavily' and x.get('event_id') and x['event_id'] not in ids:
            ids[x['event_id']] = x['id']
    def item(ev):
        k = strength_for(ev)
        return {'event_id': ev['event_id'], 'name': ev['name'], 'category': ev['category'], 'venue': ev['venue'],
                'miles': ev['distance_from_oracle_park_miles'], 'start': ev['start_time'], 'end': ev['estimated_end_time'],
                'status': ev['status'], 'placeholder': bool(ev.get('placeholder')), 'effect_pct': round(k * 100),
                'direction': 'down' if k < 0 else 'flat' if k == 0 else 'up', 'tavily': tavily_for(ev), 'source_id': ids.get(ev['event_id']),
                'more': [{'source_id': x['id'], 'tavily': {k2: v for k2, v in x.items() if k2 != 'id'}} for x in sources
                         if x['type'] == 'tavily' and x.get('event_id') == ev['event_id'] and x['id'] != ids.get(ev['event_id'])]}
    hot = []
    for venue, miles in HOTSPOTS:
        mine = [item(e) for e in evs if e['venue'] == venue]
        hot.append({'venue': venue, 'miles': miles, 'status': 'event' if mine else 'quiet', 'items': mine,
                    'check': f'{venue} events {evs[0]["date"] if evs else ""}'.strip()})
    other = [item(e) for e in evs if e['venue'] not in dict(HOTSPOTS)] + list(extra)
    return {'hotspots': hot, 'other': other}

def build_insight(d, dow, status, evs, base, total, doc_t, truth, events, weather_days, item_tot, hourly_peak, adj):
    sources = []
    def add(src):
        sources.append({'id': len(sources) + 1, **src}); return f"[{len(sources)}]"
    sq = add(baseline_sql(d, dow, base, truth))
    extra = []
    pct = (total / base - 1) * 100
    parts = []
    if status == 'past':
        parts.append(f"Sold {doc_t['actual_items']} items vs {round(total)} expected ({(doc_t['actual_items'] / total - 1) * 100:+.0f}%). "
                     f"A typical {dow} runs about {round(base)} items {sq}.")
    else:
        parts.append(f"Expected about {round(total)} items ({pct:+.0f}% vs a typical {dow} of {round(base)} {sq}), peaking around {hourly_peak}.")
    if not evs:
        m0 = normal_day_mem0(d, dow, truth)
        parts.append(f"No events within a mile, so this follows the plain weekday trend. {m0['memory']} {add(m0)}")
    for ev in evs:
        tv = add(tavily_for(ev))
        found = analogs(ev, d, events, truth, weather_days)
        mm = add(mem0_for(ev, d, found))
        line = ev_line(ev)
        parts.append(f"{line} {tv}")
        if found:
            hist = ', '.join(f"{dl(a['date'])} {a['vs_baseline_pct']:+.0f}% ({a['actual_items']} items)" for a in found)
            parts.append(f"Memory recall of similar days: {hist} {mm}.")
        else:
            parts.append(f"Memory has no close analogue, so the weekday baseline carries this one {mm}.")
    if status == 'past':
        lab = doc_t['label']
        wx = {'event_lift_muted': ('2026-09-22', 'cold, foggy, windy evening'), 'no_event_slow_day': ('2026-09-30', 'drizzle most of the day')}
        if lab in wx:
            ev = {'event_id': 'wx-' + d, 'name': f"San Francisco weather: {wx[lab][1]}", 'category': 'Weather', 'venue': 'San Francisco',
                  'date': d, 'start_time': '08:00', 'estimated_end_time': '22:00', 'start_time_confirmed': True, 'source': '', 'model': 'weather'}
            parts.append(("The expected game-night lift did not show up" if lab == 'event_lift_muted' else "Slower than a normal weekday with nothing scheduled")
                         + f"; Tavily weather lookup points to {wx[lab][1]} {add(tavily_for(ev))}.")
        elif lab == 'decoy_busy_no_event':
            ev = {'event_id': 'q-' + d, 'name': 'No events found within 1 mile', 'category': 'Search', 'venue': 'Oracle Park', 'date': d,
                  'start_time': '11:00', 'estimated_end_time': '14:00', 'start_time_confirmed': True, 'source': '', 'model': 'minor'}
            src = tavily_for(ev); src['snippet'] = '0 matching events within 1 mile for this date.'; src['results'] = 0; src['url'] = ''; src['domain'] = ''
            parts.append(f"Lunch ran well above trend with no event behind it; large walk-up group orders from a nearby office are the likeliest cause {add(src)}.")
    summary = ' '.join(parts)
    when = 'Completed at end of day.' if status == 'past' else f"Scheduled to run at the end of the day on {pretty(d)} ({CLOSE_TIME}); this is the forecast it will start from."
    return {'status': 'completed' if status == 'past' else 'scheduled', 'runs_at': CLOSE_TIME if status == 'past' else 'end of day',
            'note': when, 'summary': summary, 'sources': sources, 'adjustments': adj, 'extra_other': extra}

# ---------------------------------------------------------------- main
def main():
    ev_path = os.path.join(HERE, 'events.json')
    events = json.load(open(ev_path))
    mine = {e['event_id'] for e in NEW_EVENTS} | REMOVED_IDS
    events = [e for e in events if e['event_id'] not in mine] + NEW_EVENTS   # re-runs refresh the placeholder events
    events.sort(key=lambda e: (e['date'], e['start_time']))
    json.dump(events, open(ev_path, 'w'), indent=4, ensure_ascii=False)
    open(ev_path, 'a').write('\n')
    ev_by_day = defaultdict(list)
    for e in events:
        ev_by_day[e['date']].append(e)

    sales = json.load(open(os.path.join(HERE, 'sales.json')))
    truth = {t['date']: t for t in json.load(open(os.path.join(HERE, 'ground_truth.json')))}
    os.makedirs(os.path.join(HERE, 'orders'), exist_ok=True)
    os.makedirs(os.path.join(HERE, 'predictions'), exist_ok=True)

    # ---- orders: past days from sales.json
    day_orders = defaultdict(lambda: defaultdict(list))
    for r in sales:
        day_orders[r['date']][r['order_id']].append(r)
    by_item_samples = defaultdict(list)
    for r in sales:
        by_item_samples[r['menu_item_id']].append(r)

    def item_row(r):
        return {k: r[k] for k in ('sale_id', 'menu_item_id', 'menu_item', 'price', 'ingredient_cost', 'ingredients')}

    def write_orders(d, orders, partial, as_of=None):
        items = sum(len(o['items']) for o in orders)
        rev = round(sum(i['price'] for o in orders for i in o['items']), 2)
        cost = round(sum(i['ingredient_cost'] for o in orders for i in o['items']), 2)
        doc = {'date': d, 'day_of_week': datetime.fromisoformat(d).strftime('%A'),
               'partial': partial, 'as_of': as_of,
               'totals': {'orders': len(orders), 'items': items, 'revenue': rev, 'ingredient_cost': cost},
               'orders': orders}
        json.dump(doc, open(os.path.join(HERE, 'orders', d + '.json'), 'w'), indent=1, ensure_ascii=False)
        return doc['totals']

    index_orders = []
    for d in sorted(day_orders):
        orders = [{'order_id': oid, 'timestamp': rows[0]['timestamp'], 'items': [item_row(r) for r in rows]}
                  for oid, rows in sorted(day_orders[d].items())]
        index_orders.append({'date': d, 'partial': False, **write_orders(d, orders, False)})

    # ---- orders: today, generated up to AS_OF_HOUR
    td = TODAY.isoformat()
    hours, exp, rush, _ = day_model(TODAY, ev_by_day[td])
    next_sale = len(sales) + 1
    order_no = 0
    today_orders = []
    for h in hours:
        if h >= AS_OF_HOUR:
            break
        mean = exp[h] * rng.uniform(.93, 1.07)
        n = max(0, round(rng.gauss(mean, math.sqrt(max(mean, 1)) * .6)))
        w = {i: MIX[i] * max(.1, 1 + RUSH_SHIFT.get(i, 0) * min(1, rush[h] * 2.5)) for i in MIX}
        times = sorted(rng.uniform(h * 3600, (h + 1) * 3600) for _ in range(n))
        left, ti = n, 0
        while left > 0:
            size = min(left, rng.choices([1, 2, 3, 4], [.45, .35, .15, .05])[0])
            sec = int(times[ti]); ti += size; left -= size
            order_no += 1
            rows = []
            for _ in range(size):
                item = rng.choices(list(w), list(w.values()))[0]
                src = rng.choice(by_item_samples[item])
                rows.append({'sale_id': f'S{next_sale:06d}', 'menu_item_id': item, 'menu_item': src['menu_item'],
                             'price': src['price'], 'ingredient_cost': src['ingredient_cost'], 'ingredients': src['ingredients']})
                next_sale += 1
            today_orders.append({'order_id': f"O-{td.replace('-', '')}-{order_no:04d}",
                                 'timestamp': f"{td}T{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}-07:00", 'items': rows})
    index_orders.append({'date': td, 'partial': True, **write_orders(td, today_orders, True, f'{AS_OF_HOUR:02d}:00')})
    json.dump({'generated_for': td, 'days': index_orders}, open(os.path.join(HERE, 'orders', 'index.json'), 'w'), indent=1)

    weather_days = [(t['date'], 'Weather: ' + t['notes'][0].replace('simulated weather: ', '')) for t in truth.values()
                    if any('weather' in n for n in t['notes'])]
    # ---- predictions: Sep 5 - Nov 3
    index_pred = []
    d = date(2026, 9, 5)
    while d <= LAST_PRED:
        iso = d.isoformat()
        evs = ev_by_day[iso]
        hours, exp, rush, base = day_model(d, evs)
        t = truth.get(iso)
        if t:                                            # past: rescale the shape to the day's expected total
            tot = sum(exp.values())
            target = t['expected_items']
            if t['label'] in ('event_lift_muted', 'no_event_slow_day'):   # weather was not in the forecast
                target /= t['multipliers']['day_adjustment']
            elif t['label'] == 'decoy_busy_no_event':                     # office surge was not in the forecast
                target -= t['multipliers']['non_event_surge_items']
            for e in evs:                                                 # known closures / weather were
                if e.get('placeholder') and model_for(e) in ('closure', 'weather') and t['label'] not in ('event_lift_muted', 'no_event_slow_day'):
                    target *= 1 + strength_for(e)
            scale = target / tot
            exp = {h: v * scale for h, v in exp.items()}
        total = sum(exp.values())
        items = by_item(hours, exp, rush)
        item_tot = {i: sum(v) for i, v in items.items()}
        lift_pct = round((total / base - 1) * 100, 1)
        status = 'past' if d < TODAY else 'today' if d == TODAY else 'future'
        peak_h = max(exp, key=exp.get)
        doc = {
            'date': iso, 'day_of_week': d.strftime('%A'), 'status': status,
            'open': '11:00', 'close': f'{hours[-1] + 1:02d}:00',
            'baseline_items': round(base, 1), 'expected_items': round(total, 1),
            'expected_vs_baseline_pct': lift_pct,
            'expected_orders': round(total / 1.67), 'expected_revenue': round(sum(item_tot[i] * p for i, p in PRICE.items()), 2),
            'range_items': [round(total * .88), round(total * 1.12)],
            'confidence': 'high' if status == 'past' else ('low' if len([e for e in evs if e['venue'] == 'Chase Center']) > 1 or not any(e['start_time_confirmed'] for e in evs) and evs else 'medium'),
            'peak_hour': f'{peak_h:02d}:00',
            'hours': [f'{h:02d}:00' for h in hours],
            'hourly_expected': [round(exp[h], 1) for h in hours],
            'hourly_expected_by_item': {i: [round(x, 1) for x in v] for i, v in items.items()},
            'expected_items_by_item': {i: round(v, 1) for i, v in item_tot.items()},
            'drivers': drivers_for(evs),
            'prep_notes': prep_notes(item_tot, any(r > .05 for r in rush.values())),
            'placeholder': True,
        }
        if status == 'today':
            doc['agentic_insight'] = None
            doc['agentic_actions'] = []
            doc['agentic_pending'] = 'Agentic insights and actions for today will be generated at the end of the day.'
        else:
            adj = adjustments(d, evs, base, total, t['actual_items'] if t else None, t['label'] if t else None)
            doc['agentic_insight'] = build_insight(iso, d.strftime('%A'), status, evs, base, total, t, truth, events, weather_days, item_tot, doc['peak_hour'], adj)
            doc['agentic_actions'] = reorder_actions(iso, status, base, item_tot, total)
        doc['statistical'] = stat_block(d, hours, base, truth)
        ins = doc['agentic_insight']
        doc['external'] = external_block(evs, ins['sources'] if ins else [], ins['extra_other'] if ins else [])
        if ins:
            del ins['extra_other']
        if t:
            doc['actual_items'] = t['actual_items']
            doc['label'] = t['label']
        json.dump(doc, open(os.path.join(HERE, 'predictions', iso + '.json'), 'w'), indent=1, ensure_ascii=False)
        index_pred.append({'date': iso, 'status': status, 'expected_items': doc['expected_items'], 'baseline_items': doc['baseline_items'],
                           'expected_vs_baseline_pct': lift_pct, 'events': [e['name'] for e in evs]})
        d += timedelta(days=1)
    json.dump({'days': index_pred}, open(os.path.join(HERE, 'predictions', 'index.json'), 'w'), indent=1)
    print(f'events: {len(events)}  past order files: {len(day_orders)}  today orders: {len(today_orders)}  predictions: {len(index_pred)}')

PRICE = {'burrito': 10.5, 'bowl': 11.0, 'tacos': 9.5, 'nachos': 10.0, 'quesadilla': 8.5, 'chips-guac': 0, 'chips-queso': 0,
         'salad': 0, 'side-rice': 0, 'side-beans': 0}

if __name__ == '__main__':
    # fill in the remaining prices from the real sales
    for r in json.load(open(os.path.join(HERE, 'sales.json'))):
        PRICE[r['menu_item_id']] = r['price']
    main()
