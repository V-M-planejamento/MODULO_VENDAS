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

    # MODIFICAÇÃO PRINCIPAL - ORDENAÇÃO POR DATA REAL QUANDO APLICÁVEL
    if num_empreendimentos > 1 and num_etapas == 1:
        if tipo_visualizacao == "Real":
            df = df.sort_values('Inicio_Real', ascending=True)
        else:
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

    # --- Desenho das Barras ---
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

# --- Interface do Streamlit ---
st.title("Módulo Vendas")

with st.spinner('Carregando e processando dados...'):
    df_data = load_data()

if df_data is not None and not df_data.empty:
    try:
        # Cria 3 colunas: a do meio é mais larga para conter a imagem
        col1, col2, col3 = st.sidebar.columns([1, 2, 1])
        with col2:
            # Substitua "seu_logo.png" pelo nome do seu arquivo de imagem
            st.image("logoNova.png", width=80) 
    except Exception as e:
        st.sidebar.warning(f"Não foi possível carregar a imagem. Verifique o nome e o local do arquivo.")

    st.sidebar.header("Filtros")
    
    ugb_list = ["Todos"] + sorted(df_data["UGB"].dropna().unique().tolist())
    selected_ugb = st.sidebar.selectbox("Filtrar por UGB", ugb_list)
    
    df_filtered = df_data[df_data["UGB"] == selected_ugb] if selected_ugb != "Todos" else df_data
    
    emp_list = ["Todos"] + sorted(df_filtered["Empreendimento"].dropna().unique().tolist())
    selected_emp = st.sidebar.selectbox("Filtrar por Empreendimento", emp_list)

    if selected_emp != "Todos":
        df_filtered = df_filtered[df_filtered["Empreendimento"] == selected_emp]

    etapas_disponiveis = sorted(df_filtered["Etapa"].dropna().unique(), key=lambda x: list(sigla_para_nome_completo.keys()).index(x) if x in sigla_para_nome_completo else 99)
    etapas_list = ["Todos"] + [sigla_para_nome_completo.get(e, e) for e in etapas_disponiveis]
    selected_etapa_nome = st.sidebar.selectbox("Filtrar por Etapa", etapas_list)

    if selected_etapa_nome != "Todos":
        sigla_selecionada = nome_completo_para_sigla.get(selected_etapa_nome, selected_etapa_nome)
        df_filtered = df_filtered[df_filtered["Etapa"] == sigla_selecionada]

    tipo_visualizacao = st.sidebar.radio("Mostrar dados:", ("Ambos", "Previsto", "Real"))

    tab1, tab2, tab3, tab4 = st.tabs(["📈 Gráfico de Gantt", "📋 Dados Detalhados", "📊 Etapas – Previsto vs Real", "💾 Tabelão"])

    with tab1:
        st.subheader("Gantt Comparativo")
        if df_filtered.empty:
            st.warning("⚠️ Nenhum dado encontrado com os filtros aplicados.")
        else:
            gerar_gantt(df_filtered.copy(), tipo_visualizacao)

    with tab2:
        st.subheader("Dados Filtrados")
        st.dataframe(df_filtered, use_container_width=True)
        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Exportar para CSV",
            data=csv,
            file_name=f'dados_gantt_{datetime.now().strftime("%Y%m%d")}.csv',
            mime='text/csv',
        )
    with tab3:
        st.subheader("Visão Detalhada por Empreendimento")
    # CSS Customizado para a aparência geral da tabela
    st.markdown("""
    <style>
        .dataframe {
            border: none;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            font-size: 14px;
        }
        .dataframe th, .dataframe td {
            border: none;
            padding: 10px 8px;
            text-align: left;
        }
        .dataframe th {
            background-color: #F0F2F6;
            color: #333;
            font-weight: 600;
            border-bottom: 2px solid #174c66;
        }
        .dataframe tbody tr {
            background-color: white !important;
            border-bottom: 1px solid #e0e0e0;
        }
        .dataframe tbody tr:hover {
            background-color: #f5f5f5 !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    if df_filtered.empty:
        st.warning("⚠️ Nenhum dado encontrado com os filtros aplicados.")
    else:
        # --- 1. PREPARAÇÃO E AGREGAÇÃO DOS DADOS ---
        df_detalhes = df_filtered.copy()
        hoje = pd.Timestamp.now().normalize()

        # Convert columns to datetime
        for col in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real']:
            df_detalhes[col] = pd.to_datetime(df_detalhes[col], errors='coerce')

        # Create completion validation flag
        df_detalhes['Conclusao_Valida'] = False
        if '% concluído' in df_detalhes.columns:
            # Verifica se está 100% concluído E se tem data real anterior à prevista
            mask = (
                (df_detalhes['% concluído'] == 1) & 
                (df_detalhes['Termino_Real'].notna()) &
                ((df_detalhes['Termino_Prevista'].isna()) | 
                 (df_detalhes['Termino_Real'] <= df_detalhes['Termino_Prevista']))
            )
            df_detalhes.loc[mask, 'Conclusao_Valida'] = True

        # Aggregate data
        df_agregado = df_detalhes.groupby(['Empreendimento', 'Etapa']).agg(
            Inicio_Prevista=('Inicio_Prevista', 'min'),
            Termino_Prevista=('Termino_Prevista', 'max'),
            Inicio_Real=('Inicio_Real', 'min'),
            Termino_Real=('Termino_Real', 'max'),
            Concluido_Valido=('Conclusao_Valida', 'any'),
            Percentual_Concluido=('% concluído', 'max') if '% concluído' in df_detalhes.columns else ('% concluído', lambda x: 0)
        ).reset_index()

        df_agregado['Var. Term'] = (df_agregado['Termino_Prevista'] - df_agregado['Termino_Real']).dt.days

        # --- 2. CONTROLES DE CLASSIFICAÇÃO ---
        st.write("---")
        col1, col2 = st.columns(2)
        
        opcoes_classificacao = {
            'Padrão (Empreendimento e Etapa)': ['Empreendimento', 'Etapa_Ordem'],
            'Empreendimento (A-Z)': ['Empreendimento'],
            'Data de Início Previsto (Mais antiga)': ['Inicio_Prevista'],
            'Data de Término Previsto (Mais recente)': ['Termino_Prevista'],
            'Variação de Prazo (Pior para Melhor)': ['Var. Term']
        }

        with col1:
            classificar_por = st.selectbox("Ordenar tabela por:", options=list(opcoes_classificacao.keys()))
        with col2:
            ordem = st.radio("Ordem:", options=['Crescente', 'Decrescente'], horizontal=True)

        ordem_bool = (ordem == 'Crescente')
        colunas_para_ordenar = opcoes_classificacao[classificar_por]
        
        ordem_etapas = list(sigla_para_nome_completo.keys())
        df_agregado['Etapa_Ordem'] = df_agregado['Etapa'].apply(lambda x: ordem_etapas.index(x) if x in ordem_etapas else len(ordem_etapas))
        
        df_ordenado = df_agregado.sort_values(by=colunas_para_ordenar, ascending=ordem_bool)
        st.write("---")

        # --- 3. MONTAGEM DA ESTRUTURA HIERÁRQUICA ---
        tabela_final_lista = []
        for empreendimento, grupo in df_ordenado.groupby('Empreendimento', sort=False):
            cabecalho = pd.DataFrame([{
                'Hierarquia': f'📂 {empreendimento}', 
                'Inicio_Prevista': pd.NaT, 
                'Termino_Prevista': pd.NaT,
                'Inicio_Real': pd.NaT, 
                'Termino_Real': pd.NaT, 
                'Var. Term': pd.NA,
                'Percentual_Concluido': pd.NA
            }])
            tabela_final_lista.append(cabecalho)
            
            grupo_formatado = grupo.copy()
            grupo_formatado['Hierarquia'] = ' &nbsp; &nbsp; ' + grupo_formatado['Etapa'].map(sigla_para_nome_completo)
            tabela_final_lista.append(grupo_formatado)

        tabela_final = pd.concat(tabela_final_lista, ignore_index=True)

        # --- 4. APLICAÇÃO DE ESTILO CONDICIONAL ---
        def aplicar_estilo(df_para_estilo):
            if df_para_estilo.empty:
                return df_para_estilo.style

            def estilo_linha(row):
                style = [None] * len(row)
                
                # Header style
                if pd.isna(row["Término Prev."]):
                    style[0] = "font-weight: 600; color: #174c66; background-color: #F0F2F6;"
                    for i in range(1, len(style)): 
                        style[i] = "background-color: #F0F2F6;"
                    return style
                
                # Get status values
                percentual = row.get('Percentual_Concluido', 0)
                termino_real = row["Término Real"]
                termino_previsto = row["Término Prev."]
                                
                if percentual == 1:
                    if termino_real <= termino_previsto:
                        cor = "#2EAF5B"  # Verde - Concluído dentro do prazo
                    else:
                        cor = "#A38408"  # Amarelo - Concluído com atraso
                elif termino_previsto < hoje:
                    cor = "#C30202"  # Vermelho - Não concluído e prazo vencido
                else:
                    cor = "#000000"  # Preto - Em andamento (dentro do prazo)
                
                # Apply to date columns
                for i in [3, 4]:  # Date columns indices
                    style[i] = f"color: {cor};"
                
                # Variance style
                if pd.notna(row["Var. Term"]):
                    val = row["Var. Term"]
                    cor_texto = "#e74c3c" if val < 0 else "#2ecc71"
                    style[5] = f"color: {cor_texto}; font-weight: 600; font-size: 12px; text-align: center;"
                
                return style

            # Format columns
            styler = df_para_estilo.style.format({
                "Início Prev.": lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "",
                "Término Prev.": lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "",
                "Início Real": lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "",
                "Término Real": lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "",
                "Var. Term": lambda x: f"{'▲' if x < 0 else '▼'} {abs(int(x))} dias" if pd.notna(x) else "",
                "Percentual_Concluido": lambda x: ""
            }, na_rep="-")
            
            styler = styler.apply(estilo_linha, axis=1)
            styler = styler.hide(axis="index")
            styler = styler.hide(axis="columns", subset=["Percentual_Concluido"])
            return styler

        # Rename columns for display
        tabela_para_exibir = tabela_final.rename(columns={
            'Hierarquia': 'Empreendimento / Etapa',
            'Inicio_Prevista': 'Início Prev.',
            'Termino_Prevista': 'Término Prev.',
            'Inicio_Real': 'Início Real',
            'Termino_Real': 'Término Real'
        })

        # Display columns
        colunas_para_exibir = ['Empreendimento / Etapa', 'Início Prev.', 'Término Prev.', 'Início Real', 'Término Real', 'Var. Term', 'Percentual_Concluido']
        
        # Apply style
        tabela_estilizada = aplicar_estilo(tabela_para_exibir[colunas_para_exibir])

        html_tabela = tabela_estilizada.to_html()
        st.markdown(html_tabela, unsafe_allow_html=True)
        
    with tab4:
        st.subheader("Visão Detalhada por Etapa")
    if df_filtered.empty:
        st.warning("⚠️ Nenhum dado encontrado com os filtros aplicados.")

    # Configuração da página
    st.set_page_config(layout="wide", page_title="Dashboard de Controle de Etapas")

    # --- Funções Auxiliares ---
    def formatar_data(data):
        return data.strftime("%d/%m/%y") if pd.notna(data) else ""

    def calcular_variacao(termino_prev, termino_real):
        if pd.isna(termino_prev) or pd.isna(termino_real):
            return ""
        diff = (termino_real - termino_prev).days
        return f"({diff})" if diff > 0 else f"{diff}" if diff < 0 else "0"

    # --- Carregamento de Dados ---
    @st.cache_data
    def load_data():
        # (Implemente aqui seu carregamento de dados original)
        # Exemplo simplificado:
        data = {
            "UGB": ["GA", "CA", "SC"],
            "Empreendimento": ["Projeto 1", "Projeto 2", "Projeto 3"],
            "Etapa": ["DM", "DOC", "ENG"],
            "Inicio_Prevista": ["2023-01-01", "2023-02-01", "2023-03-01"],
            "Termino_Prevista": ["2023-01-31", "2023-02-28", "2023-03-31"],
            "Inicio_Real": ["2023-01-05", "2023-02-10", "2023-03-15"],
            "Termino_Real": ["2023-02-05", "2023-03-15", "2023-04-10"],
            "% concluído": [100, 80, 50]
        }
        return pd.DataFrame(data)

    # --- Interface Principal ---
    def main():
        st.title("📊 Controle de Etapas por Empreendimento")
        
        # Carregar dados
        df = load_data()
        
        # Filtros na sidebar
        with st.sidebar:
            # Header sem parâmetro key
            st.markdown("## 🔍 Filtros")
            
            # Filtro por UGB com key única
            ugb_list = ["Todos"] + sorted(df["UGB"].dropna().unique().tolist())
            selected_ugb = st.selectbox(
                "Selecione a UGB:",
                ugb_list,
                key="ugb_filter_selectbox"
            )
            
            # Filtro opcional por Empreendimento com key única
            empreendimento_list = ["Todos"] + sorted(df["Empreendimento"].unique().tolist())
            selected_emp = st.selectbox(
                "Selecione o Empreendimento:",
                empreendimento_list,
                key="emp_filter_selectbox"
            )
        
        # Aplicar filtros
        if selected_ugb != "Todos":
            df = df[df["UGB"] == selected_ugb]
        if selected_emp != "Todos":
            df = df[df["Empreendimento"] == selected_emp]
        
        # Ordenação
        ordem_etapas = {'DM':1, 'DOC':2, 'ENG':3, 'MEM':4, 'LAE':5, 'CONT':6, 'ASS':7}
        df['Ordem_Etapa'] = df['Etapa'].map(ordem_etapas)
        df = df.sort_values(['UGB', 'Empreendimento', 'Ordem_Etapa'])
        
        # --- Tabela de Etapas ---
        st.subheader("📋 Tabela de Andamento por Etapa")
        
        # CSS para estilização
        st.markdown("""
        <style>
            .tabela-etapas {
                width: 100%;
                border-collapse: collapse;
                margin: 1em 0;
                font-size: 0.9em;
            }
            .tabela-etapas th, .tabela-etapas td {
                border: 1px solid #ddd;
                padding: 8px;
                text-align: center;
            }
            .tabela-etapas th {
                background-color: #f2f2f2;
                position: sticky;
                top: 0;
            }
            .etapa-header {
                background-color: #e6f3ff;
                font-weight: bold;
            }
            .empreendimento-cell {
                text-align: left;
                font-weight: bold;
                background-color: #f9f9f9;
            }
            .ugb-header {
                background-color: #174c66;
                color: white;
                font-weight: bold;
                font-size: 1.1em;
                padding: 10px;
                margin-top: 20px;
                border-radius: 5px;
            }
            .negative-var {
                color: #e74c3c;
                font-weight: bold;
            }
            .positive-var {
                color: #2ecc71;
                font-weight: bold;
            }
        </style>
        """, unsafe_allow_html=True)
        
        # Agrupar por UGB
        for ugb in df['UGB'].unique():
            df_ugb = df[df['UGB'] == ugb]
            
            # Cabeçalho da UGB
            st.markdown(f"<div class='ugb-header'>UGB: {ugb}</div>", unsafe_allow_html=True)
            
            # Criar HTML da tabela
            html = """
            <table class="tabela-etapas">
                <thead>
                    <tr>
                        <th rowspan="2" class="empreendimento-cell">Empreendimento</th>
            """
            
            # Definir todas as etapas
            etapas = {
                'DM': '1.DEFINIÇÃO DO MÓDULO',
                'DOC': '2.DOCUMENTAÇÃO',
                'ENG': '3.ENGENHARIA',
                'MEM': '4.MEMORIAL',
                'LAE': '5.LAE',
                'CONT': '6.CONTRATAÇÃO',
                'ASS': '7.ASSINATURA'
            }
            
            # Cabeçalhos das etapas
            for etapa in etapas.values():
                html += f"""
                        <th colspan="5" class="etapa-header">{etapa}</th>
                """
            
            html += """
                    </tr>
                    <tr>
            """
            
            # Subcabeçalhos (5 colunas para cada etapa)
            for _ in etapas.values():
                html += """
                        <th>Início Prev.</th>
                        <th>Termino Prev.</th>
                        <th>Início Real</th>
                        <th>Termino Real</th>
                        <th>Var. Term</th>
                """
            
            html += """
                    </tr>
                </thead>
                <tbody>
            """
            
            # Linhas dos empreendimentos
            for empreendimento in df_ugb['Empreendimento'].unique():
                html += f"""
                    <tr>
                        <td class="empreendimento-cell">{empreendimento}</td>
                """
                
                # Colunas para cada etapa
                for sigla, nome_etapa in etapas.items():
                    etapa_df = df_ugb[(df_ugb['Empreendimento'] == empreendimento) & 
                                    (df_ugb['Etapa'] == sigla)]
                    
                    if not etapa_df.empty:
                        row = etapa_df.iloc[0]
                        inicio_prev = formatar_data(row['Inicio_Prevista'])
                        termino_prev = formatar_data(row['Termino_Prevista'])
                        inicio_real = formatar_data(row['Inicio_Real'])
                        termino_real = formatar_data(row['Termino_Real'])
                        var_term = calcular_variacao(row['Termino_Prevista'], row['Termino_Real'])
                        
                        html += f"""
                            <td>{inicio_prev}</td>
                            <td>{termino_prev}</td>
                            <td>{inicio_real}</td>
                            <td>{termino_real}</td>
                            <td class="{'negative-var' if '(' in str(var_term) else 'positive-var' if var_term and not '(' in str(var_term) else ''}">{var_term}</td>
                        """
                    else:
                        html += """
                            <td></td>
                            <td></td>
                            <td></td>
                            <td></td>
                            <td></td>
                        """
                
                html += """
                    </tr>
                """
            
            html += """
                </tbody>
            </table>
            """
            
            st.markdown(html, unsafe_allow_html=True)
        
        # Botões de ação com keys únicas
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Atualizar Dados", key="update_data_button"):
                st.cache_data.clear()
                st.experimental_rerun()
        
        with col2:
            if st.button("📤 Exportar para Excel", key="export_excel_button"):
                with pd.ExcelWriter('controle_etapas.xlsx') as writer:
                    df.to_excel(writer, index=False)
                st.success("Arquivo exportado com sucesso!")
        
        # Legenda
        st.markdown("""
        **📝 Legenda:**
        - **Var. Term**: Variação de Término (dias)
        - Valores em **vermelho** indicam atraso
        - Valores em **verde** indicam adiantamento
        - Células vazias = dados não disponíveis
        """)

    if __name__ == "__main__":
        main()
else:
    st.error("❌ Não foi possível carregar ou gerar os dados.")

    
    
