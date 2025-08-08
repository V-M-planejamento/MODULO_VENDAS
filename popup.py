import streamlit as st
import base64
import os

def show_welcome_screen():
    """
    Função que exibe um popup em tela cheia usando o SVG como fundo.
    Remove completamente o card/quadrado e o título, mantendo apenas o SVG e o botão.
    Posiciona o botão no canto inferior direito da tela.
    """
    
    # Inicializar o estado do popup se não existir
    if 'show_popup' not in st.session_state:
        st.session_state.show_popup = True
    
    # Se o popup deve ser exibido
    if st.session_state.show_popup:
        
        # Função para carregar e codificar o SVG
        def load_svg_as_base64():
            # Tentar diferentes caminhos para o SVG
            possible_paths = [
                '31123505_7769742.psd(10).svg',  # Mesmo diretório do script
                './31123505_7769742.psd(10).svg',  # Caminho relativo
                '/home/ubuntu/31123505_7769742.psd(10).svg',  # Diretório atual
                '/home/ubuntu/upload/31123505_7769742.psd(10).svg',  # Caminho absoluto
                os.path.join(os.path.dirname(__file__), '31123505_7769742.psd(10).svg')  # Diretório do script
            ]
            
            for svg_path in possible_paths:
                if os.path.exists(svg_path):
                    try:
                        with open(svg_path, 'rb') as svg_file:
                            svg_content = svg_file.read()
                            return base64.b64encode(svg_content).decode('utf-8')
                    except Exception as e:
                        continue
            
            # Se não conseguir carregar, retorna uma string vazia
            return ""
        
        svg_base64 = load_svg_as_base64()
        
        # CSS para criar o popup em tela cheia com SVG como fundo
        popup_css = f"""
        <style>
        /* Reset completo */
        html, body, .stApp {{
            margin: 0 !important;
            padding: 0 !important;
            height: 100vh !important;
            overflow: hidden !important;
        }}
        
        /* Esconder completamente a interface do Streamlit */
        .main .block-container,
        header,
        .stApp > div:first-child,
        .stApp > header,
        .stDeployButton,
        .stDecoration,
        .stToolbar {{
            display: none !important;
        }}
        
        /* Container principal do popup ocupando toda a tela */
        .popup-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            {f"background-image: url('data:image/svg+xml;base64,{svg_base64}');" if svg_base64 else "background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);"}
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            z-index: 9998;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            overflow: hidden;
            object-fit: contain;  /* Nova propriedade */
        }}
        /* Garantir que o SVG não seja cortado e mantenha proporção */
        .popup-overlay::before {{
            content: '';
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: inherit;
            z-index: -1;
        }}
        
        /* Estilização do botão */
        .stButton > button {{
            background: linear-gradient(45deg, #ff8c00, #ff6b00) !important;
            color: white !important;
            border: none !important;
            padding: 18px 36px !important;
            font-size: 1.2em !important;
            border-radius: 50px !important;
            cursor: pointer !important;
            transition: all 0.3s ease !important;
            width: auto !important;
            box-shadow: 0 6px 20px rgba(255, 140, 0, 0.4) !important;
            font-weight: 600 !important;
            letter-spacing: 0.8px !important;
            min-width: 220px !important;
            text-transform: uppercase !important;
        }}
        
        .stButton > button:hover {{
            transform: translateY(-3px) !important;
            box-shadow: 0 8px 25px rgba(255, 140, 0, 0.6) !important;
            background: linear-gradient(45deg, #ff9500, #ff7500) !important;
        }}
        
        .stButton > button:active {{
            transform: translateY(-1px) !important;
        }}
        
        .stButton > button:focus {{
            outline: none !important;
            box-shadow: 0 0 0 3px rgba(255, 140, 0, 0.3) !important;
        }}
        
        /* Garantir posicionamento fixo do botão no canto inferior direito */
        .stButton {{
            position: fixed !important;
            bottom: 30px !important;
            left: 1270px !important;
            z-index: 10001 !important;
            margin: 0 !important;
            transform: none !important;
        }}
        
        /* Responsividade para dispositivos móveis */
        @media (max-width: 768px) {{
            .stButton {{
                bottom: 20px !important;
                left: 20px !important;  /* Alterado de right para left */
            }}
            
            .stButton > button {{
                padding: 16px 28px !important;
                font-size: 1.1em !important;
                min-width: 180px !important;
            }}
        }}

        @media (max-width: 480px) {{
            .stButton {{
                bottom: 15px !important;
                left: 15px !important;  /* Alterado de right para left */
            }}
            
            .stButton > button {{
                padding: 14px 24px !important;
                font-size: 1em !important;
                min-width: 160px !important;
            }}
        }}
        </style>
        """
        
        st.markdown(popup_css, unsafe_allow_html=True)
        
        # Criar o popup HTML sem título
        popup_html = """
        <div class="popup-overlay">
        </div>
        """
        
        st.markdown(popup_html, unsafe_allow_html=True)
        
        # Debug: Mostrar se o SVG foi carregado (apenas para desenvolvimento)
        if not svg_base64:
            st.error("⚠️ SVG não foi carregado. Certifique-se de que o arquivo '31123505_7769742.psd(10).svg' está na mesma pasta do script.")
        
        # Botão para fechar o popup - posicionado no canto inferior direito
        if st.button("🚀 Acessar Painel", key="close_popup_btn", help="Clique para acessar o painel principal"):
            st.session_state.show_popup = False
            st.rerun()
        
        return True
    else:
        return False

def reset_popup():
    """Função para resetar o popup"""
    st.session_state.show_popup = True

def hide_popup():
    """Função para esconder o popup programaticamente"""
    st.session_state.show_popup = False

# Exemplo de uso
if __name__ == "__main__":
    st.set_page_config(
        page_title="Dashboard - Módulo de Venda",
        page_icon="🏠",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    
    # Mostrar o popup de boas-vindas
    if show_welcome_screen():
        # O popup está sendo exibido
        pass
    else:
        # Conteúdo principal da aplicação após fechar o popup
        st.title("🏠 Dashboard - Módulo de Venda")
        st.write("Bem-vindo ao sistema!")
        
        # Botão para mostrar o popup novamente
        if st.button("Mostrar Popup Novamente"):
            reset_popup()
            st.rerun()

