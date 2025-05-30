# build_layers.py
import geopandas as gpd
import pandas as pd

EPSG_METRIC = 32722      # UTM zona 22 S  (m)
EPSG_LATLON = 4326       # WGS-84

def build_layers(raw: dict) -> dict:
    """
    Constrói todos os GeoDataFrames equivalentes às views SQL
    e devolve num dicionário.  Espera:

        raw = {
            'ways'      : GeoDataFrame (ruas OSM),
            'emoc'      : GeoDataFrame (pontos coletados),
            'emoji'     : GeoDataFrame (tabela emoji com valência)
        }
    """
    gdfs = {}

    # ----------------------------------------------------------
    # 1) Ruas que fazem parte dos cenários
    # ----------------------------------------------------------
    ruas_cenarios = raw['ways'][raw['ways']['bool_cenario']].copy()
    gdfs['ruas_cenarios'] = ruas_cenarios

    # ----------------------------------------------------------
    # 2) Pontos ➜ rua mais próxima (≤100 m)
    # ----------------------------------------------------------
    ruas_u = ruas_cenarios.to_crs(EPSG_METRIC)
    pts_u  = raw['emoc'].to_crs(EPSG_METRIC)

    sjoin = gpd.sjoin_nearest(
        pts_u, ruas_u[['osm_id', 'name', 'cod_cenario', 'geometry']],
        how='left', distance_col='dist',
        max_distance=100
    )
    sjoin = sjoin.rename(columns={'index_right':'idx_rua'})
    gdfs['emoc_colec_ruas'] = sjoin.to_crs(EPSG_LATLON)

    # ----------------------------------------------------------
    # 3) Ponto médio (centroide) de cada rua
    # ----------------------------------------------------------
    ponto_medio = ruas_cenarios.copy()
    ponto_medio['geometry'] = ruas_cenarios.geometry.centroid
    gdfs['ponto_medio'] = ponto_medio

    # ----------------------------------------------------------
    # 4) Ponto médio ↔ emoção mais próxima (≤500 m)
    #    (equivalente ao WITH knn…)
    # ----------------------------------------------------------
    hubs_u   = ponto_medio.to_crs(EPSG_METRIC)
    knn_tmp  = gpd.sjoin_nearest(
        sjoin, hubs_u[['osm_id', 'geometry']],
        how='left', distance_col='dist_hub',
        max_distance=500
    )[['fid', 'osm_id_right']].drop_duplicates('fid')
    knn_tmp = knn_tmp.rename(columns={'osm_id_right':'hub_ruas'})
    gdfs['knn'] = knn_tmp

    # ----------------------------------------------------------
    # 5) emoc_colec_hub  (pontos + hub_ruas)
    # ----------------------------------------------------------
    emoc_colec_hub = gdfs['emoc_colec_ruas'].merge(
        knn_tmp, left_on='fid', right_on='fid', how='left'
    )
    gdfs['emoc_colec_hub'] = emoc_colec_hub

    # ----------------------------------------------------------
    # 6) Contagem de emoções por rua  (teste_contagem e emojis N)
    # ----------------------------------------------------------
    cnt = (emoc_colec_hub
           .groupby(['osm_id', 'cod_emoji'])
           .size()
           .reset_index(name='qta_emoji'))
    gdfs['contagem_emoji_rua'] = cnt

    # opcional: pivot para colunas por emoji
    pivot = cnt.pivot(index='osm_id', columns='cod_emoji', values='qta_emoji').fillna(0).astype(int)
    pivot = pivot.reset_index()
    gdfs['contagem_pivot'] = pivot

    # ----------------------------------------------------------
    # 7) Valência prevalente por rua
    # ----------------------------------------------------------
    #  primeiro agregamos por valência
    emo = raw['emoji'][['cod_emoji', 'valencia']]
    tmp = cnt.merge(emo, on='cod_emoji')
    sum_vlc = (tmp.pivot_table(index='osm_id',
                               columns='valencia',
                               values='qta_emoji',
                               aggfunc='sum',
                               fill_value=0)
                 .reset_index())
    sum_vlc['vlc_maior'] = sum_vlc[['Negativo', 'Neutro', 'Positivo']].max(axis=1)
    sum_vlc['vlc_maior_text'] = sum_vlc[['Negativo', 'Neutro', 'Positivo']].idxmax(axis=1)
    gdfs['emoc_count_ways_vlc'] = sum_vlc

    # 8) Junta na camada de linhas
    vias_vlc = ruas_cenarios.merge(sum_vlc, on='osm_id', how='left')
    gdfs['emoc_ways_vlc_rua'] = vias_vlc

    return gdfs
