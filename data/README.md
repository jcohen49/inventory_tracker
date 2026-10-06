# Simulated sales, Sep 5 – Oct 4, 2026

Thirty days of simulated sales for the burrito truck, placed next to Oracle Park in San Francisco. The sales are synthetic; the events that shape them are real. The dataset exists so an agent can cross-reference each day's sales with nearby events and decide whether an event moved sales.

| File | What it is | Give to the agent? |
|---|---|---|
| `sales.csv` | One row per menu item sold (7,152 rows) | Yes |
| `sales.json` | Same rows, with ingredients as a structured array | Yes |
| `events.json` | Real events within ~1 mile of Oracle Park | Optional (omit to make the agent find events itself) |
| `ground_truth.json` | Answer key: what the simulation actually did each day | **No** — grading only |
| `generate_sales.ps1` | Seeded generator that produced all of the above | No (contains the answer key's parameters) |

## Sales schema

| Column | Notes |
|---|---|
| `sale_id` | `S000001`…, in time order |
| `order_id` | `O-YYYYMMDD-NNNN`; items in one order share an id and timestamp |
| `timestamp` | ISO 8601, Pacific Daylight Time (`-07:00`) |
| `date`, `day_of_week` | Local date |
| `menu_item_id`, `menu_item` | From the app's menu in `index.html` |
| `price` | What the customer paid (app menu price) |
| `ingredient_cost` | Cost of the ingredients in that item |
| `ingredients` | CSV: `;`-separated `name qty unit`. JSON: array of `ingredient_id, name, role, qty, unit, cost` |

Ingredients reflect the choices made for that sale (which tortilla, rice, beans, protein), so two burritos can differ in ingredients and cost. Sales rows carry no event or weather information.

## Events used

| Date | Event | Venue | Start |
|---|---|---|---|
| Sep 7, 8, 9 | Giants vs Cardinals | Oracle Park | 5:10 pm, 6:45 pm, 12:45 pm* |
| Sep 9 | Weezer, The Shins, Silversun Pickups | Chase Center | 7:00 pm |
| Sep 11, 12, 13 | Giants vs Padres | Oracle Park | 7:15 pm, 1:05 pm, 4:20 pm* |
| Sep 15–17 | Dreamforce | Moscone Center | all day |
| Sep 16 | Dreamfest (Gwen Stefani, Usher) | Oracle Park | doors 6:00 pm |
| Sep 18, 19 | Valkyries vs Fire, vs Storm | Chase Center | 7:00 pm, 5:30 pm* |
| Sep 21, 22, 23 | Giants vs Twins | Oracle Park | 6:45 pm, 6:45 pm, 12:45 pm* |
| Sep 23 | Lily Allen | Chase Center | 8:00 pm |
| Sep 25, 26, 27 | Giants vs Dodgers | Oracle Park | 7:15 pm, 1:05 pm, 12:05 pm* |
| Sep 27 | WNBA Playoffs: Valkyries vs Wings | Chase Center | 6:00 pm |
| Oct 2 | WNBA Playoffs: Valkyries vs Wings | Chase Center | 6:00 pm |
| Oct 3 | Disney Worlds Collide Concert Tour | Chase Center | 7:00 pm |
| Oct 4 | WNBA Semifinals: Valkyries vs Aces | Chase Center | 1:00 pm |

\* Start time not confirmed, flagged `start_time_confirmed: false` in `events.json`:
- **Giants**: dates and opponents are confirmed. The one source with times listed them three hours early (it showed the season finale at 9:05 am); times here are that source plus three hours.
- **Valkyries Sep 18 and 19**: dates confirmed, times assumed.
- **Dreamforce**: 9:00 am is a placeholder for an all-day conference.

Distances are from Oracle Park: Chase Center and Moscone Center are each about 0.9 miles. `venue_capacity` is the venue's approximate capacity (for Dreamforce, the expected attendance), not actual attendance.

## How the sales were simulated

- **Hours**: 11:00–21:00; open to 23:00 on nights with an evening event at Oracle Park.
- **Baseline**: items per daypart (lunch, afternoon, dinner, late) scaled by the app's `dowParts` day-of-week weights, with lunch and dinner peaks and roughly ±7% daily noise. Weekday baselines run about 130–165 items, weekends 190–250.
- **Oracle Park events**: demand ramps up from 2.5 hours before the start, dips while the crowd is inside, then bumps after. Strength varies by game (Dodgers highest, midweek Twins lowest).
- **Chase Center events**: a small lift in the three hours before the start.
- **Dreamforce**: a lunch lift and a smaller early-evening one.
- **Mix**: during an event rush, more nachos, tacos and chip sides, fewer bowls and salads, and larger orders.

Deliberate traps for the agent, all recorded in `ground_truth.json`:

| Date | What happens | Label |
|---|---|---|
| Sep 22 | Giants night game, but sales look like an ordinary Tuesday (simulated cold, foggy night) | `event_lift_muted` |
| Sep 23 | Lily Allen at Chase Center has no effect; the day's lift is the Giants day game | event `true_effect: none` |
| Sep 30 | Slow day with no event (simulated drizzle) | `no_event_slow_day` |
| Oct 1 | Busy lunch with no event behind it | `decoy_busy_no_event` |
| Sep 7 | Labor Day game: lift is real but sits on a weaker holiday baseline | `event_lift_strong` |

Weather and the Oct 1 lunch surge are invented, not real.

## Ground truth fields

Per day: `label`, `baseline_expected_items` (normal hours, no event), `expected_items`, `actual_items`, `actual_orders`, `actual_revenue`, `actual_ingredient_cost`, `expected_event_lift_pct`, the non-event multipliers, and per event its `expected_incremental_items` and `true_effect` (`strong` ≥ 25% of baseline, `moderate` ≥ 10%, `weak` ≥ 3%, else `none`).

## Ingredient cost assumptions

Cost = recipe quantity × the app's price per purchase unit ÷ recipe units per purchase unit. Ounces per pound is exact; the rest are assumptions:

| Ingredient | Assumed |
|---|---|
| Queso, sour cream | 128 oz per gallon |
| Salsa verde | 32 oz per quart |
| Cilantro | 3 oz per bunch |
| Lettuce | 16 oz per head |
| Tortilla chips | 16 oz per bag |
| Foil | 500 sheets per roll |
| Bowls, cups | 50 per sleeve |

The quesadilla's protein is optional in the app; 70% of simulated quesadillas include it.

## Regenerating

```bash
powershell -ExecutionPolicy Bypass -File data/generate_sales.ps1
```

The seed is fixed, so output is identical each run. Pass `-Seed <n>` for a different draw. The script prints a per-day summary and reports a problem if any sale falls outside operating hours, any item costs more than its price, or the row count disagrees with the ground truth.
