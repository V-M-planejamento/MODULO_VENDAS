import streamlit as st
import streamlit.components.v1 as components
import base64
import io
import matplotlib.pyplot as plt
from typing import Optional

def create_fullscreen_image_viewer(figure: plt.Figure, 
                                         empreendimento: Optional[str] = None) -> None:
    """
    Renderiza um gráfico Matplotlib diretamente no HTML com um botão de tela cheia
    posicionado corretamente no canto superior direito.

    Args:
        figure (plt.Figure): A figura Matplotlib a ser exibida.
        empreendimento (Optional[str]): Um identificador único para o componente.
    """
    
    # --- Etapa 1: Converter a figura para imagem Base64 ---
    # Isso é para a imagem que será exibida na página
    img_buffer_display = io.BytesIO()
    figure.savefig(img_buffer_display, format='png', dpi=150, bbox_inches='tight') # DPI menor para exibição
    img_base64_display = base64.b64encode(img_buffer_display.getvalue()).decode('utf-8')

    # Isso é para a imagem de alta resolução que será aberta no visualizador
    img_buffer_viewer = io.BytesIO()
    figure.savefig(img_buffer_viewer, format='png', dpi=300, bbox_inches='tight', facecolor='white') # DPI maior para zoom
    img_base64_viewer = base64.b64encode(img_buffer_viewer.getvalue()).decode('utf-8')
    
    unique_id = f"viewer-btn-{empreendimento if empreendimento else hash(img_base64_display)}"

    # --- Etapa 2: Criar o HTML com o gráfico e o botão juntos ---
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            /* O container principal que segura o gráfico e o botão */
            .gantt-container {{
                position: relative; /* ESSENCIAL: Cria o contexto de posicionamento */
                width: 100%;
            }}

            /* A imagem do gráfico */
            .gantt-image {{
                width: 100%;
                height: auto;
                display: block; /* Remove espaços extras abaixo da imagem */
            }}

            /* O botão de tela cheia */
            .fullscreen-btn {{
                position: absolute; /* Posicionado em relação ao .gantt-container */
                top: 45px;   /* 10px do topo do container */
                right: 49px; /* 10px da direita do container */
                
                background-color: #FFFFFF;
                color: #31333F;
                border: 1px solid #E6EAF1;
                width: 32px;
                height: 32px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 18px;
                font-weight: bold;
                
                display: flex;
                align-items: center;
                justify-content: center;
                
                transition: all 0.2s ease;
                z-index: 10; /* Fica na frente da imagem do gráfico */
            }}
            .fullscreen-btn:hover {{
                border-color: #FF4B4B;
                color: #FF4B4B;
            }}
        </style>
    </head>
    <body>
        <!-- O container que envolve tudo -->
        <div class="gantt-container">
            <!-- A imagem do gráfico exibida na página -->
            <img src="data:image/png;base64,{img_base64_display}" class="gantt-image" alt="Gráfico Gantt">
            
            <!-- O botão posicionado sobre a imagem -->
            <button id="{unique_id}" class="fullscreen-btn" title="Visualizar em tela cheia">⛶</button>
        </div>

        <script>
            // O JavaScript para o visualizador (exatamente o mesmo de antes)
            (function() {{
                const parentDoc = window.parent.document;
                const button = document.getElementById('{unique_id}');
                const viewerImgSrc = 'data:image/png;base64,{img_base64_viewer}';

                const styleId = 'viewer-hide-streamlit-header';
                if (!parentDoc.getElementById(styleId)) {{
                    const style = parentDoc.createElement('style');
                    style.id = styleId;
                    style.innerHTML = `body.viewer-active header[data-testid="stHeader"] {{ display: none; }}`;
                    parentDoc.head.appendChild(style);
                }}

                function loadScript(src, callback) {{
                    let script = parentDoc.querySelector(`script[src="${{src}}"]`);
                    if (script) {{ if (callback) callback(); return; }}
                    script = parentDoc.createElement('script');
                    script.src = src;
                    script.onload = callback;
                    parentDoc.head.appendChild(script);
                }}

                function loadCss(href) {{
                    if (!parentDoc.querySelector(`link[href="${{href}}"]`)) {{
                        const link = parentDoc.createElement('link');
                        link.rel = 'stylesheet'; link.href = href;
                        parentDoc.head.appendChild(link);
                    }}
                }}

                loadCss('https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.css' );

                button.addEventListener('click', function() {{
                    loadScript('https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.js', function( ) {{
                        const tempImage = parentDoc.createElement('img');
                        tempImage.src = viewerImgSrc;
                        tempImage.style.display = 'none';
                        parentDoc.body.appendChild(tempImage);

                        const viewer = new parent.Viewer(tempImage, {{
                            inline: false, navbar: false, button: true, title: false,
                            toolbar: true, fullscreen: true, keyboard: true, zIndex: 99999,
                            shown: () => parentDoc.body.classList.add('viewer-active'),
                            hidden: () => {{
                                parentDoc.body.classList.remove('viewer-active');
                                viewer.destroy();
                                parentDoc.body.removeChild(tempImage);
                            }},
                        }});
                        viewer.show();
                    }});
                }});
            }})();
        </script>
    </body>
    </html>
    """
    
    # Renderiza o componente HTML. A altura será automática.
    components.html(html_content, height=figure.get_figheight() * 61) # Ajuste a altura se necessário

# --- Exemplo de uso ---
if __name__ == '__main__':
    st.set_page_config(layout="wide")
    
    st.sidebar.image("https://viannaemoura.com.br/wp-content/uploads/2023/09/logo-Vianna-Moura.png", use_column_width=True )
    st.sidebar.header("Barra Lateral")

    st.title("Solução Final: Botão e Gráfico Envelopados")
    st.success("Agora o botão está perfeitamente posicionado sobre o gráfico porque ambos vivem no mesmo container HTML.")

    # 1. Criar a figura
    fig, ax = plt.subplots(figsize=(16, 8)) # Tamanho de exemplo
    ax.barh(['Tarefa A', 'Tarefa B', 'Tarefa C'], [10, 20, 15], left=[5, 0, 12])
    ax.set_title("Gráfico de Gantt com Botão Corretamente Posicionado")
    ax.grid(True, linestyle='--', alpha=0.5)
    plt.tight_layout()

    # 2. Usar a nova função para renderizar tudo de uma vez
    create_fullscreen_image_viewer(fig, empreendimento="gantt_final")

    st.markdown("---")
    st.write("Outro conteúdo da página.")
