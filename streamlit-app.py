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

DATA_PATH = "dados"  # pasta com GeoJSON/CSV
ICON_REPO = f"{DATA_PATH}/Lista_Final_Emojis/"

st.set_page_config(page_title="Mapas Emocionais – Mobilidade Urbana", layout="wide", page_icon="🗺️")

# ────────────────────────── CARREGAMENTO DE DADOS ──────────────────────────
@st.cache_data(show_spinner="Lendo camadas …")
def load_data():
    files = {
        "emoji": "emoji_emoc.csv",
        "modais": "modais.csv",
        "cenarios": "cenarios.geojson",
        "participantes": "participantes.csv",
        "emoc": "emocoes_coletadas.geojson",
        "pts_cenarios": "pts_cenarios.geojson",
        "ways": "ways.geojson",
    }
    gdfs = {}
    for k, f in files.items():
        p = f"{DATA_PATH}/{f}"
        if f.endswith(".csv"):
            gdfs[k] = pd.read_csv(p)
        else:
            g = gpd.read_file(p)
            if not g.crs or g.crs.to_epsg() != 4326:
                g = g.to_crs(4326)
            gdfs[k] = g
    return gdfs

DATA = load_data()
DATA.update(build_layers({
    "ways": DATA["ways"],
    "emoc": DATA["emoc"],
    "emoji": DATA["emoji"],
}))

# ────────────────────────── LISTAS AUXILIARES ──────────────────────────

def lista_emoc():
    return [""] + sorted(DATA["emoji"].emocao.unique())

def lista_valencia():
    return [""] + sorted(DATA["emoji"].valencia.unique())

def lista_mdl():
    return [""] + sorted(DATA["modais"].nome.unique())

def lista_cenarios():
    return [""] + sorted(DATA["cenarios"].referencia.unique())

def lista_genero():
    return [""] + sorted(DATA["participantes"].genero.dropna().unique())

def lista_faixa():
    return [""] + sorted(DATA["participantes"].faixa_etaria.dropna().unique())

def lista_val_vias():
    return [""] + sorted(DATA["emoc_ways_vlc_rua"].vlc_maior_text.dropna().unique())

# ────────────────────────── INTERFACE ──────────────────────────

def page_explorar():
    st.header("Explorar Mapas")
    view = st.selectbox(
        "Visualização", (
            "Emoção individual",
            "Modal + Valência",
            "Cenário",
            "Valência nas vias",
        ), key="view_exp")

    m = make_base_map(DATA)

    if view == "Emoção individual":
        e = st.selectbox("Emoção", lista_emoc(), key="emo_sel")
        if e:
            emoc_indiv(DATA, e, m, ICON_REPO)

    elif view == "Modal + Valência":
        mdl = st.selectbox("Modal", lista_mdl(), key="mdl_sel")
        val = st.multiselect("Valências", lista_valencia(), key="val_modal")
        emoc_modal(DATA, mdl, val, m, ICON_REPO)

    elif view == "Cenário":
        c = st.selectbox("Cenário", lista_cenarios(), key="cnr_sel")
        if c:
            emoc_cenario(DATA, c, m, ICON_REPO)

    else:  # Valência nas vias
        vlc = st.multiselect("Valências", lista_val_vias(), key="val_via")
        if vlc:
            vias_valencia(DATA, vlc, m)

    st_folium(m, use_container_width=True, height=700)


def page_consultas():
    st.header("Realizar Consultas")
    tab_pt, tab_ln = st.tabs(["Por Pontos", "Por Linhas"])

    with tab_pt:
        col1, col2 = st.columns(2)
        with col1:
            faixa = st.selectbox("Faixa etária", lista_faixa(), key="faixa_q")
            val = st.multiselect("Valências", lista_valencia(), key="val_pt1")
            if st.button("Filtrar pontos", key="btn_pt1") and faixa:
                m = make_base_map(DATA)
                emoc_faixa(DATA, faixa, val, m, ICON_REPO)
                st_folium(m, use_container_width=True, height=600)
        with col2:
            gen = st.selectbox("Gênero", lista_genero(), key="gen_q")
            val2 = st.multiselect("Valências", lista_valencia(), key="val_pt2")
            if st.button("Filtrar por gênero", key="btn_pt2") and gen:
                m = make_base_map(DATA)
                emoc_genero(DATA, gen, val2, m, ICON_REPO)
                st_folium(m, use_container_width=True, height=600)

    with tab_ln:
        vlc = st.multiselect("Valência das vias", lista_val_vias(), key="val_ln")
        if st.button("Filtrar vias", key="btn_ln") and vlc:
            m = make_base_map(DATA)
            vias_valencia(DATA, vlc, m)
            st_folium(m, use_container_width=True, height=600)


def page_nav():
    st.header("Navegação – rotas sugeridas")
    st.info("Funcionalidade em desenvolvimento.")


def page_sobre():
    st.header("Sobre o Projeto")
    st.markdown(
        """
        **Mapas Emocionais no Contexto da Mobilidade Urbana** investiga a percepção
        emocional de diferentes públicos em trajetos urbanos.

        Dados coletados via questionário, integrados ao OpenStreetMap.
        """
    )

# ────────────────────────── MENU LATERAL ──────────────────────────

st.sidebar.markdown("## 🗺️ Mapas Emocionais\n### Mobilidade Urbana")
choice = st.sidebar.radio("Menu", ["Explorar Mapas", "Realizar Consultas", "Sobre"], index=0)

if choice == "Explorar Mapas":
    page_explorar()
# ───────── Página: Realizar Consultas ─────────
elif choice == "Realizar Consultas":
    st.header("Realizar Consultas")
    tab_pt, tab_ln = st.tabs(["Por Pontos", "Por Linhas"])

    # ---------- POR PONTOS ----------
    with tab_pt:
        col1, col2 = st.columns(2)

        # --- Faixa etária ---
        with col1:
            faixa = st.selectbox("Faixa etária", lista_faixa(),
                                 key="faixa_q")
            val = st.multiselect("Valências", lista_valencia(),
                                 key="val_pt1")

            # botão dentro de um form evita múltiplos reruns
            with st.form(key="form_faixa"):
                submit_faixa = st.form_submit_button("Filtrar pontos")

            if submit_faixa:
                st.session_state["faixa_result"] = (faixa, val)

            if "faixa_result" in st.session_state:
                faixa_sel, val_sel = st.session_state["faixa_result"]
                m = make_base_map(DATA)
                emoc_faixa(DATA, faixa_sel, val_sel, m, ICON_REPO)
                st_folium(m, height=600, use_container_width=True)

        # --- Gênero ---
        with col2:
            gen = st.selectbox("Gênero", lista_genero(),
                               key="gen_q")
            val2 = st.multiselect("Valências", lista_valencia(),
                                  key="val_pt2")

            with st.form(key="form_genero"):
                submit_gen = st.form_submit_button("Filtrar por gênero")

            if submit_gen:
                st.session_state["gen_result"] = (gen, val2)

            if "gen_result" in st.session_state:
                gen_sel, val2_sel = st.session_state["gen_result"]
                m = make_base_map(DATA)
                emoc_genero(DATA, gen_sel, val2_sel, m, ICON_REPO)
                st_folium(m, height=600, use_container_width=True)

    # ---------- POR LINHAS ----------
    with tab_ln:
        vlc = st.multiselect("Valência das vias", lista_val_vias(),
                             key="val_ln")
        if st.button("Filtrar vias", key="btn_ln"):
            st.session_state["vias_result"] = vlc

        if "vias_result" in st.session_state:
            vlc_sel = st.session_state["vias_result"]
            m = make_base_map(DATA)
            vias_valencia(DATA, vlc_sel, m)
            st_folium(m, height=600)

else:
    page_sobre()
