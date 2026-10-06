# Generates 30 days of simulated sales (2026-09-05 .. 2026-10-04) for a burrito
# truck next to Oracle Park, shaped by real nearby events.
# Outputs sales.csv, sales.json, events.json, ground_truth.json next to this script.
# Menu, prices and ingredient costs are copied from index.html.
#
#   powershell -ExecutionPolicy Bypass -File data\generate_sales.ps1
#
# Same seed -> identical output.
param([int]$Seed = 20261005, [string]$OutDir = $PSScriptRoot)
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
$inv = [cultureinfo]::InvariantCulture
$rng = New-Object System.Random $Seed

function Gauss { $u = 1.0 - $rng.NextDouble(); [math]::Sqrt(-2 * [math]::Log($u)) * [math]::Cos(2 * [math]::PI * $rng.NextDouble()) }
function Pois([double]$lam) {
  if ($lam -le 0) { return 0 }
  if ($lam -ge 30) { return [math]::Max(0, [int][math]::Round($lam + [math]::Sqrt($lam) * (Gauss))) }
  $L = [math]::Exp(-$lam); $k = 0; $p = 1.0
  do { $k++; $p *= $rng.NextDouble() } while ($p -gt $L)
  return $k - 1
}
function Pick($items, $weights) {
  $tot = 0.0; foreach ($w in $weights) { $tot += $w }
  $r = $rng.NextDouble() * $tot
  for ($i = 0; $i -lt $items.Count; $i++) { $r -= $weights[$i]; if ($r -lt 0) { return $items[$i] } }
  return $items[$items.Count - 1]
}
function Mins([string]$hhmm) { $p = $hhmm.Split(':'); [int]$p[0] * 60 + [int]$p[1] }
function Clock([int]$m) { '{0:00}:{1:00}' -f [math]::Floor($m / 60), ($m % 60) }

# ---------- ingredients: name, purchase unit, price per purchase unit, recipe units per purchase unit ----------
# The last column is an assumption (oz per lb is exact; oz per bunch/head/bag, sheets per roll, pieces per sleeve are not).
$nTilde = [char]0xF1; $dash = [char]0x2014
$INGS = @{
  'tor-flour'    = @('Large Flour Tortilla', 'tortillas', 0.28, 1)
  'tor-ww'       = @('Whole Wheat Tortilla', 'tortillas', 0.34, 1)
  'tor-gf'       = @('Gluten-Free Tortilla', 'tortillas', 0.55, 1)
  'rice-white'   = @('White Rice', 'lbs', 0.90, 16)
  'rice-brown'   = @('Brown Rice', 'lbs', 1.10, 16)
  'bean-pinto'   = @('Pinto Beans', 'lbs', 1.20, 16)
  'bean-black'   = @('Black Beans', 'lbs', 1.25, 16)
  'bean-refried' = @('Refried Beans', 'lbs', 1.40, 16)
  'beef'         = @('Beef', 'lbs', 5.20, 16)
  'pork'         = @('Pork', 'lbs', 4.10, 16)
  'chicken'      = @('Chicken', 'lbs', 3.40, 16)
  'shrimp'       = @('Shrimp', 'lbs', 9.20, 16)
  'onion'        = @('Onions', 'lbs', 0.80, 16)
  'cilantro'     = @('Cilantro', 'bunches', 0.90, 3)
  'lettuce'      = @('Lettuce', 'heads', 1.20, 16)
  'cheese-blend' = @('Mexican Blend Cheese', 'lbs', 3.60, 16)
  'queso'        = @('Queso Dip', 'gal', 12.00, 128)
  'sourcream'    = @('Sour Cream', 'gal', 6.50, 128)
  'pico'         = @('Pico de Gallo', 'lbs', 2.20, 16)
  'salsa-verde'  = @('Salsa Verde', 'qt', 2.60, 32)
  'guac'         = @('Guacamole', 'lbs', 4.80, 16)
  'corn'         = @('Corn', 'lbs', 1.10, 16)
  'jalapeno'     = @("Jalape${nTilde}os", 'lbs', 1.30, 16)
  'chips'        = @('Tortilla Chips', 'bags', 3.20, 16)
  'foil'         = @('Aluminum Foil', 'rolls', 14.50, 500)
  'bowl-lg'      = @("Paper Bowls $dash Large", 'sleeves', 9.80, 50)
  'bowl-sm'      = @("Paper Bowls $dash Small", 'sleeves', 8.20, 50)
  'cup-lg'       = @("Cups $dash Large", 'sleeves', 10.40, 50)
}
# customer preference when a component offers a choice
$OPTW = @{
  'tor-flour' = 0.78; 'tor-ww' = 0.14; 'tor-gf' = 0.08
  'rice-white' = 0.75; 'rice-brown' = 0.25
  'bean-black' = 0.42; 'bean-pinto' = 0.38; 'bean-refried' = 0.20
  'chicken' = 0.38; 'beef' = 0.30; 'pork' = 0.22; 'shrimp' = 0.10
}

# ---------- menu (index.html this.menu). w = normal mix weight, ew = mix weight during an event rush ----------
function C($label, $qty, $unit, $opts, $optional = 1.0) { @{ label = $label; qty = [double]$qty; unit = $unit; opts = $opts; p = $optional } }
$TORT = @('tor-flour', 'tor-ww', 'tor-gf'); $RICE = @('rice-white', 'rice-brown')
$BEAN = @('bean-pinto', 'bean-black', 'bean-refried'); $PROT = @('beef', 'pork', 'chicken', 'shrimp')
$MENU = @(
  @{ id = 'burrito'; name = 'Signature Burrito'; price = 10.50; w = 27; ew = 27; comps = @(
      (C 'Tortilla' 1 'ea' $TORT), (C 'Rice' 8 'oz' $RICE), (C 'Beans' 6 'oz' $BEAN), (C 'Protein' 5 'oz' $PROT),
      (C 'Cheese' 1 'oz' @('cheese-blend')), (C 'Salsa' 2 'oz' @('pico')), (C 'Wrap' 1 'sheet' @('foil'))) }
  @{ id = 'bowl'; name = 'Burrito Bowl'; price = 11.00; w = 17; ew = 12; comps = @(
      (C 'Rice' 8 'oz' $RICE), (C 'Beans' 6 'oz' $BEAN), (C 'Protein' 5 'oz' $PROT), (C 'Lettuce' 2 'oz' @('lettuce')),
      (C 'Cheese' 1 'oz' @('cheese-blend')), (C 'Salsa' 2 'oz' @('pico')), (C 'Bowl' 1 'ea' @('bowl-lg'))) }
  @{ id = 'tacos'; name = 'Street Tacos (3)'; price = 9.50; w = 18; ew = 24; comps = @(
      (C 'Tortilla' 3 'ea' @('tor-flour')), (C 'Protein' 4.5 'oz' $PROT), (C 'Onion' 1 'oz' @('onion')),
      (C 'Cilantro' 0.3 'oz' @('cilantro')), (C 'Salsa' 1.5 'oz' @('salsa-verde'))) }
  @{ id = 'quesadilla'; name = 'Quesadilla'; price = 8.50; w = 9; ew = 9; comps = @(
      (C 'Tortilla' 1 'ea' @('tor-flour')), (C 'Cheese' 3 'oz' @('cheese-blend')), (C 'Protein' 3 'oz' $PROT 0.7)) }
  @{ id = 'nachos'; name = 'Loaded Nachos'; price = 10.00; w = 8; ew = 15; comps = @(
      (C 'Chips' 4 'oz' @('chips')), (C 'Queso' 3 'oz' @('queso')), (C 'Beans' 3 'oz' $BEAN), (C 'Protein' 3 'oz' $PROT),
      (C 'Salsa' 2 'oz' @('pico')), (C "Jalape${nTilde}o" 0.5 'oz' @('jalapeno')), (C 'Sour cream' 1 'oz' @('sourcream')),
      (C 'Bowl' 1 'ea' @('bowl-lg'))) }
  @{ id = 'salad'; name = 'Taco Salad'; price = 11.00; w = 5; ew = 3; comps = @(
      (C 'Lettuce' 4 'oz' @('lettuce')), (C 'Protein' 4 'oz' $PROT), (C 'Beans' 3 'oz' $BEAN), (C 'Corn' 1 'oz' @('corn')),
      (C 'Salsa' 2 'oz' @('pico')), (C 'Cheese' 1 'oz' @('cheese-blend')), (C 'Guacamole' 2 'oz' @('guac')),
      (C 'Bowl' 1 'ea' @('bowl-lg'))) }
  @{ id = 'chips-guac'; name = 'Chips & Guacamole'; price = 5.50; w = 6; ew = 9; comps = @(
      (C 'Chips' 3 'oz' @('chips')), (C 'Guacamole' 4 'oz' @('guac')), (C 'Bowl' 1 'ea' @('bowl-sm'))) }
  @{ id = 'chips-queso'; name = 'Chips & Queso'; price = 5.00; w = 5; ew = 8; comps = @(
      (C 'Chips' 3 'oz' @('chips')), (C 'Queso' 4 'oz' @('queso')), (C 'Bowl' 1 'ea' @('bowl-sm'))) }
  @{ id = 'side-rice'; name = 'Side of Rice'; price = 3.00; w = 2.5; ew = 1.5; comps = @(
      (C 'Rice' 6 'oz' $RICE), (C 'Cup' 1 'ea' @('cup-lg'))) }
  @{ id = 'side-beans'; name = 'Side of Beans'; price = 3.00; w = 2.5; ew = 1.5; comps = @(
      (C 'Beans' 6 'oz' $BEAN), (C 'Cup' 1 'ea' @('cup-lg'))) }
)
$MENU_W = @($MENU | ForEach-Object { $_.w }); $MENU_EW = @($MENU | ForEach-Object { $_.ew })

# ---------- real events within ~1 mile of Oracle Park ----------
# model/k/dur are simulation parameters (ground truth only). k = peak extra demand multiplier.
# confirmed = whether the start time was confirmed from a source; see README.
$SRC_GIANTS = 'https://www.espn.com/mlb/team/schedule/_/name/sf/season/2026/seasontype/2/half/2'
$SRC_GSV = 'https://www.basketball-reference.com/wnba/teams/GSV/2026_games.html'
function E($id, $date, $start, $name, $venue, $cat, $model, $k, $dur, $confirmed, $src, $note = '') {
  @{ id = $id; date = $date; start = $start; name = $name; venue = $venue; cat = $cat; model = $model; k = [double]$k; dur = [int]$dur; confirmed = $confirmed; src = $src; note = $note }
}
function Giants($date, $start, $opp, $k, $note = '') { E "giants-$date" $date $start "Giants vs $opp" 'Oracle Park' 'MLB game' 'oracle' $k 160 $false $SRC_GIANTS $note }
$EVENTS = @(
  (Giants '2026-09-07' '17:10' 'St. Louis Cardinals' 2.0 'Labor Day'),
  (Giants '2026-09-08' '18:45' 'St. Louis Cardinals' 1.6),
  (Giants '2026-09-09' '12:45' 'St. Louis Cardinals' 1.5),
  (E 'weezer-2026-09-09' '2026-09-09' '19:00' 'Weezer with The Shins and Silversun Pickups' 'Chase Center' 'Concert' 'chase' 0.35 210 $true 'https://www.chasecenter.com/events/weezer-20260909/'),
  (Giants '2026-09-11' '19:15' 'San Diego Padres' 2.0),
  (Giants '2026-09-12' '13:05' 'San Diego Padres' 2.2),
  (Giants '2026-09-13' '16:20' 'San Diego Padres' 2.0),
  (E 'dreamforce-2026-09-15' '2026-09-15' '09:00' 'Dreamforce 2026 (day 1)' 'Moscone Center' 'Conference' 'conference' 0.35 540 $false 'https://www.sfmta.com/reports/dreamforce-2026'),
  (E 'dreamforce-2026-09-16' '2026-09-16' '09:00' 'Dreamforce 2026 (day 2)' 'Moscone Center' 'Conference' 'conference' 0.35 540 $false 'https://www.sfmta.com/reports/dreamforce-2026'),
  (E 'dreamfest-2026-09-16' '2026-09-16' '18:00' 'Dreamfest 2026 (Gwen Stefani, Usher)' 'Oracle Park' 'Concert' 'oracle' 2.2 285 $true 'https://www.nbcbayarea.com/news/local/gwen-stefani-usher-dreamfest-oracle-park/4134617/' 'start is doors time; private Dreamforce attendee event'),
  (E 'dreamforce-2026-09-17' '2026-09-17' '09:00' 'Dreamforce 2026 (day 3)' 'Moscone Center' 'Conference' 'conference' 0.35 540 $false 'https://www.sfmta.com/reports/dreamforce-2026'),
  (E 'valkyries-2026-09-18' '2026-09-18' '19:00' 'Valkyries vs Portland Fire' 'Chase Center' 'WNBA game' 'chase' 0.25 130 $false $SRC_GSV),
  (E 'valkyries-2026-09-19' '2026-09-19' '17:30' 'Valkyries vs Seattle Storm' 'Chase Center' 'WNBA game' 'chase' 0.25 130 $false $SRC_GSV),
  (Giants '2026-09-21' '18:45' 'Minnesota Twins' 1.2 'team already eliminated'),
  (Giants '2026-09-22' '18:45' 'Minnesota Twins' 0.4 'simulated cold, foggy night: thin crowd'),
  (Giants '2026-09-23' '12:45' 'Minnesota Twins' 1.1),
  (E 'lily-allen-2026-09-23' '2026-09-23' '20:00' 'Lily Allen' 'Chase Center' 'Concert' 'chase' 0.04 150 $true 'https://www.chasecenter.com/news/lily-allen-announcement-20260923/'),
  (Giants '2026-09-25' '19:15' 'Los Angeles Dodgers' 2.8),
  (Giants '2026-09-26' '13:05' 'Los Angeles Dodgers' 3.0),
  (Giants '2026-09-27' '12:05' 'Los Angeles Dodgers' 2.8 'season finale'),
  (E 'valkyries-2026-09-27' '2026-09-27' '18:00' 'WNBA Playoffs R1 G1: Valkyries vs Dallas Wings' 'Chase Center' 'WNBA playoff game' 'chase' 0.30 130 $true 'https://www.chasecenter.com/events/20260927-gsv-vs-dal/'),
  (E 'valkyries-2026-10-02' '2026-10-02' '18:00' 'WNBA Playoffs R1 G3: Valkyries vs Dallas Wings' 'Chase Center' 'WNBA playoff game' 'chase' 0.35 130 $true 'https://www.chasecenter.com/events/20261002-gsv-vs-dal/'),
  (E 'disney-2026-10-03' '2026-10-03' '19:00' 'Disney Worlds Collide Concert Tour' 'Chase Center' 'Concert' 'chase' 0.15 150 $true 'https://www.chasecenter.com/events/disney-worlds-collide-concert-tour-20261003/'),
  (E 'valkyries-2026-10-04' '2026-10-04' '13:00' 'WNBA Semifinals G1: Valkyries vs Las Vegas Aces' 'Chase Center' 'WNBA playoff game' 'chase' 0.30 130 $true 'https://www.chasecenter.com/events/20261004-gsv-semifinals-game-1/')
)
$VENUE = @{
  'Oracle Park'    = @{ dist = 0.1; cap = 41000 }
  'Chase Center'   = @{ dist = 0.9; cap = 18000 }
  'Moscone Center' = @{ dist = 0.9; cap = 45000 }
}

# Demand multiplier an event applies at minute-of-day $t.
function EventFactor($e, [double]$t) {
  $s = Mins $e.start; $en = $s + $e.dur; $k = $e.k
  switch ($e.model) {
    'oracle' {
      # ramp into a pre-game rush, lull while the crowd is inside, post-game bump
      if ($t -ge $s - 150 -and $t -lt $s - 45) { return 1 + $k * ($t - ($s - 150)) / 105 }
      if ($t -ge $s - 45 -and $t -lt $s + 10) { return 1 + $k }
      if ($t -ge $s + 10 -and $t -lt $en - 25) { return 0.9 }
      if ($t -ge $en - 25 -and $t -lt $en + 90) { return 1 + 0.55 * $k * (1 - ($t - ($en - 25)) / 115) }
      return 1
    }
    'chase' {
      if ($t -ge $s - 180 -and $t -lt $s - 15) { return 1 + $k }
      if ($t -ge $en -and $t -lt $en + 60) { return 1 + 0.25 * $k }
      return 1
    }
    'conference' {
      if ($t -ge 690 -and $t -lt 840) { return 1 + $k }
      if ($t -ge 1020 -and $t -lt 1140) { return 1 + 0.4 * $k }
      return 1
    }
  }
  return 1
}

# ---------- non-event day adjustments (simulated; these are the decoys) ----------
$DAYADJ = @{
  '2026-09-07' = @{ f = 0.90; why = 'Labor Day: offices closed, weaker baseline lunch' }
  '2026-09-22' = @{ f = 0.80; why = 'simulated weather: cold, foggy, windy evening' }
  '2026-09-30' = @{ f = 0.72; why = 'simulated weather: drizzle most of the day' }
}
# lunch surge with no event behind it
$SURGES = @{ '2026-10-01' = @{ from = 690; to = 810; f = 1.9; why = 'large walk-up group orders from a nearby office; no event' } }

# ---------- baseline demand: items per daypart at factor 1.0, scaled by index.html dowParts ----------
$DOWPARTS = @{
  0 = @(1.2, 1.0, 1.1, 0.6); 1 = @(0.8, 0.6, 0.8, 0.5); 2 = @(0.85, 0.65, 0.85, 0.55); 3 = @(0.9, 0.7, 0.9, 0.6)
  4 = @(1.0, 0.8, 1.05, 0.7); 5 = @(1.3, 1.0, 1.6, 1.1); 6 = @(1.4, 1.1, 1.7, 1.2)
}
$PARTS = @(
  @{ name = 'lunch'; from = 660; to = 840; base = 70; peak = 750; sd = 45 }
  @{ name = 'afternoon'; from = 840; to = 1020; base = 28; peak = 0; sd = 0 }
  @{ name = 'dinner'; from = 1020; to = 1200; base = 62; peak = 1110; sd = 50 }
  @{ name = 'late'; from = 1200; to = 1260; base = 12; peak = 0; sd = 0 }
)
$BIN = 15; $T_CLOSE = 1260; $T_CLOSE_EXT = 1380; $EXT_PER_BIN = 5.0
# share of each daypart's items falling in each 15-min bin
$SHAPE = @{}
foreach ($p in $PARTS) {
  $ws = @(); for ($t = $p.from; $t -lt $p.to; $t += $BIN) {
    if ($p.sd -gt 0) { $ws += [math]::Exp(-0.5 * [math]::Pow(($t + 7.5 - $p.peak) / $p.sd, 2)) + 0.25 } else { $ws += 1.0 }
  }
  $sum = 0.0; foreach ($w in $ws) { $sum += $w }
  $i = 0; for ($t = $p.from; $t -lt $p.to; $t += $BIN) { $SHAPE[$t] = @{ part = $p; share = $ws[$i] / $sum }; $i++ }
}

$SIZE_N = @(0.50, 0.32, 0.12, 0.06); $SIZE_E = @(0.35, 0.35, 0.18, 0.12); $SIZES = @(1, 2, 3, 4)

function F2([double]$x) { $x.ToString('0.00', $inv) }
function F4([double]$x) { $x.ToString('0.0###', $inv) }
function Qty([double]$x) { $x.ToString('0.##', $inv) }

# Builds one sold item: resolves ingredient choices and costs.
function MakeItem($m) {
  $parts = New-Object System.Collections.Generic.List[string]
  $json = New-Object System.Collections.Generic.List[string]
  $cost = 0.0
  foreach ($c in $m.comps) {
    if ($c.p -lt 1.0 -and $rng.NextDouble() -ge $c.p) { continue }
    $id = $c.opts[0]
    if ($c.opts.Count -gt 1) { $id = Pick $c.opts @($c.opts | ForEach-Object { $OPTW[$_] }) }
    $ing = $INGS[$id]
    $cc = $c.qty * $ing[2] / $ing[3]
    $cost += $cc
    $parts.Add(('{0} {1} {2}' -f $ing[0], (Qty $c.qty), $c.unit))
    $json.Add(('{{"ingredient_id":"{0}","name":"{1}","role":"{2}","qty":{3},"unit":"{4}","cost":{5}}}' -f $id, $ing[0], $c.label, (Qty $c.qty), $c.unit, (F4 $cc)))
  }
  @{ m = $m; cost = [math]::Round($cost, 2); text = ($parts -join '; '); json = ($json -join ',') }
}

# ---------- simulate ----------
$csv = New-Object System.Text.StringBuilder
[void]$csv.AppendLine('sale_id,order_id,timestamp,date,day_of_week,menu_item_id,menu_item,price,ingredient_cost,ingredients')
$js = New-Object System.Text.StringBuilder
[void]$js.Append("[`n")
$truth = New-Object System.Collections.Generic.List[object]
$saleNo = 0; $problems = New-Object System.Collections.Generic.List[string]
$start = [datetime]::new(2026, 9, 5)

for ($d = 0; $d -lt 30; $d++) {
  $day = $start.AddDays($d); $date = $day.ToString('yyyy-MM-dd'); $dow = [int]$day.DayOfWeek
  $evs = @($EVENTS | Where-Object { $_.date -eq $date })
  $ext = @($evs | Where-Object { $_.model -eq 'oracle' -and (Mins $_.start) -ge 1020 }).Count -gt 0
  $close = $T_CLOSE; if ($ext) { $close = $T_CLOSE_EXT }
  $noise = [math]::Max(0.85, [math]::Min(1.15, 1 + 0.07 * (Gauss)))
  $adj = 1.0; $notes = @()
  if ($DAYADJ.ContainsKey($date)) { $adj = $DAYADJ[$date].f; $notes += $DAYADJ[$date].why }
  $surge = $null; if ($SURGES.ContainsKey($date)) { $surge = $SURGES[$date]; $notes += $surge.why }

  $baseExp = 0.0; $exp = 0.0; $otherIncr = 0.0
  $incr = @{}; foreach ($e in $evs) { $incr[$e.id] = 0.0 }
  $orders = New-Object System.Collections.Generic.List[object]

  for ($t = 660; $t -lt $close; $t += $BIN) {
    $mid = $t + $BIN / 2.0
    if ($t -lt $T_CLOSE) {
      $sh = $SHAPE[$t]; $pi = [array]::IndexOf($PARTS, $sh.part)
      $base = $sh.part.base * $DOWPARTS[$dow][$pi] * $sh.share
      $baseExp += $base
    } else { $base = $EXT_PER_BIN * $DOWPARTS[$dow][3] }   # extra hours only exist because of the event
    $local = $base * $adj
    if ($surge -and $mid -ge $surge.from -and $mid -lt $surge.to) { $otherIncr += $local * ($surge.f - 1); $local *= $surge.f }
    $ef = 1.0
    foreach ($e in $evs) {
      $f = EventFactor $e $mid; $ef *= $f
      if ($t -lt $T_CLOSE) { $incr[$e.id] += $local * ($f - 1) }
      elseif ($e.model -eq 'oracle' -and (Mins $e.start) -ge 1020) { $incr[$e.id] += $local * $f }
    }
    $lam = $local * $ef
    $exp += $lam
    $n = Pois ($lam * $noise)
    $rush = $ef -gt 1.15
    while ($n -gt 0) {
      $sz = [math]::Min($n, (Pick $SIZES $(if ($rush) { $SIZE_E } else { $SIZE_N })))
      $items = @(); for ($i = 0; $i -lt $sz; $i++) { $items += , (MakeItem (Pick $MENU $(if ($rush) { $MENU_EW } else { $MENU_W }))) }
      $orders.Add(@{ sec = $t * 60 + $rng.Next(0, $BIN * 60); items = $items })
      $n -= $sz
    }
  }

  $sorted = @($orders | Sort-Object { $_.sec })
  $nItems = 0; $rev = 0.0; $cogs = 0.0; $ordNo = 0
  foreach ($o in $sorted) {
    $ordNo++
    $ts = '{0}T{1:00}:{2:00}:{3:00}-07:00' -f $date, [math]::Floor($o.sec / 3600), [math]::Floor(($o.sec % 3600) / 60), ($o.sec % 60)
    $oid = 'O-{0}-{1:0000}' -f $day.ToString('yyyyMMdd'), $ordNo
    if ($o.sec -lt 660 * 60 -or $o.sec -ge $close * 60) { $problems.Add("$oid outside operating hours") }
    foreach ($it in $o.items) {
      $saleNo++; $nItems++; $rev += $it.m.price; $cogs += $it.cost
      $sid = 'S{0:000000}' -f $saleNo
      if ($it.cost -ge $it.m.price) { $problems.Add("$sid cost >= price") }
      [void]$csv.AppendLine(('{0},{1},{2},{3},{4},{5},"{6}",{7},{8},"{9}"' -f $sid, $oid, $ts, $date, $day.DayOfWeek, $it.m.id, $it.m.name, (F2 $it.m.price), (F2 $it.cost), $it.text))
      if ($saleNo -gt 1) { [void]$js.Append(",`n") }
      [void]$js.Append(('{{"sale_id":"{0}","order_id":"{1}","timestamp":"{2}","date":"{3}","day_of_week":"{4}","menu_item_id":"{5}","menu_item":"{6}","price":{7},"ingredient_cost":{8},"ingredients":[{9}]}}' -f $sid, $oid, $ts, $date, $day.DayOfWeek, $it.m.id, $it.m.name, (F2 $it.m.price), (F2 $it.cost), $it.json))
    }
  }

  # ---------- ground truth for the day ----------
  $evTruth = @(); $evIncr = 0.0
  foreach ($e in $evs) {
    $share = $incr[$e.id] / $baseExp; $evIncr += $incr[$e.id]
    $eff = 'none'; if ($share -ge 0.25) { $eff = 'strong' } elseif ($share -ge 0.10) { $eff = 'moderate' } elseif ($share -ge 0.03) { $eff = 'weak' }
    $evTruth += [ordered]@{ event_id = $e.id; name = $e.name; venue = $e.venue; start_time = $e.start; model = $e.model; peak_multiplier_k = $e.k
      expected_incremental_items = [math]::Round($incr[$e.id], 1); incremental_pct_of_baseline = [math]::Round(100 * $share, 1); true_effect = $eff; note = $e.note }
  }
  $lift = $evIncr / $baseExp
  if ($surge) { $label = 'decoy_busy_no_event' }
  elseif ($evs.Count -eq 0) { $label = $(if ($adj -lt 0.9) { 'no_event_slow_day' } else { 'no_event' }) }
  elseif ($lift -ge 0.30) { $label = 'event_lift_strong' }
  elseif ($lift -ge 0.10) { $label = $(if ($adj -lt 0.9) { 'event_lift_muted' } else { 'event_lift_moderate' }) }
  elseif ($lift -ge 0.03) { $label = 'event_lift_weak' }
  else { $label = 'event_no_effect' }
  $truth.Add([ordered]@{
      date = $date; day_of_week = "$($day.DayOfWeek)"; open = '11:00'; close = (Clock $close); label = $label
      baseline_expected_items = [math]::Round($baseExp, 1); expected_items = [math]::Round($exp, 1); actual_items = $nItems
      actual_orders = $ordNo; actual_revenue = [math]::Round($rev, 2); actual_ingredient_cost = [math]::Round($cogs, 2)
      expected_event_lift_pct = [math]::Round(100 * $lift, 1)
      multipliers = [ordered]@{ day_adjustment = $adj; random_noise = [math]::Round($noise, 3); non_event_surge_items = [math]::Round($otherIncr, 1) }
      events = $evTruth; notes = $notes
    })
}
[void]$js.Append("`n]`n")

# ---------- public event calendar (no simulation parameters) ----------
$pub = @($EVENTS | ForEach-Object {
    $v = $VENUE[$_.venue]
    [ordered]@{ event_id = $_.id; name = $_.name; category = $_.cat; venue = $_.venue; distance_from_oracle_park_miles = $v.dist
      date = $_.date; start_time = $_.start; estimated_end_time = (Clock ((Mins $_.start) + $_.dur)); start_time_confirmed = $_.confirmed
      venue_capacity = $v.cap; status = 'took place'; source = $_.src }
  })

$enc = New-Object System.Text.UTF8Encoding $false
[IO.File]::WriteAllText((Join-Path $OutDir 'sales.csv'), $csv.ToString(), $enc)
[IO.File]::WriteAllText((Join-Path $OutDir 'sales.json'), $js.ToString(), $enc)
[IO.File]::WriteAllText((Join-Path $OutDir 'events.json'), (ConvertTo-Json $pub -Depth 5), $enc)
[IO.File]::WriteAllText((Join-Path $OutDir 'ground_truth.json'), (ConvertTo-Json $truth.ToArray() -Depth 6), $enc)

# ---------- summary + sanity checks ----------
$truth | ForEach-Object {
  [pscustomobject]@{ date = $_.date; dow = $_.day_of_week.Substring(0, 3); close = $_.close; base = $_.baseline_expected_items; items = $_.actual_items
    revenue = $_.actual_revenue; cogs = $_.actual_ingredient_cost; 'lift%' = $_.expected_event_lift_pct; label = $_.label
    events = (($_.events | ForEach-Object { "$($_.venue.Split(' ')[0]) $($_.start_time)" }) -join ', ') }
} | Format-Table -AutoSize | Out-String -Width 220 | Write-Host
$tot = 0; foreach ($x in $truth) { $tot += $x.actual_items }
if ($tot -ne $saleNo) { $problems.Add("ground truth total $tot != rows $saleNo") }
Write-Host "rows: $saleNo   problems: $($problems.Count)"
$problems | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }
