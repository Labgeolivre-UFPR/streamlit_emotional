# Importando bibliotecas para conexão com o banco de dados
from configparser import ConfigParser
import psycopg2

# Importando bibliotecas para a página do streamlit e para o mapa
import streamlit as st
from streamlit_folium import folium_static
import folium
from folium import plugins
from folium.plugins import HeatMap
from folium import IFrame

# Bibliotecas para geolocalização pontos rotas
from geopy.geocoders import Nominatim
from openrouteservice import client

# Biblioteca para os dados em geojson
import json

# --- CONEXÃO COM O BANCO DE DADOS ---#
conn = None
try:
  # connect to the PostgreSQL server
  print('Connecting to the PostgreSQL database...')
  conn = psycopg2.connect(**st.secrets["postgres"])
  # create a cursor
  cursor = conn.cursor()
  print ('Conexao realizada com sucesso')
except (Exception, psycopg2.DatabaseError) as error:
  print(error)
  print ('Erro na conexao com o banco de dados')

# Tamanho do mapa
width = 1050
height = 750

m = folium.Map(width = width,
              height = height,
							location = [-25.43,-49.26],
							zoom_start = 14,
							tiles = 'Cartodb Positron',
							attr = '© contribuidores do OpenStreetMap (CC BY-SA 2.0)')

# -- FUNÇÕES --- #
# Função que chama todos os nomes das emoções
def lista_emoc():
  lista_emoc = []
  cursor.execute("""SELECT emocao FROM emoji_emoc;""")
  fet_list = cursor.fetchall()
  conn.commit()
  lista_emoc.append('')
  for emocao in fet_list:
    lista_emoc.append(emocao[0])
  return lista_emoc

# Função que chama todos os nomes dos modais
def lista_mdl():
  lista_mdl = []
  cursor.execute("""SELECT nome FROM modais;""")
  fet_list = cursor.fetchall()
  conn.commit()
  lista_mdl.append('')
  for nome in fet_list:
    lista_mdl.append(nome[0])
  return lista_mdl

# Função que chama todos os nomes dos cenarios
def lista_cnr():
  lista_cnr = []
  cursor.execute("""SELECT referencia FROM cenarios;""")
  fet_list = cursor.fetchall()
  conn.commit()
  lista_cnr.append('')
  for referencia in fet_list:
    lista_cnr.append(referencia[0])
  return lista_cnr

# Função que chama todos as faixa etárias dos participantes
def lista_etr():
  lista_etr = []
  cursor.execute("""SELECT DISTINCT ON (faixa_etaria) faixa_etaria FROM participantes;""")
  fet_list = cursor.fetchall()
  conn.commit()
  lista_etr.append('')
  for faixa_etaria in fet_list:
    lista_etr.append(faixa_etaria[0])
  return lista_etr

# Função que chama os generos dos participantes
def lista_gnr():
  lista_gnr = []
  cursor.execute("""SELECT DISTINCT ON (genero) genero FROM participantes;""")
  fet_list = cursor.fetchall()
  conn.commit()
  lista_gnr.append('')
  for genero in fet_list:
    lista_gnr.append(genero[0])
  return lista_gnr

# Função que chama todos as valencias das emoções
def lista_vlc():
  lista_vlc = []
  cursor.execute("""SELECT DISTINCT ON (valencia) valencia FROM emoji_emoc;""")
  fet_list = cursor.fetchall()
  conn.commit()
  for valencia in fet_list:
    lista_vlc.append(valencia[0])
  return lista_vlc

# --- ESTILOS --- #
# Função que retorna o estilo das ruas classificada por valência
def style_vlc(feature):
	return { 'color': '#f6dd1e' if feature['properties']['vlc_maior_text'] == 'Neutro' 
	        else '#d7191c' if feature['properties']['vlc_maior_text'] == 'Negativo' else '#1a9641',
					'weight' : 5		
	}

# --- CONSULTAS NO BANCO --- #
# Função que executa as consultas EMOÇÕES PONTO individuais
def func_emoc_indiv(emoc_indiv):
	cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_indiv AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom 
  FROM emocoes_coletadas, emoji_emoc WHERE emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND emocao = '%s'""" %emoc_indiv)
	cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features 
	FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_indiv As lg   ) As f )  As fc;""")
	json_emoc_indiv = json.dumps(cursor.fetchall())
	conn.commit()
	# st.json(json_emoc_indiv)
  # this is the layer that eventually gets added to Map
	layer = folium.FeatureGroup(name='Emoção: %s'%emoc_indiv,)
	gj = folium.GeoJson(json_emoc_indiv[2:len(json_emoc_indiv)-2])
	emoc_mkr = []
	# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
	for feature in gj.data['features']:
		icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
		icon = folium.features.CustomIcon(icon_url, icon_size=(20, 20))
		emoc_mkr.append(list(reversed(feature['geometry']['coordinates'])))
		if feature['geometry']['type'] == 'Point':
			folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
												icon=icon).add_to(layer)
	layer.add_to(m)
  # Mapa de calor das emoções individuais
	hm_emoc_indiv = folium.plugins.HeatMap(emoc_mkr, name = 'Mapa de calor da emoção: %s'%emoc_indiv, radius=20, blur=15, overlay=True, control=True)
	hm_emoc_indiv.add_to(m)
 
# Função que executa as consultas EMOÇÕES PONTO modais
def func_emoc_mdl(emoc_mdl, emoc_vlc):
	if len(emoc_vlc) == 3:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_mdl AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, modais, emoji_emoc
		WHERE emocoes_coletadas.cod_modal = modais.cod_modal AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND modais.nome = '%s' AND emoji_emoc.valencia = '%s'
		UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, modais, emoji_emoc
		WHERE emocoes_coletadas.cod_modal = modais.cod_modal AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND modais.nome = '%s' AND emoji_emoc.valencia = '%s'
		UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, modais, emoji_emoc
		WHERE emocoes_coletadas.cod_modal = modais.cod_modal AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND modais.nome = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_mdl, emoc_vlc[0], emoc_mdl, emoc_vlc[1], emoc_mdl, emoc_vlc[2]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
  	FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_mdl As lg   ) As f )  As fc;""")
		json_emoc_mdl = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_2)
  	# this is the layer that eventually gets added to Map
		layer = folium.FeatureGroup(name='Emoções de todas as valências do modal: %s' %emoc_mdl,)
		gj = folium.GeoJson(json_emoc_mdl[2:len(json_emoc_mdl)-2])

		# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
		for feature in gj.data['features']:
			icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
			icon = folium.features.CustomIcon(icon_url, icon_size=(20, 20))
			if feature['geometry']['type'] == 'Point':
				folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
													icon=icon).add_to(layer)
		layer.add_to(m)
	elif len(emoc_vlc) == 2:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_mdl AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, modais, emoji_emoc
		WHERE emocoes_coletadas.cod_modal = modais.cod_modal AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND modais.nome = '%s' AND emoji_emoc.valencia = '%s'
		UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, modais, emoji_emoc
		WHERE emocoes_coletadas.cod_modal = modais.cod_modal AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND modais.nome = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_mdl, emoc_vlc[0], emoc_mdl, emoc_vlc[1]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
  	FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_mdl As lg   ) As f )  As fc;""")
		json_emoc_mdl = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_2)
  	# this is the layer that eventually gets added to Map
		layer = folium.FeatureGroup(name='Emoções das valências %s e %s do modal: %s' %(emoc_vlc[0], emoc_vlc[1], emoc_mdl),)
		gj = folium.GeoJson(json_emoc_mdl[2:len(json_emoc_mdl)-2])

		# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
		for feature in gj.data['features']:
			icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
			icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
			if feature['geometry']['type'] == 'Point':
				folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
													icon=icon).add_to(layer)
		layer.add_to(m)
	elif len(emoc_vlc) == 1:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_mdl AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, modais, emoji_emoc
		WHERE emocoes_coletadas.cod_modal = modais.cod_modal AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND modais.nome = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_mdl, emoc_vlc[0]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
  	FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_mdl As lg   ) As f )  As fc;""")
		json_emoc_mdl = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_2)
  	# this is the layer that eventually gets added to Map
		layer = folium.FeatureGroup(name='Emoções da valência %s do modal: %s' %(emoc_vlc[0], emoc_mdl),)
		gj = folium.GeoJson(json_emoc_mdl[2:len(json_emoc_mdl)-2])

		# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
		for feature in gj.data['features']:
			icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
			icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
			if feature['geometry']['type'] == 'Point':
				folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
													icon=icon).add_to(layer)
		layer.add_to(m)
	else:
		st.info('Escolha uma os mais valências para visualizar as emoções filtradas por modal')
 
# Função que executa as consultas EMOÇÕES PONTO cenários
def func_emoc_cnr(emoc_cnr, emoc_vlc):
	if len(emoc_vlc) == 3:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_cnr AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, cenarios, emoji_emoc
		WHERE emocoes_coletadas.cod_cenario = cenarios.cod_cenario AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND cenarios.referencia = '%s' AND emoji_emoc.valencia = '%s'
		UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, cenarios, emoji_emoc
		WHERE emocoes_coletadas.cod_cenario = cenarios.cod_cenario AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND cenarios.referencia = '%s' AND emoji_emoc.valencia = '%s'
		UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, cenarios, emoji_emoc
		WHERE emocoes_coletadas.cod_cenario = cenarios.cod_cenario AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND cenarios.referencia = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_cnr, emoc_vlc[0], emoc_cnr, emoc_vlc[1], emoc_cnr, emoc_vlc[2]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
		FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_cnr As lg   ) As f )  As fc;""")
		json_emoc_cnr = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_2)
  	# this is the layer that eventually gets added to Map
		layer = folium.FeatureGroup(name='Emoções de todas as valências do cenário: %s' %emoc_cnr,)
		gj = folium.GeoJson(json_emoc_cnr[2:len(json_emoc_cnr)-2])

		# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
		for feature in gj.data['features']:
			icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
			icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
			if feature['geometry']['type'] == 'Point':
				folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
												icon=icon).add_to(layer)
		layer.add_to(m)
	elif len(emoc_vlc) == 2:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_cnr AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, cenarios, emoji_emoc
		WHERE emocoes_coletadas.cod_cenario = cenarios.cod_cenario AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND cenarios.referencia = '%s' AND emoji_emoc.valencia = '%s'
		UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, cenarios, emoji_emoc
		WHERE emocoes_coletadas.cod_cenario = cenarios.cod_cenario AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND cenarios.referencia = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_cnr, emoc_vlc[0], emoc_cnr, emoc_vlc[1]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
		FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_cnr As lg   ) As f )  As fc;""")
		json_emoc_cnr = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_2)
  	# this is the layer that eventually gets added to Map
		layer = folium.FeatureGroup(name='Emoções das valências %s e %s do cenário: %s' %(emoc_vlc[0], emoc_vlc[1], emoc_cnr),)
		gj = folium.GeoJson(json_emoc_cnr[2:len(json_emoc_cnr)-2])

		# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
		for feature in gj.data['features']:
			icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
			icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
			if feature['geometry']['type'] == 'Point':
				folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
												icon=icon).add_to(layer)
		layer.add_to(m)
	elif len(emoc_vlc) == 1:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_cnr AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, cenarios, emoji_emoc
		WHERE emocoes_coletadas.cod_cenario = cenarios.cod_cenario AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND cenarios.referencia = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_cnr, emoc_vlc[0]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
		FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_cnr As lg   ) As f )  As fc;""")
		json_emoc_cnr = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_2)
  	# this is the layer that eventually gets added to Map
		layer = folium.FeatureGroup(name='Emoções da valencia %s do cenário: %s' %(emoc_vlc[0], emoc_cnr),)
		gj = folium.GeoJson(json_emoc_cnr[2:len(json_emoc_cnr)-2])

		# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
		for feature in gj.data['features']:
			icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
			icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
			if feature['geometry']['type'] == 'Point':
				folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
												icon=icon).add_to(layer)
		layer.add_to(m)
	else:
		st.info('Escolha uma os mais valências para visualizar as emoções nofiltradas por cenário')

# Função que executa as consultas para mostrar os pontos dos cenário
def func_pts_cnr(emoc_cnr):
	cursor.execute("""CREATE OR REPLACE VIEW pts_cnr_selec AS SELECT pts_cenarios.fid, pts_cenarios.pt_referencia, ST_Force2D(pts_cenarios.geom) AS geom 
	FROM pts_cenarios, cenarios
	WHERE pts_cenarios.cod_cenario = cenarios.cod_cenario AND cenarios.referencia = '%s'""" %emoc_cnr)
	cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
	FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, pt_referencia) As l)) As properties FROM pts_cnr_selec As lg   ) As f )  As fc;""")
	json_pts_cnr = json.dumps(cursor.fetchall())
	conn.commit()
	# st.json(json_pts_cnr)
  # this is the layer that eventually gets added to Map
	layer = folium.FeatureGroup(name='Pontos de referência do cenário',)
	gj = folium.GeoJson(json_pts_cnr[2:len(json_pts_cnr)-2])

	# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
	for feature in gj.data['features']:
		if feature['geometry']['type'] == 'Point':
			folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
			              popup = feature['properties']['pt_referencia'],
										icon = folium.Icon(color = "gray", icon = "ok",)
								 ).add_to(layer)
	layer.add_to(m)

# Função que executa as consultas EMOÇÕES PONTO faixa etária
def func_emoc_etr(emoc_etr, emoc_vlc):
	if len(emoc_vlc) == 3:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_etr AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, participantes, emoji_emoc
		WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.faixa_etaria = '%s' AND emoji_emoc.valencia = '%s'
		UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, participantes, emoji_emoc
		WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.faixa_etaria = '%s' AND emoji_emoc.valencia = '%s'
		UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, participantes, emoji_emoc 
		WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.faixa_etaria = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_etr, emoc_vlc[0], emoc_etr, emoc_vlc[1], emoc_etr, emoc_vlc[2]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
		FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_etr As lg   ) As f )  As fc;""")
		json_emoc_etr = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_2)
  	# this is the layer that eventually gets added to Map
		layer = folium.FeatureGroup(name='Emoções de todas as valências da faixa etária: %s' %emoc_etr,)
		gj = folium.GeoJson(json_emoc_etr[2:len(json_emoc_etr)-2])

		# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
		for feature in gj.data['features']:
			icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
			icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
			if feature['geometry']['type'] == 'Point':
				folium.Marker(location=list(reversed(feature['geometry']['coordinates'])), icon=icon).add_to(layer)
		layer.add_to(m)
	elif len(emoc_vlc) == 2:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_etr AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, participantes, emoji_emoc
		WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.faixa_etaria = '%s' AND emoji_emoc.valencia = '%s'
		UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, participantes, emoji_emoc 
		WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.faixa_etaria = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_etr, emoc_vlc[0], emoc_etr, emoc_vlc[1]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
		FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_etr As lg   ) As f )  As fc;""")
		json_emoc_etr = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_2)
  	# this is the layer that eventually gets added to Map
		layer = folium.FeatureGroup(name='Emoções das valencias %s e %s da faixa etária: %s' %(emoc_vlc[0], emoc_vlc[1], emoc_etr),)
		gj = folium.GeoJson(json_emoc_etr[2:len(json_emoc_etr)-2])

		# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
		for feature in gj.data['features']:
			icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
			icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
			if feature['geometry']['type'] == 'Point':
				folium.Marker(location=list(reversed(feature['geometry']['coordinates'])), icon=icon).add_to(layer)
		layer.add_to(m)
	elif len(emoc_vlc) == 1:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_etr AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, participantes, emoji_emoc
		WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.faixa_etaria = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_etr, emoc_vlc[0]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features
		FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_etr As lg   ) As f )  As fc;""")
		json_emoc_etr = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_2)
  	# this is the layer that eventually gets added to Map
		layer = folium.FeatureGroup(name='Emoções da valência %s da faixa etária: %s' %(emoc_vlc[0], emoc_etr),)
		gj = folium.GeoJson(json_emoc_etr[2:len(json_emoc_etr)-2])

		# iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
		for feature in gj.data['features']:
			icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
			icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
			if feature['geometry']['type'] == 'Point':
				folium.Marker(location=list(reversed(feature['geometry']['coordinates'])), icon=icon).add_to(layer)
		layer.add_to(m)
	else:
		st.info('Escolha uma os mais valências para visualizar as emoções filtradas por faixa etária dos participantes')
 
# Função que executa as consultas EMOÇÕES PONTO genero
# --- SEGUNDA VERSÃO INTERATIVA COM VALENCIA --- #
def func_emoc_gnr(emoc_gnr, emoc_vlc):
  if len(emoc_vlc) == 3:
    cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_gnr AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia
    FROM emocoes_coletadas, participantes, emoji_emoc WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.genero = '%s' AND emoji_emoc.valencia = '%s' 
    UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, participantes, emoji_emoc 
    WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.genero = '%s' AND emoji_emoc.valencia = '%s'
    UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, participantes, emoji_emoc
    WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.genero = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_gnr, emoc_vlc[0], emoc_gnr, emoc_vlc[1], emoc_gnr, emoc_vlc[2]))
    cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_gnr As lg   ) As f )  As fc;""")
    json_emoc_gnr = json.dumps(cursor.fetchall())
    conn.commit()
    # st.json(json_2)
    # this is the layer that eventually gets added to Map
    layer = folium.FeatureGroup(name='Emoções de todas as valencias do gênero: %s' %emoc_gnr,)
    gj = folium.GeoJson(json_emoc_gnr[2:len(json_emoc_gnr)-2])

    # iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
    for feature in gj.data['features']:
      icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
      icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
      if feature['geometry']['type'] == 'Point':
        folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
				                  icon=icon).add_to(layer)
    layer.add_to(m)
  elif len(emoc_vlc) == 2:
    cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_gnr AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia
    FROM emocoes_coletadas, participantes, emoji_emoc WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.genero = '%s' AND emoji_emoc.valencia = '%s' 
    UNION SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia FROM emocoes_coletadas, participantes, emoji_emoc 
    WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji AND participantes.genero = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_gnr, emoc_vlc[0], emoc_gnr, emoc_vlc[1]))
    cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_gnr As lg   ) As f )  As fc;""")
    json_emoc_gnr = json.dumps(cursor.fetchall())
    conn.commit()
    # st.json(json_2)
    # this is the layer that eventually gets added to Map
    layer = folium.FeatureGroup(name='Emoções de valencias %s e %s do gênero: %s' %(emoc_vlc[0], emoc_vlc[1], emoc_gnr),)
    gj = folium.GeoJson(json_emoc_gnr[2:len(json_emoc_gnr)-2])

    # iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
    for feature in gj.data['features']:
      icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
      icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
      if feature['geometry']['type'] == 'Point':
        folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
				                  icon=icon).add_to(layer)
    layer.add_to(m)
  elif len(emoc_vlc) == 1:
    cursor.execute("""CREATE OR REPLACE VIEW emoc_colec_gnr AS SELECT emocoes_coletadas.fid, emocoes_coletadas.cod_emoji, ST_Force2D(emocoes_coletadas.geom) AS geom, emoji_emoc.valencia
    FROM emocoes_coletadas, participantes, emoji_emoc WHERE emocoes_coletadas.cod_part = participantes.cod_part AND emocoes_coletadas.cod_emoji = emoji_emoc.cod_emoji
		AND participantes.genero = '%s' AND emoji_emoc.valencia = '%s'""" %(emoc_gnr, emoc_vlc[0]))
    cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, cod_emoji) As l)) As properties FROM emoc_colec_gnr As lg   ) As f )  As fc;""")
    json_emoc_gnr = json.dumps(cursor.fetchall())
    conn.commit()
    # st.json(json_2)
    # this is the layer that eventually gets added to Map
    layer = folium.FeatureGroup(name='Emoções de valencia %s do gênero: %s' %(emoc_vlc[0], emoc_gnr),)
    gj = folium.GeoJson(json_emoc_gnr[2:len(json_emoc_gnr)-2])

    # iterate over GEOJSON features, pull out point coordinates, make Markers and add to layer
    for feature in gj.data['features']:
      icon_url = 'https://raw.githubusercontent.com/GabrieleCamara/Streamlit-EmotionalMaps/main/Lista_Final_Emojis/%s.png' %feature['properties']['cod_emoji']
      icon = folium.features.CustomIcon(icon_url, icon_size=(25, 25))
      if feature['geometry']['type'] == 'Point':
        folium.Marker(location=list(reversed(feature['geometry']['coordinates'])),
				                  icon=icon).add_to(layer)
    layer.add_to(m)
  else:
    st.info('Escolha uma os mais valências para visualizar as emoções filtradas por gênero dos participantes')

# Função que executa a consulta das emoções por LINHA
def func_emoc_lns(emoc_vlc):
	if len(emoc_vlc) == 3:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_vlc AS SELECT * FROM emoc_ways_vlc_rua WHERE vlc_maior_text = '%s'
		UNION SELECT * FROM emoc_ways_vlc_rua WHERE vlc_maior_text = '%s' UNION SELECT * FROM emoc_ways_vlc_rua WHERE vlc_maior_text = '%s'""" %(emoc_vlc[0], emoc_vlc[1], emoc_vlc[2]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features 
		FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, vlc_maior, vlc_maior_text) As l)) As properties 
		FROM emoc_vlc As lg ) As f )  As fc;""")
		json_emoc_lns = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_emoc_lns)
	
		layer = folium.GeoJson(
				json_emoc_lns[2:len(json_emoc_lns)-2],
				name = 'Ruas classificadas por todas as valência',
				style_function = lambda feature: style_vlc(feature)
		).add_to(m)
	elif len(emoc_vlc) == 2:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_vlc AS SELECT * FROM emoc_ways_vlc_rua WHERE vlc_maior_text = '%s'
		UNION SELECT * FROM emoc_ways_vlc_rua WHERE vlc_maior_text = '%s'""" %(emoc_vlc[0], emoc_vlc[1]))
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features 
		FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, vlc_maior, vlc_maior_text) As l)) As properties 
		FROM emoc_vlc As lg ) As f )  As fc;""")
		json_emoc_lns = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_emoc_lns)
	
		layer = folium.GeoJson(
				json_emoc_lns[2:len(json_emoc_lns)-2],
				name = 'Ruas classificadas pelas valências %s e %s' %(emoc_vlc[0], emoc_vlc[1]),
				style_function = lambda feature: style_vlc(feature)
		).add_to(m)
	elif len(emoc_vlc) == 1:
		cursor.execute("""CREATE OR REPLACE VIEW emoc_vlc AS SELECT * FROM emoc_ways_vlc_rua WHERE vlc_maior_text = '%s'""" %emoc_vlc[0])
		cursor.execute("""SELECT row_to_json(fc) FROM ( SELECT 'FeatureCollection' As type, array_to_json(array_agg(f)) As features 
		FROM (SELECT 'Feature' As type, ST_AsGeoJSON(lg.geom)::json As geometry, row_to_json((SELECT l FROM (SELECT fid, vlc_maior, vlc_maior_text) As l)) As properties 
		FROM emoc_vlc As lg ) As f )  As fc;""")
		json_emoc_lns = json.dumps(cursor.fetchall())
		conn.commit()
		# st.json(json_emoc_lns)
	
		layer = folium.GeoJson(
				json_emoc_lns[2:len(json_emoc_lns)-2],
				name = 'Ruas classificadas pela valências %s' %emoc_vlc[0],
				style_function = lambda feature: style_vlc(feature)
		).add_to(m)
	else:
		pass

# Função que passa para o banco os parâmetros para fazer uma rota
def func_address_route(address_1, address_2):
	# API do openroute services
	api_key = '5b3ce3597851110001cf6248997aca5cd66d41c2aa3ad5f61948b94e'
	clnt = client.Client(key=api_key) # Create client with api key

	# Pede e geocodifica os dois endereços
	geolocator = Nominatim(user_agent = 'camaragabriele@gmail.com')
	location_1 = geolocator.geocode(address_1)
	location_2 = geolocator.geocode(address_2)

	# Coloca os pois pontos no mapa
	# Ponto de partida
	folium.Marker(location=[location_1.latitude, location_1.longitude],
                popup='Ponto de partida: '+address_1,
                icon=folium.Icon(color='blue',icon='star')).add_to(m)
	# Ponto de chegada 
	folium.Marker(location=[location_2.latitude, location_2.longitude],
	              popup='Ponto de chegada: '+address_2,
                icon=folium.Icon(color='green',icon='star')).add_to(m)

	# Implementar rota no pgrouting 
	# Adicionar no mapa as ruas com mapeamento emocional

# --- PÁGINA --- #
# Configurações da aba da página
PAGE_CONFIG = {"page_title":"Mapas Emocionais","page_icon":":heart:","layout":"wide"}
st.set_page_config(**PAGE_CONFIG)

def main():
	# --- CANVA --- #
	st.title("Mapas Emocionais no Contexto da Mobilidade Urbana")
	  
	# --- SIDEBAR --- #
	st.sidebar.header('Navegação')
 
	sobre = st.sidebar.checkbox('Sobre o projeto')
	emoc_vlc = st.multiselect('Escolha as valências da emoções consultadas', lista_vlc(), default=lista_vlc())
	
	with st.sidebar.expander("Consultas por Ponto"):
		emoc_indiv = st.selectbox('Escolha uma emoção', lista_emoc())
		emoc_mdl = st.selectbox('Escolha um meio de transporte', lista_mdl())
		emoc_cnr = st.selectbox('Escolha um cenário', lista_cnr())
		st.caption("Filtros de acordo com o perfil do usuário")
		emoc_etr = st.selectbox('Escolha uma faixa etária', lista_etr())
		emoc_gnr = st.selectbox('Escolha um gênero', lista_gnr()) 
		

  	# Executa a ação no selectbox emoção 
		if emoc_indiv != '' :
			func_emoc_indiv(emoc_indiv)
		else: 
			pass
  
 		# Executa a ação no selectbox modal 
		if emoc_mdl != '':
			func_emoc_mdl(emoc_mdl, emoc_vlc)
		else:
			pass

  	# Executa a ação no selectbox cenarios
		if emoc_cnr != '':
			# emoc_vlc = st.multiselect('Escolha as valências da emoções consultadas', lista_vlc(), default=lista_vlc())
			func_emoc_cnr(emoc_cnr, emoc_vlc)
			func_pts_cnr(emoc_cnr)
		else:
			pass

  	# Executa a ação no selectbox faixa etaria
		if emoc_etr != '':
			# emoc_vlc = st.multiselect('Escolha as valências da emoções consultadas', lista_vlc(), default=lista_vlc())
			func_emoc_etr(emoc_etr, emoc_vlc)
		else:
			pass

  	# Executa a ação no selectbox genero
		if emoc_gnr != '':
			# emoc_vlc = st.multiselect('Escolha as valências da emoções consultadas', lista_vlc(), default=lista_vlc())
			# Executa a função com a consulta espacial passando os dois parâmetros
			func_emoc_gnr(emoc_gnr, emoc_vlc)
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
		folium_static(m, width = width, height = height) 

if __name__ == '__main__':
	main()
 
cursor.close()
conn.close()