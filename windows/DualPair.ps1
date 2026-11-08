# DualPair for Windows - fixes for PCs that dual boot Windows and Linux.
# For now: the clock. Linux reads the hardware clock as UTC, Windows as local time, so the
# time is wrong after switching system. "Use UTC" makes Windows read it as UTC too
# (registry value RealTimeIsUniversal=1), which is the standard fix.
#
# Saved as UTF-8 with BOM, so Windows PowerShell 5.1 reads the accented letters correctly.
# Double-click DualPair.cmd to open the window (asks for administrator rights).
# Command line (run as administrator):
#   DualPair.ps1 -Status [-Json]    show the current setting
#   DualPair.ps1 -SetUtc            Windows reads the hardware clock as UTC
#   DualPair.ps1 -SetLocal          back to the Windows default (local time)
#   DualPair.ps1 -Resync            sync the time from the Internet now
param([switch]$Status, [switch]$SetUtc, [switch]$SetLocal, [switch]$Resync, [switch]$Json)

$ErrorActionPreference = 'Stop'
$Version = '0.2.0'
$TzKey = 'HKLM:\SYSTEM\CurrentControlSet\Control\TimeZoneInformation'
$It = ([Globalization.CultureInfo]::CurrentUICulture.TwoLetterISOLanguageName -eq 'it')
function T([string]$en, [string]$it) { if ($It) { $it } else { $en } }

function Test-Admin {
    ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-RtcUtc {
    $v = (Get-ItemProperty -Path $TzKey -Name RealTimeIsUniversal -ErrorAction SilentlyContinue).RealTimeIsUniversal
    return ($null -ne $v -and [int64]$v -eq 1)
}

function Get-TimeZoneName {
    try { (Get-TimeZone).DisplayName } catch { '' }
}

function Set-RtcUtc([bool]$utc) {
    if ($utc) {
        New-ItemProperty -Path $TzKey -Name RealTimeIsUniversal -PropertyType DWord -Value 1 -Force | Out-Null
    } else {
        Remove-ItemProperty -Path $TzKey -Name RealTimeIsUniversal -ErrorAction SilentlyContinue
    }
}

# Ask the Windows Time service to sync now. Returns $true on success.
function Sync-Time {
    try {
        $svc = Get-Service -Name w32time
        if ($svc.StartType -eq 'Disabled') { return $false }
        if ($svc.Status -ne 'Running') { Start-Service -Name w32time; Start-Sleep -Seconds 2 }
        & w32tm.exe /resync /force *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Get-StatusText([bool]$utc) {
    if ($utc) {
        T "Windows reads the hardware clock as UTC, like Linux. The time stays right when you switch system." `
          "Windows legge l'orologio hardware in UTC, come Linux. L'ora resta giusta quando cambi sistema."
    } else {
        T ("Windows reads the hardware clock as local time (the Windows default). Linux usually reads it as UTC: " +
           "that is why the time is wrong in Windows after using Linux. If in DualPair on Linux you chose " +
           "'Linux in local time', leave it like this.") `
          ("Windows legge l'orologio hardware in ora locale (l'impostazione di Windows). Linux di solito lo legge in " +
           "UTC: per questo, dopo aver usato Linux, l'ora di Windows è sbagliata. Se in DualPair su Linux hai " +
           "scelto 'Linux in ora locale', lascia così.")
    }
}

# ------------------------------------------------------------------ command line
if ($Status -or $SetUtc -or $SetLocal -or $Resync) {
    if (($SetUtc -or $SetLocal -or $Resync) -and -not (Test-Admin)) {
        Write-Error (T 'Run as administrator.' 'Esegui come amministratore.')
        exit 1
    }
    if ($SetUtc -and $SetLocal) { Write-Error '-SetUtc and -SetLocal cannot be used together.'; exit 2 }
    if ($SetUtc) { Set-RtcUtc $true }
    if ($SetLocal) { Set-RtcUtc $false }
    $synced = $null
    if ($Resync -or $SetUtc -or $SetLocal) { $synced = Sync-Time }
    $utc = Get-RtcUtc
    if ($Json) {
        [pscustomobject]@{ rtc_utc = $utc; timezone = (Get-TimeZoneName); synced = $synced; version = $Version } |
            ConvertTo-Json -Compress
    } else {
        Write-Output (Get-StatusText $utc)
        if ($null -ne $synced) {
            Write-Output $(if ($synced) { T 'Time synced.' 'Ora sincronizzata.' }
                           else { T 'Could not sync the time now: restart Windows.' 'Non riesco a sincronizzare l''ora adesso: riavvia Windows.' })
        }
    }
    exit 0
}

# ------------------------------------------------------------------ window
if (-not (Test-Admin)) {
    Start-Process powershell.exe -Verb RunAs -WindowStyle Hidden -ArgumentList `
        "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`""
    exit
}

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$font = New-Object System.Drawing.Font('Segoe UI', 10)
$form = New-Object System.Windows.Forms.Form
$form.Text = "DualPair $Version"
$form.ClientSize = New-Object System.Drawing.Size(540, 380)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false
$form.Font = $font
$form.AutoScaleMode = 'Font'

function New-Label([string]$text, [int]$y, [int]$h, [System.Drawing.Font]$f) {
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $text
    $l.Location = New-Object System.Drawing.Point(20, $y)
    $l.Size = New-Object System.Drawing.Size(500, $h)
    if ($f) { $l.Font = $f }
    $form.Controls.Add($l)
    return $l
}

function New-Button([string]$text, [int]$y) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $text
    $b.Location = New-Object System.Drawing.Point(20, $y)
    $b.Size = New-Object System.Drawing.Size(500, 36)
    $form.Controls.Add($b)
    return $b
}

$null = New-Label (T 'Clock for dual boot' 'Orologio per il dual boot') 16 30 (New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold))
$null = New-Label (T 'The PC has one hardware clock, shared by Windows and Linux. Both must read it the same way.' `
                     'Il PC ha un solo orologio hardware, condiviso da Windows e Linux. Devono leggerlo allo stesso modo.') 52 42 $null
$statusLabel = New-Label '' 100 84 (New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold))
$btnUtc   = New-Button (T 'Use UTC (recommended with Linux)' 'Usa UTC (consigliato con Linux)') 196
$btnLocal = New-Button (T 'Back to local time (Windows default)' "Torna all'ora locale (impostazione di Windows)") 240
$btnSync  = New-Button (T 'Sync the time now' "Sincronizza l'ora adesso") 284
$tz = Get-TimeZoneName
$footer = New-Label ((T 'Time zone: ' 'Fuso orario: ') + $tz) 336 30 $null
$footer.ForeColor = [System.Drawing.Color]::DimGray

function Update-Ui {
    $utc = Get-RtcUtc
    $statusLabel.Text = Get-StatusText $utc
    $statusLabel.ForeColor = if ($utc) { [System.Drawing.Color]::DarkGreen } else { [System.Drawing.Color]::DarkOrange }
    $btnUtc.Enabled = -not $utc
    $btnLocal.Enabled = $utc
}

function Show-Done([string]$what, [bool]$synced) {
    $msg = $what
    if ($synced) { $msg += "`n`n" + (T 'The time has been synced.' "L'ora è stata sincronizzata.") }
    else { $msg += "`n`n" + (T 'If the time is still wrong, restart Windows.' "Se l'ora è ancora sbagliata, riavvia Windows.") }
    [System.Windows.Forms.MessageBox]::Show($form, $msg, 'DualPair', 'OK', 'Information') | Out-Null
}

$btnUtc.Add_Click({
    try {
        Set-RtcUtc $true
        $form.UseWaitCursor = $true
        $ok = Sync-Time
        $form.UseWaitCursor = $false
        Show-Done (T "Done: Windows now reads the hardware clock as UTC.`nIf in DualPair on Linux you had set 'Linux in local time', put Linux back to UTC there (Clock tab)." `
                     "Fatto: ora Windows legge l'orologio hardware in UTC.`nSe in DualPair su Linux avevi scelto 'Linux in ora locale', rimetti Linux in UTC (scheda Orario).") $ok
    } catch { [System.Windows.Forms.MessageBox]::Show($form, "$_", 'DualPair', 'OK', 'Error') | Out-Null }
    Update-Ui
})
$btnLocal.Add_Click({
    try {
        Set-RtcUtc $false
        $form.UseWaitCursor = $true
        $ok = Sync-Time
        $form.UseWaitCursor = $false
        Show-Done (T 'Done: Windows reads the hardware clock as local time again.' "Fatto: Windows legge di nuovo l'orologio hardware in ora locale.") $ok
    } catch { [System.Windows.Forms.MessageBox]::Show($form, "$_", 'DualPair', 'OK', 'Error') | Out-Null }
    Update-Ui
})
$btnSync.Add_Click({
    $form.UseWaitCursor = $true
    $ok = Sync-Time
    $form.UseWaitCursor = $false
    $msg = if ($ok) { T 'Time synced.' 'Ora sincronizzata.' } else { T 'Could not sync now. Check the Internet connection, or restart Windows.' "Non riesco a sincronizzare adesso. Controlla la connessione a Internet, oppure riavvia Windows." }
    [System.Windows.Forms.MessageBox]::Show($form, $msg, 'DualPair', 'OK', 'Information') | Out-Null
})

Update-Ui
[void]$form.ShowDialog()
