
import streamlit as st
import streamlit.components.v1 as components
import base64
import io
import matplotlib.pyplot as plt
from typing import Optional, List, Dict, Any
import json
import time

def create_fullscreen_image_viewer(
    figure: plt.Figure,
    empreendimento: Optional[str] = None,
    all_filtered_charts_data: Optional[List[Dict[str, Any]]] = None,
    current_chart_index: int = 0
) -> None:
    """
    Renderiza um gráfico Matplotlib com um botão de tela cheia e implementa
    a navegação entre gráficos (empreendimentos) usando as setas do teclado
    e botões na barra de ferramentas do modo de tela cheia.

    Args:
        figure (plt.Figure): A figura Matplotlib a ser exibida.
        empreendimento (Optional[str]): Um identificador único para o gráfico/empreendimento.
        all_filtered_charts_data (Optional[List[Dict[str, Any]]]): Lista de todos os gráficos filtrados
                                                                    (com id e src base64) para navegação.
        current_chart_index (int): O índice do gráfico atual na lista all_filtered_charts_data.
    """

    # --- Etapa 1: Obter a imagem Base64 para exibição e para o ViewerJS ---
    img_base64_display = None
    img_base64_viewer = None
    unique_id = None

    if figure is not None:
        # Salva a figura em alta resolução uma única vez
        img_buffer_high_res = io.BytesIO()
        figure.savefig(img_buffer_high_res, format="png", dpi=300, bbox_inches="tight", facecolor="white")
        img_base64_high_res = base64.b64encode(img_buffer_high_res.getvalue()).decode("utf-8")
        
        # Usa a imagem de alta resolução tanto para exibição quanto para o viewer
        img_base64_display = img_base64_high_res
        img_base64_viewer = img_base64_high_res
        unique_id = f"viewer-btn-{empreendimento if empreendimento else hash(img_base64_display)}"
        plt.close(figure) # Fechar a figura Matplotlib após salvar para liberar memória
    elif all_filtered_charts_data and current_chart_index < len(all_filtered_charts_data):
        # Se a figura não for fornecida, mas os dados do gráfico filtrado sim, use o primeiro para exibição
        img_base64_display = all_filtered_charts_data[current_chart_index]["src"].split(",")[1] # Remove o prefixo data:image/png;base64,
        img_base64_viewer = img_base64_display # Para o viewer, pode ser o mesmo
        unique_id = f"viewer-btn-{all_filtered_charts_data[current_chart_index]["id"]}"
    else:
        st.error("Nenhum gráfico fornecido para exibição.")
        return

    if not unique_id:
        unique_id = f"viewer-btn-{int(time.time())}" # Fallback para unique_id se não for definido antes}"

    # --- Etapa 2: Preparar dados dos gráficos para o ViewerJS ---
    # Se all_filtered_charts_data não for fornecido, use apenas o gráfico atual
    if all_filtered_charts_data is None:
        charts_for_viewer = [{
            "id": empreendimento,
            "src": f"data:image/png;base64,{img_base64_viewer}"
        }]
        viewer_initial_index = 0
    else:
        charts_for_viewer = all_filtered_charts_data
        viewer_initial_index = current_chart_index

    charts_json = json.dumps(charts_for_viewer)

    # --- Etapa 3: Criar o HTML com JavaScript para navegação ---
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            .gantt-container {{ position: relative; width: 100%; height: 500px; margin: 0 auto; background-color: white; border-radius: 8px; overflow: hidden; }}
            .image-wrapper {{ width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background-color: white; }}
            .gantt-image {{ max-width: 100%; max-height: 100%; width: auto; height: auto; object-fit: contain; }}
            .fullscreen-btn {{ position: absolute; top: 10px; right: 10px; background-color: #FFFFFF; color: #31333F; border: 1px solid #E6EAF1; width: 32px; height: 32px; border-radius: 8px; cursor: pointer; font-size: 18px; font-weight: bold; display: flex; align-items: center; justify-content: center; transition: all 0.2s ease; z-index: 10; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .fullscreen-btn:hover {{ border-color: #FF4B4B; color: #FF4B4B; transform: scale(1.05); }}
        </style>
    </head>
    <body>
        <div class="gantt-container">
            <div class="image-wrapper">
                <img src="data:image/png;base64,{img_base64_display}" class="gantt-image" alt="Gráfico Gantt">
                <button id="{unique_id}" class="fullscreen-btn" title="Visualizar em tela cheia">⛶</button>
            </div>
        </div>

        <script>
            (function() {{
                const parentDoc = window.parent.document;
                const button = document.getElementById(\"{unique_id}\");
                const allCharts = {charts_json};
                const initialViewIndex = {viewer_initial_index};
                
                // Estilos para ocultar elementos do Streamlit
                const styleId = \'viewer-hide-streamlit-elements\';
                if (!parentDoc.getElementById(styleId)) {{
                    const style = parentDoc.createElement(\'style\');
                    style.id = styleId;
                    style.innerHTML = `
                        body.viewer-active header[data-testid="stHeader"],
                        body.viewer-active .stDeployButton {{ display: none; }}
                        body.viewer-active section[data-testid="stSidebar"] {{ transform: translateX(-100%); transition: transform 0.3s ease-in-out; }}
                        body.viewer-active .main .block-container {{ max-width: 100% !important; padding-left: 1rem !important; padding-right: 1rem !important; transition: all 0.3s ease-in-out; }}
                    `;
                    parentDoc.head.appendChild(style);
                }}

                // Funções para carregar CSS e JS
                function loadScript(src, callback) {{
                    let script = parentDoc.querySelector(`script[src="${{src}}"]`);
                    if (script) {{ if (callback) callback(); return; }}
                    script = parentDoc.createElement(\'script\');
                    script.src = src;
                    script.onload = callback;
                    parentDoc.head.appendChild(script);
                }}
                
                function loadCss(href) {{
                    if (!parentDoc.querySelector(`link[href="${{href}}"]`)) {{
                        const link = parentDoc.createElement(\'link\');
                        link.rel = \'stylesheet\'; link.href = href;
                        parentDoc.head.appendChild(link);
                    }}
                }}

                loadCss(\'https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.css\');

                button.addEventListener(\'click\', function() {{
                    loadScript(\'https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.js\', function() {{
                        const galleryContainer = parentDoc.createElement(\'ul\');
                        galleryContainer.style.display = \'none\';

                        allCharts.forEach(chartData => {{
                            const listItem = parentDoc.createElement(\'li\');
                            const img = parentDoc.createElement(\'img\');
                            img.src = chartData.src;
                            img.alt = chartData.id;
                            listItem.appendChild(img);
                            galleryContainer.appendChild(listItem);
                        }});
                        
                        parentDoc.body.appendChild(galleryContainer);

                        const viewer = new parent.Viewer(galleryContainer, {{
                            inline: false,
                            navbar: false, // Mantido como 'false' para ocultar a barra inferior
                            button: true,
                            title: (image) => image.alt,
                            toolbar: {{
                                zoomIn: 1,
                                zoomOut: 1,
                                oneToOne: 1,
                                reset: 1,
                                prev: 1,
                                play: {{ show: 1, size: \'large\' }},
                                next: 1,
                                rotateLeft: 1,
                                rotateRight: 1,
                                flipHorizontal: 1,
                                flipVertical: 1,
                            }},
                            fullscreen: true,
                            keyboard: true,
                            zIndex: 99999,
                            initialViewIndex: initialViewIndex,
                            shown: () => {{
                                parentDoc.body.classList.add(\'viewer-active\');
                            }},
                            hidden: () => {{
                                parentDoc.body.classList.remove(\'viewer-active\');
                                viewer.destroy();
                                if (parentDoc.body.contains(galleryContainer)) {{
                                    parentDoc.body.removeChild(galleryContainer);
                                }}
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
    
    FIXED_HEIGHT = 505
    components.html(html_content, height=FIXED_HEIGHT, scrolling=False)

# --- Funções para o sistema de sincronização de filtros (removidas ou simplificadas) ---
def setup_sync_system():
    """Configura o sistema de sincronização no lado do Streamlit."""
    if "sync_system" not in st.session_state:
        st.session_state.sync_system = {
            "filters": {},
            "last_update": time.time(),
            "fullscreen_active": False,
            "pending_updates": False,
        }


