import streamlit as st
import pandas as pd
import matplotlib as mpl
mpl.use('agg')  # Usar backend não interativo
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Rectangle
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
from datetime import datetime

# Tenta importar os scripts de processamento de dados.
try:
    from processa_venda_registro import tratar_e_retornar_dados_previstos
    from processa_venda_smartsheet import main as processar_smartsheet_main
except ImportError:
    st.warning("Scripts de processamento não encontrados. O app usará dados de exemplo.")
    tratar_e_retornar_dados_previstos = None
    processar_smartsheet_main = None

# --- Configurações de Estilo ---
class StyleConfig:
    LARGURA_GANTT = 10
    ALTURA_GANTT_POR_ITEM = 1.2
    ALTURA_BARRA_GANTT = 0.35
    LARGURA_TABELA = 4.5
    COR_PREVISTO = '#A8C5DA'
    COR_REAL = '#174c66'
    COR_HOJE = 'red'
    COR_CONCLUIDO = '#047031'
    COR_ATRASADO = '#a83232'
    COR_META_ASSINATURA = '#8e44ad'
    FONTE_TITULO = {'size': 14, 'weight': 'bold', 'color': 'black'}
    FONTE_ETAPA = {'size': 12, 'weight': 'bold', 'color': '#2c3e50'}
    FONTE_DATAS = {'family': 'monospace', 'size': 10, 'color': '#2c3e50'}
    FONTE_PORCENTAGEM = {'size': 12, 'weight': 'bold'}
    CABECALHO = {'facecolor': '#2c3e50', 'edgecolor': 'none', 'pad': 4.0, 'color': 'white'}
    CELULA_PAR = {'facecolor': 'white', 'edgecolor': '#d1d5db', 'lw': 0.8}
    CELULA_IMPAR = {'facecolor': '#f1f3f5', 'edgecolor': '#d1d5db', 'lw': 0.8}
    FUNDO_TABELA = '#f8f9fa'
    ESPACO_ENTRE_EMPREENDIMENTOS = 1.5

# --- Funções Utilitárias e Mapeamentos ---
def converter_porcentagem(valor):
    if pd.isna(valor) or valor == '': return 0.0
    if isinstance(valor, str):
        valor = ''.join(c for c in valor if c.isdigit() or c in ['.', ',']).replace(',', '.').strip()
        if not valor: return 0.0
    try:
        return float(valor) * 100 if float(valor) <= 1 else float(valor)
    except (ValueError, TypeError):
        return 0.0

def formatar_data(data):
    return data.strftime("%d/%m/%y") if pd.notna(data) else "N/D"

sigla_para_nome_completo = {
    'DM': '1.DEFINIÇÃO DO MÓDULO', 'DOC': '2.DOCUMENTAÇÃO', 'ENG': '3.ENGENHARIA',
    'MEM': '4.MEMORIAL', 'LAE': '5.LAE', 'CONT': '6.CONTRATAÇÃO', 'ASS': '7.ASSINATURA',
}
nome_completo_para_sigla = {v: k for k, v in sigla_para_nome_completo.items()}
mapeamento_variacoes_real = {
    'DEFINIÇÃO DO MÓDULO': 'DM', 'DOCUMENTAÇÃO': 'DOC', 'ENGENHARIA': 'ENG',
    'MEMORIAL': 'MEM', 'LAE': 'LAE', 'CONTRATAÇÃO': 'CONT', 'ASSINATURA': 'ASS',
    'PLANEJAMENTO': 'DM', 'ENGENHARIA CEF': 'ENG', 'MEMORIAL DE INCORPORAÇÃO': 'MEM',
    'EMISSÃO DO LAE': 'LAE', 'CONTESTAÇÃO': 'LAE', 'DJE': 'CONT', 'ANÁLISE DE RISCO': 'CONT',
    'MORAR BEM': 'ASS', 'SEGUROS': 'ASS', 'ATESTE': 'ASS', 'DEMANDA MÍNIMA': 'ASS',
}

def padronizar_etapa(etapa_str):
    if pd.isna(etapa_str): return 'UNKNOWN'
    etapa_str = str(etapa_str).strip().upper()
    for k, v in mapeamento_variacoes_real.items():
        if k == etapa_str: return v
    for k, v in nome_completo_para_sigla.items():
        if k == etapa_str: return v
    if etapa_str in sigla_para_nome_completo: return etapa_str
    return 'UNKNOWN'

# --- Função Principal do Gráfico de Gantt ---
def gerar_gantt(df, tipo_visualizacao="Ambos"):
    if df.empty:
        st.warning("Sem dados disponíveis para exibir o Gantt.")
        return

    plt.rcParams['figure.dpi'] = 150
    plt.rcParams['savefig.dpi'] = 150

    # --- Preparação e Ordenação dos Dados ---
    for col in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real']:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    if '% concluído' not in df.columns: df['% concluído'] = 0.0
    else: df['% concluído'] = df['% concluído'].apply(converter_porcentagem)

    num_empreendimentos = df['Empreendimento'].nunique()
    num_etapas = df['Etapa'].nunique()

    if num_empreendimentos > 1 and num_etapas == 1:
        df = df.sort_values('Inicio_Prevista', ascending=True)
    else:
        ordem_etapas = list(sigla_para_nome_completo.keys())
        df['Etapa_Ordem'] = df['Etapa'].apply(lambda x: ordem_etapas.index(x) if x in ordem_etapas else len(ordem_etapas))
        df = df.sort_values(['Empreendimento', 'Etapa_Ordem'])

    hoje = pd.Timestamp.now()

    # --- Lógica de Posicionamento ---
    rotulo_para_posicao = {}
    posicao = 0
    empreendimentos_unicos = df['Empreendimento'].unique()
    for empreendimento in empreendimentos_unicos:
        if num_empreendimentos > 1 and num_etapas == 1:
             rotulo = empreendimento
             rotulo_para_posicao[rotulo] = posicao
             posicao += 1
        else:
            etapas_do_empreendimento = df[df['Empreendimento'] == empreendimento]['Etapa'].unique()
            for etapa in etapas_do_empreendimento:
                rotulo = f'{empreendimento}||{etapa}'
                rotulo_para_posicao[rotulo] = posicao
                posicao += 1
        if num_empreendimentos > 1 and num_etapas > 1:
            posicao += StyleConfig.ESPACO_ENTRE_EMPREENDIMENTOS / 2

    if num_empreendimentos > 1 and num_etapas == 1:
        df['Posicao'] = df['Empreendimento'].map(rotulo_para_posicao)
    else:
        df['Posicao'] = (df['Empreendimento'] + '||' + df['Etapa']).map(rotulo_para_posicao)
    df.dropna(subset=['Posicao'], inplace=True)

    # --- Configuração da Figura ---
    num_linhas = len(rotulo_para_posicao)
    altura_total = max(10, num_linhas * StyleConfig.ALTURA_GANTT_POR_ITEM)
    figura = plt.figure(figsize=(StyleConfig.LARGURA_TABELA + StyleConfig.LARGURA_GANTT, altura_total))
    grade = gridspec.GridSpec(1, 2, width_ratios=[StyleConfig.LARGURA_TABELA, StyleConfig.LARGURA_GANTT], wspace=0.01)

    eixo_tabela = figura.add_subplot(grade[0], facecolor=StyleConfig.FUNDO_TABELA)
    eixo_gantt = figura.add_subplot(grade[1], sharey=eixo_tabela)
    eixo_tabela.axis('off')

    # --- Consolidação de Dados para a Tabela e Gantt ---
    dados_consolidados = df.groupby('Posicao').agg({
        'Empreendimento': 'first', 'Etapa': 'first',
        'Inicio_Prevista': 'min', 'Termino_Prevista': 'max',
        'Inicio_Real': 'min', 'Termino_Real': 'max',
        '% concluído': 'max'
    }).reset_index()

    # --- Desenho da Tabela ---
    empreendimento_atual = None
    for _, linha in dados_consolidados.iterrows():
        y_pos = linha['Posicao']
        
        if not (num_empreendimentos > 1 and num_etapas == 1) and linha['Empreendimento'] != empreendimento_atual:
            empreendimento_atual = linha['Empreendimento']
            y_cabecalho = y_pos - (StyleConfig.ALTURA_GANTT_POR_ITEM / 2) - 0.2
            eixo_tabela.text(0.5, y_cabecalho, empreendimento_atual,
                            va="center", ha="center", bbox=StyleConfig.CABECALHO, **StyleConfig.FONTE_TITULO)

        estilo_celula = StyleConfig.CELULA_PAR if int(y_pos) % 2 == 0 else StyleConfig.CELULA_IMPAR
        eixo_tabela.add_patch(Rectangle((0.01, y_pos - 0.5), 0.98, 1.0,
                           facecolor=estilo_celula["facecolor"], edgecolor=estilo_celula["edgecolor"], lw=estilo_celula["lw"]))

        texto_principal = linha['Empreendimento'] if (num_empreendimentos > 1 and num_etapas == 1) else sigla_para_nome_completo.get(linha['Etapa'], linha['Etapa'])
        eixo_tabela.text(0.04, y_pos - 0.2, texto_principal, va="center", ha="left", **StyleConfig.FONTE_ETAPA)
        
        texto_prev = f"Prev: {formatar_data(linha['Inicio_Prevista'])} → {formatar_data(linha['Termino_Prevista'])}"
        texto_real = f"Real: {formatar_data(linha['Inicio_Real'])} → {formatar_data(linha['Termino_Real'])}"
        eixo_tabela.text(0.04, y_pos + 0.05, f"{texto_prev:<28}", va="center", ha="left", **StyleConfig.FONTE_DATAS)
        eixo_tabela.text(0.04, y_pos + 0.28, f"{texto_real:<28}", va="center", ha="left", **StyleConfig.FONTE_DATAS)

        percentual = linha['% concluído']
        cor_texto = StyleConfig.COR_ATRASADO if (pd.notna(linha['Termino_Prevista']) and linha['Termino_Prevista'] < hoje and percentual < 100) else StyleConfig.COR_CONCLUIDO if percentual == 100 else '#2c3e50'
        cor_caixa = '#fae6e6' if cor_texto == StyleConfig.COR_ATRASADO else '#e6f5eb' if cor_texto == StyleConfig.COR_CONCLUIDO else estilo_celula['facecolor']
        eixo_tabela.add_patch(Rectangle((0.78, y_pos - 0.2), 0.2, 0.4, facecolor=cor_caixa, edgecolor="#d1d5db", lw=0.8))
        eixo_tabela.text(0.88, y_pos, f"{percentual:.0f}%", va="center", ha="center", color=cor_texto, **StyleConfig.FONTE_PORCENTAGEM)

    # --- Desenho das Barras (CORRIGIDO PARA SER CONTÍNUO) ---
    for _, linha in dados_consolidados.iterrows():
        y_pos = linha['Posicao']
        ALTURA_BARRA = StyleConfig.ALTURA_BARRA_GANTT
        ESPACAMENTO = StyleConfig.ALTURA_BARRA_GANTT * 0.5

        # Barra Prevista Contínua
        if tipo_visualizacao in ["Ambos", "Previsto"] and pd.notna(linha['Inicio_Prevista']) and pd.notna(linha['Termino_Prevista']):
           duracao = (linha['Termino_Prevista'] - linha['Inicio_Prevista']).days + 1
           eixo_gantt.barh(y=y_pos - ESPACAMENTO, width=duracao, left=linha['Inicio_Prevista'],
                          height=ALTURA_BARRA, color=StyleConfig.COR_PREVISTO, alpha=0.9,
                          antialiased=False)

        # Barra Real Contínua
        if tipo_visualizacao in ["Ambos", "Real"] and pd.notna(linha['Inicio_Real']):
            termino_real = linha['Termino_Real'] if pd.notna(linha['Termino_Real']) else hoje
            duracao = (termino_real - linha['Inicio_Real']).days + 1
            eixo_gantt.barh(y=y_pos + ESPACAMENTO, width=duracao, left=linha['Inicio_Real'],
                           height=ALTURA_BARRA, color=StyleConfig.COR_REAL, alpha=0.9,
                           antialiased=False)

    # --- Formatação Final dos Eixos ---
    if not rotulo_para_posicao:
        st.pyplot(figura)
        return

    max_pos = max(rotulo_para_posicao.values())
    eixo_gantt.set_ylim(max_pos + 1, -1)
    eixo_gantt.set_yticks([])
    
    for pos in rotulo_para_posicao.values():
        eixo_gantt.axhline(y=pos + 0.5, color='#dcdcdc', linestyle='-', alpha=0.7, linewidth=0.8)
    
    eixo_gantt.axvline(hoje, color=StyleConfig.COR_HOJE, linestyle='--', linewidth=1.5)
    eixo_gantt.text(hoje, eixo_gantt.get_ylim()[0], ' Hoje', color=StyleConfig.COR_HOJE, fontsize=10, ha='left')

    if num_empreendimentos == 1 and num_etapas > 1:
        empreendimento = df["Empreendimento"].unique()[0]
        df_assinatura = df[(df["Empreendimento"] == empreendimento) & (df["Etapa"] == "ASS")]
        
        if not df_assinatura.empty:
            data_meta = None
            if pd.notna(df_assinatura["Termino_Prevista"].iloc[0]):
                data_meta = df_assinatura["Termino_Prevista"].iloc[0]
                tipo_meta = "Prevista"
            elif pd.notna(df_assinatura["Termino_Real"].iloc[0]):
                data_meta = df_assinatura["Termino_Real"].iloc[0]
                tipo_meta = "Real"

            if data_meta is not None:
                eixo_gantt.axvline(data_meta, color=StyleConfig.COR_META_ASSINATURA, 
                                   linestyle="--", linewidth=1.7, alpha=0.7)
                eixo_gantt.text(data_meta, eixo_gantt.get_ylim()[1] + 0.2,
                              f"Meta {tipo_meta}\nAssinatura: {data_meta.strftime('%d/%m/%y')}", 
                              color=StyleConfig.COR_META_ASSINATURA, fontsize=12, 
                              ha="center", va="top",
                              bbox=dict(facecolor="white", alpha=0.8, edgecolor=StyleConfig.COR_META_ASSINATURA))

    eixo_gantt.grid(axis='x', linestyle='--', alpha=0.6)
    eixo_gantt.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    eixo_gantt.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
    plt.setp(eixo_gantt.get_xticklabels(), rotation=90, ha='center')

    handles_legenda = [Patch(color=StyleConfig.COR_PREVISTO, label='Previsto'), Patch(color=StyleConfig.COR_REAL, label='Real')]
    eixo_gantt.legend(handles=handles_legenda, loc='upper center', bbox_to_anchor=(0.5, -0.2), ncol=2, frameon=False)

    plt.tight_layout(rect=[0, 0.05, 1, 1])
    st.pyplot(figura)
    plt.close(figura)

# --- Lógica Principal do App Streamlit (sem alterações) ---
st.set_page_config(layout="wide", page_title="Dashboard de Gantt Comparativo")

@st.cache_data
def load_data():
    df_real = pd.DataFrame()
    df_previsto = pd.DataFrame()

    if processar_smartsheet_main:
        try:
            processar_smartsheet_main()
            df_real = pd.read_csv('modulos_venda_tratados.csv')
        except Exception as e:
            st.warning(f"Erro ao carregar dados reais do Smartsheet: {e}")

    if tratar_e_retornar_dados_previstos:
        try:
            df_previsto = tratar_e_retornar_dados_previstos()
            if df_previsto is None: df_previsto = pd.DataFrame()
        except Exception as e:
            st.warning(f"Erro ao carregar dados previstos: {e}")

    if df_real.empty and df_previsto.empty:
        st.warning("Nenhuma fonte de dados carregada. Usando dados de exemplo.")
        return criar_dados_exemplo()

    # Padronização e Merge
    if not df_real.empty:
        df_real['Etapa'] = df_real['Etapa'].apply(padronizar_etapa)
        df_real.rename(columns={'Emp': 'Empreendimento', 'Iniciar': 'Inicio_Real', 'Terminar': 'Termino_Real'}, inplace=True)
        df_real['% concluído'] = df_real.get('% concluído', pd.Series(0.0)).apply(converter_porcentagem)

    if not df_previsto.empty:
        df_previsto['Etapa'] = df_previsto['Etapa'].apply(padronizar_etapa)
        df_previsto.rename(columns={'EMP': 'Empreendimento', 'Valor': 'Data_Prevista'}, inplace=True)
        df_previsto_pivot = df_previsto.pivot_table(
            index=['UGB', 'Empreendimento', 'Etapa'], columns='Inicio_Fim', values='Data_Prevista', aggfunc='first'
        ).reset_index()
        df_previsto_pivot.rename(columns={'INÍCIO': 'Inicio_Prevista', 'TÉRMINO': 'Termino_Prevista'}, inplace=True)
    else:
        df_previsto_pivot = pd.DataFrame(columns=['UGB', 'Empreendimento', 'Etapa', 'Inicio_Prevista', 'Termino_Prevista'])

    # Merge final
    if not df_real.empty:
        df_merged = pd.merge(
            df_previsto_pivot,
            df_real[['UGB', 'Empreendimento', 'Etapa', 'Inicio_Real', 'Termino_Real', '% concluído']],
            on=['UGB', 'Empreendimento', 'Etapa'],
            how='outer'
        )
    else:
        df_merged = df_previsto_pivot
    
    df_merged['% concluído'] = df_merged.get('% concluído', pd.Series(0.0)).fillna(0)
    if 'Inicio_Real' not in df_merged: df_merged[['Inicio_Real', 'Termino_Real']] = pd.NaT

    df_merged.dropna(subset=['Empreendimento', 'Etapa'], inplace=True)
    return df_merged

def criar_dados_exemplo():
    dados = {
        'UGB': ['UGB1', 'UGB1', 'UGB1', 'UGB2', 'UGB2', 'UGB1'],
        'Empreendimento': ['Residencial Alfa', 'Residencial Alfa', 'Residencial Alfa', 'Condomínio Beta', 'Condomínio Beta', 'Projeto Gama'],
        'Etapa': ['DM', 'DOC', 'ENG', 'DM', 'DOC', 'DM'],
        'Inicio_Prevista': pd.to_datetime(['2024-02-01', '2024-03-01', '2024-04-15', '2024-03-20', '2024-05-01', '2024-01-10']),
        'Termino_Prevista': pd.to_datetime(['2024-02-28', '2024-04-10', '2024-05-30', '2024-04-28', '2024-06-15', '2024-01-31']),
        'Inicio_Real': pd.to_datetime(['2024-02-05', '2024-03-03', pd.NaT, '2024-03-25', '2024-05-05', '2024-01-12']),
        'Termino_Real': pd.to_datetime(['2024-03-02', '2024-04-15', pd.NaT, '2024-05-05', pd.NaT, '2024-02-01']),
        '% concluído': [100, 100, 40, 100, 85, 100]
    }
    return pd.DataFrame(dados)
