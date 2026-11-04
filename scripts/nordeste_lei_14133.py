#!/usr/bin/env python3
"""Coleta retomável e verificação do recorte Nordeste Lei 14.133 (#73/#101).

Escopo setorial: metadados/provas/nordeste-lei-14133 e normas publicadas neste lote.
Não altera índices compartilhados nem README global.
Não acessa a rede em `verify`. `collect` é retomável via estado JSON.

Uso:
  python3 scripts/nordeste_lei_14133.py verify
  python3 scripts/nordeste_lei_14133.py collect [--force-id ID]
  python3 scripts/nordeste_lei_14133.py status
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "metadados/nordeste-lei-14133/index.json"
STATE = ROOT / "provas/nordeste-lei-14133/collect-state.json"
AUDIT = ROOT / "provas/nordeste-lei-14133/auditoria-pdfs-colacao.json"
UA = "leis-corpus-nordeste/1.0 (+https://github.com/minutei-ai/leis)"
NOTE_RE = re.compile(
    r"<!-- nota-edicao:inicio -->.*?<!-- nota-edicao:fim -->\s*", re.S
)

# Candidatos de coleta retomável (só URLs oficiais conhecidas / espelhos oficiais).
# Cada item: id estável, destino relativo, url, opcional url_alt.
COLLECT_CANDIDATES = [
    {
        "id": "ce-35283-origem",
        "kind": "probe",
        "url": (
            "https://www.seplag.ce.gov.br/wp-content/uploads/sites/14/2023/01/"
            "Decreto-Estadual-no-35.283-19012023-Regulamenta-Lei-Federal-no-14.133-"
            "Ambito-Adm-Publica-Poder-Executivo-1.pdf"
        ),
        "nota": "Origem CE 35.283; esperado 500/redirect. Não substitui Wayback já publicado.",
    },
    {
        "id": "ce-35283-cegov",
        "kind": "probe",
        "url": (
            "https://www.ce.gov.br/seplag/wp-content/uploads/sites/14/2023/01/"
            "Decreto-Estadual-no-35.283-19012023-Regulamenta-Lei-Federal-no-14.133-"
            "Ambito-Adm-Publica-Poder-Executivo-1.pdf"
        ),
        "nota": "Espelho pós-redirect; esperado 500 enquanto origem indisponível.",
    },
    {
        "id": "aracaju-lo",
        "kind": "snapshot",
        "url": (
            "https://www.aracaju.se.leg.br/institucional/legislacao/"
            "LeiOrgnicaAtualizadaataEmenda72.pdf"
        ),
        "dest": (
            "provas/nordeste-lei-14133/capitais/2800308/fontes/"
            "br-municipal-2800308-lei-organica-1990.pdf.xz"
        ),
        "expected_sha256": "68300ed6855ff9ff5ed1efe69b0abe7ce45c20fd45f5ff96a84e7afdf3501ef4",
    },
    {
        "id": "aracaju-7178",
        "kind": "snapshot",
        "url": (
            "https://aracajucompras.se.gov.br/portal/documentos/legislacoes/2023/"
            "Decreto-7.178-V2.pdf"
        ),
        "dest": (
            "provas/nordeste-lei-14133/capitais/2800308/fontes/"
            "br-municipal-2800308-decreto-2023-06-12-7178.pdf.xz"
        ),
        "expected_sha256": "e7106f6c6b9a9bdbf77e88adcb831f9be6b645d7a1a22f4270c722895616ea8c",
    },
    {
        "id": "maceio-lo",
        "kind": "snapshot",
        "url": (
            "https://www.maceio.al.leg.br/documentos/docs/doc.php?"
            "filepath=publicacoes&id=1"
        ),
        "dest": (
            "provas/nordeste-lei-14133/capitais/2704302/fontes/"
            "br-municipal-2704302-lei-organica.pdf.xz"
        ),
        "expected_sha256": "5b0de1590ef54cb68252bfcc336211815ae8401addde8b9b4e1f77b5d414b568",
    },
    {
        "id": "fortaleza-15317",
        "kind": "snapshot",
        "url": (
            "https://compras.sepog.fortaleza.ce.gov.br/publico/legislacao/municipal/"
            "lei-1433/Decreto_11.254_2022.pdf"
        ),
        "dest": (
            "provas/nordeste-lei-14133/capitais/2304400/fontes/"
            "br-municipal-2304400-decreto-2022-05-06-15317.pdf.xz"
        ),
        "expected_sha256": "a5b7ec9b41a00c7acaf616b083c920d56170caaff79a296c66e6fa922649ca5b",
    },
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strip_note(md: str) -> str:
    return NOTE_RE.sub("", md, count=1).lstrip("\n")


def load_index() -> dict:
    return json.loads(META.read_text(encoding="utf-8"))


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"versao": 1, "itens": {}}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def http_get(url: str, timeout: int = 45) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), resp.read(), resp.headers.get_content_type()
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        return int(e.code), body, "error"
    except Exception as e:  # noqa: BLE001 — registro de bloqueio
        return 0, str(e).encode(), "exception"


def expected_sha_from_fontes(dest_rel: str) -> str | None:
    """Resolve expected sha from any fontes*.json under provas/nordeste or regulamentacao."""
    for base in [
        ROOT / "provas/nordeste-lei-14133",
        ROOT / "provas/regulamentacao-14133-ufs",
    ]:
        if not base.exists():
            continue
        for fontes in base.rglob("fontes*.json"):
            data = json.loads(fontes.read_text(encoding="utf-8"))
            for entry in data.get("fontes", []):
                if entry.get("arquivo") == dest_rel:
                    return entry.get("sha256_conteudo")
    return None


def cmd_status() -> int:
    idx = load_index()
    state = load_state()
    print(f"recorte_ufs={idx.get('recorte_ufs')}")
    print(f"atualizado_em={idx.get('atualizado_em')}")
    print(f"resumo={json.dumps(idx.get('resumo'), ensure_ascii=False)}")
    done = sum(1 for v in state.get("itens", {}).values() if v.get("status") == "ok")
    print(f"collect_state ok={done}/{len(COLLECT_CANDIDATES)} path={STATE.relative_to(ROOT)}")
    return 0


def cmd_collect(force_id: str | None = None) -> int:
    """Retomável: pula itens com status ok salvo se --force-id."""
    state = load_state()
    itens = state.setdefault("itens", {})
    errors = 0
    for cand in COLLECT_CANDIDATES:
        cid = cand["id"]
        prev = itens.get(cid, {})
        if force_id and force_id != cid:
            continue
        if prev.get("status") == "ok" and not (force_id == cid):
            print(f"skip {cid} (já ok)")
            continue
        print(f"collect {cid} …")
        code, body, ctype = http_get(cand["url"])
        rec = {
            "id": cid,
            "url": cand["url"],
            "http": code,
            "ctype": ctype,
            "bytes": len(body),
            "sha256": sha256_bytes(body) if body else None,
            "kind": cand["kind"],
        }
        if code == 0:
            rec["status"] = "bloqueio"
            rec["erro"] = body.decode("utf-8", "replace")[:300]
            errors += 1
        elif cand["kind"] == "probe":
            rec["status"] = "ok" if code in {200, 301, 302, 403, 500} else "falha"
            rec["nota"] = cand.get("nota", "probe")
            # probe nunca grava snapshot
        else:
            if code != 200 or not body.startswith(b"%PDF"):
                rec["status"] = "bloqueio" if code in {0, 403, 429, 500, 503} else "falha"
                rec["nota"] = "resposta não-PDF ou HTTP≠200; bloqueio≠ausência"
                errors += 1
            else:
                dest = ROOT / cand["dest"]
                expected = cand.get("expected_sha256")
                if expected == "PLACEHOLDER":
                    expected = expected_sha_from_fontes(cand["dest"])
                got = sha256_bytes(body)
                if expected and got != expected:
                    rec["status"] = "divergencia-hash"
                    rec["expected_sha256"] = expected
                    rec["nota"] = (
                        "Hash divergiu do snapshot publicado; não sobrescrever. "
                        "Preservar divergência para análise."
                    )
                    errors += 1
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with lzma.open(dest, "wb", preset=6) as f:
                        f.write(body)
                    rec["status"] = "ok"
                    rec["arquivo"] = cand["dest"]
                    rec["sha256_arquivo_xz"] = sha256_bytes(dest.read_bytes())
        itens[cid] = rec
        save_state(state)
        print(f"  -> {rec['status']} http={code} bytes={rec['bytes']}")
    return 1 if errors and force_id else 0


def _check_fonte_entry(entry: dict, label: str, errors: list[str]) -> None:
    snap = ROOT / entry["arquivo"]
    if not snap.is_file():
        errors.append(f"{label}: snapshot ausente {snap}")
        return
    raw = lzma.open(snap).read()
    if sha256_bytes(raw) != entry["sha256_conteudo"]:
        errors.append(f"{label}: sha256_conteudo divergiu")
    if sha256_bytes(snap.read_bytes()) != entry.get("sha256_arquivo_xz"):
        errors.append(f"{label}: sha256_arquivo_xz divergiu")
    md_path = None
    # try resolve markdown via norma paths in index later


def cmd_verify() -> int:
    errors: list[str] = []
    idx = load_index()
    if idx.get("issues") != [73, 101]:
        errors.append("issues != [73,101]")
    if idx.get("recorte_ufs") != ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]:
        errors.append("recorte_ufs divergiu")

    # CE provenance
    ce_fontes = json.loads(
        (ROOT / "provas/regulamentacao-14133-ufs/CE/fontes.json").read_text(encoding="utf-8")
    )
    fe = ce_fontes["fontes"][0]
    if fe.get("proveniencia") != "wayback-arquivo-url-oficial":
        errors.append("CE: proveniencia != wayback-arquivo-url-oficial")
    if fe.get("equivalente_captura_oficial_atual") is not False:
        errors.append("CE: arquivo Wayback não pode equivaler captura oficial atual")
    if fe.get("colacao_oficial_status") != "desconhecido":
        errors.append("CE: colacao_oficial_status deve ser desconhecido")
    if not fe.get("wayback_timestamp"):
        errors.append("CE: wayback_timestamp ausente")
    if not fe.get("edicao_identidade"):
        errors.append("CE: edicao_identidade ausente")
    md_ce = (ROOT / "estaduais/CE/br-ce-decreto-2023-01-19-35283.md").read_text(encoding="utf-8")
    if "wayback" not in md_ce.lower() and "Wayback" not in md_ce:
        errors.append("CE markdown sem menção Wayback")
    if "desconhecido" not in md_ce:
        errors.append("CE markdown sem colação desconhecida")
    if sha256_bytes(lzma.open(ROOT / fe["arquivo"]).read()) != fe["sha256_conteudo"]:
        errors.append("CE snapshot hash divergiu")

    # Gerais estaduais hashes
    for uf, fontes_rel, md_rel in [
        ("RN", "provas/regulamentacao-14133-ufs/RN/fontes.json", "estaduais/RN/br-rn-decreto-2023-03-07-32449.md"),
        ("SE", "provas/regulamentacao-14133-ufs/SE/fontes.json", "estaduais/SE/br-se-decreto-2023-06-28-342.md"),
        ("PI", "provas/regulamentacao-14133-ufs/PI/fontes.json", "estaduais/PI/br-pi-decreto-2023-03-07-21872.md"),
    ]:
        fontes = json.loads((ROOT / fontes_rel).read_text(encoding="utf-8"))
        entry = fontes["fontes"][0]
        snap = ROOT / entry["arquivo"]
        raw = lzma.open(snap).read()
        if sha256_bytes(raw) != entry["sha256_conteudo"]:
            errors.append(f"{uf}: sha fonte divergiu")
        md = (ROOT / md_rel).read_text(encoding="utf-8")
        if sha256_bytes(md.encode()) != entry["sha256_markdown"]:
            errors.append(f"{uf}: sha markdown divergiu")
        if sha256_bytes(strip_note(md).encode()) != entry["sha256_corpo_markdown"]:
            errors.append(f"{uf}: sha corpo divergiu")
        cob_path = {
            "RN": "provas/regulamentacao-14133-ufs/RN/cobertura-32449.json",
            "SE": "provas/regulamentacao-14133-ufs/SE/cobertura-342.json",
            "PI": "provas/regulamentacao-14133-ufs/PI/cobertura-21872.json",
        }[uf]
        cob = json.loads((ROOT / cob_path).read_text(encoding="utf-8"))
        if cob.get("colacao_oficial_status") != "desconhecido":
            errors.append(f"{uf}: colacao_oficial_status != desconhecido")
        if cob.get("fold_ok") is True:
            errors.append(f"{uf}: fold_ok não pode ser true só com texto extraído")

    # Capitais com LO / decretos novos
    required_caps = {
        "2704302": "municipais/2704302/br-municipal-2704302-lei-organica.md",
        "2800308": "municipais/2800308/br-municipal-2800308-lei-organica-1990.md",
        "2304400": "municipais/2304400/br-municipal-2304400-lei-organica.md",
        "2408102": "municipais/2408102/br-municipal-2408102-lei-organica-1990.md",
        "2507507": "municipais/2507507/br-municipal-2507507-lei-organica-1990.md",
        "2611606": "municipais/2611606/br-municipal-2611606-lei-organica-1990-04-04.md",
        "2927408": "municipais/2927408/br-municipal-2927408-lei-organica-consolidada-2024.md",
    }
    for cap in idx["capitais"]:
        ibge = cap["ibge"]
        lo = cap.get("lei_organica")
        if ibge in required_caps:
            if lo != required_caps[ibge]:
                errors.append(f"capital {ibge}: lei_organica path divergiu ({lo})")
            if not (ROOT / required_caps[ibge]).is_file():
                errors.append(f"capital {ibge}: markdown LO ausente")
        elif ibge in {"2111300", "2211001"}:
            if lo not in {"nao-recuperado", "ausente"}:
                errors.append(f"capital {ibge}: LO deveria ser nao-recuperado, got {lo}")
            # must not claim absence of legislation from HTTP alone
            if lo == "ausente":
                errors.append(
                    f"capital {ibge}: use nao-recuperado quando só há falha de acesso"
                )

    # Aracaju geral + Fortaleza transição
    aju_dec = ROOT / "municipais/2800308/br-municipal-2800308-decreto-2023-06-12-7178.md"
    if not aju_dec.is_file():
        errors.append("Aracaju Decreto 7.178 ausente")
    else:
        t = aju_dec.read_text(encoding="utf-8")
        if "regulamento-geral-municipal" not in t:
            errors.append("Aracaju 7.178 sem caráter geral na nota")
        if "14.133" not in t:
            errors.append("Aracaju 7.178 sem 14.133")
    for_dec = ROOT / "municipais/2304400/br-municipal-2304400-decreto-2022-05-06-15317.md"
    if not for_dec.is_file():
        errors.append("Fortaleza 15.317 ausente")
    else:
        t = for_dec.read_text(encoding="utf-8")
        if "marco-temporal-transicao" not in t and "transição" not in t.lower():
            errors.append("Fortaleza 15.317 sem caráter transição")

    cap_se = next(c for c in idx["capitais"] if c["ibge"] == "2800308")
    if cap_se.get("decreto_14133_carater") != "regulamento-geral-municipal":
        errors.append("index: Aracaju decreto_14133_carater != regulamento-geral-municipal")
    cap_ce = next(c for c in idx["capitais"] if c["ibge"] == "2304400")
    if cap_ce.get("decreto_14133_carater") != "marco-temporal-transicao":
        errors.append("index: Fortaleza decreto_14133_carater != marco-temporal-transicao")

    # Auditoria PDF presente
    if not AUDIT.is_file():
        errors.append("auditoria-pdfs-colacao.json ausente")
    else:
        aud = json.loads(AUDIT.read_text(encoding="utf-8"))
        if not aud.get("itens"):
            errors.append("auditoria sem itens")
        for item in aud["itens"]:
            if item.get("fold_ok") is True:
                errors.append(f"auditoria {item.get('label')}: fold_ok true indevido")

    # Hashes das novas fontes
    for fontes_rel, md_rel in [
        (
            "provas/nordeste-lei-14133/capitais/2704302/fontes.json",
            "municipais/2704302/br-municipal-2704302-lei-organica.md",
        ),
        (
            "provas/nordeste-lei-14133/capitais/2800308/fontes.json",
            "municipais/2800308/br-municipal-2800308-lei-organica-1990.md",
        ),
        (
            "provas/nordeste-lei-14133/capitais/2800308/fontes-decreto-7178.json",
            "municipais/2800308/br-municipal-2800308-decreto-2023-06-12-7178.md",
        ),
        (
            "provas/nordeste-lei-14133/capitais/2304400/fontes-decreto-15317.json",
            "municipais/2304400/br-municipal-2304400-decreto-2022-05-06-15317.md",
        ),
    ]:
        fontes = json.loads((ROOT / fontes_rel).read_text(encoding="utf-8"))
        entry = fontes["fontes"][0]
        snap = ROOT / entry["arquivo"]
        if sha256_bytes(lzma.open(snap).read()) != entry["sha256_conteudo"]:
            errors.append(f"{fontes_rel}: sha snapshot divergiu")
        md = (ROOT / md_rel).read_text(encoding="utf-8")
        if sha256_bytes(md.encode()) != entry["sha256_markdown"]:
            errors.append(f"{md_rel}: sha markdown divergiu")
        if sha256_bytes(strip_note(md).encode()) != entry["sha256_corpo_markdown"]:
            errors.append(f"{md_rel}: sha corpo divergiu")

    nota = idx.get("nota", "")
    if "índices compartilhados" not in nota.lower() and "indices compartilhados" not in nota.lower():
        errors.append("index.nota deve declarar que não altera índices compartilhados")

    if errors:
        print("VERIFY FAIL:")
        for e in errors:
            print(" -", e)
        return 1
    print("VERIFY OK")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cmd", choices=["verify", "collect", "status"])
    p.add_argument("--force-id", default=None, help="recoleta um id mesmo se ok")
    args = p.parse_args(argv)
    if args.cmd == "verify":
        return cmd_verify()
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "collect":
        return cmd_collect(args.force_id)
    return 2


if __name__ == "__main__":
    sys.exit(main())
