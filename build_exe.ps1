# Gera BaixadorDeVideos.exe (com tema Dark Studio, ícone e ffmpeg embutidos) e copia para a Área de Trabalho.
# Requer apenas o uv (https://docs.astral.sh/uv/). Rode de novo para atualizar o yt-dlp.
#   powershell -ExecutionPolicy Bypass -File build_exe.ps1
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

# Gera um ícone moderno (icone.ico) automaticamente caso não exista
$gerarIcone = @"
from PIL import Image, ImageDraw
imgs = []
for sz in (256, 128, 64, 48, 32, 16):
    im = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    r = max(4, sz // 4)
    d.rounded_rectangle([0, 0, sz - 1, sz - 1], radius=r, fill=(99, 102, 241, 255))
    cx = sz / 2
    w = max(2, sz * 0.14)
    d.rounded_rectangle([cx - w / 2, sz * 0.22, cx + w / 2, sz * 0.56], radius=max(1, int(w / 2)), fill=(255, 255, 255, 255))
    d.polygon([(cx - sz * 0.24, sz * 0.48), (cx + sz * 0.24, sz * 0.48), (cx, sz * 0.72)], fill=(255, 255, 255, 255))
    d.rounded_rectangle([sz * 0.26, sz * 0.77, sz * 0.74, sz * 0.84], radius=max(1, sz // 24), fill=(199, 210, 254, 255))
    imgs.append(im)
imgs[0].save('icone.ico', format='ICO', sizes=[(s.width, s.height) for s in imgs], append_images=imgs[1:])
"@
uv run --no-project --python 3.12 --with pillow python -c $gerarIcone

uv run --no-project --python 3.12 --with yt-dlp --with imageio-ffmpeg --with customtkinter --with pyinstaller `
    pyinstaller --noconfirm --clean --onefile --windowed `
    --name BaixadorDeVideos `
    --icon icone.ico `
    --add-data "icone.ico;." `
    --collect-all imageio_ffmpeg `
    --collect-all customtkinter `
    desktop.py
if ($LASTEXITCODE -ne 0) { throw "Falha no PyInstaller" }

$exe = Join-Path $PSScriptRoot "dist\BaixadorDeVideos.exe"
$desktop = [Environment]::GetFolderPath("Desktop")
Get-Process BaixadorDeVideos -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 400
Copy-Item $exe $desktop -Force
Write-Host "Pronto: $desktop\BaixadorDeVideos.exe"
