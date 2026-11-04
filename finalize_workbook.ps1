# Finalize CFA_Level_I_Tracker.xlsx: force a real calculation and save the cached
# values, so the dashboard is readable even before Excel recalculates on open.
# Run after make_workbook.py. Requires Microsoft Excel.
$ErrorActionPreference = 'Stop'
$path = Join-Path $PSScriptRoot 'CFA_Level_I_Tracker.xlsx'
if (-not (Test-Path -LiteralPath $path)) {
    Write-Host "  ! workbook not found: $path"
    exit 1
}

$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
    $wb = $xl.Workbooks.Open($path)
    $xl.Calculation = -4105   # xlCalculationAutomatic
    $d = $wb.Worksheets.Item('Dashboard')

    # openpyxl writes an empty cached value for formula cells; Excel can keep it
    # for these two. Re-entering the same formula forces the calculation.
    foreach ($a in 'B11', 'B12') {
        $c = $d.Range($a)
        $f = $c.Formula
        $c.ClearContents()
        $c.Formula = $f
    }

    foreach ($ws in $wb.Worksheets) {
        try { $ws.UsedRange.SpecialCells(16).Dirty() | Out-Null } catch { }
    }
    $xl.CalculateFullRebuild()
    $wb.Save()
    $wb.Close($false)
    Write-Host "  OK  workbook calculated and saved"
} finally {
    $xl.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($xl) | Out-Null
}
