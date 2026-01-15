# MODULO_VENDAS

Dashboard interativo para visualização comparativa entre prazos previstos e reais de etapas de empreendimentos imobiliários, com gráficos de Gantt e tabelas detalhadas.

## 🎯 Ordenação por Meta de Assinatura

A aplicação utiliza uma lógica centralizada para ordenar empreendimentos baseada na **urgência da meta de assinatura**. Essa ordenação é consistente em todas as visualizações: Gráficos de Gantt, Filtros e Tabelas.

### Comportamento

1.  **Definição da Meta**: A data de meta é extraída da etapa **"DEMANDA MÍNIMA"** (ou etapa 'M').
2.  **Prioridade de Data**:
    *   Tenta usar `Início Previsto`
    *   Se não houver, usa `Término Previsto`
    *   Fallback para datas reais se necessário
3.  **Critério de Ordenação**:
    *   **Do Mais Antigo para o Mais Novo**: Empreendimentos com metas mais antigas (mais urgentes) aparecem no topo.
    *   **Sem Meta**: Empreendimentos sem data de meta definida são posicionados ao final da lista.
4.  **Consistência**: A mesma ordem é garantida no Filtro de Projetos, no Gantt Consolidado, na Visão Detalhada e no Tabelão Horizontal.

### Exemplo Visual

Imagine a seguinte lista de empreendimentos ordenados por prioridade:

```text
1. AMOREIRAS-01      (Meta: 01/01/2024)  [↑ Mais Urgente]
2. AMOREIRAS-02      (Meta: 15/01/2024)
3. OLIVEIRAS-01      (Meta: 10/02/2024)
4. JARDIM DA SERRA   (Meta: 05/03/2024)
...
9. EMPREENDIMENTO X  (Sem Meta definida) [↓ Menor Prioridade]
```

Nas tabelas (Visão Detalhada e Tabelão), os empreendimentos serão listados exatamente nesta sequência, permitindo que a equipe foque nos prazos mais críticos primeiro.

