import streamlit as st
import pandas as pd
import numpy as np
import matplotlib as mpl
mpl.use("agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
from matplotlib.legend_handler import HandlerTuple
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta  #vsSetor
import traceback
import streamlit.components.v1 as components  
import json
import random
import time
try:
    from dropdown_component import simple_multiselect_dropdown
    from popup import show_welcome_screen
    from calculate_business_days import calculate_business_days
    from fullscreen_image_component import create_fullscreen_image_viewer
except ImportError:
    st.warning("Componentes 'dropdown_component', 'popup', 'calculate_business_days' ou 'fullscreen_image_component' não encontrados. Alguns recursos podem não funcionar como esperado.")
    # Definir valores padrão ou mocks se necessário
    def simple_multiselect_dropdown(label, options, key, default_selected):
        return st.multiselect(label, options, default=default_selected, key=key)
    def show_welcome_screen():
        return False
    def calculate_business_days(start, end):
        if pd.isna(start) or pd.isna(end):
            return None
        return np.busday_count(pd.to_datetime(start).date(), pd.to_datetime(end).date())
    def create_fullscreen_image_viewer(img_path):
        st.info(f"Componente de visualização de imagem em tela cheia não carregado. Imagem: {img_path}")

# --- Bloco de Importação de Dados ---
@st.cache_resource
def load_data_processing_scripts():
    try:
        from processa_venda_registro import tratar_e_retornar_dados_previstos
        from processa_venda_smartsheet import main as processar_smartsheet_main
        return tratar_e_retornar_dados_previstos, processar_smartsheet_main
    except ImportError:
        st.warning("Scripts de processamento não encontrados. O app usará dados de exemplo.")
        return None, None

tratar_e_retornar_dados_previstos, processar_smartsheet_main = load_data_processing_scripts()

# --- Funções Utilitárias ---
from typing import Optional, List, Dict, Any
import base64
import io
from dateutil.relativedelta import relativedelta # Adicionado aqui para garantir que esteja disponível

@st.cache_data
def abreviar_nome(nome):
    if pd.isna(nome):
        return nome
    
    nome = nome.replace('CONDOMINIO ', '')
    palavras = nome.split()
    
    if len(palavras) > 3:
        nome = ' '.join(palavras[:3])
    
    return nome

@st.cache_data
def converter_porcentagem(valor):
    if pd.isna(valor) or valor == '': return 0.0
    if isinstance(valor, str):
        valor = ''.join(c for c in valor if c.isdigit() or c in ['.', ',']).replace(',', '.').strip()
        if not valor: return 0.0
    try:
        val_float = float(valor)
        # Ajuste para tolerância de ponto flutuante: considera 1.0001 como 1.0 (100%)
        # Valores muito baixos (ex: 0.01 = 1%) também serão multiplicados (ex: 1.0)
        # Assumiremos que valores <= 1.5 sejam decimais, para evitar erros com "1.00000001"
        return val_float * 100 if val_float <= 1.01 else val_float
    except (ValueError, TypeError):
        return 0.0

@st.cache_data
def formatar_data(data):
    return data.strftime("%d/%m/%y") if pd.notna(data) else "N/D"

@st.cache_data
def calcular_dias_uteis(inicio, fim):
    if pd.notna(inicio) and pd.notna(fim):
        data_inicio = np.datetime64(inicio.date())
        data_fim = np.datetime64(fim.date())
        return np.busday_count(data_inicio, data_fim) + 1
    return 0

@st.cache_data
def calcular_variacao_duracao(duracao_real, duracao_prevista):
    """
    Calcula a variação entre a duração real e a duração prevista em dias.
    Retorna uma tupla (texto_variacao, cor_variacao).
    """
    if duracao_real > 0 and duracao_prevista > 0:
        diferenca_dias = duracao_real - duracao_prevista
        
        if diferenca_dias > 0:
            # Demorou mais que o previsto - vermelho
            return f"VD: +{diferenca_dias}d", "#89281d"
        elif diferenca_dias < 0:
            # Demorou menos que o previsto - verde
            return f"VD: {diferenca_dias}d", "#0b803c"
        else:
            # No prazo - cinza
            return "VD: 0d", "#666666"
    else:
        # Sem dados suficientes - cinza
        return "VD: -", "#666666"

@st.cache_data
def calcular_variacao_termino(termino_real, termino_previsto):
    """
    Calcula a variação entre o término real e o término previsto.
    Retorna uma tupla (texto_variacao, cor_variacao)
    """
    if pd.notna(termino_real) and pd.notna(termino_previsto):
        # Usando a função calculate_business_days importada no início
        diferenca_dias = calculate_business_days(termino_previsto, termino_real)
        if pd.isna(diferenca_dias): diferenca_dias = 0 # Lidar com casos em que calculate_business_days retorna NA
        
        if diferenca_dias > 0:
            # Atrasado - vermelho
            return f"VT: +{diferenca_dias}d", "#89281d"
        elif diferenca_dias < 0:
            # Adiantado - verde
            return f"VT: {diferenca_dias}d", "#0b803c"
        else:
            # No prazo - cinza
            return "VT: 0d", "#666666"
    else:
        # Sem dados suficientes - cinza
        return "VT: -", "#666666"

@st.cache_data
def calcular_porcentagem_correta(grupo):
    if '% concluído' not in grupo.columns:
        return 0.0
    
    porcentagens = grupo['% concluído'].astype(str).apply(converter_porcentagem)
    porcentagens = porcentagens[(porcentagens >= 0) & (porcentagens <= 100)]
    
    if len(porcentagens) == 0:
        return 0.0
    
    porcentagens_validas = porcentagens[pd.notna(porcentagens)]
    if len(porcentagens_validas) == 0:
        return 0.0
    return porcentagens_validas.mean()

# --- Mapeamentos e Padronização ---
ORDEM_ETAPAS_GLOBAL = ['DM', 'DOC', 'LAE', 'MEM', 'CONT', 'ASS', 'M', 'PJ']

GRUPOS = {
    'DM': ['DM'],
    'DOC': ['DOC'],
    'LAE': ['LAE'],
    'MEM': ['MEM'],
    'CONT': ['CONT'],
    'ASS': ['ASS'],
    'M':['M'],
    'PJ': ['PJ']
}

SETOR = {
    'DM': ['DM'],
    'DOC': ['DOC'],
    'LAE': ['LAE'],
    'MEM': ['MEM'],
    'CONT': ['CONT'],
    'ASS': ['ASS'],
    'M':['M'],
    'PJ': ['PJ']
}
# --- Mapeamentos e Padronização ---
sigla_para_nome_completo = {
    'DM': 'DEFINIÇÃO DO MÓDULO', 'DOC': 'DOCUMENTAÇÃO', 'LAE': 'LAE',
    'MEM': 'MEMORIAL', 'CONT': 'CONTRATAÇÃO', 'ASS': 'PRÉ-ASSINATURA',
    'M':  'DEMANDA MÍNIMA', 'PJ':  '1º PJ'
}
nome_completo_para_sigla = {v: k for k, v in sigla_para_nome_completo.items()}
mapeamento_variacoes_real = {
    'DEFINIÇÃO DO MÓDULO': 'DM', 'DOCUMENTAÇÃO': 'DOC', 'LAE': 'LAE', 'MEMORIAL': 'MEM',
    'CONTRATAÇÃO': 'CONT', 'PRÉ-ASSINATURA': 'ASS', 'ASS': 'ASS', '1º PJ': 'PJ',
    'PLANEJamento': 'DM', 'MEMORIAL DE INCORPORAÇÃO': 'MEM', 'EMISSÃO DO LAE': 'LAE',
    'CONTESTAÇÃO': 'LAE', 'DJE': 'CONT', 'ANÁLISE DE RISCO': 'CONT', 'MORAR BEM': 'ASS',
    'SEGUROS': 'ASS', 'ATESTE': 'ASS', 'DEMANDA MÍNIMA': 'M', 'DEMANDA MINIMA': 'M',
    'PRIMEIRO PJ': 'PJ',
}
sigla_para_nome_completo_emp = {

}
class StyleConfig:
    CORES_POR_SETOR = {
        'DM': {"previsto": '#A8C5DA', "real": '#174c66'},
        'DOC': {"previsto": '#A8C5DA', "real": '#174c66'},
        'LAE': {"previsto": '#A8C5DA', "real": '#174c66'},
        'MEM': {"previsto": '#A8C5DA', "real": '#174c66'},
        'CONT': {"previsto": '#A8C5DA', "real": '#174c66'},
        'ASS': {"previsto": '#A8C5DA', "real": '#174c66'},
        'M': {"previsto": "#c6e7c8", "real": "#108318"},
        'PJ': {"previsto": '#A8C5DA', "real": '#174c66'}
    }

    @classmethod
    def set_offset_variacao_termino(cls, novo_offset):
        cls.OFFSET_VARIACAO_TERMINO = novo_offset

ORDEM_ETAPAS_NOME_COMPLETO = [sigla_para_nome_completo.get(s, s) for s in ORDEM_ETAPAS_GLOBAL]
nome_completo_para_sigla = {v: k for k, v in sigla_para_nome_completo.items()}
GRUPO_POR_ETAPA = {}
for grupo, etapas in GRUPOS.items():
    for etapa in etapas:
        GRUPO_POR_ETAPA[etapa] = grupo

SETOR_POR_ETAPA = {}
for setor, etapas in SETOR.items():
    for etapa in etapas:
        SETOR_POR_ETAPA[etapa] = setor

def padronizar_etapa(etapa_str):
    if pd.isna(etapa_str): return 'UNKNOWN'
    etapa_limpa = str(etapa_str).strip().upper()
    if etapa_limpa in mapeamento_variacoes_real: return mapeamento_variacoes_real[etapa_limpa]
    if etapa_limpa in nome_completo_para_sigla: return nome_completo_para_sigla[etapa_limpa]
    if etapa_limpa in sigla_para_nome_completo: return etapa_limpa
    return 'UNKNOWN'

# --- Funções de Filtragem e Ordenação ---
@st.cache_data
def filtrar_etapas_nao_concluidas(df):
    if df.empty or '% concluído' not in df.columns:
        return df
    
    df_copy = df.copy()
    df_copy['% concluído'] = df_copy['% concluído'].apply(converter_porcentagem)
    df_filtrado = df_copy[df_copy['% concluído'] < 100]
    return df_filtrado

@st.cache_data
def obter_data_meta_assinatura(df_original, empreendimento):
    df_meta = df_original[(df_original['Empreendimento'] == empreendimento) & (df_original['Etapa'] == 'M')]
    
    if df_meta.empty:
        return pd.Timestamp.max
    
    if pd.notna(df_meta['Termino_Prevista'].iloc[0]):
        return df_meta['Termino_Prevista'].iloc[0]
    elif pd.notna(df_meta['Inicio_Prevista'].iloc[0]):
        return df_meta['Inicio_Prevista'].iloc[0]
    elif pd.notna(df_meta['Termino_Real'].iloc[0]):
        return df_meta['Termino_Real'].iloc[0]
    elif pd.notna(df_meta['Inicio_Real'].iloc[0]):
        return df_meta['Inicio_Real'].iloc[0]
    else:
        return pd.Timestamp.max

@st.cache_data
def criar_ordenacao_empreendimentos(df_original):
    empreendimentos_meta = {}
    
    for empreendimento in df_original['Empreendimento'].unique():
        data_meta = obter_data_meta_assinatura(df_original, empreendimento)
        empreendimentos_meta[empreendimento] = data_meta
        # empreendimentos_meta[empreendimento] = data_meta # Removido para usar a linha abaixo
    
    empreendimentos_ordenados = sorted(
        empreendimentos_meta.keys(),
        key=lambda x: empreendimentos_meta[x]
    )
    
    return empreendimentos_ordenados

@st.cache_data
def aplicar_ordenacao_final(df, empreendimentos_ordenados):
    if df.empty:
        return df
    
    ordem_empreendimentos = {emp: idx for idx, emp in enumerate(empreendimentos_ordenados)}
    df['ordem_empreendimento'] = df['Empreendimento'].map(ordem_empreendimentos)
    # df['Empreendimento_Abreviado'] = df['Empreendimento'].apply(abreviar_nome) # Removido para evitar conflito
    
    ordem_etapas = {etapa: idx for idx, etapa in enumerate(ORDEM_ETAPAS_GLOBAL)}
    df['ordem_etapa'] = df['Etapa'].map(ordem_etapas).fillna(len(ordem_etapas))
    
    df_ordenado = df.sort_values(['ordem_empreendimento', 'ordem_etapa']).drop(
        ['ordem_empreendimento', 'ordem_etapa'], axis=1
    )
    
    return df_ordenado.reset_index(drop=True)

@st.cache_data
def aplicar_regra_definicao_modulo(df_completo):
    """
    Aplica a regra de negócio para a etapa 'DEFINIÇÃO DO MÓDULO' (DM).
    Se DM não tem dados reais, mas outra etapa do mesmo empreendimento está 100%,
    define o percentual de DM como 100%.
    """
    # Usaremos a sigla 'DM' para a etapa, conforme seu mapeamento
    ETAPA_MODULO = 'DM'
    
    # Retorna o dataframe original se as colunas necessárias não existirem
    if 'Empreendimento' not in df_completo.columns or '% concluído' not in df_completo.columns:
        return df_completo

    df_modificado = df_completo.copy()
    
    # Itera sobre cada empreendimento individualmente
    for empreendimento in df_modificado['Empreendimento'].unique():
        # Filtra os dados apenas para o empreendimento atual
        indices_empreendimento = df_modificado[df_modificado['Empreendimento'] == empreendimento].index
        
        # Localiza a etapa de Módulo e as outras etapas
        indice_dm = df_modificado[(df_modificado['Empreendimento'] == empreendimento) & (df_modificado['Etapa'] == ETAPA_MODULO)].index
        
        # Verifica se existe alguma outra etapa com 100% concluído
        outras_etapas_100 = df_modificado[(df_modificado['Empreendimento'] == empreendimento) & 
                                         (df_modificado['Etapa'] != ETAPA_MODULO) & 
                                         (df_modificado['% concluído'].astype(str).apply(converter_porcentagem) >= 100)]
        
        # Se a etapa DM existe e não tem Termino_Real e outras etapas estão 100%
        if not indice_dm.empty:
            dm_row = df_modificado.loc[indice_dm[0]]
            
            # Verifica se Termino_Real está vazio/NaN
            termino_real_vazio = pd.isna(dm_row.get('Termino_Real'))
            
            if termino_real_vazio and not outras_etapas_100.empty:
                # Aplica 100% de conclusão
                df_modificado.loc[indice_dm[0], '% concluído'] = 100.0
                # Opcional: Se necessário, você pode querer preencher Inicio_Real e Termino_Real com as datas da primeira etapa 100%
                # Por exemplo, usando a data de Termino_Real da primeira etapa 100%
                # if 'Termino_Real' in outras_etapas_100.columns and pd.notna(outras_etapas_100['Termino_Real'].iloc[0]):
                #     df_modificado.loc[indice_dm[0], 'Termino_Real'] = outras_etapas_100['Termino_Real'].iloc[0]
                pass # Manter apenas a alteração de % concluído por enquanto
                
    return df_modificado

# --- Funções do Novo Gráfico Gantt ---
# REMOVIDO: Função ajustar_datas_com_pulmao conforme solicitado.

def calcular_periodo_datas(df, meses_padding_inicio=1, meses_padding_fim=36):
    if df.empty:
        hoje = datetime.now()
        data_min_default = (hoje - relativedelta(months=meses_padding_inicio)).replace(day=1)
        data_max_default = (hoje + relativedelta(months=meses_padding_fim))
        data_max_default = (data_max_default.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)
        return data_min_default, data_max_default

    datas = []
    colunas_data = ["Inicio_Prevista", "Termino_Prevista", "Inicio_Real", "Termino_Real"]
    for col in colunas_data:
        if col in df.columns:
            datas_validas = pd.to_datetime(df[col], errors='coerce').dropna()
            datas.extend(datas_validas.tolist())

    if not datas:
        return calcular_periodo_datas(pd.DataFrame())

    data_min_real = min(datas)
    data_max_real = max(datas)

    data_inicio_final = (data_min_real - relativedelta(months=meses_padding_inicio)).replace(day=1)
    data_fim_temp = data_max_real + relativedelta(months=meses_padding_fim)
    data_fim_final = (data_fim_temp.replace(day=1) + relativedelta(months=1)) - timedelta(days=1)

    return data_inicio_final, data_fim_final

def calcular_dias_uteis_novo(data_inicio, data_fim):
    # Esta função é a mesma que calcular_dias_uteis, mas mantida para compatibilidade
    return calcular_dias_uteis(data_inicio, data_fim)

def obter_data_meta_assinatura_novo(df_empreendimento):
    # Esta função é a mesma que obter_data_meta_assinatura, mas mantida para compatibilidade
    # No contexto do novo código, a etapa 'M' (Demanda Mínima) é a meta de assinatura
    df_meta = df_empreendimento[df_empreendimento["Etapa"] == "M"]
    if df_meta.empty:
        return None
    
    # MODIFICAÇÃO AQUI: Prioridade alterada para Inicio_Prevista primeiro
    for col in ["Inicio_Prevista", "Termino_Prevista", "Inicio_Real", "Termino_Real"]:
        if col in df_meta.columns and pd.notna(df_meta[col].iloc[0]):
            return pd.to_datetime(df_meta[col].iloc[0])
    return None

# --- CÓDIGO MODIFICADO ---
def converter_dados_para_gantt(df):
    # Conversão explícita de colunas de data para datetime
    for col in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    if df.empty:
        return []

    gantt_data = []

    for empreendimento in df["Empreendimento"].unique():
        df_emp = df[df["Empreendimento"] == empreendimento].copy()

        # DEBUG: Verificar etapas disponíveis
        etapas_disponiveis = df_emp["Etapa"].unique()
        print(f"=== ETAPAS PARA {empreendimento} ===")
        print(f"Etapas disponíveis: {etapas_disponiveis}")
        
        tasks = []
        
        # CORREÇÃO: Garantir que todas as etapas da ORDEM_ETAPAS_GLOBAL sejam incluídas
        # mesmo que não estejam presentes nos dados
        etapas_para_processar = []
        
        for etapa_sigla in ORDEM_ETAPAS_GLOBAL:
            # Verificar se esta etapa existe nos dados
            etapa_data = df_emp[df_emp["Etapa"] == etapa_sigla]
            if not etapa_data.empty:
                # Se existe, adicionar todas as linhas desta etapa
                for idx, row in etapa_data.iterrows():
                    etapas_para_processar.append((etapa_sigla, row))
            else:
                # Se não existe, criar uma linha vazia para manter a ordem
                etapas_para_processar.append((etapa_sigla, None))
        
        print(f"Etapas ordenadas para processamento: {[e[0] for e in etapas_para_processar]}")

        for i, (etapa_sigla, row) in enumerate(etapas_para_processar):
            if row is None:
                # Criar task vazia para etapa que não existe nos dados
                etapa_nome_completo = sigla_para_nome_completo.get(etapa_sigla, etapa_sigla)
                task = {
                    "id": f"t{i}", 
                    "name": etapa_nome_completo,
                    "name_sigla": etapa_sigla,
                    "numero_etapa": i + 1,
                    "start_previsto": None,
                    "end_previsto": None,
                    "start_real": None,
                    "end_real": None,
                    "end_real_original_raw": None,
                    "setor": "Não especificado",
                    "grupo": GRUPO_POR_ETAPA.get(etapa_sigla, "Não especificado"),
                    "progress": 0,
                    "inicio_previsto": "N/D",
                    "termino_previsto": "N/D",
                    "inicio_real": "N/D",
                    "termino_real": "N/D",
                    "duracao_prev_meses": "-",
                    "duracao_real_meses": "-",
                    "vt_text": "-",
                    "vd_text": "-",
                    "status_color_class": 'status-default'
                }
                tasks.append(task)
                continue

            # Processar etapa existente nos dados
            start_date = row.get("Inicio_Prevista")
            end_date = row.get("Termino_Prevista")
            start_real = row.get("Inicio_Real")
            end_real_original = row.get("Termino_Real")

            # Garantir que as datas são objetos datetime
            if pd.notna(start_date): start_date = pd.to_datetime(start_date)
            if pd.notna(end_date): end_date = pd.to_datetime(end_date)
            if pd.notna(start_real): start_real = pd.to_datetime(start_real)
            if pd.notna(end_real_original): end_real_original = pd.to_datetime(end_real_original)
            
            progress = row.get("% concluído", 0)

            etapa_nome_completo = sigla_para_nome_completo.get(etapa_sigla, etapa_sigla)

            # Lógica para tratar datas vazias
            if pd.isna(start_date) or start_date is None: 
                start_date = start_real if pd.notna(start_real) else datetime.now()
            if pd.isna(end_date) or end_date is None: 
                end_date = end_real_original if pd.notna(end_real_original) else (start_date + timedelta(days=30))
            
            # Garante que start_date e end_date são datetime se não forem None
            if pd.notna(start_date): start_date = pd.to_datetime(start_date)
            if pd.notna(end_date): end_date = pd.to_datetime(end_date)

            end_real_visual = end_real_original
            if pd.notna(start_real) and progress < 100 and pd.isna(end_real_original):
                end_real_visual = datetime.now()

            # Mapeamento de Grupo
            grupo = "Não especificado"
            if etapa_sigla in GRUPO_POR_ETAPA:
                grupo = GRUPO_POR_ETAPA[etapa_sigla]

            print(f"Processando: {etapa_sigla} -> {etapa_nome_completo} -> Grupo: {grupo}")

            # Cálculos de duração
            dur_prev_meses = None
            if pd.notna(start_date) and pd.notna(end_date):
                duracao_prevista_uteis = calculate_business_days(start_date, end_date)
                dur_prev_meses = duracao_prevista_uteis / 21.75

            dur_real_meses = None
            if pd.notna(start_real) and pd.notna(end_real_original):
                duracao_real_uteis = calculate_business_days(start_real, end_real_original)
                dur_real_meses = duracao_real_uteis / 21.75

            # Variações
            vt = calculate_business_days(end_date, end_real_original)
            duracao_prevista_uteis = calculate_business_days(start_date, end_date)
            duracao_real_uteis = calculate_business_days(start_real, end_real_original)
            
            vd = None
            if pd.notna(duracao_real_uteis) and pd.notna(duracao_prevista_uteis):
                vd = duracao_real_uteis - duracao_prevista_uteis

            # Lógica de Cor do Status
            status_color_class = 'status-default'
            hoje = pd.Timestamp.now().normalize()

            if progress == 100:
                if pd.notna(end_real_original) and pd.notna(end_date):
                    if end_real_original <= end_date:
                        status_color_class = 'status-green'
                    else:
                        status_color_class = 'status-red'
            elif progress < 100 and pd.notna(start_real) and pd.notna(end_real_original) and (end_real_original < hoje):
                status_color_class = 'status-yellow'

            task = {
                "id": f"t{i}", 
                "name": etapa_nome_completo,
                "name_sigla": etapa_sigla,
                "numero_etapa": i + 1,
                "start_previsto": start_date.strftime("%Y-%m-%d") if pd.notna(start_date) and start_date is not None else None,
                "end_previsto": end_date.strftime("%Y-%m-%d") if pd.notna(end_date) and end_date is not None else None,
                "start_real": pd.to_datetime(start_real).strftime("%Y-%m-%d") if pd.notna(start_real) else None,
                "end_real": pd.to_datetime(end_real_visual).strftime("%Y-%m-%d") if pd.notna(end_real_visual) else None,
                "end_real_original_raw": pd.to_datetime(end_real_original).strftime("%Y-%m-%d") if pd.notna(end_real_original) else None,
                "setor": row.get("SETOR", "Não especificado"),
                "grupo": grupo,
                "progress": int(progress),
                "inicio_previsto": start_date.strftime("%d/%m/%y") if pd.notna(start_date) and start_date is not None else "N/D",
                "termino_previsto": end_date.strftime("%d/%m/%y") if pd.notna(end_date) and end_date is not None else "N/D",
                "inicio_real": pd.to_datetime(start_real).strftime("%d/%m/%y") if pd.notna(start_real) else "N/D",
                "termino_real": pd.to_datetime(end_real_original).strftime("%d/%m/%y") if pd.notna(end_real_original) else "N/D",
                "duracao_prev_meses": f"{dur_prev_meses:.1f}".replace('.', ',') if dur_prev_meses is not None else "-",
                "duracao_real_meses": f"{dur_real_meses:.1f}".replace('.', ',') if dur_real_meses is not None else "-",
                "vt_text": f"{int(vt):+d}d" if pd.notna(vt) else "-",
                "vd_text": f"{int(vd):+d}d" if pd.notna(vd) else "-",
                "status_color_class": status_color_class
            }
            tasks.append(task)

        data_meta = obter_data_meta_assinatura_novo(df_emp)

        project = {
            "id": f"p{len(gantt_data)}", 
            "name": empreendimento,
            "tasks": tasks,
            "meta_assinatura_date": data_meta.strftime("%Y-%m-%d") if data_meta else None
        }
        gantt_data.append(project)

    return gantt_data

def converter_porcentagem(valor):
    if pd.isna(valor) or valor == "":
        return 0.0
    if isinstance(valor, str):
        valor = "".join(c for c in valor if c.isdigit() or c in [".", ","]).replace(",", ".").strip()
        if not valor: return 0.0
    try:
        val_float = float(valor)
        return val_float * 100 if val_float <= 1 else val_float
    except (ValueError, TypeError):
        return 0.0

def formatar_data(data):
    return data.strftime("%d/%m/%y") if pd.notna(data) else "N/D"

def calcular_dias_uteis(inicio, fim):
    if pd.notna(inicio) and pd.notna(fim):
        data_inicio = np.datetime64(inicio.date())
        data_fim = np.datetime64(fim.date())
        return np.busday_count(data_inicio, data_fim) + 1
    return 0

def calcular_variacao_termino(termino_real, termino_previsto):
    if pd.notna(termino_real) and pd.notna(termino_previsto):
        diferenca_dias = calculate_business_days(termino_previsto, termino_real)
        if pd.isna(diferenca_dias): diferenca_dias = 0
        if diferenca_dias > 0: return f"V: +{diferenca_dias}d", "#89281d"
        elif diferenca_dias < 0: return f"V: {diferenca_dias}d", "#0b803c"
        else: return "V: 0d", "#666666"
    else:
        return "V: -", "#666666"

def calcular_porcentagem_correta(grupo):
    if "% concluído" not in grupo.columns: return 0.0
    porcentagens = grupo["% concluído"].astype(str).apply(converter_porcentagem)
    porcentagens = porcentagens[(porcentagens >= 0) & (porcentagens <= 100)]
    if porcentagens.empty: return 0.0
    porcentagens_validas = porcentagens.dropna()
    if porcentagens_validas.empty: return 0.0
    return porcentagens_validas.mean()

def padronizar_etapa(etapa_str):
    """
    Função robusta para padronizar o nome da etapa.
    """
    if pd.isna(etapa_str) or etapa_str == "" or etapa_str == "Não especificado":
        return "Não especificado"
    
    # Converter para string e limpar
    etapa_limpa = str(etapa_str).strip().upper()
    
    # Mapeamento direto dos valores que vêm do Smartsheet para as siglas da ORDEM_ETAPAS_GLOBAL
    mapeamento_direto = {
    'DEFINIÇÃO DO MÓDULO': 'DM', 'DOCUMENTAÇÃO': 'DOC', 'LAE': 'LAE', 'MEMORIAL': 'MEM',
    'CONTRATAÇÃO': 'CONT', 'PRÉ-ASSINATURA': 'ASS', 'ASS': 'ASS', '1º PJ': 'PJ',
    'PLANEJamento': 'DM', 'MEMORIAL DE INCORPORAÇÃO': 'MEM', 'EMISSÃO DO LAE': 'LAE',
    'CONTESTAÇÃO': 'LAE', 'DJE': 'CONT', 'ANÁLISE DE RISCO': 'CONT', 'MORAR BEM': 'ASS',
    'SEGUROS': 'ASS', 'ATESTE': 'ASS', 'DEMANDA MÍNIMA': 'M', 'DEMANDA MINIMA': 'M',
    'PRIMEIRO PJ': 'PJ',
    }
    
    # Tentar mapeamento direto primeiro
    if etapa_limpa in mapeamento_direto:
        return mapeamento_direto[etapa_limpa]
    
    # Verificar se já é uma sigla válida da ordem global
    if etapa_limpa in ORDEM_ETAPAS_GLOBAL:
        return etapa_limpa
    
    # Tentar encontrar correspondência parcial
    for sigla in ORDEM_ETAPAS_GLOBAL:
        if sigla in etapa_limpa or etapa_limpa in sigla:
            return sigla
    
    # Se não encontrar, retornar original (será colocado no final)
    print(f"⚠️ Etapa não mapeada: '{etapa_str}' -> '{etapa_limpa}'")
    return etapa_limpa


# --- Funções de Filtragem e Ordenação ---
def filtrar_etapas_nao_concluidas_func(df):
    if df.empty or "% concluído" not in df.columns: return df
    df_copy = df.copy()
    df_copy["% concluído"] = df_copy["% concluído"].apply(converter_porcentagem)
    return df_copy[df_copy["% concluído"] < 100]

def obter_data_meta_assinatura(df_original, empreendimento):
    df_meta = df_original[(df_original["Empreendimento"] == empreendimento) & (df_original["Etapa"] == "DEM.MIN")]
    if df_meta.empty: return pd.Timestamp.max
    for col in ["Termino_Prevista", "Inicio_Prevista", "Termino_Real", "Inicio_Real"]:
        if col in df_meta.columns and pd.notna(df_meta[col].iloc[0]): return df_meta[col].iloc[0]
    return pd.Timestamp.max

def converter_nome_empreendimento(nome):
    """
    Converte siglas de empreendimentos para nomes completos.
    """
    if pd.isna(nome):
        return "Não especificado"
    
    nome_str = str(nome).strip()
    return sigla_para_nome_completo_emp.get(nome_str, nome_str)

def criar_ordenacao_empreendimentos(df_original):
    """
    Cria uma lista ordenada dos nomes COMPLETOS dos empreendimentos
    com base na data da meta de assinatura (DEMANDA MÍNIMA).
    """
    # Aplica conversão aos nomes antes de criar a ordenação
    df_convertido = df_original.copy()
    df_convertido["Empreendimento"] = df_convertido["Empreendimento"].apply(converter_nome_empreendimento)
    
    empreendimentos_meta = {emp: obter_data_meta_assinatura(df_convertido, emp)
                           for emp in df_convertido["Empreendimento"].unique()}
    
    # Retorna a lista de nomes COMPLETOS ordenados pela data meta
    return sorted(empreendimentos_meta.keys(), key=empreendimentos_meta.get)


def aplicar_ordenacao_final(df, empreendimentos_ordenados):
    if df.empty: 
        return df
        
    # Garantir que as etapas estão no formato correto (siglas)
    df['Etapa'] = df['Etapa'].apply(padronizar_etapa)
    
    # Ordenação por empreendimento
    ordem_empreendimentos = {emp: idx for idx, emp in enumerate(empreendimentos_ordenados)}
    df["ordem_empreendimento"] = df["Empreendimento"].map(ordem_empreendimentos).fillna(len(empreendimentos_ordenados))
    
    # Ordenação por etapa - usar a ordem das SIGLAS
    ordem_etapas = {etapa: idx for idx, etapa in enumerate(ORDEM_ETAPAS_GLOBAL)}
    df["ordem_etapa"] = df["Etapa"].map(ordem_etapas).fillna(len(ordem_etapas))
    
    # Ordenar
    df_ordenado = df.sort_values(["ordem_empreendimento", "ordem_etapa"]).drop(
        ["ordem_empreendimento", "ordem_etapa"], axis=1
    )
    
    return df_ordenado.reset_index(drop=True)

def verificar_ordem_etapas(gantt_data):
    """Função para verificar a ordem das etapas nos dados do Gantt"""
    print("\n=== VERIFICAÇÃO DA ORDEM DAS ETAPAS NO GANTT ===")
    
    for project in gantt_data:
        print(f"\nProjeto: {project['name']}")
        etapas_no_gantt = [task['name'] for task in project['tasks']]
        print(f"Etapas no Gantt: {etapas_no_gantt}")
        
        # Verificar se a ordem está correta
        etapas_ordenadas_corretamente = True
        for i, etapa_gantt in enumerate(etapas_no_gantt):
            if i < len(ORDEM_ETAPAS_NOME_COMPLETO):
                etapa_esperada = ORDEM_ETAPAS_NOME_COMPLETO[i]
                if etapa_gantt != etapa_esperada:
                    print(f"⚠️ ORDEM INCORRETA: Posição {i+1} - Esperado: '{etapa_esperada}', Encontrado: '{etapa_gantt}'")
                    etapas_ordenadas_corretamente = False
        
        if etapas_ordenadas_corretamente:
            print("✅ Etapas ordenadas corretamente!")
        else:
            print("❌ Problema na ordenação das etapas!")

def debug_ordem_etapas(gantt_data):
    """Função simples para debug da ordem das etapas"""
    print("\n" + "="*50)
    print("DEBUG DA ORDEM DAS ETAPAS")
    print("="*50)
    
    for project in gantt_data:
        print(f"\n📊 Projeto: {project['name']}")
        etapas_no_gantt = [task['name'] for task in project['tasks']]
        siglas_no_gantt = [task.get('name_sigla', 'N/A') for task in project['tasks']]
        
        print(f"📋 Etapas no Gantt ({len(etapas_no_gantt)}):")
        for i, (etapa, sigla) in enumerate(zip(etapas_no_gantt, siglas_no_gantt)):
            print(f"   {i+1:2d}. {etapa} ({sigla})")
        
        # Verificar se a ordem está correta
        problemas = []
        for i, task in enumerate(project['tasks']):
            sigla = task.get('name_sigla', '')
            if sigla in ORDEM_ETAPAS_GLOBAL:
                posicao_esperada = ORDEM_ETAPAS_GLOBAL.index(sigla)
                if i != posicao_esperada:
                    problemas.append(f"Posição {i+1}: '{sigla}' deveria estar na posição {posicao_esperada+1}")
        
        if problemas:
            print("❌ PROBLEMAS DE ORDEM:")
            for problema in problemas:
                print(f"   ⚠️ {problema}")
        else:
            print("✅ Ordem das etapas CORRETA!")
    
    print("="*50)

# --- Funções de Geração de Relatório ---

def gerar_relatorio_txt(gantt_data):
    """
    Extrai as datas e etapas do gantt_data e formata em um relatório de texto simples.
    """
    relatorio = ["\n*** RELATÓRIO DE DATAS E ETAPAS ***\n"]
    
    for project in gantt_data:
        relatorio.append(f"\n--- EMPREENDIMENTO: {project['name']} ---\n")
        
        # Cabeçalho da tabela
        relatorio.append(f"{'Etapa':<30} | {'Início Prev.':<12} | {'Término Prev.':<12} | {'Início Real':<12} | {'Término Real':<12} | {'% Concluído':<12} | {'VT (dias)':<10}")
        relatorio.append("-" * 100)
        
        for task in project['tasks']:
            # Extrai os dados formatados
            etapa = task.get('name', 'N/D')
            inicio_prev = task.get('inicio_previsto', 'N/D')
            termino_prev = task.get('termino_previsto', 'N/D')
            inicio_real = task.get('inicio_real', 'N/D')
            termino_real = task.get('termino_real', 'N/D')
            progresso = f"{task.get('progress', 0)}%"
            vt = task.get('vt_text', '-')
            
            # Formata a linha
            linha = f"{etapa[:30]:<30} | {inicio_prev:<12} | {termino_prev:<12} | {inicio_real:<12} | {termino_real:<12} | {progresso:<12} | {vt:<10}"
            relatorio.append(linha)
            
    return "\n".join(relatorio)

# --- *** FUNÇÃO gerar_gantt_por_projeto MODIFICADA *** ---
def gerar_gantt_por_projeto(df, tipo_visualizacao, df_original_para_ordenacao, pulmao_status, pulmao_meses):
        """
        Gera um único gráfico de Gantt com todos os projetos.
        """
        
        # --- Processar DF SEM PULMÃO ---
        df_sem_pulmao = df.copy()
        df_gantt_sem_pulmao = df_sem_pulmao.copy()

        # **CORREÇÃO: Garantir que as colunas de datas sejam datetime ANTES da agregação**
        for col in ["Inicio_Prevista", "Termino_Prevista", "Inicio_Real", "Termino_Real"]:
            if col in df_gantt_sem_pulmao.columns:
                df_gantt_sem_pulmao[col] = pd.to_datetime(df_gantt_sem_pulmao[col], errors="coerce")

        if "% concluído" not in df_gantt_sem_pulmao.columns:
            df_gantt_sem_pulmao["% concluído"] = 0
        # A conversão já foi feita no load_data, então apenas garantimos 0 nos NaNs
        df_gantt_sem_pulmao["% concluído"] = df_gantt_sem_pulmao["% concluído"].fillna(0)

        # Agrega os dados (usando siglas)
        df_gantt_agg_sem_pulmao = df_gantt_sem_pulmao.groupby(['Empreendimento', 'Etapa']).agg(
            Inicio_Prevista=('Inicio_Prevista', 'min'),
            Termino_Prevista=('Termino_Prevista', 'max'),
            Inicio_Real=('Inicio_Real', 'min'),
            Termino_Real=('Termino_Real', 'max'),
            **{'% concluído': ('% concluído', 'mean')},
            SETOR=('SETOR', 'first')
        ).reset_index()

        # CORREÇÃO: Manter as siglas para o processamento interno
        # A conversão para nome completo será feita dentro da função converter_dados_para_gantt
        
        # Mapear o SETOR e GRUPO
        df_gantt_agg_sem_pulmao["SETOR"] = df_gantt_agg_sem_pulmao["Etapa"].map(SETOR_POR_ETAPA).fillna(df_gantt_agg_sem_pulmao["SETOR"])
        df_gantt_agg_sem_pulmao["GRUPO"] = df_gantt_agg_sem_pulmao["Etapa"].map(GRUPO_POR_ETAPA).fillna("Não especificado")

        # Converte o DataFrame FILTRADO agregado em lista de projetos
        gantt_data_base = converter_dados_para_gantt(df_gantt_agg_sem_pulmao)

        # --- SE NÃO HÁ DADOS FILTRADOS, NÃO FAZ NADA ---
        if not gantt_data_base:
            st.warning("Nenhum dado disponível para exibir.")
            return

        # --- Prepara opções de filtro ---
        filter_options = {
            "setores": ["Todos"] + sorted(list(SETOR.keys())),
            "grupos": ["Todos"] + sorted(list(GRUPOS.keys())),
            "etapas": ["Todas"] + ORDEM_ETAPAS_NOME_COMPLETO
        }

        # *** CORREÇÃO: USAR O PRIMEIRO PROJETO DA LISTA EM VEZ DE CRIAR "TODOS OS EMPREENDIMENTOS" ***
        if gantt_data_base:
            # Usa o primeiro projeto da lista
            project = gantt_data_base[0]
            project_id = f"p_{project['name'].replace(' ', '_').lower()}"
            correct_project_index_for_js = 0
        else:
            return

        # Filtra o DF agregado para cálculo de data_min/max
        df_para_datas = df_gantt_agg_sem_pulmao

        tasks_base_data = project['tasks'] if project else []

        data_min_proj, data_max_proj = calcular_periodo_datas(df_para_datas)
        total_meses_proj = ((data_max_proj.year - data_min_proj.year) * 12) + (data_max_proj.month - data_min_proj.month) + 1

        num_tasks = len(project["tasks"]) if project else 0
            # Converte o DataFrame FILTRADO agregado em lista de projetos
        gantt_data_base = converter_dados_para_gantt(df_gantt_agg_sem_pulmao)
        
        # DEBUG SIMPLES da ordem
        debug_ordem_etapas(gantt_data_base)

        if num_tasks == 0:
            st.warning("Nenhuma tarefa disponível para exibir.")
            return
        
        # Reduz o fator de multiplicação para evitar excesso de espaço
        altura_gantt = max(400, min(800, (num_tasks * 25) + 200))  # Limita a altura máxima

        # --- Geração do HTML ---
        gantt_html = f"""
        <!DOCTYPE html>
            <html lang="pt-BR">
            <head>
                <meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                
                <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/virtual-select-plugin@1.0.39/dist/virtual-select.min.css">
                
                <style>
                    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                    html, body {{ width: 100%; height: 100%; font-family: 'Segoe UI', sans-serif; background-color: #f5f5f5; color: #333; overflow: hidden; }}
                    .gantt-container {{ width: 100%; height: 100%; background-color: white; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden; position: relative; display: flex; flex-direction: column; }}
                    .gantt-main {{ display: flex; flex: 1; overflow: hidden; }}
                    .gantt-sidebar-wrapper {{ width: 680px; display: flex; flex-direction: column; flex-shrink: 0; transition: width 0.3s ease-in-out; border-right: 2px solid #e2e8f0; overflow: hidden; }}
                    .gantt-sidebar-header {{ background: linear-gradient(135deg, #4a5568, #2d3748); display: flex; flex-direction: column; height: 60px; flex-shrink: 0; }}
                    .project-title-row {{ display: flex; justify-content: space-between; align-items: center; padding: 0 15px; height: 30px; color: white; font-weight: 600; font-size: 14px; }}
                    .toggle-sidebar-btn {{ background: rgba(255,255,255,0.2); border: none; color: white; width: 24px; height: 24px; border-radius: 5px; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; transition: background-color 0.2s, transform 0.3s ease-in-out; }}
                    .toggle-sidebar-btn:hover {{ background: rgba(255,255,255,0.4); }}
                    .sidebar-grid-header-wrapper {{ display: grid; grid-template-columns: 30px 1fr; color: #d1d5db; font-size: 9px; font-weight: 600; text-transform: uppercase; height: 30px; align-items: center; }}
                    .sidebar-grid-header {{ display: grid; grid-template-columns: 2.5fr 0.9fr 0.9fr 0.6fr 0.9fr 0.9fr 0.6fr 0.5fr 0.6fr 0.6fr; padding: 0 10px; align-items: center; }}
                    .sidebar-row {{ display: grid; grid-template-columns: 2.5fr 0.9fr 0.9fr 0.6fr 0.9fr 0.9fr 0.6fr 0.5fr 0.6fr 0.6fr; border-bottom: 1px solid #eff2f5; height: 30px; padding: 0 10px; background-color: white; transition: all 0.2s ease-in-out; }}
                    .sidebar-cell {{ display: flex; align-items: center; justify-content: center; font-size: 11px; color: #4a5568; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 0 8px; border: none; }}
                    .header-cell {{ text-align: center; }}
                    .header-cell.task-name-cell {{ text-align: left; }}
                    .gantt-sidebar-content {{ background-color: #f8f9fa; flex: 1; overflow-y: auto; overflow-x: hidden; }}
                    
                    /* Estilos para agrupamento */
                    .main-task-row {{ font-weight: 600; }}
                    .main-task-row.has-subtasks {{ cursor: pointer; }}
                    .expand-collapse-btn {{
                        background: none;
                        border: none;
                        cursor: pointer;
                        width: 20px;
                        height: 20px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 12px;
                        color: #4a5568;
                        margin-right: 5px;
                    }}
                    .subtask-row {{ 
                        display: none;
                        background-color: #f8fafc;
                        padding-left: 40px;
                    }}
                    .subtask-row.visible {{ display: grid; }}
                    .gantt-subtask-row {{ 
                        display: none;
                        background-color: #f8fafc;
                    }}
                    .gantt-subtask-row.visible {{ 
                        display: block !important;
                    }}
                    
                    /* Estilo para barras de etapas pai quando subetapas estão expandidas */
                    .gantt-bar.parent-task-real.expanded {{
                        background-color: transparent !important;
                        border: 2px solid;
                        box-shadow: none;
                    }}
                    .gantt-bar.parent-task-real.expanded .bar-label {{
                        color: #000000 !important;
                        text-shadow: 0 1px 2px rgba(255,255,255,0.8);
                    }}
                    
                    .sidebar-group-wrapper {{
                        display: flex;
                        border-bottom: 1px solid #e2e8f0;
                    }}
                    .gantt-sidebar-content > .sidebar-group-wrapper:last-child {{ border-bottom: none; }}
                    .sidebar-group-title-vertical {{
                        width: 30px; background-color: #f8fafc; color: #4a5568;
                        font-size: 8px; 
                        font-weight: 700; text-transform: uppercase;
                        display: flex; align-items: center; justify-content: center;
                        writing-mode: vertical-rl; transform: rotate(180deg);
                        flex-shrink: 0; border-right: 1px solid #e2e8f0;
                        text-align: center; white-space: nowrap; overflow: hidden;
                        text-overflow: ellipsis; padding: 5px 0; letter-spacing: -0.5px;
                        align-self: flex-start;
                    }}
                    .sidebar-group-spacer {{ display: none; }}
                    .sidebar-rows-container {{ flex-grow: 1; }}
                    .sidebar-row.odd-row {{ background-color: #fdfdfd; }}
                    .sidebar-rows-container .sidebar-row:last-child {{ border-bottom: none; }}
                    .sidebar-row:hover {{ background-color: #f5f8ff; }}
                    .sidebar-cell.task-name-cell {{ justify-content: flex-start; font-weight: 600; color: #2d3748; }}
                    .sidebar-cell.status-green {{ color: #1E8449; font-weight: 700; }}
                    .sidebar-cell.status-red    {{ color: #C0392B; font-weight: 700; }}
                    .sidebar-cell.status-yellow{{ color: #B9770E; font-weight: 700; }}
                    .sidebar-cell.status-default{{ color: #566573; font-weight: 700; }}
                    .sidebar-row .sidebar-cell:nth-child(2),
                    .sidebar-row .sidebar-cell:nth-child(3),
                    .sidebar-row .sidebar-cell:nth-child(4),
                    .sidebar-row .sidebar-cell:nth-child(5),
                    .sidebar-row .sidebar-cell:nth-child(6),
                    .sidebar-row .sidebar-cell:nth-child(7),
                    .sidebar-row .sidebar-cell:nth-child(8),
                    .sidebar-row .sidebar-cell:nth-child(9),
                    .sidebar-row .sidebar-cell:nth-child(10) {{ font-size: 8px; }}
                    .gantt-row-spacer, .sidebar-row-spacer {{
                        height: 15px;
                        border: none;
                        border-bottom: 1px solid #e2e8f0; 
                        box-sizing: border-box; 
                    }}
                    .gantt-row-spacer {{ background-color: #ffffff; position: relative; z-index: 5; }}
                    .sidebar-row-spacer {{ background-color: #f8f9fa; }}
                    .gantt-sidebar-wrapper.collapsed {{ width: 250px; }}
                    .gantt-sidebar-wrapper.collapsed .sidebar-grid-header, .gantt-sidebar-wrapper.collapsed .sidebar-row {{ grid-template-columns: 1fr; padding: 0 15px 0 10px; }}
                    .gantt-sidebar-wrapper.collapsed .header-cell:not(.task-name-cell), .gantt-sidebar-wrapper.collapsed .sidebar-cell:not(.task-name-cell) {{ display: none; }}
                    .gantt-sidebar-wrapper.collapsed .toggle-sidebar-btn {{ transform: rotate(180deg); }}
                    .gantt-chart-content {{ flex: 1; overflow: auto; position: relative; background-color: white; user-select: none; cursor: grab; }}
                    .gantt-chart-content.active {{ cursor: grabbing; }}
                    .chart-container {{ position: relative; min-width: {total_meses_proj * 60}px; }}
                    .chart-header {{ background: linear-gradient(135deg, #4a5568, #2d3748); color: white; height: 60px; position: sticky; top: 0; z-index: 9; display: flex; flex-direction: column; }}
                    .year-header {{ height: 30px; display: flex; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.2); }}
                    .year-section {{ text-align: center; font-weight: 600; font-size: 12px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.1); height: 100%; border-right: 1px solid rgba(255,255,255,0.3); box-sizing: border-box; }}
                    .month-header {{ height: 30px; display: flex; align-items: center; }}
                    .month-cell {{ width: 60px; height: 30px; border-right: 1px solid rgba(255,255,255,0.2); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 500; }}
                    .chart-body {{ position: relative; min-height: auto; background-size: 60px 60px; background-image: linear-gradient(to right, #f8f9fa 1px, transparent 1px); }}
                    .gantt-row {{ position: relative; height: 30px; border-bottom: 1px solid #eff2f5; background-color: white; }}
                    .gantt-bar {{ position: absolute; height: 14px; top: 8px; border-radius: 3px; cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; padding: 0 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    .gantt-bar-overlap {{ position: absolute; height: 14px; top: 8px; background-image: linear-gradient(45deg, rgba(0, 0, 0, 0.25) 25%, transparent 25%, transparent 50%, rgba(0, 0, 0, 0.25) 50%, rgba(0, 0, 0, 0.25) 75%, transparent 75%, transparent); background-size: 8px 8px; z-index: 9; pointer-events: none; border-radius: 3px; }}
                    .gantt-bar:hover {{ transform: translateY(-1px) scale(1.01); box-shadow: 0 4px 8px rgba(0,0,0,0.2); z-index: 10 !important; }}
                    .gantt-bar.previsto {{ z-index: 7; }}
                    .gantt-bar.real {{ z-index: 8; }}
                    .bar-label {{ font-size: 8px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-shadow: 0 1px 2px rgba(0,0,0,0.4); }}
                    .gantt-bar.real .bar-label {{ color: white; }}
                    .gantt-bar.previsto .bar-label {{ color: #6C6C6C; }}
                    .tooltip {{ position: fixed; background-color: #2d3748; color: white; padding: 6px 10px; border-radius: 4px; font-size: 11px; z-index: 1000; box-shadow: 0 2px 8px rgba(0,0,0,0.3); pointer-events: none; opacity: 0; transition: opacity 0.2s ease; max-width: 220px; }}
                    .tooltip.show {{ opacity: 1; }}
                    .today-line {{ position: absolute; top: 60px; bottom: 0; width: 1px; background-color: #fdf1f1; z-index: 5; box-shadow: 0 0 1px rgba(229, 62, 62, 0.6); }}
                    .month-divider {{ position: absolute; top: 60px; bottom: 0; width: 1px; background-color: #fcf6f6; z-index: 4; pointer-events: none; }}
                    .month-divider.first {{ background-color: #eeeeee; width: 1px; }}
                    .meta-line {{ position: absolute; top: 60px; bottom: 0; width: 2px; border-left: 2px dashed #108318; z-index: 5; box-shadow: 0 0 1px rgba(142, 68, 173, 0.6); }}
                    .meta-line-label {{ position: absolute; top: 65px; background-color: #108318; color: white; padding: 2px 5px; border-radius: 4px; font-size: 9px; font-weight: 600; white-space: nowrap; z-index: 8; transform: translateX(-50%); }}
                    .gantt-chart-content, .gantt-sidebar-content {{
                        scrollbar-width: thin;
                        scrollbar-color: transparent transparent;
                    }}
                    .gantt-chart-content:hover, .gantt-sidebar-content:hover {{
                        scrollbar-color: #d1d5db transparent;
                    }}
                    .gantt-chart-content::-webkit-scrollbar,
                    .gantt-sidebar-content::-webkit-scrollbar {{
                        height: 8px;
                        width: 8px;
                    }}
                    .gantt-chart-content::-webkit-scrollbar-track,
                    .gantt-sidebar-content::-webkit-scrollbar-track {{
                        background: transparent;
                    }}
                    .gantt-chart-content::-webkit-scrollbar-thumb,
                    .gantt-sidebar-content::-webkit-scrollbar-thumb {{
                        background-color: transparent;
                        border-radius: 4px;
                    }}
                    .gantt-chart-content:hover::-webkit-scrollbar-thumb,
                    .gantt-sidebar-content:hover::-webkit-scrollbar-thumb {{
                        background-color: #d1d5db;
                    }}
                    .gantt-chart-content:hover::-webkit-scrollbar-thumb:hover,
                    .gantt-sidebar-content:hover::-webkit-scrollbar-thumb:hover {{
                        background-color: #a8b2c1;
                    }}
                    .gantt-toolbar {{
                        position: absolute; top: 10px; right: 10px;
                        z-index: 100;
                        display: flex;
                        flex-direction: column;
                        gap: 5px;
                        background: rgba(45, 55, 72, 0.9); /* Cor de fundo escura para minimalismo */
                        border-radius: 6px;
                        padding: 5px;
                        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                    }}
                    .toolbar-btn {{
                        background: none;
                        border: none;
                        width: 36px;
                        height: 36px;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 20px;
                        color: white;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        transition: background-color 0.2s, box-shadow 0.2s;
                        padding: 0;
                    }}
                    .toolbar-btn:hover {{
                        background-color: rgba(255, 255, 255, 0.1);
                        box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.2);
                    }}
                    .toolbar-btn.is-fullscreen {{
                        background-color: #3b82f6; /* Cor de destaque para o botão ativo */
                        box-shadow: 0 0 0 2px #3b82f6;
                    }}
                    .toolbar-btn.is-fullscreen:hover {{
                        background-color: #2563eb;
                    }}
                    .floating-filter-menu {{
                        display: none;
                        position: absolute;
                        top: 10px; right: 50px; /* Ajuste a posição para abrir ao lado da barra de ferramentas */
                        width: 280px;
                        background: white;
                        border-radius: 8px;
                        box-shadow: 0 5px 15px rgba(0,0,0,0.3);
                        z-index: 99;
                        padding: 15px;
                        border: 1px solid #e2e8f0;
                    }}
                    .floating-filter-menu.is-open {{
                        display: block;
                    }}
                    .filter-group {{ margin-bottom: 12px; }}
                    .filter-group label {{
                        display: block;
                        font-size: 11px; font-weight: 600;
                        color: #4a5568; margin-bottom: 4px;
                        text-transform: uppercase;
                    }}
                    .filter-group select, .filter-group input[type=number] {{
                        width: 100%;
                        padding: 6px 8px;
                        border: 1px solid #cbd5e0;
                        border-radius: 4px;
                        font-size: 13px;
                    }}
                    .filter-group-radio, .filter-group-checkbox {{
                        display: flex; align-items: center;
                        padding: 5px 0;
                    }}
                    .filter-group-radio input, .filter-group-checkbox input {{
                        width: auto; margin-right: 8px;
                    }}
                    .filter-group-radio label, .filter-group-checkbox label {{
                        font-size: 13px; font-weight: 500;
                        color: #2d3748; margin-bottom: 0; text-transform: none;
                    }}
                    .filter-apply-btn {{
                        width: 100%; padding: 8px; font-size: 14px; font-weight: 600;
                        color: white; background-color: #2d3748;
                        border: none; border-radius: 4px; cursor: pointer;
                        margin-top: 5px;
                    }}

                    .floating-filter-menu .vscomp-toggle-button {{
                        border: 1px solid #cbd5e0;
                        border-radius: 4px;
                        padding: 6px 8px;
                        font-size: 13px;
                        min-height: 30px;
                    }}
                    .floating-filter-menu .vscomp-options {{
                        font-size: 13px;
                    }}
                    .floating-filter-menu .vscomp-option {{
                        min-height: 30px;
                    }}
                    .floating-filter-menu .vscomp-search-input {{
                        height: 30px;
                        font-size: 13px;
                    }}

                    /* ==== RADIAL CONTEXT MENU ==== */
                    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
                    
                    #radial-menu {{
                        position: fixed;
                        z-index: 2147483647;
                        display: none;
                        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                    }}

                    .radial-menu-wrapper {{
                        position: relative;
                        width: 170px;
                        height: 170px;
                    }}

                    .radial-center {{
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        width: 28px;
                        height: 28px;
                        border: 2px solid #007AFF;
                        border-radius: 50%;
                        background: transparent;
                        cursor: pointer;
                        transition: all 0.2s ease;
                        z-index: 10;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}

                    .radial-center:hover {{
                        transform: translate(-50%, -50%) scale(1.1);
                        border-width: 3px;
                    }}

                    .radial-background-circle {{
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        width: 90px;
                        height: 90px;
                        border: 2px solid #f0f0f0;
                        border-radius: 50%;
                        background: transparent;
                        z-index: 1;
                    }}

                    .radial-item {{
                        position: absolute;
                        width: 22px;
                        height: 22px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        cursor: pointer;
                        transition: all 0.2s ease;
                        z-index: 5;
                        background: white;
                        border: 1.5px solid #f0f0f0;
                        border-radius: 5px;
                        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
                    }}

                    .radial-item:hover {{
                        background: #f5f5f5;
                        transform: scale(1.1);
                        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);
                        border-color: #007AFF;
                    }}

                    .radial-item svg {{
                        width: 14px;
                        height: 14px;
                        transition: all 0.2s ease;
                        fill: #333333;
                        stroke: #333333;
                    }}

                    .radial-item:hover svg {{
                        fill: #007AFF;
                        stroke: #007AFF;
                    }}

                    /* Modo de Foco - Escurecer barras */
                    .gantt-bar.focus-mode {{
                        filter: grayscale(100%) brightness(0.4) !important;
                        opacity: 0.5 !important;
                        transition: all 0.3s ease;
                    }}

                    .gantt-bar.focus-mode.focused {{
                        filter: none !important;
                        opacity: 1 !important;
                    }}

                    .radial-tooltip {{
                        position: absolute;
                        padding: 3px 6px;
                        border-radius: 10px;
                        font-size: 8px;
                        font-weight: 500;
                        white-space: nowrap;
                        display: flex;
                        align-items: center;
                        gap: 5px;
                        pointer-events: none;
                        transition: background 0.2s ease, color 0.2s ease;
                        z-index: 15;
                        background: #f5f5f5;
                        color: #333;
                    }}

                    .radial-item:hover + .radial-tooltip {{
                        background: #007AFF;
                        color: white;
                    }}

                    .radial-item:hover + .radial-tooltip .tooltip-badge {{
                        background: white;
                        color: #007AFF;
                    }}

                    .radial-item:hover + .radial-tooltip.yellow-tooltip {{
                        background: #FFC107 !important;
                        color: #333 !important;
                    }}

                    .radial-item:hover + .radial-tooltip.yellow-tooltip .tooltip-badge {{
                        background: #333;
                        color: #FFC107;
                    }}

                    .tooltip-badge {{
                        padding: 2px 5px;
                        border-radius: 4px;
                        font-size: 8px;
                        font-weight: 600;
                        min-width: 14px;
                        text-align: center;
                        font-family: 'SF Mono', Monaco, 'Courier New', monospace;
                        background: #e0e0e0;
                        color: #666;
                    }}

                    @keyframes fadeIn {{
                        from {{ opacity: 0; transform: scale(0.8); }}
                        to {{ opacity: 1; transform: scale(1); }}
                    }}

                    .radial-item, .radial-tooltip {{
                        animation: fadeIn 0.3s ease-out;
                    }}

                    /* ==== FLOATING NOTEPAD ==== */
                    #floating-notepad {{
                        display: none;
                        position: fixed;
                        top: 100px;
                        right: 50px;
                        width: 320px;
                        height: 420px;
                        background: white;
                        border: 1px solid #e8e8e8;
                        border-radius: 16px;
                        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.08);
                        z-index: 9999;
                        flex-direction: column;
                        font-family: 'Inter', sans-serif;
                        overflow: hidden;
                        resize: both;
                        min-width: 250px;
                        min-height: 200px;
                        max-width: 600px;
                        max-height: 80vh;
                    }}

                    .notepad-header {{
                        padding: 14px 18px;
                        background: #2E384A;
                        color: white;
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        cursor: move;
                        user-select: none;
                        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                    }}

                    .notepad-header-title {{
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }}

                    .notepad-header-title svg {{
                        width: 18px;
                        height: 18px;
                        fill: white;
                    }}

                    .notepad-header span {{
                        font-size: 13px;
                        font-weight: 600;
                        letter-spacing: 0.3px;
                    }}

                    .notepad-close {{
                        background: rgba(255, 255, 255, 0.15);
                        border: none;
                        color: white;
                        width: 26px;
                        height: 26px;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 16px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        transition: all 0.2s ease;
                    }}

                    .notepad-close:hover {{
                        background: rgba(255, 255, 255, 0.25);
                        transform: scale(1.1);
                    }}

                    .notepad-content {{
                        flex: 1;
                        padding: 18px;
                        border: none;
                        outline: none;
                        resize: none;
                        font-size: 14px;
                        line-height: 1.6;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                        color: #2d3748;
                    }}

                    .notepad-content::placeholder {{
                        color: #a0aec0;
                    }}

                    .notepad-toolbar {{
                        display: flex;
                        gap: 4px;
                        padding: 8px 12px;
                        background: #f7f9fc;
                        border-bottom: 1px solid #e2e8f0;
                        flex-wrap: wrap;
                    }}

                    .notepad-toolbar-btn {{
                        background: white;
                        border: 1px solid #cbd5e0;
                        border-radius: 4px;
                        padding: 6px 10px;
                        cursor: pointer;
                        font-size: 13px;
                        color: #4a5568;
                        transition: all 0.2s ease;
                        display: flex;
                        align-items: center;
                        gap: 4px;
                        font-weight: 500;
                    }}

                    .notepad-toolbar-btn:hover {{
                        background: #f7fafc;
                        border-color: #007AFF;
                        color: #007AFF;
                    }}

                    .notepad-toolbar-btn:active {{
                        transform: scale(0.95);
                    }}

                    .notepad-toolbar-btn svg {{
                        width: 14px;
                        height: 14px;
                        fill: currentColor;
                    }}


                </style>
            </head>
            <body>
                <script id="grupos-gantt-data" type="application/json">{json.dumps(GRUPOS)}</script>
                
                
                <div class="gantt-container" id="gantt-container-{project['id']}">
                    <!-- Menu Radial de Contexto -->
                    <div id="radial-menu">
                        <div class="radial-menu-wrapper">
                            <div class="radial-background-circle"></div>
                            <div class="radial-center" title="Menu Radial"></div>
                            <div class="radial-item" id="btn-notepad" style="top: 74px; left: 120px;">
                                <svg viewBox="0 0 24 24"><path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/></svg>
                            </div>
                            <div class="radial-tooltip" style="top: 74px; left: 146px;">Notas <span class="tooltip-badge">Shift+N</span></div>
                            <div class="radial-item" id="btn-focus-mode" style="top: 74px; left: 28px;">
                                <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><path d="M18 18l-3-3m3 3l3-3m-3 3v-6" stroke="currentColor" fill="none" stroke-width="2"/></svg>
                            </div>
                            <div class="radial-tooltip" style="top: 74px; right: 146px;">Modo Foco <span class="tooltip-badge">Shift+F</span></div>
                        </div>
                    </div>
                    <div id="floating-notepad">
                        <div class="notepad-header">
                            <div class="notepad-header-title">
                                <svg version="1.1" viewBox="0 0 512 512"><path d="M438.8,73.2H292.4L255,0H73.2v512h365.6V73.2z M401.3,474.5H110.7V37.5h119.2l37.4,73.2h134.1V474.5z"/><rect x="146.3" y="150.8" width="219.4" height="36.6"/><rect x="146.3" y="224" width="219.4" height="36.6"/><rect x="146.3" y="297.1" width="219.4" height="36.6"/><rect x="146.3" y="370.3" width="135.9" height="36.6"/></svg>
                                <span>Anotações <small style="font-weight: 400; opacity: 0.7; font-size: 10px;">(Shift+N)</small></span>
                            </div>
                            <button class="notepad-close">×</button>
                        </div>
                        <div class="notepad-toolbar">
                            <button class="notepad-toolbar-btn" id="btn-bold" title="Negrito">
                                <svg viewBox="0 0 24 24"><path d="M15.6 10.79c.97-.67 1.65-1.77 1.65-2.79 0-2.26-1.75-4-4-4H7v14h7.04c2.09 0 3.71-1.7 3.71-3.79 0-1.52-.86-2.82-2.15-3.42zM10 6.5h3c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5h-3v-3zm3.5 9H10v-3h3.5c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5z"/></svg>
                                <span>N</span>
                            </button>
                            <button class="notepad-toolbar-btn" id="btn-italic" title="Itálico">
                                <svg viewBox="0 0 24 24"><path d="M10 4v3h2.21l-3.42 8H6v3h8v-3h-2.21l3.42-8H18V4z"/></svg>
                                <span>I</span>
                            </button>
                            <button class="notepad-toolbar-btn" id="btn-list" title="Lista">
                                <svg viewBox="0 0 24 24"><path d="M4 10.5c-.83 0-1.5.67-1.5 1.5s.67 1.5 1.5 1.5 1.5-.67 1.5-1.5-.67-1.5-1.5-1.5zm0-6c-.83 0-1.5.67-1.5 1.5S3.17 7.5 4 7.5 5.5 6.83 5.5 6 4.83 4.5 4 4.5zm0 12c-.83 0-1.5.68-1.5 1.5s.68 1.5 1.5 1.5 1.5-.68 1.5-1.5-.67-1.5-1.5-1.5zM7 19h14v-2H7v2zm0-6h14v-2H7v2zm0-8v2h14V5H7z"/></svg>
                                <span>•</span>
                            </button>
                        </div>
                        <textarea class="notepad-content" spellcheck="true" placeholder="Digite suas anotações aqui...&#10;&#10;• Use este espaço para lembrar de tarefas pendentes&#10;• Anote insights sobre o projeto&#10;• Suas notas são salvas automaticamente"></textarea>
                    </div>
                    
                <div class="gantt-toolbar" id="gantt-toolbar-{project["id"]}">
                    <button class="toolbar-btn" id="filter-btn-{project["id"]}" title="Filtros">
                        <span>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
                            </svg>
                        </span>
                    </button>
                    <button class="toolbar-btn" id="fullscreen-btn-{project["id"]}" title="Tela Cheia">
                        <span>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
                            </svg>
                        </span>
                    </button>
                </div>

                    <div class="floating-filter-menu" id="filter-menu-{project['id']}">
                    <div class="filter-group">
                        <label for="filter-project-{project['id']}">Empreendimento</label>
                        <select id="filter-project-{project['id']}"></select>
                    </div>
                    
                    <div class="filter-group">
                        <label for="filter-etapa-{project['id']}">Etapa</label>
                        <div id="filter-etapa-{project['id']}"></div>
                    </div>
                    <div class="filter-group">
                        <div class="filter-group-checkbox">
                            <input type="checkbox" id="filter-concluidas-{project['id']}">
                            <label for="filter-concluidas-{project['id']}">Mostrar apenas não concluídas</label>
                        </div>
                    </div>
                    <div class="filter-group">
                        <label>Visualização</label>
                        <div class="filter-group-radio">
                            <input type="radio" id="filter-vis-ambos-{project['id']}" name="filter-vis-{project['id']}" value="Ambos" checked>
                            <label for="filter-vis-ambos-{project['id']}">Ambos</label>
                        </div>
                        <div class="filter-group-radio">
                            <input type="radio" id="filter-vis-previsto-{project['id']}" name="filter-vis-{project['id']}" value="Previsto">
                            <label for="filter-vis-previsto-{project['id']}">Previsto</label>
                        </div>
                        <div class="filter-group-radio">
                            <input type="radio" id="filter-vis-real-{project['id']}" name="filter-vis-{project['id']}" value="Real">
                            <label for="filter-vis-real-{project['id']}">Real</label>
                        </div>
                    </div>
                    <button class="filter-apply-btn" id="filter-apply-btn-{project['id']}">Aplicar Filtros</button>
                </div>

                    <div class="gantt-main">
                        <div class="gantt-sidebar-wrapper" id="gantt-sidebar-wrapper-{project['id']}">
                            <div class="gantt-sidebar-header">
                                <div class="project-title-row">
                                    <span>{project["name"]}</span>
                                    <button class="toggle-sidebar-btn" id="toggle-sidebar-btn-{project['id']}" title="Recolher/Expandir Tabela">«</button>
                                </div>
                                <div class="sidebar-grid-header-wrapper">
                                    <div></div>
                                    <div class="sidebar-grid-header">
                                        <div class="header-cell task-name-cell">SERVIÇO</div>
                                        <div class="header-cell">INÍCIO-P</div>
                                        <div class="header-cell">TÉRMINO-P</div>
                                        <div class="header-cell">DUR-P</div>
                                        <div class="header-cell">INÍCIO-R</div>
                                        <div class="header-cell">TÉRMINO-R</div>
                                        <div class="header-cell">DUR-R</div>
                                        <div class="header-cell">%</div>
                                        <div class="header-cell">VT</div>
                                        <div class="header-cell">VD</div>
                                    </div>
                                </div>
                            </div>
                            <div class="gantt-sidebar-content" id="gantt-sidebar-content-{project['id']}"></div>
                        </div>
                        <div class="gantt-chart-content" id="gantt-chart-content-{project['id']}">
                            <div class="chart-container" id="chart-container-{project["id"]}">
                                <div class="chart-header">
                                    <div class="year-header" id="year-header-{project["id"]}"></div>
                                    <div class="month-header" id="month-header-{project["id"]}"></div>
                                </div>
                                <div class="chart-body" id="chart-body-{project["id"]}"></div>
                                <div class="today-line" id="today-line-{project["id"]}"></div>
                                <div class="meta-line" id="meta-line-{project["id"]}"></div>
                                <div class="meta-line-label" id="meta-line-label-{project["id"]}"></div>
                            </div>
                        </div>
                    </div>
                    <div class="tooltip" id="tooltip-{project["id"]}"></div>
                </div>
                
                
                <script src="https://cdn.jsdelivr.net/npm/virtual-select-plugin@1.0.39/dist/virtual-select.min.js"></script>
                

                <script>
                    // DEBUG: Verificar dados
                    console.log('Inicializando Gantt para projeto:', '{project["name"]}');
                    
                    const coresPorSetor = {json.dumps(StyleConfig.CORES_POR_SETOR)};

                    const allProjectsData = {json.dumps(gantt_data_base)};

                    let currentProjectIndex = {correct_project_index_for_js};
                    const initialProjectIndex = {correct_project_index_for_js};

                    let projectData = {json.dumps([project])};

                    // Datas originais (Python)
                    const dataMinStr = '{data_min_proj.strftime("%Y-%m-%d")}';
                    const dataMaxStr = '{data_max_proj.strftime("%Y-%m-%d")}';

                    let activeDataMinStr = dataMinStr;
                    let activeDataMaxStr = dataMaxStr;

                    const initialTipoVisualizacao = '{tipo_visualizacao}';
                    let tipoVisualizacao = '{tipo_visualizacao}';
                    const PIXELS_PER_MONTH = 60;

                    // --- ESTRUTURA DE SUBETAPAS ---

                    
                    // Mapeamento reverso para encontrar etapa pai


                    // --- INÍCIO HELPERS DE DATA E PULMÃO ---
                    const etapas_pulmao = ["PULMÃO VENDA", "PULMÃO INFRA", "PULMÃO RADIER"];
                    const etapas_sem_alteracao = ["PROSPECÇÃO", "RADIER", "DEMANDA MÍNIMA", "PE. ÁREAS COMUNS (URB)", "PE. ÁREAS COMUNS (ENG)", "ORÇ. ÁREAS COMUNS", "SUP. ÁREAS COMUNS", "EXECUÇÃO ÁREAS COMUNS"];

                    const formatDateDisplay = (dateStr) => {{
                        if (!dateStr) return "N/D";
                        const d = parseDate(dateStr);
                        if (!d || isNaN(d.getTime())) return "N/D";
                        const day = String(d.getUTCDate()).padStart(2, '0');
                        const month = String(d.getUTCMonth() + 1).padStart(2, '0');
                        const year = String(d.getUTCFullYear()).slice(-2);
                        return `${{day}}/${{month}}/${{year}}`;
                    }};

                    function addMonths(dateStr, months) {{
                        if (!dateStr) return null;
                        const date = parseDate(dateStr);
                        if (!date || isNaN(date.getTime())) return null;
                        const originalDay = date.getUTCDate();
                        date.setUTCMonth(date.getUTCMonth() + months);
                        if (date.getUTCDate() !== originalDay) {{
                            date.setUTCDate(0);
                        }}
                        return date.toISOString().split('T')[0];
                    }}
                    // --- FIM HELPERS DE DATA E PULMÃO ---

                    const filterOptions = {json.dumps(filter_options)};

                    let allTasks_baseData = {json.dumps(tasks_base_data)};

                    const initialPulmaoStatus = '{pulmao_status}';
                    const initialPulmaoMeses = {pulmao_meses};

                    let pulmaoStatus = '{pulmao_status}';
                    let filtersPopulated = false;

                    // *** INÍCIO: Variáveis Globais para Virtual Select ***
                    let vsGrupo, vsEtapa;
                    // *** FIM: Variáveis Globais para Virtual Select ***

                    function parseDate(dateStr) {{ 
                        if (!dateStr) return null; 
                        const [year, month, day] = dateStr.split('-').map(Number); 
                        return new Date(Date.UTC(year, month - 1, day)); 
                    }}

                    function findNewDateRange(tasks) {{
                        let minDate = null;
                        let maxDate = null;

                        const updateRange = (dateStr) => {{
                            if (!dateStr) return;
                            const date = parseDate(dateStr);
                            if (!date || isNaN(date.getTime())) return;

                            if (!minDate || date < minDate) {{
                                minDate = date;
                            }}
                            if (!maxDate || date > maxDate) {{
                                maxDate = date;
                            }}
                        }};

                        tasks.forEach(task => {{
                            updateRange(task.start_previsto);
                            updateRange(task.end_previsto);
                            updateRange(task.start_real);
                            updateRange(task.end_real_original_raw || task.end_real);
                        }});

                        return {{
                            min: minDate ? minDate.toISOString().split('T')[0] : null,
                            max: maxDate ? maxDate.toISOString().split('T')[0] : null
                        }};
                    }}

                    // --- FUNÇÕES DE AGRUPAMENTO ---
                    function organizarTasksComSubetapas(tasks) {{
                        const tasksOrganizadas = [];
                        const tasksProcessadas = new Set();
                        
                        // Primeiro, adiciona todas as etapas principais
                        tasks.forEach(task => {{
                            if (tasksProcessadas.has(task.name)) return;
                            
                            const etapaPai = null;
                            
                            // Se é uma subetapa, pula por enquanto
                            if (etapaPai) return;
                            
                            // Se é uma etapa principal que tem subetapas
                            if (false) {{
                                const taskPrincipal = {{...task, isMainTask: true, expanded: false}};
                                tasksOrganizadas.push(taskPrincipal);
                                tasksProcessadas.add(task.name);
                                
                                // Adiciona subetapas
                                SUBETAPAS[task.name].forEach(subetapaNome => {{
                                    const subetapa = tasks.find(t => t.name === subetapaNome);
                                    if (subetapa) {{
                                        const subetapaComPai = {{
                                            ...subetapa, 
                                            isSubtask: true, 
                                            parentTask: task.name,
                                            visible: false
                                        }};
                                        tasksOrganizadas.push(subetapaComPai);
                                        tasksProcessadas.add(subetapaNome);
                                    }}
                                }});
                            }} else {{
                                // É uma etapa principal sem subetapas
                                tasksOrganizadas.push({{...task, isMainTask: true}});
                                tasksProcessadas.add(task.name);
                            }}
                        }});
                        
                        // Adiciona quaisquer tasks que não foram processadas (não estão no mapeamento)
                        tasks.forEach(task => {{
                            if (!tasksProcessadas.has(task.name)) {{
                                tasksOrganizadas.push({{...task, isMainTask: true}});
                                tasksProcessadas.add(task.name);
                            }}
                        }});
                        
                        return tasksOrganizadas;
                    }}

                    function toggleSubtasks(taskName) {{
                        const subtaskRows = document.querySelectorAll('.subtask-row[data-parent="' + taskName + '"]');
                        const ganttSubtaskRows = document.querySelectorAll('.gantt-subtask-row[data-parent="' + taskName + '"]');
                        const button = document.querySelector('.expand-collapse-btn[data-task="' + taskName + '"]');
                        
                        const isVisible = subtaskRows[0]?.classList.contains('visible');
                        
                        // Alterna visibilidade
                        subtaskRows.forEach(row => {{
                            row.classList.toggle('visible', !isVisible);
                        }});
                        
                        ganttSubtaskRows.forEach(row => {{
                            row.style.display = isVisible ? 'none' : 'block';
                            row.classList.toggle('visible', !isVisible);
                        }});
                        
                        // Atualiza ícone do botão
                        if (button) {{
                            button.textContent = isVisible ? '+' : '-';
                        }}
                        
                        // Atualiza estado no array de tasks
                        const taskIndex = projectData[0].tasks.findIndex(t => t.name === taskName && t.isMainTask);
                        if (taskIndex !== -1) {{
                            projectData[0].tasks[taskIndex].expanded = !isVisible;
                        }}

                        // Aplica/remove estilo nas barras reais da etapa pai
                        updateParentTaskBarStyle(taskName, !isVisible);
                    }}

                    function updateParentTaskBarStyle(taskName, isExpanded) {{
                        const parentTaskRow = document.querySelector('.gantt-row[data-task="' + taskName + '"]');
                        if (parentTaskRow) {{
                            const realBars = parentTaskRow.querySelectorAll('.gantt-bar.real');
                            realBars.forEach(bar => {{
                                if (isExpanded) {{
                                    bar.classList.add('parent-task-real', 'expanded');
                                    // Define a cor da borda com a mesma cor original
                                    const originalColor = bar.style.backgroundColor;
                                    bar.style.borderColor = originalColor;
                                }} else {{
                                    bar.classList.remove('parent-task-real', 'expanded');
                                    bar.style.borderColor = '';
                                }}
                            }});
                        }}
                    }}

                    function initGantt() {{
                        console.log('Iniciando Gantt com dados:', projectData);
                        
                        // Verificar se há dados para renderizar
                        if (!projectData || !projectData[0] || !projectData[0].tasks || projectData[0].tasks.length === 0) {{
                            console.error('Nenhum dado disponível para renderizar');
                            document.getElementById('chart-body-{project["id"]}').innerHTML = '<div style="padding: 20px; text-align: center; color: red;">Erro: Nenhum dado disponível</div>';
                            return;
                        }}

                        // Organizar tasks com estrutura de subetapas
                        projectData[0].tasks = organizarTasksComSubetapas(projectData[0].tasks);
                        allTasks_baseData = JSON.parse(JSON.stringify(projectData[0].tasks));

                        applyInitialPulmaoState();

                        if (initialPulmaoStatus === 'Com Pulmão' && initialPulmaoMeses > 0) {{
                            const {{ min: newMinStr, max: newMaxStr }} = findNewDateRange(projectData[0].tasks);
                            const newMin = parseDate(newMinStr);
                            const newMax = parseDate(newMaxStr);
                            const originalMin = parseDate(activeDataMinStr);
                            const originalMax = parseDate(activeDataMaxStr);

                            let finalMinDate = originalMin;
                            if (newMin && newMin < finalMinDate) {{
                                finalMinDate = newMin;
                            }}
                            let finalMaxDate = originalMax;
                            if (newMax && newMax > finalMaxDate) {{
                                finalMaxDate = newMax;
                            }}

                            finalMinDate = new Date(finalMinDate.getTime());
                            finalMaxDate = new Date(finalMaxDate.getTime());

                            finalMinDate.setUTCDate(1);
                            finalMaxDate.setUTCMonth(finalMaxDate.getUTCMonth() + 1, 0);

                            activeDataMinStr = finalMinDate.toISOString().split('T')[0];
                            activeDataMaxStr = finalMaxDate.toISOString().split('T')[0];
                        }}

                        renderSidebar();
                        renderHeader();
                        renderChart();
                        renderMonthDividers();
                        setupEventListeners();
                        positionTodayLine();
                        positionMetaLine();
                        populateFilters();
                    }}

                    function applyInitialPulmaoState() {{
                        if (initialPulmaoStatus === 'Com Pulmão' && initialPulmaoMeses > 0) {{
                            const offsetMeses = -initialPulmaoMeses;
                            let baseTasks = projectData[0].tasks;

                            baseTasks.forEach(task => {{
                                const etapaNome = task.name;
                                if (etapas_sem_alteracao.includes(etapaNome)) {{
                                    // Não altera datas
                                }}
                                else if (etapas_pulmao.includes(etapaNome)) {{
                                    // APENAS PREVISTO
                                    task.start_previsto = addMonths(task.start_previsto, offsetMeses);
                                    task.inicio_previsto = formatDateDisplay(task.start_previsto);
                                }}
                                else {{
                                    // APENAS PREVISTO
                                    task.start_previsto = addMonths(task.start_previsto, offsetMeses);
                                    task.end_previsto = addMonths(task.end_previsto, offsetMeses);
                                    task.inicio_previsto = formatDateDisplay(task.start_previsto);
                                    task.termino_previsto = formatDateDisplay(task.end_previsto);
                                    // NÃO modificar dados reais
                                }}
                            }});

                            allTasks_baseData = JSON.parse(JSON.stringify(baseTasks));
                        }}
                    }}

                    function renderSidebar() {{
                        const sidebarContent = document.getElementById('gantt-sidebar-content-{project['id']}');
                        const gruposGantt = JSON.parse(document.getElementById('grupos-gantt-data').textContent);
                        const tasks = projectData[0].tasks;
                        
                        if (!tasks || tasks.length === 0) {{
                            sidebarContent.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">Nenhuma tarefa disponível para os filtros aplicados</div>';
                            return;
                        }}
                        
                        let html = '';
                        let globalRowIndex = 0;
                        
                        // CORREÇÃO: Renderizar as tasks na ORDEM EXATA em que estão no array
                        // Ignorar completamente a estrutura de grupos e seguir apenas a ordem das tasks
                        html += '<div class="sidebar-rows-container">';
                        
                        tasks.forEach(task => {{
                            if (task.isSubtask) return; // Pular subetapas se existirem
                            
                            globalRowIndex++;
                            const rowClass = globalRowIndex % 2 !== 0 ? 'odd-row' : '';
                            const hasSubtasks = false;
                            const mainTaskClass = hasSubtasks ? 'main-task-row has-subtasks' : 'main-task-row';
                            
                            html += `<div class="sidebar-row ${{mainTaskClass}} ${{rowClass}}" data-task="${{task.name}}">`;
                            
                            // Coluna do botão de expandir/recolher
                            if (hasSubtasks) {{
                                html += `<div class="sidebar-cell task-name-cell" style="display: flex; align-items: center;">`;
                                html += `<button class="expand-collapse-btn" data-task="${{task.name}}">${{task.expanded ? '-' : '+'}}</button>`;
                                html += `<span title="${{task.numero_etapa}}. ${{task.name}}">${{task.numero_etapa}}. ${{task.name}}</span>`;
                                html += `</div>`;
                            }} else {{
                                html += `<div class="sidebar-cell task-name-cell" title="${{task.numero_etapa}}. ${{task.name}}">${{task.numero_etapa}}. ${{task.name}}</div>`;
                            }}
                            
                            html += `<div class="sidebar-cell">${{task.inicio_previsto}}</div>`;
                            html += `<div class="sidebar-cell">${{task.termino_previsto}}</div>`;
                            html += `<div class="sidebar-cell">${{task.duracao_prev_meses}}</div>`;
                            html += `<div class="sidebar-cell">${{task.inicio_real}}</div>`;
                            html += `<div class="sidebar-cell">${{task.termino_real}}</div>`;
                            html += `<div class="sidebar-cell">${{task.duracao_real_meses}}</div>`;
                            html += `<div class="sidebar-cell ${{task.status_color_class}}">${{task.progress}}%</div>`;
                            html += `<div class="sidebar-cell ${{task.status_color_class}}">${{task.vt_text}}</div>`;
                            html += `<div class="sidebar-cell ${{task.status_color_class}}">${{task.vd_text}}</div>`;
                            html += `</div>`;
                            
                            // Adicionar subetapas se existirem (mantido para compatibilidade)
                            if (hasSubtasks && SUBETAPAS[task.name]) {{
                                SUBETAPAS[task.name].forEach(subetapaNome => {{
                                    const subetapa = tasks.find(t => t.name === subetapaNome && t.isSubtask);
                                    if (subetapa) {{
                                        globalRowIndex++;
                                        const subtaskRowClass = globalRowIndex % 2 !== 0 ? 'odd-row' : '';
                                        const visibleClass = task.expanded ? 'visible' : '';
                                        html += `<div class="sidebar-row subtask-row ${{subtaskRowClass}} ${{visibleClass}}" data-parent="${{task.name}}">`;
                                        html += `<div class="sidebar-cell task-name-cell" title="${{subetapa.numero_etapa}}. • ${{subetapa.name}}">${{subetapa.numero_etapa}}. • ${{subetapa.name}}</div>`;
                                        html += `<div class="sidebar-cell">${{subetapa.inicio_previsto}}</div>`;
                                        html += `<div class="sidebar-cell">${{subetapa.termino_previsto}}</div>`;
                                        html += `<div class="sidebar-cell">${{subetapa.duracao_prev_meses}}</div>`;
                                        html += `<div class="sidebar-cell">${{subetapa.inicio_real}}</div>`;
                                        html += `<div class="sidebar-cell">${{subetapa.termino_real}}</div>`;
                                        html += `<div class="sidebar-cell">${{subetapa.duracao_real_meses}}</div>`;
                                        html += `<div class="sidebar-cell ${{subetapa.status_color_class}}">${{subetapa.progress}}%</div>`;
                                        html += `<div class="sidebar-cell ${{subetapa.status_color_class}}">${{subetapa.vt_text}}</div>`;
                                        html += `<div class="sidebar-cell ${{subetapa.status_color_class}}">${{subetapa.vd_text}}</div>`;
                                        html += `</div>`;
                                    }}
                                }});
                            }}
                        }});
                        
                        html += '</div>';
                        sidebarContent.innerHTML = html;
                        
                        // Adicionar event listeners para os botões de expandir/recolher
                        document.querySelectorAll('.expand-collapse-btn').forEach(button => {{
                            button.addEventListener('click', function(e) {{
                                e.stopPropagation();
                                const taskName = this.getAttribute('data-task');
                                toggleSubtasks(taskName);
                            }});
                        }});
                        
                        // Adicionar event listeners para as linhas principais com subetapas
                        document.querySelectorAll('.main-task-row.has-subtasks').forEach(row => {{
                            row.addEventListener('click', function() {{
                                const taskName = this.getAttribute('data-task');
                                toggleSubtasks(taskName);
                            }});
                        }});
                    }}

                    function renderHeader() {{
                        const yearHeader = document.getElementById('year-header-{project["id"]}');
                        const monthHeader = document.getElementById('month-header-{project["id"]}');
                        let yearHtml = '', monthHtml = '';
                        const yearsData = [];

                        let currentDate = parseDate(activeDataMinStr);
                        const dataMax = parseDate(activeDataMaxStr);

                        if (!currentDate || !dataMax || isNaN(currentDate.getTime()) || isNaN(dataMax.getTime())) {{
                            yearHeader.innerHTML = "Datas inválidas";
                            monthHeader.innerHTML = "";
                            return;
                        }}

                        // DECLARE estas variáveis
                        let currentYear = -1, monthsInCurrentYear = 0;

                        let totalMonths = 0;
                        while (currentDate <= dataMax && totalMonths < 240) {{
                            const year = currentDate.getUTCFullYear();
                            if (year !== currentYear) {{
                                if (currentYear !== -1) yearsData.push({{ year: currentYear, count: monthsInCurrentYear }});
                                currentYear = year; 
                                monthsInCurrentYear = 0;
                            }}
                            const monthNumber = String(currentDate.getUTCMonth() + 1).padStart(2, '0');
                            monthHtml += `<div class="month-cell" style="display:flex; flex-direction:column; justify-content:center; align-items:center; line-height:1;">
                                <div style="font-size:9px; font-weight:bold; height: 50%; display:flex; align-items:center;">${{monthNumber}}</div>
                                <div style="display:flex; width:100%; height: 50%; border-top:1px solid rgba(255,255,255,0.2);">
                                    <div style="flex:1; text-align:center; font-size:8px; border-right:1px solid rgba(255,255,255,0.1); color:#ccc; display:flex; align-items:center; justify-content:center;">1</div>
                                    <div style="flex:1; text-align:center; font-size:8px; color:#ccc; display:flex; align-items:center; justify-content:center;">2</div>
                                </div>
                            </div>`;
                            monthsInCurrentYear++;
                            currentDate.setUTCMonth(currentDate.getUTCMonth() + 1);
                            totalMonths++;
                        }}
                        if (currentYear !== -1) yearsData.push({{ year: currentYear, count: monthsInCurrentYear }});
                        yearsData.forEach(data => {{ 
                            const yearWidth = data.count * PIXELS_PER_MONTH; 
                            yearHtml += `<div class="year-section" style="width:${{yearWidth}}px">${{data.year}}</div>`; 
                        }});

                        const chartContainer = document.getElementById('chart-container-{project["id"]}');
                        if (chartContainer) {{
                            chartContainer.style.minWidth = `${{totalMonths * PIXELS_PER_MONTH}}px`;
                        }}

                        yearHeader.innerHTML = yearHtml;
                        monthHeader.innerHTML = monthHtml;
                    }}

                    function renderChart() {{
                        const chartBody = document.getElementById('chart-body-{project["id"]}');
                        const tasks = projectData[0].tasks;
                        
                        if (!tasks || tasks.length === 0) {{
                            chartBody.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">Nenhuma tarefa disponível</div>';
                            return;
                        }}
                        
                        chartBody.innerHTML = '';
                        
                        // CORREÇÃO: Renderizar as tasks na ORDEM EXATA do array
                        tasks.forEach(task => {{
                            if (task.isSubtask) return; // Pular subetapas
                            
                            // Linha principal
                            const row = document.createElement('div'); 
                            row.className = 'gantt-row';
                            row.setAttribute('data-task', task.name);
                            
                            let barPrevisto = null;
                            if (tipoVisualizacao === 'Ambos' || tipoVisualizacao === 'Previsto') {{ 
                                barPrevisto = createBar(task, 'previsto'); 
                                if (barPrevisto) row.appendChild(barPrevisto); 
                            }}
                            let barReal = null;
                            if ((tipoVisualizacao === 'Ambos' || tipoVisualizacao === 'Real') && task.start_real && (task.end_real_original_raw || task.end_real)) {{ 
                                barReal = createBar(task, 'real'); 
                                if (barReal) row.appendChild(barReal); 
                            }}
                            if (barPrevisto && barReal) {{
                                const s_prev = parseDate(task.start_previsto), e_prev = parseDate(task.end_previsto), s_real = parseDate(task.start_real), e_real = parseDate(task.end_real_original_raw || task.end_real);
                                if (s_prev && e_prev && s_real && e_real && s_real <= s_prev && e_real >= e_prev) {{ 
                                    barPrevisto.style.zIndex = '8'; 
                                    barReal.style.zIndex = '7'; 
                                }}
                                renderOverlapBar(task, row);
                            }}
                            chartBody.appendChild(row);
                            
                            // Aplica estilo se a tarefa pai estiver expandida
                            if (task.expanded) {{
                                updateParentTaskBarStyle(task.name, true);
                            }}
                            
                            // Subetapas - SEMPRE criar as linhas, mas controlar visibilidade via CSS
                            if (false) {{
                                SUBETAPAS[task.name].forEach(subetapaNome => {{
                                    const subetapa = tasks.find(t => t.name === subetapaNome && t.isSubtask);
                                    if (subetapa) {{
                                        const subtaskRow = document.createElement('div'); 
                                        subtaskRow.className = 'gantt-row gantt-subtask-row';
                                        subtaskRow.setAttribute('data-parent', task.name);
                                        // Inicialmente oculto - será mostrado via toggle
                                        subtaskRow.style.display = task.expanded ? 'block' : 'none';
                                        if (task.expanded) {{
                                            subtaskRow.classList.add('visible');
                                        }}
                                        
                                        let subBarPrevisto = null;
                                        if (tipoVisualizacao === 'Ambos' || tipoVisualizacao === 'Previsto') {{ 
                                            subBarPrevisto = createBar(subetapa, 'previsto'); 
                                            if (subBarPrevisto) subtaskRow.appendChild(subBarPrevisto); 
                                        }}
                                        let subBarReal = null;
                                        if ((tipoVisualizacao === 'Ambos' || tipoVisualizacao === 'Real') && subetapa.start_real && (subetapa.end_real_original_raw || subetapa.end_real)) {{ 
                                            subBarReal = createBar(subetapa, 'real'); 
                                            if (subBarReal) subtaskRow.appendChild(subBarReal); 
                                        }}
                                        if (subBarPrevisto && subBarReal) {{
                                            const s_prev = parseDate(subetapa.start_previsto), e_prev = parseDate(subetapa.end_previsto), s_real = parseDate(subetapa.start_real), e_real = parseDate(subetapa.end_real_original_raw || subetapa.end_real);
                                            if (s_prev && e_prev && s_real && e_real && s_real <= s_prev && e_real >= e_prev) {{ 
                                                subBarPrevisto.style.zIndex = '8'; 
                                                subBarReal.style.zIndex = '7'; 
                                            }}
                                            renderOverlapBar(subetapa, subtaskRow);
                                        }}
                                        chartBody.appendChild(subtaskRow);
                                    }}
                                }});
                            }}
                        }});
                    }}

                    function createBar(task, tipo) {{
                        const startDate = parseDate(tipo === 'previsto' ? task.start_previsto : task.start_real);
                        const endDate = parseDate(tipo === 'previsto' ? task.end_previsto : (task.end_real_original_raw || task.end_real));

                        if (!startDate || !endDate) {{
                            console.log('Datas inválidas para barra:', task.name, tipo);
                            return null;
                        }}
                        
                        const left = getPosition(startDate);
                        const width = Math.max(getPosition(endDate) - left + (PIXELS_PER_MONTH / 30), 5); // Mínimo de 5px
                        
                        if (width <= 0) {{
                            console.log('Largura inválida para barra:', task.name, tipo, width);
                            return null;
                        }}
                        
                        const bar = document.createElement('div'); 
                        bar.className = `gantt-bar ${{tipo}}`;
                        const coresSetor = coresPorSetor[task.setor] || coresPorSetor['Não especificado'] || {{previsto: '#cccccc', real: '#888888'}};
                        bar.style.backgroundColor = tipo === 'previsto' ? coresSetor.previsto : coresSetor.real;
                        bar.style.left = `${{left}}px`; 
                        bar.style.width = `${{width}}px`;
                        
                        // Adicionar rótulo apenas se houver espaço suficiente
                        if (width > 40) {{
                            const barLabel = document.createElement('span'); 
                            barLabel.className = 'bar-label'; 
                            barLabel.textContent = `${{task.name}} (${{task.progress}}%)`; 
                            bar.appendChild(barLabel);
                        }}
                        
                        bar.addEventListener('mousemove', e => showTooltip(e, task, tipo));
                        bar.addEventListener('mouseout', () => hideTooltip());
                        return bar;
                    }}

                    function renderOverlapBar(task, row) {{
                    if (!task.start_real || !(task.end_real_original_raw || task.end_real)) return;
                        const s_prev = parseDate(task.start_previsto), e_prev = parseDate(task.end_previsto), s_real = parseDate(task.start_real), e_real = parseDate(task.end_real_original_raw || task.end_real);
                        const overlap_start = new Date(Math.max(s_prev, s_real)), overlap_end = new Date(Math.min(e_prev, e_real));
                        if (overlap_start < overlap_end) {{
                            const left = getPosition(overlap_start), width = getPosition(overlap_end) - left + (PIXELS_PER_MONTH / 30);
                            if (width > 0) {{ 
                                const overlapBar = document.createElement('div'); 
                                overlapBar.className = 'gantt-bar-overlap'; 
                                overlapBar.style.left = `${{left}}px`; 
                                overlapBar.style.width = `${{width}}px`; 
                                row.appendChild(overlapBar); 
                            }}
                        }}
                    }}

                    function getPosition(date) {{
                        if (!date) return 0;
                        const chartStart = parseDate(activeDataMinStr);
                        if (!chartStart || isNaN(chartStart.getTime())) return 0;

                        const monthsOffset = (date.getUTCFullYear() - chartStart.getUTCFullYear()) * 12 + (date.getUTCMonth() - chartStart.getUTCMonth());
                        const dayOfMonth = date.getUTCDate() - 1;
                        const daysInMonth = new Date(date.getUTCFullYear(), date.getUTCMonth() + 1, 0).getUTCDate();
                        const fractionOfMonth = daysInMonth > 0 ? dayOfMonth / daysInMonth : 0;
                        return (monthsOffset + fractionOfMonth) * PIXELS_PER_MONTH;
                    }}

                    function positionTodayLine() {{
                        const todayLine = document.getElementById('today-line-{project["id"]}');
                        const today = new Date(), todayUTC = new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()));

                        const chartStart = parseDate(activeDataMinStr);
                        const chartEnd = parseDate(activeDataMaxStr);

                        if (chartStart && chartEnd && !isNaN(chartStart.getTime()) && !isNaN(chartEnd.getTime()) && todayUTC >= chartStart && todayUTC <= chartEnd) {{ 
                            const offset = getPosition(todayUTC); 
                            todayLine.style.left = `${{offset}}px`; 
                            todayLine.style.display = 'block'; 
                        }} else {{ 
                            todayLine.style.display = 'none'; 
                        }}
                    }}

                    function positionMetaLine() {{
                        const metaLine = document.getElementById('meta-line-{project["id"]}'), metaLabel = document.getElementById('meta-line-label-{project["id"]}');
                        const metaDateStr = projectData[0].meta_assinatura_date;
                        if (!metaDateStr) {{ metaLine.style.display = 'none'; metaLabel.style.display = 'none'; return; }}

                        const metaDate = parseDate(metaDateStr);
                        const chartStart = parseDate(activeDataMinStr);
                        const chartEnd = parseDate(activeDataMaxStr);

                        if (metaDate && chartStart && chartEnd && !isNaN(metaDate.getTime()) && !isNaN(chartStart.getTime()) && !isNaN(chartEnd.getTime()) && metaDate >= chartStart && metaDate <= chartEnd) {{ 
                            const offset = getPosition(metaDate); 
                            metaLine.style.left = `${{offset}}px`; 
                            metaLabel.style.left = `${{offset}}px`; 
                            metaLine.style.display = 'block'; 
                            metaLabel.style.display = 'block'; 
                            metaLabel.textContent = `DM: ${{metaDate.toLocaleDateString('pt-BR', {{day: '2-digit', month: '2-digit', year: '2-digit', timeZone: 'UTC'}})}}`; 
                        }} else {{ 
                            metaLine.style.display = 'none'; 
                            metaLabel.style.display = 'none'; 
                        }}
                    }}

                    function showTooltip(e, task, tipo) {{
                        const tooltip = document.getElementById('tooltip-{project["id"]}');
                        let content = `<b>${{task.name}}</b><br>`;
                        if (tipo === 'previsto') {{ content += `Previsto: ${{task.inicio_previsto}} - ${{task.termino_previsto}}<br>Duração: ${{task.duracao_prev_meses}}M`; }} else {{ content += `Real: ${{task.inicio_real}} - ${{task.termino_real}}<br>Duração: ${{task.duracao_real_meses}}M<br>Variação Término: ${{task.vt_text}}<br>Variação Duração: ${{task.vd_text}}`; }}
                        content += `<br><b>Progresso: ${{task.progress}}%</b><br>Setor: ${{task.setor}}<br>Grupo: ${{task.grupo}}`;
                        tooltip.innerHTML = content;
                        tooltip.classList.add('show');
                        const tooltipWidth = tooltip.offsetWidth;
                        const tooltipHeight = tooltip.offsetHeight;
                        const viewportWidth = window.innerWidth;
                        const viewportHeight = window.innerHeight;
                        const mouseX = e.clientX; 
                        const mouseY = e.clientY;
                        const padding = 15;
                        let left, top;
                        if ((mouseX + padding + tooltipWidth) > viewportWidth) {{
                            left = mouseX - padding - tooltipWidth;
                        }} else {{
                            left = mouseX + padding;
                        }}
                        if ((mouseY + padding + tooltipHeight) > viewportHeight) {{
                            top = mouseY - padding - tooltipHeight;
                        }} else {{
                            top = mouseY + padding;
                        }}
                        if (left < padding) left = padding;
                        if (top < padding) top = padding;
                        tooltip.style.left = `${{left}}px`;
                        tooltip.style.top = `${{top}}px`;
                    }}

                    function hideTooltip() {{ 
                        document.getElementById('tooltip-{project["id"]}').classList.remove('show'); 
                    }}

                    function renderMonthDividers() {{
                        const chartContainer = document.getElementById('chart-container-{project["id"]}');
                        chartContainer.querySelectorAll('.month-divider, .month-divider-label').forEach(el => el.remove());

                        let currentDate = parseDate(activeDataMinStr);
                        const dataMax = parseDate(activeDataMaxStr);

                        if (!currentDate || !dataMax || isNaN(currentDate.getTime()) || isNaN(dataMax.getTime())) return;

                        let totalMonths = 0;
                        while (currentDate <= dataMax && totalMonths < 240) {{
                            const left = getPosition(currentDate);
                            const divider = document.createElement('div'); 
                            divider.className = 'month-divider';
                            if (currentDate.getUTCMonth() === 0) divider.classList.add('first');
                            divider.style.left = `${{left}}px`; 
                            chartContainer.appendChild(divider);

                            // Fortnight divider (pixel based alignment)
                            const leftF = left + 30;
                            const dividerF = document.createElement('div');
                            dividerF.className = 'month-divider fortnight';
                            dividerF.style.left = (leftF) + 'px';
                            dividerF.style.borderLeft = '1px solid #eff2f5';
                            chartContainer.appendChild(dividerF);

                            currentDate.setUTCMonth(currentDate.getUTCMonth() + 1);
                            totalMonths++;
                        }}
                    }}

                    function setupEventListeners() {{
                        const ganttChartContent = document.getElementById('gantt-chart-content-{project["id"]}'), sidebarContent = document.getElementById('gantt-sidebar-content-{project['id']}');
                        const fullscreenBtn = document.getElementById('fullscreen-btn-{project["id"]}'), toggleBtn = document.getElementById('toggle-sidebar-btn-{project['id']}');
                        const filterBtn = document.getElementById('filter-btn-{project["id"]}');
                        const filterMenu = document.getElementById('filter-menu-{project['id']}');
                        const container = document.getElementById('gantt-container-{project["id"]}');

                        const applyBtn = document.getElementById('filter-apply-btn-{project["id"]}');
                        if (applyBtn) applyBtn.addEventListener('click', () => applyFiltersAndRedraw());

                        if (fullscreenBtn) fullscreenBtn.addEventListener('click', () => toggleFullscreen());

                        // Adiciona listener para o botão de filtro
                        if (filterBtn) {{
                            filterBtn.addEventListener('click', () => {{
                                filterMenu.classList.toggle('is-open');
                            }});
                        }}

                        // Fecha o menu de filtro ao clicar fora
                        document.addEventListener('click', (event) => {{
                            if (filterMenu && filterBtn && !filterMenu.contains(event.target) && !filterBtn.contains(event.target)) {{
                                filterMenu.classList.remove('is-open');
                            }}
                        }});

                        if (container) container.addEventListener('fullscreenchange', () => handleFullscreenChange());

                        if (toggleBtn) toggleBtn.addEventListener('click', () => toggleSidebar());
                        if (ganttChartContent && sidebarContent) {{
                            let isSyncing = false;
                            ganttChartContent.addEventListener('scroll', () => {{ if (!isSyncing) {{ isSyncing = true; sidebarContent.scrollTop = ganttChartContent.scrollTop; isSyncing = false; }} }});
                            sidebarContent.addEventListener('scroll', () => {{ if (!isSyncing) {{ isSyncing = true; ganttChartContent.scrollTop = sidebarContent.scrollTop; isSyncing = false; }} }});
                            let isDown = false, startX, scrollLeft;
                            ganttChartContent.addEventListener('mousedown', (e) => {{ isDown = true; ganttChartContent.classList.add('active'); startX = e.pageX - ganttChartContent.offsetLeft; scrollLeft = ganttChartContent.scrollLeft; }});
                            ganttChartContent.addEventListener('mouseleave', () => {{ isDown = false; ganttChartContent.classList.remove('active'); }});
                            ganttChartContent.addEventListener('mouseup', () => {{ isDown = false; ganttChartContent.classList.remove('active'); }});
                            ganttChartContent.addEventListener('mousemove', (e) => {{ if (!isDown) return; e.preventDefault(); const x = e.pageX - ganttChartContent.offsetLeft; const walk = (x - startX) * 2; ganttChartContent.scrollLeft = scrollLeft - walk; }});
                        }}
                    }}

                    function toggleSidebar() {{ 
                        document.getElementById('gantt-sidebar-wrapper-{project["id"]}').classList.toggle('collapsed'); 
                    }}

                    function updatePulmaoInputVisibility() {{
                        const radioCom = document.getElementById('filter-pulmao-com-{project["id"]}');
                        const mesesGroup = document.getElementById('pulmao-meses-group-{project["id"]}');
                        if (radioCom && mesesGroup) {{ 
                            if (radioCom.checked) {{
                                mesesGroup.style.display = 'block';
                            }} else {{
                                mesesGroup.style.display = 'none';
                            }}
                        }}
                    }}

                    function resetToInitialState() {{
                        currentProjectIndex = initialProjectIndex;
                        const initialProject = allProjectsData[initialProjectIndex];

                        projectData = [JSON.parse(JSON.stringify(initialProject))];
                        // Reorganizar tasks com estrutura de subetapas
                        projectData[0].tasks = organizarTasksComSubetapas(projectData[0].tasks);
                        allTasks_baseData = JSON.parse(JSON.stringify(projectData[0].tasks));

                        tipoVisualizacao = initialTipoVisualizacao;
                        pulmaoStatus = initialPulmaoStatus;

                        applyInitialPulmaoState();

                        activeDataMinStr = dataMinStr;
                        activeDataMaxStr = dataMaxStr;

                        if (initialPulmaoStatus === 'Com Pulmão' && initialPulmaoMeses > 0) {{
                            const {{ min: newMinStr, max: newMaxStr }} = findNewDateRange(projectData[0].tasks);
                            const newMin = parseDate(newMinStr);
                            const newMax = parseDate(newMaxStr);
                            const originalMin = parseDate(activeDataMinStr);
                            const originalMax = parseDate(activeDataMaxStr);

                            let finalMinDate = originalMin;
                            if (newMin && newMin < finalMinDate) {{
                                finalMinDate = newMin;
                            }}
                            let finalMaxDate = originalMax;
                            if (newMax && newMax > finalMaxDate) {{
                                finalMaxDate = newMax;
                            }}

                            finalMinDate = new Date(finalMinDate.getTime());
                            finalMaxDate = new Date(finalMaxDate.getTime());
                            finalMinDate.setUTCDate(1);
                            finalMaxDate.setUTCMonth(finalMaxDate.getUTCMonth() + 1, 0);

                            activeDataMinStr = finalMinDate.toISOString().split('T')[0];
                            activeDataMaxStr = finalMaxDate.toISOString().split('T')[0];
                        }}

                        document.getElementById('filter-project-{project["id"]}').value = initialProjectIndex;
                        
                        // *** CORREÇÃO: Reset Virtual Select ***
                        if(vsSetor) vsSetor.setValue(["Todos"]);
                        if(vsGrupo) vsGrupo.setValue(["Todos"]);
                        if(vsEtapa) vsEtapa.setValue(["Todas"]);
                        
                        document.getElementById('filter-concluidas-{project["id"]}').checked = false;

                        const visRadio = document.querySelector('input[name="filter-vis-{project['id']}"][value="' + initialTipoVisualizacao + '"]');
                        if (visRadio) visRadio.checked = true;

                        const pulmaoRadio = document.querySelector('input[name="filter-pulmao-{project['id']}"][value="' + initialPulmaoStatus + '"]');
                        if (pulmaoRadio) pulmaoRadio.checked = true;

                        document.getElementById('filter-pulmao-meses-{project["id"]}').value = initialPulmaoMeses;

                        updatePulmaoInputVisibility();

                        renderHeader();
                        renderMonthDividers();
                        renderSidebar();
                        renderChart();
                        positionTodayLine();
                        positionMetaLine();
                        updateProjectTitle();
                    }}

                    function updateProjectTitle() {{
                        const projectTitle = document.querySelector('#gantt-sidebar-wrapper-{project["id"]} .project-title-row span');
                        if (projectTitle) {{
                            projectTitle.textContent = projectData[0].name;
                        }}
                    }}

                    function toggleFullscreen() {{
                        const container = document.getElementById('gantt-container-{project["id"]}');
                        if (!document.fullscreenElement) {{
                            container.requestFullscreen().catch(err => alert('Erro: ' + err.message));
                        }} else {{
                            document.exitFullscreen();
                        }}
                    }}



                    function toggleFullscreen() {{
                        const container = document.getElementById('gantt-container-{project["id"]}');
                        if (!document.fullscreenElement) {{
                            container.requestFullscreen().catch(err => console.error('Erro ao tentar entrar em tela cheia: ' + err.message));
                        }} else {{
                            document.exitFullscreen();
                        }}
                    }}

                    function handleFullscreenChange() {{
                        const btn = document.getElementById('fullscreen-btn-{project["id"]}');
                        const container = document.getElementById('gantt-container-{project["id"]}');
                        if (document.fullscreenElement === container) {{
                            btn.innerHTML = '<span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 9l6 6m0-6l-6 6M3 20.29V5a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2v-.29"></path></svg></span>';
                            btn.classList.add('is-fullscreen');
                        }} else {{
                            btn.innerHTML = '<span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path></svg></span>';
                            btn.classList.remove('is-fullscreen');
                            document.getElementById('filter-menu-{project["id"]}').classList.remove('is-open');
                        }}
                    }}
                    function populateFilters() {{
                        if (filtersPopulated) return;

                        // *** ORDENAR PROJETOS POR DATA DE META ***
                        // Criar array com índices e datas de meta para ordenação
                        const projectsWithMeta = allProjectsData.map((proj, originalIndex) => ({{
                            project: proj,
                            originalIndex: originalIndex,
                            metaDate: proj.meta_assinatura_date ? new Date(proj.meta_assinatura_date) : new Date('9999-12-31')
                        }}));
                        
                        // Ordenar do mais antigo (urgente) ao mais novo
                        projectsWithMeta.sort((a, b) => a.metaDate - b.metaDate);
                        
                        // Popula o select normal de Projeto com projetos ordenados por meta
                        const selProject = document.getElementById('filter-project-{project["id"]}');
                        projectsWithMeta.forEach(({{project, originalIndex}}) => {{
                            const isSelected = (originalIndex === initialProjectIndex) ? 'selected' : '';
                            selProject.innerHTML += '<option value="' + originalIndex + '" ' + isSelected + '>' + project.name + '</option>';
                        }});

                        // Configurações comuns para Virtual Select
                        const vsConfig = {{
                            multiple: true,
                            search: true,
                            optionsCount: 6,
                            showResetButton: true,
                            resetButtonText: 'Limpar',
                            selectAllText: 'Selecionar Todos',
                            allOptionsSelectedText: 'Todos',
                            optionsSelectedText: 'selecionados',
                            searchPlaceholderText: 'Buscar...',
                            optionHeight: '30px',
                            popupDropboxBreakpoint: '3000px',
                            noOptionsText: 'Nenhuma opção encontrada',
                            noSearchResultsText: 'Nenhum resultado encontrado',
                        }};

                        
                        // Prepara opções e inicializa Virtual Select para Etapa
                        const etapaOptions = filterOptions.etapas.map(e => ({{ label: e, value: e }}));
                        vsEtapa = VirtualSelect.init({{
                            ...vsConfig,
                            ele: '#filter-etapa-{project["id"]}',
                            options: etapaOptions,
                            placeholder: "Selecionar Etapa(s)",
                            selectedValue: ["Todas"]
                        }});

                        // Configura os radios de visualização
                        const visRadio = document.querySelector('input[name="filter-vis-{project['id']}"][value="' + initialTipoVisualizacao + '"]');
                        if (visRadio) visRadio.checked = true;

                        filtersPopulated = true;
                    }}
                    // *** FUNÇÃO applyFiltersAndRedraw CORRIGIDA ***
                    function applyFiltersAndRedraw() {{
                        try {{
                            const selProjectIndex = parseInt(document.getElementById('filter-project-{project["id"]}').value, 10);
                            
                            // *** LEITURA CORRIGIDA dos Virtual Select ***
                            const selEtapaArray = vsEtapa ? vsEtapa.getValue() || [] : [];
                            
                            const selConcluidas = document.getElementById('filter-concluidas-{project["id"]}').checked;
                            const selVis = document.querySelector('input[name="filter-vis-{project['id']}"]:checked').value;

                            console.log('Filtros aplicados:', {{
                                etapa: selEtapaArray,
                                concluidas: selConcluidas,
                                visualizacao: selVis,
                            }});

                            // *** FECHAR MENU DE FILTROS ***
                            document.getElementById('filter-menu-{project["id"]}').classList.remove('is-open');

                            if (selProjectIndex !== currentProjectIndex) {{
                                currentProjectIndex = selProjectIndex;
                                const newProject = allProjectsData[selProjectIndex];
                                projectData = [JSON.parse(JSON.stringify(newProject))];
                                // Reorganizar tasks com estrutura de subetapas
                                projectData[0].tasks = organizarTasksComSubetapas(projectData[0].tasks);
                                allTasks_baseData = JSON.parse(JSON.stringify(projectData[0].tasks));
                            }}

                            let baseTasks = JSON.parse(JSON.stringify(allTasks_baseData));
                            let filteredTasks = baseTasks;

                            // *** LÓGICA DE FILTRO CORRIGIDA ***                
                            // Filtro por Etapa
                            if (selEtapaArray.length > 0 && !selEtapaArray.includes('Todas')) {{
                                filteredTasks = filteredTasks.filter(t => selEtapaArray.includes(t.name));
                                console.log('Após filtro etapa:', filteredTasks.length);
                            }}

                            // Filtro por Concluídas
                            if (selConcluidas) {{
                                filteredTasks = filteredTasks.filter(t => t.progress < 100);
                                console.log('Após filtro concluídas:', filteredTasks.length);
                            }}

                            console.log('Tasks após filtros:', filteredTasks.length);
                            console.log('Tasks filtradas:', filteredTasks);

                            // Se não há tasks após filtrar, mostrar mensagem mas permitir continuar
                            if (filteredTasks.length === 0) {{
                                console.warn('Nenhuma task passou pelos filtros aplicados');
                                // Não interromper o processo, deixar que o renderSidebar mostre a mensagem apropriada
                            }}

                            // Recalcular range de datas apenas se houver tasks
                            if (filteredTasks.length > 0) {{
                                const {{ min: newMinStr, max: newMaxStr }} = findNewDateRange(filteredTasks);
                                const newMin = parseDate(newMinStr);
                                const newMax = parseDate(newMaxStr);
                                const originalMin = parseDate(dataMinStr);
                                const originalMax = parseDate(dataMaxStr);

                                let finalMinDate = originalMin;
                                if (newMin && newMin < finalMinDate) {{
                                    finalMinDate = newMin;
                                }}

                                let finalMaxDate = originalMax;
                                if (newMax && newMax > finalMaxDate) {{
                                    finalMaxDate = newMax;
                                }}

                                finalMinDate = new Date(finalMinDate.getTime());
                                finalMaxDate = new Date(finalMaxDate.getTime());
                                finalMinDate.setUTCDate(1);
                                finalMaxDate.setUTCMonth(finalMaxDate.getUTCMonth() + 1, 0);

                                activeDataMinStr = finalMinDate.toISOString().split('T')[0];
                                activeDataMaxStr = finalMaxDate.toISOString().split('T')[0];
                            }}

                            // Atualizar dados e redesenhar
                            projectData[0].tasks = filteredTasks;
                            tipoVisualizacao = selVis;

                            renderSidebar();
                            renderHeader();
                            renderChart();
                            positionTodayLine();
                            positionMetaLine();
                            updateProjectTitle();

                        }} catch (error) {{
                            console.error('Erro ao aplicar filtros:', error);
                            alert('Erro ao aplicar filtros: ' + error.message);
                        }}
                    }}

                    // --- MENU RADIAL DE CONTEXTO ---
                    const menu = document.getElementById('radial-menu');
                    const notepad = document.getElementById('floating-notepad');
                    const container = document.getElementById('gantt-container-{project["id"]}');

                    // 1. Botão direito para abrir menu
                    container.addEventListener('contextmenu', (e) => {{
                        // Impedir menu radial se clicar dentro do notepad
                        if (e.target.closest('#floating-notepad')) {{
                            return; // Permitir menu de contexto nativo do navegador
                        }}
                        
                        e.preventDefault();
                        const viewportWidth = window.innerWidth;
                        const viewportHeight = window.innerHeight;
                        const menuWidth = 170;
                        const menuHeight = 170;
                        
                        let left = e.clientX;
                        let top = e.clientY;
                        
                        if (left + menuWidth > viewportWidth) left = viewportWidth - menuWidth - 10;
                        if (left < 0) left = 10;
                        if (top + menuHeight > viewportHeight) top = viewportHeight - menuHeight - 10;
                        if (top < 0) top = 10;
                        
                        menu.style.left = left + 'px';
                        menu.style.top = top + 'px';
                        menu.style.display = 'block';
                        
                        console.log('📍 Menu radial aberto');
                    }});
                    
                    // 2. Fechar ao clicar fora
                    document.addEventListener('click', (e) => {{
                        if (!menu.contains(e.target) && menu.style.display === 'block') {{
                            menu.style.display = 'none';
                        }}
                    }});
                    
                    // 2.1. Fechar menu ao clicar nos circulos internos
                    const radialCenter = menu.querySelector('.radial-center');
                    const radialBgCircle = menu.querySelector('.radial-background-circle');
                    
                    if (radialCenter) {{
                        radialCenter.addEventListener('click', (e) => {{
                            e.stopPropagation();
                            menu.style.display = 'none';
                            console.log('❌ Menu fechado (clique no centro)');
                        }});
                    }}
                    
                    if (radialBgCircle) {{
                        radialBgCircle.addEventListener('click', (e) => {{
                            e.stopPropagation();
                            menu.style.display = 'none';
                            console.log('❌ Menu fechado (clique no circulo de fundo)');
                        }});
                    }}
                    
                    // 3. FLOATING NOTEPAD
                    let notepadActive = false;
                    const notepadBtn = document.getElementById('btn-notepad');
                    const notepadTextarea = notepad.querySelector('.notepad-content');
                    const notepadClose = notepad.querySelector('.notepad-close');
                    const NOTEPAD_STORAGE_KEY = 'gantt_notepad_content';
                    
                    const savedContent = localStorage.getItem(NOTEPAD_STORAGE_KEY);
                    if (savedContent && notepadTextarea) {{
                        notepadTextarea.value = savedContent;
                    }}
                    
                    if (notepadTextarea) {{
                        notepadTextarea.addEventListener('input', () => {{
                            localStorage.setItem(NOTEPAD_STORAGE_KEY, notepadTextarea.value);
                        }});
                    }}
                    
                    if (notepadBtn) {{
                        notepadBtn.addEventListener('click', (e) => {{
                            e.stopPropagation();
                            notepadActive = !notepadActive;
                            notepad.style.display = notepadActive ? 'flex' : 'none';
                            
                            if (notepadActive) {{
                                notepadBtn.style.borderColor = '#007AFF';
                                notepadBtn.style.background = '#e6f2ff';
                            }} else {{
                                notepadBtn.style.borderColor = '';
                                notepadBtn.style.background = '';
                            }}
                            
                            menu.style.display = 'none';
                            console.log('📝 Notepad toggled:', notepadActive);
                        }});
                    }}
                    
                    if (notepadClose) {{
                        notepadClose.addEventListener('click', () => {{
                            notepadActive = false;
                            notepad.style.display = 'none';
                            if (notepadBtn) {{
                                notepadBtn.style.borderColor = '';
                                notepadBtn.style.background = '';
                            }}
                        }});
                    }}
                    
                    // Drag-and-drop do notepad
                    let isDragging = false;
                    let offsetX, offsetY;
                    const notepadHeader = notepad.querySelector('.notepad-header');
                    
                    if (notepadHeader) {{
                        notepadHeader.addEventListener('mousedown', (e) => {{
                            if (e.target.closest('.notepad-close')) return;
                            isDragging = true;
                            offsetX = e.clientX - notepad.offsetLeft;
                            offsetY = e.clientY - notepad.offsetTop;
                            notepadHeader.style.cursor = 'grabbing';
                        }});
                    }}
                    
                    document.addEventListener('mousemove', (e) => {{
                        if (isDragging) {{
                            notepad.style.left = (e.clientX - offsetX) + 'px';
                            notepad.style.top = (e.clientY - offsetY) + 'px';
                            notepad.style.right = 'auto';
                        }}
                    }});
                    
                    document.addEventListener('mouseup', () => {{
                        if (isDragging) {{
                            isDragging = false;
                            if (notepadHeader) notepadHeader.style.cursor = 'move';
                        }}
                    }});
                    
                    // 4. MODO FOCO
                    let focusModeActive = false;
                    const focusBtn = document.getElementById('btn-focus-mode');
                    
                    if (focusBtn) {{
                        focusBtn.addEventListener('click', (e) => {{
                            e.stopPropagation();
                            focusModeActive = !focusModeActive;
                            
                            const allBars = container.querySelectorAll('.gantt-bar');
                            
                            if (focusModeActive) {{
                                allBars.forEach(bar => bar.classList.add('focus-mode'));
                                focusBtn.style.borderColor = '#007AFF';
                                focusBtn.style.background = '#e6f2ff';
                                console.log('🎯 Modo foco ATIVADO');
                            }} else {{
                                allBars.forEach(bar => {{
                                    bar.classList.remove('focus-mode', 'focused');
                                }});
                                focusBtn.style.borderColor = '';
                                focusBtn.style.background = '';
                                console.log('🎯 Modo foco DESATIVADO');
                            }}
                            
                            menu.style.display = 'none';
                        }});
                    }}
                    
                    // 5. Click em barras para focar/desfocar
                    container.addEventListener('click', (e) => {{
                        if (!focusModeActive) return;
                        
                        const clickedBar = e.target.closest('.gantt-bar');
                        if (!clickedBar) return;
                        
                        if (clickedBar.classList.contains('focused')) {{
                            clickedBar.classList.remove('focused');
                        }} else {{
                            container.querySelectorAll('.gantt-bar').forEach(bar => bar.classList.remove('focused'));
                            clickedBar.classList.add('focused');
                        }}
                    }});

                    // 6. Atalhos de teclado (Shift+N e Shift+F)
                    document.addEventListener('keydown', (e) => {{
                        // Shift+N para notepad
                        if (e.shiftKey && (e.key === 'N')) {{
                            e.preventDefault();
                            if (notepadBtn) notepadBtn.click();
                        }}
                        // Shift+F para modo foco
                        if (e.shiftKey && (e.key === 'F')) {{
                            e.preventDefault();
                            if (focusBtn) focusBtn.click();
                        }}
                    }});

                    // 7. Botoes de formatacao da toolbar
                    const boldBtn = document.getElementById('btn-bold');
                    const italicBtn = document.getElementById('btn-italic');
                    const listBtn = document.getElementById('btn-list');

                    // Funcao auxiliar para inserir texto no cursor
                    function insertAtCursor(textBefore, textAfter = '') {{
                        const start = notepadTextarea.selectionStart;
                        const end = notepadTextarea.selectionEnd;
                        const text = notepadTextarea.value;
                        const selectedText = text.substring(start, end);
                        
                        const newText = text.substring(0, start) + textBefore + selectedText + textAfter + text.substring(end);
                        notepadTextarea.value = newText;
                        
                        // Mover cursor para depois do texto inserido
                        const newCursorPos = start + textBefore.length + selectedText.length + textAfter.length;
                        notepadTextarea.setSelectionRange(newCursorPos, newCursorPos);
                        notepadTextarea.focus();
                        
                        // Salvar no localStorage
                        localStorage.setItem(NOTEPAD_STORAGE_KEY, notepadTextarea.value);
                    }}

                    if (boldBtn) {{
                        boldBtn.addEventListener('click', () => {{
                            const start = notepadTextarea.selectionStart;
                            const end = notepadTextarea.selectionEnd;
                            const selectedText = notepadTextarea.value.substring(start, end);
                            
                            if (selectedText) {{
                                // Se ha texto selecionado, envolver com **
                                insertAtCursor('**', '**');
                            }} else {{
                                // Se nao ha selecao, inserir marcador
                                insertAtCursor('**texto em negrito**');
                            }}
                        }});
                    }}

                    if (italicBtn) {{
                        italicBtn.addEventListener('click', () => {{
                            const start = notepadTextarea.selectionStart;
                            const end = notepadTextarea.selectionEnd;
                            const selectedText = notepadTextarea.value.substring(start, end);
                            
                            if (selectedText) {{
                                insertAtCursor('*', '*');
                            }} else {{
                                insertAtCursor('*texto em italico*');
                            }}
                        }});
                    }}

                    if (listBtn) {{
                        listBtn.addEventListener('click', () => {{
                            // Adicionar bullet point no inicio da linha
                            const start = notepadTextarea.selectionStart;
                            const text = notepadTextarea.value;
                            
                            // Encontrar inicio da linha atual
                            let lineStart = start;
                            while (lineStart > 0 && text[lineStart - 1] !== '\n') {{
                                lineStart--;
                            }}
                            
                            // Inserir bullet point
                            const newText = text.substring(0, lineStart) + '• ' + text.substring(lineStart);
                            notepadTextarea.value = newText;
                            
                            // Mover cursor
                            notepadTextarea.setSelectionRange(start + 2, start + 2);
                            notepadTextarea.focus();
                            
                            // Salvar
                            localStorage.setItem(NOTEPAD_STORAGE_KEY, notepadTextarea.value);
                        }});
                    }}


                    // DEBUG: Verificar se há dados antes de inicializar
                    console.log('Dados do projeto:', projectData);
                    console.log('Tasks base:', allTasks_baseData);
                    
                    // Inicializar o Gantt
                    initGantt();
                </script>
            </body>
            </html>
        """
        # Exibe o componente HTML no Streamlit
        components.html(gantt_html, height=altura_gantt, scrolling=True)
        # *** GERAÇÃO DO RELATÓRIO TXT ***
        relatorio_txt = gerar_relatorio_txt(gantt_data_base)

        col1, col2 = st.columns([5, 1])
        with col2:
            st.download_button(
                label="↓",
                data=relatorio_txt,
                file_name="relatorio_etapas.txt",
                mime="text/plain",
                help="Download do relatório",
                use_container_width=True
            )

        st.markdown("---")

        # CSS para botão circular com largura fixa
        st.markdown("""
        <style>
            div[data-testid="stDownloadButton"] {
                width: 60px !important;
                min-width: 60px !important;
                max-width: 60px !important;
                margin-left: auto !important;  /* Isso alinha à direita */
            }
            div[data-testid="stDownloadButton"] > button {
                background: white !important;
                color: #6c757d !important;
                border: 2px solid #e9ecef !important;
                border-radius: 50% !important;
                padding: 0.6rem !important;
                font-size: 20px !important;
                font-weight: bold !important;
                height: 50px !important;
                width: 50px !important;
                min-width: 50px !important;
                max-width: 50px !important;
                margin: 0 auto !important;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
            }
            div[data-testid="stDownloadButton"] > button:hover {
                background: #f8f9fa !important;
                border-color: #007bff !important;
                color: #007bff !important;
                transform: translateY(-2px) !important;
                box-shadow: 0 4px 8px rgba(0,0,0,0.15) !important;
            }
        </style>
        """, unsafe_allow_html=True)
        
# --- *** FUNÇÃO gerar_gantt_consolidado MODIFICADA *** ---
def converter_dados_para_gantt_consolidado(df, etapa_selecionada):
    """
    Versão modificada para o Gantt consolidado que também calcula datas de etapas pai
    a partir das subetapas.
    """
    if df.empty:
        return []

    # Filtrar pela etapa selecionada
    sigla_selecionada = nome_completo_para_sigla.get(etapa_selecionada, etapa_selecionada)
    df_filtrado = df[df["Etapa"] == sigla_selecionada].copy()
    
    if df_filtrado.empty:
        return []

    gantt_data = []
    tasks = []

    # Para cada empreendimento na etapa selecionada
    for empreendimento in df_filtrado["Empreendimento"].unique():
        df_emp = df_filtrado[df_filtrado["Empreendimento"] == empreendimento].copy()

        # Aplicar a mesma lógica de cálculo de datas para etapas pai
        etapa_nome_completo = sigla_para_nome_completo.get(sigla_selecionada, sigla_selecionada)

        # Processar cada linha (deve ser apenas uma por empreendimento na visão consolidada)
        for i, (idx, row) in enumerate(df_emp.iterrows()):
            start_date = row.get("Inicio_Prevista")
            end_date = row.get("Termino_Prevista")
            start_real = row.get("Inicio_Real")
            end_real_original = row.get("Termino_Real")

            # Garantir que as datas são objetos datetime, pois o .get() pode retornar NaT ou None
            if pd.notna(start_date): start_date = pd.to_datetime(start_date)
            if pd.notna(end_date): end_date = pd.to_datetime(end_date)
            if pd.notna(start_real): start_real = pd.to_datetime(start_real)
            if pd.notna(end_real_original): end_real_original = pd.to_datetime(end_real_original)
            progress = row.get("% concluído", 0)

            # Lógica para tratar datas vazias
            if pd.isna(start_date): 
                start_date = datetime.now()
            if pd.isna(end_date): 
                end_date = start_date + timedelta(days=30)

            end_real_visual = end_real_original
            if pd.notna(start_real) and progress < 100 and pd.isna(end_real_original):
                end_real_visual = datetime.now()

            # Cálculos de duração e variação
            dur_prev_meses = None
            if pd.notna(start_date) and pd.notna(end_date):
                dur_prev_meses = (end_date - start_date).days / 30.4375

            dur_real_meses = None
            if pd.notna(start_real) and pd.notna(end_real_original):
                dur_real_meses = (end_real_original - start_real).days / 30.4375

            vt = calculate_business_days(end_date, end_real_original)
            
            duracao_prevista_uteis = calculate_business_days(start_date, end_date)
            duracao_real_uteis = calculate_business_days(start_real, end_real_original)
            
            vd = None
            if pd.notna(duracao_real_uteis) and pd.notna(duracao_prevista_uteis):
                vd = duracao_real_uteis - duracao_prevista_uteis

            # Lógica de Cor do Status
            status_color_class = 'status-default'
            hoje = pd.Timestamp.now().normalize()
            if progress == 100:
                if pd.notna(end_real_original) and pd.notna(end_date):
                    if end_real_original <= end_date:
                        status_color_class = 'status-green'
                    else:
                        status_color_class = 'status-red'
            elif progress < 100 and pd.notna(end_date) and (end_date < hoje):
                status_color_class = 'status-yellow'

            task = {
                "id": f"t{i}", 
                "name": empreendimento,  # No consolidado, o nome é o empreendimento
                "numero_etapa": i + 1,
                "start_previsto": start_date.strftime("%Y-%m-%d"),
                "end_previsto": end_date.strftime("%Y-%m-%d"),
                "start_real": pd.to_datetime(start_real).strftime("%Y-%m-%d") if pd.notna(start_real) else None,
                "end_real": pd.to_datetime(end_real_visual).strftime("%Y-%m-%d") if pd.notna(end_real_visual) else None,
                "end_real_original_raw": pd.to_datetime(end_real_original).strftime("%Y-%m-%d") if pd.notna(end_real_original) else None,
                "setor": row.get("SETOR", "Não especificado"),
                "grupo": "Consolidado",
                "progress": int(progress),
                "inicio_previsto": start_date.strftime("%d/%m/%y"),
                "termino_previsto": end_date.strftime("%d/%m/%y"),
                "inicio_real": pd.to_datetime(start_real).strftime("%d/%m/%y") if pd.notna(start_real) else "N/D",
                "termino_real": pd.to_datetime(end_real_original).strftime("%d/%m/%y") if pd.notna(end_real_original) else "N/D",
                "duracao_prev_meses": f"{dur_prev_meses:.1f}".replace('.', ',') if dur_prev_meses is not None else "-",
                "duracao_real_meses": f"{dur_real_meses:.1f}".replace('.', ',') if dur_real_meses is not None else "-",
                "vt_text": f"{int(vt):+d}d" if pd.notna(vt) else "-",
                "vd_text": f"{int(vd):+d}d" if pd.notna(vd) else "-",
                "status_color_class": status_color_class
            }
            tasks.append(task)

    # Criar um projeto único para a visão consolidada
    project = {
        "id": "p_consolidado",
        "name": f"Comparativo: {etapa_selecionada}",
        "tasks": tasks,
        "meta_assinatura_date": None
    }
    gantt_data.append(project)

    return gantt_data
# Substitua sua função gerar_gantt_consolidado inteira por esta
def gerar_gantt_consolidado(df, tipo_visualizacao, df_original_para_ordenacao, pulmao_status, pulmao_meses, etapa_selecionada_inicialmente):
    """
    Gera um gráfico de Gantt HTML consolidado que contém dados para TODAS as etapas
    e permite a troca de etapas via menu flutuante.
    
    'etapa_selecionada_inicialmente' define qual etapa mostrar no carregamento.
    """
    # # st.info(f"Exibindo visão comparativa. Etapa inicial: {etapa_selecionada_inicialmente}")

    # --- 1. Preparação dos Dados (MODIFICADO) ---
    df_gantt = df.copy() # df agora tem MÚLTIPLAS etapas

    for col in ["Inicio_Prevista", "Termino_Prevista", "Inicio_Real", "Termino_Real"]:
        if col in df_gantt.columns:
            df_gantt[col] = pd.to_datetime(df_gantt[col], errors="coerce")

    if "% concluído" not in df_gantt.columns: 
        df_gantt["% concluído"] = 0
    # A conversão já foi feita no load_data, então apenas garantimos 0 nos NaNs
    df_gantt["% concluído"] = df_gantt["% concluído"].fillna(0)

    # Agrupar por Etapa E Empreendimento
    df_gantt_agg = df_gantt.groupby(['Etapa', 'Empreendimento']).agg(
        Inicio_Prevista=('Inicio_Prevista', 'min'),
        Termino_Prevista=('Termino_Prevista', 'max'),
        Inicio_Real=('Inicio_Real', 'min'),
        Termino_Real=('Termino_Real', 'max'),
        **{'% concluído': ('% concluído', 'mean')},
        SETOR=('SETOR', 'first')
    ).reset_index()
    
    all_data_by_stage_js = {}
    all_stage_names_full = [] # Para o novo filtro
    # Iterar por cada etapa única
    etapas_unicas_no_df = df_gantt_agg['Etapa'].unique()
    
    for i, etapa_sigla in enumerate(etapas_unicas_no_df):
        df_etapa_agg = df_gantt_agg[df_gantt_agg['Etapa'] == etapa_sigla]
        etapa_nome_completo = sigla_para_nome_completo.get(etapa_sigla, etapa_sigla)
        all_stage_names_full.append(etapa_nome_completo)
        
        # *** ORDENAR EMPREENDIMENTOS POR META DE ASSINATURA ***
        # Criar ordenação baseada na data de meta de cada empreendimento
        empreendimentos_ordenados = criar_ordenacao_empreendimentos(df_original_para_ordenacao)
        
        # Criar mapeamento de ordem para esta etapa
        ordem_meta = {emp: idx for idx, emp in enumerate(empreendimentos_ordenados)}
        
        # Adicionar coluna de ordem e ordenar DataFrame da etapa por meta
        df_etapa_agg['ordem_meta'] = df_etapa_agg['Empreendimento'].map(ordem_meta).fillna(999)
        df_etapa_agg = df_etapa_agg.sort_values('ordem_meta')
        
        tasks_base_data_for_stage = []
        
        for j, row in df_etapa_agg.iterrows():
            start_date = row.get("Inicio_Prevista")
            end_date = row.get("Termino_Prevista")
            start_real = row.get("Inicio_Real")
            end_real_original = row.get("Termino_Real")

            # Garantir que as datas são objetos datetime, pois o .get() pode retornar NaT ou None
            if pd.notna(start_date): start_date = pd.to_datetime(start_date)
            if pd.notna(end_date): end_date = pd.to_datetime(end_date)
            if pd.notna(start_real): start_real = pd.to_datetime(start_real)
            if pd.notna(end_real_original): end_real_original = pd.to_datetime(end_real_original)
            progress = row.get("% concluído", 0)

            if pd.isna(start_date): start_date = datetime.now()
            if pd.isna(end_date): end_date = start_date + timedelta(days=30)
            end_real_visual = end_real_original
            if pd.notna(start_real) and progress < 100 and pd.isna(end_real_original): end_real_visual = datetime.now()

            vt = calculate_business_days(end_date, end_real_original)
            duracao_prevista_uteis = calculate_business_days(start_date, end_date)
            duracao_real_uteis = calculate_business_days(start_real, end_real_original)
            vd = None
            if pd.notna(duracao_real_uteis) and pd.notna(duracao_prevista_uteis): vd = duracao_real_uteis - duracao_prevista_uteis
            status_color_class = 'status-default'
            hoje = pd.Timestamp.now().normalize()
            if progress == 100:
                if pd.notna(end_real_original) and pd.notna(end_date):
                    if end_real_original <= end_date: status_color_class = 'status-green'
                    else: status_color_class = 'status-red'
            elif progress < 100 and pd.notna(start_real) and pd.notna(end_real_original) and (end_real_original < hoje): status_color_class = 'status-yellow'

            task = {
                "id": f"t{j}_{i}", # ID único
                "name": row["Empreendimento"], # O 'name' ainda é o Empreendimento
                "numero_etapa": j + 1,
                "start_previsto": start_date.strftime("%Y-%m-%d"),
                "end_previsto": end_date.strftime("%Y-%m-%d"),
                "start_real": pd.to_datetime(start_real).strftime("%Y-%m-%d") if pd.notna(start_real) else None,
                "end_real": pd.to_datetime(end_real_visual).strftime("%Y-%m-%d") if pd.notna(end_real_visual) else None,
                "end_real_original_raw": pd.to_datetime(end_real_original).strftime("%Y-%m-%d") if pd.notna(end_real_original) else None,
                "setor": row.get("SETOR", "Não especificado"),
                "grupo": "Consolidado", # Correto
                "progress": int(progress),
                "inicio_previsto": start_date.strftime("%d/%m/%y"),
                "termino_previsto": end_date.strftime("%d/%m/%y"),
                "inicio_real": pd.to_datetime(start_real).strftime("%d/%m/%y") if pd.notna(start_real) else "N/D",
                "termino_real": pd.to_datetime(end_real_original).strftime("%d/%m/%y") if pd.notna(end_real_original) else "N/D",
                "duracao_prev_meses": f"{(end_date - start_date).days / 30.4375:.1f}".replace('.', ',') if pd.notna(start_date) and pd.notna(end_date) else "-",
                "duracao_real_meses": f"{(end_real_original - start_real).days / 30.4375:.1f}".replace('.', ',') if pd.notna(start_real) and pd.notna(end_real_original) else "-",
                "vt_text": f"{int(vt):+d}d" if pd.notna(vt) else "-",
                "vd_text": f"{int(vd):+d}d" if pd.notna(vd) else "-",
                "status_color_class": status_color_class
            }
            tasks_base_data_for_stage.append(task)
            
        all_data_by_stage_js[etapa_nome_completo] = tasks_base_data_for_stage
    
    if not all_data_by_stage_js:
        st.warning("Nenhum dado válido para o Gantt Consolidado após a conversão.")
        return

    empreendimentos_no_df = sorted(list(df_gantt_agg["Empreendimento"].unique()))
    
    filter_options = {
        "empreendimentos": ["Todos"] + empreendimentos_no_df, # Renomeado
        "etapas_consolidadas": sorted(all_stage_names_full) # Novo (sem "Todos")
    }

    # Pegar os dados da *primeira* etapa selecionada para a renderização inicial
    tasks_base_data_inicial = all_data_by_stage_js.get(etapa_selecionada_inicialmente, [])

    # Criar um "projeto" único
    project_id = f"p_cons_{random.randint(1000, 9999)}"
    project = {
        "id": project_id,
        "name": f"Comparativo: {etapa_selecionada_inicialmente}", # Nome inicial
        "tasks": tasks_base_data_inicial, # Dados iniciais
        "meta_assinatura_date": None
    }

    df_para_datas = df_gantt_agg
    data_min_proj, data_max_proj = calcular_periodo_datas(df_para_datas)
    total_meses_proj = ((data_max_proj.year - data_min_proj.year) * 12) + (data_max_proj.month - data_min_proj.month) + 1

    num_tasks = len(project["tasks"])
        
    altura_gantt = max(400, (len(empreendimentos_no_df) * 30) + 150)

    # --- 4. Geração do HTML/JS Corrigido ---
    gantt_html = f"""
    <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            {'''
            <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/virtual-select-plugin@1.0.39/dist/virtual-select.min.css">
            '''}
            <style>
                /* CSS idêntico ao de gerar_gantt_por_projeto, exceto adaptações para consolidado */
                 * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                html, body {{ width: 100%; height: 100%; font-family: 'Segoe UI', sans-serif; background-color: #f5f5f5; color: #333; overflow: hidden; }}
                .gantt-container {{ width: 100%; height: 100%; background-color: white; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden; position: relative; display: flex; flex-direction: column; }}
                .gantt-main {{ display: flex; flex: 1; overflow: hidden; }}
                .gantt-sidebar-wrapper {{ width: 680px; display: flex; flex-direction: column; flex-shrink: 0; transition: width 0.3s ease-in-out; border-right: 2px solid #e2e8f0; overflow: hidden; }}
                .gantt-sidebar-header {{ background: linear-gradient(135deg, #4a5568, #2d3748); display: flex; flex-direction: column; height: 60px; flex-shrink: 0; }}
                .project-title-row {{ display: flex; justify-content: space-between; align-items: center; padding: 0 15px; height: 30px; color: white; font-weight: 600; font-size: 14px; }}
                .toggle-sidebar-btn {{ background: rgba(255,255,255,0.2); border: none; color: white; width: 24px; height: 24px; border-radius: 5px; cursor: pointer; font-size: 14px; display: flex; align-items: center; justify-content: center; transition: background-color 0.2s, transform 0.3s ease-in-out; }}
                .toggle-sidebar-btn:hover {{ background: rgba(255,255,255,0.4); }}
                .sidebar-grid-header-wrapper {{ display: grid; grid-template-columns: 0px 1fr; color: #d1d5db; font-size: 9px; font-weight: 600; text-transform: uppercase; height: 30px; align-items: center; }}
                .sidebar-grid-header {{ display: grid; grid-template-columns: 2.5fr 0.9fr 0.9fr 0.6fr 0.9fr 0.9fr 0.6fr 0.5fr 0.6fr 0.6fr; padding: 0 10px; align-items: center; }}
                .sidebar-row {{ display: grid; grid-template-columns: 2.5fr 0.9fr 0.9fr 0.6fr 0.9fr 0.9fr 0.6fr 0.5fr 0.6fr 0.6fr; border-bottom: 1px solid #eff2f5; height: 30px; padding: 0 10px; background-color: white; transition: all 0.2s ease-in-out; }}
                .sidebar-cell {{ display: flex; align-items: center; justify-content: center; font-size: 11px; color: #4a5568; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 0 8px; border: none; }}
                .header-cell {{ text-align: center; }}
                .header-cell.task-name-cell {{ text-align: left; }}
                .gantt-sidebar-content {{ background-color: #f8f9fa; flex: 1; overflow-y: auto; overflow-x: hidden; }}
                .sidebar-group-wrapper {{ display: flex; border-bottom: none; }}
                .gantt-sidebar-content > .sidebar-group-wrapper:last-child {{ border-bottom: none; }}
                .sidebar-group-title-vertical {{ display: none; }}
                .sidebar-group-spacer {{ display: none; }}
                .sidebar-rows-container {{ flex-grow: 1; }}
                .sidebar-row.odd-row {{ background-color: #fdfdfd; }}
                .sidebar-rows-container .sidebar-row:last-child {{ border-bottom: none; }}
                .sidebar-row:hover {{ background-color: #f5f8ff; }}
                .sidebar-cell.task-name-cell {{ justify-content: flex-start; font-weight: 600; color: #2d3748; }}
                .sidebar-cell.status-green {{ color: #1E8449; font-weight: 700; }}
                .sidebar-cell.status-red   {{ color: #C0392B; font-weight: 700; }}
                .sidebar-cell.status-yellow{{ color: #B9770E; font-weight: 700; }}
                .sidebar-cell.status-default{{ color: #566573; font-weight: 700; }}
                .sidebar-row .sidebar-cell:nth-child(2),
                .sidebar-row .sidebar-cell:nth-child(3),
                .sidebar-row .sidebar-cell:nth-child(4),
                .sidebar-row .sidebar-cell:nth-child(5),
                .sidebar-row .sidebar-cell:nth-child(6),
                .sidebar-row .sidebar-cell:nth-child(7),
                .sidebar-row .sidebar-cell:nth-child(8),
                .sidebar-row .sidebar-cell:nth-child(9),
                .sidebar-row .sidebar-cell:nth-child(10) {{ font-size: 8px; }}
                .gantt-row-spacer, .sidebar-row-spacer {{ display: none; }}
                .gantt-sidebar-wrapper.collapsed {{ width: 250px; }}
                .gantt-sidebar-wrapper.collapsed .sidebar-grid-header, .gantt-sidebar-wrapper.collapsed .sidebar-row {{ grid-template-columns: 1fr; padding: 0 15px 0 10px; }}
                .gantt-sidebar-wrapper.collapsed .header-cell:not(.task-name-cell), .gantt-sidebar-wrapper.collapsed .sidebar-cell:not(.task-name-cell) {{ display: none; }}
                .gantt-sidebar-wrapper.collapsed .toggle-sidebar-btn {{ transform: rotate(180deg); }}
                .gantt-chart-content {{ flex: 1; overflow: auto; position: relative; background-color: white; user-select: none; cursor: grab; }}
                .gantt-chart-content.active {{ cursor: grabbing; }}
                .chart-container {{ position: relative; min-width: {total_meses_proj * 60}px; }}
                .chart-header {{ background: linear-gradient(135deg, #4a5568, #2d3748); color: white; height: 60px; position: sticky; top: 0; z-index: 9; display: flex; flex-direction: column; }}
                .year-header {{ height: 30px; display: flex; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.2); }}
                .year-section {{ text-align: center; font-weight: 600; font-size: 12px; display: flex; align-items: center; justify-content: center; background: rgba(255,255,255,0.1); height: 100%; border-right: 1px solid rgba(255,255,255,0.3); box-sizing: border-box; }}
                .month-header {{ height: 30px; display: flex; align-items: center; }}
                .month-cell {{ width: 60px; height: 30px; border-right: 1px solid rgba(255,255,255,0.2); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 500; }}
                .chart-body {{ position: relative; min-height: auto; background-size: 60px 60px; background-image: linear-gradient(to right, #f8f9fa 1px, transparent 1px); }}
                .gantt-row {{ position: relative; height: 30px; border-bottom: 1px solid #eff2f5; background-color: white; }}
                .gantt-bar {{ position: absolute; height: 14px; top: 8px; border-radius: 3px; cursor: pointer; transition: all 0.2s ease; display: flex; align-items: center; padding: 0 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                .gantt-bar-overlap {{ position: absolute; height: 14px; top: 8px; background-image: linear-gradient(45deg, rgba(0, 0, 0, 0.25) 25%, transparent 25%, transparent 50%, rgba(0, 0, 0, 0.25) 50%, rgba(0, 0, 0, 0.25) 75%, transparent 75%, transparent); background-size: 8px 8px; z-index: 9; pointer-events: none; border-radius: 3px; }}
                .gantt-bar:hover {{ transform: translateY(-1px) scale(1.01); box-shadow: 0 4px 8px rgba(0,0,0,0.2); z-index: 10 !important; }}
                .gantt-bar.previsto {{ z-index: 7; }}
                .gantt-bar.real {{ z-index: 8; }}
                .bar-label {{ font-size: 8px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-shadow: 0 1px 2px rgba(0,0,0,0.4); }}
                .gantt-bar.real .bar-label {{ color: white; }}
                .gantt-bar.previsto .bar-label {{ color: #6C6C6C; }}
                .tooltip {{ position: fixed; background-color: #2d3748; color: white; padding: 6px 10px; border-radius: 4px; font-size: 11px; z-index: 1000; box-shadow: 0 2px 8px rgba(0,0,0,0.3); pointer-events: none; opacity: 0; transition: opacity 0.2s ease; max-width: 220px; }}
                .tooltip.show {{ opacity: 1; }}
                .today-line {{ position: absolute; top: 60px; bottom: 0; width: 1px; background-color: #fdf1f1; z-index: 5; box-shadow: 0 0 1px rgba(229, 62, 62, 0.6); }}
                .month-divider {{ position: absolute; top: 60px; bottom: 0; width: 1px; background-color: #fcf6f6; z-index: 4; pointer-events: none; }}
                .month-divider.first {{ background-color: #eeeeee; width: 1px; }}
                .meta-line, .meta-line-label {{ display: none; }}
                .gantt-chart-content, .gantt-sidebar-content {{ scrollbar-width: thin; scrollbar-color: transparent transparent; }}
                .gantt-chart-content:hover, .gantt-sidebar-content:hover {{ scrollbar-color: #d1d5db transparent; }}
                .gantt-chart-content::-webkit-scrollbar, .gantt-sidebar-content::-webkit-scrollbar {{ height: 8px; width: 8px; }}
                .gantt-chart-content::-webkit-scrollbar-track, .gantt-sidebar-content::-webkit-scrollbar-track {{ background: transparent; }}
                .gantt-chart-content::-webkit-scrollbar-thumb, .gantt-sidebar-content::-webkit-scrollbar-thumb {{ background-color: transparent; border-radius: 4px; }}
                .gantt-chart-content:hover::-webkit-scrollbar-thumb, .gantt-sidebar-content:hover::-webkit-scrollbar-thumb {{ background-color: #d1d5db; }}
                .gantt-chart-content:hover::-webkit-scrollbar-thumb:hover, .gantt-sidebar-content:hover::-webkit-scrollbar-thumb:hover {{ background-color: #a8b2c1; }}
                .gantt-toolbar {{
                    position: absolute; top: 10px; right: 10px;
                    z-index: 100;
                    display: flex;
                    flex-direction: column;
                    gap: 5px;
                    background: rgba(45, 55, 72, 0.9); /* Cor de fundo escura para minimalismo */
                    border-radius: 6px;
                    padding: 5px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                }}
                .toolbar-btn {{
                    background: none;
                    border: none;
                    width: 36px;
                    height: 36px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 20px;
                    color: white;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    transition: background-color 0.2s, box-shadow 0.2s;
                    padding: 0;
                }}
                .toolbar-btn:hover {{
                    background-color: rgba(255, 255, 255, 0.1);
                    box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.2);
                }}
                .toolbar-btn.is-fullscreen {{
                    background-color: #3b82f6; /* Cor de destaque para o botão ativo */
                    box-shadow: 0 0 0 2px #3b82f6;
                }}
                .toolbar-btn.is-fullscreen:hover {{
                    background-color: #2563eb;
                }}
                 /* *** INÍCIO: Arredondar Dropdown Virtual Select *** */
                    .floating-filter-menu .vscomp-dropbox {{
                        border-radius: 8px; /* Controla o arredondamento dos cantos do dropdown */
                        overflow: hidden;   /* Necessário para que o conteúdo interno não "vaze" pelos cantos arredondados */
                        box-shadow: 0 5px 15px rgba(0,0,0,0.2); /* Sombra para melhor visualização (opcional) */
                        border: 1px solid #ccc; /* Borda sutil (opcional) */
                    }}

                    /* Opcional: Arredondar também o campo de busca interno, se ele ficar visível no topo */
                    .floating-filter-menu .vscomp-search-wrapper {{
                    /* Remove o arredondamento padrão se houver, para não conflitar com o container */
                    border-radius: 0;
                    }}

                    /* Opcional: Garantir que a lista de opções não ultrapasse */
                    .floating-filter-menu .vscomp-options-container {{
                        /* Geralmente não precisa de arredondamento próprio se o overflow:hidden funcionar */
                    }}
                    .floating-filter-menu .vscomp-toggle-button .vscomp-value-tag .vscomp-clear-button {{
                        display: inline-flex;    /* Usa flex para alinhar o ícone interno */
                        align-items: center;     /* Alinha verticalmente o ícone */
                        justify-content: center; /* Alinha horizontalmente o ícone */
                        vertical-align: middle;  /* Ajuda no alinhamento com o texto adjacente */
                        margin-left: 4px;        /* Espaçamento à esquerda (ajuste conforme necessário) */
                        padding: 0;            /* Remove padding interno se houver */
                        position: static;        /* Garante que não use posicionamento absoluto/relativo que possa quebrar o fluxo */
                        transform: none;         /* Remove qualquer translação que possa estar desalinhando */
                    }}

                    /* Opcional: Se o próprio ícone 'X' (geralmente uma tag <i>) precisar de ajuste */
                    .floating-filter-menu .vscomp-toggle-button .vscomp-value-tag .vscomp-clear-button i {{
                    }}
                .fullscreen-btn.is-fullscreen {{
	                    font-size: 24px; padding: 5px 10px; color: white;
	                }}
	                .floating-filter-menu {{
	                    display: none;
	                    position: absolute;
	                    top: 10px; right: 50px; /* Ajuste a posição para abrir ao lado da barra de ferramentas */
	                    width: 280px;
	                    background: white;
	                    border-radius: 8px;
	                    box-shadow: 0 5px 15px rgba(0,0,0,0.3);
	                    z-index: 99;
	                    padding: 15px;
	                    border: 1px solid #e2e8f0;
	                }}
	                .floating-filter-menu.is-open {{
	                    display: block;
	                }}
                .filter-group {{ margin-bottom: 12px; }}
                .filter-group label {{
                    display: block; font-size: 11px; font-weight: 600;
                    color: #4a5568; margin-bottom: 4px;
                    text-transform: uppercase;
                }}
                .filter-group select, .filter-group input[type=number] {{
                    width: 100%; padding: 6px 8px;
                    border: 1px solid #cbd5e0; border-radius: 4px;
                    font-size: 13px;
                }}
                .filter-group-radio, .filter-group-checkbox {{
                    display: flex; align-items: center; padding: 5px 0;
                }}
                .filter-group-radio input, .filter-group-checkbox input {{
                    width: auto; margin-right: 8px;
                }}
                .filter-group-radio label, .filter-group-checkbox label {{
                    font-size: 13px; font-weight: 500;
                    color: #2d3748; margin-bottom: 0; text-transform: none;
                }}
                .filter-apply-btn {{
                    width: 100%; padding: 8px; font-size: 14px; font-weight: 600;
                    color: white; background-color: #2d3748;
                    border: none; border-radius: 4px; cursor: pointer;
                    margin-top: 5px;
                }}
                .floating-filter-menu .vscomp-toggle-button {{
                    border: 1px solid #cbd5e0;
                    border-radius: 4px;
                    padding: 6px 8px;
                    font-size: 13px;
                    min-height: 30px;
                }}
                .floating-filter-menu .vscomp-options {{
                    font-size: 13px;
                }}
                .floating-filter-menu .vscomp-option {{
                    min-height: 30px;
                }}
                .floating-filter-menu .vscomp-search-input {{
                    height: 30px;
                    font-size: 13px;
                }}
            </style>
        </head>
        <body>
            <div class="gantt-container" id="gantt-container-{project['id']}">
                    <div class="gantt-toolbar" id="gantt-toolbar-{project["id"]}">
                        <button class="toolbar-btn" id="filter-btn-{project["id"]}" title="Filtros">
                        <span>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
                            </svg>
                        </span>
                    </button>
                    <button class="toolbar-btn" id="fullscreen-btn-{project["id"]}" title="Tela Cheia">
                        <span>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
                            </svg>
                        </span>
                    </button>
                </div>

                <div class="floating-filter-menu" id="filter-menu-{project['id']}">
                    
                    <div class="filter-group">
                        <label for="filter-etapa-consolidada-{project['id']}">Etapa (Visão Atual)</label>
                        <select id="filter-etapa-consolidada-{project['id']}">
                            </select>
                    </div>

                    <div class="filter-group">
                        <label for="filter-empreendimento-{project['id']}">Empreendimento</label>
                        <div id="filter-empreendimento-{project['id']}"></div>
                    </div>

                    <div class="filter-group">
                        <div class="filter-group-checkbox">
                            <input type="checkbox" id="filter-concluidas-{project['id']}">
                            <label for="filter-concluidas-{project['id']}">Mostrar apenas não concluídas</label>
                        </div>
                    </div>
                    
                    <div class="filter-group">
                        <label>Visualização</label>
                        <div class="filter-group-radio">
                            <input type="radio" id="filter-vis-ambos-{project['id']}" name="filter-vis-{project['id']}" value="Ambos" checked>
                            <label for="filter-vis-ambos-{project['id']}">Ambos</label>
                        </div>
                        <div class="filter-group-radio">
                            <input type="radio" id="filter-vis-previsto-{project['id']}" name="filter-vis-{project['id']}" value="Previsto">
                            <label for="filter-vis-previsto-{project['id']}">Previsto</label>
                        </div>
                        <div class="filter-group-radio">
                            <input type="radio" id="filter-vis-real-{project['id']}" name="filter-vis-{project['id']}" value="Real">
                            <label for="filter-vis-real-{project['id']}">Real</label>
                        </div>
                    </div>

                
                    <button class="filter-apply-btn" id="filter-apply-btn-{project['id']}">Aplicar Filtros</button>
                </div>

                <div class="gantt-main">
                    <div class="gantt-sidebar-wrapper" id="gantt-sidebar-wrapper-{project['id']}">
                        <div class="gantt-sidebar-header">
                            <div class="project-title-row">
                                <span>{project["name"]}</span>
                                <button class="toggle-sidebar-btn" id="toggle-sidebar-btn-{project['id']}" title="Recolher/Expandir Tabela">«</button>
                            </div>
                            <div class="sidebar-grid-header-wrapper">
                                <div style="width: 0px;"></div>
                                <div class="sidebar-grid-header">
                                    <div class="header-cell task-name-cell">EMPREENDIMENTO</div>
                                    <div class="header-cell">INÍCIO-P</div>
                                    <div class="header-cell">TÉRMINO-P</div>
                                    <div class="header-cell">DUR-P</div>
                                    <div class="header-cell">INÍCIO-R</div>
                                    <div class="header-cell">TÉRMINO-R</div>
                                    <div class="header-cell">DUR-R</div>
                                    <div class="header-cell">%</div>
                                    <div class="header-cell">VT</div>
                                    <div class="header-cell">VD</div>
                                </div>
                            </div>
                        </div>
                        <div class="gantt-sidebar-content" id="gantt-sidebar-content-{project['id']}"></div>
                    </div>
                    <div class="gantt-chart-content" id="gantt-chart-content-{project['id']}">
                        <div class="chart-container" id="chart-container-{project["id"]}">
                            <div class="chart-header">
                                <div class="year-header" id="year-header-{project["id"]}"></div>
                                <div class="month-header" id="month-header-{project["id"]}"></div>
                            </div>
                            <div class="chart-body" id="chart-body-{project["id"]}"></div>
                            <div class="today-line" id="today-line-{project["id"]}"></div>
                            <div class="meta-line" id="meta-line-{project["id"]}" style="display: none;"></div>
                            <div class="meta-line-label" id="meta-line-label-{project["id"]}" style="display: none;"></div>
                        </div>
                    </div>
                </div>
                <div class="tooltip" id="tooltip-{project["id"]}"></div>
            </div>

            {''''''}
            <script src="https://cdn.jsdelivr.net/npm/virtual-select-plugin@1.0.39/dist/virtual-select.min.js"></script>
            {''''''}

            <script>
                // DEBUG: Verificar dados
                console.log('Inicializando Gantt Consolidado para:', '{project["name"]}');
                
                const coresPorSetor = {json.dumps(StyleConfig.CORES_POR_SETOR)};
                
                // --- NOVAS VARIÁVEIS DE DADOS ---
                // 'projectData' armazena o estado ATUAL (inicia com a etapa selecionada)
                const projectData = [{json.dumps(project)}]; 
                // 'allDataByStage' armazena TUDO, chaveado por nome de etapa
                const allDataByStage = {json.dumps(all_data_by_stage_js)};
                
                // 'allTasks_baseData' agora armazena os dados "crus" da etapa ATUAL
                let allTasks_baseData = {json.dumps(tasks_base_data_inicial)}; 
                
                const initialStageName = {json.dumps(etapa_selecionada_inicialmente)};
                let currentStageName = initialStageName;
                // --- FIM NOVAS VARIÁVEIS ---
                
                const dataMinStr = '{data_min_proj.strftime("%Y-%m-%d")}'; // Range global
                const dataMaxStr = '{data_max_proj.strftime("%Y-%m-%d")}'; // Range global
                let tipoVisualizacao = '{tipo_visualizacao}';
                const PIXELS_PER_MONTH = 60;

                // --- Helpers de Data ---
                const formatDateDisplay = (dateStr) => {{
                    if (!dateStr) return "N/D";
                    const d = parseDate(dateStr);
                    if (!d || isNaN(d.getTime())) return "N/D";
                    const day = String(d.getUTCDate()).padStart(2, '0');
                    const month = String(d.getUTCMonth() + 1).padStart(2, '0');
                    const year = String(d.getUTCFullYear()).slice(-2);
                    return `${{day}}/${{month}}/${{year}}`;
                }};

                function addMonths(dateStr, months) {{
                    if (!dateStr) return null;
                    const date = parseDate(dateStr);
                    if (!date || isNaN(date.getTime())) return null;
                    const originalDay = date.getUTCDate();
                    date.setUTCMonth(date.getUTCMonth() + months);
                    if (date.getUTCDate() !== originalDay) {{
                        date.setUTCDate(0);
                    }}
                    return date.toISOString().split('T')[0];
                }}

                function parseDate(dateStr) {{ 
                    if (!dateStr) return null; 
                    const [year, month, day] = dateStr.split('-').map(Number); 
                    return new Date(Date.UTC(year, month - 1, day)); 
                }}

                // --- Dados de Filtro e Tasks ---
                const filterOptions = {json.dumps(filter_options)};
                // 'allTasks_baseData' (definido acima) é a base da etapa inicial

                const initialPulmaoStatus = 'Sem Pulmão'; // Valor fixo
                const initialPulmaoMeses = 0; // Zero meses
                let pulmaoStatus = 'Sem Pulmão'; // Valor fixo
                let filtersPopulated = false;

                // *** Variáveis Globais para Filtros ***
                // let vsSetor, vsGrupo; // REMOVIDO
                let vsEmpreendimento; 
                let selEtapaConsolidada; // Novo <select>

            
                // --- Lógica de Pulmão para Consolidado ---
                // *** aplicarLogicaPulmaoConsolidado ***
                function aplicarLogicaPulmaoConsolidado(tasks, offsetMeses, stageName) {{
                    console.log(`Aplicando pulmão de ${{offsetMeses}}m para etapa: ${{stageName}}`);

                    // Verifica o *tipo* de etapa que estamos processando
                    if (etapas_sem_alteracao.includes(stageName)) {{
                        console.log("Etapa sem alteração, retornando tasks originais.");
                        return tasks; // Não altera datas
                    
                    }} else if (etapas_pulmao.includes(stageName)) {{
                        console.log("Etapa Pulmão: movendo apenas início PREVISTO.");
                        // Para etapas de pulmão, move apenas o Início PREVISTO
                        tasks.forEach(task => {{
                            task.start_previsto = addMonths(task.start_previsto, offsetMeses);
                            // DATAS REAIS PERMANECEM INALTERADAS
                            task.inicio_previsto = formatDateDisplay(task.start_previsto);
                            // Não mexe no 'end_date' real
                        }});
                    
                    }} else {{
                        console.log("Etapa Padrão: movendo apenas PREVISTO.");
                        // Para todas as outras etapas, move apenas Início e Fim PREVISTOS
                        tasks.forEach(task => {{
                            task.start_previsto = addMonths(task.start_previsto, offsetMeses);
                            task.end_previsto = addMonths(task.end_previsto, offsetMeses);
                            // DATAS REAIS PERMANECEM INALTERADAS

                            task.inicio_previsto = formatDateDisplay(task.start_previsto);
                            task.termino_previsto = formatDateDisplay(task.end_previsto);
                            // Datas reais mantêm seus valores originais
                        }});
                    }}
                    return tasks;
                }}

                // *** FUNÇÃO CORRIGIDA: applyInitialPulmaoState ***
                function applyInitialPulmaoState() {{
                    if (initialPulmaoStatus === 'Com Pulmão' && initialPulmaoMeses > 0) {{
                        const offsetMeses = -initialPulmaoMeses;
                        let baseTasks = JSON.parse(JSON.stringify(allTasks_baseData));
                        
                        // Passa o nome da etapa inicial - APENAS DATAS PREVISTAS SERÃO MODIFICADAS
                        const tasksProcessadas = aplicarLogicaPulmaoConsolidado(baseTasks, offsetMeses, initialStageName);
                        
                        projectData[0].tasks = tasksProcessadas;
                        // Atualiza também o 'allTasks_baseData' que é a fonte "crua" da etapa atual
                        allTasks_baseData = JSON.parse(JSON.stringify(tasksProcessadas));
                    }}
                }}


                function initGantt() {{
                    console.log('Iniciando Gantt Consolidado com dados:', projectData);
                    
                    if (!projectData || !projectData[0] || !projectData[0].tasks || projectData[0].tasks.length === 0) {{
                        console.warn('Nenhum dado disponível para renderizar na etapa inicial');
                    }}

                    // NOTA: applyInitialPulmaoState foi movida para DENTRO de initGantt
                    applyInitialPulmaoState(); 
                    
                    renderSidebar();
                    renderHeader();
                    renderChart();
                    renderMonthDividers();
                    setupEventListeners();
                    positionTodayLine();
                    populateFilters();
                }}

                // *** FUNÇÃO CORRIGIDA: renderSidebar para ordenação ***
                function renderSidebar() {{
                    const sidebarContent = document.getElementById('gantt-sidebar-content-{project["id"]}');
                    let tasks = projectData[0].tasks;

                    if (!tasks || tasks.length === 0) {{
                        sidebarContent.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">Nenhum empreendimento disponível</div>';
                        return;
                    }}

                // *** ORDENAÇÃO RESTAURADA: do mais antigo para o mais novo ***
                const dateSortFallback = new Date(8640000000000000);

                if (tipoVisualizacao === 'Real') {{
                    tasks.sort((a, b) => {{
                        const dateA = a.start_real ? parseDate(a.start_real) : dateSortFallback;
                        const dateB = b.start_real ? parseDate(b.start_real) : dateSortFallback;
                        if (dateA > dateB) return 1;
                        if (dateA < dateB) return -1;
                        return a.name.localeCompare(b.name);
                    }});
                }} else {{
                    tasks.sort((a, b) => {{
                        const dateA = a.start_previsto ? parseDate(a.start_previsto) : dateSortFallback;
                        const dateB = b.start_previsto ? parseDate(b.start_previsto) : dateSortFallback;
                        if (dateA > dateB) return 1;
                        if (dateA < dateB) return -1;
                        return a.name.localeCompare(b.name);
                    }});
                }}
                    let html = '';
                    let globalRowIndex = 0;

                    html += '<div class="sidebar-rows-container">';
                    tasks.forEach(task => {{
                        globalRowIndex++;
                        const rowClass = globalRowIndex % 2 !== 0 ? 'odd-row' : '';
                        task.numero_etapa = globalRowIndex;

                        html += '<div class="sidebar-row ' + rowClass + '">' +
                            '<div class="sidebar-cell task-name-cell" title="' + task.numero_etapa + '. ' + task.name + '">' + task.numero_etapa + '. ' + task.name + '</div>' +
                            '<div class="sidebar-cell">' + task.inicio_previsto + '</div>' +
                            '<div class="sidebar-cell">' + task.termino_previsto + '</div>' +
                            '<div class="sidebar-cell">' + task.duracao_prev_meses + '</div>' +
                            '<div class="sidebar-cell">' + task.inicio_real + '</div>' +
                            '<div class="sidebar-cell">' + task.termino_real + '</div>' +
                            '<div class="sidebar-cell">' + task.duracao_real_meses + '</div>' +
                            '<div class="sidebar-cell ' + task.status_color_class + '">' + task.progress + '%</div>' +
                            '<div class="sidebar-cell ' + task.status_color_class + '">' + task.vt_text + '</div>' +
                            '<div class="sidebar-cell ' + task.status_color_class + '">' + task.vd_text + '</div>' +
                            '</div>';
                    }});
                    html += '</div>';
                    sidebarContent.innerHTML = html;
                }}

                // *** FUNÇÃO CORRIGIDA: renderHeader ***
                function renderHeader() {{
                    const yearHeader = document.getElementById('year-header-{project["id"]}');
                    const monthHeader = document.getElementById('month-header-{project["id"]}');
                    let yearHtml = '', monthHtml = '';
                    const yearsData = [];
                    let currentDate = parseDate(dataMinStr);
                    const dataMax = parseDate(dataMaxStr);

                    if (!currentDate || !dataMax || isNaN(currentDate.getTime()) || isNaN(dataMax.getTime())) {{
                         yearHeader.innerHTML = "Datas inválidas";
                         monthHeader.innerHTML = "";
                         return;
                    }}

                    // DECLARE estas variáveis
                    let currentYear = -1, monthsInCurrentYear = 0;

                    let totalMonths = 0;
                    while (currentDate <= dataMax && totalMonths < 240) {{
                        const year = currentDate.getUTCFullYear();
                        if (year !== currentYear) {{
                            if (currentYear !== -1) yearsData.push({{ year: currentYear, count: monthsInCurrentYear }});
                            currentYear = year; 
                            monthsInCurrentYear = 0;
                        }}
                        const monthNumber = String(currentDate.getUTCMonth() + 1).padStart(2, '0');
                        monthHtml += `<div class="month-cell" style="display:flex; flex-direction:column; justify-content:center; align-items:center; line-height:1;">
                                <div style="font-size:9px; font-weight:bold; height: 50%; display:flex; align-items:center;">${{monthNumber}}</div>
                                <div style="display:flex; width:100%; height: 50%; border-top:1px solid rgba(255,255,255,0.2);">
                                    <div style="flex:1; text-align:center; font-size:8px; border-right:1px solid rgba(255,255,255,0.1); color:#ccc; display:flex; align-items:center; justify-content:center;">1</div>
                                    <div style="flex:1; text-align:center; font-size:8px; color:#ccc; display:flex; align-items:center; justify-content:center;">2</div>
                                </div>
                            </div>`;
                        monthsInCurrentYear++;
                        currentDate.setUTCMonth(currentDate.getUTCMonth() + 1);
                        totalMonths++;
                    }}
                    if (currentYear !== -1) yearsData.push({{ year: currentYear, count: monthsInCurrentYear }});
                    yearsData.forEach(data => {{ 
                        const yearWidth = data.count * PIXELS_PER_MONTH; 
                        yearHtml += '<div class="year-section" style="width:' + yearWidth + 'px">' + data.year + '</div>'; 
                    }});

                    const chartContainer = document.getElementById('chart-container-{project["id"]}');
                    if (chartContainer) {{
                        chartContainer.style.minWidth = totalMonths * PIXELS_PER_MONTH + 'px';
                    }}

                    yearHeader.innerHTML = yearHtml;
                    monthHeader.innerHTML = monthHtml;
                }}

                function renderChart() {{
                    const chartBody = document.getElementById('chart-body-{project["id"]}');
                    const tasks = projectData[0].tasks;
                    
                    if (!tasks || tasks.length === 0) {{
                        chartBody.innerHTML = '<div style="padding: 20px; text-align: center; color: #666;">Nenhum empreendimento disponível</div>';
                        return;
                    }}
                    
                    chartBody.innerHTML = '';

                    tasks.forEach(task => {{
                        const row = document.createElement('div'); 
                        row.className = 'gantt-row';
                        let barPrevisto = null;
                        if (tipoVisualizacao === 'Ambos' || tipoVisualizacao === 'Previsto') {{ 
                            barPrevisto = createBar(task, 'previsto'); 
                            row.appendChild(barPrevisto); 
                        }}
                        let barReal = null;
                        if ((tipoVisualizacao === 'Ambos' || tipoVisualizacao === 'Real') && task.start_real && (task.end_real_original_raw || task.end_real)) {{ 
                            barReal = createBar(task, 'real'); 
                            row.appendChild(barReal); 
                        }}
                        if (barPrevisto && barReal) {{
                            const s_prev = parseDate(task.start_previsto), e_prev = parseDate(task.end_previsto), s_real = parseDate(task.start_real), e_real = parseDate(task.end_real_original_raw || task.end_real);
                            if (s_prev && e_prev && s_real && e_real && s_real <= s_prev && e_real >= e_prev) {{ 
                                barPrevisto.style.zIndex = '8'; 
                                barReal.style.zIndex = '7'; 
                            }}
                            renderOverlapBar(task, row);
                        }}
                        chartBody.appendChild(row);
                    }});
                }}

                function createBar(task, tipo) {{
                    const startDate = parseDate(tipo === 'previsto' ? task.start_previsto : task.start_real);
                    const endDate = parseDate(tipo === 'previsto' ? task.end_previsto : (task.end_real_original_raw || task.end_real));
                    if (!startDate || !endDate) return document.createElement('div');
                    const left = getPosition(startDate);
                    const width = getPosition(endDate) - left + (PIXELS_PER_MONTH / 30);
                    const bar = document.createElement('div'); 
                    bar.className = 'gantt-bar ' + tipo;
                    const coresSetor = coresPorSetor[task.setor] || coresPorSetor['Não especificado'] || {{previsto: '#cccccc', real: '#888888'}};
                    bar.style.backgroundColor = tipo === 'previsto' ? coresSetor.previsto : coresSetor.real;
                    bar.style.left = left + 'px'; 
                    bar.style.width = width + 'px';
                    const barLabel = document.createElement('span'); 
                    barLabel.className = 'bar-label'; 
                    barLabel.textContent = task.name + ' (' + task.progress + '%)'; 
                    bar.appendChild(barLabel);
                    bar.addEventListener('mousemove', e => showTooltip(e, task, tipo));
                    bar.addEventListener('mouseout', () => hideTooltip());
                    return bar;
                }}

                function renderOverlapBar(task, row) {{
                   if (!task.start_real || !(task.end_real_original_raw || task.end_real)) return;
                    const s_prev = parseDate(task.start_previsto), e_prev = parseDate(task.end_previsto), s_real = parseDate(task.start_real), e_real = parseDate(task.end_real_original_raw || task.end_real);
                    const overlap_start = new Date(Math.max(s_prev, s_real)), overlap_end = new Date(Math.min(e_prev, e_real));
                    if (overlap_start < overlap_end) {{
                        const left = getPosition(overlap_start), width = getPosition(overlap_end) - left + (PIXELS_PER_MONTH / 30);
                        if (width > 0) {{ 
                            const overlapBar = document.createElement('div'); 
                            overlapBar.className = 'gantt-bar-overlap'; 
                            overlapBar.style.left = left + 'px'; 
                            overlapBar.style.width = width + 'px'; 
                            row.appendChild(overlapBar); 
                        }}
                    }}
                }}

                function getPosition(date) {{
                    if (!date) return 0;
                    const chartStart = parseDate(dataMinStr);
                    if (!chartStart || isNaN(chartStart.getTime())) return 0;
                    const monthsOffset = (date.getUTCFullYear() - chartStart.getUTCFullYear()) * 12 + (date.getUTCMonth() - chartStart.getUTCMonth());
                    const dayOfMonth = date.getUTCDate() - 1;
                    const daysInMonth = new Date(date.getUTCFullYear(), date.getUTCMonth() + 1, 0).getUTCDate();
                    const fractionOfMonth = daysInMonth > 0 ? dayOfMonth / daysInMonth : 0;
                    return (monthsOffset + fractionOfMonth) * PIXELS_PER_MONTH;
                }}

                function positionTodayLine() {{
                    const todayLine = document.getElementById('today-line-{project["id"]}');
                    const today = new Date(), todayUTC = new Date(Date.UTC(today.getFullYear(), today.getMonth(), today.getDate()));
                    const chartStart = parseDate(dataMinStr), chartEnd = parseDate(dataMaxStr);
                    if (chartStart && chartEnd && !isNaN(chartStart.getTime()) && !isNaN(chartEnd.getTime()) && todayUTC >= chartStart && todayUTC <= chartEnd) {{ 
                        const offset = getPosition(todayUTC); 
                        todayLine.style.left = offset + 'px'; 
                        todayLine.style.display = 'block'; 
                    }} else {{ 
                        todayLine.style.display = 'none'; 
                    }}
                }}

                function showTooltip(e, task, tipo) {{
                    const tooltip = document.getElementById('tooltip-{project["id"]}');
                    let content = '<b>' + task.name + '</b><br>';
                    if (tipo === 'previsto') {{ 
                        content += 'Previsto: ' + task.inicio_previsto + ' - ' + task.termino_previsto + '<br>Duração: ' + task.duracao_prev_meses + 'M'; 
                    }} else {{ 
                        content += 'Real: ' + task.inicio_real + ' - ' + task.termino_real + '<br>Duração: ' + task.duracao_real_meses + 'M<br>Variação Término: ' + task.vt_text + '<br>Variação Duração: ' + task.vd_text; 
                    }}
                    content += '<br><b>Progresso: ' + task.progress + '%</b><br>Setor: ' + task.setor + '<br>Grupo: ' + task.grupo;
                    tooltip.innerHTML = content;
                    tooltip.classList.add('show');
                    const tooltipWidth = tooltip.offsetWidth, tooltipHeight = tooltip.offsetHeight;
                    const viewportWidth = window.innerWidth, viewportHeight = window.innerHeight;
                    const mouseX = e.clientX, mouseY = e.clientY;
                    const padding = 15;
                    let left, top;
                    if ((mouseX + padding + tooltipWidth) > viewportWidth) {{ 
                        left = mouseX - padding - tooltipWidth; 
                    }} else {{ 
                        left = mouseX + padding; 
                    }}
                    if ((mouseY + padding + tooltipHeight) > viewportHeight) {{ 
                        top = mouseY - padding - tooltipHeight; 
                    }} else {{ 
                        top = mouseY + padding; 
                    }}
                    if (left < padding) left = padding;
                    if (top < padding) top = padding;
                    tooltip.style.left = left + 'px';
                    tooltip.style.top = top + 'px';
                }}

                function hideTooltip() {{ 
                    document.getElementById('tooltip-{project["id"]}').classList.remove('show'); 
                }}

                function renderMonthDividers() {{
                    const chartContainer = document.getElementById('chart-container-{project["id"]}');
                    chartContainer.querySelectorAll('.month-divider, .month-divider-label').forEach(el => el.remove());
                    let currentDate = parseDate(dataMinStr);
                    const dataMax = parseDate(dataMaxStr);
                     if (!currentDate || !dataMax || isNaN(currentDate.getTime()) || isNaN(dataMax.getTime())) return;
                    let totalMonths = 0;
                    while (currentDate <= dataMax && totalMonths < 240) {{
                        const left = getPosition(currentDate);
                        const divider = document.createElement('div'); 
                        divider.className = 'month-divider';
                        if (currentDate.getUTCMonth() === 0) divider.classList.add('first');
                        divider.style.left = left + 'px'; 
                        chartContainer.appendChild(divider);

                        // Week dividers (pixel based alignment)
                        // Fortnight divider (pixel based alignment)
                        const leftF = left + 30;
                        const dividerF = document.createElement('div');
                        dividerF.className = 'month-divider fortnight';
                        dividerF.style.left = (leftF) + 'px';
                        dividerF.style.borderLeft = '1px solid #eff2f5';
                        chartContainer.appendChild(dividerF);

                        currentDate.setUTCMonth(currentDate.getUTCMonth() + 1);
                        totalMonths++;
                    }}
                }}

                function setupEventListeners() {{
                    const ganttChartContent = document.getElementById('gantt-chart-content-{project["id"]}'), sidebarContent = document.getElementById('gantt-sidebar-content-{project['id']}');
                    const fullscreenBtn = document.getElementById('fullscreen-btn-{project["id"]}'), toggleBtn = document.getElementById('toggle-sidebar-btn-{project['id']}');
                    const filterBtn = document.getElementById('filter-btn-{project["id"]}');
                    const filterMenu = document.getElementById('filter-menu-{project['id']}');
                    const container = document.getElementById('gantt-container-{project["id"]}');

                    const applyBtn = document.getElementById('filter-apply-btn-{project["id"]}');
                    if (applyBtn) applyBtn.addEventListener('click', () => applyFiltersAndRedraw());

                    if (fullscreenBtn) fullscreenBtn.addEventListener('click', () => toggleFullscreen());

                    // Adiciona listener para o botão de filtro
                    if (filterBtn) {{
                        filterBtn.addEventListener('click', () => {{
                            filterMenu.classList.toggle('is-open');
                        }});
                    }}

                    // Fecha o menu de filtro ao clicar fora
                    document.addEventListener('click', (event) => {{ 
                        if (filterMenu && filterBtn && !filterMenu.contains(event.target) && !filterBtn.contains(event.target)) {{
                            filterMenu.classList.remove('is-open');
                        }}
                    }});

                    if (container) container.addEventListener('fullscreenchange', () => handleFullscreenChange());

                    if (toggleBtn) toggleBtn.addEventListener('click', () => toggleSidebar());
                    if (ganttChartContent && sidebarContent) {{
                        let isSyncing = false;
                        ganttChartContent.addEventListener('scroll', () => {{ if (!isSyncing) {{ isSyncing = true; sidebarContent.scrollTop = ganttChartContent.scrollTop; isSyncing = false; }} }});
                        sidebarContent.addEventListener('scroll', () => {{ if (!isSyncing) {{ isSyncing = true; ganttChartContent.scrollTop = sidebarContent.scrollTop; isSyncing = false; }} }});
                        let isDown = false, startX, scrollLeft;
                        ganttChartContent.addEventListener('mousedown', (e) => {{ isDown = true; ganttChartContent.classList.add('active'); startX = e.pageX - ganttChartContent.offsetLeft; scrollLeft = ganttChartContent.scrollLeft; }});
                        ganttChartContent.addEventListener('mouseleave', () => {{ isDown = false; ganttChartContent.classList.remove('active'); }});
                        ganttChartContent.addEventListener('mouseup', () => {{ isDown = false; ganttChartContent.classList.remove('active'); }});
                        ganttChartContent.addEventListener('mousemove', (e) => {{ if (!isDown) return; e.preventDefault(); const x = e.pageX - ganttChartContent.offsetLeft; const walk = (x - startX) * 2; ganttChartContent.scrollLeft = scrollLeft - walk; }});
                    }}
                }}

                function toggleSidebar() {{ 
                    document.getElementById('gantt-sidebar-wrapper-{project["id"]}').classList.toggle('collapsed'); 
                }}

                function toggleFullscreen() {{
                    const container = document.getElementById('gantt-container-{project["id"]}');
                    if (!document.fullscreenElement) {{
                        container.requestFullscreen().catch(err => alert('Erro: ' + err.message));
                    }} else {{
                        document.exitFullscreen();
                    }}
                }}

                function handleFullscreenChange() {{
                        const btn = document.getElementById('fullscreen-btn-{project["id"]}');
                        const container = document.getElementById('gantt-container-{project["id"]}');
                        if (document.fullscreenElement === container) {{
                            btn.innerHTML = '<span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 9l6 6m0-6l-6 6M3 20.29V5a2 2 0 012-2h14a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2v-.29"></path></svg></span>';
                            btn.classList.add('is-fullscreen');
                        }} else {{
                            btn.innerHTML = '<span><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path></svg></span>';
                            btn.classList.remove('is-fullscreen');
                            document.getElementById('filter-menu-{project["id"]}').classList.remove('is-open');
                        }}
                    }}

                // *** FUNÇÃO populateFilters MODIFICADA ***
                function populateFilters() {{
                    if (filtersPopulated) return;

                    // *** 1. NOVO FILTRO DE ETAPA (Single Select) ***
                    selEtapaConsolidada = document.getElementById('filter-etapa-consolidada-{project["id"]}');
                    filterOptions.etapas_consolidadas.forEach(etapaNome => {{
                        const isSelected = (etapaNome === initialStageName) ? 'selected' : '';
                        selEtapaConsolidada.innerHTML += `<option value="${{etapaNome}}" ${{isSelected}}>${{etapaNome}}</option>`;
                    }});

                    const vsConfig = {{
                        multiple: true,
                        search: true,
                        optionsCount: 6,
                        showResetButton: true,
                        resetButtonText: 'Limpar',
                        selectAllText: 'Selecionar Todos',
                        allOptionsSelectedText: 'Todos',
                        optionsSelectedText: 'selecionados',
                        searchPlaceholderText: 'Buscar...',
                        optionHeight: '30px',
                        popupDropboxBreakpoint: '3000px',
                        noOptionsText: 'Nenhuma opção encontrada',
                        noSearchResultsText: 'Nenhum resultado encontrado',
                    }};

                    // *** 2. FILTRO DE SETOR (REMOVIDO) ***
                    // if (filterOptions.setores) {{
                    //     const setorOptions = filterOptions.setores.map(s => ({{ label: s, value: s }}));
                    //     vsSetor = VirtualSelect.init({{ ... }});
                    // }}

                    // *** 3. FILTRO DE GRUPO (REMOVIDO) ***
                    // if (filterOptions.grupos) {{
                    //     const grupoOptions = filterOptions.grupos.map(g => ({{ label: g, value: g }}));
                    //     vsGrupo = VirtualSelect.init({{ ... }});
                    // }}

                    // *** 4. FILTRO DE EMPREENDIMENTO (Renomeado e ORDENADO) ***
                    // *** ORDENAR EMPREENDIMENTOS POR DATA DE META ***
                    // Extrair empreendimentos únicos de todos os dados
                    let empreendimentosComMeta = [];
                    const empsSet = new Set();
                    
                    // Coletar todos os empreendimentos únicos de todas as etapas
                    Object.values(allDataByStage).forEach(stageTasks => {{
                        stageTasks.forEach(task => {{
                            if (!empsSet.has(task.name)) {{
                                empsSet.add(task.name);
                                // Tentar encontrar a meta deste empreendimento
                                // Buscar nos dados da etapa 'M' (se existir em allDataByStage)
                                let metaDate = null;
                                const stageMeta = allDataByStage['DEMANDA MÍNIMA'] || allDataByStage['Demanda Mínima'] || allDataByStage['DEMANDA MINIMA'];
                                if (stageMeta) {{
                                    const taskMeta = stageMeta.find(t => t.name === task.name);
                                    if (taskMeta && taskMeta.start_previsto) {{
                                        metaDate = new Date(taskMeta.start_previsto);
                                    }}
                                }}
                                
                                empreendimentosComMeta.push({{
                                    name: task.name,
                                    metaDate: metaDate || new Date('9999-12-31')
                                }});
                            }}
                        }});
                    }});
                    
                    // Ordenar do mais antigo (urgente) ao mais novo
                    empreendimentosComMeta.sort((a, b) => a.metaDate - b.metaDate);
                    
                    // Criar array de opções ordenadas
                    const empreendimentoOptions = empreendimentosComMeta.map(e => ({{ label: e.name, value: e.name }}));
                    empreendimentoOptions.unshift({{ label: 'Todos', value: 'Todos' }}); // Adicionar opção "Todos" no início
                    
                    vsEmpreendimento = VirtualSelect.init({{ // Renomeado de vsEtapa
                        ...vsConfig,
                        ele: '#filter-empreendimento-{project["id"]}', // ID Modificado
                        options: empreendimentoOptions,
                        placeholder: "Selecionar Empreendimento(s)",
                        selectedValue: ["Todos"]
                    }});

                    // *** 5. RESTO DOS FILTROS (Idêntico) ***
                    const visRadio = document.querySelector('input[name="filter-vis-{project['id']}"][value="' + tipoVisualizacao + '"]');
                    if(visRadio) visRadio.checked = true;

                    filtersPopulated = true;
                }}

                // *** FUNÇÃO updateProjectTitle (Nova/Modificada) ***
                function updateProjectTitle(newStageName) {{
                    const projectTitle = document.querySelector('#gantt-sidebar-wrapper-{project["id"]} .project-title-row span');
                    if (projectTitle) {{
                        projectTitle.textContent = `Comparativo: ${{newStageName}}`;
                        // Atualiza também o 'projectData' global se necessário, embora o 'name' não seja mais usado
                        projectData[0].name = `Comparativo: ${{newStageName}}`;
                    }}
                }}

                // *** FUNÇÃO applyFiltersAndRedraw MODIFICADA ***
                function applyFiltersAndRedraw() {{
                    try {{
                        // *** 1. LER A ETAPA PRIMEIRO ***
                        const selEtapaNome = selEtapaConsolidada.value;
                        
                        // *** 2. LER OUTROS FILTROS ***
                        const selEmpreendimentoArray = vsEmpreendimento ? vsEmpreendimento.getValue() || [] : [];
                        
                        const selConcluidas = document.getElementById('filter-concluidas-{project["id"]}').checked;
                        const selVis = document.querySelector('input[name="filter-vis-{project['id']}"]:checked').value;
                        // selPulmao e selPulmaoMeses removidos - pulmão desativado

                        // *** FECHAR MENU DE FILTROS ***
                        document.getElementById('filter-menu-{project["id"]}').classList.remove('is-open');

                        // *** 3. ATUALIZAR DADOS BASE SE A ETAPA MUDOU ***
                        if (selEtapaNome !== currentStageName) {{
                            currentStageName = selEtapaNome;
                            // Pegar os dados "crus" para a nova etapa
                            allTasks_baseData = JSON.parse(JSON.stringify(allDataByStage[currentStageName] || []));
                            console.log(`Mudando para etapa: ${{currentStageName}}. Tasks carregadas: ${{allTasks_baseData.length}}`);
                        }}

                        // Começar com os dados da etapa (já atualizados ou não)
                        let baseTasks = JSON.parse(JSON.stringify(allTasks_baseData));

                        // *** 4. PULMÃO DESATIVADO - NÃO APLICA LÓGICA DE PULMÃO ***

                        // *** 5. APLICAR FILTROS SECUNDÁRIOS ***
                        let filteredTasks = baseTasks;

                        // Lógica de filtro de empreendimento
                        if (selEmpreendimentoArray.length > 0 && !selEmpreendimentoArray.includes('Todos')) {{
                            filteredTasks = filteredTasks.filter(t => selEmpreendimentoArray.includes(t.name));
                        }}

                        if (selConcluidas) {{
                            filteredTasks = filteredTasks.filter(t => t.progress < 100);
                        }}

                        console.log('Empreendimentos após filtros:', filteredTasks.length);

                        // *** 6. ATUALIZAR DADOS E REDESENHAR ***
                        projectData[0].tasks = filteredTasks; // Atualiza as tarefas ativas
                        tipoVisualizacao = selVis;
                        // pulmaoStatus removido

                        // *** 7. ATUALIZAR TÍTULO DO PROJETO ***
                        updateProjectTitle(currentStageName);

                        // Redesenhar
                        renderSidebar();
                        renderChart();

                    }} catch (error) {{
                        console.error('Erro ao aplicar filtros no consolidado:', error);
                        alert('Erro ao aplicar filtros: ' + error.message);
                    }}
                }}

                // DEBUG: Verificar dados antes de inicializar
                console.log('Dados do projeto consolidado (inicial):', projectData);
                console.log('Tasks base consolidado (inicial):', allTasks_baseData);
                console.log('TODOS os dados de etapa (full):', allDataByStage);
                
                // Inicializar o Gantt Consolidado
                initGantt();
            </script>
        </body>
        </html>
    """
    components.html(gantt_html, height=altura_gantt, scrolling=True)
    # st.markdown("---") no consolidado, pois ele não é parte de um loop

# --- FUNÇÃO PRINCIPAL DE GANTT (DISPATCHER) ---
def gerar_gantt(df, tipo_visualizacao, filtrar_nao_concluidas, df_original_para_ordenacao, pulmao_status, pulmao_meses, etapa_selecionada_inicialmente):
    """
    Decide qual Gantt gerar com base na seleção da etapa inicial.
    """
    if df.empty:
        st.warning("Sem dados disponíveis para exibir o Gantt.")
        return
    # APLICAR ABREVIAÇÃO AQUI
    df_original_completo = df.copy()
    if 'Empreendimento' in df.columns:
        df['Empreendimento'] = df['Empreendimento'].apply(abreviar_nome)
        df_original_completo['Empreendimento'] = df_original_completo['Empreendimento'].apply(abreviar_nome)

    # A decisão do modo é baseada no parâmetro, não mais no conteúdo do DF
    is_consolidated_view = etapa_selecionada_inicialmente != "Todos"

    if is_consolidated_view:
        gerar_gantt_consolidado(
            df, 
            tipo_visualizacao, 
            df_original_para_ordenacao, 
            pulmao_status, 
            pulmao_meses,
            etapa_selecionada_inicialmente
        )
    else:
        # Agora gera apenas UM gráfico com todos os empreendimentos
        gerar_gantt_por_projeto(
            df, 
            tipo_visualizacao, 
            df_original_para_ordenacao, 
            pulmao_status, 
            pulmao_meses
        )

# O restante do código Streamlit...
st.set_page_config(layout="wide", page_title="Dashboard de Gantt Comparativo")

# Tente executar a tela de boas-vindas. Se os arquivos não existirem, apenas pule.
try:
    if show_welcome_screen():
        st.stop()
except NameError:
    st.warning("Arquivo `popup.py` não encontrado. Pulando tela de boas-vindas.")
except Exception as e:
    st.warning(f"Erro ao carregar `popup.py`: {e}")


st.markdown("""
<style>
    div.stMultiSelect div[role="option"] input[type="checkbox"]:checked + div > div:first-child { background-color: #4a0101 !important; border-color: #4a0101 !important; }
    div.stMultiSelect [aria-selected="true"] { background-color: #f8d7da !important; color: #333 !important; border-radius: 4px; }
    div.stMultiSelect [aria-selected="true"]::after { color: #4a0101 !important; font-weight: bold; }
    .stSidebar .stMultiSelect, .stSidebar .stSelectbox, .stSidebar .stRadio { margin-bottom: 1rem; }
    .nav-button-container { position: fixed; right: 20px; top: 20%; transform: translateY(-20%); z-index: 80; background: white; padding: 5px; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
    .nav-link { display: block; background-color: #a6abb5; color: white !important; text-decoration: none !important; border-radius: 10px; padding: 5px 10px; margin: 5px 0; text-align: center; font-weight: bold; font-size: 14px; transition: all 0.3s ease; }
    .nav-link:hover { background-color: #ff4b4b; transform: scale(1.05); }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    df_real = pd.DataFrame()
    df_previsto = pd.DataFrame()

    # CORREÇÃO: Carregar dados REAIS do Smartsheet (usando abordagem da versão antiga)
    try:
        if processar_smartsheet_main:
            # Método da versão antiga que funcionava
            processar_smartsheet_main()  # Processa os dados
            df_real = pd.read_csv('modulos_venda_tratados.csv')  # Lê o CSV gerado
            
            # Renomear colunas conforme versão antiga
            df_real.rename(columns={
                'Emp': 'Empreendimento', 
                'Iniciar': 'Inicio_Real', 
                'Terminar': 'Termino_Real'
            }, inplace=True)
            
            # Aplicar padronização de etapa
            df_real['Etapa'] = df_real['Etapa'].apply(padronizar_etapa)
            
            # Converter porcentagem
            df_real['% concluído'] = df_real.get('% concluído', pd.Series(0.0)).apply(converter_porcentagem)
            
            # Garantir coluna UGB
            if 'UGB' not in df_real.columns:
                df_real['UGB'] = "Não especificado"
                
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados reais do Smartsheet: {e}")
        df_real = pd.DataFrame()

    # CORREÇÃO: Carregar dados PREVISTOS do NEO
    try:
        if tratar_e_retornar_dados_previstos:
            df_previsto = tratar_e_retornar_dados_previstos()
            
            if df_previsto is not None and not df_previsto.empty:
                # Aplicar padronização (igual versão antiga)
                df_previsto['Etapa'] = df_previsto['Etapa'].apply(padronizar_etapa)
                df_previsto.rename(columns={'EMP': 'Empreendimento', 'Valor': 'Data_Prevista'}, inplace=True)
                
                # Criar pivot table (igual versão antiga)
                df_previsto_pivot = df_previsto.pivot_table(
                    index=['UGB', 'Empreendimento', 'Etapa'], 
                    columns='Inicio_Fim', 
                    values='Data_Prevista', 
                    aggfunc='first'
                ).reset_index()
                
                df_previsto_pivot.rename(columns={
                    'INÍCIO': 'Inicio_Prevista', 
                    'TÉRMINO': 'Termino_Prevista'
                }, inplace=True)
                
                df_previsto = df_previsto_pivot
                
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados previstos: {e}")
        df_previsto = pd.DataFrame()

    # Fallback para dados de exemplo
    if df_real.empty and df_previsto.empty:
        st.warning("⚠️ Nenhuma fonte de dados carregada. Usando dados de exemplo.")
        return criar_dados_exemplo()
    
    # Merge dos dados (igual versão antiga)
    if not df_real.empty:
        df_merged = pd.merge(
            df_previsto,
            df_real[['UGB', 'Empreendimento', 'Etapa', 'Inicio_Real', 'Termino_Real', '% concluído']],
            on=['UGB', 'Empreendimento', 'Etapa'],
            how='outer'
        )
    else:
        df_merged = df_previsto
        # APLICAR ABREVIAÇÃO AQUI
    df_merged['Empreendimento'] = df_merged['Empreendimento'].apply(abreviar_nome)
    
    # Garantir colunas necessárias (igual versão antiga)
    df_merged['% concluído'] = df_merged.get('% concluído', pd.Series(0.0)).fillna(0)
    if 'Inicio_Real' not in df_merged.columns: 
        df_merged[['Inicio_Real', 'Termino_Real']] = pd.NaT

    # Limpeza final
    df_merged.dropna(subset=['Empreendimento', 'Etapa'], inplace=True)
    
    # Adicionar mapeamentos de grupo e setor
    df_merged["GRUPO"] = df_merged["Etapa"].map(GRUPO_POR_ETAPA).fillna("Não especificado")
    df_merged["SETOR"] = df_merged["Etapa"].map(SETOR_POR_ETAPA).fillna("Não especificado")

    return df_merged


def criar_dados_exemplo():
    dados = {
        "UGB": ["UGB1", "UGB1", "UGB1", "UGB2", "UGB2", "UGB1"],
        "Empreendimento": ["Residencial Alfa", "Residencial Alfa", "Residencial Alfa", "Condomínio Beta", "Condomínio Beta", "Projeto Gama"],
        "Etapa": ["PROSPEC", "LEGVENDA", "PL.LIMP", "PROSPEC", "LEGVENDA", "PROSPEC"],
        "Inicio_Prevista": pd.to_datetime(["2024-01-01", "2024-02-15", "2024-04-01", "2024-01-20", "2024-03-10", "2024-05-01"]),
        "Termino_Prevista": pd.to_datetime(["2024-02-14", "2024-03-31", "2024-05-15", "2024-03-09", "2024-04-30", "2024-06-15"]),
        "Inicio_Real": pd.to_datetime(["2024-01-05", "2024-02-20", pd.NaT, "2024-01-22", "2024-03-15", pd.NaT]),
        "Termino_Real": pd.to_datetime(["2024-02-18", pd.NaT, pd.NaT, "2024-03-12", pd.NaT, pd.NaT]),
        "% concluído": [100, 50, 0, 100, 25, 0],
    }
    df_exemplo = pd.DataFrame(dados)
    df_exemplo["GRUPO"] = df_exemplo["Etapa"].map(GRUPO_POR_ETAPA).fillna("PLANEJAMENTO MACROFLUXO")
    df_exemplo["SETOR"] = df_exemplo["Etapa"].map(SETOR_POR_ETAPA).fillna("PROSPECÇÃO")
    return df_exemplo

@st.cache_data
def get_unique_values(df, column):
    if column == "Empreendimento":
        # Para empreendimentos, garantir que estamos usando os nomes convertidos
        df_temp = df.copy()
        df_temp[column] = df_temp[column].apply(converter_nome_empreendimento)
        return sorted(df_temp[column].dropna().unique().tolist())
    else:
        return sorted(df[column].dropna().unique().tolist())

@st.cache_data
def filter_dataframe(df, ugb_filter, emp_filter, grupo_filter, setor_filter):
    if not ugb_filter:
        return df.iloc[0:0]

    # Aplicar conversão aos nomes dos empreendimentos
    df_filtered = df.copy()
    df_filtered["Empreendimento"] = df_filtered["Empreendimento"].apply(converter_nome_empreendimento)
    df_filtered = df_filtered[df_filtered["UGB"].isin(ugb_filter)]
    
    # Aplicar filtros apenas se não estiverem vazios
    if emp_filter and len(emp_filter) > 0:
        df_filtered = df_filtered[df_filtered["Empreendimento"].isin(emp_filter)]
    
    if grupo_filter and len(grupo_filter) > 0: 
        df_filtered = df_filtered[df_filtered["GRUPO"].isin(grupo_filter)]
    
    if setor_filter and len(setor_filter) > 0:
        df_filtered = df_filtered[df_filtered["SETOR"].isin(setor_filter)]
        
    return df_filtered

# --- Bloco Principal ---
with st.spinner("Carregando e processando dados..."):
    df_data = load_data()
    if df_data is not None and not df_data.empty:
        with st.sidebar:
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                try:
                    st.image("logoNova.png", width=200)
                except:
                    # st.warning("Logo 'logoNova.png' não encontrada.")
                    pass
        
            st.markdown("---")
            # Título centralizado
            st.markdown("""
            <div style='
                margin: 1px 0 -70px 0; 
                padding: 12px 16px;
                border-radius: 6px;
                height: 60px;
                display: flex;
                justify-content: flex-start;
                align-items: center;
            '>
                <h4 style='
                    color: #707070; 
                    margin: 0; 
                    font-weight: 600;
                    font-size: 18px;
                    text-align: left;
                '>Filtros:</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # Filtro UGB centralizado
            st.markdown("""
            <style>
            .stMultiSelect [data-baseweb="select"] {
                margin: 0 auto;
            }
            .stMultiSelect > div > div {
                display: flex;
                justify-content: center;
            }
            </style>
            """, unsafe_allow_html=True)
            
            ugb_options = get_unique_values(df_data, "UGB")
            
            # Inicializar session_state para UGB se não existir
            if 'selected_ugb' not in st.session_state:
                st.session_state.selected_ugb = ugb_options  # Todos selecionados por padrão
            
            # Usar o valor da session_state no multiselect
            selected_ugb = simple_multiselect_dropdown(
                "UGB",
                options=ugb_options,
                key="ugb_multiselect"
            )
            
            # Atualizar session_state com a seleção atual
            st.session_state.selected_ugb = selected_ugb
            
            # Botão centralizado
            st.markdown("""
            <style>
            .stButton > button {
                width: 100%;
                display: block;
                margin: 0 auto;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Definir valores padrão para os filtros removidos
            selected_emp = get_unique_values(df_data[df_data["UGB"].isin(selected_ugb)], "Empreendimento") if selected_ugb else []
            selected_grupo = get_unique_values(df_data, "GRUPO")
            selected_setor = list(SETOR.keys())

            # Filtrar o DataFrame com base apenas na UGB para determinar as etapas disponíveis
            df_temp_filtered = filter_dataframe(df_data, selected_ugb, selected_emp, selected_grupo, selected_setor)
            if not df_temp_filtered.empty:
                etapas_disponiveis = get_unique_values(df_temp_filtered, "Etapa")
                etapas_ordenadas = [etapa for etapa in ORDEM_ETAPAS_GLOBAL if etapa in etapas_disponiveis]
                etapas_para_exibir = ["Todos"] + [sigla_para_nome_completo.get(e, e) for e in etapas_ordenadas]
            else:
                etapas_para_exibir = ["Todos"]
            
            # Inicializa o estado da visualização se não existir
            if 'consolidated_view' not in st.session_state:
                st.session_state.consolidated_view = False
                st.session_state.selected_etapa_nome = "Todos" # Valor inicial

            # Função de callback para alternar o estado
            def toggle_consolidated_view():
                st.session_state.consolidated_view = not st.session_state.consolidated_view
                if st.session_state.consolidated_view:
                    # Se for para consolidar, pega a primeira etapa disponível (ou uma lógica mais robusta se necessário)
                    etapa_para_consolidar = next((e for e in etapas_para_exibir if e != "Todos"), "Todos")
                    st.session_state.selected_etapa_nome = etapa_para_consolidar
                else:
                    st.session_state.selected_etapa_nome = "Todos"

            # Botão de ativação da visão etapa - já centralizado pelo CSS acima
            button_label = "Aplicar Visão Etapa" if not st.session_state.consolidated_view else "Voltar para Visão EMP"
            st.button(button_label, on_click=toggle_consolidated_view, use_container_width=True)
            
            # Mensagens centralizadas
            st.markdown("""
            <style>
            .stSuccess, .stInfo {
                text-align: center;
            }
            </style>
            """, unsafe_allow_html=True)
            
            etapas_nao_mapeadas = []  # Você precisa definir esta variável com os dados apropriados
            
            # Define a variável que será usada no resto do código
            selected_etapa_nome = st.session_state.selected_etapa_nome

            # Exibe a etapa selecionada quando no modo consolidado (alerta abaixo do botão)
            if st.session_state.consolidated_view:
                st.success(f"**Visão Consolidada Ativa:** {selected_etapa_nome}")
                # # st.info("💡 Esta visão mostra todos os empreendimentos para uma etapa específica")

            filtrar_nao_concluidas = False
            
            # Definir valores padrão para os filtros removidos
            pulmao_status = "Sem Pulmão"
            pulmao_meses = 0
            tipo_visualizacao = "Ambos"  

        # --- FIM DO NOVO LAYOUT ---
        # Mantemos a chamada a filter_dataframe, mas com os valores padrão para EMP, GRUPO e SETOR
        df_filtered = filter_dataframe(df_data, selected_ugb, selected_emp, selected_grupo, selected_setor)

        # 2. Determinar o modo de visualização (agora baseado no st.session_state)
        is_consolidated_view = st.session_state.consolidated_view

        # 3. NOVO: Se for visão consolidada, AINDA filtramos pela etapa aqui.
        if is_consolidated_view and not df_filtered.empty:
            sigla_selecionada = nome_completo_para_sigla.get(selected_etapa_nome, selected_etapa_nome)
            df_filtered = df_filtered[df_filtered["Etapa"] == sigla_selecionada]
        df_para_exibir = df_filtered.copy()
        # Criar a lista de ordenação de empreendimentos (necessário para ambas as tabelas)
        # *** CORREÇÃO CRÍTICA: Usar df_filtered em vez de df_data ***
        # df_data pode não conter todos os empreendimentos que aparecem em df_filtered após filtros
        # Precisamos ordenar os empreendimentos que REALMENTE aparecem nos dados filtrados
        empreendimentos_ordenados_por_meta_raw = criar_ordenacao_empreendimentos(df_data)
        empreendimentos_ordenados_por_meta_convertidos = [converter_nome_empreendimento(emp) for emp in empreendimentos_ordenados_por_meta_raw]
        
        # Pegar empreendimentos únicos que REALMENTE aparecem em df_filtered
        empreendimentos_visiveis = df_filtered['Empreendimento'].unique().tolist()
        
        # Ordenar apenas os empreendimentos visíveis pela ordem de meta
        # Preservar a ordem de empreendimentos_ordenados_por_meta_convertidos, mas incluir APENAS os visíveis
        empreendimentos_ordenados_por_meta = [emp for emp in empreendimentos_ordenados_por_meta_convertidos if emp in empreendimentos_visiveis]
        
        # Adicionar empreendimentos visíveis que não estavam na lista original (no final)
        for emp in empreendimentos_visiveis:
            if emp not in empreendimentos_ordenados_por_meta:
                empreendimentos_ordenados_por_meta.append(emp)
        # Copiar o dataframe filtrado para ser usado nas tabelas
        df_detalhes = df_para_exibir.copy()
        
        # A lógica de pulmão foi removida da sidebar, então não é mais aplicada aqui.
        tab1, tab2 = st.tabs(["Gráfico de Gantt", "Tabelão Horizontal"])
        with tab1:
            st.subheader("Gantt Comparativo")
            if df_para_exibir.empty:
                st.warning("⚠️ Nenhum dado encontrado com os filtros aplicados.")
                pass
            else:
                df_para_gantt = filter_dataframe(df_data, selected_ugb, selected_emp, selected_grupo, selected_setor)

                gerar_gantt(
                    df_para_gantt.copy(), # Passa o DF filtrado (sem filtro de etapa/concluídas)
                    tipo_visualizacao, 
                    filtrar_nao_concluidas, # Passa o *estado* do checkbox
                    df_data, 
                    pulmao_status, 
                    pulmao_meses,
                    selected_etapa_nome  # Novo parâmetro
                )
            st.markdown('<div id="visao-detalhada"></div>', unsafe_allow_html=True)
            st.subheader("Visão Detalhada por Empreendimento")

            if df_detalhes.empty: # Verifique df_detalhes
                st.warning("⚠️ Nenhum dado encontrado com os filtros aplicados.")
                pass
            else:
                hoje = pd.Timestamp.now().normalize()

                for col in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real']:
                    if col in df_detalhes.columns:
                        df_detalhes[col] = pd.to_datetime(df_detalhes[col], errors='coerce')

                df_agregado = df_detalhes.groupby(['Empreendimento', 'Etapa']).agg(
                    Inicio_Prevista=('Inicio_Prevista', 'min'),
                    Termino_Prevista=('Termino_Prevista', 'max'),
                    Inicio_Real=('Inicio_Real', 'min'),
                    Termino_Real=('Termino_Real', 'max'),
                    Percentual_Concluido=('% concluído', 'max') if '% concluído' in df_detalhes.columns else ('% concluído', lambda x: 0)
                ).reset_index()

                if '% concluído' in df_detalhes.columns and not df_agregado.empty and (df_agregado['Percentual_Concluido'].fillna(0).max() <= 1):
                    df_agregado['Percentual_Concluido'] *= 100

                df_agregado['Var. Term'] = df_agregado.apply(
                    lambda row: calculate_business_days(row['Termino_Prevista'], row['Termino_Real']), axis=1
                )
                
                # *** ORDENAÇÃO POR META - USAR ÍNDICE NUMÉRICO DIRETO ***
                # Criar dicionário de mapeamento: empreendimento -> índice de ordem
                ordem_meta_dict = {emp: idx for idx, emp in enumerate(empreendimentos_ordenados_por_meta)}
                
                # Mapear cada empreendimento para seu índice de ordem (número)
                df_agregado['ordem_meta_num'] = df_agregado['Empreendimento'].map(ordem_meta_dict).fillna(9999)
                
                # 1. Mapear a etapa para sua ordem global (agora incluindo subetapas)
                def get_global_order_linear(etapa):
                    try:
                        return ORDEM_ETAPAS_GLOBAL.index(etapa)
                    except ValueError:
                        return len(ORDEM_ETAPAS_GLOBAL) # Coloca no final se não for encontrada

                df_agregado['Etapa_Ordem'] = df_agregado['Etapa'].apply(get_global_order_linear)
                
                # 2. Ordenar: PRIMEIRO por ordem_meta_num, DEPOIS por Ordem da Etapa
                df_ordenado = df_agregado.sort_values(by=['ordem_meta_num', 'Etapa_Ordem'])

                st.write("---")

                etapas_unicas = df_ordenado['Etapa'].unique()
                usar_layout_horizontal = len(etapas_unicas) == 1

                tabela_final_lista = []
                
                if usar_layout_horizontal:
                    tabela_para_processar = df_ordenado.copy()
                    tabela_para_processar['Etapa'] = tabela_para_processar['Etapa'].map(sigla_para_nome_completo)
                    tabela_final_lista.append(tabela_para_processar)
                else:
                    for _, grupo in df_ordenado.groupby('ordem_meta_num', sort=False):
                        if grupo.empty:
                            continue

                        empreendimento = grupo['Empreendimento'].iloc[0]
                        
                        percentual_medio = grupo['Percentual_Concluido'].mean()
                        
                        cabecalho = pd.DataFrame([{
                            'Hierarquia': f'📂 {abreviar_nome(empreendimento)}',
                            'Inicio_Prevista': grupo['Inicio_Prevista'].min(),
                            'Termino_Prevista': grupo['Termino_Prevista'].max(),
                            'Inicio_Real': grupo['Inicio_Real'].min(),
                            'Termino_Real': grupo['Termino_Real'].max(),
                            'Var. Term': grupo['Var. Term'].mean(),
                            'Percentual_Concluido': percentual_medio
                        }])
                        tabela_final_lista.append(cabecalho)

                        grupo_formatado = grupo.copy()
                        grupo_formatado['Hierarquia'] = ' &nbsp; &nbsp; ' + grupo_formatado['Etapa'].map(sigla_para_nome_completo)
                        tabela_final_lista.append(grupo_formatado)

                if not tabela_final_lista:
                    st.info("ℹ️ Nenhum dado para exibir na tabela detalhada com os filtros atuais")
                    pass
                else:
                    tabela_final = pd.concat(tabela_final_lista, ignore_index=True)

                    def aplicar_estilo(df_para_estilo, layout_horizontal):
                        if df_para_estilo.empty:
                            return df_para_estilo.style

                        def estilo_linha(row):
                            style = [''] * len(row)
                            
                            if not layout_horizontal and 'Empreendimento / Etapa' in row.index and str(row['Empreendimento / Etapa']).startswith('📂'):
                                style = ['font-weight: 500; color: #000000; background-color: #F0F2F6; border-left: 4px solid #000000; padding-left: 10px;'] * len(row)
                                for i in range(1, len(style)):
                                    style[i] = "background-color: #F0F2F6;"
                                return style
                            
                            percentual = row.get('% Concluído', 0)
                            if isinstance(percentual, str) and '%' in percentual:
                                try: percentual = int(percentual.replace('%', ''))
                                except: percentual = 0

                            termino_real, termino_previsto = pd.to_datetime(row.get("Término Real"), errors='coerce'), pd.to_datetime(row.get("Término Prev."), errors='coerce')
                            cor = "#000000"
                            if percentual == 100:
                                if pd.notna(termino_real) and pd.notna(termino_previsto):
                                    if termino_real < termino_previsto: cor = "#2EAF5B"
                                    elif termino_real > termino_previsto: cor = "#C30202"
                            elif pd.notna(termino_previsto) and (termino_previsto < pd.Timestamp.now()):
                                cor = "#A38408"

                            for i, col in enumerate(df_para_estilo.columns):
                                if col in ['Início Real', 'Término Real']:
                                    style[i] = f"color: {cor};"

                            if pd.notna(row.get("Var. Term", None)):
                                val = row["Var. Term"]
                                if isinstance(val, str):
                                    try: val = int(val.split()[1]) * (-1 if '▲' in val else 1)
                                    except: val = 0
                                cor_texto = "#e74c3c" if val < 0 else "#2ecc71"
                                style[df_para_estilo.columns.get_loc("Var. Term")] = f"color: {cor_texto}; font-weight: 600; font-size: 12px; text-align: center;"
                            return style

                        styler = df_para_estilo.style.format({
                            "Início Prev.": lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "-",
                            "Término Prev.": lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "-",
                            "Início Real": lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "-",
                            "Término Real": lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "-",
                            "Var. Term": lambda x: f"{'▼' if isinstance(x, (int, float)) and x > 0 else '▲'} {abs(int(x))} dias" if pd.notna(x) else "-",
                            "% Concluído": lambda x: f"{int(x)}%" if pd.notna(x) and str(x) != 'nan' else "-"
                        }, na_rep="-")
                        
                        styler = styler.set_properties(**{'white-space': 'nowrap', 'text-overflow': 'ellipsis', 'overflow': 'hidden', 'max-width': '380px'})
                        styler = styler.apply(estilo_linha, axis=1).hide(axis="index")
                        return styler
                    
                    st.markdown("""
                    <style>
                        .stDataFrame { width: 100%; }
                        .stDataFrame td, .stDataFrame th { white-space: nowrap !important; text-overflow: ellipsis !important; overflow: hidden !important; max-width: 380px !important; }
                    </style>
                    """, unsafe_allow_html=True)

                    colunas_rename = {
                        'Inicio_Prevista': 'Início Prev.', 'Termino_Prevista': 'Término Prev.',
                        'Inicio_Real': 'Início Real', 'Termino_Real': 'Término Real',
                        'Percentual_Concluido': '% Concluído'
                    }
                    
                    if usar_layout_horizontal:
                        colunas_rename['Empreendimento'] = 'Empreendimento (Abrev.)'
                        colunas_rename['Etapa'] = 'Etapa'
                        colunas_para_exibir = ['Empreendimento (Abrev.)', 'Etapa', '% Concluído', 'Início Prev.', 'Término Prev.', 'Início Real', 'Término Real', 'Var. Term']
                    else:
                        colunas_rename['Hierarquia'] = 'Empreendimento / Etapa'
                        colunas_para_exibir = ['Empreendimento / Etapa', '% Concluído', 'Início Prev.', 'Término Prev.', 'Início Real', 'Término Real', 'Var. Term']

                    tabela_para_exibir = tabela_final.rename(columns=colunas_rename)
                    
                    tabela_estilizada = aplicar_estilo(tabela_para_exibir[colunas_para_exibir], layout_horizontal=usar_layout_horizontal)
                    
                    st.markdown(tabela_estilizada.to_html(), unsafe_allow_html=True)

                with tab2:
                    st.subheader("Tabelão Horizontal")
                    
                    if df_detalhes.empty:
                        st.warning("⚠️ Nenhum dado encontrado com os filtros aplicados.")
                    else:
                        hoje = pd.Timestamp.now().normalize()

                        df_detalhes_tabelao = df_detalhes.rename(columns={
                            'Termino_prevista': 'Termino_Prevista',
                            'Termino_real': 'Termino_Real'
                        })
                        
                        for col in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real']:
                            if col in df_detalhes_tabelao.columns:
                                df_detalhes_tabelao[col] = df_detalhes_tabelao[col].replace('-', pd.NA)
                                df_detalhes_tabelao[col] = pd.to_datetime(df_detalhes_tabelao[col], errors='coerce')

                        # --- Bloco de Agregação e Ordenação (sem alterações) ---
                        st.write("---")
                        col1, col2 = st.columns(2)
                        
                        opcoes_classificacao = {
                            'Padrão (UGB, Empreendimento e Etapa)': ['UGB', 'Empreendimento', 'Etapa_Ordem'],
                            'Meta de Assinatura': ['ordem_meta', 'Etapa_Ordem'],
                            'UGB (A-Z)': ['UGB'],
                            'Empreendimento (A-Z)': ['Empreendimento'],
                            'Data de Início Previsto (Mais antiga)': ['Inicio_Prevista'],
                            'Data de Término Previsto (Mais recente)': ['Termino_Prevista'],
                        }
                        
                        with col1:
                            classificar_por = st.selectbox(
                                "Ordenar tabela por:",
                                options=list(opcoes_classificacao.keys()),
                                index=1,  # Meta de Assinatura como padrão
                                key="classificar_por_selectbox"
                            )
                            
                        with col2:
                            ordem = st.radio(
                                "Ordem:",
                                options=['Crescente', 'Decrescente'],
                                horizontal=True,
                                key="ordem_radio"
                            )

                        def get_global_order_linear_tabelao(etapa):
                            try:
                                return ORDEM_ETAPAS_GLOBAL.index(etapa)
                            except ValueError:
                                return len(ORDEM_ETAPAS_GLOBAL)

                        df_detalhes_tabelao['Etapa_Ordem'] = df_detalhes_tabelao['Etapa'].apply(get_global_order_linear_tabelao)
                        
                        agg_dict = {
                            'Inicio_Prevista': ('Inicio_Prevista', 'min'),
                            'Termino_Prevista': ('Termino_Prevista', 'max'),
                            'Inicio_Real': ('Inicio_Real', 'min'),
                            'Termino_Real': ('Termino_Real', 'max'),
                        }
                        
                        if '% concluído' in df_detalhes_tabelao.columns:
                            agg_dict['Percentual_Concluido'] = ('% concluído', 'mean')

                        # *** CALCULAR ORDEM POR META ANTES DE ABREVIAR NOMES ***
                        # Criar ordenação por meta de assinatura usando nomes completos
                        empreendimentos_ordenados_por_meta = criar_ordenacao_empreendimentos(df_data)
                        ordem_meta_dict = {emp: idx for idx, emp in enumerate(empreendimentos_ordenados_por_meta)}
                        
                        # Mapear ordem de meta para cada empreendimento (ainda com nome completo)
                        df_detalhes_tabelao['ordem_meta'] = df_detalhes_tabelao['Empreendimento'].map(ordem_meta_dict).fillna(999)
                        
                        # Agora abreviar os nomes dos empreendimentos
                        df_detalhes_tabelao['Empreendimento'] = df_detalhes_tabelao['Empreendimento'].apply(abreviar_nome)
                        
                        # Adicionar ordem_meta ao agg_dict para preservar após groupby
                        agg_dict['ordem_meta'] = ('ordem_meta', 'first')
                        
                        df_agregado = df_detalhes_tabelao.groupby(['UGB', 'Empreendimento', 'Etapa']).agg(**agg_dict).reset_index()
                        
                        df_agregado['Var. Term'] = df_agregado.apply(lambda row: calculate_business_days(row['Termino_Prevista'], row['Termino_Real']), axis=1)
                        
                        ordem_etapas_completas = ORDEM_ETAPAS_GLOBAL
                        df_agregado['Etapa_Ordem'] = df_agregado['Etapa'].apply(
                            lambda x: ordem_etapas_completas.index(x) if x in ordem_etapas_completas else len(ordem_etapas_completas)
                        )

                        df_ordenado = df_agregado.sort_values(
                            by=opcoes_classificacao[classificar_por],
                            ascending=(ordem == 'Crescente')
                        )
                        
                        st.write("---")

                        df_pivot = df_ordenado.pivot_table(
                            index=['UGB', 'Empreendimento'],
                            columns='Etapa',
                            values=['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real', 'Var. Term'],
                            aggfunc='first'
                        )

                        etapas_existentes_no_pivot = df_pivot.columns.get_level_values(1).unique()
                        colunas_ordenadas = []
                        
                        for etapa in ordem_etapas_completas:
                            if etapa in etapas_existentes_no_pivot:
                                for tipo in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real', 'Var. Term']:
                                    if (tipo, etapa) in df_pivot.columns:
                                        colunas_ordenadas.append((tipo, etapa))
                        
                        df_final = df_pivot[colunas_ordenadas] # Não reseta o índice ainda

                        # --- INÍCIO DA CORREÇÃO ---

                        # 1. Renomear colunas ANTES de formatar
                        novos_nomes = []
                        for col in df_final.columns:
                            tipo, etapa = col[0], col[1]
                            nome_etapa = sigla_para_nome_completo.get(etapa, etapa)
                            nome_tipo = {
                                'Inicio_Prevista': 'Início Prev.',
                                'Termino_Prevista': 'Término Prev.',
                                'Inicio_Real': 'Início Real',
                                'Termino_Real': 'Término Real',
                                'Var. Term': 'VarTerm'
                            }[tipo]
                            novos_nomes.append((nome_etapa, nome_tipo))
                        
                        df_final.columns = pd.MultiIndex.from_tuples(novos_nomes)

                        # 2. Função de formatação (sem alterações)
                        def formatar_valor(valor, tipo):
                            if pd.isna(valor):
                                return "-"
                            if tipo == 'data':
                                return valor.strftime("%d/%m/%Y")
                            if tipo == 'variacao':
                                sinal = '▼' if valor > 0 else ('▲' if valor < 0 else '▶')
                                return f"{sinal} {abs(int(valor))} dias"
                            return str(valor)

                        # 3. Criar o DataFrame formatado para exibição
                        df_formatado = df_final.copy()
                        for col_tuple in df_formatado.columns:
                            if any(x in col_tuple[1] for x in ["Início Prev.", "Término Prev.", "Início Real", "Término Real"]):
                                df_formatado[col_tuple] = df_formatado[col_tuple].apply(lambda x: formatar_valor(x, "data"))
                            elif "VarTerm" in col_tuple[1]:
                                df_formatado[col_tuple] = df_formatado[col_tuple].apply(lambda x: formatar_valor(x, "variacao"))

                        # 4. Resetar o índice e renomear colunas de índice
                        df_formatado.reset_index(inplace=True)
                        df_formatado.rename(columns={'UGB': 'UGB', 'Empreendimento': 'Empreendimento (Abrev.)'}, inplace=True)
                        df_formatado.set_index(['UGB', 'Empreendimento (Abrev.)'], inplace=True)

                        # 5. Função de estilização REESCRITA
                        def aplicar_estilos(styler):
                            # Função interna para determinar a cor
                            def determinar_cor(row_index, col_tuple):
                                ugb, empreendimento = row_index
                                etapa_nome_completo, tipo_dado = col_tuple

                                if tipo_dado not in ['Início Real', 'Término Real']:
                                    return ''

                                etapa_sigla = nome_completo_para_sigla.get(etapa_nome_completo)
                                if not etapa_sigla:
                                    return ''

                                # Busca no df_agregado original
                                etapa_data = df_agregado[
                                    (df_agregado['UGB'] == ugb) &
                                    (df_agregado['Empreendimento'] == empreendimento) &
                                    (df_agregado['Etapa'] == etapa_sigla)
                                ]

                                if not etapa_data.empty:
                                    dados = etapa_data.iloc[0]
                                    percentual = dados.get('Percentual_Concluido', 0)
                                    termino_real = pd.to_datetime(dados.get('Termino_Real'), errors='coerce')
                                    termino_previsto = pd.to_datetime(dados.get('Termino_Prevista'), errors='coerce')

                                    if percentual == 100:
                                        if pd.notna(termino_real) and pd.notna(termino_previsto):
                                            if termino_real < termino_previsto: return "color: #2EAF5B; font-weight: bold;"
                                            if termino_real > termino_previsto: return "color: #C30202; font-weight: bold;"
                                    elif percentual < 100 and pd.notna(termino_previsto) and (termino_previsto < hoje):
                                        return "color: #A38408; font-weight: bold;"
                                return ''

                            # Aplica a estilização célula por célula
                            for i, row in enumerate(styler.data.itertuples()):
                                cor_fundo = "#fbfbfb" if i % 2 == 0 else '#ffffff'
                                styler.set_properties(subset=pd.IndexSlice[row.Index, :], **{'background-color': cor_fundo})

                                for j, col in enumerate(styler.columns):
                                    style = ''
                                    # Cor para dados de variação
                                    if 'VarTerm' in col[1]:
                                        valor_original = df_final.loc[row.Index, col]
                                        if pd.notna(valor_original):
                                            if valor_original > 0: style += 'color: #e74c3c; font-weight: 600;'
                                            elif valor_original < 0: style += 'color: #2ecc71; font-weight: 600;'
                                    
                                    # Cor para datas reais
                                    style += determinar_cor(row.Index, col)
                                    
                                    if style:
                                        styler.apply(lambda x, style=style: [style] * len(x), subset=pd.IndexSlice[row.Index, col], axis=0)
                            
                            return styler

                        # 6. Estilos do cabeçalho e da tabela
                        header_styles = [
                            {'selector': 'th.level0', 'props': [('font-size', '12px'), ('font-weight', 'bold'), ('background-color', "#6c6d6d"), ('border-bottom', '2px solid #ddd'), ('text-align', 'center'), ('white-space', 'nowrap')]},
                            {'selector': 'th.level1', 'props': [('font-size', '11px'), ('font-weight', 'normal'), ('background-color', '#f8f9fa'), ('text-align', 'center'), ('white-space', 'nowrap')]},
                            {'selector': 'td', 'props': [('font-size', '12px'), ('text-align', 'center'), ('padding', '5px 8px'), ('border', '1px solid #f0f0f0')]},
                        ]
                        
                        # 7. Aplicar estilos e exibir
                        styled_df = df_formatado.style.pipe(aplicar_estilos)
                        styled_df = styled_df.set_table_styles(header_styles)

                        st.dataframe(
                            styled_df,
                            height=min(35 * len(df_formatado) + 80, 600), # Aumentado para caber o header duplo
                            use_container_width=True
                        )
                        
                        # Legenda (sem alterações)
                        st.markdown("""<div style="margin-top: 10px; font-size: 12px; color: #555;">
                            <strong>Legenda:</strong> 
                            <span style="color: #2EAF5B; font-weight: bold;">■ Concluído antes do prazo</span> | 
                            <span style="color: #C30202; font-weight: bold;">■ Concluído com atraso</span> | 
                            <span style="color: #A38408; font-weight: bold;">■ Atrasado</span> | 
                            <span style="color: #000000; font-weight: bold;">■ Em andamento</span>
                        </div>""", unsafe_allow_html=True)

    else:
        st.error("❌ Não foi possível carregar ou gerar os dados.")
