"""Interface web: baixar vídeos na melhor qualidade possível.

Rodar localmente:  streamlit run app.py
"""
from pathlib import Path

import streamlit as st

from baixador import baixar

st.set_page_config(page_title="Baixador de Vídeos", page_icon="⬇️")
st.title("⬇️ Baixador de Vídeos")
st.caption("TikTok, Reels, Shorts e outras plataformas — sempre na melhor qualidade disponível.")

url = st.text_input("URL do vídeo", placeholder="https://www.tiktok.com/@usuario/video/123...")

if st.button("Baixar", type="primary", disabled=not url.strip()):
    with st.spinner("Baixando na melhor qualidade disponível..."):
        try:
            st.session_state["baixado"] = str(baixar(url.strip()))
        except Exception as e:
            st.error(f"Não foi possível baixar: {e}")

caminho = st.session_state.get("baixado")
if caminho and Path(caminho).exists():
    p = Path(caminho)
    st.success(f"Salvo em `{p}`")
    st.video(str(p))
    st.download_button(
        "Salvar MP4 no meu computador",
        p.read_bytes(),
        file_name=p.name,
        mime="video/mp4",
    )
