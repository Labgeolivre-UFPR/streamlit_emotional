import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from folium import plugins
from streamlit_folium import st_folium
from build_layers import build_layers
import matplotlib

# ────────────────────────────────────────────────────────────────
# Configurações gerais
# ────────────────────────────────────────────────────────────────
DATA_PATH = "dados"  # pasta onde ficam os .geojson / .gpkg
ICON_REPO = f"{DATA_PATH}/Lista_Final_Emojis/"

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
        "emoji": "emoji_emoc.csv",
        "modais": "modais.csv",
        "cenarios": "cenarios.geojson",
        "participantes": "participantes.csv",
        "emoc": "emocoes_coletadas.geojson",
        "pts_cenarios": "pts_cenarios.geojson",
        #"vias": "emoc_ways_vlc_rua.geojson",
        "ways": "ways.geojson"
    }

    gdfs = {}
    for key, fname in files.items():
        try:
            if fname.endswith(".csv"):
                df = pd.read_csv(f"{DATA_PATH}/{fname}")
                gdfs[key] = df
            else:
                gdf = gpd.read_file(f"{DATA_PATH}/{fname}")
                if not gdf.crs or gdf.crs.to_epsg() != 4326:
                    gdf = gdf.to_crs(4326)
                gdfs[key] = gdf
        except Exception as e:
            st.warning(f"⚠️ Não foi possível ler {fname}: {e}")
    return gdfs

DATA = load_data()
#st.write("Colunas em DATA['emoji']:", DATA["emoji"].columns.tolist())

# depois de ler os GeoJSON originais ─ raw_dfs é o seu dicionário DATA
derived = build_layers({
    'ways': DATA['ways'],      # GeoJSON das ruas OSM
    'emoc': DATA['emoc'],      # pontos coletados
    'emoji': DATA['emoji'],    # tabela emoji
})

# Adiciona ao DATA principal, se quiser visualizá-los
DATA.update(derived)

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
    return [""] + sorted(DATA["cenarios"]["referencia"].unique())

def lista_genero():
    return [""] + sorted(DATA["participantes"]["genero"].dropna().unique())

def lista_faixa_etaria():
    return [""] + sorted(DATA["participantes"]["faixa_etaria"].dropna().unique())

def lista_valencia_ways():
    return [""] + sorted(DATA["emoc_ways_vlc_rua"]["vlc_maior_text"].dropna().unique())

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
            icon=folium.features.CustomIcon(
                f"{ICON_REPO}{int(row.cod_emoji)}.png", icon_size=(20, 20))
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
            icon=folium.features.CustomIcon(f"{ICON_REPO}{int(row.cod_emoji)}.png", icon_size=(20, 20)),
            tooltip=f"{row.valencia} – {row.nome}",
        ).add_to(layer)
        heat_coords.append([y, x])
    layer.add_to(mapa)
    plugins.HeatMap(heat_coords, name=f"Heat-map {lyr_name}", radius=20, blur=15).add_to(mapa)

def func_pts_cnr(cnr_nome, mapa):
    """Plota *pontos de referência* do cenário selecionado.
    Utiliza DATA['pts_cenarios'] (Point) com coluna `pt_referencia` e
    DATA['cenarios'] para mapear `cod_cenario` → `referencia`.
    """
    if "pts_cenarios" not in DATA:
        return

    pts = DATA["pts_cenarios"].merge(
        DATA["cenarios"][["cod_cenario", "referencia"]], on="cod_cenario"
    )
    sel = pts[pts["referencia"] == cnr_nome]
    if sel.empty:
        return

    layer = folium.FeatureGroup(name="Pontos de referência do cenário")
    for _, row in sel.iterrows():
        folium.Marker(
            [row.geometry.y, row.geometry.x],
            popup=row.get("pt_referencia", ""),
            icon=folium.Icon(color="gray", icon="ok")
        ).add_to(layer)
    layer.add_to(mapa)

    # Também desenha a pequena rota (linhas) se pts forem segmentados
    if sel.geometry.geom_type.iloc[0] == "LineString":
        folium.GeoJson(
            sel.__geo_interface__,
            name="Rota cenário",
            style_function=lambda _: {"color": "#3264a8", "weight": 4},
        ).add_to(mapa)

def func_emoc_cnr(cnr_nome, mapa, mostrar_rota=True):
    pts = (
        DATA["emoc"]
        .merge(DATA["cenarios"][["cod_cenario", "referencia"]], on="cod_cenario")
        .merge(DATA["emoji"][["cod_emoji", "valencia"]], on="cod_emoji")
    )
    sel = pts[pts["referencia"] == cnr_nome]
    if sel.empty:
        st.info("Nenhum ponto para esse cenário.")
        return

    layer = folium.FeatureGroup(name=f"Pontos – {cnr_nome}")
    heat_coords = []
    for _, row in sel.iterrows():
        y, x = row.geometry.y, row.geometry.x
        folium.Marker(
            location=[y, x],
            icon=folium.features.CustomIcon(f"{ICON_REPO}{int(row.cod_emoji)}.png", icon_size=(20, 20)),
            tooltip=row.valencia,
        ).add_to(layer)
        heat_coords.append([y, x])
    layer.add_to(mapa)
    plugins.HeatMap(heat_coords, name=f"Heat-map {cnr_nome}", radius=20, blur=15).add_to(mapa)

    if mostrar_rota and "pts_cenarios" in DATA:
        rota = DATA["pts_cenarios"].merge(
            DATA["cenarios"][["cod_cenario", "referencia"]], on="cod_cenario"
        )
        rota_sel = rota[rota["referencia"] == cnr_nome]
        if not rota_sel.empty:
            # Adiciona marcadores com tooltip pt_referencia
            for _, row in rota_sel.iterrows():
                y, x = row.geometry.y, row.geometry.x
                folium.Marker(
                    location=[y, x],
                    icon=folium.Icon(color="blue", icon="info-sign"),
                    tooltip=row.get("pt_referencia", ""),
                ).add_to(mapa)
            folium.GeoJson(
                rota_sel.__geo_interface__,
                name=f"Rota {cnr_nome}",
                style_function=lambda _: {"color": "#3264a8", "weight": 4, "opacity": 0.8},
            ).add_to(mapa)

def func_emoc_etr(faixa, valencias, mapa):
    """Versão independente (sem _plot_points):
    Plota diretamente os marcadores e o heat‑map na *folium.Map* recebida.
    """
    # 1) Junta pontos + info de participante + valência
    pts = (
        DATA["emoc"].merge(
            DATA["participantes"][["cod_part", "faixa_etaria"]], on="cod_part"
        ).merge(
            DATA["emoji"][["cod_emoji", "valencia"]], on="cod_emoji"
        )
    )
    pts = pts[pts["faixa_etaria"] == faixa]
    if valencias:
        pts = pts[pts["valencia"].isin(valencias)]

    if pts.empty:
        st.info("Nenhum ponto para esses filtros.")
        return

    # Nome da camada conforme nº de valências
    if not valencias or len(valencias) == 3:
        cam_name = f"Emoções de todas as valências da faixa etária: {faixa}"
    elif len(valencias) == 2:
        cam_name = f"Emoções das valências {valencias[0]} e {valencias[1]} da faixa etária: {faixa}"
    else:
        cam_name = f"Emoções da valência {valencias[0]} da faixa etária: {faixa}"

    layer = folium.FeatureGroup(name=cam_name)
    heat_coords = []

    for _, row in pts.iterrows():
        y, x = row.geometry.y, row.geometry.x
        icon = folium.features.CustomIcon(
            f"{ICON_REPO}{int(row.cod_emoji)}.png", icon_size=(20, 20)
        )
        folium.Marker([y, x], icon=icon, tooltip=row.valencia).add_to(layer)
        heat_coords.append([y, x])

    layer.add_to(mapa)
    plugins.HeatMap(heat_coords, name=f"Heat {cam_name}", radius=20, blur=15).add_to(mapa)

def func_emoc_gnr(genero, valencias, mapa):
    """Plota emoções filtradas por *gênero* e lista de *valências*.
    Construído sem depender de _plot_points.
    """
    pts = (
        DATA["emoc"].merge(
            DATA["participantes"][["cod_part", "genero"]], on="cod_part"
        ).merge(
            DATA["emoji"][["cod_emoji", "valencia"]], on="cod_emoji"
        )
    )
    pts = pts[pts["genero"] == genero]
    if valencias:
        pts = pts[pts["valencia"].isin(valencias)]

    if pts.empty:
        st.info("Nenhum ponto para esses filtros.")
        return

    # Nome da camada conforme nº de valências
    if not valencias or len(valencias) == 3:
        cam_name = f"Emoções de todas as valências do gênero: {genero}"
    elif len(valencias) == 2:
        cam_name = (
            f"Emoções das valências {valencias[0]} e {valencias[1]} do gênero: {genero}"
        )
    else:
        cam_name = f"Emoções da valência {valencias[0]} do gênero: {genero}"

    layer = folium.FeatureGroup(name=cam_name)
    heat_coords = []

    for _, row in pts.iterrows():
        y, x = row.geometry.y, row.geometry.x
        icon = folium.features.CustomIcon(
            f"{ICON_REPO}{int(row.cod_emoji)}.png", icon_size=(20, 20)
        )
        folium.Marker([y, x], icon=icon, tooltip=row.valencia).add_to(layer)
        heat_coords.append([y, x])

    layer.add_to(mapa)
    plugins.HeatMap(heat_coords, name=f"Heat {cam_name}", radius=20, blur=15).add_to(mapa)

def func_emoc_lns(valencias, mapa):
    vias = DATA["emoc_ways_vlc_rua"]
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

# Adiciona linhas dos cenários coloridas por 'referencia' no mapa de fundo
if viz_type in ("Emoção individual", "Modal + Valência"):
    if "cenarios" in DATA and "referencia" in DATA["cenarios"].columns:
        referencias = DATA["cenarios"]["referencia"].dropna().unique()
        cores = matplotlib.cm.get_cmap('tab10', len(referencias))
        cor_map = {ref: matplotlib.colors.rgb2hex(cores(i)) for i, ref in enumerate(referencias)}

        def style_cenario(feature):
            ref = feature["properties"].get("referencia")
            return {
                "color": cor_map.get(ref, "#888"),
                "weight": 2,
                "opacity": 1,
            }

        folium.GeoJson(
            DATA["cenarios"].__geo_interface__,
            name="Cenários (referência)",
            style_function=style_cenario,
            tooltip=folium.GeoJsonTooltip(fields=["referencia"]),
        ).add_to(m)

        # Adiciona legenda personalizada
        legenda_html = """
        <div style='position: fixed; 
                    bottom: 50px; left: 50px; width: 220px; z-index:9999; font-size:14px;
                    background: white; border:2px solid grey; border-radius:8px; padding: 10px;'>
          <b>Referências dos Cenários</b><br>
        """
        for ref, cor in cor_map.items():
            legenda_html += f"<i style='background:{cor};width:18px;height:18px;display:inline-block;margin-right:8px;'></i>{ref}<br>"
        legenda_html += "</div>"

        m.get_root().html.add_child(folium.Element(legenda_html))

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

        # Adiciona a linha do cenário selecionado, destacada
        cen_sel = DATA["cenarios"][DATA["cenarios"]["referencia"] == cnr_sel]
        if not cen_sel.empty:
            folium.GeoJson(
                cen_sel.__geo_interface__,
                name=f"Cenário selecionado: {cnr_sel}",
                style_function=lambda feat: {
                    "color": "#ff6600",
                    "weight": 6,
                    "opacity": 1,
                },
                tooltip=folium.GeoJsonTooltip(fields=["referencia"]),
            ).add_to(m)

elif viz_type == "Valência nas vias":
    vlc_sel = st.sidebar.multiselect("Valência", lista_valencia_ways())
    if vlc_sel:
        func_emoc_lns(vlc_sel, m)

folium.LayerControl().add_to(m)
st_folium(m, height=750, width=750)

def main():
	# --- CANVA --- #
	st.title("Mapas Emocionais no Contexto da Mobilidade Urbana")
	  
	# --- SIDEBAR --- #
	st.sidebar.header('Navegação')
 
	sobre = st.sidebar.checkbox('Sobre o projeto')
	emoc_vlc = st.multiselect('Escolha as valências da emoções consultadas', lista_valencia(), default=lista_valencia())
	
	with st.sidebar.expander("Consultas por Ponto"):
		emoc_indiv = st.selectbox('Escolha uma emoção', lista_emoc())
		emoc_mdl = st.selectbox('Escolha um meio de transporte', lista_mdl())
		emoc_cnr = st.selectbox('Escolha um cenário', lista_cenarios())
		st.caption("Filtros de acordo com o perfil do usuário")
		emoc_etr = st.selectbox('Escolha uma faixa etária', lista_faixa_etaria())
		emoc_gnr = st.selectbox('Escolha um gênero', lista_genero()) 
		

  	# Executa a ação no selectbox emoção 
		if emoc_indiv != '' :
			func_emoc_indiv(emoc_indiv,m)
		else: 
			pass
  
 		# Executa a ação no selectbox modal 
		if emoc_mdl != '':
			func_emoc_mdl(emoc_mdl, emoc_vlc,m)
		else:
			pass

  	# Executa a ação no selectbox cenarios
		if emoc_cnr != '':
			# emoc_vlc = st.multiselect('Escolha as valências da emoções consultadas', lista_valencia(), default=lista_valencia())
			func_emoc_cnr(emoc_cnr, m)
			func_pts_cnr(emoc_cnr,m)
		else:
			pass

  	# Executa a ação no selectbox faixa etaria
		if emoc_etr != '':
			# emoc_vlc = st.multiselect('Escolha as valências da emoções consultadas', lista_valencia(), default=lista_valencia())
			func_emoc_etr(emoc_etr, emoc_vlc,m)
		else:
			pass

  	# Executa a ação no selectbox genero
		if emoc_gnr != '':
			# emoc_vlc = st.multiselect('Escolha as valências da emoções consultadas', lista_valencia(), default=lista_valencia())
			# Executa a função com a consulta espacial passando os dois parâmetros
			func_emoc_gnr(emoc_gnr, emoc_vlc,m)
		else:
			pass

	with st.sidebar.expander("Consultas por Linha"):
		if st.checkbox('Trechos de rua por valência'):
			func_emoc_lns(emoc_vlc)
		if st.checkbox('Ponto médio emoções'):
			pass

	with st.sidebar.expander("Fazer uma rota"):
		address_1 = st.text_input('Digite um endereço para ser o ponto inicial')
		address_2 = st.text_input('Digite outro endereço para ser o ponto final')
		button_route = st.button('Fazer a rota')
		if button_route:
			func_address_route(address_1, address_2)
 

	if sobre:
		st.markdown("""Este projeto é parte da dissertação de mestrado de Gabriele Silveira Camara, no [Programa de Pós-Graduação em Ciências Geodésicas](http://www.cienciasgeodesicas.ufpr.br/portal/) da Universidade Federal do Paraná. 
		Foi desenvolvido sob orientação da Profa. Dra. Silvana Philippi Camboim e Prof. Dr. João Vitor Meza Bravo.""")
		st.subheader('Artigos relacionados')
		with st.expander('COLLABORATIVE EMOTIONAL MAPPING AS A TOOL FOR URBAN MOBILITY PLANNING.'):
			st.markdown('[Boletim de Ciências Geodésicas 27 (spe) • 2021](https://doi.org/10.1590/s1982-21702021000s00011)')
			st.markdown('**Autores:** Gabriele Silveira Camara, Silvana Philippi Camboim e João Vitor Meza Bravo.')
			st.markdown("""**Abstract:** In this article, we present a framework to collect and represent people’s emotions, considering the urban mobility context of Curitiba. As a procedure, we have interviewed individuals 
			during an intermodal challenge. The participants have described their experiences of urban mobility while using different transport modes. 
			We have we used emojis as graphic symbols representing emotional data, once it is a modern language widely incorporated in everyday life as well as evokes a natural emotional 
			association with the data we collected. We built an online geoinformation solution for visualising the emotional phenomenon. As a result, we found that the proposed methodology 
			captures environmental factors as well as specific urban features triggering positive and negative/neutral emotions. Therefore, we validated the methodology of collaborative 
			emotional mapping through volunteered geographic information, collecting and representing emotions on maps through emojis. Thus, here we argue this is a valid way to represent
			""")
	else:
		# --- MAPA DO CANVA --- #
		folium.LayerControl(collapsed = False,).add_to(m)
		st_folium(m, width=750, height=750)

if __name__ == '__main__':
	main()