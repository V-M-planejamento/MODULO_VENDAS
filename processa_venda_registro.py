import pandas as pd
import os

def tratar_e_retornar_dados_previstos():
    """Carrega e trata os dados, retornando apenas os dados PREV"""
    try:
        # 1. CARREGAR OS DADOS
        caminho_arquivo = r"C:\Users\Viana e Moura\Dropbox\PLANEJAMENTO\8. PCP - MACROFLUXO\MACROFLUXO ATUALIZADO\BASE - VENDA E REGISTRO.xlsx"
        if not os.path.exists(caminho_arquivo):
            print(f"Erro: Arquivo não encontrado no caminho: {caminho_arquivo}")
            return None

        # Carrega sem considerar a primeira linha como cabeçalho
        df = pd.read_excel(caminho_arquivo, sheet_name="PLANEJADOR MÓDULOS", header=None)

        # 2. REMOVER COLUNAS ESPECÍFICAS (pelos índices originais)
        # Column1 (0), Column10 (9), Column15 (14), Column20 (19), Column25 (24), Column30 (29), Column35 (34)
        df = df.drop(columns=[0, 9, 14, 19, 24, 29, 34])

        # 3. FILTRAR LINHAS (Column2 e Column5 não nulas - índices 1 e 4)
        df = df[df[1].notna() & df[4].notna()].copy()

        # 4. PROMOVER CABEÇALHOS (primeira linha vira nome das colunas)
        df.columns = df.iloc[0]
        df = df.drop(df.index[0]).reset_index(drop=True)

        # Verifica estrutura esperada
        if 'UGB' not in df.columns or 'Nº LOTES' not in df.columns:
            print("Erro: Estrutura de colunas diferente do esperado")
            return None

        # 5. UNPIVOT (transformar colunas em linhas)
        colunas_unpivot = [
            "ASS.REAL.TÉRMINO", "ASS.REAL.INÍCIO", "ASS.PREV.TÉRMINO", "ASS.PREV.INÍCIO",
            "CONT.REAL.TÉRMINO", "CONT.REAL.INÍCIO", "CONT.PREV.TÉRMINO", "CONT.PREV.INÍCIO",
            "LAE.REAL.TÉRMINO", "LAE.REAL.INÍCIO", "LAE.PREV.TÉRMINO", "LAE.PREV.INÍCIO",
            "MEM.REAL.TÉRMINO", "MEM.REAL.INÍCIO", "MEM.PREV.TÉRMINO", "MEM.PREV.INÍCIO",
            "ENG.REAL.TÉRMINO", "ENG.REAL.INÍCIO", "ENG.PREV.TÉRMINO", "ENG.PREV.INÍCIO",
            "DOC.REAL.TÉRMINO", "DOC.REAL.INICIO", "DOC.PREV.TÉRMINO", "DOC.PREV.INÍCIO",
            "DM.REAL.TÉRMINO", "DM.REAL.INÍCIO", "DM.PREV.TÉRMINO", "DM.PREV.INÍCIO"
        ]
        
        colunas_fixas = [col for col in df.columns if col not in colunas_unpivot]
        df_unpivoted = pd.melt(
            df,
            id_vars=colunas_fixas,
            value_vars=colunas_unpivot,
            var_name="Atributo",
            value_name="Valor"
        )

        # 6. DIVIDIR COLUNA POR DELIMITADOR
        split_cols = df_unpivoted['Atributo'].str.split('.', expand=True)
        split_cols.columns = ['Etapa', 'Tipo', 'Inicio_Fim']
        df_final = pd.concat([df_unpivoted, split_cols], axis=1)
        df_final = df_final.drop(columns=['Atributo'])

        # 7. CONVERTER TIPOS DE COLUNAS
        df_final = df_final.astype({
            'UGB': 'str',
            'EMP': 'str',
            'MÓDULO': 'str',
            'Avaliação': 'int64',
            'Nº LOTES': 'int64'
        })
        df_final['Valor'] = pd.to_datetime(df_final['Valor']).dt.date

        # 8. FILTRAR APENAS "PREV" (REMOVER "REAL")
        df_final = df_final[df_final['Tipo'] == 'PREV'].copy()

        return df_final

    except Exception as e:
        print(f"Erro durante o processamento: {str(e)}")
        return None

# Executa a função e mostra o resultado
if __name__ == "__main__":
    dados_previstos = tratar_e_retornar_dados_previstos()
    if dados_previstos is not None:
        print("\nDados Previstos Tratados:")
        print(dados_previstos)
        
        # Opcional: Salvar em CSV
        dados_previstos.to_csv('dados_previstos_tratados.csv', index=False)
        print("\nArquivo 'dados_previstos_tratados.csv' salvo com sucesso!")
    else:
        print("Não foi possível obter os dados previstos.")