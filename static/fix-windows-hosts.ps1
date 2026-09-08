# NoteTask / baski.pro — fix LAN access when Firefox DoH / public DNS
# breaks hairpin (router has no NAT loopback).
# Run PowerShell AS ADMINISTRATOR, then reload the page.
# Usage: irm https://todo.baski.pro/assets/fix-windows-hosts.ps1 | iex
#   or:  powershell -ExecutionPolicy Bypass -File .\fix-windows-hosts.ps1

$ErrorActionPreference = "Stop"
$hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
$ip = "192.168.0.6"
$names = @(
  "todo.baski.pro",
  "baski.pro",
  "www.baski.pro",
  "treck.baski.pro",
  "gendoc.baski.pro"
)

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
  [Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "Нужен запуск от Администратора. ПКМ по PowerShell → Запуск от имени администратора." -ForegroundColor Red
  exit 1
}

$lines = Get-Content $hostsPath -ErrorAction SilentlyContinue
$keep = @()
foreach ($line in $lines) {
  $skip = $false
  foreach ($n in $names) {
    if ($line -match "(?i)\b$([regex]::Escape($n))\b") { $skip = $true; break }
  }
  if (-not $skip) { $keep += $line }
}

$block = @()
$block += ""
$block += "# baski.pro LAN (no hairpin) — managed by fix-windows-hosts.ps1"
foreach ($n in $names) { $block += "$ip`t$n" }

($keep + $block) | Set-Content -Path $hostsPath -Encoding ASCII

Clear-DnsClientCache -ErrorAction SilentlyContinue
Write-Host "OK. hosts обновлён → $ip" -ForegroundColor Green
Write-Host "Проверка: https://todo.baski.pro/  и  https://treck.baski.pro/" -ForegroundColor Cyan
try {
  $r = Invoke-WebRequest -Uri "https://todo.baski.pro/api/health" -UseBasicParsing -TimeoutSec 8
  Write-Host "todo health: $($r.StatusCode) $($r.Content)" -ForegroundColor Green
} catch {
  Write-Host "todo health FAIL: $_" -ForegroundColor Yellow
  Write-Host "Если FAIL — отключи Secure DNS / DoH, либо открой http://192.168.0.6/" -ForegroundColor Yellow
}
try {
  $t = Invoke-WebRequest -Uri "https://treck.baski.pro/health" -UseBasicParsing -TimeoutSec 8
  Write-Host "treck health: $($t.StatusCode) $($t.Content)" -ForegroundColor Green
} catch {
  Write-Host "treck health FAIL: $_" -ForegroundColor Yellow
  Write-Host "Обход LAN: http://192.168.0.6:8000/app" -ForegroundColor Yellow
}
