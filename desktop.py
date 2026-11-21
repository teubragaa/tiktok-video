"""App desktop (Windows) do Baixador de Vídeos.

Rodar sem compilar:  python desktop.py
Gerar o .exe:        powershell -ExecutionPolicy Bypass -File build_exe.ps1
"""
import json
import os
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from baixador import baixar
from metadados import EXTENSOES_VIDEO, limpar_metadados

TITULO = "Baixador de Vídeos"
CONFIG = Path(os.environ.get("APPDATA", Path.home())) / "BaixadorDeVideos" / "config.json"


def _carregar_config() -> dict:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _salvar_config(cfg: dict):
    try:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class _LogYtDlp:
    """Encaminha as mensagens do yt-dlp para a janela."""

    def __init__(self, fila: queue.Queue):
        self.fila = fila

    def debug(self, msg):
        if not msg.startswith("[debug]"):
            self.fila.put(("log", msg))

    def info(self, msg):
        self.fila.put(("log", msg))

    def warning(self, msg):
        self.fila.put(("log", f"Aviso: {msg}"))

    def error(self, msg):
        self.fila.put(("log", msg))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(TITULO)
        self.geometry("760x620")
        self.minsize(620, 520)
        self.fila: queue.Queue = queue.Queue()
        self.ocupado = False
        cfg = _carregar_config()

        self.var_pasta = tk.StringVar(value=cfg.get("pasta", str(Path.home() / "Videos" / "Baixador")))
        self.var_limpar = tk.BooleanVar(value=cfg.get("limpar", True))
        self.var_substituir = tk.BooleanVar(value=cfg.get("substituir", False))
        self.var_status = tk.StringVar(value="Pronto.")

        estilo = ttk.Style(self)
        if "vista" in estilo.theme_names():
            estilo.theme_use("vista")
        estilo.configure("Grande.TButton", font=("Segoe UI", 11, "bold"), padding=8)

        abas = ttk.Notebook(self)
        abas.pack(fill="x", padx=10, pady=(10, 4))
        abas.add(self._aba_baixar(abas), text="  Baixar vídeos  ")
        abas.add(self._aba_limpar(abas), text="  Limpar metadados  ")

        rodape = ttk.Frame(self)
        rodape.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.barra = ttk.Progressbar(rodape, mode="determinate", maximum=100)
        self.barra.pack(fill="x", pady=(4, 2))
        ttk.Label(rodape, textvariable=self.var_status).pack(anchor="w")
        caixa = ttk.Frame(rodape)
        caixa.pack(fill="both", expand=True, pady=(4, 0))
        self.log = tk.Text(caixa, height=10, state="disabled", wrap="word",
                           font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
        rolagem = ttk.Scrollbar(caixa, command=self.log.yview)
        self.log.configure(yscrollcommand=rolagem.set)
        rolagem.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.after(100, self._processar_fila)

    # ---------- abas ----------
    def _aba_baixar(self, pai):
        f = ttk.Frame(pai, padding=10)
        ttk.Label(f, text="Cole as URLs (uma por linha) — TikTok, Reels, Shorts, Pinterest, YouTube...").pack(anchor="w")
        self.txt_urls = tk.Text(f, height=5, wrap="none", font=("Segoe UI", 10))
        self.txt_urls.pack(fill="x", pady=4)

        linha = ttk.Frame(f)
        linha.pack(fill="x", pady=4)
        ttk.Label(linha, text="Salvar em:").pack(side="left")
        ttk.Entry(linha, textvariable=self.var_pasta).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(linha, text="Escolher...", command=self._escolher_pasta).pack(side="left")
        ttk.Button(linha, text="Abrir pasta", command=self._abrir_pasta).pack(side="left", padx=(6, 0))

        ttk.Checkbutton(f, text="Remover metadados após baixar", variable=self.var_limpar).pack(anchor="w", pady=4)

        botoes = ttk.Frame(f)
        botoes.pack(fill="x", pady=(4, 0))
        ttk.Button(botoes, text="Colar", command=self._colar).pack(side="left")
        ttk.Button(botoes, text="Limpar campo", command=lambda: self.txt_urls.delete("1.0", "end")).pack(side="left", padx=6)
        self.btn_baixar = ttk.Button(botoes, text="⬇  Baixar na melhor qualidade", style="Grande.TButton",
                                     command=self._iniciar_download)
        self.btn_baixar.pack(side="right")
        return f

    def _aba_limpar(self, pai):
        f = ttk.Frame(pai, padding=10)
        ttk.Label(f, text="Remove título, comentários, datas, encoder, GPS, capa e IDs — sem recodificar (zero perda).").pack(anchor="w")
        self.lista = tk.Listbox(f, height=6, selectmode="extended", font=("Segoe UI", 9))
        self.lista.pack(fill="x", pady=4)

        botoes = ttk.Frame(f)
        botoes.pack(fill="x")
        ttk.Button(botoes, text="Adicionar vídeos...", command=self._adicionar_arquivos).pack(side="left")
        ttk.Button(botoes, text="Remover selecionados", command=self._remover_selecionados).pack(side="left", padx=6)
        ttk.Button(botoes, text="Esvaziar lista", command=lambda: self.lista.delete(0, "end")).pack(side="left")

        ttk.Checkbutton(f, text="Substituir os arquivos originais (senão cria NOME_limpo)",
                        variable=self.var_substituir).pack(anchor="w", pady=6)
        self.btn_limpar = ttk.Button(f, text="🧹  Remover metadados", style="Grande.TButton",
                                     command=self._iniciar_limpeza)
        self.btn_limpar.pack(anchor="e")
        return f

    # ---------- ações ----------
    def _colar(self):
        try:
            texto = self.clipboard_get().strip()
        except tk.TclError:
            return
        if texto:
            atual = self.txt_urls.get("1.0", "end").strip()
            self.txt_urls.insert("end", ("\n" if atual else "") + texto)

    def _escolher_pasta(self):
        p = filedialog.askdirectory(initialdir=self.var_pasta.get() or str(Path.home()))
        if p:
            self.var_pasta.set(p)

    def _abrir_pasta(self):
        p = Path(self.var_pasta.get())
        p.mkdir(parents=True, exist_ok=True)
        os.startfile(p)

    def _adicionar_arquivos(self):
        tipos = " ".join(f"*{e}" for e in sorted(EXTENSOES_VIDEO))
        arquivos = filedialog.askopenfilenames(
            title="Escolha os vídeos", initialdir=self.var_pasta.get(),
            filetypes=[("Vídeos", tipos), ("Todos os arquivos", "*.*")])
        existentes = set(self.lista.get(0, "end"))
        for a in arquivos:
            if a not in existentes:
                self.lista.insert("end", a)

    def _remover_selecionados(self):
        for i in reversed(self.lista.curselection()):
            self.lista.delete(i)

    def _iniciar_download(self):
        urls = [u.strip() for u in self.txt_urls.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showinfo(TITULO, "Cole pelo menos uma URL.")
            return
        self._comecar(self._trabalho_download, urls, self.var_pasta.get(), self.var_limpar.get())

    def _iniciar_limpeza(self):
        arquivos = list(self.lista.get(0, "end"))
        if not arquivos:
            messagebox.showinfo(TITULO, "Adicione pelo menos um vídeo.")
            return
        self._comecar(self._trabalho_limpeza, arquivos, self.var_substituir.get())

    def _comecar(self, alvo, *args):
        if self.ocupado:
            return
        self.ocupado = True
        self.btn_baixar.state(["disabled"])
        self.btn_limpar.state(["disabled"])
        self.barra["value"] = 0
        threading.Thread(target=alvo, args=args, daemon=True).start()

    # ---------- trabalho em segundo plano ----------
    def _trabalho_download(self, urls, pasta, limpar):
        ok = 0
        for i, url in enumerate(urls, 1):
            prefixo = f"[{i}/{len(urls)}]"
            self.fila.put(("status", f"{prefixo} Iniciando..."))
            self.fila.put(("log", f"\n{prefixo} {url}"))

            def progresso(d, prefixo=prefixo):
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    faixa = "áudio" if d.get("info_dict", {}).get("vcodec") == "none" else "vídeo"
                    vel = (d.get("_speed_str") or "").strip()
                    if total:
                        self.fila.put(("prog", d.get("downloaded_bytes", 0) / total * 100))
                    self.fila.put(("status", f"{prefixo} Baixando {faixa}... {vel}"))
                elif d["status"] == "finished":
                    self.fila.put(("prog", 100))
                    self.fila.put(("status", f"{prefixo} Juntando vídeo + áudio..."))

            try:
                caminho = baixar(url, pasta, limpar=limpar, progresso=progresso, logger=_LogYtDlp(self.fila))
                extra = " (metadados removidos)" if limpar else ""
                self.fila.put(("log", f"✔ Salvo{extra}: {caminho}"))
                ok += 1
            except Exception as e:
                self.fila.put(("log", f"✖ Falhou: {e}"))
        self.fila.put(("fim", f"Concluído: {ok}/{len(urls)} vídeo(s) baixado(s)."))

    def _trabalho_limpeza(self, arquivos, substituir):
        ok = 0
        for i, arq in enumerate(arquivos, 1):
            self.fila.put(("status", f"[{i}/{len(arquivos)}] Limpando {Path(arq).name}..."))
            try:
                destino = limpar_metadados(arq, substituir=substituir)
                self.fila.put(("log", f"✔ Limpo: {destino}"))
                ok += 1
            except Exception as e:
                self.fila.put(("log", f"✖ Falhou: {arq}\n   {e}"))
            self.fila.put(("prog", i / len(arquivos) * 100))
        self.fila.put(("fim", f"Concluído: {ok}/{len(arquivos)} vídeo(s) limpo(s)."))

    # ---------- interface ----------
    def _escrever(self, texto):
        self.log.configure(state="normal")
        self.log.insert("end", texto + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _processar_fila(self):
        try:
            while True:
                tipo, valor = self.fila.get_nowait()
                if tipo == "log":
                    self._escrever(valor)
                elif tipo == "prog":
                    self.barra["value"] = valor
                elif tipo == "status":
                    self.var_status.set(valor)
                elif tipo == "fim":
                    self.ocupado = False
                    self.btn_baixar.state(["!disabled"])
                    self.btn_limpar.state(["!disabled"])
                    self.var_status.set(valor)
                    self._escrever(valor)
        except queue.Empty:
            pass
        self.after(100, self._processar_fila)

    def _fechar(self):
        if self.ocupado and not messagebox.askyesno(TITULO, "Há uma tarefa em andamento. Fechar mesmo assim?"):
            return
        _salvar_config({
            "pasta": self.var_pasta.get(),
            "limpar": self.var_limpar.get(),
            "substituir": self.var_substituir.get(),
        })
        self.destroy()


def main():
    if sys.platform == "win32":
        try:  # texto nítido em telas com escala (125%, 150%...)
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()


if __name__ == "__main__":
    main()
