# map_functions.py
import folium
from folium import plugins
import matplotlib
import branca

# i18n
from i18n import t

# ---------------------------------------------------------------------------------
# Funções de visualização para o aplicativo “Mapas Emocionais”.
# As funções recebem o dicionário DATA (Geo/DataFrames) e um folium.Map.
# ---------------------------------------------------------------------------------

DEFAULT_ICON_REPO = "dados/Lista_Final_Emojis/"

# ---------------------------------------------------------------------------------
# Utilitários (internacionalização de valências)
# ---------------------------------------------------------------------------------

def _norm_valence(v) -> str | None:
    """Normaliza rótulos de valência para códigos 'neg', 'neu', 'pos'."""
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"neg", "negative", "negativo", "-1", "−1"}:
        return "neg"
    if s in {"neu", "neutral", "neutro", "0"}:
        return "neu"
    if s in {"pos", "positive", "positivo", "1"}:
        return "pos"
    return s  # fallback (mantém como veio)

def _valence_labels(lang: str) -> dict[str, str]:
    """Rótulos traduzidos para exibição."""
    return {
        "neg": t("metrics.valence.negative", lang),
        "neu": t("metrics.valence.neutral",  lang),
        "pos": t("metrics.valence.positive", lang),
    }

# ---------------------------------------------------------------------------------
# Cenários – camada de fundo colorida + legenda
# ---------------------------------------------------------------------------------

def add_cenarios(data, mapa, lang: str = "pt"):
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
        data["cenarios"].__geo_interface__,
        name=t("map.layers.scenarios", lang),
        style_function=style,
        tooltip=folium.GeoJsonTooltip(fields=["referencia"]),
    ).add_to(mapa)

    # --- legenda ---
    html = (
        "<div style='position: fixed; bottom: 30px; left: 30px; z-index: 9999; "
        "background: rgba(255,255,255,0.8); padding: 10px; border-radius:6px;'>"
    )
    html += f"<b>{t('map.legend.scenarios_title', lang)}</b><br>"
    for ref, col in colordict.items():
        html += (
            f"<i style='background:{col};width:12px;height:12px;display:inline-block;"
            f"margin-right:4px;'></i>{ref}<br>"
        )
    html += "</div>"
    mapa.get_root().html.add_child(branca.element.Element(html))

# ---------------------------------------------------------------------------------
# Mapa base
# ---------------------------------------------------------------------------------

def make_base_map(data, tiles: str = "CartoDB positron", include_cenarios: bool = True, lang: str = "pt"):
    if not data.get("emoc", None) is None and not data["emoc"].empty:
        c = data["emoc"].geometry.unary_union.centroid
        m = folium.Map([c.y, c.x], zoom_start=14, tiles=tiles)
    else:
        m = folium.Map([0, 0], zoom_start=2, tiles=tiles)

    if include_cenarios:
        add_cenarios(data, m, lang)

    folium.LayerControl(collapsed=False).add_to(m)
    return m

# ---------------------------------------------------------------------------------
# Funções de pontos (emoções)
# ---------------------------------------------------------------------------------

def _add_points(gdf, name: str, mapa, icon_repo=DEFAULT_ICON_REPO, tooltip_col: str | None = None, lang: str = "pt"):
    layer = folium.FeatureGroup(name=name)
    heat = []
    for _, r in gdf.iterrows():
        y, x = r.geometry.y, r.geometry.x
        icon = folium.features.CustomIcon(f"{icon_repo}{int(r.cod_emoji)}.png", icon_size=(20, 20))
        tooltip_val = None
        if tooltip_col:
            val = r[tooltip_col]
            # se tooltip for valência, traduz
            if tooltip_col == "valence_code":
                tooltip_val = _valence_labels(lang).get(val, val)
            else:
                tooltip_val = val
        folium.Marker([y, x], icon=icon, tooltip=tooltip_val).add_to(layer)
        heat.append([y, x])
    layer.add_to(mapa)
    plugins.HeatMap(heat, name=f"{t('map.layers.heat', lang)} – {name}", radius=20, blur=15).add_to(mapa)

def emoc_indiv(data, emocao: str, mapa, icon_repo=DEFAULT_ICON_REPO, lang: str = "pt"):
    pts = data["emoc"].merge(data["emoji"][["cod_emoji", "emocao"]], on="cod_emoji")
    sel = pts[pts["emocao"] == emocao]
    if sel.empty:
        return
    layer_name = t("map.layers.emotion_single", lang, emotion=emocao)
    _add_points(sel, layer_name, mapa, icon_repo, lang=lang)

def emoc_modal(data, modal: str | None, valencias: list[str] | None, mapa, icon_repo=DEFAULT_ICON_REPO, lang: str = "pt"):
    pts = (
        data["emoc"].merge(data["emoji"][["cod_emoji", "valencia"]], on="cod_emoji")
                    .merge(data["modais"], on="cod_modal")
    )
    # cria 'valence_code' para filtrar/mostrar traduzido
    pts["valence_code"] = pts["valencia"].map(_norm_valence)

    if modal:
        pts = pts[pts["nome"] == modal]

    if valencias:
        # aceita códigos ('neg/neu/pos') ou rótulos em PT/EN
        wanted = { _norm_valence(v) for v in valencias }
        pts = pts[pts["valence_code"].isin(wanted)]

    if pts.empty:
        return

    # título traduzido
    labels = _valence_labels(lang)
    if valencias:
        shown = ", ".join(labels.get(_norm_valence(v), v) for v in valencias)
    else:
        shown = t("common.all_feminine", lang)  # ex.: "todas"
    titulo = f"{modal or t('common.all_masculine', lang)} – {shown}"

    _add_points(pts, titulo, mapa, icon_repo, tooltip_col="valence_code", lang=lang)

def emoc_cenario(data, cenario: str, mapa, icon_repo=DEFAULT_ICON_REPO, lang: str = "pt"):
    pts = (
        data["emoc"].merge(data["cenarios"][["cod_cenario", "referencia"]], on="cod_cenario")
                    .merge(data["emoji"][["cod_emoji", "valencia"]], on="cod_emoji")
    )
    pts["valence_code"] = pts["valencia"].map(_norm_valence)
    sel = pts[pts["referencia"] == cenario]
    if sel.empty:
        return
    layer_name = t("map.layers.scenario_named", lang, scenario=cenario)
    _add_points(sel, layer_name, mapa, icon_repo, tooltip_col="valence_code", lang=lang)

    # Pontos de referência do cenário (se houver)
    if "pts_cenarios" in data and not data["pts_cenarios"].empty:
        ref = data["pts_cenarios"].merge(
            data["cenarios"][["cod_cenario", "referencia"]], on="cod_cenario"
        )
        ref = ref[ref["referencia"] == cenario]
        for _, r in ref.iterrows():
            folium.Marker(
                [r.geometry.y, r.geometry.x],
                icon=folium.Icon(color="gray", icon="ok"),
                popup=r.get("pt_referencia", "")
            ).add_to(mapa)

def emoc_faixa(data, faixa: str, valencias: list[str] | None, mapa, icon_repo=DEFAULT_ICON_REPO, lang: str = "pt"):
    pts = (data["emoc"].merge(data["participantes"], on="cod_part")
                       .merge(data["emoji"], on="cod_emoji"))
    pts["valence_code"] = pts["valencia"].map(_norm_valence)

    pts = pts[pts["faixa_etaria"] == faixa]
    if valencias:
        wanted = { _norm_valence(v) for v in valencias }
        pts = pts[pts["valence_code"].isin(wanted)]
    if pts.empty:
        return

    layer_name = t("map.layers.age_range_named", lang, age=faixa)
    _add_points(pts, layer_name, mapa, icon_repo, tooltip_col="valence_code", lang=lang)

def emoc_genero(data, genero: str, valencias: list[str] | None, mapa, icon_repo=DEFAULT_ICON_REPO, lang: str = "pt"):
    pts = (data["emoc"].merge(data["participantes"], on="cod_part")
                       .merge(data["emoji"], on="cod_emoji"))
    pts["valence_code"] = pts["valencia"].map(_norm_valence)

    pts = pts[pts["genero"] == genero]
    if valencias:
        wanted = { _norm_valence(v) for v in valencias }
        pts = pts[pts["valence_code"].isin(wanted)]
    if pts.empty:
        return

    layer_name = t("map.layers.gender_named", lang, gender=genero)
    _add_points(pts, layer_name, mapa, icon_repo, tooltip_col="valence_code", lang=lang)

# ------------------------------------------------------------------
# Linhas – valência dominante nas vias
# ------------------------------------------------------------------

def vias_valencia(data, valencias: list[str] | None, mapa, lang: str = "pt"):
    if "emoc_ways_vlc_rua" not in data or data["emoc_ways_vlc_rua"].empty:
        return
    vias = data["emoc_ways_vlc_rua"]

    # Usa coluna padronizada por código (ver build_layers.py)
    # fallback: se não existir, tenta mapear a partir de 'vlc_maior_text'
    if "vlc_maior_code" not in vias.columns and "vlc_maior_text" in vias.columns:
        # mapeia PT->code como contingência
        mapping = {"Negativo": "neg", "Neutro": "neu", "Positivo": "pos"}
        vias = vias.copy()
        vias["vlc_maior_code"] = vias["vlc_maior_text"].map(mapping)

    if valencias:
        wanted = { _norm_valence(v) for v in valencias }
        sel = vias[vias["vlc_maior_code"].isin(wanted)]
    else:
        sel = vias

    if sel.empty:
        return

    # Cores por código
    color_map = {"neg": "#FF6C00", "neu": "#F6DD1B", "pos": "#46BDC6"}

    def style(feat):
        code = feat["properties"].get("vlc_maior_code")
        return {"color": color_map.get(code, "#46BDC6"), "weight": 5}

    folium.GeoJson(
        sel.__geo_interface__,
        name=t("map.layers.roads", lang),
        style_function=style
    ).add_to(mapa)

