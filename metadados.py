#!/usr/bin/env python3
"""
Remove metadados de vídeos (título, comentário, datas, encoder, GPS,
capítulos, capa, IDs da plataforma etc.) SEM recodificar: as faixas de
vídeo e áudio são copiadas bit a bit, então não há perda de qualidade.

Uso:
    python metadados.py video.mp4                 -> cria video_limpo.mp4
    python metadados.py --substituir *.mp4        -> sobrescreve os originais
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

EXTENSOES_VIDEO = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".flv", ".ts", ".3gp"}
_MP4_LIKE = {".mp4", ".m4v", ".mov", ".3gp"}


def ffmpeg_exe() -> str | None:
    """ffmpeg embutido (imageio-ffmpeg, usado no .exe) ou o do sistema."""
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def _rodar(cmd: list[str]) -> subprocess.CompletedProcess:
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    return subprocess.run(
        cmd, capture_output=True, text=True, errors="replace", creationflags=flags
    )


def limpar_metadados(entrada, saida=None, substituir: bool = False) -> Path:
    """Gera uma cópia do vídeo sem metadados e devolve o caminho final.

    - substituir=True: troca o arquivo original pela versão limpa.
    - caso contrário: salva em `saida` ou em NOME_limpo.EXT ao lado do original.
    """
    entrada = Path(entrada)
    if not entrada.is_file():
        raise FileNotFoundError(f"Arquivo não encontrado: {entrada}")
    ff = ffmpeg_exe()
    if not ff:
        raise RuntimeError("ffmpeg não encontrado (instale-o ou use o .exe).")

    if substituir:
        destino = entrada
    elif saida:
        destino = Path(saida)
    else:
        destino = entrada.with_name(f"{entrada.stem}_limpo{entrada.suffix}")
    temp = destino.with_name(f".{destino.stem}.limpando{entrada.suffix}")

    cmd = [
        ff, "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(entrada),
        # só vídeo (sem capas/miniaturas embutidas) e áudio; descarta
        # faixas de dados, legendas e timecode
        "-map", "0:V?", "-map", "0:a?",
        "-c", "copy",
        # apaga metadados globais, por faixa e capítulos
        "-map_metadata", "-1",
        "-map_metadata:s:v", "-1",
        "-map_metadata:s:a", "-1",
        "-map_chapters", "-1",
        # não grava a assinatura "Lavf/encoder" do ffmpeg
        "-fflags", "+bitexact",
        "-flags:v", "+bitexact",
        "-flags:a", "+bitexact",
    ]
    if entrada.suffix.lower() in _MP4_LIKE:
        cmd += ["-movflags", "+faststart"]
    cmd.append(str(temp))

    r = _rodar(cmd)
    if r.returncode != 0 or not temp.exists():
        temp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg falhou: {r.stderr.strip() or r.returncode}")
    os.replace(temp, destino)
    return destino


def main():
    p = argparse.ArgumentParser(description="Remove metadados de vídeos sem perder qualidade.")
    p.add_argument("arquivos", nargs="+", help="um ou mais vídeos")
    p.add_argument("--substituir", action="store_true", help="sobrescreve os arquivos originais")
    args = p.parse_args()

    falhas = 0
    for arq in args.arquivos:
        try:
            print(f"Limpo: {limpar_metadados(arq, substituir=args.substituir)}")
        except Exception as e:
            falhas += 1
            print(f"Falhou: {arq} -> {e}", file=sys.stderr)
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
