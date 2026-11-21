"""App desktop (Windows) do Baixador de Vídeos — Interface Dark Studio.

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
from tkinter import filedialog, messagebox

import customtkinter as ctk

from baixador import baixar
from metadados import EXTENSOES_VIDEO, limpar_metadados

TITULO = "Baixador de Vídeos"
CONFIG = Path(os.environ.get("APPDATA", Path.home())) / "BaixadorDeVideos" / "config.json"

# Paleta Dark Studio (Obsidian & Indigo)
COR_FUNDO = "#0B0F17"
COR_CARD = "#131A26"
COR_CARD_INTERNO = "#0E141F"
COR_BORDA = "#1F2A3D"
COR_BORDA_FORTE = "#2A3952"
COR_PRIMARIA = "#6366F1"
COR_PRIMARIA_HOVER = "#4F46E5"
COR_SECUNDARIA = "#1E293B"
COR_SECUNDARIA_HOVER = "#334155"
COR_TEXTO = "#F8FAFC"
COR_SUBTEXTO = "#94A3B8"
COR_MUTED = "#64748B"
COR_SUCESSO = "#10B981"
COR_AVISO = "#F59E0B"
COR_ERRO = "#EF4444"

PLACEHOLDER_URLS = (
    "https://www.tiktok.com/@usuario/video/1234567890\n"
    "https://www.instagram.com/reel/ABC123xyz/\n"
    "https://www.youtube.com/shorts/xyz987..."
)


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


def _formatar_tamanho(caminho: str) -> str:
    try:
        b = Path(caminho).stat().st_size
        if b >= 1024 * 1024:
            return f"{b / (1024 * 1024):.1f} MB"
        return f"{b / 1024:.0f} KB"
    except Exception:
        return ""


class _LogYtDlp:
    """Encaminha as mensagens do yt-dlp para a janela."""

    def __init__(self, fila: queue.Queue):
        self.fila = fila

    def debug(self, msg):
        if not msg.startswith("[debug]"):
            self.fila.put(("log", ("info", msg)))

    def info(self, msg):
        self.fila.put(("log", ("info", msg)))

    def warning(self, msg):
        self.fila.put(("log", ("aviso", f"⚠ Aviso: {msg}")))

    def error(self, msg):
        self.fila.put(("log", ("erro", msg)))


class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=COR_FUNDO)
        self.title(TITULO)
        self.geometry("860x720")
        self.minsize(740, 640)
        self._ativar_barra_escura_win11()
        self._aplicar_icone()

        self.fila: queue.Queue = queue.Queue()
        self.ocupado = False
        self.arquivos_limpeza: list[str] = []
        self._placeholder_ativo = False
        cfg = _carregar_config()

        self.var_pasta = tk.StringVar(value=cfg.get("pasta", str(Path.home() / "Videos" / "Baixador")))
        self.var_limpar = tk.BooleanVar(value=cfg.get("limpar", True))
        self.var_substituir = tk.BooleanVar(value=cfg.get("substituir", False))
        self.var_status = tk.StringVar(value="Pronto para começar")
        self.var_pct = tk.StringVar(value="0%")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self._construir_cabecalho()
        self._construir_navegacao()
        self._construir_painel_principal()
        self._construir_painel_progresso()

        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.after(80, self._processar_fila)

    def _ativar_barra_escura_win11(self):
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
                valor = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(valor), ctypes.sizeof(valor))
            except Exception:
                pass

    def _aplicar_icone(self):
        for base in [Path(getattr(sys, "_MEIPASS", "")), Path(__file__).parent]:
            ico = base / "icone.ico"
            if ico.is_file():
                try:
                    self.iconbitmap(str(ico))
                except Exception:
                    pass
                break

    # ---------- estrutura visual ----------
    def _construir_cabecalho(self):
        topo = ctk.CTkFrame(self, fg_color="transparent")
        topo.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 10))
        topo.grid_columnconfigure(1, weight=1)

        # Ícone / Emblema com destaque Indigo
        emblema = ctk.CTkFrame(
            topo, width=46, height=46, corner_radius=12,
            fg_color=COR_PRIMARIA, border_width=1, border_color="#818CF8"
        )
        emblema.grid(row=0, column=0, rowspan=2, padx=(0, 14))
        emblema.grid_propagate(False)
        ctk.CTkLabel(
            emblema, text="⬇", font=ctk.CTkFont("Segoe UI", 22, "bold"), text_color="#FFFFFF"
        ).place(relx=0.5, rely=0.48, anchor="center")

        ctk.CTkLabel(
            topo, text="Baixador de Vídeos",
            font=ctk.CTkFont("Segoe UI", 21, "bold"), text_color=COR_TEXTO
        ).grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            topo, text="TikTok · Reels · Shorts · YouTube · Pinterest  —  Qualidade máxima original & limpeza de metadados",
            font=ctk.CTkFont("Segoe UI", 12), text_color=COR_SUBTEXTO
        ).grid(row=1, column=1, sticky="w")

        # Pílula de status no canto direito
        self.pilula_status = ctk.CTkFrame(
            topo, fg_color=COR_CARD, corner_radius=20,
            border_width=1, border_color=COR_BORDA
        )
        self.pilula_status.grid(row=0, column=2, rowspan=2, sticky="e")
        self.lbl_ponto_status = ctk.CTkLabel(
            self.pilula_status, text="●", font=ctk.CTkFont("Segoe UI", 12),
            text_color=COR_SUCESSO
        )
        self.lbl_ponto_status.pack(side="left", padx=(12, 5), pady=5)
        self.lbl_texto_pilula = ctk.CTkLabel(
            self.pilula_status, text="Online · Zero-Loss",
            font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=COR_SUBTEXTO
        )
        self.lbl_texto_pilula.pack(side="left", padx=(0, 12), pady=5)

    def _construir_navegacao(self):
        self.seletor_aba = ctk.CTkSegmentedButton(
            self,
            values=["⬇   Baixar Vídeos", "🛡️   Limpar Metadados"],
            command=self._trocar_aba,
            height=40,
            corner_radius=10,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=COR_CARD,
            selected_color=COR_PRIMARIA,
            selected_hover_color=COR_PRIMARIA_HOVER,
            unselected_color=COR_CARD,
            unselected_hover_color=COR_SECUNDARIA,
            text_color=COR_TEXTO,
        )
        self.seletor_aba.grid(row=1, column=0, sticky="ew", padx=24, pady=(4, 12))
        self.seletor_aba.set("⬇   Baixar Vídeos")

    def _construir_painel_principal(self):
        self.container_abas = ctk.CTkFrame(
            self, fg_color=COR_CARD, corner_radius=16,
            border_width=1, border_color=COR_BORDA
        )
        self.container_abas.grid(row=2, column=0, sticky="ew", padx=24, pady=(0, 12))
        self.container_abas.grid_columnconfigure(0, weight=1)

        self.frame_baixar = self._criar_aba_baixar(self.container_abas)
        self.frame_limpar = self._criar_aba_limpar(self.container_abas)
        self.frame_baixar.grid(row=0, column=0, sticky="nsew", padx=20, pady=18)

    def _trocar_aba(self, valor: str):
        if "Baixar" in valor:
            self.frame_limpar.grid_forget()
            self.frame_baixar.grid(row=0, column=0, sticky="nsew", padx=20, pady=18)
        else:
            self.frame_baixar.grid_forget()
            self.frame_limpar.grid(row=0, column=0, sticky="nsew", padx=20, pady=18)

    def _criar_aba_baixar(self, pai):
        f = ctk.CTkFrame(pai, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)

        # Linha 0: Título da seção + ações rápidas de clipboard
        cab = ctk.CTkFrame(f, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        cab.grid_columnconfigure(0, weight=1)

        bloco_titulo = ctk.CTkFrame(cab, fg_color="transparent")
        bloco_titulo.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            bloco_titulo, text="URLs dos vídeos",
            font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=COR_TEXTO
        ).pack(side="left")
        ctk.CTkLabel(
            bloco_titulo, text="  •  Cole um ou vários links (um por linha)",
            font=ctk.CTkFont("Segoe UI", 12), text_color=COR_MUTED
        ).pack(side="left")

        acoes_url = ctk.CTkFrame(cab, fg_color="transparent")
        acoes_url.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            acoes_url, text="📋  Colar link", width=110, height=30, corner_radius=8,
            fg_color=COR_SECUNDARIA, hover_color=COR_SECUNDARIA_HOVER,
            border_width=1, border_color=COR_BORDA_FORTE,
            font=ctk.CTkFont("Segoe UI", 12, "bold"), command=self._colar
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            acoes_url, text="✕  Limpar", width=86, height=30, corner_radius=8,
            fg_color="transparent", hover_color=COR_SECUNDARIA,
            border_width=1, border_color=COR_BORDA,
            text_color=COR_SUBTEXTO, font=ctk.CTkFont("Segoe UI", 12),
            command=self._limpar_campo_urls
        ).pack(side="left")

        # Linha 1: Caixa de texto de URLs
        self.txt_urls = ctk.CTkTextbox(
            f, height=104, corner_radius=12,
            fg_color=COR_CARD_INTERNO, border_width=1, border_color=COR_BORDA_FORTE,
            text_color=COR_TEXTO, font=ctk.CTkFont("Consolas", 12), wrap="none"
        )
        self.txt_urls.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        self.txt_urls.bind("<FocusIn>", self._ao_focar_urls)
        self.txt_urls.bind("<FocusOut>", self._ao_desfocar_urls)
        self._mostrar_placeholder()

        # Linha 2: Pasta de destino em sub-card elegante
        card_opcoes = ctk.CTkFrame(
            f, fg_color=COR_CARD_INTERNO, corner_radius=12,
            border_width=1, border_color=COR_BORDA
        )
        card_opcoes.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        card_opcoes.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card_opcoes, text="📁  Destino:",
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=COR_SUBTEXTO
        ).grid(row=0, column=0, padx=(14, 8), pady=(12, 8), sticky="w")

        self.ent_pasta = ctk.CTkEntry(
            card_opcoes, textvariable=self.var_pasta, height=34, corner_radius=8,
            fg_color=COR_CARD, border_width=1, border_color=COR_BORDA_FORTE,
            text_color=COR_TEXTO, font=ctk.CTkFont("Segoe UI", 12)
        )
        self.ent_pasta.grid(row=0, column=1, padx=(0, 8), pady=(12, 8), sticky="ew")

        ctk.CTkButton(
            card_opcoes, text="Alterar...", width=92, height=34, corner_radius=8,
            fg_color=COR_SECUNDARIA, hover_color=COR_SECUNDARIA_HOVER,
            font=ctk.CTkFont("Segoe UI", 12), command=self._escolher_pasta
        ).grid(row=0, column=2, padx=(0, 6), pady=(12, 8))

        ctk.CTkButton(
            card_opcoes, text="Abrir pasta", width=98, height=34, corner_radius=8,
            fg_color=COR_SECUNDARIA, hover_color=COR_SECUNDARIA_HOVER,
            font=ctk.CTkFont("Segoe UI", 12), command=self._abrir_pasta
        ).grid(row=0, column=3, padx=(0, 14), pady=(12, 8))

        # Linha divisória fina
        ctk.CTkFrame(card_opcoes, height=1, fg_color=COR_BORDA).grid(
            row=1, column=0, columnspan=4, sticky="ew", padx=14
        )

        # Switch de remoção de metadados
        linha_switch = ctk.CTkFrame(card_opcoes, fg_color="transparent")
        linha_switch.grid(row=2, column=0, columnspan=4, sticky="ew", padx=14, pady=(10, 12))

        ctk.CTkSwitch(
            linha_switch,
            text="  Limpar metadados automaticamente após o download (IDs, GPS, datas, encoder)",
            variable=self.var_limpar,
            progress_color=COR_PRIMARIA,
            button_color="#FFFFFF",
            button_hover_color="#E2E8F0",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=COR_TEXTO,
        ).pack(side="left")

        badge = ctk.CTkLabel(
            linha_switch, text=" SEM PERDA ", corner_radius=6,
            fg_color="#1E1B4B", text_color="#A5B4FC",
            font=ctk.CTkFont("Segoe UI", 10, "bold")
        )
        badge.pack(side="right")

        # Linha 3: Botão principal de ação
        self.btn_baixar = ctk.CTkButton(
            f, text="⬇   Baixar na Melhor Qualidade Disponível",
            height=46, corner_radius=12,
            fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HOVER,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color="#FFFFFF", command=self._iniciar_download
        )
        self.btn_baixar.grid(row=3, column=0, sticky="ew")
        return f

    def _criar_aba_limpar(self, pai):
        f = ctk.CTkFrame(pai, fg_color="transparent")
        f.grid_columnconfigure(0, weight=1)

        # Cabeçalho + botões de adicionar/esvaziar
        cab = ctk.CTkFrame(f, fg_color="transparent")
        cab.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        cab.grid_columnconfigure(0, weight=1)

        info_col = ctk.CTkFrame(cab, fg_color="transparent")
        info_col.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            info_col, text="Limpeza profunda de metadados",
            font=ctk.CTkFont("Segoe UI", 14, "bold"), text_color=COR_TEXTO
        ).pack(anchor="w")
        ctk.CTkLabel(
            info_col,
            text="Copia vídeo e áudio bit a bit (-c copy) removendo rastros, IDs do TikTok, GPS, datas e capas.",
            font=ctk.CTkFont("Segoe UI", 12), text_color=COR_MUTED
        ).pack(anchor="w")

        botoes = ctk.CTkFrame(cab, fg_color="transparent")
        botoes.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(
            botoes, text="+  Adicionar vídeos...", width=150, height=32, corner_radius=8,
            fg_color=COR_SECUNDARIA, hover_color=COR_SECUNDARIA_HOVER,
            border_width=1, border_color=COR_BORDA_FORTE,
            font=ctk.CTkFont("Segoe UI", 12, "bold"), command=self._adicionar_arquivos
        ).pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            botoes, text="Esvaziar", width=84, height=32, corner_radius=8,
            fg_color="transparent", hover_color=COR_SECUNDARIA,
            border_width=1, border_color=COR_BORDA, text_color=COR_SUBTEXTO,
            font=ctk.CTkFont("Segoe UI", 12), command=self._esvaziar_arquivos
        ).pack(side="left")

        # Lista rolável moderna de arquivos
        self.scroll_arquivos = ctk.CTkScrollableFrame(
            f, height=140, corner_radius=12,
            fg_color=COR_CARD_INTERNO, border_width=1, border_color=COR_BORDA_FORTE
        )
        self.scroll_arquivos.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        self.scroll_arquivos.grid_columnconfigure(0, weight=1)
        self._atualizar_lista_visual()

        # Opção substituir
        linha_op = ctk.CTkFrame(
            f, fg_color=COR_CARD_INTERNO, corner_radius=10,
            border_width=1, border_color=COR_BORDA
        )
        linha_op.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        ctk.CTkSwitch(
            linha_op,
            text="  Substituir arquivos originais (desmarcado = salva ao lado como NOME_limpo.mp4)",
            variable=self.var_substituir,
            progress_color=COR_PRIMARIA,
            button_color="#FFFFFF",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=COR_TEXTO,
        ).pack(side="left", padx=14, pady=10)

        self.btn_limpar = ctk.CTkButton(
            f, text="🛡️   Remover Metadados dos Vídeos Selecionados",
            height=46, corner_radius=12,
            fg_color=COR_PRIMARIA, hover_color=COR_PRIMARIA_HOVER,
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
            text_color="#FFFFFF", command=self._iniciar_limpeza
        )
        self.btn_limpar.grid(row=3, column=0, sticky="ew")
        return f

    def _construir_painel_progresso(self):
        painel = ctk.CTkFrame(
            self, fg_color=COR_CARD, corner_radius=16,
            border_width=1, border_color=COR_BORDA
        )
        painel.grid(row=3, column=0, sticky="nsew", padx=24, pady=(0, 20))
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_rowconfigure(2, weight=1)

        # Cabeçalho do console e status
        topo = ctk.CTkFrame(painel, fg_color="transparent")
        topo.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 6))
        topo.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            topo, textvariable=self.var_status,
            font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=COR_TEXTO
        ).grid(row=0, column=0, sticky="w")

        direita = ctk.CTkFrame(topo, fg_color="transparent")
        direita.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(
            direita, textvariable=self.var_pct,
            font=ctk.CTkFont("Consolas", 12, "bold"), text_color="#A5B4FC"
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            direita, text="Limpar log", width=76, height=24, corner_radius=6,
            fg_color="transparent", hover_color=COR_SECUNDARIA,
            border_width=1, border_color=COR_BORDA,
            text_color=COR_MUTED, font=ctk.CTkFont("Segoe UI", 11),
            command=self._limpar_log
        ).pack(side="left")

        # Barra de progresso
        self.barra = ctk.CTkProgressBar(
            painel, height=10, corner_radius=5,
            fg_color=COR_CARD_INTERNO, progress_color=COR_PRIMARIA
        )
        self.barra.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        self.barra.set(0)

        # Console de eventos com cores por tipo de mensagem
        self.log = ctk.CTkTextbox(
            painel, corner_radius=10,
            fg_color=COR_CARD_INTERNO, border_width=1, border_color=COR_BORDA,
            text_color=COR_SUBTEXTO, font=ctk.CTkFont("Consolas", 11),
            wrap="word", state="disabled"
        )
        self.log.grid(row=2, column=0, sticky="nsew", padx=18, pady=(0, 14))
        tb = self.log._textbox
        tb.tag_config("titulo", foreground="#A5B4FC")
        tb.tag_config("sucesso", foreground="#34D399")
        tb.tag_config("aviso", foreground="#FBBF24")
        tb.tag_config("erro", foreground="#F87171")
        tb.tag_config("info", foreground=COR_SUBTEXTO)

    # ---------- placeholder de URLs ----------
    def _mostrar_placeholder(self):
        self.txt_urls.delete("1.0", "end")
        self.txt_urls.insert("1.0", PLACEHOLDER_URLS)
        self.txt_urls.configure(text_color=COR_MUTED)
        self._placeholder_ativo = True

    def _ao_focar_urls(self, _event=None):
        if self._placeholder_ativo:
            self.txt_urls.delete("1.0", "end")
            self.txt_urls.configure(text_color=COR_TEXTO)
            self._placeholder_ativo = False

    def _ao_desfocar_urls(self, _event=None):
        if not self.txt_urls.get("1.0", "end").strip():
            self._mostrar_placeholder()

    def _obter_urls(self) -> list[str]:
        if self._placeholder_ativo:
            return []
        return [u.strip() for u in self.txt_urls.get("1.0", "end").splitlines() if u.strip()]

    def _limpar_campo_urls(self):
        self.txt_urls.delete("1.0", "end")
        if self.focus_get() != self.txt_urls._textbox:
            self._mostrar_placeholder()

    # ---------- gerenciamento da lista de vídeos ----------
    def _atualizar_lista_visual(self):
        for w in self.scroll_arquivos.winfo_children():
            w.destroy()

        if not self.arquivos_limpeza:
            vazio = ctk.CTkFrame(self.scroll_arquivos, fg_color="transparent")
            vazio.grid(row=0, column=0, pady=34)
            ctk.CTkLabel(
                vazio, text="Nenhum vídeo selecionado",
                font=ctk.CTkFont("Segoe UI", 13, "bold"), text_color=COR_SUBTEXTO
            ).pack()
            ctk.CTkLabel(
                vazio, text="Clique em '+ Adicionar vídeos...' para escolher arquivos MP4, MOV, MKV ou WebM",
                font=ctk.CTkFont("Segoe UI", 11), text_color=COR_MUTED
            ).pack(pady=(2, 0))
            return

        for idx, arq in enumerate(self.arquivos_limpeza):
            item = ctk.CTkFrame(
                self.scroll_arquivos, fg_color=COR_CARD, corner_radius=8,
                border_width=1, border_color=COR_BORDA
            )
            item.grid(row=idx, column=0, sticky="ew", pady=3, padx=2)
            item.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(
                item, text="🎬", font=ctk.CTkFont("Segoe UI", 14)
            ).grid(row=0, column=0, padx=(10, 6), pady=6)

            p = Path(arq)
            ctk.CTkLabel(
                item, text=p.name, anchor="w",
                font=ctk.CTkFont("Segoe UI", 12, "bold"), text_color=COR_TEXTO
            ).grid(row=0, column=1, sticky="ew", pady=6)

            tam = _formatar_tamanho(arq)
            if tam:
                ctk.CTkLabel(
                    item, text=tam,
                    font=ctk.CTkFont("Consolas", 11), text_color=COR_MUTED
                ).grid(row=0, column=2, padx=8, pady=6)

            ctk.CTkButton(
                item, text="✕", width=26, height=24, corner_radius=6,
                fg_color="transparent", hover_color="#3F1D24",
                text_color=COR_SUBTEXTO, font=ctk.CTkFont("Segoe UI", 11, "bold"),
                command=lambda a=arq: self._remover_arquivo(a)
            ).grid(row=0, column=3, padx=(0, 8), pady=6)

    def _remover_arquivo(self, arq: str):
        if arq in self.arquivos_limpeza:
            self.arquivos_limpeza.remove(arq)
            self._atualizar_lista_visual()

    def _esvaziar_arquivos(self):
        self.arquivos_limpeza.clear()
        self._atualizar_lista_visual()

    # ---------- ações ----------
    def _colar(self):
        try:
            texto = self.clipboard_get().strip()
        except tk.TclError:
            return
        if texto:
            if self._placeholder_ativo:
                self.txt_urls.delete("1.0", "end")
                self.txt_urls.configure(text_color=COR_TEXTO)
                self._placeholder_ativo = False
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
        alterou = False
        for a in arquivos:
            if a not in self.arquivos_limpeza:
                self.arquivos_limpeza.append(a)
                alterou = True
        if alterou:
            self._atualizar_lista_visual()

    def _limpar_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _iniciar_download(self):
        urls = self._obter_urls()
        if not urls:
            messagebox.showinfo(TITULO, "Cole pelo menos uma URL de vídeo.")
            return
        self._comecar(self._trabalho_download, urls, self.var_pasta.get(), self.var_limpar.get())

    def _iniciar_limpeza(self):
        if not self.arquivos_limpeza:
            messagebox.showinfo(TITULO, "Adicione pelo menos um vídeo na lista.")
            return
        self._comecar(self._trabalho_limpeza, list(self.arquivos_limpeza), self.var_substituir.get())

    def _comecar(self, alvo, *args):
        if self.ocupado:
            return
        self.ocupado = True
        self.btn_baixar.configure(state="disabled")
        self.btn_limpar.configure(state="disabled")
        self.lbl_ponto_status.configure(text_color=COR_AVISO)
        self.lbl_texto_pilula.configure(text="Processando...")
        self.barra.set(0)
        self.var_pct.set("0%")
        threading.Thread(target=alvo, args=args, daemon=True).start()

    # ---------- trabalho em segundo plano ----------
    def _trabalho_download(self, urls, pasta, limpar):
        ok = 0
        for i, url in enumerate(urls, 1):
            prefixo = f"[{i}/{len(urls)}]"
            self.fila.put(("status", f"{prefixo} Conectando e analisando formatos..."))
            self.fila.put(("log", ("titulo", f"━━━ {prefixo} {url}")))

            def progresso(d, prefixo=prefixo):
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    faixa = "áudio" if d.get("info_dict", {}).get("vcodec") == "none" else "vídeo"
                    vel = (d.get("_speed_str") or "").strip()
                    if total:
                        self.fila.put(("prog", d.get("downloaded_bytes", 0) / total * 100))
                    self.fila.put(("status", f"{prefixo} Baixando melhor faixa de {faixa}... {vel}"))
                elif d["status"] == "finished":
                    self.fila.put(("prog", 100))
                    self.fila.put(("status", f"{prefixo} Mesclando vídeo + áudio sem perda..."))

            try:
                caminho = baixar(url, pasta, limpar=limpar, progresso=progresso, logger=_LogYtDlp(self.fila))
                extra = " · metadados removidos" if limpar else ""
                self.fila.put(("log", ("sucesso", f"✔ Concluído{extra}: {caminho}")))
                ok += 1
            except Exception as e:
                self.fila.put(("log", ("erro", f"✖ Falhou: {e}")))
        self.fila.put(("fim", (ok == len(urls), f"Finalizado: {ok} de {len(urls)} vídeo(s) salvo(s) com sucesso.")))

    def _trabalho_limpeza(self, arquivos, substituir):
        ok = 0
        for i, arq in enumerate(arquivos, 1):
            nome = Path(arq).name
            self.fila.put(("status", f"[{i}/{len(arquivos)}] Limpando metadados de {nome}..."))
            try:
                destino = limpar_metadados(arq, substituir=substituir)
                self.fila.put(("log", ("sucesso", f"✔ Metadados removidos: {destino}")))
                ok += 1
            except Exception as e:
                self.fila.put(("log", ("erro", f"✖ Falhou em {nome}: {e}")))
            self.fila.put(("prog", i / len(arquivos) * 100))
        self.fila.put(("fim", (ok == len(arquivos), f"Finalizado: {ok} de {len(arquivos)} vídeo(s) limpo(s).")))

    # ---------- fila de eventos ----------
    def _escrever(self, item):
        tag, texto = item if isinstance(item, tuple) else ("info", str(item))
        self.log.configure(state="normal")
        self.log._textbox.insert("end", texto + "\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _processar_fila(self):
        try:
            while True:
                tipo, valor = self.fila.get_nowait()
                if tipo == "log":
                    self._escrever(valor)
                elif tipo == "prog":
                    pct = max(0.0, min(100.0, float(valor)))
                    self.barra.set(pct / 100.0)
                    self.var_pct.set(f"{int(pct)}%")
                elif tipo == "status":
                    self.var_status.set(valor)
                elif tipo == "fim":
                    sucesso_total, msg = valor
                    self.ocupado = False
                    self.btn_baixar.configure(state="normal")
                    self.btn_limpar.configure(state="normal")
                    self.lbl_ponto_status.configure(text_color=COR_SUCESSO if sucesso_total else COR_AVISO)
                    self.lbl_texto_pilula.configure(text="Online · Zero-Loss")
                    self.barra.set(1.0 if sucesso_total else 0.0)
                    self.var_pct.set("100%" if sucesso_total else "0%")
                    self.var_status.set(msg)
                    self._escrever(("sucesso" if sucesso_total else "aviso", msg))
        except queue.Empty:
            pass
        self.after(80, self._processar_fila)

    def _fechar(self):
        if self.ocupado and not messagebox.askyesno(TITULO, "Há uma tarefa em andamento. Deseja fechar mesmo assim?"):
            return
        _salvar_config({
            "pasta": self.var_pasta.get(),
            "limpar": self.var_limpar.get(),
            "substituir": self.var_substituir.get(),
        })
        self.destroy()


def main():
    ctk.set_appearance_mode("dark")
    App().mainloop()


if __name__ == "__main__":
    main()
