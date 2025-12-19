import pandas as pd
import smartsheet
import os
from dotenv import load_dotenv
import streamlit as st
import sys
from datetime import datetime

# Configurações
SHEET_NAME = "MÓDULOS DE VENDA"
OUTPUT_CSV = "modulos_venda_tratados.csv"

def carregar_configuracao():
    """Carrega as configurações e verifica o ambiente"""
    try:
        # Tenta pegar do st.secrets primeiro
        if hasattr(st, "secrets") and "SMARTSHEET_ACCESS_TOKEN" in st.secrets:
            return st.secrets["SMARTSHEET_ACCESS_TOKEN"]
        
        # Fallback para variável de ambiente/arquivo .env
        load_dotenv()
        token = os.getenv("SMARTSHEET_ACCESS_TOKEN")
        
        if not token:
            print("Token não encontrado nem no st.secrets nem nas variáveis de ambiente.")
            return None
        
        return token
    
    except Exception as e:
        print(f"\nERRO DE CONFIGURAÇÃO: {str(e)}")
        return None

def setup_smartsheet_client(token):
    """Configura o cliente Smartsheet"""
    try:
        client = smartsheet.Smartsheet(token)
        client.errors_as_exceptions(True)
        return client
    except Exception as e:
        print(f"\nERRO: Falha ao configurar cliente Smartsheet - {str(e)}")
        return None

def get_sheet_id(client, sheet_name):
    """Obtém o ID da planilha"""
    try:
        print(f"\nBuscando planilha '{sheet_name}'...")
        response = client.Sheets.list_sheets(include_all=True)
        
        for sheet in response.data:
            if sheet.name == sheet_name:
                print(f"Planilha encontrada (ID: {sheet.id})")
                return sheet.id
        
        print(f"\nERRO: Planilha '{sheet_name}' não encontrada")
        print("Verifique:")
        print(f"- O nome exato da planilha ('{sheet_name}')")
        print("- Se você tem acesso a esta planilha")
        return None
        
    except smartsheet.exceptions.ApiError as api_error:
        print(f"\nERRO DE API: {api_error.message}")
        return None
    except Exception as e:
        print(f"\nErro inesperado ao buscar planilhas: {str(e)}")
        return None

def get_sheet_data(client, sheet_id):
    """Obtém os dados da planilha"""
    try:
        print("\nObtendo dados da planilha...")
        sheet = client.Sheets.get_sheet(sheet_id)
        
        # Converter para DataFrame de forma eficiente
        rows = []
        for row in sheet.rows:
            row_data = {}
            for cell in row.cells:
                column_name = next((col.title for col in sheet.columns if col.id == cell.column_id), None)
                if column_name:
                    row_data[column_name] = cell.value
            rows.append(row_data)
        
        df = pd.DataFrame(rows)
        print(f"✅ Dados obtidos ({len(df)} linhas)")
        return df
    
    except Exception as e:
        print(f"\n❌ Falha ao obter dados: {str(e)}")
        return pd.DataFrame()

def process_data(df):
    """Processa e limpa os dados"""
    if df.empty:
        print("⚠️ Aviso: Nenhum dado recebido para processamento")
        return df

    try:
        # Verificar colunas essenciais
        colunas_necessarias = ['Atividade', 'Módulo']
        faltantes = [col for col in colunas_necessarias if col not in df.columns]
        if faltantes:
            print(f"❌ Colunas necessárias faltando: {faltantes}")
            return pd.DataFrame()

        # Converter tipos de dados
        print("\n🔁 Convertendo tipos de dados...")
        df = df.astype({
            '% concluído': 'object',
            'Nome da tarefa': 'string',
            'Atividade': 'string',
            'Módulo': 'string'
        }, errors='ignore')

        # Converter datas
        for col in ['Iniciar', 'Terminar']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        # Remover colunas desnecessárias
        colunas_remover = [
            "RowNumber", "AT.", "Antecessores", "OK", "Var. Térm.",
            "Início LB", "Término LB", "Dur. LB", "Atribuído a",
            "Status", "Coluna23", "Coluna24", "Coluna25", "Coluna26", "% de alocação"
        ]
        df = df.drop(columns=[col for col in colunas_remover if col in df.columns], errors='ignore')

        # Filtrar linhas válidas
        df = df[df['Atividade'].notna()].copy()

        # Processar coluna Módulo
        if 'Módulo' in df.columns:
            print("🔀 Dividindo coluna 'Módulo'...")
            split_mod = df['Módulo'].str.split(r' \| ', n=1, expand=True)
            df['UGB'] = split_mod[0]
            df['Emp'] = split_mod[1] if split_mod.shape[1] > 1 else pd.NA
            df = df.drop(columns=['Módulo'])

        # Converter % concluído
        if '% concluído' in df.columns:
            # Primeiro converte para string e limpa
            df['% concluído'] = df['% concluído'].astype(str).str.replace('%', '').str.replace(',', '.')
            
            # Converte para numérico
            df['% concluído'] = pd.to_numeric(df['% concluído'], errors='coerce').fillna(0)
            
            # Se o valor for > 1 (ex: 100), divide por 100. Se for <= 1 (ex: 1.0 ou 0.5), mantém.
            # Assume que 1.0 significa 100% vindo do Smartsheet se já estiver em decimal
            mask_maior_que_um = df['% concluído'] > 1.0
            df.loc[mask_maior_que_um, '% concluído'] = df.loc[mask_maior_que_um, '% concluído'] / 100.0

        # Renomear colunas
        df = df.rename(columns={'Atividade': 'Etapa'})

        # Filtrar empresas
        if 'Emp' in df.columns:
            empresas_remover = [
                None, "BA-10", "BA-11", 
                "Módulo 05 - São Francisco (I)", 
                "Módulo 06 - Zona da Mata (H)",
                "Módulo 07 - Metropolitano (G)",
                "Módulo 08 - Pajeú (F)"
            ]
            df = df[~df['Emp'].isin(empresas_remover)]

        print("✅ Dados processados com sucesso")
        return df

    except Exception as e:
        print(f"\n❌ ERRO NO PROCESSAMENTO: {str(e)}")
        return pd.DataFrame()

def salvar_resultados(df):
    """Salva os dados processados em CSV"""
    try:
        df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
        print(f"\n💾 Arquivo salvo com sucesso: {OUTPUT_CSV}")
        print("\n📋 Visualização dos dados:")
        print(df.head())
        return True
    except Exception as e:
        print(f"\n❌ ERRO AO SALVAR: {str(e)}")
        return False

def main():
    print("\n" + "="*50)
    print(" INÍCIO DO PROCESSAMENTO ".center(50, "="))
    print("="*50)

    # 1. Carregar configurações
    token = carregar_configuracao()
    if not token:
        print("Aborting: No Token found.")
        return # Substitui sys.exit(1)

    # 2. Configurar cliente Smartsheet
    client = setup_smartsheet_client(token)
    if not client:
        return # Substitui sys.exit(1)

    # 3. Obter ID da planilha
    sheet_id = get_sheet_id(client, SHEET_NAME)
    if not sheet_id:
        return # Substitui sys.exit(1)

    # 4. Obter dados
    raw_data = get_sheet_data(client, sheet_id)
    if raw_data.empty:
        return # Substitui sys.exit(1)

    # 5. Processar dados
    processed_data = process_data(raw_data)
    if processed_data.empty:
        return # Substitui sys.exit(1)

    # 6. Salvar resultados
    if not salvar_resultados(processed_data):
        return # Substitui sys.exit(1)

if __name__ == "__main__":
    main()
