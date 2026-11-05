#!/usr/bin/env python3
"""Verificação offline do lote Sul/Sudeste 14.133 (issues #73/#101).

Lê somente snapshots em provas/sul-sudeste-14133/ e Markdown publicados.
Não acessa a rede.

Uso:
  python3 scripts/sul_sudeste_14133.py verify
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "metadados/sul-sudeste-14133/index.json"
NOTE_RE = re.compile(r"<!-- nota-edicao:inicio -->.*?<!-- nota-edicao:fim -->\s*", re.S)

UFS = ("ES", "MG", "RJ", "SP", "PR", "SC", "RS")
IBGES = {
    "Vitória": "3205309",
    "Belo Horizonte": "3106200",
    "Rio de Janeiro": "3304557",
    "São Paulo": "3550308",
    "Curitiba": "4106902",
    "Florianópolis": "4205407",
    "Porto Alegre": "4314902",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"(?<=\d)\s*[oº°ª](?![a-z0-9])", " ", text)
    return re.sub(r"[^0-9a-z]+", "", text)


def strip_note(markdown: str) -> str:
    return NOTE_RE.sub("", markdown, count=1)


def load_index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8"))


def verify_fonte_entry(entry: dict, cobertura: dict | None = None) -> None:
    path = ROOT / entry["arquivo"]
    if not path.is_file():
        raise SystemExit(f"snapshot ausente: {path}")
    raw = lzma.open(path).read()
    got = sha256_bytes(raw)
    if got != entry["sha256_conteudo"]:
        raise SystemExit(f"hash fonte divergiu {entry['chave']}: {got}")
    if "sha256_arquivo_xz" in entry:
        xz_got = sha256_bytes(path.read_bytes())
        if xz_got != entry["sha256_arquivo_xz"]:
            raise SystemExit(f"hash xz divergiu {entry['chave']}: {xz_got}")


def verify_markdown(path: Path, sha_md: str, sha_corpo: str) -> str:
    if not path.is_file():
        raise SystemExit(f"markdown ausente: {path}")
    full = path.read_text(encoding="utf-8")
    if sha256_bytes(full.encode()) != sha_md:
        raise SystemExit(f"sha256_markdown divergiu: {path}")
    corpo = strip_note(full)
    if sha256_bytes(corpo.encode()) != sha_corpo:
        raise SystemExit(f"sha256_corpo_markdown divergiu: {path}")
    if "<!-- nota-edicao:inicio -->" not in full:
        raise SystemExit(f"nota-edicao ausente: {path}")
    return corpo


def verify_vitoria() -> None:
    fontes = json.loads(
        (ROOT / "provas/sul-sudeste-14133/capitais/vitoria/fontes.json").read_text(
            encoding="utf-8"
        )
    )
    entry = fontes["fontes"][0]
    verify_fonte_entry(entry)
    md_path = ROOT / "municipais/3205309/br-municipal-3205309-lei-organica-1990-04-05.md"
    corpo = verify_markdown(
        md_path, entry["sha256_markdown"], entry["sha256_corpo_markdown"]
    )
    if "LEI ORGÂNICA DO MUNICÍPIO DE VITÓRIA" not in corpo:
        raise SystemExit("Vitória LO: título ausente")
    if "PREÂMBULO" not in corpo.upper() and "Preâmbulo" not in corpo:
        raise SystemExit("Vitória LO: preâmbulo ausente")
    raw = lzma.open(ROOT / entry["arquivo"]).read()
    from bs4 import BeautifulSoup

    html_fold = fold(BeautifulSoup(raw, "lxml").get_text(" "))
    md_fold = fold(corpo)
    marker = "leiorganicadomunicipiodevitoria"
    hi, mi = html_fold.find(marker), md_fold.find(marker)
    if hi < 0 or mi < 0:
        raise SystemExit("Vitória LO: marker fold ausente")
    stop = "estetextonaosubstitui"
    hs, ms = html_fold.find(stop, hi), md_fold.find(stop, mi)
    hseg = html_fold[hi : hs if hs >= 0 else None]
    mseg = md_fold[mi : ms if ms >= 0 else None]
    if hseg != mseg:
        raise SystemExit("Vitória LO: fold HTML↔MD divergiu")
    cob = json.loads(
        (ROOT / "provas/sul-sudeste-14133/capitais/vitoria/cobertura-lei-organica.json").read_text(
            encoding="utf-8"
        )
    )
    if not cob.get("fold_equal"):
        raise SystemExit("Vitória cobertura fold_equal falso")


def verify_curitiba() -> None:
    fontes = json.loads(
        (ROOT / "provas/sul-sudeste-14133/capitais/curitiba/fontes.json").read_text(
            encoding="utf-8"
        )
    )
    entry = fontes["fontes"][0]
    verify_fonte_entry(entry)
    md_path = ROOT / (
        "municipais/4106902/br-municipal-4106902-lei-organica-1990-consolidada-cmc-2014.md"
    )
    corpo = verify_markdown(
        md_path, entry["sha256_markdown"], entry["sha256_corpo_markdown"]
    )
    if "ORGÂNICA" not in corpo.upper():
        raise SystemExit("Curitiba LO: título ausente")
    cob = json.loads(
        (
            ROOT / "provas/sul-sudeste-14133/capitais/curitiba/cobertura-lei-organica.json"
        ).read_text(encoding="utf-8")
    )
    if cob.get("paginas") != 101:
        raise SystemExit("Curitiba LO: esperado 101 páginas")
    if len(cob.get("page_text_sha256") or []) != 101:
        raise SystemExit("Curitiba LO: hashes por página incompletos")
    if len(cob.get("page_text_lens") or []) != 101:
        raise SystemExit("Curitiba LO: lens por página incompletos")
    if any(n <= 20 for n in cob["page_text_lens"]):
        raise SystemExit("Curitiba LO: página com texto curto demais")
    if not cob.get("fold_equal"):
        raise SystemExit("Curitiba LO: fold_equal falso")
    # Amostra bbox (páginas 1/50/101) e reconversão leve das mesmas páginas —
    # a íntegra das 101 páginas fica nos hashes armazenados na cobertura.
    import subprocess
    import tempfile

    raw = lzma.open(ROOT / entry["arquivo"]).read()
    sample_pages = (1, 50, 101)
    with tempfile.TemporaryDirectory() as td:
        pdf = Path(td) / "lo.pdf"
        pdf.write_bytes(raw)
        for p in sample_pages:
            pt = subprocess.check_output(
                [
                    "pdftotext",
                    "-f",
                    str(p),
                    "-l",
                    str(p),
                    "-layout",
                    "-enc",
                    "UTF-8",
                    str(pdf),
                    "-",
                ],
                text=True,
            )
            if sha256_bytes(pt.encode()) != cob["page_text_sha256"][p - 1]:
                raise SystemExit(f"Curitiba LO: hash página {p} divergiu")
            if len(pt) != cob["page_text_lens"][p - 1]:
                raise SystemExit(f"Curitiba LO: lens página {p} divergiu")
            bbox = subprocess.check_output(
                ["pdftotext", "-bbox", "-f", str(p), "-l", str(p), str(pdf), "-"],
                text=True,
            )
            words = bbox.count("<word ")
            expected = (cob.get("bbox_word_counts_sample") or {}).get(str(p))
            if expected is not None and words != expected:
                raise SystemExit(
                    f"Curitiba LO: bbox page {p} words {words} != {expected}"
                )
    if "ATO DAS DISPOSIÇÕES TRANSITÓRIAS" not in corpo and "DISPOSIÇÕES TRANSITÓRIAS" not in corpo:
        # índice/corpo deve preservar ADCT se presente na consolidação
        if "TRANSIT" not in corpo.upper():
            raise SystemExit("Curitiba LO: disposições transitórias ausentes no corpo")

def verify_sc30() -> None:
    fontes = json.loads(
        (ROOT / "provas/sul-sudeste-14133/SC/fontes.json").read_text(encoding="utf-8")
    )
    entry = fontes["fontes"][0]
    verify_fonte_entry(entry)
    if entry.get("carater") != "especifico-contratacao-direta-dispensa-eletronica":
        raise SystemExit("SC 30: caráter incorreto")
    md_path = ROOT / "estaduais/SC/br-sc-decreto-2023-02-17-30.md"
    corpo = verify_markdown(
        md_path, entry["sha256_markdown"], entry["sha256_corpo_markdown"]
    )
    full = md_path.read_text(encoding="utf-8")
    if "NÃO é regulamento geral" not in full and "Não é regulamento geral" not in full:
        # note uses **Caráter: específico**
        if "específico/temático" not in full and "especifico" not in full.lower():
            raise SystemExit("SC 30: nota deve marcar caráter não-geral")
    if "14.133" not in corpo:
        raise SystemExit("SC 30: 14.133 ausente no corpo")
    cob = json.loads(
        (ROOT / "provas/sul-sudeste-14133/SC/cobertura-30.json").read_text(encoding="utf-8")
    )
    if not cob.get("fold_equal"):
        raise SystemExit("SC 30: fold_equal falso")


def verify_poa() -> None:
    fontes = json.loads(
        (
            ROOT / "provas/sul-sudeste-14133/capitais/porto-alegre/fontes.json"
        ).read_text(encoding="utf-8")
    )
    entry = fontes["fontes"][0]
    verify_fonte_entry(entry)
    md_path = ROOT / "municipais/4314902/br-municipal-4314902-decreto-2023-05-11-21978.md"
    corpo = verify_markdown(
        md_path, entry["sha256_markdown"], entry["sha256_corpo_markdown"]
    )
    full = md_path.read_text(encoding="utf-8")
    if "específico/temático" not in full and "NÃO é regulamento geral" not in full:
        raise SystemExit("POA 21978: nota deve marcar caráter não-geral")
    if "21.978" not in corpo and "21978" not in fold(corpo):
        raise SystemExit("POA 21978: número ausente")
    cob = json.loads(
        (
            ROOT / "provas/sul-sudeste-14133/capitais/porto-alegre/cobertura-21978.json"
        ).read_text(encoding="utf-8")
    )
    if cob.get("paginas") != 12:
        raise SystemExit("POA: esperado 12 páginas")
    if len(cob.get("page_text_lens") or []) != 12:
        raise SystemExit("POA: lens incompletos")
    if not cob.get("fold_equal"):
        raise SystemExit("POA: fold_equal falso")


def verify_index() -> None:
    idx = load_index()
    if idx.get("tema") != "sul-sudeste-14133":
        raise SystemExit("index tema incorreto")
    if set(idx.get("ufs") or []) != set(UFS):
        raise SystemExit("index UFs incompleto")
    if len(idx.get("estaduais") or []) != 7:
        raise SystemExit("index estaduais != 7")
    if len(idx.get("capitais") or []) != 7:
        raise SystemExit("index capitais != 7")

    # Reuso PR geral
    pr = next(u for u in idx["estaduais"] if u["uf"] == "PR")
    if pr["status_acervo"] != "decreto-geral-publicado":
        raise SystemExit("PR deveria ser decreto-geral-publicado")
    pr_dec = pr["decretos_14133"][0]
    if pr_dec["norma_id"] != "br-pr-ato-259084" or not pr_dec.get("reuso"):
        raise SystemExit("PR deve reusar br-pr-ato-259084")
    if not (ROOT / pr_dec["arquivo"]).is_file():
        raise SystemExit(f"PR arquivo ausente: {pr_dec['arquivo']}")

    # MG suite: nenhum geral
    mg = next(u for u in idx["estaduais"] if u["uf"] == "MG")
    if mg["status_acervo"] != "suite-tematica-sem-decreto-geral":
        raise SystemExit("MG status incorreto")
    for d in mg["decretos_14133"]:
        if d.get("carater") == "regulamento-geral-estadual":
            raise SystemExit("MG não deve marcar geral")
        if not d.get("reuso"):
            raise SystemExit(f"MG deve marcar reuso: {d['norma_id']}")
        if not (ROOT / d["arquivo"]).is_file():
            raise SystemExit(f"MG arquivo ausente: {d['arquivo']}")

    # SP capital completo
    sp = next(c for c in idx["capitais"] if c["ibge"] == "3550308")
    if sp["decreto_14133_carater"] != "geral":
        raise SystemExit("SP capital deve ter decreto geral")
    if not (ROOT / sp["lei_organica"]).is_file():
        raise SystemExit("SP LO ausente")
    if not (ROOT / sp["decreto_14133"]).is_file():
        raise SystemExit("SP decreto ausente")

    # BH: parcial + LO pendente acesso
    bh = next(c for c in idx["capitais"] if c["ibge"] == "3106200")
    if bh["decreto_14133_carater"] != "parcial-criterio-julgamento":
        raise SystemExit("BH deve permanecer parcial-criterio-julgamento")
    if not str(bh["lei_organica"]).startswith("pendente"):
        raise SystemExit("BH LO deve permanecer pendente-acesso")

    # SC específico
    sc = next(u for u in idx["estaduais"] if u["uf"] == "SC")
    sc_dec = sc["decretos_14133"][0]
    if "especifico" not in sc_dec["carater"]:
        raise SystemExit("SC 30 deve ser específico")
    if not (ROOT / sc_dec["arquivo"]).is_file():
        raise SystemExit("SC 30 arquivo ausente")

    # Novas publicações
    novas = set(idx["resumo"]["novas_publicacoes_neste_lote"])
    expected = {
        "br-es-decreto-2023-02-15-5307-r",
        "br-es-decreto-2023-03-28-5352-r",
        "br-es-decreto-2023-03-28-5353-r",
        "br-municipal-3205309-lei-organica-1990-04-05",
        "br-municipal-4106902-lei-organica-1990-consolidada-cmc-2014",
        "br-municipal-4314902-decreto-2023-05-11-21978",
        "br-sc-decreto-2023-02-17-30",
    }
    if novas != expected:
        raise SystemExit(f"resumo novas_publicacoes divergiu: {novas}")

    # ES suite temática publicada (≠ geral) + bloqueios concretos
    es = next(u for u in idx["estaduais"] if u["uf"] == "ES")
    if es["status_acervo"] != "suite-tematica-sem-decreto-geral":
        raise SystemExit("ES status deve ser suite-tematica-sem-decreto-geral")
    if len(es.get("decretos_14133") or []) < 3:
        raise SystemExit("ES deve publicar ao menos 5307/5352/5353")
    for d in es["decretos_14133"]:
        if d.get("carater") == "regulamento-geral-estadual":
            raise SystemExit(f"ES não deve marcar geral: {d['norma_id']}")
        if not (ROOT / d["arquivo"]).is_file():
            raise SystemExit(f"ES arquivo ausente: {d['arquivo']}")
    if not es.get("bloqueios"):
        raise SystemExit("ES deve registrar bloqueios concretos")
    flo = next(c for c in idx["capitais"] if c["ibge"] == "4205407")
    if not flo.get("bloqueios"):
        raise SystemExit("Florianópolis deve registrar bloqueios")



def verify_es_suite() -> None:
    """Verifica suite ES SEGER (5307/5352/5353) via pypdf offline."""
    from pypdf import PdfReader

    fontes = json.loads(
        (ROOT / "provas/sul-sudeste-14133/ES/fontes.json").read_text(encoding="utf-8")
    )
    published = {
        "seger-decreto-5307-R-2023": ("5307", "estaduais/ES/br-es-decreto-2023-02-15-5307-r.md"),
        "seger-decreto-5352-R-2023": ("5352", "estaduais/ES/br-es-decreto-2023-03-28-5352-r.md"),
        "seger-decreto-5353-R-2023": ("5353", "estaduais/ES/br-es-decreto-2023-03-28-5353-r.md"),
    }
    by_key = {e["chave"]: e for e in fontes["fontes"]}
    for chave, (num, md_rel) in published.items():
        entry = by_key[chave]
        verify_fonte_entry(entry)
        if "sha256_markdown" not in entry:
            raise SystemExit(f"ES {num}: fonte sem sha256_markdown")
        corpo = verify_markdown(
            ROOT / md_rel, entry["sha256_markdown"], entry["sha256_corpo_markdown"]
        )
        full = (ROOT / md_rel).read_text(encoding="utf-8")
        if "NÃO é regulamento geral" not in full and "não é regulamento geral" not in full.lower():
            if "suite ampla" not in full.lower() and "regras de transição" not in full.lower() and "governança" not in full.lower():
                raise SystemExit(f"ES {num}: nota deve marcar caráter não-geral")
        if "14.133" not in corpo:
            raise SystemExit(f"ES {num}: 14.133 ausente")
        cob = json.loads(
            (ROOT / f"provas/sul-sudeste-14133/ES/cobertura-{num}-R.json").read_text(
                encoding="utf-8"
            )
        )
        if not cob.get("fold_equal"):
            raise SystemExit(f"ES {num}: fold_equal falso")
        if len(cob.get("page_text_sha256") or []) != cob.get("paginas"):
            raise SystemExit(f"ES {num}: hashes por página incompletos")
        # Reconversão pypdf de todas as páginas vs hashes armazenados
        raw = lzma.open(ROOT / entry["arquivo"]).read()
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            pdf = Path(td) / "d.pdf"
            pdf.write_bytes(raw)
            reader = PdfReader(str(pdf))
            if len(reader.pages) != cob["paginas"]:
                raise SystemExit(f"ES {num}: páginas {len(reader.pages)} != {cob['paginas']}")
            for i, page in enumerate(reader.pages):
                pt = (page.extract_text() or "").replace("\r\n", "\n").replace("\r", "\n").strip("\n")
                if sha256_bytes(pt.encode()) != cob["page_text_sha256"][i]:
                    raise SystemExit(f"ES {num}: hash página {i+1} divergiu")
                if len(pt) != cob["page_text_lens"][i]:
                    raise SystemExit(f"ES {num}: lens página {i+1} divergiu")
        if num == "5352" and "concorrência" not in corpo.lower() and "CONCORRÊNCIA" not in corpo:
            raise SystemExit("ES 5352: concorrência ausente no corpo")
    # Fontes 5354/5545 capturadas sem MD publicado
    for chave in ("seger-decreto-5354-R-2023", "seger-decreto-5545-R-2023"):
        entry = by_key[chave]
        verify_fonte_entry(entry)
        if entry.get("status") != "fonte-capturada-conversao-bbox-pendente":
            raise SystemExit(f"{chave}: status bbox pendente esperado")


def verify() -> None:
    verify_index()
    verify_vitoria()
    verify_curitiba()
    verify_sc30()
    verify_poa()
    verify_es_suite()
    print("sul-sudeste-14133: verify ok")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cmd", choices=["verify"])
    args = parser.parse_args(argv)
    if args.cmd == "verify":
        verify()
    else:
        raise SystemExit(f"comando desconhecido: {args.cmd}")


if __name__ == "__main__":
    main()
