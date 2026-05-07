$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"
$Wheel = Join-Path $Root "dist\chat_hole-0.2.0-py3-none-any.whl"
$TempDir = Join-Path $Root ".tmp"

New-Item -ItemType Directory -Force $TempDir | Out-Null
$env:TEMP = $TempDir
$env:TMP = $TempDir

if (!(Test-Path $Wheel)) {
    Write-Host "未找到安装包，正在构建 wheel..."
    python "$Root\setup.py" bdist_wheel
}

if (!(Test-Path $Venv)) {
    Write-Host "正在创建本地虚拟环境..."
    python -m venv $Venv
    if ($LASTEXITCODE -ne 0) {
        throw "创建虚拟环境失败。请确认 Python 的 venv/ensurepip 可用。"
    }
}

$Pip = Join-Path $Venv "Scripts\python.exe"
& $Pip -m pip --version | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "虚拟环境中没有 pip。请尝试修复 Python 安装，或直接使用: python .\lan_chat.py --help"
}

Write-Host "正在安装 Chat Hole..."
& $Pip -m pip install --force-reinstall $Wheel
if ($LASTEXITCODE -ne 0) {
    throw "安装失败。"
}

@'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$Root\.venv\Scripts\chat-hole.exe" --server @args
'@ | Set-Content -Path (Join-Path $Root "run-server.ps1") -Encoding UTF8

@'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$Root\.venv\Scripts\chat-hole.exe" @args
'@ | Set-Content -Path (Join-Path $Root "run-client.ps1") -Encoding UTF8

Write-Host ""
Write-Host "安装完成。"
Write-Host "启动服务器: .\run-server.ps1"
Write-Host "连接服务器: .\run-client.ps1 --name 小高"
