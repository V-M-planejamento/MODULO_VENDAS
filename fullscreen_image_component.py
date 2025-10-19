import streamlit as st
import streamlit.components.v1 as components
import base64
import io
import matplotlib.pyplot as plt
from typing import Optional, List, Dict, Any
import json
import re  # Importado para limpar o unique_id
import time

def create_fullscreen_image_viewer(
    figure: Optional[plt.Figure] = None,
    empreendimento: Optional[str] = None,
    ugb: Optional[str] = None,  # <-- O novo argumento para "etiquetar"
    all_filtered_charts_data: Optional[List[Dict[str, Any]]] = None,
    current_chart_index: int = 0,
    ugb_filter_options: Optional[List[str]] = None,
    selected_ugb_filter: Optional[str] = None
) -> None:
    """
    Renderiza um gráfico Matplotlib com um botão de tela cheia e implementa
    todas as funcionalidades: navegação, cópia, download,
    ícone personalizado, ocultamento de interface E FILTRO UGB DINÂMICO.
    
    VERSÃO v2.7 (Filtro por Chave 'ugb'):
    Esta versão filtra os gráficos usando uma chave 'ugb' nos dados,
    em vez de procurar no 'id'.
    
    REQUISITO: Você DEVE passar o argumento 'ugb' (ex: ugb="CA") 
    ou adicionar a chave 'ugb' ao dicionário all_filtered_charts_data
    no seu app.py
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
        
        # Adiciona a chave "ugb" ao gráfico
        charts_for_viewer = [{
            "id": empreendimento or "Gráfico", 
            "src": f"data:image/png;base64,{img_base64_viewer}",
            "ugb": ugb  # A "etiqueta" UGB
        }]
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
    
    unique_id = re.sub(r"[^a-zA-Z0-9_-]", "_", unique_id)
    charts_json = json.dumps(charts_for_viewer)
    ugb_filter_options_json = json.dumps(ugb_filter_options or [])
    selected_ugb_filter_json = json.dumps(selected_ugb_filter or 'all')

    # --- Etapa 3: HTML, CSS e JavaScript ---
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            .gantt-container {{ 
                position: relative; width: 100%; height: 500px; 
                margin: 0 auto; background-color: white; 
                border-radius: 8px; overflow: hidden; 
            }}
            .image-wrapper {{ 
                width: 100%; height: 100%; display: flex; 
                align-items: center; justify-content: center; 
                background-color: white; 
            }}
            .gantt-image {{ 
                max-width: 100%; max-height: 100%; 
                width: auto; height: auto; object-fit: contain; 
            }}
            .action-buttons-container {{
                position: absolute; top: 10px; right: 10px;
                display: flex; flex-direction: column;
                gap: 8px; z-index: 10;
            }}
            .fullscreen-btn {{ 
                background-color: #FFFFFF; color: #31333F; 
                border: 1px solid #E6EAF1; width: 32px; 
                height: 32px; border-radius: 8px; 
                cursor: pointer; font-size: 18px; 
                font-weight: bold; display: flex; 
                align-items: center; justify-content: center; 
                transition: all 0.2s ease; 
                box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
            }}
            .fullscreen-btn:hover {{ 
                border-color: #FF4B4B; color: #FF4B4B; 
                transform: scale(1.05); 
            }}
            .viewer-header-custom {{
                display: none;
            }}
        </style>
    </head>
    <body>
        <div class="gantt-container">
            <div class="image-wrapper">
                <img src="data:image/png;base64,{img_base64_display}" class="gantt-image" alt="Gráfico Gantt">
                <div class="action-buttons-container">
                    <button id="{unique_id}" class="fullscreen-btn" title="Visualizar em tela cheia">⛶</button>
                </div>
                
                <div class="viewer-header-custom">
                    <label for="ugb-select">Filtrar UGB:</label>
                    <select id="ugb-select" class="ugb-select-initial">
                        <option value="all">Todas as UGBs</option>
                    </select>
                </div>
            </div>
        </div>

        <script>
            (function() {{
                // --- 1. Inicialização e Captura de Dados ---
                const parentDoc = window.parent.document;
                const button = document.getElementById("{unique_id}");
                
                const allCharts = {charts_json};
                const ugbFilterOptions = {ugb_filter_options_json};
                const initialSelectedUGB = {selected_ugb_filter_json}; 

                let filteredCharts = []; 
                let currentUGBFilter = initialSelectedUGB; 
                let viewerInstance = null; 
                let galleryContainer = null; 
                let isNavbarVisible = true; 
                
                const ugbSelect = document.getElementById("ugb-select");
                let customHeaderClone = null;
                let clonedSelect = null;

                // --- 2. Funções de Configuração Inicial ---

                function populateUGBFilter() {{
                    if (!ugbSelect) return;
                    ugbSelect.innerHTML = '';
                    const allOption = document.createElement("option");
                    allOption.value = "all";
                    allOption.textContent = "Todas as UGBs";
                    ugbSelect.appendChild(allOption);
                    ugbFilterOptions.forEach(ugb => {{
                        const option = document.createElement("option");
                        option.value = ugb;
                        option.textContent = ugb;
                        ugbSelect.appendChild(option);
                    }});
                }}

                function loadScript(src, callback) {{
                    let script = parentDoc.querySelector(`script[src="${{src}}"]`);
                    if (script) {{ if (callback) callback(); return; }}
                    script = parentDoc.createElement("script"); script.src = src; script.onload = callback; parentDoc.head.appendChild(script);
                }}

                function loadCss(href) {{
                    if (!parentDoc.querySelector(`link[href="${{href}}"]`)) {{
                        const link = parentDoc.createElement("link"); link.rel = "stylesheet"; link.href = href; parentDoc.head.appendChild(link);
                    }}
                }}

                function injectStreamlitHideStyles() {{
                    const styleId = "viewer-hide-streamlit-elements";
                    if (!parentDoc.getElementById(styleId)) {{
                        const style = parentDoc.createElement("style");
                        style.id = styleId;
                        style.innerHTML = `
                            body.viewer-active header[data-testid="stHeader"], body.viewer-active .stDeployButton {{ display: none; }}
                            body.viewer-active section[data-testid="stSidebar"] {{ transform: translateX(-100%); transition: transform 0.3s ease-in-out; }}
                            body.viewer-active .main .block-container {{ max-width: 100% !important; padding-left: 1rem !important; padding-right: 1rem !important; transition: all 0.3s ease-in-out; }}
                        `;
                        parentDoc.head.appendChild(style);
                    }}
                }}

                function injectViewerFilterStyles() {{
                    const customHeaderStyleId = "custom-header-styles";
                    if (!parentDoc.getElementById(customHeaderStyleId)) {{
                        const customHeaderStyle = parentDoc.createElement("style");
                        customHeaderStyle.id = customHeaderStyleId;
                        customHeaderStyle.innerHTML = `
                            .viewer-header-custom-injected {{
                                position: absolute; top: 50px; left: 50%;
                                transform: translateX(-50%);
                                background-color: rgba(0, 0, 0, 0.7); color: white;
                                padding: 8px 12px; box-sizing: border-box;
                                display: flex; justify-content: flex-start; align-items: center;
                                z-index: 99998; border-radius: 8px;
                                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                                font-size: 14px;
                            }}
                            .viewer-header-custom-injected select {{
                                margin-left: 10px; padding: 5px;
                                border-radius: 5px; border: 1px solid #ccc;
                                background-color: #333; color: white;
                            }}
                        `;
                        parentDoc.head.appendChild(customHeaderStyle);
                    }}
                }}

                function injectViewerToolbarStyles() {{
                    const customViewerStyleId = "custom-viewer-styles";
                    if (!parentDoc.getElementById(customViewerStyleId)) {{
                        const customStyle = parentDoc.createElement("style");
                        customStyle.id = customViewerStyleId;
                        customStyle.innerHTML = `
                            .viewer-toolbar > ul {{ background-color: rgba(0, 0, 0, 0.7) !important; border-radius: 12px !important; padding: 4px !important; display: flex !important; justify-content: center !important; align-items: center !important; max-width: fit-content !important; margin: 0 auto !important; }}
                            .viewer-toolbar > ul > li {{ background-color: transparent !important; width: 32px !important; height: 32px !important; border-radius: 8px !important; display: flex !important; align-items: center !important; justify-content: center !important; overflow: hidden !important; box-sizing: border-box !important; padding: 0 !important; margin: 0 !important; vertical-align: middle !important; line-height: 1 !important; }}
                            .viewer-toolbar > ul > li > button {{ width: 100% !important; height: 100% !important; border: none !important; background: transparent !important; color: white !important; display: flex !important; align-items: center !important; justify-content: center !important; padding: 0 !important; margin: 0 !important; font-size: 14px !important; line-height: 1 !important; cursor: pointer !important; }}
                            .viewer-toolbar > ul > li:hover {{ background-color: rgba(255, 255, 255, 0.2) !important; }}
                            .viewer-toolbar svg {{ width: 18px !important; height: 18px !important; fill: white !important; display: block !important; object-fit: contain; }}
                        `;
                        parentDoc.head.appendChild(customStyle);
                    }}
                }}

                // --- 3. Funções Principais (Filtragem e Visualização) ---

                // ########################
                // ## INÍCIO DA LÓGICA (v2.7) ##
                // ########################
                
                /**
                 * Filtra a lista de gráficos. Agora procura pela chave "ugb"
                 * nos dados do gráfico, em vez de no ID.
                 */
                function filterAndRenderCharts(selectedUGB) {{
                    const oldUGBFilter = currentUGBFilter; // Salva o valor anterior
                    let newFilteredCharts; // Lista temporária

                    if (selectedUGB === 'all') {{
                        newFilteredCharts = allCharts;
                    }} else {{
                        newFilteredCharts = allCharts.filter(chart => {{
                            // A NOVA REGRA DE FILTRO (v2.7):
                            // Procura pela chave 'ugb' no objeto
                            // Ex: chart = {{"id": "OLIVEIRAS-01", "ugb": "CA", ...}}
                            return chart.ugb && chart.ugb === selectedUGB;
                        }});
                    }}

                    // --- LÓGICA (v2.6) Mantida: Impede o modal de fechar ---
                    if (viewerInstance) {{ 
                        if (newFilteredCharts.length === 0) {{
                            showToast("Nenhum gráfico encontrado para esta UGB.", 3000);
                            if (clonedSelect) clonedSelect.value = oldUGBFilter;
                            if (ugbSelect) ugbSelect.value = oldUGBFilter;
                            return; 
                        }}
                    }}
                    
                    filteredCharts = newFilteredCharts;
                    currentUGBFilter = selectedUGB; // Atualiza o estado global
                    
                    if (viewerInstance) {{
                        createViewer(isNavbarVisible);
                    }}
                }}
                // ######################
                // ## FIM DA LÓGICA ##
                // ######################


                function createViewer(startNavbar) {{
                    const currentIndex = (viewerInstance && startNavbar === isNavbarVisible) ? viewerInstance.index : 0;

                    if (viewerInstance) {{
                        viewerInstance.destroy();
                        viewerInstance = null; 
                    }}
                    
                    if (galleryContainer && parentDoc.body.contains(galleryContainer)) {{
                        parentDoc.body.removeChild(galleryContainer);
                        galleryContainer = null;
                    }}

                    if (filteredCharts.length === 0) {{
                        showToast("Nenhum gráfico encontrado para a UGB selecionada.", 3000);
                        parentDoc.body.classList.remove('viewer-active'); 
                        return;
                    }}

                    galleryContainer = parentDoc.createElement('ul');
                    galleryContainer.style.display = 'none';
                    filteredCharts.forEach(chartData => {{
                        const listItem = parentDoc.createElement('li');
                        const img = parentDoc.createElement('img');
                        img.src = chartData.src; img.alt = chartData.id;
                        listItem.appendChild(img);
                        galleryContainer.appendChild(listItem);
                    }});
                    parentDoc.body.appendChild(galleryContainer);
                    
                    isNavbarVisible = startNavbar;

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

                            const originalHeader = document.querySelector('.viewer-header-custom');
                            if (originalHeader) {{
                                customHeaderClone = originalHeader.cloneNode(true);
                                customHeaderClone.id = "ugb-select-cloned-container";
                                customHeaderClone.classList.remove('viewer-header-custom');
                                customHeaderClone.classList.add('viewer-header-custom-injected');

                                clonedSelect = customHeaderClone.querySelector('.ugb-select-initial');
                                if (clonedSelect) {{
                                    clonedSelect.id = "ugb-select-cloned";
                                    clonedSelect.value = currentUGBFilter; 
                                    
                                    clonedSelect.addEventListener('change', (event) => {{
                                        const selectedUGB = event.target.value;
                                        ugbSelect.value = selectedUGB; 
                                        
                                        filterAndRenderCharts(selectedUGB); 

                                        if (window.parent.Streamlit) {{
                                            window.parent.Streamlit.setComponentValue("ugb_filter_fullscreen", selectedUGB);
                                        }}
                                    }});
                                }}
                                this.viewer.viewer.appendChild(customHeaderClone);
                                customHeaderClone.style.display = 'flex';
                            }}
                            
                            const toolbar = this.viewer.toolbar;
                            const iconMap = {{
                                'viewer-navbar': '<svg viewBox="0 0 24 24"><path d="M21,2H3A1,1,0,0,0,2,3V21a1,1,0,0,0,1,1H21a1,1,0,0,0,1-1V3A1,1,0,0,0,21,2ZM9,11H5V7H9Zm6,0H11V7h4Zm6,0H17V7h4Zm0,6H17V13h4Zm-6,0H11V13h4ZM9,17H5V13H9Z"/></svg>',
                                'viewer-download': '<svg viewBox="0 0 24 24"><path d="M12,16L6,10H9V4h6V10h3M18,20H6V18H18Z"/></svg>',
                                'viewer-copy': '<svg viewBox="0 0 24 24"><path d="M19,21H8V7H19M19,5H8A2,2,0,0,0,6,7V21a2,2,0,0,0,2,2H19a2,2,0,0,0,2-2V7a2,2,0,0,0-2-2M4,15H2V3A2,2,0,0,1,4,1H15V3H4Z"/></svg>'
                            }};
                            for (const className in iconMap) {{
                                const btn = toolbar.querySelector(`.${{className}}`);
                                if (btn) {{ btn.innerHTML = iconMap[className]; }}
                            }}
                        }},
                        
                        hidden: function () {{
                            parentDoc.body.classList.remove("viewer-active"); 

                            if (customHeaderClone && customHeaderClone.parentNode) {{
                                customHeaderClone.remove();
                            }}
                            customHeaderClone = null;
                            clonedSelect = null;

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

                // --- 4. Funções da Barra de Ferramentas ---

                function getToolbarOptions() {{
                    const showNav = filteredCharts.length > 1; 
                    return {{
                        navbar: {{ 
                            show: showNav ? 1 : 0, size: 'large',
                            title: 'Mostrar/Ocular miniaturas',
                            click: toggleThumbnails
                        }},
                        zoomIn: 1, zoomOut: 1, oneToOne: 1, reset: 1,
                        prev: showNav ? 1 : 0, 
                        play: showNav ? 1 : 0, 
                        next: showNav ? 1 : 0, 
                        rotateLeft: 1, rotateRight: 1,
                        download: {{ 
                            show: true, size: 'large', title: 'Baixar Imagem', 
                            click: downloadImage 
                        }},
                        copy: {{ 
                            show: true, size: 'large', title: 'Copiar Imagem', 
                            click: copyImageToClipboard 
                        }}
                    }};
                }}

                function toggleThumbnails() {{
                    if (!viewerInstance) return;
                    createViewer(!isNavbarVisible);
                }}

                function downloadImage() {{
                    if (!viewerInstance) return;
                    const image = viewerInstance.image;
                    const a = parentDoc.createElement("a");
                    a.href = image.src;
                    a.download = image.alt ? `${{image.alt}}.png` : "gantt-chart.png";
                    parentDoc.body.appendChild(a); a.click(); parentDoc.body.removeChild(a);
                }}

                async function copyImageToClipboard() {{
                    if (!viewerInstance) return;
                    const image = viewerInstance.image;
                    if (!window.parent.navigator.clipboard || !window.parent.isSecureContext) {{
                        showToast("Cópia indisponível (HTTPS necessário)", 3000); return;
                    }}
                    try {{
                        const response = await fetch(image.src);
                        const blob = await response.blob();
                        const clipboardItem = new window.parent.ClipboardItem({{ [blob.type]: blob }});
                        await window.parent.navigator.clipboard.write([clipboardItem]);
                        showToast("Gráfico copiado!");
                    }} catch (err) {{
                        console.error("Falha ao copiar:", err);
                        showToast("Erro ao copiar", 3000);
                    }}
                }}

                function showToast(message, duration = 2000) {{
                    let toast = parentDoc.getElementById("viewer-toast");
                    if (!toast) {{
                        toast = parentDoc.createElement("div");
                        toast.id = "viewer-toast";
                        toast.style.cssText = `
                            visibility: hidden; position: fixed; top: 50%; left: 50%;
                            transform: translate(-50%, -50%);
                            background-color: rgba(0, 0, 0, 0.85); color: white;
                            padding: 12px 20px; border-radius: 8px;
                            z-index: 100000; opacity: 0;
                            transition: opacity 0.3s ease, visibility 0.3s ease;
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                            font-size: 14px; font-weight: 500; line-height: 1.6;
                        `;
                        parentDoc.body.appendChild(toast);
                    }}
                    toast.textContent = message;
                    toast.style.visibility = "visible";
                    toast.style.opacity = "1";
                    setTimeout(() => {{
                        toast.style.opacity = "0";
                        toast.style.visibility = "hidden";
                    }}, duration);
                }}
                
                // --- 5. Execução (Ponto de Entrada) ---
                
                injectStreamlitHideStyles();
                injectViewerFilterStyles();
                injectViewerToolbarStyles();
                
                loadCss("https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.css");
                
                // 1. Popula o filtro e seta o valor inicial
                populateUGBFilter();
                if (ugbSelect) {{
                    ugbSelect.value = initialSelectedUGB;
                }}
                
                // 2. FILTRA a lista pela primeira vez
                // Se você não passar a chave 'ugb' no app.py,
                // `filteredCharts` ficará vazia aqui (se o filtro não for 'all').
                filterAndRenderCharts(initialSelectedUGB); 

                // 3. Adiciona o ouvinte ao filtro "molde"
                if (ugbSelect) {{
                    ugbSelect.addEventListener('change', (event) => {{
                        const selectedUGB = event.target.value;
                        if (clonedSelect) {{ 
                            clonedSelect.value = selectedUGB;
                        }}
                        filterAndRenderCharts(selectedUGB); 
                        if (window.parent.Streamlit) {{ 
                            window.parent.Streamlit.setComponentValue("ugb_filter_fullscreen", selectedUGB);
                        }}
                    }});
                }}

                if (!window.parent.Streamlit) {{
                    loadScript("https://cdn.jsdelivr.net/npm/@streamlit/streamlit-component-lib@1.0.0/dist/streamlit-component-lib.js", () => {{
                        console.log("Streamlit Component Lib loaded.");
                    }});
                }}
                
                loadScript("https://cdnjs.cloudflare.com/ajax/libs/viewerjs/1.11.6/viewer.min.js", function() {{
                    if(button) {{
                        button.addEventListener('click', function() {{
                            // Ao clicar, ele tenta abrir com a lista `filteredCharts`
                            // que foi processada no passo 2.
                            createViewer(filteredCharts.length > 1);
                        }});
                    }} else {{
                        console.error("Botão de tela cheia não encontrado: ", "{unique_id}");
                    }}
                }}); 
            }})();
        </script>
    </body>
    </html>
    """

    # --- Etapa 4: Renderização no Streamlit ---
    components.html(html_content, height=520)