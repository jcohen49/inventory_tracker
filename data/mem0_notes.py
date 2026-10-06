"""Builds the reasoning note the agent saves to Mem0 at the end of each day.

The note correlates the external influences present that day (events, calamities, weather, holidays) with how
sales moved against the statistical prediction and the agent's forecast. Used by research_mem0_notes.py (which
saves past days' notes to Mem0) and by build_agentic_page_data.py (which shows the note, or a draft of it, per day).
"""
import json, os
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))

def _load(p):
    return json.load(open(os.path.join(HERE, p)))

def _pretty(iso):
    return datetime.fromisoformat(iso).strftime('%b %-d')

HOTSPOTS = ('Oracle Park', 'Chase Center', 'Moscone Center')

def influences(d, events, truth_row, picks):
    """-> (readable list, short tags) of everything external the reasoning layer knew about that day."""
    long_, tags = [], []
    for e in events:
        if e['venue'] in HOTSPOTS:
            long_.append(f"{e['name']} at {e['venue']} ({e['distance_from_oracle_park_miles']} mi, {e['start_time']} to {e['estimated_end_time']})")
        else:
            long_.append(f"{e['name']} ({e['venue']})")
        tags.append(e['name'])
    for headline, dist in picks:
        long_.append(f"incident near the truck: {headline[0].lower() + headline[1:]} (about {dist} away)")
        tags.append('Incident: ' + headline)
    for n in (truth_row or {}).get('notes', []):
        n = n.replace('simulated weather: ', 'weather: ').replace('; no event', '')
        long_.append(n[0].lower() + n[1:] if not n.startswith('weather') else n)
        tags.append(n.split(':')[0].capitalize() + (': ' + n.split(': ', 1)[1] if ': ' in n else ''))
    return long_, tags

def lesson(label, gap, stat_pct, has_events, picks):
    if label == 'event_lift_muted':
        return 'Lesson: bad weather can erase an expected game-night lift, so check the forecast before crediting an event.'
    if label == 'no_event_slow_day':
        return 'Lesson: drizzle plus a transit outage cut a normal weekday by about a quarter; weigh weather and commuter disruption together.'
    if label == 'decoy_busy_no_event':
        return 'Lesson: office group orders can spike lunch with no event; a Financial District evacuation was nearby that morning (unconfirmed link).'
    if gap is None:
        return ''
    if has_events and abs(gap) <= 0.08:
        return "Lesson: the model's lift for these influences held; keep the same weights."
    if has_events and gap < 0:
        return 'Lesson: the lift came in below the model; discount similar influences next time.'
    if has_events and gap > 0:
        return 'Lesson: the lift came in above the model; weight similar influences up next time.'
    if abs(stat_pct) <= 0.08:
        return 'Lesson: no external influence moved sales; the weekday trend held.'
    return 'Lesson: sales moved without a known cause; flagged for the next run.'

def build(d, pred, events, truth_row, picks):
    """pred is predictions/<date>.json. Returns {'text', 'metadata', 'draft'}."""
    dow = pred['day_of_week']
    long_, tags = influences(d, events, truth_row, picks)
    stat = round(pred['statistical']['total'])
    fc = round(pred['expected_items'])
    ins = pred.get('agentic_insight')
    rows = ins['adjustments']['rows'] if ins else []
    if ins:
        parts_txt = ', '.join(f"{r['label']} {r['delta']:+d}" for r in rows if r['delta']) or 'no external lift'
    else:                                   # today: no adjustment breakdown yet, so quote the expected effects
        parts_txt = ', '.join(f"{x['name']} ({x['expected_effect_pct']:+d}%)" for x in pred.get('drivers', []) if x['expected_effect_pct']) or 'no external lift'
    head = f"{d} ({dow}) reasoning note for the burrito truck next to Oracle Park. External influences: {'; '.join(long_) or 'none found within 1.5 mi'}."
    model = f" Statistical prediction {stat} items; agent forecast {fc} ({(fc / stat - 1) * 100:+.0f}%): {parts_txt}."
    meta = {'type': 'reasoning_note', 'date': d, 'day_of_week': dow, 'influences': tags, 'statistical_items': stat, 'forecast_items': fc}
    actual = pred.get('actual_items')
    if actual is None:
        text = head + model + ' Actual sales and the effect of each influence will be filled in at the end of the day.'
        return {'text': text, 'metadata': meta, 'draft': True}
    gap = actual / fc - 1
    stat_pct = actual / stat - 1
    note = (ins['adjustments'].get('gap_note') or '') if ins else ''
    outcome = (f" Actual {actual} items: {stat_pct * 100:+.0f}% vs the statistical prediction and {gap * 100:+.0f}% vs the forecast."
               + (f" {note}" if note else ''))
    text = head + model + outcome + ' ' + lesson(pred.get('label'), gap, stat_pct, bool(events), picks)
    meta.update({'actual_items': actual, 'vs_statistical_pct': round(stat_pct * 100, 1), 'vs_forecast_pct': round(gap * 100, 1)})
    return {'text': text.strip(), 'metadata': meta, 'draft': False}
