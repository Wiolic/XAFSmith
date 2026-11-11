<#
统一构建脚本（本机与 CI 共用）。在 XAFSmith/ 目录下运行：
    powershell -ExecutionPolicy Bypass -File packaging\build.ps1 [-SkipTests] [-SkipInstaller] [-LimitMB 550] [-Python python]
步骤：
  1. 独立构建环境 .venv-build（不动日常 .venv）：pip install -e . pyinstaller，然后卸载 mkl / mkl_fft（larch 回退到 scipy.fftpack）
  2. 在构建环境里跑 pytest（unit + benchmark）——证明去掉 MKL 后数值不变
  3. PyInstaller 构建 → size_report 体积护栏（超限或出现禁用包则失败）
  4. 冒烟测试：--version / validate / process / fit Cu 箔（amp≈0.92、ΔE0≈4.4）
  5. Inno Setup（iscc）生成安装程序 + 便携 zip
任一步失败即停止（退出码非 0）。
#>
param(
    [switch]$SkipTests,
    [switch]$SkipInstaller,
    [double]$LimitMB = 550,
    [string]$Python = "python",
    [string]$Iscc = ""          # Inno Setup 的 ISCC.exe 路径；不给则自动查找（PATH、Program Files、$env:INNO_SETUP_DIR）
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Cyan }
function Run($exe, [string[]]$a) {
    $ErrorActionPreference = "Continue"      # 原生程序写 stderr（如 pip 警告）不应被当作终止错误，只看退出码
    & $exe @a
    if ($LASTEXITCODE -ne 0) { throw "失败（$LASTEXITCODE）：$exe $($a -join ' ')" }
}

Step "1/5 构建环境 .venv-build"
$venv = Join-Path $root ".venv-build"
if (-not (Test-Path (Join-Path $venv "Scripts\python.exe"))) { Run $Python @("-m", "venv", $venv) }
$py = Join-Path $venv "Scripts\python.exe"
Run $py @("-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel", "--quiet")
Run $py @("-m", "pip", "install", "-e", ".[dev]", "pyinstaller", "--quiet")
$ErrorActionPreference = "Continue"; & $py -m pip uninstall -y mkl_fft mkl; $ErrorActionPreference = "Stop"   # 未安装时报错无妨
$left = & $py -m pip list --format=freeze | Select-String -Pattern "^(mkl|mkl_fft)=="
if ($left) { throw "mkl 仍在构建环境里：$left" }

if (-not $SkipTests) {
    Step "2/5 pytest（unit + benchmark，无 MKL）"
    Run $py @("-m", "pytest", "tests/unit", "tests/benchmark", "-q")
} else { Write-Host "跳过测试（-SkipTests）：数值未验证" -ForegroundColor Yellow }

Step "3/5 PyInstaller + 体积护栏"
Run $py @("-m", "PyInstaller", "packaging\xafsmith.spec", "--noconfirm", "--distpath", "dist", "--workpath", "build\pyi")
Run $py @("packaging\size_report.py", "dist\XAFSmith", "--limit-mb", "$LimitMB")

Step "4/5 冒烟测试（打包后的程序）"
$cli = Join-Path $root "dist\XAFSmith\xafsmith-cli.exe"
$demo = Join-Path ([IO.Path]::GetTempPath()) ("xafsmith_demo_" + [guid]::NewGuid().ToString("N").Substring(0, 8))
Copy-Item -Recurse (Join-Path $root "tests\data\demo_project") $demo
try {
    Run $cli @("--version")
    Run $cli @("--project", $demo, "validate")
    Run $cli @("--project", $demo, "process")
    # Cu 箔拟合冒烟：模型与 feffcu01.dat（larch 教程）临时写进演示项目副本，结果与 larch 教程值比对
    New-Item -ItemType Directory -Force (Join-Path $demo "output\feff\cu"), (Join-Path $demo "models") | Out-Null
    Copy-Item (Join-Path $root "tests\data\benchmark\feffcu01.dat") (Join-Path $demo "output\feff\cu\")
    $model = '{"name":"cu_smoke","sample":"cu_metal_rt","kmin":3.0,"kmax":17.0,"dk":4.0,"window":"kaiser","kweight":[2],"rmin":1.4,"rmax":3.0,"fitspace":"r","params":{"s02":{"value":0.9,"vary":true,"min":0.3,"max":1.5},"e0":{"value":0.0,"vary":true,"min":-15,"max":15},"dr1":{"value":0.0,"vary":true,"min":-0.3,"max":0.3},"ss1":{"value":0.003,"vary":true,"min":0.0,"max":0.03}},"paths":[{"file":"output/feff/cu/feffcu01.dat","label":"Cu-Cu","N":"12","s02":"s02","e0":"e0","deltar":"dr1","sigma2":"ss1"}]}'
    [IO.File]::WriteAllText((Join-Path $demo "models\cu_smoke.json"), $model, (New-Object Text.UTF8Encoding($false)))
    $ErrorActionPreference = "Continue"
    $out = & $cli --project $demo fit cu_smoke --nosave 2>&1 | Out-String
    $code = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    if ($code -ne 0) { Write-Host $out; throw "fit 冒烟失败" }
    $m = [regex]::Match($out, "n\*s02\s*=\s*([-\d.eE+]+).*?e0\s*=\s*([-\d.eE+]+).*?sigma2\s*=\s*([-\d.eE+]+)", "Singleline")
    if (-not $m.Success) { Write-Host $out; throw "fit 冒烟：读不到拟合结果" }
    $s02 = [double]$m.Groups[1].Value / 12; $e0 = [double]$m.Groups[2].Value; $ss = [double]$m.Groups[3].Value
    Write-Host ("Cu 箔：S0²={0:N3} ΔE0={1:N3} σ²={2:N5}（larch 教程 0.93 / 4.364 / 0.0087）" -f $s02, $e0, $ss)
    if ([math]::Abs($s02 - 0.917) -gt 0.01 -or [math]::Abs($e0 - 4.373) -gt 0.1 -or [math]::Abs($ss - 0.00867) -gt 0.0003) { throw "Cu 箔拟合结果偏离基准（0.917 / 4.373 / 0.00867）" }
} finally {
    if (Test-Path $demo) { Remove-Item -Recurse -Force $demo }
}

$ver = (& $py -c "import xafsmith;print(xafsmith.__version__)").Trim()
if (-not $SkipInstaller) {
    Step "5/5 安装程序与便携 zip（版本 $ver）"
    $isccCmd = Get-Command iscc -ErrorAction SilentlyContinue
    $cand = @($Iscc, "$env:INNO_SETUP_DIR\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "${env:ProgramFiles}\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe")
    $isccPath = if ($isccCmd) { $isccCmd.Source } else { $cand | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1 }
    if (-not $isccPath) { throw "找不到 Inno Setup（ISCC.exe）。请先安装 Inno Setup 6，或加 -SkipInstaller。" }
    Run $isccPath @("/DAppVersion=$ver", "packaging\xafsmith.iss")
    $zip = "dist\XAFSmith-$ver-win64-portable.zip"
    if (Test-Path $zip) { Remove-Item $zip }
    Compress-Archive -Path "dist\XAFSmith" -DestinationPath $zip
    Get-ChildItem dist\XAFSmith-* | ForEach-Object { "{0,8:N1} MB  {1}" -f ($_.Length / 1MB), $_.Name }
    Get-ChildItem dist\XAFSmith-$ver-* | Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } | Set-Content dist\SHA256SUMS.txt -Encoding ascii
}
Write-Host "`n构建完成。" -ForegroundColor Green
