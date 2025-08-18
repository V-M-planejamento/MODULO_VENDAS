import pandas as pd
import os

def tratar_e_retornar_dados_previstos():
    """Carrega e trata os dados, retornando apenas os dados PREV com a nova ordem de etapas."""
    try:
        # 1. CARREGAR OS DADOS
        # O ideal é usar um caminho absoluto ou garantir que o script e o arquivo estejam no mesmo local.
        # Para este exemplo, vou assumir que o arquivo está no mesmo diretório do script.
        diretorio_atual = os.path.dirname(os.path.abspath(__file__))
        caminho_arquivo = os.path.join(diretorio_atual, "BASE - VENDA E REGISTRO.xlsx")
        
        if not os.path.exists(caminho_arquivo):
            print(f"Erro: Arquivo não encontrado no caminho: {caminho_arquivo}")
            return None

        df = pd.read_excel(caminho_arquivo, sheet_name="PLANEJADOR MÓDULOS", header=None)

        # 2. REMOVER COLUNAS ESPECÍFICAS
        df = df.drop(columns=[0, 9, 14, 19, 24, 29, 34])

        # 3. FILTRAR LINHAS
        df = df[df[1].notna() & df[4].notna()].copy()

        # 4. PROMOVER CABEÇALHOS
        df.columns = df.iloc[0]
        df = df.drop(df.index[0]).reset_index(drop=True)

        if 'UGB' not in df.columns or 'Nº LOTES' not in df.columns:
            print("Erro: Estrutura de colunas diferente do esperado.")
            return None

        # 5. UNPIVOT (transformar colunas em linhas)
        ### ALTERADO ### - Adicionadas as novas colunas 'M' e 'PJ' na lista de unpivot.
        colunas_unpivot = [
            "DM.REAL.TÉRMINO", "DM.REAL.INÍCIO", "DM.PREV.TÉRMINO", "DM.PREV.INÍCIO",
            "DOC.REAL.TÉRMINO", "DOC.REAL.INICIO", "DOC.PREV.TÉRMINO", "DOC.PREV.INÍCIO",
            "LAE.REAL.TÉRMINO", "LAE.REAL.INÍCIO", "LAE.PREV.TÉRMINO", "LAE.PREV.INÍCIO",
            "MEM.REAL.TÉRMINO", "MEM.REAL.INÍCIO", "MEM.PREV.TÉRMINO", "MEM.PREV.INÍCIO",
            "CONT.REAL.TÉRMINO", "CONT.REAL.INÍCIO", "CONT.PREV.TÉRMINO", "CONT.PREV.INÍCIO",
            "ASS.REAL.TÉRMINO", "ASS.REAL.INÍCIO", "ASS.PREV.TÉRMINO", "ASS.PREV.INÍCIO",
            "M.REAL.TÉRMINO", "M.REAL.INÍCIO", "M.PREV.TÉRMINO", "M.PREV.INÍCIO",      # Nova Etapa
            "PJ.REAL.TÉRMINO", "PJ.REAL.INÍCIO", "PJ.PREV.TÉRMINO", "PJ.PREV.INÍCIO"      # Nova Etapa
        ]
        
        colunas_fixas = [col for col in df.columns if col not in colunas_unpivot]
        df_unpivoted = pd.melt(
            df,
            id_vars=colunas_fixas,
            value_vars=colunas_unpivot,
            var_name="Atributo",
            value_name="Valor"
        )

        # 6. DIVIDIR COLUNA "Atributo"
        split_cols = df_unpivoted['Atributo'].str.split('.', expand=True)
        split_cols.columns = ['Etapa', 'Tipo', 'Inicio_Fim']
        df_final = pd.concat([df_unpivoted, split_cols], axis=1)
        df_final = df_final.drop(columns=['Atributo'])

        # 7. CONVERTER TIPOS DE COLUNAS
        df_final = df_final.astype({
            'UGB': 'str', 'EMP': 'str', 'MÓDULO': 'str',
            'Avaliação': 'int64', 'Nº LOTES': 'int64'
        })
        df_final['Valor'] = pd.to_datetime(df_final['Valor'], errors='coerce').dt.date

        # 8. FILTRAR APENAS "PREV"
        df_final = df_final[df_final['Tipo'] == 'PREV'].copy()
        
        ### ALTERADO ### - Adicionado o mapeamento e a ordenação pelas novas etapas.
        # 9. CRIAR ORDEM DAS ETAPAS E ORDENAR
        mapa_ordem = {
            'DM': 1, 'DOC': 2, 'LAE': 3, 'MEM': 4, 
            'CONT': 5, 'ASS': 6, 'M': 7, 'PJ': 8
        }
        df_final['Ordem_Etapa'] = df_final['Etapa'].map(mapa_ordem)
        
        # Ordena o DataFrame final pela ordem definida
        df_final = df_final.sort_values(by=['UGB', 'MÓDULO', 'Ordem_Etapa']).reset_index(drop=True)

        return df_final

    except Exception as e:
        print(f"Erro durante o processamento: {str(e)}")
        return None

# Executa a função e mostra o resultado
if __name__ == "__main__":
    dados_previstos = tratar_e_retornar_dados_previstos()
    if dados_previstos is not None:
        print("\nDados Previstos Tratados e Ordenados:")
        # Mostra as colunas relevantes para verificar a ordem
        print(dados_previstos[['UGB', 'MÓDULO', 'Etapa', 'Ordem_Etapa', 'Inicio_Fim', 'Valor']].head(20))
        
        # Opcional: Salvar em CSV
        dados_previstos.to_csv('dados_previstos_tratados_ordenados.csv', index=False)
        print("\nArquivo 'dados_previstos_tratados_ordenados.csv' salvo com sucesso!")
    else:
        print("\nNão foi possível obter os dados previstos.")

