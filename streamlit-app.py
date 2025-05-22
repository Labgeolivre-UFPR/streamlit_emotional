import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from folium import plugins
from streamlit_folium import folium_static

# ────────────────────────────────────────────────────────────────
# Configurações gerais
# ────────────────────────────────────────────────────────────────
DATA_PATH = "dados"  # pasta onde ficam os .geojson / .gpkg
ICON_REPO = (
    "https://raw.githubusercontent.com/GabrieleCamara/"
    "Streamlit-EmotionalMaps/main/Lista_Final_Emojis/"
)

st.set_page_config(
    page_title="Emotional Maps – GeoPandas Edition",
    layout="wide",
    page_icon="🗺️",
)

# ────────────────────────────────────────────────────────────────
# Carregamento de dados (cacheado)
# ────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner="Carregando camadas GeoJSON …")
def load_data():
    """Lê todos os GeoJSON necessários e garante CRS WGS‑84."""
    files = {
        "emoji": "emoji_emoc.geojson",
        "modais": "modais.geojson",
        "cenarios": "cenarios.geojson",
        "participantes": "participantes.geojson",
        "emoc": "emocoes_coletadas.geojson",
        "pts_cenarios": "pts_cenarios.geojson",
        "vias": "emoc_ways_vlc_rua.geojson",
    }

    gdfs = {}
    for key, fname in files.items():
        try:
            gdf = gpd.read_file(f"{DATA_PATH}/{fname}")
            if not gdf.crs or gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(4326)
            gdfs[key] = gdf
        except Exception as e:
            st.warning(f"⚠️ Não foi possível ler {fname}: {e}")
    return gdfs

DATA = load_data()

# ────────────────────────────────────────────────────────────────
# Funções auxiliares – listas de seleção
# ────────────────────────────────────────────────────────────────

def lista_emoc():
    return [""] + sorted(DATA["emoji"]["emocao"].unique())

def lista_valencia():
    return [""] + sorted(DATA["emoji"]["valencia"].unique())

def lista_mdl():
    return [""] + sorted(DATA["modais"]["nome"].unique())

def lista_cenarios():
    return [""] + sorted(DATA["cenarios"]["nome"].unique())

def lista_genero():
    return [""] + sorted(DATA["participantes"]["genero"].dropna().unique())

def lista_faixa_etaria():
    return [""] + sorted(DATA["participantes"]["faixa_etaria"].dropna().unique())

def lista_valencia_ways():
    return [""] + sorted(DATA["vias"]["vlc_maior_text"].dropna().unique())

# ────────────────────────────────────────────────────────────────
# Funções de visualização
# ────────────────────────────────────────────────────────────────

def make_base_map():
    """Cria mapa folium centralizado na média dos pontos coletados."""
    if not DATA["emoc"].empty:
        center = DATA["emoc"].geometry.unary_union.centroid
        return folium.Map(location=[center.y, center.x], zoom_start=13, tiles="CartoDB positron")
    return folium.Map(location=[0, 0], zoom_start=2)


def func_emoc_indiv(emoc_indiv, mapa):
    """Plota todos os pontos de uma emoção específica."""
    pts = DATA["emoc"].merge(
        DATA["emoji"][["cod_emoji", "emocao"]], on="cod_emoji"
    )
    sel = pts[pts["emocao"] == emoc_indiv]
    if sel.empty:
        st.info("Nenhum ponto para essa emoção.")
        return

    layer = folium.FeatureGroup(name=f"Emoção: {emoc_indiv}")
    heat_coords = []

    for _, row in sel.iterrows():
        y, x = row.geometry.y, row.geometry.x
        folium.Marker(
            location=[y, x],
            icon=folium.features.CustomIcon(f"{ICON_REPO}{row.cod_emoji}.png", icon_size=(20, 20)),
        ).add_to(layer)
        heat_coords.append([y, x])

    layer.add_to(mapa)
    plugins.HeatMap(heat_coords, name=f"Heat-map {emoc_indiv}", radius=20, blur=15).add_to(mapa)


def func_emoc_mdl(emoc_mdl, emoc_vlc, mapa):
    """Filtra por modal e valência."""
    pts = (
        DATA["emoc"]
        .merge(DATA["emoji"][["cod_emoji", "valencia"]], on="cod_emoji")
        .merge(DATA["modais"][["cod_modal", "nome"]], on="cod_modal")
    )
    if emoc_mdl:
        pts = pts[pts["nome"] == emoc_mdl]
    if emoc_vlc:
        if isinstance(emoc_vlc, str):
            emoc_vlc = [emoc_vlc]
        pts = pts[pts["valencia"].isin(emoc_vlc)]
    if pts.empty:
        st.info("Nenhum ponto com esses filtros.")
        return

    lyr_name = f"{emoc_mdl or 'Todos os modais'} – {', '.join(emoc_vlc) if emoc_vlc else 'Todas as valências'}"
    layer = folium.FeatureGroup(name=lyr_name)
    heat_coords = []
    for _, row in pts.iterrows():
        y, x = row.geometry.y, row.geometry.x
        folium.Marker(
            location=[y, x],
            icon=folium.features.CustomIcon(f"{ICON_REPO}{row.cod_emoji}.png", icon_size=(20, 20)),
            tooltip=f"{row.valencia} – {row.nome}",
        ).add_to(layer)
        heat_coords.append([y, x])
    layer.add_to(mapa)
    plugins.HeatMap(heat_coords, name=f"Heat-map {lyr_name}", radius=20, blur=15).add_to(mapa)


def func_emoc_cnr(cnr_nome, mapa, mostrar_rota=True):
    pts = (
        DATA["emoc"]
        .merge(DATA["cenarios"][["cod_cenario", "nome"]], on="cod_cenario")
        .merge(DATA["emoji"][["cod_emoji", "valencia"]], on="cod_emoji")
    )
    sel = pts[pts["nome"] == cnr_nome]
    if sel.empty:
        st.info("Nenhum ponto para esse cenário.")
        return

    layer = folium.FeatureGroup(name=f"Pontos – {cnr_nome}")
    heat_coords = []
    for _, row in sel.iterrows():
        y, x = row.geometry.y, row.geometry.x
        folium.Marker(
            location=[y, x],
            icon=folium.features.CustomIcon(f"{ICON_REPO}{row.cod_emoji}.png", icon_size=(20, 20)),
            tooltip=row.valencia,
        ).add_to(layer)
        heat_coords.append([y, x])
    layer.add_to(mapa)
    plugins.HeatMap(heat_coords, name=f"Heat-map {cnr_nome}", radius=20, blur=15).add_to(mapa)

    if mostrar_rota and "pts_cenarios" in DATA:
        rota = DATA["pts_cenarios"].merge(
            DATA["cenarios"][["cod_cenario", "nome"]], on="cod_cenario"
        )
        rota_sel = rota[rota["nome"] == cnr_nome]
        if not rota_sel.empty:
            folium.GeoJson(
                rota_sel.__geo_interface__,
                name=f"Rota {cnr_nome}",
                style_function=lambda _: {"color": "#3264a8", "weight": 4, "opacity": 0.8},
            ).add_to(mapa)


def func_emoc_lns(valencias, mapa):
    vias = DATA["vias"]
    sel = vias[vias["vlc_maior_text"].isin(valencias)]
    if sel.empty:
        st.info("Nenhuma via com essas valências.")
        return

    def style(feature):
        cor = {"Neutro": "#f6dd1e", "Negativo": "#d7191c"}.get(
            feature["properties"]["vlc_maior_text"], "#1a9641"
        )
        return {"color": cor, "weight": 5}

    folium.GeoJson(
        sel.__geo_interface__, name="Vias por valência", style_function=style
    ).add_to(mapa)

# ────────────────────────────────────────────────────────────────
# Interface Streamlit
# ────────────────────────────────────────────────────────────────

st.title("🗺️ Emotional Maps – versão GeoPandas")

viz_type = st.sidebar.selectbox(
    "Tipo de visualização",
    (
        "Emoção individual",
        "Modal + Valência",
        "Cenário",
        "Valência nas vias",
    ),
)

m = make_base_map()

if viz_type == "Emoção individual":
    emoc_escolhida = st.sidebar.selectbox("Emoção", lista_emoc())
    if emoc_escolhida:
        func_emoc_indiv(emoc_escolhida, m)

elif viz_type == "Modal + Valência":
    modal_sel = st.sidebar.selectbox("Modal", lista_mdl())
    valencias_sel = st.sidebar.multiselect("Valência", lista_valencia())
    func_emoc_mdl(modal_sel, valencias_sel, m)

elif viz_type == "Cenário":
    cnr_sel = st.sidebar.selectbox("Cenário", lista_cenarios())
    if cnr_sel:
        func_emoc_cnr(cnr_sel, m, mostrar_rota=True)

elif viz_type == "Valência nas vias":
    vlc_sel = st.sidebar.multiselect("Valência", lista_valencia_ways())
    if vlc_sel:
        func_emoc_lns(vlc_sel, m)

folium.LayerControl().add_to(m)
folium_static(m, height=750)
