#!/usr/bin/env python3
"""
Baixador de vídeos (TikTok, Reels, Shorts, Pinterest, YouTube etc.) na
melhor qualidade disponível, sem limite de resolução ou codec.

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
    qualidade disponíveis, juntando os dois num único MP4 (sem recodificar,
    então não há perda de qualidade).

    O nome do arquivo é curto: PLATAFORMA_ID.mp4 (ex.: TikTok_7234567890.mp4).
    """
    Path(pasta).mkdir(exist_ok=True)
    opts = {
        # melhor vídeo + melhor áudio separados; "b" só como último recurso
        "format": "bv*+ba/b",
        # ie_pref: evita as versões com marca d'água (ex.: TikTok);
        # depois ordena por resolução, fps, HDR e bitrate reais
        "format_sort": ["ie_pref", "res", "fps", "hdr", "vbr", "tbr", "abr"],
        "merge_output_format": "mp4",
        # nome curto e sempre único, sem título/uploader gigantes
        "outtmpl": f"{pasta}/%(extractor_key)s_%(id).50s.%(ext)s",
        # remove caracteres problemáticos e limita o tamanho total do nome
        "restrictfilenames": True,
        "trim_file_name": 80,
        "noplaylist": True,
        # qualidade acima de velocidade: tenta de novo se a conexão falhar
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 5,
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
