#!/usr/bin/env python3
"""
Baixador de vídeos (TikTok, Reels, Shorts, YouTube etc.) na melhor
qualidade disponível, sem limite de resolução ou codec.

Uso:
    python baixador.py "https://www.tiktok.com/@user/video/123"
    python baixador.py "URL1" "URL2" "URL3"
"""
import argparse
import sys
from pathlib import Path

from yt_dlp import YoutubeDL


def baixar(url: str, pasta: str = "downloads") -> Path:
    """Baixa o vídeo escolhendo sempre o vídeo e o áudio de maior
    qualidade disponíveis (resolução, depois fps, depois bitrate),
    juntando os dois num único MP4."""
    Path(pasta).mkdir(exist_ok=True)
    opts = {
        # bestvideo + bestaudio separados = maior qualidade possível;
        # "b" como último recurso, caso a origem só ofereça um arquivo único
        "format": "bv*+ba/b",
        # ordena todas as opções pela maior qualidade real, ignorando codec
        "format_sort": ["res", "fps", "vbr", "abr"],
        "merge_output_format": "mp4",
        "outtmpl": f"{pasta}/%(uploader)s - %(title).60s [%(id)s].%(ext)s",
        "noplaylist": True,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        caminho = Path(info["requested_downloads"][0]["filepath"])
    print(f"Salvo em: {caminho}")
    return caminho


def main():
    p = argparse.ArgumentParser(description="Baixa vídeos na melhor qualidade possível.")
    p.add_argument("urls", nargs="+", help="uma ou mais URLs de vídeo")
    args = p.parse_args()

    erros = []
    for url in args.urls:
        try:
            baixar(url)
        except Exception as e:
            erros.append((url, e))
            print(f"Falhou: {url} -> {e}", file=sys.stderr)

    if erros:
        sys.exit(1)


if __name__ == "__main__":
    main()
