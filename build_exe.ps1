# Gera BaixadorDeVideos.exe (com ffmpeg embutido) e copia para a Área de Trabalho.
# Requer apenas o uv (https://docs.astral.sh/uv/). Rode de novo para atualizar o yt-dlp.
#   powershell -ExecutionPolicy Bypass -File build_exe.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

uv run --no-project --python 3.12 --with yt-dlp --with imageio-ffmpeg --with pyinstaller `
    pyinstaller --noconfirm --clean --onefile --windowed `
    --name BaixadorDeVideos `
    --collect-all imageio_ffmpeg `
    desktop.py
if ($LASTEXITCODE -ne 0) { throw "Falha no PyInstaller" }

$exe = Join-Path $PSScriptRoot "dist\BaixadorDeVideos.exe"
$desktop = [Environment]::GetFolderPath("Desktop")
Copy-Item $exe $desktop -Force
Write-Host "Pronto: $desktop\BaixadorDeVideos.exe"
