"""Decretos federais 8.001–9.000 (issue #81): catálogo Senado DEC + coleta retomável.

Reconcili a faixa contra o catálogo oficial do Senado (tipo=DEC, espécie+número+data),
prioriza lacunas 8001–9000 e publica íntegras oficiais com cobertura fonte→Markdown.

Fontes:
- Amostra inicial Planalto (7 decretos já publicados neste lote).
- Lacunas: Câmara (publicação original via LexML), quando o HTML traz `.textoNorma`
  sem placeholders `<<ANEXO>>`/`<<TABELA>>`.

Subcomandos: fetch-catalog, reconcile, collect, fetch, ingest, build, verify.
"""
from __future__ import annotations

import argparse
import datetime
import json
import lzma
import re
import subprocess
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / "provas/federal-decretos-8001-9000"
FONTES_DIR = PROVAS / "fontes"
CATALOGO_DIR = PROVAS / "catalogo-senado"
LACUNAS = ROOT / "provas/federal-lacunas-catalogo"
MANIFESTO = PROVAS / "manifesto.json"
FONTES_JSON = PROVAS / "fontes.json"
PENDENCIAS = PROVAS / "PENDENCIAS-decretos.md"
DOCS_COLETADOS = PROVAS / "docs-coletados.json"
RECONCILIACAO = PROVAS / "catalogo-reconciliacao.json"
RESUME_STATE = PROVAS / "collect-resume.json"
CATALOGO_81 = LACUNAS / "catalogo-81-decretos-milhares.json"

UNKNOWN = nl.UNKNOWN
PLANALTO = nl.PLANALTO
CAMARA = nl.CAMARA
USER_AGENT = nl.USER_AGENT
CONTRACT_VERSION = nl.CONTRACT_VERSION
LOTE = "federal-decretos-8001-9000"
TITLE_PATTERN = r"^DECRETO N"
FAIXA = range(8001, 9001)
SENADO_DEC_YEARS = range(2013, 2018)
MESES = [
    "", "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
]
MESES_PT_URL = {
    1: "janeiro", 2: "fevereiro", 3: "marco", 4: "abril", 5: "maio", 6: "junho",
    7: "julho", 8: "agosto", 9: "setembro", 10: "outubro", 11: "novembro", 12: "dezembro",
}

# Amostra Planalto já publicada no lote inicial.
SEED_SOURCES = {
    "planalto-D8100": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/decreto/D8100.htm", file="D8100.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-D8300": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/decreto/D8300.htm", file="D8300.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-D8500": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/decreto/D8500.htm", file="D8500.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-D8600": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/decreto/D8600.htm", file="D8600.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-D8700": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/decreto/D8700.htm", file="D8700.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-D8800": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/decreto/D8800.htm", file="D8800.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-D8900": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/decreto/D8900.htm", file="D8900.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
}

SEED_DOCS = [
    dict(slug="br-federal-decreto-2013-09-04-8100", arquivo="federal/br-federal-decreto-2013-09-04-8100.md", fonte="planalto-D8100",
         norma=dict(tipo="decreto", numero="8100", data="2013-09-04", titulo="DECRETO Nº 8100, DE 4 DE SETEMBRO DE 2013", ementa="Decreto nº 8.100, de 4 de setembro de 2013.", denominacao=None),
         edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN, origem="seed-planalto"),
    dict(slug="br-federal-decreto-2014-08-29-8300", arquivo="federal/br-federal-decreto-2014-08-29-8300.md", fonte="planalto-D8300",
         norma=dict(tipo="decreto", numero="8300", data="2014-08-29", titulo="DECRETO Nº 8300, DE 29 DE AGOSTO DE 2014", ementa="Decreto nº 8.300, de 29 de agosto de 2014.", denominacao=None),
         edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN, origem="seed-planalto"),
    dict(slug="br-federal-decreto-2015-08-12-8500", arquivo="federal/br-federal-decreto-2015-08-12-8500.md", fonte="planalto-D8500",
         norma=dict(tipo="decreto", numero="8500", data="2015-08-12", titulo="DECRETO Nº 8500, DE 12 DE AGOSTO DE 2015", ementa="Decreto nº 8.500, de 12 de agosto de 2015.", denominacao=None),
         edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN, origem="seed-planalto"),
    dict(slug="br-federal-decreto-2015-12-18-8600", arquivo="federal/br-federal-decreto-2015-12-18-8600.md", fonte="planalto-D8600",
         norma=dict(tipo="decreto", numero="8600", data="2015-12-18", titulo="DECRETO Nº 8600, DE 18 DE DEZEMBRO DE 2015", ementa="Decreto nº 8.600, de 18 de dezembro de 2015.", denominacao=None),
         edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN, origem="seed-planalto"),
    dict(slug="br-federal-decreto-2016-03-30-8700", arquivo="federal/br-federal-decreto-2016-03-30-8700.md", fonte="planalto-D8700",
         norma=dict(tipo="decreto", numero="8700", data="2016-03-30", titulo="DECRETO Nº 8700, DE 30 DE MARÇO DE 2016", ementa="Decreto nº 8.700, de 30 de março de 2016.", denominacao=None),
         edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN, origem="seed-planalto"),
    dict(slug="br-federal-decreto-2016-07-06-8800", arquivo="federal/br-federal-decreto-2016-07-06-8800.md", fonte="planalto-D8800",
         norma=dict(tipo="decreto", numero="8800", data="2016-07-06", titulo="DECRETO Nº 8800, DE 6 DE JULHO DE 2016", ementa="Decreto nº 8.800, de 6 de julho de 2016.", denominacao=None),
         edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN, origem="seed-planalto"),
    dict(slug="br-federal-decreto-2016-11-10-8900", arquivo="federal/br-federal-decreto-2016-11-10-8900.md", fonte="planalto-D8900",
         norma=dict(tipo="decreto", numero="8900", data="2016-11-10", titulo="DECRETO Nº 8900, DE 10 DE NOVEMBRO DE 2016", ementa="Decreto nº 8.900, de 10 de novembro de 2016.", denominacao=None),
         edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN, origem="seed-planalto"),
]


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def load_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def parse_senado_date(value: str) -> str:
    day, month, year = value.split("/")
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def titulo_decreto(numero: str, data: str) -> str:
    d = datetime.date.fromisoformat(data)
    return f"DECRETO Nº {numero}, DE {d.day} DE {MESES[d.month]} DE {d.year}"


def slug_for(data: str, numero: str) -> str:
    return f"br-federal-decreto-{data}-{numero}"


def arquivo_for(data: str, numero: str) -> str:
    return f"federal/{slug_for(data, numero)}.md"


def fonte_key_camara(numero: str) -> str:
    return f"camara-D{numero}"


def fonte_key_planalto(numero: str) -> str:
    return f"planalto-D{numero}"


def snapshot_path_for(file_name: str) -> Path:
    return FONTES_DIR / (file_name + ".xz")


def planalto_url_candidates(numero: str, data: str) -> list[str]:
    """URLs candidatas Planalto por ato/ano; não prova ausência se todas falharem."""
    year = int(data[:4])
    if 2011 <= year <= 2014:
        atos = ["_ato2011-2014", "_Ato2011-2014"]
    elif 2015 <= year <= 2018:
        atos = ["_ato2015-2018", "_Ato2015-2018"]
    elif 2019 <= year <= 2022:
        atos = ["_ato2019-2022", "_Ato2019-2022"]
    else:
        atos = [f"_ato{year}-{year}"]
    forms = [f"D{numero}", f"d{numero}"]
    out: list[str] = []
    seen: set[str] = set()
    for ato in atos:
        for form in forms:
            for folder in ("decreto", "Decreto"):
                url = f"https://www.planalto.gov.br/ccivil_03/{ato}/{year}/{folder}/{form}.htm"
                if url not in seen:
                    seen.add(url)
                    out.append(url)
    return out


def curl_get(url: str, dest: Path, max_time: int = 90) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    header_file = dest.with_suffix(dest.suffix + ".headers")
    captured = now_utc()
    proc = subprocess.run([
        "curl", "--silent", "--show-error", "--location", "--http1.1",
        "--proto", "=https", "--proto-redir", "=https",
        "--connect-timeout", "30", "--max-time", str(max_time),
        "--max-filesize", str(64 * 1024 * 1024),
        "--user-agent", USER_AGENT, "--dump-header", str(header_file),
        "--write-out", "%{http_code} %{url_effective}",
        "--output", str(dest), url,
    ], capture_output=True, text=True)
    record = dict(url=url, capturado_em=captured, curl_exit=proc.returncode, user_agent=USER_AGENT)
    if proc.returncode == 0:
        status, _, effective = proc.stdout.partition(" ")
        record.update(http_status=int(status), url_final=effective)
        data = dest.read_bytes()
        record.update(bytes=len(data), sha256=nl.sha256(data), sha256_conteudo=nl.content_sha256(data))
        if header_file.is_file():
            raw_headers = header_file.read_bytes().decode("latin-1").replace("\r\n", "\n")
            final_block = [b for b in raw_headers.split("\n\n") if b.strip()][-1:] or [""]
            for line in final_block[0].splitlines():
                name, _, value = line.partition(":")
                if name.lower() in ("last-modified", "etag", "content-type", "date"):
                    record["cabecalho_" + name.lower().replace("-", "_")] = value.strip()
        looks_like_gateway = b"504 Gateway Time-out" in data[:400] or b"<title>5" in data[:400]
        record["utilizavel"] = status == "200" and not looks_like_gateway and len(data) > 1000
        if not record["utilizavel"]:
            record["motivo"] = f"resposta HTTP {status} sem conteúdo utilizável ({len(data)} bytes)"
    else:
        record.update(utilizavel=False, motivo=(proc.stderr or proc.stdout or "curl failed")[-500:])
    header_file.unlink(missing_ok=True)
    return record


def dou_aviso_from_html(data: bytes, charset: str) -> str | None:
    text = nl.decode(data, charset)
    m = re.search(r"Este texto não substitui.{0,500}?(?:</(?:p|font|small)>|$)", text, flags=re.I | re.S)
    if not m:
        return None
    plain = re.sub(r"<[^>]+>", " ", m.group(0))
    plain = plain.replace("\xa0", " ").replace("&nbsp;", " ")
    plain = re.sub(r"\s+", " ", plain).strip()
    plain = re.sub(r"\s+\*.*$", "", plain).strip()
    if not plain.lower().startswith("este texto não substitui"):
        return None
    return plain or None


def local_decretos_faixa() -> dict[int, str]:
    pat = re.compile(r"^br-federal-decreto-(\d{4})-\d{2}-\d{2}-(\d+)(?:-.*)?\.md$")
    out = {}
    for path in (ROOT / "federal").glob("br-federal-decreto-*.md"):
        m = pat.match(path.name)
        if not m:
            continue
        year, num = int(m.group(1)), int(m.group(2))
        if year >= 1991 and num in FAIXA:
            out[num] = path.name
    return out


def load_senado_dec_identidades() -> list[dict]:
    items = []
    for year in SENADO_DEC_YEARS:
        path = CATALOGO_DIR / f"DEC-{year}.json"
        if not path.is_file():
            raise SystemExit(f"catálogo Senado ausente: {path} (rode fetch-catalog)")
        data = json.loads(path.read_text(encoding="utf-8"))
        docs = data["ListaDocumento"]["documentos"]["documento"]
        if isinstance(docs, dict):
            docs = [docs]
        meta = data["ListaDocumento"].get("Metadados") or {}
        for d in docs:
            if d.get("tipo") != "DEC-n" or not d.get("numero"):
                # DEC-sn e demais espécies ficam registrados à parte; não são lacunas da faixa numerada.
                continue
            numero = str(d["numero"])
            if not numero.isdigit() or int(numero) not in FAIXA:
                continue
            complemento = d.get("complemento") or d.get("sequencia") or ""
            items.append(dict(
                especie="DEC-n",
                numero=numero,
                complemento=str(complemento) if complemento not in (None, "") else "",
                data=parse_senado_date(d["dataassinatura"]),
                senado_id=str(d["id"]),
                norma=d.get("norma"),
                normaNome=d.get("normaNome"),
                ementa=d.get("ementa") or "",
                ano_catalogo=year,
                metadados_versao=meta.get("Versao"),
            ))
    # identidade oficial: espécie + número/complemento + data
    by_key = {}
    for it in items:
        key = (it["especie"], it["numero"], it["complemento"], it["data"])
        by_key[key] = it
    return [by_key[k] for k in sorted(by_key, key=lambda x: (int(x[1]), x[2], x[3]))]


def fetch_catalog() -> None:
    CATALOGO_DIR.mkdir(parents=True, exist_ok=True)
    registry = {}
    for year in SENADO_DEC_YEARS:
        url = f"https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=DEC&ano={year}"
        dest = CATALOGO_DIR / f"DEC-{year}.json"
        rec = curl_get(url, dest, max_time=120)
        if not rec.get("utilizavel"):
            raise SystemExit(f"falha ao capturar DEC/{year}: {rec.get('motivo') or rec}")
        raw = dest.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        docs = data["ListaDocumento"]["documentos"]["documento"]
        if isinstance(docs, dict):
            docs = [docs]
        registry[str(year)] = dict(
            url=url,
            capturado_em=rec["capturado_em"],
            http_status=rec["http_status"],
            sha256=nl.sha256(raw),
            bytes=len(raw),
            records=len(docs),
            metadados=data["ListaDocumento"].get("Metadados"),
            snapshot=str(dest.relative_to(ROOT)),
        )
        print(f"DEC/{year}: {len(docs)} registros sha={registry[str(year)]['sha256'][:16]}…", flush=True)
        time.sleep(0.4)
    write_json(CATALOGO_DIR / "registry.json", dict(gerado_em=now_utc(), anos=registry))
    print("fetch-catalog ok", flush=True)


def reconcile() -> dict:
    identidades = load_senado_dec_identidades()
    local = local_decretos_faixa()
    presentes = []
    ausentes = []
    for it in identidades:
        n = int(it["numero"])
        row = dict(**it)
        if n in local:
            row["estado"] = "presente-arquivo-local"
            row["arquivo"] = f"federal/{local[n]}"
            presentes.append(row)
        else:
            row["estado"] = "ausente-arquivo-canonic"
            row["arquivo"] = None
            ausentes.append(row)
    # Inteiros da faixa sem identidade no catálogo (não marcar como lacuna oficial).
    catalog_nums = {int(it["numero"]) for it in identidades}
    sem_identidade = [n for n in FAIXA if n not in catalog_nums]
    result = dict(
        gerado_em=now_utc(),
        issue=81,
        fonte_catalogo="https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=DEC&ano=AAAA",
        anos=list(SENADO_DEC_YEARS),
        criterio_identidade="especie+numero/complemento+data",
        totais=dict(
            identidades_catalogo=len(identidades),
            presentes_local=len(presentes),
            ausentes_local=len(ausentes),
            inteiros_faixa_sem_identidade_catalogo=len(sem_identidade),
            arquivos_locais_faixa=len(local),
        ),
        inteiros_sem_identidade_catalogo=sem_identidade,
        ausentes=ausentes,
        limites=[
            "Ausência de arquivo canônico não prova inexistência fora do catálogo capturado.",
            "Falha de transporte na coleta não implica inexistência da norma.",
            "DEC-sn (não numerados) ficam fora do denominador da faixa 8001–9000.",
            "Presença de arquivo não certifica íntegra/atualização nem vigência.",
        ],
    )
    write_json(RECONCILIACAO, result)
    # Atualiza mapa por milhar com denominador oficial da faixa prioritária.
    cat81 = load_json(CATALOGO_81, default={})
    issue = cat81.get("issue_81") or {}
    faixas = issue.get("faixas") or []
    for f in faixas:
        if f.get("faixa") == "8001-9000":
            f["presentes"] = len(local)
            f["denominador_oficial_senado_DEC_n"] = len(identidades)
            f["ausentes_vs_catalogo"] = len(ausentes)
            f["observacao"] = (
                "Denominador oficial: identidades DEC-n do Senado 2013–2017 com número em 8001–9000 "
                "(espécie+número/complemento+data). O denominador 1000 por milhar permanece convenção de faixa."
            )
            f["reconciliacao"] = str(RECONCILIACAO.relative_to(ROOT))
    issue["faixas"] = faixas
    issue["nota_lote"] = (
        f"Reconciliação Senado DEC: {len(identidades)} identidades; {len(presentes)} presentes; "
        f"{len(ausentes)} ausentes no acervo. Coleta retomável via `collect`."
    )
    issue["limites"] = [
        "Presença de arquivo não certifica íntegra/atualização.",
        "Ausência de arquivo não prova inexistência do número fora do catálogo.",
        "Coleta prioriza 8001–9000 com retomada; demais milhares pós-1991 seguem pendentes.",
    ]
    cat81["issue_81"] = issue
    cat81["atualizado_em"] = now_utc()
    write_json(CATALOGO_81, cat81)
    print(
        f"reconcile: catalogo={len(identidades)} presentes={len(presentes)} "
        f"ausentes={len(ausentes)} sem_identidade={len(sem_identidade)}",
        flush=True,
    )
    return result


def load_docs_coletados() -> list[dict]:
    return load_json(DOCS_COLETADOS, default=[]) or []


def all_sources() -> dict:
    fontes_meta = load_json(FONTES_JSON, default={}) or {}
    sources = dict(SEED_SOURCES)
    for doc in load_docs_coletados():
        key = doc["fonte"]
        if key in sources:
            continue
        sources[key] = dict(
            url=doc["fonte_url"],
            file=doc["fonte_file"],
            orgao=doc.get("fonte_orgao") or CAMARA,
            formato="html",
            charset=doc.get("charset") or "utf-8",
        )
    # fontes.json pode ter chaves extras já ingeridas
    for key, rec in fontes_meta.items():
        if key not in sources and rec.get("snapshot"):
            sources[key] = dict(
                url=rec["url"],
                file=Path(rec["snapshot"]).name.replace(".xz", ""),
                orgao=rec.get("orgao") or CAMARA,
                formato=rec.get("formato") or "html",
                charset=rec.get("charset") or ("cp1252" if key.startswith("planalto-") else "utf-8"),
            )
    return sources


def all_docs() -> list[dict]:
    docs = list(SEED_DOCS)
    seen = {d["slug"] for d in docs}
    for doc in load_docs_coletados():
        if doc["slug"] in seen:
            continue
        docs.append(dict(
            slug=doc["slug"],
            arquivo=doc["arquivo"],
            fonte=doc["fonte"],
            senado_id=doc.get("senado_id"),
            norma=dict(
                tipo="decreto",
                numero=doc["numero"],
                data=doc["data"],
                titulo=doc["titulo"],
                ementa=doc.get("ementa") or "",
                denominacao=None,
            ),
            edicao=dict(tipo="historica", identidade=doc.get("identidade") or "camara", integral=UNKNOWN),
            situacao=dict(valor="nao-informada"),
            title_pattern=TITLE_PATTERN,
            origem=doc.get("origem") or "collect-camara",
        ))
        seen.add(doc["slug"])
    return docs


# Compat: testes legados importam SOURCES/DOCS
SOURCES = SEED_SOURCES
DOCS = SEED_DOCS


def _extract_camara_publicacao_urls(html: str) -> list[str]:
    links = []
    seen = set()
    for raw in re.findall(r"https?://[^\"\s<>]+", html):
        L = raw.replace("&amp;", "&")
        low = L.lower()
        if "camara" not in low or "publicacaooriginal" not in low:
            continue
        if "linker.lexml" in low:
            continue
        if L.startswith("http://"):
            L = "https://" + L[len("http://"):]
        if L not in seen:
            seen.add(L)
            links.append(L)
    return links


def resolve_camara_url(numero: str, data: str, attempts: int = 3) -> str | None:
    """Resolve URL Câmara (publicação original) via LexML; retenta falhas transitórias."""
    urn = f"urn:lex:br:federal:decreto:{data};{numero}"
    dest = Path("/tmp") / f"lexml-dec-{numero}.html"
    last_err = None
    for i in range(max(1, attempts)):
        rec = curl_get(f"https://www.lexml.gov.br/urn/{urn}", dest, max_time=60)
        if not rec.get("utilizavel"):
            last_err = rec.get("motivo") or f"HTTP {rec.get('http_status')}"
            time.sleep(0.4 * (i + 1))
            continue
        html = dest.read_text(encoding="utf-8", errors="replace")
        if re.search(r"urn não encontrada", html, re.I):
            return None
        links = _extract_camara_publicacao_urls(html)
        if links:
            return links[0]
        last_err = "LexML sem link Câmara publicacaooriginal"
        time.sleep(0.3 * (i + 1))
    return None


def resolve_planalto_url(numero: str, data: str) -> tuple[str, bytes, dict] | None:
    """Tenta URLs Planalto candidatas; None = falha de transporte/fonte, não ausência normativa."""
    for url in planalto_url_candidates(numero, data):
        dest = Path("/tmp") / f"planalto-D{numero}.htm"
        rec = curl_get(url, dest, max_time=90)
        if not rec.get("utilizavel"):
            continue
        data_bytes = dest.read_bytes()
        plain = nl.decode(data_bytes, "cp1252")
        if re.search(r"n[aã]o\s+encontrad", plain[:2500], re.I):
            continue
        if not re.search(r"DECRETO\s+N", plain, re.I):
            continue
        if has_annex_placeholder(plain):
            continue
        # identidade numérica no título oficial
        m = re.search(r"DECRETO\s+N[^\n]{0,60}", plain, re.I)
        if not m:
            continue
        digits = re.sub(r"\D", "", m.group(0).split(",")[0])
        if not digits.endswith(str(int(numero))):
            continue
        if not re.search(r"(?:Art\.|Artigo)\s*\d", plain, re.I):
            continue
        return url, data_bytes, rec
    return None


def has_annex_placeholder(text: str) -> bool:
    return bool(re.search(r"<<\s*(ANEXO|TABELA)\s*>>", text, flags=re.I))


def trim_camara_decreto_blocks(blocks: list[str], numero: str) -> list[str]:
    num = str(int(numero))
    title_re = re.compile(r"^DECRETO N", re.I)
    start = None
    for i, block in enumerate(blocks):
        plain = nl.md_plain(block, True).strip()
        if not title_re.match(plain):
            continue
        if "Legislação Informatizada" in plain:
            continue
        digits = re.sub(r"\D", "", plain.split(",")[0])
        if digits.endswith(num) or num in digits:
            start = i
            break
    if start is None:
        raise RuntimeError(f"decreto {numero}: título não encontrado")
    end = None
    for i in range(start + 1, len(blocks)):
        plain = nl.md_plain(blocks[i], True).strip()
        if re.match(r"^Este texto não substitui", plain, re.I):
            end = i
            break
        if re.match(r"^Publicação\s*:", plain, re.I):
            end = i
            break
        if re.match(r"^Diário Oficial", plain, re.I):
            end = i
            break
        if re.match(r"^Coleção de Leis do Brasil", plain, re.I):
            end = i
            break
    if end is None:
        end = len(blocks)
    out = blocks[start:end]
    if not out:
        raise RuntimeError(f"decreto {numero}: recorte vazio")
    joined = "\n".join(nl.md_plain(b, True) for b in out)
    if has_annex_placeholder(joined):
        raise RuntimeError(f"decreto {numero}: placeholder de anexo/tabela na íntegra")
    if not re.search(r"(?:Art\.|Artigo)\s*", joined, re.I):
        raise RuntimeError(f"decreto {numero}: nenhum artigo no recorte")
    return out


def convert_camara_decreto(data: bytes, url: str, numero: str) -> tuple[list[str], str, BeautifulSoup]:
    conv = nl.convert_html(data, "utf-8", url)
    blocks = trim_camara_decreto_blocks(conv.blocks, numero)
    body = "\n\n".join(blocks) + "\n"
    soup = BeautifulSoup(data.decode("utf-8"), "lxml")
    title = soup.select_one("#content > h1")
    region = soup.select_one(".textoNorma")
    if title is None or region is None:
        raise RuntimeError(f"decreto {numero}: região normativa oficial ausente")
    if has_annex_placeholder(region.get_text(" ")):
        raise RuntimeError(f"decreto {numero}: placeholder de anexo no textoNorma")
    source_text = title.get_text(" ") + region.get_text(" ")
    if nl.strip_fold(source_text) != nl.strip_fold(nl.md_text_all(body)):
        raise RuntimeError(f"decreto {numero}: cobertura h1+textoNorma diverge do Markdown")
    return blocks, body, soup


def collect(limit: int | None = None, sleep_s: float = 0.35) -> None:
    recon = reconcile()
    ausentes = recon["ausentes"]
    state = load_json(RESUME_STATE, default={"done": {}, "failed": {}, "updated_em": None}) or {
        "done": {}, "failed": {}, "updated_em": None,
    }
    coletados = {d["numero"]: d for d in load_docs_coletados()}
    fontes = load_json(FONTES_JSON, default={}) or {}
    pending = []
    for it in ausentes:
        n = it["numero"]
        if n in coletados or n in state.get("done", {}):
            continue
        pending.append(it)
    if limit is not None:
        pending = pending[:limit]
    print(f"collect: pendentes nesta execução={len(pending)} (ausentes totais={len(ausentes)})", flush=True)
    ok = 0
    for it in pending:
        numero, data = it["numero"], it["data"]
        try:
            cam_url = resolve_camara_url(numero, data)
            camara_err = None
            if cam_url:
                try:
                    key = fonte_key_camara(numero)
                    file_name = f"camara-D{numero}.htm"
                    dest = Path("/tmp") / file_name
                    rec = curl_get(cam_url, dest, max_time=90)
                    if not rec.get("utilizavel"):
                        raise RuntimeError(rec.get("motivo") or f"HTTP {rec.get('http_status')}")
                    data_bytes = dest.read_bytes()
                    blocks, body, soup = convert_camara_decreto(data_bytes, cam_url, numero)
                    head = nl.md_plain(blocks[0], True)
                    digits = re.sub(r"\D", "", head.split(",")[0])
                    if not digits.endswith(str(int(numero))):
                        raise RuntimeError(f"identidade numérica falhou: {head[:120]!r}")
                    snap = snapshot_path_for(file_name)
                    snap.parent.mkdir(parents=True, exist_ok=True)
                    snap.write_bytes(lzma.compress(data_bytes, preset=9 | lzma.PRESET_EXTREME))
                    dou = dou_aviso_from_html(data_bytes, "utf-8")
                    fontes[key] = dict(
                        orgao=CAMARA,
                        formato="html",
                        url=cam_url,
                        capturado_em=rec["capturado_em"],
                        user_agent=USER_AGENT,
                        http_status=rec["http_status"],
                        url_final=rec.get("url_final") or cam_url,
                        bytes=len(data_bytes),
                        sha256=nl.sha256(data_bytes),
                        sha256_conteudo=nl.content_sha256(data_bytes),
                        utilizavel=True,
                        dou_aviso=dou,
                        snapshot=str(snap.relative_to(ROOT)),
                        sha256_snapshot_armazenado=nl.sha256(snap.read_bytes()),
                        charset="utf-8",
                        senado_id=it["senado_id"],
                        lexml_urn=f"urn:lex:br:federal:decreto:{data};{numero}",
                    )
                    doc_row = dict(
                        slug=slug_for(data, numero),
                        arquivo=arquivo_for(data, numero),
                        fonte=key,
                        fonte_url=cam_url,
                        fonte_file=file_name,
                        fonte_orgao=CAMARA,
                        charset="utf-8",
                        numero=numero,
                        data=data,
                        titulo=titulo_decreto(numero, data),
                        ementa=it.get("ementa") or "",
                        senado_id=it["senado_id"],
                        identidade="camara",
                        origem="collect-camara-lexml",
                        capturado_em=rec["capturado_em"],
                    )
                    coletados[numero] = doc_row
                    state.setdefault("done", {})[numero] = dict(
                        slug=doc_row["slug"], capturado_em=rec["capturado_em"], url=cam_url, via="camara",
                    )
                    state.get("failed", {}).pop(numero, None)
                    ok += 1
                    print(f"OK {numero} {data} camara bytes={len(data_bytes)} blocos={len(blocks)}", flush=True)
                    state["updated_em"] = now_utc()
                    write_json(RESUME_STATE, state)
                    write_json(DOCS_COLETADOS, [coletados[k] for k in sorted(coletados, key=lambda x: int(x))])
                    write_json(FONTES_JSON, fontes)
                    time.sleep(sleep_s)
                    continue
                except Exception as exc:  # noqa: BLE001 — tenta Planalto sem inferir ausência
                    camara_err = f"{type(exc).__name__}: {exc}"
            else:
                camara_err = "URL Câmara não encontrada no LexML"

            pl = resolve_planalto_url(numero, data)
            if not pl:
                raise RuntimeError(
                    f"falha de fonte/transporte (Câmara: {camara_err}; Planalto: sem URL utilizável). "
                    "Não interpreta ausência normativa."
                )
            pl_url, data_bytes, rec = pl
            key = fonte_key_planalto(numero)
            # Evita colidir com seeds D8100.htm etc.; coletados usam prefixo planalto-.
            file_name = f"planalto-D{numero}.htm"
            snap = snapshot_path_for(file_name)
            snap.parent.mkdir(parents=True, exist_ok=True)
            snap.write_bytes(lzma.compress(data_bytes, preset=9 | lzma.PRESET_EXTREME))
            dou = dou_aviso_from_html(data_bytes, "cp1252")
            fontes[key] = dict(
                orgao=PLANALTO,
                formato="html",
                url=pl_url,
                capturado_em=rec["capturado_em"],
                user_agent=USER_AGENT,
                http_status=rec["http_status"],
                url_final=rec.get("url_final") or pl_url,
                bytes=len(data_bytes),
                sha256=nl.sha256(data_bytes),
                sha256_conteudo=nl.content_sha256(data_bytes),
                utilizavel=True,
                dou_aviso=dou,
                snapshot=str(snap.relative_to(ROOT)),
                sha256_snapshot_armazenado=nl.sha256(snap.read_bytes()),
                charset="cp1252",
                senado_id=it["senado_id"],
                lexml_urn=f"urn:lex:br:federal:decreto:{data};{numero}",
                fallback_de=camara_err,
            )
            doc_row = dict(
                slug=slug_for(data, numero),
                arquivo=arquivo_for(data, numero),
                fonte=key,
                fonte_url=pl_url,
                fonte_file=file_name,
                fonte_orgao=PLANALTO,
                charset="cp1252",
                numero=numero,
                data=data,
                titulo=titulo_decreto(numero, data),
                ementa=it.get("ementa") or "",
                senado_id=it["senado_id"],
                identidade="planalto",
                origem="collect-planalto-fallback",
                capturado_em=rec["capturado_em"],
            )
            coletados[numero] = doc_row
            state.setdefault("done", {})[numero] = dict(
                slug=doc_row["slug"], capturado_em=rec["capturado_em"], url=pl_url, via="planalto",
            )
            state.get("failed", {}).pop(numero, None)
            ok += 1
            print(f"OK {numero} {data} planalto bytes={len(data_bytes)}", flush=True)
        except Exception as exc:  # noqa: BLE001 — registrar falha retomável sem abortar o lote
            state.setdefault("failed", {})[numero] = dict(
                erro=str(exc)[:500],
                em=now_utc(),
                data=data,
                senado_id=it.get("senado_id"),
                classe=type(exc).__name__,
            )
            print(f"FAIL {numero}: {type(exc).__name__}: {exc}", flush=True)
        state["updated_em"] = now_utc()
        write_json(RESUME_STATE, state)
        write_json(DOCS_COLETADOS, [coletados[k] for k in sorted(coletados, key=lambda x: int(x))])
        write_json(FONTES_JSON, fontes)
        time.sleep(sleep_s)
    print(f"collect fim: ok={ok} done={len(state.get('done', {}))} failed={len(state.get('failed', {}))}", flush=True)


def snapshot_path(key: str) -> Path:
    sources = all_sources()
    return FONTES_DIR / (sources[key]["file"] + ".xz")


def read_snapshot(key: str) -> bytes:
    return lzma.decompress(snapshot_path(key).read_bytes())


def write_snapshot(key: str, data: bytes) -> None:
    path = snapshot_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME))


def fetch(dest: Path) -> dict:
    """Fetch apenas das fontes seed Planalto (amostra inicial)."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, spec in SEED_SOURCES.items():
        target = dest / spec["file"]
        records[key] = curl_get(spec["url"], target)
        print(f"{key}: {records[key].get('http_status')} {records[key].get('bytes')} utilizável={records[key]['utilizavel']}", flush=True)
    write_json(dest / "fetch.json", records)
    return records


def ingest_capture(capture_dir: Path, capturado_em: str | None = None) -> dict:
    capture_dir = Path(capture_dir)
    fontes = load_json(FONTES_JSON, default={}) or {}
    stamp = capturado_em
    if stamp is None:
        stamp_file = capture_dir / "capturado_em.txt"
        stamp = stamp_file.read_text(encoding="utf-8").strip() if stamp_file.exists() else now_utc()
    for key, spec in SEED_SOURCES.items():
        raw_path = capture_dir / spec["file"]
        if not raw_path.is_file():
            raise SystemExit(f"captura ausente: {raw_path}")
        data = raw_path.read_bytes()
        write_snapshot(key, data)
        fontes[key] = dict(
            orgao=spec["orgao"], formato=spec["formato"], url=spec["url"],
            capturado_em=stamp, user_agent=USER_AGENT, http_status=200,
            url_final=spec["url"], bytes=len(data), sha256=nl.sha256(data),
            sha256_conteudo=nl.content_sha256(data), utilizavel=True,
            dou_aviso=dou_aviso_from_html(data, spec["charset"]),
            snapshot=str(snapshot_path(key).relative_to(ROOT)),
            sha256_snapshot_armazenado=nl.sha256(snapshot_path(key).read_bytes()),
            charset=spec["charset"],
        )
        print(f"ingest {key}: {fontes[key]['bytes']} sha256={fontes[key]['sha256'][:16]}…", flush=True)
    write_json(FONTES_JSON, fontes)
    return fontes


def load_fontes() -> dict:
    return json.loads(FONTES_JSON.read_text(encoding="utf-8"))


def load_sources_bytes() -> dict:
    return {key: read_snapshot(key) for key in all_sources() if key in load_fontes()}


def edition_note(doc: dict, rec: dict, conv_stats: dict, images: list) -> str:
    edicao = doc["edicao"]["tipo"]
    label = "Edição consolidada" if edicao == "consolidada" else "Edição histórica"
    orgao = rec["orgao"]
    lines = [
        (f"**{label} — {orgao}.** Fonte: {rec['url']} "
         f"(capturada em {rec['capturado_em']}, SHA-256 da fonte `{rec['sha256']}`, "
         f"SHA-256 do conteúdo sem script de proteção `{rec['sha256_conteudo']}`). "
         f"Snapshot: `{rec['snapshot']}`. O acervo não certifica vigência."),
    ]
    if doc.get("origem", "").startswith("collect-camara") or rec.get("orgao") == CAMARA:
        lines.append(
            "Página oficial da Câmara (publicação original). Notas, remissões, tabelas e trechos "
            "riscados da região normativa foram preservados literalmente."
        )
    else:
        lines.append(
            "Página oficial do Planalto. Notas, remissões, tabelas e trechos riscados da "
            "página foram preservados literalmente. Não é republicação isolada do DOU."
        )
    lines.append(
        "Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial "
        "mantém riscada; não é dispositivo em vigor. A presença deste arquivo no acervo "
        "não indica vigência."
    )
    if rec.get("dou_aviso"):
        lines.append(rec["dou_aviso"])
    lines.append(
        f"Prova de cobertura fonte→Markdown e reconversão: "
        f"`provas/{LOTE}/reconciliacao-{doc['slug']}.json`."
    )
    if images:
        lines.append(
            f"{len(images)} imagem(ns) institucional(is) do cabeçalho da página foram omitidas do "
            "Markdown (brasão/logotipo sem texto jurídico)."
        )
    if conv_stats.get("tabelas_markdown") or conv_stats.get("tabelas_html"):
        n = conv_stats["tabelas_markdown"] + conv_stats["tabelas_html"]
        lines.append(f"{n} tabela(s) da fonte foram convertidas para Markdown/`<table>` no corpo.")
    return nl.note_block(lines)


def build_document_planalto(doc: dict, data: bytes, rec: dict):
    spec = all_sources()[doc["fonte"]]
    conv = nl.convert_html(data, spec["charset"], spec["url"])
    body = nl.blocks_to_markdown(conv.blocks, doc["title_pattern"])
    # Python versions differ on urljoin(base, '#'). An empty fragment has
    # no distinct target; canonicalize it without changing named anchors.
    body = re.sub(r'(\]\(https?://[^)\s]+)#\)', r'\1)', body)
    src = nl.strip_fold(nl.source_text_chars_from_html(data, spec["charset"]))
    md_all = nl.strip_fold(nl.md_text_all(body))
    coverage_ok = src == md_all
    _arts, order = nl.split_articles(conv.blocks)
    anexos = sum(1 for b in conv.blocks if re.match(r"^ANEXO\b", nl.md_plain(b, True).strip(), re.I))
    note = edition_note(doc, rec, conv.stats, conv.images)
    if "# " not in body:
        raise SystemExit(f"{doc['slug']}: título H1 ausente após conversão")
    title_at = body.index("# ") if body.startswith("# ") else body.index("\n# ") + 1
    title_end = body.index("\n\n", title_at)
    head, rest = body[:title_end], body[title_end + 2:]
    published_body = head + "\n\n" + note + "\n\n" + rest
    if not published_body.endswith("\n"):
        published_body += "\n"
    return published_body, coverage_ok, conv, order, anexos, "planalto-fullpage"


def build_document_camara(doc: dict, data: bytes, rec: dict):
    blocks, body, soup = convert_camara_decreto(data, rec["url"], doc["norma"]["numero"])
    # Fake converter stats for note/manifest
    class _C:
        pass
    conv = _C()
    conv.stats = dict(tabelas_markdown=0, tabelas_html=body.lower().count("<table"), trechos_riscados=body.count("~~"))
    conv.images = []
    conv.tables = []
    conv.blocks = blocks
    _arts, order = nl.split_articles(blocks)
    anexos = sum(1 for b in blocks if re.match(r"^ANEXO\b", nl.md_plain(b, True).strip(), re.I))
    note = edition_note(doc, rec, conv.stats, conv.images)
    if not body.startswith("# "):
        first_line = body.split("\n", 1)[0].lstrip("# ").strip()
        if first_line.upper().startswith("DECRETO"):
            first, _, rest_body = body.partition("\n\n")
            body = "# " + first.lstrip("# ").strip() + ("\n\n" + rest_body if rest_body else "\n")
    if not body.startswith("# "):
        raise SystemExit(f"{doc['slug']}: título H1 ausente após conversão Câmara")
    title_end = body.index("\n\n") if "\n\n" in body else len(body)
    head, rest = body[:title_end], body[title_end + 2:] if title_end < len(body) else ""
    published_body = head + "\n\n" + note + "\n\n" + rest
    if not published_body.endswith("\n"):
        published_body += "\n"
    coverage_ok = True  # enforced inside convert_camara_decreto
    return published_body, coverage_ok, conv, order, anexos, "camara-textoNorma"


def build_document(doc: dict, data: bytes, rec: dict):
    if doc.get("origem", "").startswith("collect-camara") or (rec.get("orgao") == CAMARA and doc["fonte"].startswith("camara-")):
        published_body, coverage_ok, conv, order, anexos, metodo = build_document_camara(doc, data, rec)
    else:
        published_body, coverage_ok, conv, order, anexos, metodo = build_document_planalto(doc, data, rec)

    norma = doc["norma"]
    edicao_tipo = doc["edicao"]["tipo"]
    identidade = doc["edicao"]["identidade"]
    edicao_id = f"{doc['slug']}@historica-{identidade}"
    edicao_integral = UNKNOWN
    spec_orgao = rec["orgao"]
    meta = dict(
        id=doc["slug"],
        norma_id=doc["slug"],
        norma_tipo=norma["tipo"],
        norma_numero=norma["numero"],
        norma_data=norma["data"],
        titulo=norma["titulo"],
        esfera="federal",
        edicao_id=edicao_id,
        edicao_tipo=edicao_tipo,
        edicao_integral=edicao_integral,
        edicao_relacionada=None,
        fonte_orgao=spec_orgao,
        fonte_url=rec["url"],
        fonte_formato="html",
        fonte_conferencia="nenhuma",
        capturado_em=rec["capturado_em"],
        sha256_fonte=rec["sha256"],
        situacao=doc["situacao"]["valor"],
        situacao_fundamento=UNKNOWN,
        vigencia_certificada=False,
        texto_riscado=conv.stats["trechos_riscados"] > 0,
        anexos_no_corpo=anexos,
        tabelas=conv.stats["tabelas_markdown"] + conv.stats["tabelas_html"],
        imagens_omitidas=len(conv.images),
        efeitos_diferidos="preservados-nas-notas-do-texto",
        sha256_markdown=nl.sha256(published_body.encode("utf-8")),
        manifesto=str(MANIFESTO.relative_to(ROOT)),
        contrato_versao=CONTRACT_VERSION,
    )
    errors = nl.validate_meta(meta, doc["slug"])
    if errors:
        raise SystemExit("metadados inválidos:\n" + "\n".join(errors))

    markdown = nl.render_frontmatter(meta) + published_body
    _, body_only = nl.parse_frontmatter(markdown)
    meta["sha256_markdown"] = nl.sha256(body_only.encode("utf-8"))
    markdown = nl.render_frontmatter(meta) + body_only

    if not coverage_ok:
        raise SystemExit(f"{doc['slug']}: cobertura fonte→Markdown falhou")

    proof = dict(
        documento=doc["slug"],
        fonte_principal=doc["fonte"],
        sha256_fonte_principal=rec["sha256"],
        sha256_conteudo=rec["sha256_conteudo"],
        capturado_em=rec["capturado_em"],
        url=rec["url"],
        snapshot=rec["snapshot"],
        sha256_snapshot_armazenado=rec["sha256_snapshot_armazenado"],
        fontes_conferencia=[],
        cobertura_texto=dict(
            descricao=(
                "planalto: texto integral da página == Markdown convertido; "
                "camara: h1+#textoNorma == Markdown após trim"
            ),
            equivalente=True,
            metodo=metodo,
        ),
        conversao=dict(
            **conv.stats,
            imagens=conv.images,
            tabelas=getattr(conv, "tables", []),
            blocos=len(conv.blocks),
            artigos=len(order),
            primeiros_artigos=order[:5],
            ultimos_artigos=order[-5:],
        ),
        identidade=dict(
            norma_id=doc["slug"],
            numero=norma["numero"],
            data=norma["data"],
            titulo_fonte=norma["titulo"],
            ementa=norma["ementa"],
            edicao=doc["edicao"],
            senado_id=doc.get("senado_id"),
        ),
        limites=[
            "Fonte única nesta entrega; fonte_conferencia=nenhuma.",
            "O acervo não certifica vigência.",
            "Imagens institucionais do cabeçalho foram omitidas; tabelas/notas/riscados preservados.",
            "Lote parcial da #81; demais milhares pós-1991 e falhas de coleta em PENDENCIAS/resume.",
        ],
    )
    entry = dict(
        id=doc["slug"],
        arquivo=doc["arquivo"],
        norma=norma,
        edicao=dict(tipo=edicao_tipo, integral=edicao_integral, identidade=identidade, edicao_id=edicao_id),
        situacao=doc["situacao"],
        fonte=dict(
            chave=doc["fonte"], orgao=spec_orgao, url=rec["url"], formato="html",
            capturado_em=rec["capturado_em"], sha256=rec["sha256"],
            sha256_conteudo=rec["sha256_conteudo"], snapshot=rec["snapshot"],
            sha256_snapshot_armazenado=rec["sha256_snapshot_armazenado"],
            dou_aviso=rec.get("dou_aviso"),
        ),
        prova=f"provas/{LOTE}/reconciliacao-{doc['slug']}.json",
        sha256_markdown=meta["sha256_markdown"],
        estrutura=dict(
            blocos=len(conv.blocks), artigos=len(order),
            tabelas=meta["tabelas"], anexos_no_corpo=anexos,
            imagens_omitidas=meta["imagens_omitidas"],
            texto_riscado=meta["texto_riscado"],
        ),
    )
    return markdown, proof, entry, conv


def write_pendencias(manifest_docs: list) -> str:
    recon = load_json(RECONCILIACAO, default={}) or {}
    state = load_json(RESUME_STATE, default={}) or {}
    lines = [
        "# Pendências — decretos pós-1991 (#81)",
        "",
        "Reconciliação oficial Senado DEC (espécie + número/complemento + data) na faixa 8001–9000.",
        f"Gerado em {now_utc()}. Não certifica vigência.",
        "",
        "## Publicadas neste lote",
        "",
        "| Número | Arquivo | Fonte |",
        "| --- | --- | --- |",
    ]
    for e in sorted(manifest_docs, key=lambda x: int(x["norma"]["numero"])):
        lines.append(f"| {e['norma']['numero']} | `{e['arquivo']}` | {e['fonte']['url']} |")
    ausentes = recon.get("ausentes") or []
    published = {e["norma"]["numero"] for e in manifest_docs}
    still = [a for a in ausentes if a["numero"] not in published]
    lines += [
        "",
        f"## Ausentes vs catálogo Senado DEC-n ({len(still)})",
        "",
        "Identidades do catálogo ainda sem Markdown canônico neste acervo.",
        "Falha de coleta/transporte não prova inexistência.",
        "",
        "| Número | Data | Senado | Estado coleta |",
        "| --- | --- | --- | --- |",
    ]
    failed = (state.get("failed") or {})
    for a in still[:200]:
        st = failed.get(a["numero"], {})
        estado = f"falha:{st.get('classe')}" if st else "pendente-coleta"
        lines.append(
            f"| {a['numero']} | {a['data']} | [{a['senado_id']}](https://legis.senado.leg.br/norma/{a['senado_id']}) | {estado} |"
        )
    if len(still) > 200:
        lines.append(f"| … | … | … | +{len(still) - 200} omitidos nesta tabela; ver `{RECONCILIACAO.relative_to(ROOT)}` |")
    lines += [
        "",
        "## Limites",
        "",
        "- Denominador oficial da faixa: catálogo Senado DEC-n 2013–2017.",
        "- Inteiros sem identidade no catálogo não são lacunas oficiais.",
        "- Coleta retomável: `python3 scripts/federal_decretos_8001_9000.py collect`.",
        "- Demais milhares pós-1991 fora de 8001–9000 permanecem para lotes seguintes.",
        "",
    ]
    return "\n".join(lines)


def compute(sources: dict, fontes: dict):
    docs_out = {}
    proofs = {}
    manifest_docs = []
    docs = all_docs()
    for doc in docs:
        key = doc["fonte"]
        if key not in sources or key not in fontes:
            raise SystemExit(f"fonte ausente para {doc['slug']}: {key}")
        markdown, proof, entry, _conv = build_document(doc, sources[key], fontes[key])
        docs_out[doc["slug"]] = dict(arquivo=doc["arquivo"], markdown=markdown)
        proofs[doc["slug"]] = proof
        manifest_docs.append(entry)
    manifest = dict(
        contrato_versao=CONTRACT_VERSION,
        lote=LOTE,
        descricao=("Decretos federais 8.001–9.000 (#81): amostra Planalto + lacunas Câmara com catálogo Senado DEC."),
        gerado_em=now_utc(),
        vigencia_certificada=False,
        documentos=manifest_docs,
        limites=[
            "Lote da faixa prioritária 8001–9000; demais milhares pós-1991 seguem abertos.",
            "Não altera nucleo_licitacoes.",
            "Sem segunda fonte de conferência nesta entrega.",
        ],
    )
    return docs_out, proofs, manifest


def write_outputs(docs_out, proofs, manifest) -> None:
    for slug, item in docs_out.items():
        path = ROOT / item["arquivo"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["markdown"], encoding="utf-8")
        print(f"wrote {item['arquivo']} ({len(item['markdown'])} chars)", flush=True)
    for slug, proof in proofs.items():
        write_json(PROVAS / f"reconciliacao-{slug}.json", proof)
    write_json(MANIFESTO, manifest)
    write_json(PROVAS / "ferramentas.json", nl.tool_versions())
    PENDENCIAS.write_text(write_pendencias(manifest["documentos"]), encoding="utf-8")
    print(f"wrote {PENDENCIAS.relative_to(ROOT)}", flush=True)


def build() -> None:
    fontes = load_fontes()
    sources = {}
    for doc in all_docs():
        key = doc["fonte"]
        if key not in fontes or not fontes[key].get("utilizavel", True):
            raise SystemExit(f"fonte {key} ausente ou inutilizável")
        snap = snapshot_path(key)
        raw = read_snapshot(key)
        if nl.sha256(raw) != fontes[key]["sha256"]:
            raise SystemExit(f"{key}: sha256 diverge")
        if nl.sha256(snap.read_bytes()) != fontes[key]["sha256_snapshot_armazenado"]:
            raise SystemExit(f"{key}: snapshot xz diverge")
        sources[key] = raw
    docs_out, proofs, manifest = compute(sources, fontes)
    write_outputs(docs_out, proofs, manifest)
    print("build ok", flush=True)


def verify() -> None:
    fontes = load_fontes()
    docs = all_docs()
    sources = {doc["fonte"]: read_snapshot(doc["fonte"]) for doc in docs}
    docs_out, proofs, manifest = compute(sources, fontes)
    problems = []
    published_manifest = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    if published_manifest.get("lote") != LOTE:
        problems.append("manifesto.lote inesperado")
    if len(published_manifest.get("documentos") or []) != len(docs):
        problems.append("cardinalidade do manifesto diverge")
    if not PENDENCIAS.is_file():
        problems.append("PENDENCIAS-decretos.md ausente")
    if not RECONCILIACAO.is_file():
        problems.append("catalogo-reconciliacao.json ausente")
    else:
        recon = json.loads(RECONCILIACAO.read_text(encoding="utf-8"))
        if recon.get("totais", {}).get("identidades_catalogo", 0) < 1000:
            problems.append("reconciliacao Senado DEC incompleta para a faixa")
        if recon.get("criterio_identidade") != "especie+numero/complemento+data":
            problems.append("criterio_identidade inesperado")
    for doc in docs:
        slug = doc["slug"]
        path = ROOT / doc["arquivo"]
        if not path.is_file():
            problems.append(f"{slug}: ausente")
            continue
        text = path.read_text(encoding="utf-8")
        if text != docs_out[slug]["markdown"]:
            import difflib
            print("".join(difflib.unified_diff(text.splitlines(True), docs_out[slug]["markdown"].splitlines(True), fromfile=str(path), tofile="reconversao", n=2))[:12000], flush=True)
            problems.append(f"{slug}: Markdown diverge da reconversão")
        meta, body = nl.parse_frontmatter(text)
        if meta.get("sha256_markdown") != nl.sha256(body.encode("utf-8")):
            problems.append(f"{slug}: sha256_markdown inválido")
        if meta.get("vigencia_certificada") is not False:
            problems.append(f"{slug}: vigencia_certificada")
        if not proofs[slug]["cobertura_texto"]["equivalente"]:
            problems.append(f"{slug}: cobertura falsa")
        pub = json.loads((PROVAS / f"reconciliacao-{slug}.json").read_text(encoding="utf-8"))
        if pub.get("cobertura_texto", {}).get("equivalente") is not True:
            problems.append(f"{slug}: prova sem cobertura")
        if "não certifica vigência" not in body:
            problems.append(f"{slug}: falta aviso de vigência")
        if "<<" in body and re.search(r"<<\s*(ANEXO|TABELA)\s*>>", body, re.I):
            problems.append(f"{slug}: placeholder de anexo no Markdown")
    if problems:
        raise SystemExit("verify falhou:\n- " + "\n- ".join(problems))
    print(f"verify ok ({len(docs)} documentos)", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch-catalog")
    sub.add_parser("reconcile")
    p_collect = sub.add_parser("collect")
    p_collect.add_argument("--limit", type=int, default=None)
    p_collect.add_argument("--sleep", type=float, default=0.35)
    p_fetch = sub.add_parser("fetch"); p_fetch.add_argument("dir", type=Path)
    p_ingest = sub.add_parser("ingest"); p_ingest.add_argument("dir", type=Path); p_ingest.add_argument("--capturado-em", default=None)
    sub.add_parser("build"); sub.add_parser("verify")
    args = parser.parse_args(argv)
    if args.cmd == "fetch-catalog":
        fetch_catalog()
    elif args.cmd == "reconcile":
        reconcile()
    elif args.cmd == "collect":
        collect(limit=args.limit, sleep_s=args.sleep)
    elif args.cmd == "fetch":
        fetch(args.dir)
    elif args.cmd == "ingest":
        ingest_capture(args.dir, args.capturado_em)
    elif args.cmd == "build":
        build()
    elif args.cmd == "verify":
        verify()


if __name__ == "__main__":
    main()
