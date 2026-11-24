# Previsão semanal de dengue no Ceará

Versão da apresentação parcial: casos classificados como dengue por município
e semana de notificação. A LSTM resume as semanas anteriores de cada município;
a GCN combina os estados de municípios vizinhos; a saída prevê a semana seguinte.

## Código

| Caminho | Responsabilidade |
|---|---|
| `scripts/` | Baixar e preparar os dados e a malha municipal |
| `dengue_gcn/data.py` | Ler o painel, montar janelas temporais e o grafo |
| `dengue_gcn/models/lstm.py` | Codificar a série de cada município |
| `dengue_gcn/models/gcn.py` | Propagar estados pelos municípios vizinhos |
| `dengue_gcn/models/lstm_gcn.py` | Combinar LSTM, GCN e previsão |
| `dengue_gcn/training.py` | Treinar e calcular métricas |
| `dengue_gcn/grid.py` | Testar configurações e selecionar a melhor |
| `run_grid.py` | Executar o grid search |

## Executar

```bash
./setup.sh
python3 -m venv .venv-train
.venv-train/bin/python -m pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu128
.venv-train/bin/python -m pip install -r requirements-train.txt
.venv-train/bin/python run_grid.py
```

O comando `run_grid.py --dry-run` mostra o número de combinações sem treinar.
O resultado fica em `runs/gcn_grid_v1/`: `summary.json` traz a configuração
selecionada e as métricas, `leaderboard.csv` contém todas as combinações e
`checkpoints/` guarda os pesos. O script retoma configurações já concluídas.

## Grade de hiperparâmetros

| Parâmetro | Valores | Motivo |
|---|---|---|
| Lookback | 4, 8, 16 semanas | Comparar histórico recente de cerca de 1, 2 e 4 meses |
| Estado oculto | 16, 32 | Testar duas capacidades pequenas |
| Camadas LSTM | 1, 2 | Verificar se mais profundidade temporal ajuda |
| Camadas GCN | 1, 2, 4 | Testar propagação por mais vizinhos no grafo |
| Calendário | nenhum; semana; semana e mês | Verificar o valor da sazonalidade conhecida |
| Taxa de aprendizado | 0,001; 0,0003 | Comparar dois passos de otimização |

São 216 combinações, o produto completo desses valores. Os demais parâmetros
ficam fixos: AdamW, Smooth L1, batch size 16, até 20 épocas e parada após 5
épocas sem melhora. Não há escala das contagens. Treino, validação e teste são
cronológicos; a escolha usa apenas a validação. O grafo usa a adjacência da
malha municipal do IBGE de 2025.

Os resultados e limites desta primeira versão estão em
[`docs/apresentacao_parcial.md`](docs/apresentacao_parcial.md).
