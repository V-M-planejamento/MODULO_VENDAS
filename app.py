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
    LARGURA_TABELA = 5
    COR_PREVISTO = '#A8C5DA'
    COR_REAL = '#174c66'
    COR_HOJE = 'red'
    COR_CONCLUIDO = '#047031'
    COR_ATRASADO = '#a83232'
    COR_META_ASSINATURA = '#8e44ad'
    FONTE_TITULO = {'size': 10, 'weight': 'bold', 'color': 'black'}
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
        termino_real = linha['Termino_Real']
        termino_previsto = linha['Termino_Prevista']
        hoje = pd.Timestamp.now()

        if percentual == 100:
            if pd.notna(termino_real) and pd.notna(termino_previsto):
                if termino_real < termino_previsto:
                    cor_texto = "#2EAF5B"  # Verde - concluído antes do prazo
                    cor_caixa = "#e6f5eb"
                elif termino_real > termino_previsto:
                    cor_texto = "#C30202"  # Vermelho - concluído com atraso
                    cor_caixa = "#fae6e6"
                else:
                    cor_texto = "#000000"  # Preto - concluído exatamente no prazo
                    cor_caixa = estilo_celula['facecolor']
            else:
                cor_texto = "#000000"  # Preto - concluído mas sem dados completos
                cor_caixa = estilo_celula['facecolor']
        elif percentual < 100:
            if pd.notna(termino_real) and (termino_real < hoje):
                cor_texto = "#A38408"  # Amarelo - atrasado na execução real
                cor_caixa = "#faf3d9"
            else:
                cor_texto = "#000000"  # Preto - em andamento normal
                cor_caixa = estilo_celula['facecolor']
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

    # NOVO CÓDIGO PARA AJUSTE DA META PREVISTA
    if num_empreendimentos == 1 and num_etapas > 1:
        empreendimento = df["Empreendimento"].unique()[0]
        df_assinatura = df[(df["Empreendimento"] == empreendimento) & (df["Etapa"] == "ASS")]
        
        if not df_assinatura.empty:
            data_meta = None
            tipo_meta = ""
            if pd.notna(df_assinatura["Termino_Prevista"].iloc[0]):
                data_meta = df_assinatura["Termino_Prevista"].iloc[0]
                tipo_meta = "Prevista"
            elif pd.notna(df_assinatura["Termino_Real"].iloc[0]):
                data_meta = df_assinatura["Termino_Real"].iloc[0]
                tipo_meta = "Real"

            if data_meta is not None:
                # Ajustar os limites do eixo X para acomodar a meta
                xlim_atual = eixo_gantt.get_xlim()
                margem = pd.Timedelta(days=100)  # 2 meses de margem
                
                if data_meta > pd.to_datetime(xlim_atual[1]) - margem:
                    nova_data_limite = data_meta + margem
                    eixo_gantt.set_xlim(right=nova_data_limite)
                
                eixo_gantt.axvline(data_meta, color=StyleConfig.COR_META_ASSINATURA, 
                                   linestyle="--", linewidth=1.7, alpha=0.7)
                
                # Posicionar o texto dentro do gráfico
                y_texto = eixo_gantt.get_ylim()[1] + 0.2
                eixo_gantt.text(data_meta, y_texto,
                               f"Meta {tipo_meta}\nAssinatura: {data_meta.strftime('%d/%m/%y')}", 
                               color=StyleConfig.COR_META_ASSINATURA, fontsize=10, 
                               ha="center", va="top",
                               bbox=dict(facecolor="white", alpha=0.8, 
                                        edgecolor=StyleConfig.COR_META_ASSINATURA,
                                        boxstyle="round,pad=0.5"))

    eixo_gantt.grid(axis='x', linestyle='--', alpha=0.6)
    eixo_gantt.xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    eixo_gantt.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
    plt.setp(eixo_gantt.get_xticklabels(), rotation=90, ha='center')

    handles_legenda = [
    Patch(color=StyleConfig.COR_PREVISTO, label='Previsto'),
    Patch(color=StyleConfig.COR_REAL, label='Real')
]

    # Ajuste o segundo valor de bbox_to_anchor para diminuir o espaço (ex: -0.05 em vez de -0.2)
    eixo_gantt.legend(
        handles=handles_legenda,
        loc='upper center',          # Alinha no canto superior direito
        bbox_to_anchor=(1.1, 1),  # Ajuste fino para posicionar fora do gráfico (se necessário)
        frameon=False,             # Remove a borda
        borderaxespad=0.1          # Espaçamento entre a legenda e o gráfico
    )

    # Ajuste o rect para evitar que o tight_layout corte a legenda
    plt.tight_layout(rect=[0, 0.03, 1, 1])  # O segundo valor controla o espaço inferior
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
import streamlit as st
from dropdown_component import simple_multiselect_dropdown  # Importando o componente personalizado

# CSS customizado
st.markdown("""
<style>
    /* Altera APENAS os checkboxes dos multiselects */
    div.stMultiSelect div[role="option"] input[type="checkbox"]:checked + div > div:first-child {
        background-color: #4a0101 !important;
        border-color: #4a0101 !important;
    }
    
    /* Cor de fundo dos itens selecionados */
    div.stMultiSelect [aria-selected="true"] {
        background-color: #f8d7da !important;
        color: #333 !important;
        border-radius: 4px;
    }
    
    /* Estilo do "×" de remoção */
    div.stMultiSelect [aria-selected="true"]::after {
        color: #4a0101 !important;
        font-weight: bold;
    }
    
    /* Espaçamento entre os filtros */
    .stSidebar .stMultiSelect, .stSidebar .stSelectbox, .stSidebar .stRadio {
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.title("Módulo Vendas")

# Cache para melhorar performance
@st.cache_data
def get_unique_values(df, column):
    """Função para cachear valores únicos de uma coluna"""
    return sorted(df[column].dropna().unique().tolist())

@st.cache_data
def filter_dataframe(df, ugb_filter, emp_filter):
    """Função para cachear filtragem do DataFrame"""
    if not ugb_filter:
        return df.iloc[0:0]  # DataFrame vazio se nenhuma UGB selecionada
    
    df_filtered = df[df["UGB"].isin(ugb_filter)]
    
    if emp_filter:
        df_filtered = df_filtered[df_filtered["Empreendimento"].isin(emp_filter)]
    
    return df_filtered

with st.spinner('Carregando e processando dados...'):
    df_data = load_data()

if df_data is not None and not df_data.empty:
    # Logo no sidebar
    with st.sidebar:
        st.markdown("<br>", unsafe_allow_html=True)  # Espaço no topo
        
        # Centraliza a imagem
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.image("logoNova.png", width=200)
            
        st.markdown("<br>", unsafe_allow_html=True)  # Espaço abaixo da imagem
        
        st.header("Filtros")

        # 1️⃣ Filtro UGB (Componente personalizado)
        ugb_options = get_unique_values(df_data, "UGB")
        selected_ugb = simple_multiselect_dropdown(
            label="Filtrar por UGB",
            options=ugb_options,
            key="ugb_filter",
            default_selected=ugb_options
        )
        
        # 2️⃣ Filtro Empreendimento (Componente personalizado)
        # Otimização: só calcular opções de empreendimento se UGB foi selecionada
        if selected_ugb:
            emp_options = get_unique_values(
                df_data[df_data["UGB"].isin(selected_ugb)], 
                "Empreendimento"
            )
        else:
            emp_options = []
            
        selected_emp = simple_multiselect_dropdown(
            label="Filtrar por Empreendimento",
            options=emp_options,
            key="empreendimento_filter",
            default_selected=emp_options
        )
        
        # 3️⃣ Filtro Etapa
        # Usar função cacheada para filtragem
        df_filtered = filter_dataframe(df_data, selected_ugb, selected_emp)
        
        if not df_filtered.empty:
            etapas_disponiveis = get_unique_values(df_filtered, "Etapa")
            
            # Ordenar etapas se sigla_para_nome_completo estiver definido
            try:
                etapas_disponiveis = sorted(
                    etapas_disponiveis,
                    key=lambda x: list(sigla_para_nome_completo.keys()).index(x) if x in sigla_para_nome_completo else 99
                )
                etapas_para_exibir = ["Todos"] + [sigla_para_nome_completo.get(e, e) for e in etapas_disponiveis]
            except NameError:
                # Se sigla_para_nome_completo não estiver definido, usar as etapas como estão
                etapas_para_exibir = ["Todos"] + etapas_disponiveis
        else:
            etapas_para_exibir = ["Todos"]
        
        selected_etapa_nome = st.selectbox(
            "Filtrar por Etapa",
            options=etapas_para_exibir
        )

        # 4️⃣ Opção de visualização
        tipo_visualizacao = st.radio("Mostrar dados:", ("Ambos", "Previsto", "Real"))

    # Aplica o filtro de etapa final
    if selected_etapa_nome != "Todos" and not df_filtered.empty:
        try:
            sigla_selecionada = nome_completo_para_sigla.get(selected_etapa_nome, selected_etapa_nome)
            df_filtered = df_filtered[df_filtered["Etapa"] == sigla_selecionada]
        except NameError:
            # Se nome_completo_para_sigla não estiver definido, usar o nome como está
            df_filtered = df_filtered[df_filtered["Etapa"] == selected_etapa_nome]

    # Abas principais
    tab1, tab2 = st.tabs(["📈 Gráfico de Gantt – Previsto vs Real", "💾 Tabelão"])


#========================================================================================================


    with tab1:
        st.subheader("Gantt Comparativo")
        if df_filtered.empty:
            st.warning("⚠️ Nenhum dado encontrado com os filtros aplicados.")
        else:
            gerar_gantt(df_filtered.copy(), tipo_visualizacao)
        
        st.subheader("Visão Detalhada por Empreendimento")
        if df_filtered.empty:
            st.warning("⚠️ Nenhum dado encontrado com os filtros aplicados.")
        else:
            # --- INÍCIO DA LÓGICA CORRIGIDA (DENTRO DO ELSE) ---
            df_detalhes = df_filtered.copy()
            hoje = pd.Timestamp.now().normalize()

            # Converter colunas para datetime, tratando '-' como NaN
            for col in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real']:
                df_detalhes[col] = df_detalhes[col].replace('-', pd.NA)
                df_detalhes[col] = pd.to_datetime(df_detalhes[col], errors='coerce')

            # Criar flag de validação de conclusão
            df_detalhes['Conclusao_Valida'] = False
            if '% concluído' in df_detalhes.columns:
                mask = (
                    (df_detalhes['% concluído'] == 100) & 
                    (df_detalhes['Termino_Real'].notna()) &
                    ((df_detalhes['Termino_Prevista'].isna()) | 
                    (df_detalhes['Termino_Real'] <= df_detalhes['Termino_Prevista']))
                )
                df_detalhes.loc[mask, 'Conclusao_Valida'] = True

            # Agregar dados
            df_agregado = df_detalhes.groupby(['Empreendimento', 'Etapa']).agg(
                Inicio_Prevista=('Inicio_Prevista', 'min'),
                Termino_Prevista=('Termino_Prevista', 'max'),
                Inicio_Real=('Inicio_Real', 'min'),
                Termino_Real=('Termino_Real', 'max'),
                Concluido_Valido=('Conclusao_Valida', 'any'),
                Percentual_Concluido=('% concluído', 'max') if '% concluído' in df_detalhes.columns else ('% concluído', lambda x: 0)
            ).reset_index()

            # Converter para porcentagem (0-100) se estiver em formato decimal (0-1)
            if '% concluído' in df_detalhes.columns:
                if not df_agregado.empty and df_agregado['Percentual_Concluido'].max() <= 1:
                    df_agregado['Percentual_Concluido'] = df_agregado['Percentual_Concluido'] * 100

            # Calcular variação de término
            df_agregado['Var. Term'] = (df_agregado['Termino_Prevista'] - df_agregado['Termino_Real']).dt.days

            # --- Controles de Classificação ---
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

            # --- Montagem da Estrutura Hierárquica ---
            tabela_final_lista = []
            for empreendimento, grupo in df_ordenado.groupby('Empreendimento', sort=False):
                var_term_assinatura = grupo[grupo['Etapa'] == 'ASS']['Var. Term']
                var_term_cabecalho = var_term_assinatura.iloc[0] if not var_term_assinatura.empty and pd.notna(var_term_assinatura.iloc[0]) else grupo['Var. Term'].mean()
                
                percentuais = grupo['Percentual_Concluido']
                var_term = grupo['Var. Term']
                valid_mask = (~var_term.isna()) & (~percentuais.isna())
                percentuais_validos = percentuais[valid_mask]
                var_term_validos = var_term[valid_mask]
                
                if len(percentuais_validos) > 0 and len(var_term_validos) > 0 and var_term_validos.sum() != 0:
                    soma_ponderada = (percentuais_validos * var_term_validos).sum()
                    soma_pesos = var_term_validos.sum()
                    percentual_medio = soma_ponderada / soma_pesos
                else:
                    percentual_medio = percentuais.mean()
                
                cabecalho = pd.DataFrame([{
                    'Hierarquia': f'📂 {empreendimento}', 
                    'Inicio_Prevista': grupo['Inicio_Prevista'].min(), 
                    'Termino_Prevista': grupo['Termino_Prevista'].max(),
                    'Inicio_Real': grupo['Inicio_Real'].min(), 
                    'Termino_Real': grupo['Termino_Real'].max(), 
                    'Var. Term': var_term_cabecalho,
                    'Percentual_Concluido': percentual_medio
                }])
                tabela_final_lista.append(cabecalho)
                
                grupo_formatado = grupo.copy()
                grupo_formatado['Hierarquia'] = ' &nbsp; &nbsp; ' + grupo_formatado['Etapa'].map(sigla_para_nome_completo)
                tabela_final_lista.append(grupo_formatado)

            tabela_final = pd.concat(tabela_final_lista, ignore_index=True)

            # --- Aplicação de Estilo Condicional e Formatação ---
            def aplicar_estilo(df_para_estilo):
                if df_para_estilo.empty:
                    return df_para_estilo.style

                def estilo_linha(row):
                    style = [None] * len(row)
                    
                    if row['Empreendimento / Etapa'].startswith('📂'):
                        for i in range(len(style)):
                            style[i] = "font-weight: 500; color: #000000; background-color: #F0F2F6; border-left: 4px solid #000000; padding-left: 10px;"
                            if i > 0:
                                style[i] = "background-color: #F0F2F6;"
                        return style
                    
                    percentual = row.get('% Concluído', 0)
                    if isinstance(percentual, str) and '%' in percentual:
                        try: percentual = int(percentual.replace('%', ''))
                        except: percentual = 0

                    termino_real, termino_previsto, hoje_data = row["Término Real"], row["Término Prev."], pd.Timestamp.now()
                    cor = "#000000"
                    if percentual == 100:
                        if pd.notna(termino_real) and pd.notna(termino_previsto):
                            if termino_real < termino_previsto: cor = "#2EAF5B"
                            elif termino_real > termino_previsto: cor = "#C30202"
                    elif pd.notna(termino_real) and (termino_real < hoje_data):
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

            tabela_para_exibir = tabela_final.rename(columns={
                'Hierarquia': 'Empreendimento / Etapa', 'Inicio_Prevista': 'Início Prev.',
                'Termino_Prevista': 'Término Prev.', 'Inicio_Real': 'Início Real',
                'Termino_Real': 'Término Real', 'Percentual_Concluido': '% Concluído'
            })
            colunas_para_exibir = ['Empreendimento / Etapa', '% Concluído', 'Início Prev.', 'Término Prev.', 'Início Real', 'Término Real', 'Var. Term']
            tabela_estilizada = aplicar_estilo(tabela_para_exibir[colunas_para_exibir])
            st.markdown(tabela_estilizada.to_html(), unsafe_allow_html=True)
#========================================================================================================

    with tab2:
        st.subheader("Tabelão Detalhado")
        if df_filtered.empty:
            st.warning("⚠️ Nenhum dado encontrado com os filtros aplicados.")
        else:
            # --- INÍCIO DA LÓGICA CORRIGIDA (DENTRO DO ELSE) ---
            df_detalhes = df_filtered.copy()
            hoje = pd.Timestamp.now().normalize()

            df_detalhes = df_detalhes.rename(columns={'Termino_prevista': 'Termino_Prevista', 'Termino_real': 'Termino_Real'})
            for col in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real']:
                if col in df_detalhes.columns:
                    df_detalhes[col] = df_detalhes[col].replace('-', pd.NA)
                    df_detalhes[col] = pd.to_datetime(df_detalhes[col], errors='coerce')

            df_detalhes['Conclusao_Valida'] = False
            if '% concluído' in df_detalhes.columns:
                mask = ((df_detalhes['% concluído'] == 100) & (df_detalhes['Termino_Real'].notna()) & ((df_detalhes['Termino_Prevista'].isna()) | (df_detalhes['Termino_Real'] <= df_detalhes['Termino_Prevista'])))
                df_detalhes.loc[mask, 'Conclusao_Valida'] = True

            agg_dict = {
                'Inicio_Prevista': ('Inicio_Prevista', 'min'), 'Termino_Prevista': ('Termino_Prevista', 'max'),
                'Inicio_Real': ('Inicio_Real', 'min'), 'Termino_Real': ('Termino_Real', 'max'),
                'Var. Term': ('Termino_Real', lambda x: (x.max() - df_detalhes.loc[x.index, 'Termino_Prevista'].max()).days if pd.notna(x.max()) and pd.notna(df_detalhes.loc[x.index, 'Termino_Prevista'].max()) else pd.NA),
                'Concluido_Valido': ('Conclusao_Valida', 'any')
            }
            if '% concluído' in df_detalhes.columns:
                agg_dict['Percentual_Concluido'] = ('% concluído', 'max')
                if not df_detalhes.empty and df_detalhes['% concluído'].max() <= 1:
                    df_detalhes['% concluído'] *= 100

            df_agregado = df_detalhes.groupby(['UGB', 'Empreendimento', 'Etapa']).agg(**agg_dict).reset_index()

            st.write("---")
            col1, col2 = st.columns(2)
            opcoes_classificacao = {
                'Padrão (UGB, Empreendimento e Etapa)': ['UGB', 'Empreendimento', 'Etapa_Ordem'], 'UGB (A-Z)': ['UGB'],
                'Empreendimento (A-Z)': ['Empreendimento'], 'Data de Início Previsto (Mais antiga)': ['Inicio_Prevista'],
                'Data de Término Previsto (Mais recente)': ['Termino_Prevista'], 'Variação de Prazo (Pior para Melhor)': ['Var. Term']
            }
            with col1: classificar_por = st.selectbox("Ordenar tabela por:", options=list(opcoes_classificacao.keys()), key="classificar_por_selectbox")
            with col2: ordem = st.radio("Ordem:", options=['Crescente', 'Decrescente'], horizontal=True, key="ordem_radio")

            ordem_etapas_completas = list(sigla_para_nome_completo.keys())
            df_agregado['Etapa_Ordem'] = df_agregado['Etapa'].apply(lambda x: ordem_etapas_completas.index(x) if x in ordem_etapas_completas else len(ordem_etapas_completas))
            df_ordenado = df_agregado.sort_values(by=opcoes_classificacao[classificar_por], ascending=(ordem == 'Crescente'))
            st.write("---")

            df_pivot = df_ordenado.pivot_table(index=['UGB', 'Empreendimento'], columns='Etapa', values=['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real', 'Var. Term'], aggfunc='first')

            # --- CORREÇÃO DO KEYERROR ---
            etapas_existentes_no_pivot = df_pivot.columns.get_level_values(1).unique()
            colunas_ordenadas = []
            for etapa in ordem_etapas_completas:
                if etapa in etapas_existentes_no_pivot:
                    for tipo in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real', 'Var. Term']:
                        if (tipo, etapa) in df_pivot.columns:
                            colunas_ordenadas.append((tipo, etapa))
            
            df_final = df_pivot[colunas_ordenadas].reset_index()
            # --- FIM DA CORREÇÃO ---

            novos_nomes = []
            for col in df_final.columns:
                if col[0] in ['UGB', 'Empreendimento']: novos_nomes.append(col[0])
                else:
                    tipo, etapa = col[0], col[1]
                    nome_etapa = sigla_para_nome_completo.get(etapa, etapa)
                    nome_tipo = {'Inicio_Prevista': 'Início Prev.', 'Termino_Prevista': 'Término Prev.', 'Inicio_Real': 'Início Real', 'Termino_Real': 'Término Real', 'Var. Term': 'Var. Term'}[tipo]
                    novos_nomes.append(f"{nome_etapa} {nome_tipo}")
            df_final.columns = novos_nomes

            def formatar_valor(valor, tipo):
                if pd.isna(valor): return "-"
                if tipo == 'data': return valor.strftime("%d/%m/%Y")
                if tipo == 'variacao': return f"{'▼' if valor > 0 else '▲'} {abs(int(valor))} dias"
                return str(valor)

            def determinar_cor(row, col_name):
                if 'Início Real' in col_name or 'Término Real' in col_name:
                    etapa_nome_completo = " ".join(col_name.split(' ')[:-2])
                    etapa_sigla = nome_completo_para_sigla.get(etapa_nome_completo)
                    if etapa_sigla:
                        etapa_data_list = df_agregado[(df_agregado['UGB'] == row['UGB']) & (df_agregado['Empreendimento'] == row['Empreendimento']) & (df_agregado['Etapa'] == etapa_sigla)]
                        if not etapa_data_list.empty:
                            etapa_data = etapa_data_list.iloc[0]
                            percentual = etapa_data.get('Percentual_Concluido', 0)
                            termino_real, termino_previsto = etapa_data['Termino_Real'], etapa_data['Termino_Prevista']
                            if percentual == 100:
                                if pd.notna(termino_real) and pd.notna(termino_previsto):
                                    if termino_real < termino_previsto: return "#2EAF5B"
                                    elif termino_real > termino_previsto: return "#C30202"
                            elif pd.notna(termino_real) and (termino_real < hoje): return "#A38408"
                return "#000000"

            df_formatado = df_final.copy()
            for col in df_formatado.columns:
                if any(x in col for x in ['Início Prev.', 'Término Prev.', 'Início Real', 'Término Real']): df_formatado[col] = df_formatado[col].apply(lambda x: formatar_valor(x, 'data'))
                elif 'Var. Term' in col: df_formatado[col] = df_formatado[col].apply(lambda x: formatar_valor(x, 'variacao'))

            def estilo_linha(row):
                styles = []
                for col_name, val in row.items():
                    if val == '-': styles.append('color: #999999; font-style: italic;')
                    elif 'Início Real' in col_name or 'Término Real' in col_name: styles.append(f'color: {determinar_cor(row, col_name)}; font-weight: bold;')
                    elif 'Var. Term' in col_name:
                        if '▲' in val: styles.append('color: #e74c3c; font-weight: 600;')
                        elif '▼' in val: styles.append('color: #2ecc71; font-weight: 600;')
                        else: styles.append('color: #000000;')
                    else: styles.append('color: #000000;')
                return styles

            styled_df = df_formatado.style.apply(estilo_linha, axis=1)
            styled_df = styled_df.set_properties(**{'text-align': 'center', 'font-size': '12px', 'border': '1px solid #f0f0f0', 'white-space': 'nowrap'})
            styled_df = styled_df.set_table_styles([{'selector': 'th', 'props': [('font-size', '12px'), ('text-align', 'center'), ('white-space', 'nowrap')]}])
            st.dataframe(styled_df, height=min(35 * len(df_final) + 40, 600), hide_index=True, use_container_width=True)
            
            st.markdown("""<div style="margin-top: 10px; font-size: 12px; color: #555;">
                <strong>Legenda:</strong> 
                <span style="color: #2EAF5B; font-weight: bold;">■ Concluído antes do prazo</span> | 
                <span style="color: #C30202; font-weight: bold;">■ Concluído com atraso</span> | 
                <span style="color: #A38408; font-weight: bold;">■ Aguardando atualização</span> | 
                <span style="color: #000000; font-weight: bold;">■ Em andamento</span> | 
                <span style="color: #999; font-style: italic;"> - Dados não disponíveis</span>
            </div>""", unsafe_allow_html=True)
else:
    st.error("❌ Não foi possível carregar ou gerar os dados.")