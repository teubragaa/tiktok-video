#!/usr/bin/env python3
"""
Baixador de vídeos (TikTok, Reels, Shorts, Pinterest, YouTube etc.) na
melhor qualidade disponível, sem limite de resolução ou codec.

Uso:
    python baixador.py "https://www.tiktok.com/@user/video/123"
    python baixador.py --limpar "URL1" "URL2"      # + remove metadados
"""
import argparse
import sys
from pathlib import Path

from yt_dlp import YoutubeDL

from metadados import ffmpeg_exe, limpar_metadados


def _caminho_baixado(info: dict) -> Path:
    """Acha o arquivo final, inclusive quando a URL é um post com vários vídeos."""
    for item in [info, *(info.get("entries") or [])]:
        if not item:
            continue
        for d in item.get("requested_downloads") or []:
            if d.get("filepath"):
                return Path(d["filepath"])
        if item.get("filepath"):
            return Path(item["filepath"])
    raise RuntimeError("Download concluído, mas o arquivo não foi localizado.")


def baixar(url: str, pasta="downloads", limpar: bool = False, progresso=None, logger=None) -> Path:
    """Baixa o vídeo escolhendo sempre o vídeo e o áudio de maior
    qualidade disponíveis, juntando os dois num único MP4 (sem recodificar,
    então não há perda de qualidade).

    O nome do arquivo é curto: PLATAFORMA_ID.mp4 (ex.: TikTok_7234567890.mp4).
    Com limpar=True os metadados são removidos logo após o download.
    """
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    opts = {
        # melhor vídeo + melhor áudio separados; "b" só como último recurso
        "format": "bv*+ba/b",
        # ie_pref: evita as versões com marca d'água (ex.: TikTok);
        # depois ordena por resolução, fps, HDR, bitrate e taxa de amostragem
        "format_sort": ["ie_pref", "res", "fps", "hdr:12", "vbr", "tbr", "abr", "asr"],
        "merge_output_format": "mp4",
        # nome curto e sempre único, sem título/uploader gigantes
        "outtmpl": str(pasta / "%(extractor_key)s_%(id).50s.%(ext)s"),
        # remove caracteres problemáticos e limita o tamanho total do nome
        "restrictfilenames": True,
        "trim_file_name": 80,
        "noplaylist": True,
        # não usa a data de upload como data do arquivo
        "updatetime": False,
        # qualidade acima de velocidade: tenta de novo se a conexão falhar
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 5,
        "concurrent_fragment_downloads": 4,
    }
    ff = ffmpeg_exe()
    if ff:
        # sem ffmpeg não dá para juntar vídeo+áudio separados (= qualidade menor)
        opts["ffmpeg_location"] = ff
    if progresso:
        opts["progress_hooks"] = [progresso]
        opts["noprogress"] = True
    if logger:
        opts["logger"] = logger

    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        caminho = _caminho_baixado(info)

    if limpar:
        caminho = limpar_metadados(caminho, substituir=True)
    return caminho


def main():
    p = argparse.ArgumentParser(description="Baixa vídeos na melhor qualidade possível.")
    p.add_argument("urls", nargs="+", help="uma ou mais URLs de vídeo")
    p.add_argument("--limpar", action="store_true", help="remove os metadados após baixar")
    p.add_argument("--pasta", default="downloads", help="pasta de destino (padrão: downloads)")
    args = p.parse_args()

    erros = []
    for url in args.urls:
        try:
            print(f"Salvo em: {baixar(url, args.pasta, limpar=args.limpar)}")
        except Exception as e:
            erros.append((url, e))
            print(f"Falhou: {url} -> {e}", file=sys.stderr)

    if erros:
        sys.exit(1)


if __name__ == "__main__":
    main()
