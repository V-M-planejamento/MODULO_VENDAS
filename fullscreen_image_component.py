import streamlit as st
import streamlit.components.v1 as components
import base64
import io
import matplotlib.pyplot as plt
from typing import Optional, List, Dict, Any
import json
import time

def create_fullscreen_image_viewer(
    figure: Optional[plt.Figure] = None,
    empreendimento: Optional[str] = None,
    all_filtered_charts_data: Optional[List[Dict[str, Any]]] = None,
    current_chart_index: int = 0
) -> None:
    """
    Renderiza um gráfico Matplotlib com um botão de tela cheia e implementa
    todas as funcionalidades discutidas: navegação, cópia, download,
    ícone personalizado e ocultamento de interface. (Versão final corrigida).
    """
    # --- Etapas 1 e 2: Preparação da Imagem ---
    img_base64_display = None
    unique_id = None

    if figure is not None:
        img_buffer_display = io.BytesIO()
        figure.savefig(img_buffer_display, format="png", dpi=150, bbox_inches="tight")
        img_base64_display = base64.b64encode(img_buffer_display.getvalue()).decode("utf-8")

        img_buffer_viewer = io.BytesIO()
        figure.savefig(img_buffer_viewer, format="png", dpi=300, bbox_inches="tight", facecolor="white")
        img_base64_viewer = base64.b64encode(img_buffer_viewer.getvalue()).decode("utf-8")
        
        unique_id = f"viewer-btn-{empreendimento if empreendimento else hash(img_base64_display)}"
        plt.close(figure)
        
        charts_for_viewer = [{"id": empreendimento or "Gráfico", "src": f"data:image/png;base64,{img_base64_viewer}"}]
        viewer_initial_index = 0

    elif all_filtered_charts_data and current_chart_index < len(all_filtered_charts_data):
        chart_data = all_filtered_charts_data[current_chart_index]
        img_base64_display = chart_data["src"].split(",")[1]
        unique_id = f"viewer-btn-{chart_data['id']}"
        
        charts_for_viewer = all_filtered_charts_data
        viewer_initial_index = current_chart_index
    else:
        st.error("Nenhum gráfico ou dados de imagem fornecidos para exibição.")
        return

    if not unique_id:
        unique_id = f"viewer-btn-{int(time.time())}"

    charts_json = json.dumps(charts_for_viewer)

    # --- Etapa 3: HTML, CSS e JavaScript ---
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
                const button = document.getElementById("{unique_id}");
                const allCharts = {charts_json};
                const initialViewIndex = {viewer_initial_index};

                const styleId = 'viewer-hide-streamlit-elements';
                if (!parentDoc.getElementById(styleId)) {{
                    const style = parentDoc.createElement('style');
                    style.id = styleId;
                    style.innerHTML = `
                        body.viewer-active header[data-testid="stHeader"], body.viewer-active .stDeployButton {{ display: none; }}
                        body.viewer-active section[data-testid="stSidebar"] {{ transform: translateX(-100%); transition: transform 0.3s ease-in-out; }}
                        body.viewer-active .main .block-container {{ max-width: 100% !important; padding-left: 1rem !important; padding-right: 1rem !important; transition: all 0.3s ease-in-out; }}
                    `;
                    parentDoc.head.appendChild(style);
                }}

                function loadScript(src, callback) {{
                    let script = parentDoc.querySelector(`script[src="${{src}}"]`);
                    if (script) {{ if (callback) callback(); return; }}
                    script = parentDoc.createElement('script'); script.src = src; script.onload = callback; parentDoc.head.appendChild(script);
                }}
                
                function loadCss(href) {{
                    if (!parentDoc.querySelector(`link[href="${{href}}"]`)) {{
                        const link = parentDoc.createElement('link'); link.rel = 'stylesheet'; link.href = href; parentDoc.head.appendChild(link);
                    }}
                }}

                loadCss('https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.css' );
                
                const customViewerStyleId = 'custom-viewer-styles';
                if (!parentDoc.getElementById(customViewerStyleId)) {{
                    const customStyle = parentDoc.createElement('style');
                    customStyle.id = customViewerStyleId;
                    customStyle.innerHTML = `
                        .viewer-toolbar > ul {{ background-color: rgba(0, 0, 0, 0.7) !important; border-radius: 12px !important; padding: 4px !important; display: flex !important; justify-content: center !important; max-width: fit-content !important; margin: 0 auto !important; }}
                        .viewer-toolbar > ul > li {{ background-color: transparent !important; width: 32px !important; height: 32px !important; border-radius: 8px !important; display: flex !important; align-items: center !important; justify-content: center !important; overflow: hidden; box-sizing: border-box; vertical-align: middle; }}
                        .viewer-toolbar > ul > li:hover {{ background-color: rgba(255, 255, 255, 0.2) !important; }}
                        .viewer-download::before {{ content: '⬇'; font-size: 16px; color: white; }}
                        .viewer-copy {{ background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='white' viewBox='0 0 16 16'%3E%3Cpath d='M4 1.5H3a2 2 0 0 0-2 2V14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V3.5a2 2 0 0 0-2-2h-1v1h1a1 1 0 0 1 1 1V14a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3.5a1 1 0 0 1 1-1h1v-1z'/%3E%3Cpath d='M9.5 1a.5.5 0 0 1 .5.5v1a.5.5 0 0 1-.5.5h-3a.5.5 0 0 1-.5-.5v-1a.5.5 0 0 1 .5-.5h3zM9 2H7v.5a.5.5 0 0 0 .5.5h1a.5.5 0 0 0 .5-.5V2z'/%3E%3C/svg%3E"   ); background-repeat: no-repeat; background-position: center; background-size: 16px 16px; }}
                        .viewer-toggleThumbnails svg {{ width: 20px; height: 20px; fill: white; }}
                    `;
                    parentDoc.head.appendChild(customStyle);
                }}

                // ==================================================================
                // INÍCIO DA SEÇÃO CORRIGIDA
                // ==================================================================
                let viewerInstance = null;
                let isNavbarVisible = allCharts.length > 1;
                let galleryContainer = null;

                function createViewer(startNavbar) {{
                    const currentIndex = viewerInstance ? viewerInstance.index : initialViewIndex;

                    if (viewerInstance) {{
                        viewerInstance.destroy();
                    }}
                    
                    if (!galleryContainer) {{
                        galleryContainer = parentDoc.createElement('ul');
                        galleryContainer.style.display = 'none';
                        allCharts.forEach(chartData => {{
                            const listItem = parentDoc.createElement('li');
                            const img = parentDoc.createElement('img');
                            img.src = chartData.src; img.alt = chartData.id;
                            listItem.appendChild(img);
                            galleryContainer.appendChild(listItem);
                        }});
                        parentDoc.body.appendChild(galleryContainer);
                    }}

                    const viewer = new parent.Viewer(galleryContainer, {{
                        inline: false,
                        navbar: startNavbar,
                        button: true,
                        title: (image) => image.alt,
                        fullscreen: true,
                        keyboard: true,
                        zIndex: 99999,
                        initialViewIndex: currentIndex,
                        toolbar: getToolbarOptions(),
                        ready: function () {{
                            viewerInstance = this.viewer;
                            parentDoc.body.classList.add('viewer-active');
                        }},
                        hidden: function () {{
                            parentDoc.body.classList.remove('viewer-active');
                            if (viewerInstance) {{
                                viewerInstance.destroy();
                                viewerInstance = null;
                            }}
                            if (galleryContainer && parentDoc.body.contains(galleryContainer)) {{
                                parentDoc.body.removeChild(galleryContainer);
                                galleryContainer = null;
                            }}
                        }}
                    }});
                    viewer.show();
                }}

                function toggleThumbnails() {{
                    if (!viewerInstance) return;
                    isNavbarVisible = !isNavbarVisible;
                    createViewer(isNavbarVisible);
                }}
                
                async function copyImageToClipboard() {{
                    if (!viewerInstance) return;
                    const viewer = viewerInstance; // Usa a instância ativa
                    const image = viewer.image;
                    const buttonElement = viewer.toolbar.querySelector('.viewer-copy');
                    const originalTitle = buttonElement.getAttribute('data-original-title');

                    function setTooltip(message, duration = 2000) {{
                        buttonElement.setAttribute('data-original-title', message);
                        viewer.tooltip();
                        if (duration > 0) setTimeout(() => {{
                            buttonElement.setAttribute('data-original-title', originalTitle);
                            viewer.tooltip();
                        }}, duration);
                    }}

                    if (!window.parent.navigator.clipboard || !window.parent.isSecureContext) {{
                        setTooltip("Cópia indisponível (HTTPS necessário)", 3000); return;
                    }}
                    try {{
                        const response = await fetch(image.src);
                        const blob = await response.blob();
                        const clipboardItem = new window.parent.ClipboardItem({{ [blob.type]: blob }});
                        await window.parent.navigator.clipboard.write([clipboardItem]);
                        setTooltip("Copiado!");
                    }} catch (err) {{
                        console.error('Falha ao copiar:', err);
                        setTooltip("Erro ao copiar", 3000);
                    }}
                }}

                function downloadImage() {{
                    if (!viewerInstance) return;
                    const viewer = viewerInstance; // Usa a instância ativa
                    const image = viewer.image;
                    const a = parentDoc.createElement('a');
                    a.href = image.src;
                    a.download = image.alt ? `${{image.alt}}.png` : 'gantt-chart.png';
                    parentDoc.body.appendChild(a); a.click(); parentDoc.body.removeChild(a);
                }}

                function getToolbarOptions() {{
                    return {{
                        toggleThumbnails: {{
                            show: allCharts.length > 1 ? 1 : 0,
                            size: 'large',
                            title: 'Mostrar/Ocultar miniaturas',
                            click: toggleThumbnails,
                            render: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M21,2H3A1,1,0,0,0,2,3V21a1,1,0,0,0,1,1H21a1,1,0,0,0,1-1V3A1,1,0,0,0,21,2ZM9,11H5V7H9Zm6,0H11V7h4Zm6,0H17V7h4Zm0,6H17V13h4Zm-6,0H11V13h4ZM9,17H5V13H9Z"/></svg>`
                        }},
                        zoomIn: 1, zoomOut: 1, oneToOne: 1, reset: 1,
                        prev: allCharts.length > 1 ? 1 : 0,
                        play: allCharts.length > 1 ? 1 : 0,
                        next: allCharts.length > 1 ? 1 : 0,
                        rotateLeft: 1, rotateRight: 1,
                        download: {{ show: true, size: 'large', title: 'Baixar Imagem', click: downloadImage }},
                        copy: {{ show: true, size: 'large', title: 'Copiar Imagem', click: copyImageToClipboard }}
                    }};
                }}
                // ==================================================================
                // FIM DA SEÇÃO CORRIGIDA
                // ==================================================================

                button.addEventListener('click', function( ) {{
                    loadScript('https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.js', function( ) {{
                        isNavbarVisible = allCharts.length > 1;
                        createViewer(isNavbarVisible);
                    }});
                }});
            }})();
        </script>
    </body>
    </html>
    """
    
    FIXED_HEIGHT = 505
    components.html(html_content, height=FIXED_HEIGHT, scrolling=False)
