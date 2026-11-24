# Grid search: previsão semanal de dengue no Ceará

## Dados e alvo

O experimento usa o painel em `data/processed/dengue_confirmed_weekly/`:
184 municípios, 1.033 semanas completas de 2007-01-07 a 2026-10-18.
Cada valor é a quantidade de registros por município de residência e semana
de notificação classificados como dengue, com critério laboratorial ou
clínico-epidemiológico. Entram apenas contagens passadas e, quando selecionadas,
features de calendário. Não há chuva, temperatura, população nem escala.

## Como o treinamento funciona

1. Para prever a semana `t`, a entrada contém as contagens das últimas `L`
   semanas (`t-L` a `t-1`) dos 184 municípios. `L` é testado no grid.
2. A sazonalidade opcional é seno/cosseno da semana do ano e do mês das semanas
   de entrada. Esses valores são conhecidos antes da semana prevista.
3. `node_lstm`: a mesma LSTM codifica cada município isoladamente. Os pesos são
   compartilhados, mas não há troca de informação entre municípios.
4. `joint_lstm`: uma LSTM recebe o vetor de contagens dos 184 municípios a cada
   passo e prevê os 184 valores de uma vez, sem arestas explícitas.
5. `lstm_gcn`: uma LSTM por município produz um estado oculto; de 1 a 4 camadas
   propagam informação pelas arestas de vizinhança do IBGE. Cada camada usa
   adjacência simétrica normalizada com autoarestas, transformação linear,
   ativação ReLU e conexão residual.
6. Todos os modelos aprendem uma correção para a última contagem observada.
   Durante a avaliação, previsões negativas são truncadas em zero.

As semanas-alvo e os limites de corte são idênticos em toda a grade:

| Parte | Semanas-alvo |
|---|---|
| Treino | 2007-04-29 a 2020-11-08 |
| Validação | 2020-11-15 a 2023-10-29 |
| Teste | 2023-11-05 a 2026-10-18 |

O treino usa AdamW (`weight_decay=1e-4`), perda Smooth L1 (`beta=10`), batch
size 16, até 20 épocas e parada antecipada após 5 épocas sem melhora do MAE
de validação. A época 0 representa a previsão por persistência e também é
uma candidata ao melhor checkpoint. Os modelos foram comparados por MAE de
validação; o teste foi calculado somente depois da escolha do melhor de cada
família. Todas as configurações do grid usaram semente 42.

## Grade exaustiva dentro dos intervalos definidos

| Hiperparâmetro | Valores |
|---|---|
| Lookback | 4, 8, 16 semanas |
| Dimensão oculta | 16, 32 |
| Camadas LSTM | 1, 2 |
| Sazonalidade | nenhuma; semana; semana e mês |
| Learning rate | 0,001; 0,0003 |
| Camadas GCN | 1, 2, 4 (somente `lstm_gcn`) |

Foram executadas **360/360 configurações sem erro**: 72 `node_lstm`, 72
`joint_lstm` e 216 `lstm_gcn`. A busca foi dividida entre BL3-L4BRAIN-05 e
BL3-L4BRAIN-07, cada um com uma RTX 5060 Ti. O computador 06 estava offline no
Tailscale. As durações somadas das configurações foram 101 s no 05 e 136 s no
07; uma repetição da busca nas mesmas condições deve levar aproximadamente
**3 a 5 minutos**, incluindo inicialização, sincronização e consolidação.

## Melhores configurações por família

Os valores são casos por município-semana. MAE ≥10 mede somente as observações
em que o valor real da semana foi pelo menos 10 casos; há 709 dessas observações
no teste, em 28.520 observações totais.

| Modelo | Lookback | Sazonalidade | Camadas LSTM | Camadas GCN | MAE validação | MAE teste | RMSE teste | MAE teste ≥10 |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| Persistência (última semana) | 1 | nenhuma | 0 | 0 | 1,222 | 0,665 | 2,991 | **10,396** |
| LSTM por município | 8 | semana + mês | 2 | 0 | **1,156** | 0,631 | **2,929** | 10,499 |
| LSTM conjunta | 16 | semana + mês | 2 | 0 | 1,216 | 0,680 | 2,996 | 10,388 |
| LSTM + GCN | 4 | semana | 2 | 1 | 1,159 | **0,625** | 2,934 | 10,452 |

Todos os melhores modelos usaram dimensão oculta 32 e learning rate 0,001.
A LSTM por município foi escolhida pelo menor MAE de validação. A GCN teve o
menor MAE geral no teste, mas a diferença frente à LSTM por município é de
aproximadamente 0,006 caso por município-semana. Nenhum dos dois superou a
persistência no subconjunto ≥10, que é mais próximo do interesse em surtos.

## Repetição com cinco sementes

As arquiteturas acima foram fixadas pela validação do grid e repetidas com
sementes 42, 43, 44, 45 e 46. A semente não foi usada para escolher uma nova
arquitetura.

| Modelo | MAE médio no teste | Desvio padrão |
|---|---:|---:|
| LSTM por município | 0,647 | 0,017 |
| LSTM conjunta | 0,680 | 0,015 |
| LSTM + GCN | **0,641** | 0,016 |

A diferença média entre GCN e LSTM por município (0,006) é menor que a
variação entre sementes. Ainda não há evidência forte de ganho consistente da
GCN. Estes resultados são retrospectivos, usam uma divisão cronológica e um
grafo municipal estático da malha de 2025. O alvo é **casos classificados como
dengue**, não internações ou leitos ocupados.

Resultados completos: `runs/grid_v1/summary.json`, `leaderboard.csv`,
`repeats_summary.json`, `results_shard0.jsonl`, `results_shard1.jsonl` e os
checkpoints dos 360 treinos.
