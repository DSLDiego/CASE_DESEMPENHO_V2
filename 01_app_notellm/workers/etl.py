"""Worker orquestrador ETL: scan -> parse -> de-para -> carga -> qualidade.

Cada arquivo processado grava status, duracao (ms), nº de extracoes e a mensagem de
erro em `tb_fonte_dados`; cada execucao do pipeline vira uma linha em `tb_etl_execucao`
(ambos alimentam o painel "Gestao ETL" do web e da GUI).
"""
from __future__ import annotations

import time
from pathlib import Path

from config import CONFIDENCE_MIN, PDF_PARSE_ALLOW, PDF_PARSE_SKIP, PERIODS
from models.database import DatabaseManager
from models.repositories import DeParaRepository, FatoRepository, FonteRepository, QualityRepository
from models.depara import resolve
from workers.parse_pdf import parse_pdf
from workers.parse_tab import RawExtraction, parse_tab
from workers.parse_txt import parse_txt
from workers.quality import brl_milhoes_para_usd_bi, run_audit
from workers.scanner import scan_container

OPERACIONAIS = {"EFETIVO_TOTAL", "PRODUCAO_BOED", "FUT_REFINO"}

# Limites de plausibilidade (USD bi, trimestre/posicao). Acima -> tenta re-escala.
LIMITES = {
    "RECEITA_LIQUIDA": (0.0, 300.0), "LUCRO_BRUTO": (0.0, 200.0),
    "DESPESA_OPERACIONAL": (-300.0, 50.0), "EBITDA_AJUSTADO": (-50.0, 150.0),
    "LUCRO_LIQUIDO": (-80.0, 100.0), "FCO": (-50.0, 200.0), "FCL": (-50.0, 120.0),
    "DIVIDA_BRUTA": (0.0, 900.0), "DIVIDA_LIQUIDA": (-50.0, 700.0),
    "CAPEX": (0.0, 120.0),
}


def escolher_parser(caminho: Path):
    ext = caminho.suffix.lower()
    if ext in (".xlsx", ".xlsm", ".xls", ".csv"):
        return parse_tab
    if ext == ".pdf":
        return parse_pdf
    if ext in (".txt", ".docx"):
        return parse_txt
    return None


def deve_parsear_pdf(caminho: Path) -> bool:
    nome = caminho.name.lower()
    if any(skip in nome for skip in PDF_PARSE_SKIP):
        return False
    if any(keep in nome for keep in PDF_PARSE_ALLOW):
        return True
    try:
        return caminho.stat().st_size < 3_000_000
    except OSError:
        return False


def normalizar_sinal(canon: str, valor: float) -> float:
    """Padroniza sinais: CAPEX como magnitude positiva, despesa como redutora."""
    if canon == "CAPEX" and valor < 0:
        return round(abs(valor), 4)
    if canon == "DESPESA_OPERACIONAL" and valor > 0:
        return round(-valor, 4)
    return valor


def plausivel(rubrica: str, valor: float) -> tuple[float, float, bool]:
    """Aplica limites; tenta re-escala /1000 (ex.: dolares lidos como milhoes)."""
    if rubrica not in LIMITES:
        return valor, 0.0, True
    lo, hi = LIMITES[rubrica]
    conf_penalty, ok = 0.0, lo <= valor <= hi
    tentativas = 0
    while not ok and tentativas < 3 and valor > hi:
        valor /= 1000.0
        conf_penalty += 0.05
        tentativas += 1
        ok = lo <= valor <= hi
    return round(valor, 4), conf_penalty, ok


def prioridade_arquivo(caminho: Path) -> int:
    nome = caminho.name.lower()
    if "r$" in nome or "reais" in nome:
        return 2  # BRL convertido: processa por ultimo, nunca sobrescreve USD
    if "usd" in nome or "databook" in nome or "supplement" in nome:
        return 0
    return 1


def run_etl(db: DatabaseManager | None = None, apenas_periodos: set[str] | None = None,
            parse_pdfs: bool = True) -> dict:
    db = db or DatabaseManager()
    fontes = FonteRepository(db)
    depara = DeParaRepository(db)
    fatos = FatoRepository(db)
    quality = QualityRepository(db)

    # Painel de gestão do ETL: cada execução vira uma linha em tb_etl_execucao.
    id_execucao = fontes.abrir_execucao()
    resumo = {"scan": {}, "arquivos_processados": 0, "extracoes": 0,
              "cargas": 0, "revisao": 0, "pulados_pdf": 0, "erros": 0, "nao_baixados": 0}
    try:
        resumo["scan"] = scan_container(fontes)
    except Exception as exc:                      # varredura é opcional p/ o pipeline
        resumo["scan"] = {"erro": str(exc)}
        resumo["erros"] += 1
    alvos = apenas_periodos or set(PERIODS)

    arquivos = sorted(fontes.listar(), key=lambda r: (prioridade_arquivo(Path(r["caminho_local"] or "")),
                                                      r["caminho_local"] or ""))
    for row in arquivos:
        caminho = Path(row["caminho_local"] or "") if row["caminho_local"] else None
        # Fonte web descoberta mas nunca baixada NAO e erro: e "NAO_BAIXADO".
        if caminho is None:
            fontes.registrar_processamento(row["id_fonte"], "NAO_BAIXADO")
            resumo["nao_baixados"] += 1
            continue
        if not caminho.is_file():
            # ja estava catalogada com caminho local e o arquivo sumiu = erro real
            fontes.registrar_processamento(row["id_fonte"], "ERRO",
                                          erro=f"arquivo local ausente: {caminho}")
            resumo["erros"] += 1
            continue
        parser = escolher_parser(caminho)
        if parser is None:
            fontes.registrar_processamento(row["id_fonte"], "SEM_PARSER")
            continue
        if caminho.suffix.lower() == ".pdf" and (not parse_pdfs or not deve_parsear_pdf(caminho)):
            fontes.registrar_processamento(row["id_fonte"], "NAO_PROCESSADO", erro=None,
                                          n_extracoes=0)
            resumo["pulados_pdf"] += 1
            continue
        inicio = time.perf_counter()
        try:
            extracoes = parser(caminho)
        except Exception as exc:
            duracao = int((time.perf_counter() - inicio) * 1000)
            fontes.registrar_processamento(row["id_fonte"], "ERRO", duracao,
                                          erro=f"{type(exc).__name__}: {exc}"[:500])
            quality.para_revisao(row["nome_empresa"], "?", "?", None,
                                 f"falha de parsing em {caminho.name}: {exc}", 0.0)
            resumo["revisao"] += 1
            resumo["erros"] += 1
            continue
        resumo["arquivos_processados"] += 1
        gravou_algo = False
        for ext in extracoes:
            if ext.periodo not in alvos:
                continue
            resumo["extracoes"] += 1
            rotulo = ext.extras.get("rotulo_origem", ext.rubrica)
            canon, fator = depara.resolver(row["nome_empresa"], rotulo)
            if canon is None:
                canon, _, fator = resolve(rotulo)
                if canon is None:
                    canon = ext.rubrica
                depara.upsert(row["nome_empresa"], rotulo, canon, "DRE", fator)
            valor = round(ext.valor * (fator or 1.0), 4)
            conf = ext.confianca
            if ext.moeda_origem == "BRL" and canon not in OPERACIONAIS:
                valor = brl_milhoes_para_usd_bi(valor * 1000.0, ext.periodo)
                conf -= 0.05
            if canon == "CAPEX":
                valor = normalizar_sinal(canon, valor)  # outflow -> magnitude
            if canon not in OPERACIONAIS:
                valor, penalty, ok = plausivel(canon, valor)
                conf -= penalty
                if not ok:
                    quality.para_revisao(row["nome_empresa"], ext.periodo, canon, valor,
                                         f"fora do limite de plausibilidade ({caminho.name})", conf)
                    resumo["revisao"] += 1
                    continue
            if canon == "DESPESA_OPERACIONAL":
                valor = normalizar_sinal(canon, valor)  # redutora (apos plausibilidade)
            if conf < CONFIDENCE_MIN:
                quality.para_revisao(row["nome_empresa"], ext.periodo, canon, valor,
                                     f"confianca {conf:.2f} em {caminho.name}", conf)
                resumo["revisao"] += 1
                continue
            if ext.moeda_origem == "BRL":
                existente = fatos.obter(row["nome_empresa"], ext.periodo, canon)
                if existente and existente.get("moeda") == "USD":
                    continue  # fonte USD direta prevalece sobre conversao
            if canon == "PRODUCAO_BOED" and valor < 100:
                valor = round(valor * 1000.0, 3)  # Mboed -> kboed
            if canon not in OPERACIONAIS:
                existente = fatos.obter(row["nome_empresa"], ext.periodo, canon)
                if existente and (existente.get("confianca") or 0) > round(conf, 3):
                    continue  # nunca rebaixa fato bom com extracao pior
            if canon in OPERACIONAIS:
                fatos.upsert_operacional(row["nome_empresa"], ext.periodo, canon,
                                         valor, ext.unidade, row["id_fonte"])
            else:
                fatos.upsert_financeiro(row["nome_empresa"], ext.periodo, canon, valor,
                                        "USD", row["id_fonte"], round(conf, 3))
            resumo["cargas"] += 1
            gravou_algo = True
        duracao = int((time.perf_counter() - inicio) * 1000)
        status = "PROCESSADO" if gravou_algo else "SEM_DADOS"
        erro = None if gravou_algo else f"parser nao extraiu periods de {alvos}"
        fontes.registrar_processamento(row["id_fonte"], status, duracao, erro=erro,
                                      n_extracoes=len(extracoes))
    resumo["auditoria"] = run_audit(db)
    fontes.fechar_execucao(id_execucao, arquivos=resumo["arquivos_processados"],
                           extracoes=resumo["extracoes"], cargas=resumo["cargas"],
                           pulados=resumo["pulados_pdf"], revisao=resumo["revisao"],
                           erros=resumo["erros"],
                           detalhe=(f"periodos={sorted(alvos)} · nao_baixados={resumo['nao_baixados']}"))
    fontes.exportar()
    return resumo
