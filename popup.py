import streamlit as st

def show_welcome_screen():
    """
    Função que exibe um popup em tela cheia com design moderno e card fosco.
    Mantém a mensagem e botão originais, mas com estilização aprimorada.
    """
    
    # Inicializar o estado do popup se não existir
    if 'show_popup' not in st.session_state:
        st.session_state.show_popup = True
    
    # Se o popup deve ser exibido
    if st.session_state.show_popup:
        # CSS para criar o popup em tela cheia com card fosco
        popup_css = """
        <style>
        /* Fundo com gradiente sutil */
        .popup-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(135deg, #f5f7fa 0%, #e4e8eb 100%);
            z-index: 9998;
            display: flex;
            justify-content: center;
            align-items: center;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        /* Card central fosco com efeito glassmorphism */
        .popup-content {
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            padding: 50px 60px 40px 60px;
            border-radius: 16px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            text-align: center;
            max-width: 500px;
            width: 80%;
            position: relative;
            z-index: 9999;
            border: 1px solid rgba(255, 255, 255, 0.3);
        }
        
        /* Título com gradiente */
        .popup-title {
            font-size: 2.2em;
            margin-bottom: 20px;
            font-weight: 700;
            background: linear-gradient(45deg, #2c3e50, #3498db);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            line-height: 1.2;
        }
        
        /* Mensagem estilizada */
        .popup-message {
            font-size: 1.1em;
            color: #555;
            margin-bottom: 30px;
            line-height: 1.6;
        }
        
        /* Esconder outros elementos do Streamlit */
        .main .block-container {
            display: none !important;
        }
        
        header {
            display: none !important;
        }
        
        .stApp > div:first-child {
            display: none !important;
        }
        
        /* Estilizar o botão do Streamlit */
        .stButton > button {
            background: linear-gradient(45deg, #3498db, #2c3e50) !important;
            color: white !important;
            border: none !important;
            padding: 14px 32px !important;
            font-size: 1.1em !important;
            border-radius: 50px !important;
            cursor: pointer !important;
            transition: all 0.3s ease !important;
            width: auto !important;
            box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3) !important;
            font-weight: 500 !important;
            letter-spacing: 0.5px !important;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(52, 152, 219, 0.4) !important;
        }
        
        .stButton > button:focus {
            outline: none !important;
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.3) !important;
        }
        
        /* Posicionar o botão dentro do popup */
        .stButton {
            position: relative !important;
            margin: 0 auto !important;
            display: block !important;
            z-index: 10000 !important;
            transform: none !important;
            top: auto !important;
            left: auto !important;
        }
        
        /* Efeito de marca d'água no fundo */
        .watermark {
            position: absolute;
            bottom: 20px;
            left: 0;
            right: 0;
            text-align: center;
            color: rgba(0, 0, 0, 0.1);
            font-size: 12px;
            font-weight: bold;
        }
        </style>
        """
        
        st.markdown(popup_css, unsafe_allow_html=True)
        
        # Criar o popup HTML
        popup_html = """
        <div class="popup-overlay">
            <div class="popup-content">
                <h1 class="popup-title">🎯 Bem-vindo!</h1>
                <p class="popup-message">
                    Este é o seu sistema de gestão do Modulo Vendas.<br>
                    Clique no botão abaixo para acessar o painel principal.
                </p>
                <div class="watermark">VIANA & MOURA CONSTRUÇÕES</div>
            </div>
        </div>
        """
        
        st.markdown(popup_html, unsafe_allow_html=True)
        
        # Botão para fechar o popup usando Streamlit nativo
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

