# streamlit-app.py
import streamlit as st
import geopandas as gpd
import pandas as pd
from streamlit_folium import st_folium
import folium

from build_layers import build_layers
from map_functions import (
    make_base_map,
    emoc_indiv,
    emoc_modal,
    emoc_cenario,
    emoc_faixa,
    emoc_genero,
    vias_valencia,
)
from i18n import t, reload_locales, available_languages  # <— adicione reload_locales
reload_locales()  # limpa o cache do i18n

# ⚠️ PRIMEIRO comando Streamlit do arquivo (evita o aviso):
st.set_page_config(page_title="Emotional Maps", layout="wide", page_icon="🗺️")

# ────────────────────────── IDIOMA ──────────────────────────
# Streamlit 1.32+: st.query_params
params = st.query_params
if "lang" not in st.session_state:
    st.session_state.lang = params.get("lang", "pt")
lang = st.session_state.lang

# Seletor de idioma (sidebar)
with st.sidebar:
    st.markdown("### 🌐")
    choice = st.radio(
        label="",
        options=[("pt", "🇧🇷 Português"), ("en", "🇬🇧 English")],
        index=0 if lang == "pt" else 1,
        horizontal=True,
        format_func=lambda x: x[1],
        key="lang_radio",
    )
    if choice[0] != lang:
        st.session_state.lang = choice[0]
        st.query_params["lang"] = choice[0]  # atualiza URL
        st.rerun()
lang = st.session_state.lang

# ────────────────────────── CAMINHOS ──────────────────────────
DATA_PATH = "dados"
ICON_REPO = f"{DATA_PATH}/Lista_Final_Emojis/"

# ────────────────────────── DADOS ──────────────────────────
@st.cache_data(show_spinner=False)
def load_data(data_path: str) -> dict:
    from contextlib import contextmanager
    @contextmanager
    def spinner(msg: str):
        with st.spinner(msg):
            yield

    files = {
        "emoji": "emoji_emoc.csv",
        "modais": "modais.csv",
        "cenarios": "cenarios.geojson",
        "participantes": "participantes.csv",
        "emoc": "emocoes_coletadas.geojson",
        "pts_cenarios": "pts_cenarios.geojson",
        "ways": "ways.geojson",
    }

    with spinner(t("loading.data", lang)):
        gdfs = {}
        for k, f in files.items():
            p = f"{data_path}/{f}"
            if f.endswith(".csv"):
                gdfs[k] = pd.read_csv(p)
            else:
                g = gpd.read_file(p)
                if not g.crs or g.crs.to_epsg() != 4326:
                    g = g.to_crs(4326)
                gdfs[k] = g
        return gdfs

DATA = load_data(DATA_PATH)
DATA.update(build_layers({"ways": DATA["ways"], "emoc": DATA["emoc"], "emoji": DATA["emoji"]}))

# ────────────────────────── LISTAS / OPÇÕES (i18n) ──────────────────────────
def lista_emoc():
    # nomes de emoções vêm do CSV; mantemos como estão
    return [""] + sorted(DATA["emoji"].emocao.unique())

def valence_choices(lang: str):
    """Retorna lista de tuplas (code, label traduzido)."""
    codes = ["neg", "neu", "pos"]
    labels = {
        "neg": t("metrics.valence.negative", lang),
        "neu": t("metrics.valence.neutral", lang),
        "pos": t("metrics.valence.positive", lang),
    }
    return [(c, labels[c]) for c in codes]

def lista_mdl():
    return [""] + sorted(DATA["modais"].nome.unique())

def lista_cenarios():
    return [""] + sorted(DATA["cenarios"].referencia.unique())

def lista_genero():
    return [""] + sorted(DATA["participantes"].genero.dropna().unique())

def lista_faixa():
    return [""] + sorted(DATA["participantes"].faixa_etaria.dropna().unique())

def lista_val_vias_codes():
    """Obtém códigos de valência das vias a partir de build_layers (fallback do texto PT)."""
    df = DATA.get("emoc_ways_vlc_rua")
    if df is None or df.empty:
        return []
    if "vlc_maior_code" in df.columns:
        vals = df["vlc_maior_code"].dropna().unique().tolist()
    else:
        # fallback PT -> code
        mapping = {"Negativo": "neg", "Neutro": "neu", "Positivo": "pos"}
        vals = df["vlc_maior_text"].map(mapping).dropna().unique().tolist()
    # ordenar por a ordem lógica neg, neu, pos
    order = {"neg": 0, "neu": 1, "pos": 2}
    return sorted(vals, key=lambda x: order.get(x, 99))

# ────────────────────────── PÁGINAS ──────────────────────────
# streamlit-app.py (versão corrigida e mais robusta)

def page_explorar():
    st.header(t("ui.explore_maps", lang))

    # 1. Defina chaves estáveis (em inglês, por convenção) para cada visualização.
    view_options = {
        "emotion_single": t("ui.views.emotion_single", lang),
        "modal_valence": t("ui.views.modal_valence", lang),
        "scenario": t("ui.views.scenario", lang),
        "valence_on_roads": t("ui.views.valence_on_roads", lang),
    }

    # 2. Use as CHAVES como opções e `format_func` para mostrar os valores traduzidos.
    # O selectbox agora retornará a chave estável (ex: "emotion_single").
    view_key = st.selectbox(
        t("ui.visualization", lang),
        options=list(view_options.keys()),
        format_func=lambda key: view_options[key], # Mostra o texto traduzido
        key="view_exp",
    )

    m = make_base_map(DATA, lang=lang, tiles="OpenStreetMap")

    # 3. Use as chaves estáveis e não traduzidas para a lógica do if/elif.
    if view_key == "emotion_single":
        e = st.selectbox(t("ui.select.emotion", lang), lista_emoc(), key="emo_sel")
        if e:
            emoc_indiv(DATA, e, m, ICON_REPO, lang=lang)

    elif view_key == "modal_valence":
        mdl = st.selectbox(t("ui.select.modal", lang), lista_mdl(), key="mdl_sel")
        choices = valence_choices(lang)
        val = st.multiselect(
            t("ui.select.valences", lang),
            options=[c for c, _ in choices],
            format_func=lambda code: dict(choices)[code],
            key="val_modal",
        )
        emoc_modal(DATA, mdl, val, m, ICON_REPO, lang=lang)

    elif view_key == "scenario":
        c = st.selectbox(t("ui.select.scenario", lang), lista_cenarios(), key="cnr_sel")
        if c:
            emoc_cenario(DATA, c, m, ICON_REPO, lang=lang)

    elif view_key == "valence_on_roads":  # É mais explícito que usar 'else'
        road_codes = lista_val_vias_codes()
        choices = valence_choices(lang)
        code2label = dict(choices)
        vlc = st.multiselect(
            t("ui.select.valences_roads", lang),
            options=road_codes,
            format_func=lambda code: code2label.get(code, code),
            key="val_via",
        )
        # O original não filtrava se a seleção estivesse vazia, adicionei o 'if'
        if vlc:
            vias_valencia(DATA, vlc, m, lang=lang)
        # Se quiser mostrar todas as vias quando nada for selecionado, remova o 'if'
    folium.LayerControl(collapsed=False).add_to(m)
    st_folium(m, key="explore_map", use_container_width=True, height=700)

# streamlit-app.py (substitua a função inteira)

def page_consultas():
    st.header(t("ui.perform_queries", lang))

    # Inicializa a variável de estado se ela não existir
    if 'consulta_ativa' not in st.session_state:
        st.session_state.consulta_ativa = None

    tab_pt, tab_ln = st.tabs([t("ui.tabs.points", lang), t("ui.tabs.lines", lang)])

    # ---------- POR PONTOS ----------
    with tab_pt:
        col1, col2 = st.columns(2)

        # Faixa etária
        with col1:
            st.subheader(t("ui.select.age_range", lang))
            faixa = st.selectbox("", lista_faixa(), key="faixa_q")
            choices = valence_choices(lang)
            val = st.multiselect(
                t("ui.select.valences", lang),
                options=[c for c, _ in choices],
                format_func=lambda code: dict(choices)[code],
                key="val_pt1",
            )
            
            b1, b2 = st.columns(2)
            if b1.button(t("ui.buttons.filter_points", lang), key="btn_pt1", use_container_width=True):
                if faixa:
                    # Salva os parâmetros da consulta no estado
                    st.session_state.consulta_ativa = {"tipo": "faixa", "faixa": faixa, "val": val}
                else:
                    st.warning("Por favor, selecione uma faixa etária.")

            if b2.button("Limpar", key="clear_pt1", use_container_width=True):
                st.session_state.consulta_ativa = None
                st.rerun() # Força a re-execução para limpar o mapa

        # Gênero
        with col2:
            st.subheader(t("ui.select.gender", lang))
            gen = st.selectbox("", lista_genero(), key="gen_q")
            choices2 = valence_choices(lang)
            val2 = st.multiselect(
                t("ui.select.valences", lang),
                options=[c for c, _ in choices2],
                format_func=lambda code: dict(choices2)[code],
                key="val_pt2",
            )

            b3, b4 = st.columns(2)
            if b3.button(t("ui.buttons.filter_gender", lang), key="btn_pt2", use_container_width=True):
                if gen:
                    # Salva os parâmetros da consulta no estado
                    st.session_state.consulta_ativa = {"tipo": "genero", "gen": gen, "val2": val2}
                else:
                    st.warning("Por favor, selecione um gênero.")

            if b4.button("Limpar", key="clear_pt2", use_container_width=True):
                st.session_state.consulta_ativa = None
                st.rerun()

    # ---------- POR LINHAS ----------
    with tab_ln:
        road_codes = lista_val_vias_codes()
        choices_ln = valence_choices(lang)
        code2label_ln = dict(choices_ln)
        vlc = st.multiselect(
            t("ui.select.valences_roads", lang),
            options=road_codes,
            format_func=lambda code: code2label_ln.get(code, code),
            key="val_ln",
        )
        b5, b6 = st.columns([3,1]) # Botão de filtrar maior
        if b5.button(t("ui.buttons.filter_roads", lang), key="btn_ln", use_container_width=True):
            if vlc:
                # Salva os parâmetros da consulta no estado
                st.session_state.consulta_ativa = {"tipo": "vias", "vlc": vlc}
            else:
                st.warning("Por favor, selecione ao menos uma valência.")

        if b6.button("Limpar", key="clear_ln", use_container_width=True):
            st.session_state.consulta_ativa = None
            st.rerun()

    # --- LÓGICA DE EXIBIÇÃO DO MAPA ---
    # Fica fora das abas e colunas, e verifica o estado da sessão
    if st.session_state.consulta_ativa:
        st.divider()
        m = make_base_map(DATA, lang=lang)
        
        consulta = st.session_state.consulta_ativa
        if consulta["tipo"] == "faixa":
            emoc_faixa(DATA, consulta["faixa"], consulta["val"], m, ICON_REPO, lang=lang)
        elif consulta["tipo"] == "genero":
            emoc_genero(DATA, consulta["gen"], consulta["val2"], m, ICON_REPO, lang=lang)
        elif consulta["tipo"] == "vias":
            vias_valencia(DATA, consulta["vlc"], m, lang=lang)

        folium.LayerControl(collapsed=False).add_to(m)
        # Uma única chamada st_folium com uma key fixa
        st_folium(m, key="query_map", use_container_width=True, height=600)
def page_sobre():
    st.header(t("ui.about", lang))
    st.markdown(t("about.body_md", lang))

# (placeholder para futuras rotas)
def page_nav():
    st.header(t("ui.navigation.header", lang))
    st.info(t("ui.navigation.wip", lang))

# ────────────────────────── MENU LATERAL ──────────────────────────
st.sidebar.markdown(f"## 🗺️ {t('app.title', lang)}\n### {t('app.subtitle', lang)}")
menu_options = {
    t("ui.explore_maps", lang): page_explorar,
    t("ui.perform_queries", lang): page_consultas,
    t("ui.about", lang): page_sobre,
}
choice = st.sidebar.radio(t("ui.sidebar.menu", lang), list(menu_options.keys()), index=0)
menu_options[choice]()
