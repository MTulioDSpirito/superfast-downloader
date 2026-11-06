# build_windows.ps1 — compila o instalador Inno Setup do SuperFast DM (Windows).
#
# Uso local:
#   powershell -ExecutionPolicy Bypass -File installer\windows\build_windows.ps1
# (O workflow do GitHub Actions chama este MESMO script — nada duplicado.)
#
# Produz:
#   installer\windows\output\SuperFastDM-Setup-<ver>.exe   (+ .sha256)
#
# Requer o Inno Setup 6. Ordem de localizacao do ISCC.exe:
#   1) ja instalado no PATH/Program Files  2) choco install innosetup
#   3) download portable oficial do GitHub (fallback extremo)

$ErrorActionPreference = "Stop"

$here   = Split-Path -Parent $MyInvocation.MyCommand.Path
$iss    = Join-Path $here "superfastdm.iss"
$outDir = Join-Path $here "output"

# --- le a versao do .iss (MyAppVersion "x.y") ---
$line = Select-String -Path $iss -Pattern 'MyAppVersion\s+"([^"]+)"' | Select-Object -First 1
if (-not $line) { Write-Error "nao encontrei MyAppVersion em $iss"; exit 1 }
$ver = $line.Matches[0].Groups[1].Value
Write-Host "Versao: $ver"

# --- localiza ISCC.exe ---
function Find-ISCC {
  $pf86 = ${env:ProgramFiles(x86)}
  $pf   = $env:ProgramFiles
  $candidates = @(
    (Join-Path $pf86 "Inno Setup 6\ISCC.exe"),
    (Join-Path $pf   "Inno Setup 6\ISCC.exe")
  )
  foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
  $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  return $null
}

$iscc = Find-ISCC
if (-not $iscc) {
  Write-Host "ISCC nao encontrado; tentando chocolatey..."
  choco install innosetup --no-progress -y
  $iscc = Find-ISCC
}
if (-not $iscc) {
  Write-Host "choco nao resolveu; baixando Inno Setup (portable) do GitHub..."
  $portable = Join-Path $here "_inno"
  $dl = Join-Path $here "innosetup.exe"
  $u = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
  Invoke-WebRequest -Uri $u -OutFile $dl
  & $dl //portable=1 //silent //currentuser //dir="$portable"
  Remove-Item $dl -ErrorAction SilentlyContinue
  $iscc = Join-Path $portable "ISCC.exe"
}
if (-not (Test-Path $iscc)) { Write-Error "ISCC.exe continua indisponivel"; exit 1 }
$pv = (Get-Item $iscc).VersionInfo.ProductVersion
Write-Host "Usando Inno Setup $pv : $iscc"

# --- compila ---
if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }
New-Item -ItemType Directory -Path $outDir | Out-Null
& $iscc $iss
if ($LASTEXITCODE -ne 0) { Write-Error "ISCC falhou (exit $LASTEXITCODE)"; exit 1 }

$exe = Join-Path $outDir "SuperFastDM-Setup-$ver.exe"
if (-not (Test-Path $exe)) { Write-Error "saida nao encontrada: $exe"; exit 1 }

# --- sha256 ---
$hash = (Get-FileHash $exe -Algorithm SHA256).Hash
$leaf = Split-Path $exe -Leaf
("{0}  {1}" -f $hash, $leaf) | Out-File (Join-Path $outDir "$leaf.sha256") -Encoding ascii

$kb = [math]::Round((Get-Item $exe).Length / 1KB)
Write-Host "============================================================"
Write-Host " Instalador gerado : $exe"
Write-Host " Tamanho           : ${kb} KB"
Write-Host " SHA-256           : $hash"
Write-Host "============================================================"

# limpeza do portable (se foi usado)
Remove-Item (Join-Path $here "_inno") -Recurse -Force -ErrorAction SilentlyContinue
