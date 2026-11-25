import marimo

__generated_with = "0.26.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import csv
    import json
    import sys
    from pathlib import Path

    import marimo as mo

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    return csv, json, mo, root


@app.cell
def _(mo):
    mo.md("""
    \
    # Dengue no Ceará: LSTM + GCN

    Este caderno é o pipeline da primeira versão do experimento. Ele prepara
    o painel semanal de casos e a vizinhança municipal, mostra os dados,
    executa o grid e apresenta o resultado selecionado pela validação.

    Cada exemplo contém as semanas anteriores dos 184 municípios. A LSTM
    resume o histórico de cada município; a GCN combina os estados dos
    vizinhos; a saída prevê a contagem da semana seguinte.
    """)


@app.cell
def _(mo):
    prepare_button = mo.ui.run_button(label="Baixar e preparar os dados")
    prepare_button
    return (prepare_button,)


@app.cell
def _(mo, prepare_button):
    if prepare_button.value:
        from prepare_data import prepare_data as _prepare_data

        _prepare_data()
        prepared = True
        _message = mo.md("Painel semanal e grafo preparados em `data/processed/`.")
    else:
        prepared = False
        _message = mo.md("Use o botão para baixar ou atualizar os dados. Arquivos já preparados são lidos abaixo.")
    _message
    return (prepared,)


@app.cell
def _(csv, mo, prepared, root):
    _ = prepared
    panel_path = root / "data/processed/dengue_confirmed_weekly/casos_municipio_semana.csv.gz"
    graph_path = root / "data/processed/dengue_v1/arestas_vizinhos.csv"
    if panel_path.exists() and graph_path.exists():
        from dengue_gcn.data import load_weekly_data

        data = load_weekly_data()
        with graph_path.open(newline="", encoding="utf-8") as _stream:
            edges = sum(1 for _ in csv.DictReader(_stream))
        _message = mo.md(
            f"""
            ## Dados disponíveis

            - {len(data.weeks)} semanas: {data.weeks[0]} a {data.weeks[-1]}
            - {len(data.municipalities)} municípios
            - {int(data.counts.sum().item()):,} casos no painel
            - {edges} pares de municípios vizinhos

            As contagens são usadas em valores absolutos, sem divisão pela população.
            """
        )
    else:
        data = None
        _message = mo.md("## Dados disponíveis\n\nO painel ainda não está preparado. Use o botão acima.")
    _message
    return (data,)


@app.cell
def _(mo):
    from dengue_gcn.grid import configurations

    configs = configurations()
    mo.md(
        f"""
        ## Grid de hiperparâmetros

        | Escolha | Valores |
        |---|---|
        | Lookback | 4, 8, 16 semanas |
        | Estado oculto da LSTM | 16, 32 |
        | Camadas LSTM | 1, 2 |
        | Camadas GCN | 1, 2, 4 |
        | Calendário | nenhum; semana; semana e mês |
        | Taxa de aprendizado | 0,001; 0,0003 |

        **{len(configs)} combinações.** Todas usam as mesmas semanas-alvo.
        O treino ocupa as primeiras 70% das semanas, a validação as próximas
        15% e o teste as últimas 15%. As janelas avançam uma semana de cada vez;
        apenas a ordem dos exemplos de treino é embaralhada a cada época.
        """
    )


@app.cell
def _(data, mo):
    grid_button = mo.ui.run_button(
        label="Executar ou retomar o grid",
        disabled=data is None,
    )
    grid_button
    return (grid_button,)


@app.cell
def _(grid_button, mo, root):
    if grid_button.value:
        from dengue_gcn.grid import run_grid

        run_grid(root / "runs/gcn_grid_v1")
        grid_finished = True
        _message = mo.md("Grid concluído. Resultados em `runs/gcn_grid_v1/`.")
    else:
        grid_finished = False
        _message = mo.md("O grid só é executado ao clicar no botão. Uma execução interrompida pode ser retomada.")
    _message
    return (grid_finished,)


@app.cell
def _(grid_finished, json, mo, root):
    _ = grid_finished
    summary_path = root / "runs/gcn_grid_v1/summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        best = summary["best"]
        config = best["config"]
        validation = best["validation"]
        test = best["test"]
        _message = mo.md(
            f"""
            ## Configuração selecionada

            O menor MAE de validação escolheu o lookback de **{config['lookback']}**
            semanas, estado oculto de **{config['hidden']}**, **{config['lstm_layers']}**
            camadas LSTM, **{config['gcn_layers']}** camada(s) GCN, calendário
            **{config['seasonal']}** e taxa de aprendizado **{config['learning_rate']}**.
            Melhor época: **{best['best_epoch']}**.

            | Métrica | Validação | Teste |
            |---|---:|---:|
            | MAE geral | {validation['mae']:.3f} | {test['mae']:.3f} |
            | RMSE geral | {validation['rmse']:.3f} | {test['rmse']:.3f} |
            | MAE com ao menos 1 caso | {validation['mae_nonzero']:.3f} | {test['mae_nonzero']:.3f} |
            | MAE com ao menos 10 casos | {validation['mae_ge10']:.3f} | {test['mae_ge10']:.3f} |

            O teste é avaliado uma vez, após a seleção pela validação.
            """
        )
    else:
        summary = None
        _message = mo.md("## Resultado\n\nExecute o grid para gerar o resumo.")
    _message
    return (summary,)


@app.cell
def _(csv, mo, root, summary):
    if summary is not None:
        leaderboard_path = root / "runs/gcn_grid_v1/leaderboard.csv"
        with leaderboard_path.open(newline="", encoding="utf-8") as _stream:
            top = list(csv.DictReader(_stream))[:10]
        rows = "\n".join(
            f"| {row['rank']} | {row['lookback']} | {row['hidden']} | "
            f"{row['lstm_layers']} | {row['gcn_layers']} | {row['seasonal']} | "
            f"{float(row['validation_mae']):.3f} |"
            for row in top
        )
        _message = mo.md(
            "## Dez melhores configurações na validação\n\n"
            "| Posição | Lookback | Estado | LSTM | GCN | Calendário | MAE |\n"
            "|---:|---:|---:|---:|---:|---|---:|\n"
            + rows
        )
    else:
        _message = mo.md("")
    _message


if __name__ == "__main__":
    app.run()
