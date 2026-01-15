# MODULO_VENDAS

Dashboard interativo para visualização comparativa entre prazos previstos e reais de etapas de empreendimentos imobiliários, com gráficos de Gantt e tabelas detalhadas.

## 🎯 Ordenação por Meta de Assinatura

A aplicação utiliza uma lógica centralizada para ordenar empreendimentos baseada na **urgência da meta de assinatura**. 

### 📊 Exemplo Visual

```
GANTT CHART
═══════════════════════════════════════════════════════════════
  Jan/26    Fev/26    Mar/26    Abr/26    Mai/26    Jun/26
─────────────────────────────────────────────────────────────
                            ┊
DM         ████████████     ┊
DOC              ██████████ ┊
LAE                   █████ ┊ █████
MEM                         ┊   ██████████
CONT                        ┊        ███████████
ASS                         ┊              ██████████
M                           ┊                 ███████
PJ                          ┊                      ██████
                            ┊
                        [DM: 15/04/26]
                            ↑
                  LINHA DE META (tracejada verde)
```

### 🛠️ Comportamento e Casos Especiais

A lógica de ordenação e visualização trata automaticamente diversos cenários:

#### 1. Empreendimento sem Etapa 'M'
**Situação**: Novo empreendimento ainda em fase inicial ou sem cadastro da etapa de Demanda Mínima.
**Comportamento**: 
- Assume `pd.Timestamp.max` (data muito distante).
- O empreendimento aparece **no final** de todas as listas e tabelas.

#### 2. Etapa 'M' sem Datas
**Situação**: A etapa existe mas não possui datas previstas ou reais preenchidas.
**Comportamento**: 
- Assume `pd.Timestamp.max`.
- O empreendimento aparece **no final** da ordenação.

#### 3. Meta já Passou
**Situação**: A data de meta (Demanda Mínima) é anterior à data atual.
**Comportamento**:
- ✅ A linha de meta **continua aparecendo** no gráfico (se estiver no período visível).
- ✅ O empreendimento mantém sua posição de **alta prioridade** na ordenação (pois é urgente/atrasado).
- ⚠️ Serve como alerta visual de possível atraso na conquista da meta.

#### 4. Filtragem
**Comportamento**:
- A lista de ordenação se adapta dinamicamente aos filtros aplicados.
- Apenas empreendimentos visíveis na tabela atual são reordenados, garantindo que a sequência (Mais Urgente → Menos Urgente) seja sempre respeitada.
