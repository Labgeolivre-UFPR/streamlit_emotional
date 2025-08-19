# streamlit-app.py
import streamlit as st
import geopandas as gpd
import pandas as pd
from streamlit_folium import st_folium

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
from i18n import t

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
def page_explorar():
    st.header(t("ui.explore_maps", lang))
    view = st.selectbox(
        t("ui.visualization", lang),
        (
            t("ui.views.emotion_single", lang),
            t("ui.views.modal_valence", lang),
            t("ui.views.scenario", lang),
            t("ui.views.valence_on_roads", lang),
        ),
        key="view_exp",
    )

    m = make_base_map(DATA, lang=lang)

    if view == t("ui.views.emotion_single", lang):
        e = st.selectbox(t("ui.select.emotion", lang), lista_emoc(), key="emo_sel")
        if e:
            emoc_indiv(DATA, e, m, ICON_REPO, lang=lang)

    elif view == t("ui.views.modal_valence", lang):
        mdl = st.selectbox(t("ui.select.modal", lang), lista_mdl(), key="mdl_sel")
        choices = valence_choices(lang)
        val = st.multiselect(
            t("ui.select.valences", lang),
            options=[c for c, _ in choices],
            format_func=lambda code: dict(choices)[code],
            key="val_modal",
        )
        emoc_modal(DATA, mdl, val, m, ICON_REPO, lang=lang)

    elif view == t("ui.views.scenario", lang):
        c = st.selectbox(t("ui.select.scenario", lang), lista_cenarios(), key="cnr_sel")
        if c:
            emoc_cenario(DATA, c, m, ICON_REPO, lang=lang)

    else:  # Valência nas vias
        road_codes = lista_val_vias_codes()
        choices = valence_choices(lang)
        code2label = dict(choices)
        vlc = st.multiselect(
            t("ui.select.valences_roads", lang),
            options=road_codes,
            format_func=lambda code: code2label.get(code, code),
            key="val_via",
        )
        if vlc:
            vias_valencia(DATA, vlc, m, lang=lang)

    st_folium(m, use_container_width=True, height=700)

def page_consultas():
    st.header(t("ui.perform_queries", lang))
    tab_pt, tab_ln = st.tabs([t("ui.tabs.points", lang), t("ui.tabs.lines", lang)])

    # ---------- POR PONTOS ----------
    with tab_pt:
        col1, col2 = st.columns(2)

        # Faixa etária
        with col1:
            faixa = st.selectbox(t("ui.select.age_range", lang), lista_faixa(), key="faixa_q")
            choices = valence_choices(lang)
            val = st.multiselect(
                t("ui.select.valences", lang),
                options=[c for c, _ in choices],
                format_func=lambda code: dict(choices)[code],
                key="val_pt1",
            )
            if st.button(t("ui.buttons.filter_points", lang), key="btn_pt1") and faixa:
                m = make_base_map(DATA, lang=lang)
                emoc_faixa(DATA, faixa, val, m, ICON_REPO, lang=lang)
                st_folium(m, use_container_width=True, height=600)

        # Gênero
        with col2:
            gen = st.selectbox(t("ui.select.gender", lang), lista_genero(), key="gen_q")
            choices2 = valence_choices(lang)
            val2 = st.multiselect(
                t("ui.select.valences", lang),
                options=[c for c, _ in choices2],
                format_func=lambda code: dict(choices2)[code],
                key="val_pt2",
            )
            if st.button(t("ui.buttons.filter_gender", lang), key="btn_pt2") and gen:
                m = make_base_map(DATA, lang=lang)
                emoc_genero(DATA, gen, val2, m, ICON_REPO, lang=lang)
                st_folium(m, use_container_width=True, height=600)

    # ---------- POR LINHAS ----------
    with tab_ln:
        road_codes = lista_val_vias_codes()
        choices = valence_choices(lang)
        code2label = dict(choices)
        vlc = st.multiselect(
            t("ui.select.valences_roads", lang),
            options=road_codes,
            format_func=lambda code: code2label.get(code, code),
            key="val_ln",
        )
        if st.button(t("ui.buttons.filter_roads", lang), key="btn_ln") and vlc:
            m = make_base_map(DATA, lang=lang)
            vias_valencia(DATA, vlc, m, lang=lang)
            st_folium(m, use_container_width=True, height=600)

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
