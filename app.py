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

# CSS customizado APENAS para os checkboxes dos filtros UGB e Empreendimento
# CSS que realmente funciona para os checkboxes
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
</style>
""", unsafe_allow_html=True)


st.title("Módulo Vendas")

with st.spinner('Carregando e processando dados...'):
    df_data = load_data()

if df_data is not None and not df_data.empty:
    # Logo no sidebar
    try:
        # Adiciona espaço no topo
        st.sidebar.markdown("<br>", unsafe_allow_html=True)
        
        # Centraliza a imagem usando columns
        col1, col2, col3 = st.sidebar.columns([1,2,1])
        with col2:
            st.image("logoNova.png", width=200)  # Ajuste o width conforme necessário
            
        # Adiciona espaço abaixo da imagem
        st.sidebar.markdown("<br>", unsafe_allow_html=True)
        
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar imagem: {str(e)}")
        st.sidebar.warning("A imagem 'logoNova.png' não foi encontrada no diretório.")

    st.sidebar.header("Filtros")

    # 1️⃣ Filtro UGB (Multiselect com cor personalizada)
    ugb_options = sorted(df_data["UGB"].dropna().unique().tolist())
    selected_ugb = st.sidebar.multiselect(
        "Filtrar por UGB",
        options=ugb_options,
        default=ugb_options,
        placeholder="Selecione uma ou mais UGBs"
    )
    df_filtered = df_data[df_data["UGB"].isin(selected_ugb)] if selected_ugb else df_data

    # 2️⃣ Filtro Empreendimento (Multiselect com cor personalizada)
    emp_options = sorted(df_filtered["Empreendimento"].dropna().unique().tolist())
    selected_emp = st.sidebar.multiselect(
        "Filtrar por Empreendimento",
        options=emp_options,
        default=emp_options,
        placeholder="Selecione um ou mais empreendimentos"
    )
    if selected_emp:
        df_filtered = df_filtered[df_filtered["Empreendimento"].isin(selected_emp)]

       # 3️⃣ Filtro Etapa (usando seus dicionários existentes)
    etapas_disponiveis = sorted(
        df_filtered["Etapa"].dropna().unique(),
        key=lambda x: list(sigla_para_nome_completo.keys()).index(x) if x in sigla_para_nome_completo else 99
    )
    
    # Mostra os nomes completos no dropdown
    etapas_para_exibir = ["Todos"] + [sigla_para_nome_completo.get(e, e) for e in etapas_disponiveis]
    
    selected_etapa_nome = st.sidebar.selectbox(
        "Filtrar por Etapa",
        options=etapas_para_exibir
    )

    # Aplica o filtro convertendo o nome completo de volta para sigla
    if selected_etapa_nome != "Todos":
        sigla_selecionada = nome_completo_para_sigla.get(selected_etapa_nome, selected_etapa_nome)
        df_filtered = df_filtered[df_filtered["Etapa"] == sigla_selecionada]

    # 4️⃣ Opção de visualização
    tipo_visualizacao = st.sidebar.radio("Mostrar dados:", ("Ambos", "Previsto", "Real"))

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
            # --- 1. PREPARAÇÃO E AGREGAÇÃO DOS DADOS ---
            df_detalhes = df_filtered.copy()
        hoje = pd.Timestamp.now().normalize()

        # Convert columns to datetime, tratando '-' como NaN
        for col in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real']:
            df_detalhes[col] = df_detalhes[col].replace('-', pd.NA)
            df_detalhes[col] = pd.to_datetime(df_detalhes[col], errors='coerce')

        # Create completion validation flag
        df_detalhes['Conclusao_Valida'] = False
        if '% concluído' in df_detalhes.columns:
            mask = (
                (df_detalhes['% concluído'] == 100) & 
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

        # Converter para porcentagem (0-100) se estiver em formato decimal (0-1)
        if '% concluído' in df_detalhes.columns:
            if df_agregado['Percentual_Concluido'].max() <= 1:
                df_agregado['Percentual_Concluido'] = df_agregado['Percentual_Concluido'] * 100

        # Calcular variação de término
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
            inicio_previsto_empreendimento = grupo['Inicio_Prevista'].min()
            termino_previsto_empreendimento = grupo['Termino_Prevista'].max()
            inicio_real_empreendimento = grupo['Inicio_Real'].min()
            termino_real_empreendimento = grupo['Termino_Real'].max()
            
            var_term_assinatura = grupo[grupo['Etapa'] == 'ASS']['Var. Term']
            if not var_term_assinatura.empty and pd.notna(var_term_assinatura.iloc[0]):
                var_term_cabecalho = var_term_assinatura.iloc[0]
            else:
                var_term_cabecalho = grupo['Var. Term'].mean()
            
            # Calcular média ponderada do % concluído
            percentuais = grupo['Percentual_Concluido']
            var_term = grupo['Var. Term']
            
            valid_mask = (~var_term.isna()) & (~percentuais.isna())
            percentuais_validos = percentuais[valid_mask]
            var_term_validos = var_term[valid_mask]
            
            if len(percentuais_validos) > 0 and len(var_term_validos) > 0:
                soma_ponderada = (percentuais_validos * var_term_validos).sum()
                soma_pesos = var_term_validos.sum()
                percentual_medio = soma_ponderada / soma_pesos
            else:
                percentual_medio = percentuais.mean()
            
            cabecalho = pd.DataFrame([{
                'Hierarquia': f'📂 {empreendimento}', 
                'Inicio_Prevista': inicio_previsto_empreendimento, 
                'Termino_Prevista': termino_previsto_empreendimento,
                'Inicio_Real': inicio_real_empreendimento, 
                'Termino_Real': termino_real_empreendimento, 
                'Var. Term': var_term_cabecalho,
                'Percentual_Concluido': percentual_medio
            }])
            tabela_final_lista.append(cabecalho)
            
            grupo_formatado = grupo.copy()
            grupo_formatado['Hierarquia'] = ' &nbsp; &nbsp; ' + grupo_formatado['Etapa'].map(sigla_para_nome_completo)
            tabela_final_lista.append(grupo_formatado)

        tabela_final = pd.concat(tabela_final_lista, ignore_index=True)

        # --- 4. APLICAÇÃO DE ESTILO CONDICIONAL E FORMATAÇÃO ---
        def aplicar_estilo(df_para_estilo):
            if df_para_estilo.empty:
                return df_para_estilo.style

            def estilo_linha(row):
                style = [None] * len(row)
                
                # Verifica se é um cabeçalho de empreendimento
                if row['Empreendimento / Etapa'].startswith('📂'):
                    for i in range(len(style)):
                        style[i] = "font-weight: 500; color: #000000; background-color: #F0F2F6; border-left: 4px solid #000000; padding-left: 10px;"
                        if i > 0:
                            style[i] = "background-color: #F0F2F6;"
                    return style
                
                percentual = row.get('% Concluído', 0)
                if isinstance(percentual, str) and '%' in percentual:
                    try:
                        percentual = int(percentual.replace('%', ''))
                    except:
                        percentual = 0

                termino_real = row["Término Real"]
                termino_previsto = row["Término Prev."]
                hoje = pd.Timestamp.now()

                # Lógica de cores principal
                if percentual == 100:
                    if pd.notna(termino_real) and pd.notna(termino_previsto):
                        if termino_real < termino_previsto:
                            cor = "#2EAF5B"  # Verde - concluído antes do prazo
                        elif termino_real > termino_previsto:
                            cor = "#C30202"  # Vermelho - concluído com atraso (permanente)
                        else:
                            cor = "#000000"  # Preto - concluído exatamente no prazo
                    else:
                        cor = "#000000"  # Preto - concluído mas sem dados completos
                elif pd.notna(termino_real) and (termino_real < hoje):
                    cor = "#A38408"  # Amarelo - atrasado na execução real e não concluído
                else:
                    cor = "#000000"  # Preto - em andamento normal

                # Aplica cor apenas para as colunas de datas
                for i, col in enumerate(df_para_estilo.columns):
                    if col in ['Início Real', 'Término Real']:
                        style[i] = f"color: {cor};"

                # Estilo para a coluna de variação de prazo (mantido igual)
                if pd.notna(row.get("Var. Term", None)):
                    val = row["Var. Term"]
                    if isinstance(val, str):
                        try:
                            val = int(val.split()[1]) * (-1 if '▲' in val else 1)
                        except:
                            val = 0
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
            
            # Aplicar estilo para evitar quebras de linha
            styler = styler.set_properties(**{
                'white-space': 'nowrap',
                'text-overflow': 'ellipsis',
                'overflow': 'hidden',
                'max-width': '380px'
            })
            
            styler = styler.apply(estilo_linha, axis=1)
            styler = styler.hide(axis="index")
            return styler

        # Adicionar CSS adicional para melhorar a exibição
        st.markdown("""
        <style>
            .stDataFrame {
                width: 100%;
            }
            .stDataFrame td {
                white-space: nowrap !important;
                text-overflow: ellipsis !important;
                overflow: hidden !important;
                max-width: 380px !important;
            }
            .stDataFrame th {
                white-space: nowrap !important;
            }
        </style>
        """, unsafe_allow_html=True)

        tabela_para_exibir = tabela_final.rename(columns={
            'Hierarquia': 'Empreendimento / Etapa',
            'Inicio_Prevista': 'Início Prev.',
            'Termino_Prevista': 'Término Prev.',
            'Inicio_Real': 'Início Real',
            'Termino_Real': 'Término Real',
            'Percentual_Concluido': '% Concluído'
        })

        colunas_para_exibir = ['Empreendimento / Etapa', '% Concluído', 'Início Prev.', 'Término Prev.', 'Início Real', 'Término Real', 'Var. Term']
        
        tabela_estilizada = aplicar_estilo(tabela_para_exibir[colunas_para_exibir])

        html_tabela = tabela_estilizada.to_html()
        st.markdown(html_tabela, unsafe_allow_html=True)

#========================================================================================================

    with tab2:
        st.subheader("Tabelão Detalhado")
        if df_filtered.empty:
            st.warning("⚠️ Nenhum dado encontrado com os filtros aplicados.")
        else:
            # --- 1. PREPARAÇÃO DOS DADOS ---
            df_detalhes = df_filtered.copy()
        hoje = pd.Timestamp.now().normalize()

        # Padronizar nomes de colunas
        df_detalhes = df_detalhes.rename(columns={
            'Termino_prevista': 'Termino_Prevista',
            'Termino_real': 'Termino_Real'
        })

        # Convert columns to datetime, tratando '-' como NaN
        for col in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real']:
            df_detalhes[col] = df_detalhes[col].replace('-', pd.NA)
            df_detalhes[col] = pd.to_datetime(df_detalhes[col], errors='coerce')

        # Create completion validation flag
        df_detalhes['Conclusao_Valida'] = False
        if '% concluído' in df_detalhes.columns:
            mask = (
                (df_detalhes['% concluído'] == 100) & 
                (df_detalhes['Termino_Real'].notna()) &
                ((df_detalhes['Termino_Prevista'].isna()) | 
                (df_detalhes['Termino_Real'] <= df_detalhes['Termino_Prevista']))
            )
            df_detalhes.loc[mask, 'Conclusao_Valida'] = True

        # Aggregate data - INCLUINDO % CONCLUÍDO MESMO QUE NÃO APAREÇA NA TABELA FINAL
        agg_dict = {
            'Inicio_Prevista': ('Inicio_Prevista', 'min'),
            'Termino_Prevista': ('Termino_Prevista', 'max'),
            'Inicio_Real': ('Inicio_Real', 'min'),
            'Termino_Real': ('Termino_Real', 'max'),
            'Var. Term': ('Termino_Real', lambda x: (x.max() - df_detalhes.loc[x.index, 'Termino_Prevista'].max()).days if pd.notna(x.max()) and pd.notna(df_detalhes.loc[x.index, 'Termino_Prevista'].max()) else pd.NA),
            'Concluido_Valido': ('Conclusao_Valida', 'any')
        }
        
        if '% concluído' in df_detalhes.columns:
            agg_dict['Percentual_Concluido'] = ('% concluído', 'max')
            # Converter para porcentagem (0-100) se estiver em formato decimal (0-1)
            if df_detalhes['% concluído'].max() <= 1:
                df_detalhes['% concluído'] = df_detalhes['% concluído'] * 100

        df_agregado = df_detalhes.groupby(['UGB', 'Empreendimento', 'Etapa']).agg(**agg_dict).reset_index()

        # --- 2. CONTROLES DE CLASSIFICAÇÃO ---
        st.write("---")
        col1, col2 = st.columns(2)
        
        opcoes_classificacao = {
            'Padrão (UGB, Empreendimento e Etapa)': ['UGB', 'Empreendimento', 'Etapa_Ordem'],
            'UGB (A-Z)': ['UGB'],
            'Empreendimento (A-Z)': ['Empreendimento'],
            'Data de Início Previsto (Mais antiga)': ['Inicio_Prevista'],
            'Data de Término Previsto (Mais recente)': ['Termino_Prevista'],
            'Variação de Prazo (Pior para Melhor)': ['Var. Term']
        }

        with col1:
            classificar_por = st.selectbox(
                "Ordenar tabela por:", 
                options=list(opcoes_classificacao.keys()),
                key="classificar_por_selectbox"
            )
        with col2:
            ordem = st.radio(
                "Ordem:", 
                options=['Crescente', 'Decrescente'], 
                horizontal=True,
                key="ordem_radio"
            )

        ordem_bool = (ordem == 'Crescente')
        colunas_para_ordenar = opcoes_classificacao[classificar_por]
        
        ordem_etapas = list(sigla_para_nome_completo.keys())
        df_agregado['Etapa_Ordem'] = df_agregado['Etapa'].apply(lambda x: ordem_etapas.index(x) if x in ordem_etapas else len(ordem_etapas))
        
        df_ordenado = df_agregado.sort_values(by=colunas_para_ordenar, ascending=ordem_bool)
        st.write("---")

        # --- 3. CRIAÇÃO DA TABELA HORIZONTAL ---
        etapas_ordenadas = list(sigla_para_nome_completo.keys())

        # Agrupar por UGB e empreendimento e pivotar as etapas
        df_pivot = df_ordenado.pivot(
            index=['UGB', 'Empreendimento'],
            columns='Etapa',
            values=['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real', 'Var. Term']
        )

        # Reorganizar as colunas para ter a sequência de etapas desejada
        colunas_ordenadas = []
        for etapa in etapas_ordenadas:
            if etapa in df_ordenado['Etapa'].unique():
                for tipo in ['Inicio_Prevista', 'Termino_Prevista', 'Inicio_Real', 'Termino_Real', 'Var. Term']:
                    colunas_ordenadas.append((tipo, etapa))

        # Criar DataFrame final
        df_final = df_pivot[colunas_ordenadas].reset_index()

        # Renomear colunas para melhor legibilidade
        novos_nomes = []
        for col in df_final.columns:
            if col[0] == 'UGB':
                novos_nomes.append('UGB')
            elif col[0] == 'Empreendimento':
                novos_nomes.append('Empreendimento')
            else:
                etapa = col[1]
                nome_etapa = sigla_para_nome_completo.get(etapa, etapa)
                tipo = {
                    'Inicio_Prevista': 'Início Prev.',
                    'Termino_Prevista': 'Término Prev.',
                    'Inicio_Real': 'Início Real',
                    'Termino_Real': 'Término Real',
                    'Var. Term': 'Var. Term'
                }[col[0]]
                novos_nomes.append(f"{nome_etapa[:15]} {tipo}")

        df_final.columns = novos_nomes

        # --- 4. FORMATAÇÃO E ESTILO COM NOVAS REGRAS DE CORES ---
        def formatar_valor(valor, tipo):
            if pd.isna(valor):
                return "-"
            if tipo == 'data':
                return valor.strftime("%d/%m/%Y")
            elif tipo == 'variacao':
                return f"{'▼' if valor > 0 else '▲'} {abs(int(valor))} dias"
            return str(valor)

        # Função para determinar a cor com base nas regras completas
        def determinar_cor(row, col):
            # Aplicar apenas para colunas de Início Real e Término Real
            if 'Início Real' in col or 'Término Real' in col:
                # Obter o nome da etapa a partir do nome da coluna
                etapa_nome = col.split(' ')[0]
                etapa_sigla = next((k for k, v in sigla_para_nome_completo.items() if v.startswith(etapa_nome)), None)
                
                # Obter os dados completos da etapa
                etapa_data = df_agregado[
                    (df_agregado['UGB'] == row['UGB']) & 
                    (df_agregado['Empreendimento'] == row['Empreendimento']) & 
                    (df_agregado['Etapa'] == etapa_sigla)
                ].iloc[0] if etapa_sigla else None
                
                if etapa_data is not None:
                    percentual = etapa_data.get('Percentual_Concluido', 0) if '% concluído' in df_detalhes.columns else 0
                    termino_real = etapa_data['Termino_Real']
                    termino_previsto = etapa_data['Termino_Prevista']
                    
                    # Lógica de cores principal
                    if percentual == 100:
                        if pd.notna(termino_real) and pd.notna(termino_previsto):
                            if termino_real < termino_previsto:
                                return "#2EAF5B"  # Verde - concluído antes do prazo
                            elif termino_real > termino_previsto:
                                return "#C30202"  # Vermelho - concluído com atraso (permanente)
                            else:
                                return "#000000"  # Preto - concluído exatamente no prazo
                        else:
                            return "#000000"  # Preto - concluído mas sem dados completos
                    elif pd.notna(termino_real) and (termino_real < hoje):
                        return "#A38408"  # Amarelo - atrasado na execução real e não concluído
                    else:
                        return "#000000"  # Preto - em andamento normal
            
            return "#000000"  # Preto padrão

        # Aplicar formatação condicional
        for col in df_final.columns:
            if 'Início Prev.' in col or 'Término Prev.' in col or 'Início Real' in col or 'Término Real' in col:
                df_final[col] = df_final[col].apply(lambda x: formatar_valor(x, 'data'))
            elif 'Var. Term' in col:
                df_final[col] = df_final[col].apply(lambda x: formatar_valor(x, 'variacao'))

        # Precisamos criar uma função auxiliar para aplicar o estilo linha por linha
        def estilo_linha(row):
            styles = []
            for col in df_final.columns:
                val = row[col]
                if pd.isna(val) or val == '-':
                    styles.append('color: #999999; font-style: italic;')
                elif 'Início Real' in col or 'Término Real' in col:
                    cor = determinar_cor(row, col)
                    styles.append(f'color: {cor}; font-weight: bold;')
                elif 'Var. Term' in col:
                    if isinstance(val, str) and '▲' in val:
                        styles.append('color: #e74c3c; font-weight: 600;')  # Vermelho para atraso
                    elif isinstance(val, str) and '▼' in val:
                        styles.append('color: #2ecc71; font-weight: 600;')  # Verde para adiantado
                    else:
                        styles.append('color: #000000;')
                else:
                    styles.append('color: #000000;')
            return styles

        # Aplicar estilo
        styled_df = df_final.style \
            .apply(estilo_linha, axis=1) \
            .set_properties(**{
                'text-align': 'center',
                'font-size': '12px',
                'border': '1px solid #f0f0f0',
                'white-space': 'nowrap'
            }) \
            .set_table_styles([{
                'selector': 'th',
                'props': [('font-size', '12px'), ('text-align', 'center'), ('white-space', 'nowrap')]
            }])

        # Exibir tabela com rolagem horizontal e colunas congeladas
        st.dataframe(
            styled_df,
            height=min(35 * len(df_final) + 40, 600),
            width=1200,
            hide_index=True,
            use_container_width=True
        )
        
        # Legenda de cores atualizada
        st.markdown("""
        <div style="margin-top: 10px; font-size: 12px; color: #555;">
            <strong>Legenda:</strong> 
            <span style="color: #2EAF5B; font-weight: bold;">■ Concluído antes do prazo</span> | 
            <span style="color: #C30202; font-weight: bold;">■ Concluído com atraso</span> | 
            <span style="color: #A38408; font-weight: bold;">■ Aguardando atualização</span> | 
            <span style="color: #000000; font-weight: bold;">■ Em andamento</span> | 
            <span style="color: #999; font-style: italic;"> - Dados não disponíveis</span>
        </div>
        """, unsafe_allow_html=True)
else:
    st.error("❌ Não foi possível carregar ou gerar os dados.")