from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd

IBGE_CE_URL = (
    "https://servicodados.ibge.gov.br/"
    "api/v1/localidades/estados/23/municipios"
)

COLUNAS_POSSIVEIS = [
    "SG_UF", "ID_MN_RESI", "DT_SIN_PRI", "DT_NOTIFIC", "SEM_PRI",
    "NU_ANO", "ANO", "CLASSI_FIN", "CON_CLASSI", "CRITERIO",
    "CON_CRITER", "ID_AGRAVO", "NDUPLIC_N", "NDUPLIC", "TPAUTOCTO",
]

COLUNAS_SAIDA = [
    "ano_arquivo", "layout_origem", "SG_UF", "codigo_municipio_original",
    "municipio_ibge", "DT_SIN_PRI", "DT_NOTIFIC", "data_sintomas",
    "data_notificacao", "dias_sintomas_ate_notificacao", "SEM_PRI",
    "semana_original", "ano_epidemiologico", "semana_epidemiologica",
    "ano_semana", "campo_classificacao", "classificacao_original",
    "criterio_original", "data_sintomas_ausente", "data_notificacao_ausente",
    "data_sintomas_posterior_notificacao", "intervalo_superior_365",
    "ano_sintomas_anterior_ano_arquivo", "semana_original_invalida",
    "divergencia_semana", "municipio_invalido",
]


def obter_ano_arquivo(caminho: Path) -> Optional[int]:
    match = re.search(r"DENGBR(\d{2})$", caminho.stem.upper())
    return 2000 + int(match.group(1)) if match else None


def normalizar_uf(valor: object) -> str:
    if pd.isna(valor):
        return ""
    texto = str(valor).strip().upper()
    return "CE" if texto in {"CE", "23", "23.0"} else texto


def carregar_municipios_ibge(cache_path: Path) -> tuple[set[str], dict[str, str]]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        municipios = pd.read_csv(cache_path, dtype=str)
    else:
        req = urllib.request.Request(
            IBGE_CE_URL,
            headers={"User-Agent": "Mozilla/5.0 dengue-dataset-preparation"},
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            dados = json.loads(response.read().decode("utf-8"))
        municipios = pd.DataFrame({
            "codigo_ibge": [str(x["id"]) for x in dados],
            "municipio": [x["nome"] for x in dados],
        })
        municipios.to_csv(cache_path, index=False, encoding="utf-8")

    municipios["codigo_ibge"] = (
        municipios["codigo_ibge"].astype(str).str.replace(r"\.0$", "", regex=True)
    )
    validos = set(municipios["codigo_ibge"])
    mapa = {codigo[:6]: codigo for codigo in validos}
    if len(validos) != 184 or len(mapa) != 184:
        raise RuntimeError("Cache do IBGE não contém 184 códigos municipais únicos do Ceará.")
    return validos, mapa


def normalizar_codigo_municipio(valor: object, validos: set[str], mapa: dict[str, str]):
    if pd.isna(valor):
        return pd.NA
    texto = str(valor).strip()
    if not texto:
        return pd.NA
    try:
        numero = float(texto)
        if not numero.is_integer():
            return pd.NA
        codigo = str(int(numero))
    except (ValueError, TypeError, OverflowError):
        return pd.NA
    if len(codigo) == 7:
        return codigo if codigo in validos else pd.NA
    if len(codigo) == 6:
        return mapa.get(codigo, pd.NA)
    return pd.NA


def converter_data(coluna: pd.Series) -> pd.Series:
    texto = coluna.astype("string").str.strip()
    texto = texto.replace({"": pd.NA, "NA": pd.NA, "NaN": pd.NA, "nan": pd.NA})
    return pd.to_datetime(texto, format="%Y-%m-%d", errors="coerce")


def calcular_semana_epidemiologica(datas: pd.Series) -> pd.DataFrame:
    dia = (datas.dt.day_of_week + 1) % 7  # domingo = 0
    inicio = datas - pd.to_timedelta(dia, unit="D")
    quinta = datas + pd.to_timedelta(3 - dia, unit="D")
    ano = quinta.dt.year
    quatro_jan = pd.to_datetime(
        ano.astype("Int64").astype("string") + "-01-04", errors="coerce"
    )
    dia_quatro_jan = (quatro_jan.dt.day_of_week + 1) % 7
    inicio_primeira = quatro_jan - pd.to_timedelta(dia_quatro_jan, unit="D")
    semana = ((inicio - inicio_primeira).dt.days // 7) + 1

    resultado = pd.DataFrame(index=datas.index)
    resultado["ano_epidemiologico"] = ano.astype("Int64")
    resultado["semana_epidemiologica"] = semana.astype("Int64")
    resultado["ano_semana"] = (
        resultado["ano_epidemiologico"].astype("string")
        + resultado["semana_epidemiologica"].astype("string").str.zfill(2)
    )
    resultado.loc[datas.isna(), "ano_semana"] = pd.NA
    return resultado

def normalizar_semana_original(
    coluna: pd.Series,
    ano_arquivo: int
) -> tuple[pd.Series, pd.Series]:

    texto = (
        coluna.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace(r"\D", "", regex=True)
    )

    formato = texto.str.fullmatch(r"\d{6}", na=False)

    if ano_arquivo <= 2006:
        semana = pd.to_numeric(texto.str[:2], errors="coerce")
        ano = pd.to_numeric(texto.str[2:6], errors="coerce")
    else:
        ano = pd.to_numeric(texto.str[:4], errors="coerce")
        semana = pd.to_numeric(texto.str[4:6], errors="coerce")

    valida = (
        formato
        & semana.between(1, 53)
        & ano.between(1900, 2100)
    )

    normalizada = (
        ano.astype("Int64").astype("string")
        + semana.astype("Int64").astype("string").str.zfill(2)
    )

    return normalizada.where(valida, pd.NA), valida

def processar_lote(
    bruto: pd.DataFrame,
    ano_arquivo: int,
    validos: set[str],
    mapa: dict[str, str],
) -> pd.DataFrame:
    bruto.columns = [str(c).strip().upper() for c in bruto.columns]
    if bruto.empty:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    uf = bruto["SG_UF"].map(normalizar_uf)
    df = bruto.loc[uf.eq("CE")].copy()
    if df.empty:
        return pd.DataFrame(columns=COLUNAS_SAIDA)

    df["ano_arquivo"] = ano_arquivo
    df["layout_origem"] = (
        "historico_2000_2006" if ano_arquivo <= 2006 else "novo_2007_2026"
    )
    df["codigo_municipio_original"] = df["ID_MN_RESI"].astype("string").str.strip()
    df["municipio_ibge"] = df["ID_MN_RESI"].map(
        lambda x: normalizar_codigo_municipio(x, validos, mapa)
    )

    df["data_sintomas"] = converter_data(
        df["DT_SIN_PRI"] if "DT_SIN_PRI" in df else pd.Series(pd.NA, index=df.index)
    )
    df["data_notificacao"] = converter_data(df["DT_NOTIFIC"])
    df["dias_sintomas_ate_notificacao"] = (
        df["data_notificacao"] - df["data_sintomas"]
    ).dt.days

    semanas = calcular_semana_epidemiologica(df["data_sintomas"])
    df["ano_epidemiologico"] = semanas["ano_epidemiologico"]
    df["semana_epidemiologica"] = semanas["semana_epidemiologica"]
    df["ano_semana"] = semanas["ano_semana"]

    if "SEM_PRI" in df:
        sem, sem_valida = normalizar_semana_original(df["SEM_PRI"], ano_arquivo)
        df["SEM_PRI"] = df["SEM_PRI"].astype("string")
    else:
        sem = pd.Series(pd.NA, index=df.index, dtype="string")
        sem_valida = pd.Series(False, index=df.index)
        df["SEM_PRI"] = pd.NA
    df["semana_original"] = sem
    df["divergencia_semana"] = (
        sem_valida & df["ano_semana"].notna() & sem.ne(df["ano_semana"])
    )

    if "CLASSI_FIN" in df:
        df["campo_classificacao"] = "CLASSI_FIN"
        df["classificacao_original"] = df["CLASSI_FIN"].astype("string").str.strip()
    elif "CON_CLASSI" in df:
        df["campo_classificacao"] = "CON_CLASSI"
        df["classificacao_original"] = df["CON_CLASSI"].astype("string").str.strip()
    else:
        df["campo_classificacao"] = pd.NA
        df["classificacao_original"] = pd.NA

    if "CRITERIO" in df:
        df["criterio_original"] = df["CRITERIO"].astype("string").str.strip()
    elif "CON_CRITER" in df:
        df["criterio_original"] = df["CON_CRITER"].astype("string").str.strip()
    else:
        df["criterio_original"] = pd.NA

    df["data_sintomas_ausente"] = df["data_sintomas"].isna()
    df["data_notificacao_ausente"] = df["data_notificacao"].isna()
    df["data_sintomas_posterior_notificacao"] = df["dias_sintomas_ate_notificacao"] < 0
    df["intervalo_superior_365"] = df["dias_sintomas_ate_notificacao"] > 365
    df["ano_sintomas_anterior_ano_arquivo"] = df["data_sintomas"].dt.year < ano_arquivo
    df["municipio_invalido"] = df["municipio_ibge"].isna()
    df["semana_original_invalida"] = (
        df["SEM_PRI"].notna() & ~sem_valida
    )

    for coluna in COLUNAS_SAIDA:
        if coluna not in df:
            df[coluna] = pd.NA
    return df[COLUNAS_SAIDA].copy()


def acumular_qualidade(resumo: dict, municipios_por_ano: dict, lote: pd.DataFrame, ano: int):
    chaves_bool = [
        "data_sintomas_ausente", "data_notificacao_ausente",
        "data_sintomas_posterior_notificacao", "intervalo_superior_365",
        "ano_sintomas_anterior_ano_arquivo", "semana_original_invalida",
        "divergencia_semana", "municipio_invalido",
    ]
    item = resumo[ano]
    item["total_residentes_ceara"] += len(lote)
    for coluna in chaves_bool:
        item[coluna] += int(lote[coluna].sum())
    municipios_por_ano[ano].update(lote["municipio_ibge"].dropna().astype(str).unique())


def acumular_agregacoes(
    lote: pd.DataFrame,
    serie_contagem: Counter,
    classificacao_contagem: Counter,
):
    base = lote.loc[lote["municipio_ibge"].notna() & lote["ano_semana"].notna()].copy()
    if base.empty:
        return

    dias = base["dias_sintomas_ate_notificacao"]
    base["intervalo_aceitavel"] = dias.between(0, 365).fillna(False)
    base["intervalo_suspeito"] = (dias < 0) | (dias > 365)
    base["intervalo_indefinido"] = dias.isna()

    chaves = ["municipio_ibge", "ano_epidemiologico", "semana_epidemiologica", "ano_semana"]
    agrupado = base.groupby(chaves, dropna=False).agg(
        registros_total=("ano_semana", "size"),
        registros_intervalo_0_365=("intervalo_aceitavel", "sum"),
        registros_intervalo_suspeito=("intervalo_suspeito", "sum"),
        registros_intervalo_indefinido=("intervalo_indefinido", "sum"),
    )
    for chave, linha in agrupado.iterrows():
        acumulado = serie_contagem[tuple(chave)]
        for i, coluna in enumerate(agrupado.columns):
            acumulado[i] += int(linha[coluna])

    base["classificacao_agrupamento"] = base["classificacao_original"].fillna("AUSENTE")
    chaves_class = chaves + ["campo_classificacao", "classificacao_agrupamento"]
    contagens = base.groupby(chaves_class, dropna=False).size()
    for chave, quantidade in contagens.items():
        classificacao_contagem[tuple(chave)] += int(quantidade)


def salvar_resultados(
    output: Path,
    resumo: dict,
    municipios_por_ano: dict,
    serie_contagem: Counter,
    classificacao_contagem: Counter,
):
    qualidade_linhas = []
    nomes = {
        "data_sintomas_ausente": "datas_sintomas_ausentes",
        "data_notificacao_ausente": "datas_notificacao_ausentes",
        "data_sintomas_posterior_notificacao": "sintomas_posteriores_notificacao",
        "intervalo_superior_365": "intervalos_superiores_365_dias",
        "ano_sintomas_anterior_ano_arquivo": "sintomas_anteriores_ano_arquivo",
        "semana_original_invalida": "semanas_originais_invalidas",
        "divergencia_semana": "divergencias_semana",
        "municipio_invalido": "registros_sem_municipio_valido",
    }
    for ano in sorted(resumo):
        linha = {"ano_arquivo": ano, "total_residentes_ceara": resumo[ano]["total_residentes_ceara"]}
        linha.update({nomes[k]: resumo[ano][k] for k in nomes})
        linha["municipios_ibge_presentes"] = len(municipios_por_ano[ano])
        qualidade_linhas.append(linha)
    pd.DataFrame(qualidade_linhas).to_csv(
        output / "qualidade_anual.csv", index=False, encoding="utf-8-sig"
    )

    serie_linhas = []
    for chave, valores in serie_contagem.items():
        municipio, ano_epi, semana_epi, ano_semana = chave
        serie_linhas.append({
            "municipio_ibge": municipio,
            "ano_epidemiologico": ano_epi,
            "semana_epidemiologica": semana_epi,
            "ano_semana": ano_semana,
            "registros_total": valores[0],
            "registros_intervalo_0_365": valores[1],
            "registros_intervalo_suspeito": valores[2],
            "registros_intervalo_indefinido": valores[3],
        })
    serie_df = pd.DataFrame(serie_linhas)
    if not serie_df.empty:
        serie_df = serie_df.sort_values(["municipio_ibge", "ano_semana"])
    serie_df.to_csv(output / "serie_semanal.csv", index=False, encoding="utf-8-sig")

    class_linhas = []
    for chave, quantidade in classificacao_contagem.items():
        municipio, ano_epi, semana_epi, ano_semana, campo, classificacao = chave
        class_linhas.append({
            "municipio_ibge": municipio,
            "ano_epidemiologico": ano_epi,
            "semana_epidemiologica": semana_epi,
            "ano_semana": ano_semana,
            "campo_classificacao": campo,
            "classificacao_original": classificacao,
            "registros": quantidade,
        })
    class_df = pd.DataFrame(class_linhas)
    if not class_df.empty:
        class_df = class_df.sort_values(["municipio_ibge", "ano_semana", "campo_classificacao", "classificacao_original"])
    class_df.to_csv(
        output / "serie_semanal_classificacao.csv", index=False, encoding="utf-8-sig"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepara os arquivos SINAN de dengue no Ceará em lotes.")
    parser.add_argument("--input", type=Path, default=Path("data/raw/dengue"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/dengue"))
    parser.add_argument("--ibge-cache", type=Path, default=Path("data/interim/municipios_ceara_ibge.csv"))
    parser.add_argument("--chunksize", type=int, default=20_000,
                        help="Linhas lidas por lote (padrão: 20000). Reduza para 10000 ou 5000 se faltar RAM.")
    args = parser.parse_args()

    if args.chunksize < 1:
        parser.error("--chunksize precisa ser maior que zero")
    if not args.input.exists():
        print(f"ERRO: diretório não encontrado: {args.input}", file=sys.stderr)
        return 1

    arquivos = sorted(
        [p for p in args.input.glob("DENGBR*.csv") if obter_ano_arquivo(p) is not None],
        key=lambda p: obter_ano_arquivo(p),
    )
    if not arquivos:
        print(f"ERRO: nenhum DENGBRxx.csv encontrado em {args.input}", file=sys.stderr)
        return 1

    args.output.mkdir(parents=True, exist_ok=True)
    try:
        validos, mapa = carregar_municipios_ibge(args.ibge_cache)
    except Exception as exc:
        print(f"ERRO ao carregar municípios do IBGE: {exc}", file=sys.stderr)
        return 1

    caminho_registros = args.output / "registros_ceara.csv"
    if caminho_registros.exists():
        caminho_registros.unlink()

    resumo = defaultdict(lambda: Counter())
    municipios_por_ano = defaultdict(set)
    serie_contagem = defaultdict(lambda: [0, 0, 0, 0])
    classificacao_contagem = Counter()
    total_geral = 0
    primeiro_lote_saida = True

    for caminho in arquivos:
        ano = obter_ano_arquivo(caminho)
        print(f"[{ano}] {caminho.name}: iniciando leitura em lotes de {args.chunksize:,} linhas", flush=True)
        cabecalho = pd.read_csv(caminho, nrows=0, encoding="latin1")
        mapa_nomes = {str(c).strip().upper(): c for c in cabecalho.columns}
        obrigatorias = {"SG_UF", "ID_MN_RESI", "DT_NOTIFIC"}
        faltantes = obrigatorias - set(mapa_nomes)
        if faltantes:
            print(f"ERRO em {caminho.name}: colunas ausentes {sorted(faltantes)}", file=sys.stderr)
            return 1
        selecionadas = [mapa_nomes[c] for c in COLUNAS_POSSIVEIS if c in mapa_nomes]

        linhas_arquivo = 0
        try:
            leitor = pd.read_csv(
                caminho, usecols=selecionadas, dtype=str, encoding="latin1",
                low_memory=False, chunksize=args.chunksize,
            )
            for numero_lote, bruto in enumerate(leitor, start=1):
                lote = processar_lote(bruto, ano, validos, mapa)
                if lote.empty:
                    continue

                lote.to_csv(
                    caminho_registros,
                    mode="a",
                    header=primeiro_lote_saida,
                    index=False,
                    encoding="utf-8-sig" if primeiro_lote_saida else "utf-8",
                )
                primeiro_lote_saida = False

                acumular_qualidade(resumo, municipios_por_ano, lote, ano)
                acumular_agregacoes(lote, serie_contagem, classificacao_contagem)
                linhas_arquivo += len(lote)
                total_geral += len(lote)
                print(
                    f"    lote {numero_lote}: {len(lote):,} residentes no CE "
                    f"(acumulado do ano: {linhas_arquivo:,})",
                    flush=True,
                )
        except Exception as exc:
            print(f"ERRO processando {caminho.name}: {exc}", file=sys.stderr)
            return 1

        print(f"[{ano}] concluído: {linhas_arquivo:,} residentes no Ceará", flush=True)

    salvar_resultados(args.output, resumo, municipios_por_ano, serie_contagem, classificacao_contagem)

    print("\n===== RESUMO =====")
    print(f"Arquivos processados: {len(arquivos)}")
    print(f"Registros de residentes no Ceará: {total_geral:,}")
    print(f"Combinações município-semana: {len(serie_contagem):,}")
    print(f"Saída: {args.output.resolve()}")
    print("\nAs séries contam registros por classificação original; não são ainda casos confirmados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
