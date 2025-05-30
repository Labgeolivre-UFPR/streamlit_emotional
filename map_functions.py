import folium
from folium import plugins
import matplotlib
import branca

# ---------------------------------------------------------------------------------
# Funções de visualização para o aplicativo “Mapas Emocionais”.
# As funções recebem o dicionário DATA (Geo/ DataFrames) e um folium.Map.
# ---------------------------------------------------------------------------------

DEFAULT_ICON_REPO = "dados/Lista_Final_Emojis/"

# ---------------------------------------------------------------------------------
# Cenários – camada de fundo colorida + legenda
# ---------------------------------------------------------------------------------

def add_cenarios(data, mapa):
    """Adiciona polígono/linha dos cenários com cores únicas + legenda."""
    if "cenarios" not in data or data["cenarios"].empty:
        return

    refs = data["cenarios"].referencia.dropna().unique()
    cmap = matplotlib.cm.get_cmap("tab10", len(refs))
    colordict = {r: matplotlib.colors.rgb2hex(cmap(i)) for i, r in enumerate(refs)}

    def style(f):
        ref = f["properties"].get("referencia")
        return {"color": colordict.get(ref, "#666"), "weight": 2, "opacity": 0.7}

    folium.GeoJson(
        data["cenarios"].__geo_interface__, name="Cenários", style_function=style,
        tooltip=folium.GeoJsonTooltip(fields=["referencia"]),
    ).add_to(mapa)

    # --- legenda ---
    html = """<div style='position: fixed; bottom: 30px; left: 30px; z-index: 9999; \
                background: rgba(255,255,255,0.8); padding: 10px; border-radius:6px;'>"""
    html += "<b>Cenários</b><br>"
    for ref, col in colordict.items():
        html += f"<i style='background:{col};width:12px;height:12px;display:inline-block;\
                   margin-right:4px;'></i>{ref}<br>"
    html += "</div>"
    mapa.get_root().html.add_child(branca.element.Element(html))

# ---------------------------------------------------------------------------------
# Mapa base
# ---------------------------------------------------------------------------------

def make_base_map(data, tiles="CartoDB positron", include_cenarios=True):
    if not data["emoc"].empty:
        c = data["emoc"].geometry.unary_union.centroid
        m = folium.Map([c.y, c.x], zoom_start=14, tiles=tiles)
    else:
        m = folium.Map([0, 0], zoom_start=2, tiles=tiles)

    if include_cenarios:
        add_cenarios(data, m)
    return m
    folium.LayerControl(collapsed=False).add_to(mapa)

# ---------------------------------------------------------------------------------
# Funções de pontos (emoções)
# ---------------------------------------------------------------------------------

def _add_points(gdf, name, mapa, icon_repo=DEFAULT_ICON_REPO, tooltip_col=None):
    layer = folium.FeatureGroup(name=name)
    heat = []
    for _, r in gdf.iterrows():
        y, x = r.geometry.y, r.geometry.x
        icon = folium.features.CustomIcon(f"{icon_repo}{int(r.cod_emoji)}.png", icon_size=(20, 20))
        folium.Marker([y, x], icon=icon, tooltip=r[tooltip_col] if tooltip_col else None).add_to(layer)
        heat.append([y, x])
    layer.add_to(mapa)
    plugins.HeatMap(heat, name=f"Heat {name}", radius=20, blur=15).add_to(mapa)


def emoc_indiv(data, emocao, mapa, icon_repo=DEFAULT_ICON_REPO):
    pts = data["emoc"].merge(data["emoji"][["cod_emoji", "emocao"]], on="cod_emoji")
    sel = pts[pts["emocao"] == emocao]
    if sel.empty:
        return
    _add_points(sel, f"Emoção: {emocao}", mapa, icon_repo)


def emoc_modal(data, modal, valencias, mapa, icon_repo=DEFAULT_ICON_REPO):
    pts = (
        data["emoc"].merge(data["emoji"][["cod_emoji", "valencia"]], on="cod_emoji")
                      .merge(data["modais"], on="cod_modal")
    )
    if modal:
        pts = pts[pts["nome"] == modal]
    if valencias:
        pts = pts[pts["valencia"].isin(valencias)]
    if pts.empty:
        return
    titulo = f"{modal or 'Todos'} – {', '.join(valencias) if valencias else 'todas'}"
    _add_points(pts, titulo, mapa, icon_repo, tooltip_col="valencia")


def emoc_cenario(data, cenario, mapa, icon_repo=DEFAULT_ICON_REPO):
    pts = (
        data["emoc"].merge(data["cenarios"][["cod_cenario", "referencia"]], on="cod_cenario")
                      .merge(data["emoji"][["cod_emoji", "valencia"]], on="cod_emoji")
    )
    sel = pts[pts["referencia"] == cenario]
    if sel.empty:
        return
    _add_points(sel, f"Cenário {cenario}", mapa, icon_repo, tooltip_col="valencia")

    # Pontos de referência
    if "pts_cenarios" in data:
        ref = data["pts_cenarios"].merge(
            data["cenarios"][["cod_cenario", "referencia"]], on="cod_cenario")
        ref = ref[ref["referencia"] == cenario]
        for _, r in ref.iterrows():
            folium.Marker([r.geometry.y, r.geometry.x], icon=folium.Icon(color="gray", icon="ok"),
                          popup=r.get("pt_referencia", "")).add_to(mapa)


def emoc_faixa(data, faixa, valencias, mapa, icon_repo=DEFAULT_ICON_REPO):
    pts = (data["emoc"].merge(data["participantes"], on="cod_part")
                       .merge(data["emoji"], on="cod_emoji"))
    pts = pts[pts["faixa_etaria"] == faixa]
    if valencias:
        pts = pts[pts["valencia"].isin(valencias)]
    if pts.empty:
        return
    _add_points(pts, f"Faixa {faixa}", mapa, icon_repo, tooltip_col="valencia")


def emoc_genero(data, genero, valencias, mapa, icon_repo=DEFAULT_ICON_REPO):
    pts = (data["emoc"].merge(data["participantes"], on="cod_part")
                       .merge(data["emoji"], on="cod_emoji"))
    pts = pts[pts["genero"] == genero]
    if valencias:
        pts = pts[pts["valencia"].isin(valencias)]
    if pts.empty:
        return
    _add_points(pts, f"Gênero {genero}", mapa, icon_repo, tooltip_col="valencia")

# ------------------------------------------------------------------
# Linhas – valência dominante nas vias
# ------------------------------------------------------------------

def vias_valencia(data, valencias, mapa):
    if "emoc_ways_vlc_rua" not in data:
        return
    vias = data["emoc_ways_vlc_rua"]
    sel = vias[vias["vlc_maior_text"].isin(valencias)]
    if sel.empty:
        return

    def style(feat):
        return {"color": {"Neutro": "#f6dd1e", "Negativo": "#d7191c"}.get(feat["properties"]["vlc_maior_text"], "#1a9641"),
                "weight": 5}

    folium.GeoJson(sel.__geo_interface__, name="Vias", style_function=style).add_to(mapa)