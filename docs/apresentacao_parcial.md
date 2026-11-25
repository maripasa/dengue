# Apresentação parcial: LSTM + GCN para dengue no Ceará

## Objetivo desta versão

Prever a quantidade de casos classificados como dengue na próxima semana para
cada município do Ceará. Esta versão prevê **casos absolutos**, não incidência
por 100 mil habitantes nem ocupação de leitos. As únicas entradas são o
histórico de casos e, quando habilitado pelo grid, a posição da semana no
calendário.

## Dados

- Sinan/Dengue: casos por município de residência e semana de notificação,
  filtrados por classificação de dengue e critério laboratorial ou
  clínico-epidemiológico.
- Recorte: 2007 em diante, 184 municípios, 1.033 semanas completas.
- Grafo: 469 pares de municípios que compartilham fronteira na malha do IBGE
  de 2025. O mesmo grafo é usado em todas as semanas.
- Não são usados clima, população, mobilidade nem sintomas individuais.

## Modelo

Para cada município, uma LSTM compartilhada lê as últimas `L` semanas e
produz um estado `h`. Uma GCN transmite informação entre municípios vizinhos.
A camada final usa o estado espacial para ajustar a contagem observada na
última semana e prever a próxima. Previsões negativas são truncadas em zero
na avaliação.

```text
casos das últimas L semanas ─→ LSTM ─→ h por município
                                         ↓
                             GCN na malha municipal
                                         ↓
                              casos na próxima semana
```

## Por que essa configuração

O grid apresentado no notebook `notebooks/lstm_gcn.py` testou o produto
completo de seis escolhas:

| Escolha | Valores testados | Pergunta |
|---|---|---|
| Lookback | 4, 8, 16 semanas | Quanto histórico recente ajuda? |
| Estado oculto | 16, 32 | Quanta capacidade temporal é necessária? |
| Camadas LSTM | 1, 2 | Uma segunda camada temporal ajuda? |
| Camadas GCN | 1, 2, 4 | Mais saltos de vizinhança ajudam? |
| Calendário | nenhum; semana; semana e mês | Sazonalidade melhora a previsão? |
| Learning rate | 0,001; 0,0003 | Qual passo otimiza melhor? |

Foram treinadas **216 configurações**, todas com as mesmas semanas-alvo e sem
escala das contagens. A escolha foi feita pelo menor MAE de validação. O teste
foi consultado após essa escolha. O melhor modelo teve:

| Parâmetro | Valor escolhido |
|---|---|
| Lookback | 4 semanas |
| Estado oculto | 32 |
| Camadas LSTM | 2 |
| Camadas GCN | 1 |
| Calendário | seno/cosseno da semana do ano |
| Learning rate | 0,001 |
| Melhor época | 11 |

Treino: 2007-04-29 a 2020-11-08. Validação: 2020-11-15 a 2023-10-29.
Teste: 2023-11-05 a 2026-10-18. O treinamento usa AdamW, Smooth L1,
batch size 16, até 20 épocas e parada após 5 épocas sem melhora na validação.

## Resultado da primeira versão

| Métrica | Validação | Teste |
|---|---:|---:|
| MAE geral | 1,159 | 0,625 |
| RMSE geral | 6,885 | 2,934 |
| MAE quando há ao menos 1 caso | 4,212 | 2,545 |
| MAE quando há ao menos 10 casos | 14,464 | 10,452 |

As métricas são em casos por município-semana. No teste, 79,5% das observações
têm zero casos; por isso o MAE geral deve ser lido junto com os erros nas semanas
com casos. Ainda não há uma previsão direta de leitos, e a precisão durante
semanas com mais casos precisa melhorar.

## Reproduzir

1. Instalar as dependências conforme o `README.md`.
2. Abrir `notebooks/lstm_gcn.py` com Marimo.
3. Usar os botões do notebook para preparar os dados e executar o grid quando necessário.
4. Ler o resumo e a classificação no próprio notebook ou em `runs/gcn_grid_v1/`.
