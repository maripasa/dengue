# Dengue no Ceará: LSTM + GCN

Projeto de pesquisa para prever os casos de dengue da próxima semana em cada
município do Ceará. O ponto de entrada é o notebook Marimo
[`notebooks/lstm_gcn.py`](notebooks/lstm_gcn.py).

## Abrir o notebook

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/marimo edit notebooks/lstm_gcn.py
```

O notebook mostra os dados e os resultados já existentes ao abrir. Seus botões
preparam ou atualizam os dados e executam ou retomam o grid. Abrir o notebook
não inicia downloads nem treinamento.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `notebooks/lstm_gcn.py` | Pipeline de pesquisa e resultados |
| `prepare_data.py` | Download e preparo do painel semanal e do grafo |
| `dengue_gcn/` | Dados, modelo LSTM + GCN, treino e grid |
| `data/` | Dados brutos e processados locais; fora do Git |
| `runs/` | Resultados e pesos dos experimentos; fora do Git |
| `docs/` | Apresentação, metodologia e fontes de referência |

O grid compara 216 combinações de lookback, tamanho e camadas da LSTM,
camadas da GCN, calendário e taxa de aprendizado. A escolha usa o menor MAE
de validação em uma divisão cronológica. O regime está descrito em
[`docs/grid_test_e_regime.txt`](docs/grid_test_e_regime.txt), e a síntese da
primeira versão em [`docs/apresentacao_parcial.md`](docs/apresentacao_parcial.md).
