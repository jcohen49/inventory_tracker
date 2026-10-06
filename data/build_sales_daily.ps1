# Rolls sales.csv up into sales_daily.js: items sold per day per menu item,
# which index.html loads with a <script> tag for the dashboard sales graph.
#
#   powershell -ExecutionPolicy Bypass -File data\build_sales_daily.ps1
#
# Re-run after regenerating sales.csv.
param([string]$Dir = $PSScriptRoot)
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$rows = Import-Csv (Join-Path $Dir 'sales.csv')
$first = [datetime]::ParseExact(($rows | Measure-Object date -Minimum).Minimum, 'yyyy-MM-dd', $null)
$last = [datetime]::ParseExact(($rows | Measure-Object date -Maximum).Maximum, 'yyyy-MM-dd', $null)

# every calendar day in the span, so a closed day shows as zero rather than a gap
$dates = @()
for ($d = $first; $d -le $last; $d = $d.AddDays(1)) { $dates += $d.ToString('yyyy-MM-dd') }
$idx = @{}
for ($i = 0; $i -lt $dates.Count; $i++) { $idx[$dates[$i]] = $i }

$items = [ordered]@{}
foreach ($r in $rows) {
  if (-not $items.Contains($r.menu_item_id)) { $items[$r.menu_item_id] = New-Object int[] $dates.Count }
  $items[$r.menu_item_id][$idx[$r.date]]++
}

$lines = @()
foreach ($k in ($items.Keys | Sort-Object { -(($items[$_] | Measure-Object -Sum).Sum) })) {
  $lines += "    '$k':[" + ($items[$k] -join ',') + ']'
}
$js = "// GENERATED from sales.csv by build_sales_daily.ps1 - do not edit.`n" +
  "window.SALES_DAILY={`n  dates:['" + ($dates -join "','") + "'],`n  items:{`n" + ($lines -join ",`n") + "`n  }`n};`n"
[IO.File]::WriteAllText((Join-Path $Dir 'sales_daily.js'), $js, (New-Object Text.UTF8Encoding $false))

Write-Host ("{0} sales over {1} days ({2} .. {3})" -f $rows.Count, $dates.Count, $dates[0], $dates[-1])
foreach ($k in $items.Keys) { Write-Host ("  {0,-12} {1,5}" -f $k, ($items[$k] | Measure-Object -Sum).Sum) }
