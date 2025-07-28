import streamlit as st

def simple_multiselect_dropdown(label, options, key=None, default_selected=None):
    """
    Cria um filtro dropdown personalizado com múltiplas seleções que replica
    o comportamento mostrado na imagem de referência.
    
    Args:
        label (str): Rótulo do filtro
        options (list): Lista de opções disponíveis
        key (str): Chave única para o componente
        default_selected (list): Opções pré-selecionadas (padrão: todas)
    
    Returns:
        list: Lista de opções selecionadas
    """
    
    # CSS personalizado para os filtros
    st.markdown(
        """
        <style>
        div[data-testid="stExpander"] * {
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }
        div[data-testid="stExpander"] {
            background-color: white;
            border-radius: 8px !important;
            margin-bottom: 12px !important;
        }
        .stCheckbox > label {
            font-weight: 400 !important;
            font-size: 14px !important;
        }
        .stCheckbox {
            margin-bottom: 4px !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    if key is None:
        key = f"simple_{hash(label)}"
    
    # Inicializar estado se não existir
    if f"{key}_selected" not in st.session_state:
        st.session_state[f"{key}_selected"] = default_selected.copy() if default_selected is not None else options.copy()
    
    # Contar seleções
    selected_count = len(st.session_state[f"{key}_selected"])
    total_count = len(options)
    all_selected = selected_count == total_count
    
    # Determinar texto do header
    if selected_count == total_count:
        header_text = f"Todos selecionados ({selected_count})"
    elif selected_count == 0:
        header_text = "Nenhum selecionado"
    else:
        header_text = f"{selected_count}"
    
    # Controlar estado de expansão do expander
    expander_key = f"{key}_expanded"
    if expander_key not in st.session_state:
        st.session_state[expander_key] = True  # Inicialmente expandido
    
    # Usar um container para o dropdown para melhor controle
    with st.expander(label=f"{label}: {header_text}", expanded=st.session_state[expander_key]):
        # Checkbox "Select all"
        select_all_key = f"{key}_select_all"
        select_all_value = st.checkbox(
            "Selecionar Todos",
            value=all_selected,
            key=select_all_key
        )
        
        # Lógica para "Selecionar Todos" ou "Desmarcar Todos"
        if select_all_value != all_selected:
            if select_all_value:
                st.session_state[f"{key}_selected"] = options.copy()
            else:
                st.session_state[f"{key}_selected"] = []
            # Não precisa de st.rerun() aqui, o Streamlit já vai re-renderizar
            # ao mudar o session_state

        # Checkboxes individuais
        # Criar uma cópia para iterar e evitar problemas de modificação durante a iteração
        current_selection = st.session_state[f"{key}_selected"].copy()
        new_selection = []

        for option in options:
            is_selected = option in current_selection
            checkbox_key = f"{key}_{option}"
            
            if st.checkbox(
                option,
                value=is_selected,
                key=checkbox_key
            ):
                if option not in new_selection:
                    new_selection.append(option)
            else:
                if option in new_selection:
                    new_selection.remove(option)
        
        # Atualizar o session_state apenas se houver mudança
        if set(new_selection) != set(current_selection):
            st.session_state[f"{key}_selected"] = new_selection

    return st.session_state[f"{key}_selected"]