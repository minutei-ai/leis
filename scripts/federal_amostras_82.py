"""Amostras e avanço da issue #82: lacunas 1822–1965 e 2010–2026.

Publica as 12 amostras da issue (9 Planalto + 3 Câmara para 4920/4921/4926,
cujas URLs Planalto responderam 404). Reconcilia denominadores oficiais do
Senado (LEI anual) em provas/federal-lacunas-catalogo/.

Reutiliza `nucleo_licitacoes.convert_html` sem alterar aquele gerador.
Separado do lote #71 (faixa 5.000–11.999).
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

PROVAS = ROOT / "provas/federal-amostras-82"
FONTES_DIR = PROVAS / "fontes"
MANIFESTO = PROVAS / "manifesto.json"
FONTES_JSON = PROVAS / "fontes.json"
PENDENCIAS = PROVAS / "PENDENCIAS-amostras.md"
CATALOGO = PROVAS / "catalogo-pendencias.json"
LACUNAS = ROOT / "provas/federal-lacunas-catalogo"
CATALOGO_82_RESUMO = LACUNAS / "catalogo-82-resumo.json"
CATALOGO_82_RECON = LACUNAS / "catalogo-82-reconciliacao.json"
UNKNOWN = nl.UNKNOWN
PLANALTO = nl.PLANALTO
CAMARA = nl.CAMARA
USER_AGENT = nl.USER_AGENT
CONTRACT_VERSION = nl.CONTRACT_VERSION
LOTE = "federal-amostras-82"
TITLE_PATTERN = r"^LEI(?: COMPLEMENTAR)? N"

# Amostras da issue recuperadas; pendentes vazias após Câmara 4920/4921/4926.
AMOSTRAS_PENDENTES: list[dict] = []

SOURCES = {
    "planalto-L15103": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/L15103.htm", file="planalto-L15103.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-L14950": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/L14950.htm", file="planalto-L14950.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-L14847": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/L14847.htm", file="planalto-L14847.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-L14823": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/L14823.htm", file="planalto-L14823.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-L14642": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/lei/L14642.htm", file="planalto-L14642.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-L14087": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/L14087.htm", file="planalto-L14087.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-L14059": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/L14059.htm", file="planalto-L14059.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-L13898": dict(url="https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/lei/L13898.htm", file="planalto-L13898.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "planalto-L4923": dict(url="https://www.planalto.gov.br/ccivil_03/leis/L4923.htm", file="planalto-L4923.htm", orgao=PLANALTO, formato="html", charset="cp1252"),
    "camara-L4920": dict(
        url="https://www2.camara.leg.br/legin/fed/lei/1960-1969/lei-4920-23-dezembro-1965-368267-publicacaooriginal-1-pl.html",
        file="camara-L4920.htm", orgao=CAMARA, formato="html", charset="utf-8"),
    "camara-L4921": dict(
        url="https://www2.camara.leg.br/legin/fed/lei/1960-1969/lei-4921-23-dezembro-1965-368268-publicacaooriginal-1-pl.html",
        file="camara-L4921.htm", orgao=CAMARA, formato="html", charset="utf-8"),
    "camara-L4926": dict(
        url="https://www2.camara.leg.br/legin/fed/lei/1960-1969/lei-4926-23-dezembro-1965-368283-publicacaooriginal-1-pl.html",
        file="camara-L4926.htm", orgao=CAMARA, formato="html", charset="utf-8"),
}

DOCS = [
    dict(
        slug="br-federal-lei-2025-01-22-15103", arquivo="federal/br-federal-lei-2025-01-22-15103.md",
        fonte="planalto-L15103", senado_id="40306198",
        norma=dict(tipo="lei", numero="15103", data="2025-01-22", titulo="LEI Nº 15103, DE 22 DE JANEIRO DE 2025",
                   ementa="Institui o Programa de Aceleração da Transição Energética (Paten); e altera as Leis nºs 13.988, de 14 de abril de 2020, 11.484, de 31 de maio de 2007, 9.991, de 24 de julho de 2000, e 9.478, de 6 de agosto de 1997.", denominacao=None),
        edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-2024-08-02-14950", arquivo="federal/br-federal-lei-2024-08-02-14950.md",
        fonte="planalto-L14950", senado_id="39410175",
        norma=dict(tipo="lei", numero="14950", data="2024-08-02", titulo="LEI Nº 14950, DE 2 DE AGOSTO DE 2024",
                   ementa="Altera a Lei nº 8.069, de 13 de julho de 1990 (Estatuto da Criança e do Adolescente), para dispor sobre o direito da criança e do adolescente de visitação à mãe ou ao pai internados em instituição de saúde", denominacao=None),
        edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-2024-04-25-14847", arquivo="federal/br-federal-lei-2024-04-25-14847.md",
        fonte="planalto-L14847", senado_id="38377648",
        norma=dict(tipo="lei", numero="14847", data="2024-04-25", titulo="LEI Nº 14847, DE 25 DE ABRIL DE 2024",
                   ementa="Altera a Lei nº 8.080, de 19 de setembro de 1990 (Lei Orgânica da Saúde), para dispor sobre o atendimento de mulheres vítimas de violência em ambiente privativo e individualizado nos serviços de saúde prestados no âmbito do Sistema Único de Saúde.", denominacao=None),
        edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-2024-02-29-14823", arquivo="federal/br-federal-lei-2024-02-29-14823.md",
        fonte="planalto-L14823", senado_id="38231098",
        norma=dict(tipo="lei", numero="14823", data="2024-02-29", titulo="LEI Nº 14823, DE 29 DE FEVEREIRO DE 2024",
                   ementa="Abre crédito extraordinário em favor dos Ministérios da Defesa, da Integração e do Desenvolvimento Regional e do Desenvolvimento e Assistência Social, Família e Combate à Fome, no valor de R$ 360.900.000,00 (trezentos e sessenta milhões e novecentos mil reais), para os fins que especifica.", denominacao=None),
        edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-2023-08-01-14642", arquivo="federal/br-federal-lei-2023-08-01-14642.md",
        fonte="planalto-L14642", senado_id="37441123",
        norma=dict(tipo="lei", numero="14642", data="2023-08-01", titulo="LEI Nº 14642, DE 1 DE AGOSTO DE 2023",
                   ementa="Denomina João Batista Menegatti o viaduto localizado na rodovia BR-282, na travessia urbana do Município de Xanxerê, Estado de Santa Catarina.", denominacao=None),
        edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-2020-11-17-14087", arquivo="federal/br-federal-lei-2020-11-17-14087.md",
        fonte="planalto-L14087", senado_id="32929356",
        norma=dict(tipo="lei", numero="14087", data="2020-11-17", titulo="LEI Nº 14087, DE 17 DE NOVEMBRO DE 2020",
                   ementa="Abre ao Orçamento Fiscal da União, em favor da Justiça Federal, crédito suplementar no valor de R$ 6.194.427,00, para reforço de dotações constantes da Lei Orçamentária vigente.", denominacao=None),
        edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-2020-09-22-14059", arquivo="federal/br-federal-lei-2020-09-22-14059.md",
        fonte="planalto-L14059", senado_id="32789770",
        norma=dict(tipo="lei", numero="14059", data="2020-09-22", titulo="LEI Nº 14059, DE 22 DE SETEMBRO DE 2020",
                   ementa="Altera as L eis nºs 9.264, de 7 de fevereiro de 1996 , 11.134, de 15 de julho de 2005 , 11.361, de 19 de outubro de 2006 , e 13.328, de 29 de julho de 2016 , para aumentar a remuneração da Polícia Militar, do Corpo de Bombeiros Militar e da Polícia Civil do Distrito Federal e da Polícia Militar e do Corpo de Bombeiros Militar dos extintos Territórios Federais e pa", denominacao=None),
        edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-2019-11-11-13898", arquivo="federal/br-federal-lei-2019-11-11-13898.md",
        fonte="planalto-L13898", senado_id="31666914",
        norma=dict(tipo="lei", numero="13898", data="2019-11-11", titulo="LEI Nº 13898, DE 11 DE NOVEMBRO DE 2019",
                   ementa="Dispõe sobre as diretrizes para a elaboração e a execução da Lei Orçamentária de 2020 e dá outras providências.", denominacao=None),
        edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-1965-12-23-4923", arquivo="federal/br-federal-lei-1965-12-23-4923.md",
        fonte="planalto-L4923", senado_id="546780",
        norma=dict(tipo="lei", numero="4923", data="1965-12-23", titulo="LEI Nº 4923, DE 23 DE DEZEMBRO DE 1965",
                   ementa="Institui o Cadastro Permanente das Admissões e Dispensas de Empregados, Estabelece Medidas Contra o Desemprego e de Assistência aos Desempregados, e dá outras Providências.", denominacao=None),
        edicao=dict(tipo="historica", identidade="planalto", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-1965-12-23-4920", arquivo="federal/br-federal-lei-1965-12-23-4920.md",
        fonte="camara-L4920", senado_id="546777",
        norma=dict(tipo="lei", numero="4920", data="1965-12-23", titulo="LEI Nº 4920, DE 23 DE DEZEMBRO DE 1965",
                   ementa='Autoriza o Poder Executivo a abrir ao Ministério das Minas e Energia o crédito especial de Cr$ 1.500.000.000,00 (um bilhão e quinhentos milhões de cruzeiros) para a complementação dos recursos destinados à construção da "Usina Coaraci Nunes", no Território Federal do Amapá.', denominacao=None),
        edicao=dict(tipo="historica", identidade="camara", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-1965-12-23-4921", arquivo="federal/br-federal-lei-1965-12-23-4921.md",
        fonte="camara-L4921", senado_id="546778",
        norma=dict(tipo="lei", numero="4921", data="1965-12-23", titulo="LEI Nº 4921, DE 23 DE DEZEMBRO DE 1965",
                   ementa="Estende aos Serviços de Navegação da Amazônia e de Administração do Porto do Pará (SNAPP) a isenção de taxas de que gozam o Lloyd Brasileiro e a Companhia Nacional de Navegação Costeira.", denominacao=None),
        edicao=dict(tipo="historica", identidade="camara", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug="br-federal-lei-1965-12-23-4926", arquivo="federal/br-federal-lei-1965-12-23-4926.md",
        fonte="camara-L4926", senado_id="546783",
        norma=dict(tipo="lei", numero="4926", data="1965-12-23", titulo="LEI Nº 4926, DE 23 DE DEZEMBRO DE 1965",
                   ementa='Isenta dos impostos de importação e de consumo equipamento para produção de formol a ser importado por "Resinas Sintéticas S.A.", com fábrica no Município de Gravataí, Estado do Rio Grande do Sul.', denominacao=None),
        edicao=dict(tipo="historica", identidade="camara", integral=UNKNOWN), situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
    ),
]


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshot_path(key: str) -> Path:
    return FONTES_DIR / (SOURCES[key]["file"] + ".xz")


def read_snapshot(key: str) -> bytes:
    return lzma.decompress(snapshot_path(key).read_bytes())


def write_snapshot(key: str, data: bytes) -> None:
    path = snapshot_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


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


def fetch(dest: Path) -> dict:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, spec in SOURCES.items():
        target = dest / spec["file"]
        header_file = dest / (spec["file"] + ".headers")
        captured = now_utc()
        proc = subprocess.run([
            "curl", "--silent", "--show-error", "--location", "--http1.1",
            "--proto", "=https", "--proto-redir", "=https",
            "--connect-timeout", "30", "--max-time", "300",
            "--max-filesize", str(64 * 1024 * 1024),
            "--user-agent", USER_AGENT, "--dump-header", str(header_file),
            "--write-out", "%{http_code} %{url_effective}",
            "--output", str(target), spec["url"],
        ], capture_output=True, text=True)
        record = dict(url=spec["url"], capturado_em=captured, curl_exit=proc.returncode, user_agent=USER_AGENT)
        if proc.returncode == 0:
            status, _, effective = proc.stdout.partition(" ")
            record.update(http_status=int(status), url_final=effective)
            data = target.read_bytes()
            record.update(bytes=len(data), sha256=nl.sha256(data), sha256_conteudo=nl.content_sha256(data))
            raw_headers = header_file.read_bytes().decode("latin-1").replace("\r\n", "\n")
            final_block = [b for b in raw_headers.split("\n\n") if b.strip()][-1:] or [""]
            for line in final_block[0].splitlines():
                name, _, value = line.partition(":")
                if name.lower() in ("last-modified", "etag", "content-type", "date"):
                    record["cabecalho_" + name.lower().replace("-", "_")] = value.strip()
            looks_like_gateway = b"504 Gateway Time-out" in data[:400] or b"<title>5" in data[:400]
            record["utilizavel"] = status == "200" and not looks_like_gateway and len(data) > 1000
            if record["utilizavel"]:
                record["dou_aviso"] = dou_aviso_from_html(data, spec["charset"])
            else:
                record["motivo"] = f"resposta HTTP {status} sem conteúdo utilizável ({len(data)} bytes)"
        else:
            record.update(utilizavel=False, motivo=proc.stderr.strip()[-500:])
        header_file.unlink(missing_ok=True)
        records[key] = record
        print(f"{key}: {record.get('http_status')} {record.get('bytes')} utilizável={record['utilizavel']}", flush=True)
    write_json(dest / "fetch.json", records)
    return records


def ingest_capture(capture_dir: Path, capturado_em: str | None = None) -> dict:
    capture_dir = Path(capture_dir)
    fontes = {}
    stamp = capturado_em
    if stamp is None:
        stamp_file = capture_dir / "capturado_em.txt"
        stamp = stamp_file.read_text(encoding="utf-8").strip() if stamp_file.exists() else now_utc()
    for key, spec in SOURCES.items():
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
    return {key: read_snapshot(key) for key in SOURCES}


def trim_camara_lei_blocks(blocks: list[str], numero: str) -> list[str]:
    num = str(int(numero))
    title_re = re.compile(r"^LEI N", re.I)
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
        raise RuntimeError(f"lei {numero}: título não encontrado")
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
        raise RuntimeError(f"lei {numero}: recorte vazio")
    joined = "\n".join(nl.md_plain(b, True) for b in out)
    if re.search(r"<<\s*(ANEXO|TABELA)\s*>>", joined, re.I):
        raise RuntimeError(f"lei {numero}: placeholder de anexo/tabela")
    if not re.search(r"(?:Art\.|Artigo)\s*", joined, re.I):
        raise RuntimeError(f"lei {numero}: nenhum artigo no recorte")
    return out


def edition_note(doc: dict, rec: dict, conv_stats: dict, images: list) -> str:
    edicao = doc["edicao"]["tipo"]
    label = "Edição consolidada" if edicao == "consolidada" else "Edição histórica"
    lines = [
        (f"**{label} — {rec['orgao']}.** Fonte: {rec['url']} "
         f"(capturada em {rec['capturado_em']}, SHA-256 da fonte `{rec['sha256']}`, "
         f"SHA-256 do conteúdo sem script de proteção `{rec['sha256_conteudo']}`). "
         f"Snapshot: `{rec['snapshot']}`. O acervo não certifica vigência."),
    ]
    if rec.get("orgao") == CAMARA:
        lines.append(
            "Página oficial da Câmara (publicação original). Planalto L{n}.htm respondeu HTTP 404 "
            "nesta captura anterior; a íntegra foi recuperada na Câmara. Notas e trechos da região "
            "normativa foram preservados literalmente.".format(n=doc["norma"]["numero"])
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


def build_document(doc: dict, data: bytes, rec: dict):
    spec = SOURCES[doc["fonte"]]
    if spec["orgao"] == CAMARA:
        conv = nl.convert_html(data, spec["charset"], spec["url"])
        blocks = trim_camara_lei_blocks(conv.blocks, doc["norma"]["numero"])
        body = "\n\n".join(blocks) + "\n"
        soup = BeautifulSoup(data.decode(spec["charset"]), "lxml")
        title = soup.select_one("#content > h1")
        region = soup.select_one(".textoNorma")
        if title is None or region is None:
            raise SystemExit(f"{doc['slug']}: região normativa Câmara ausente")
        source_text = title.get_text(" ") + region.get_text(" ")
        coverage_ok = nl.strip_fold(source_text) == nl.strip_fold(nl.md_text_all(body))
        metodo = "camara-h1+textoNorma"
        order = nl.split_articles(blocks)[1]
        anexos = sum(1 for b in blocks if re.match(r"^ANEXO\b", nl.md_plain(b, True).strip(), re.I))
        conv.blocks = blocks
    else:
        conv = nl.convert_html(data, spec["charset"], spec["url"])
        body = nl.blocks_to_markdown(conv.blocks, doc["title_pattern"])
        src = nl.strip_fold(nl.source_text_chars_from_html(data, spec["charset"]))
        md_all = nl.strip_fold(nl.md_text_all(body))
        coverage_ok = src == md_all
        metodo = "planalto-fullpage"
        _arts, order = nl.split_articles(conv.blocks)
        anexos = sum(1 for b in conv.blocks if re.match(r"^ANEXO\b", nl.md_plain(b, True).strip(), re.I))

    note = edition_note(doc, rec, conv.stats, conv.images)
    # Câmara trim devolve o título sem '#'; promove antes da checagem.
    if not body.startswith("# "):
        first_line = body.split("\n", 1)[0].lstrip("# ").strip()
        if first_line.upper().startswith("LEI"):
            first, _, rest_body = body.partition("\n\n")
            body = "# " + first.lstrip("# ").strip() + ("\n\n" + rest_body if rest_body else "\n")
    if "# " not in body:
        raise SystemExit(f"{doc['slug']}: título H1 ausente após conversão")
    title_at = body.index("# ") if body.startswith("# ") else body.index("\n# ") + 1
    title_end = body.index("\n\n", title_at)
    head, rest = body[:title_end], body[title_end + 2:]
    published_body = head + "\n\n" + note + "\n\n" + rest
    if not published_body.endswith("\n"):
        published_body += "\n"

    norma = doc["norma"]
    edicao_tipo = doc["edicao"]["tipo"]
    identidade = doc["edicao"]["identidade"]
    edicao_id = f"{doc['slug']}@historica-{identidade}"
    edicao_integral = UNKNOWN
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
        fonte_orgao=spec["orgao"],
        fonte_url=spec["url"],
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
        url=spec["url"],
        snapshot=rec["snapshot"],
        sha256_snapshot_armazenado=rec["sha256_snapshot_armazenado"],
        fontes_conferencia=[],
        cobertura_texto=dict(
            descricao="cobertura integral fonte→Markdown após normalização",
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
            "Lote parcial da #82; denominadores amplos em provas/federal-lacunas-catalogo/.",
        ],
    )
    entry = dict(
        id=doc["slug"],
        arquivo=doc["arquivo"],
        norma=norma,
        edicao=dict(tipo=edicao_tipo, integral=edicao_integral, identidade=identidade, edicao_id=edicao_id),
        situacao=doc["situacao"],
        fonte=dict(
            chave=doc["fonte"], orgao=spec["orgao"], url=spec["url"], formato="html",
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
    lines = [
        "# Pendências — amostras da issue #82",
        "",
        "As 12 amostras da issue têm Markdown integral neste lote (9 Planalto + 3 Câmara).",
        f"Gerado em {now_utc()}. Não esgota as identidades dos denominadores 1822–1965 / 2010–2026.",
        "",
        "## Publicadas neste lote",
        "",
        "| Número | Arquivo | Senado | Fonte |",
        "| --- | --- | --- | --- |",
    ]
    for e in sorted(manifest_docs, key=lambda x: int(x["norma"]["numero"])):
        sid = next(d["senado_id"] for d in DOCS if d["slug"] == e["id"])
        lines.append(
            f"| {e['norma']['numero']} | `{e['arquivo']}` | [{sid}](https://legis.senado.leg.br/norma/{sid}) | {e['fonte']['url']} |"
        )
    lines += [
        "",
        "## Pendentes das amostras da issue",
        "",
        "Nenhuma. 4920/4921/4926 recuperadas na Câmara (Planalto 404 documentado).",
        "",
        "## Catálogo amplo / denominadores",
        "",
        "- Resumo: `provas/federal-lacunas-catalogo/catalogo-82-resumo.json`",
        "- Reconciliação Senado LEI (espécie+número/complemento+data): `provas/federal-lacunas-catalogo/catalogo-82-reconciliacao.json`",
        "- Snapshots anuais: `provas/federal-lacunas-catalogo/senado-lei-anual/`",
        "- Avanço 2010–2026: `docs-avancados.json` + `collect-avancado-resume.json` (retomável).",
        "",
        "## Limites",
        "",
        "- Catálogo Senado é denominador de identidades; ementa não substitui íntegra.",
        "- HTTP 404 / falha de transporte do Planalto não prova inexistência da lei.",
        "- Cobertura fonte→Markdown insuficiente bloqueia publicação (não inventa texto).",
        "- Trabalhos da #71 (1966–2009) e #62 ficam separados.",
        "- Anos sem documentos na API são limites da fonte, não prova de inexistência.",
        "- 1822–1965 permanece majoritariamente pendente após este lote de amostras.",
        "",
    ]
    return "\n".join(lines)


def write_catalogo(manifest_docs: list) -> dict:
    publicados = []
    for e in manifest_docs:
        doc = next(d for d in DOCS if d["slug"] == e["id"])
        publicados.append(dict(
            senado_id=doc["senado_id"], numero=doc["norma"]["numero"], data=doc["norma"]["data"],
            estado="publicado", caminho=e["arquivo"], url_fonte=e["fonte"]["url"],
            url_senado=f"https://legis.senado.leg.br/norma/{doc['senado_id']}",
            orgao=e["fonte"]["orgao"],
        ))
    return dict(
        lote=LOTE,
        gerado_em=now_utc(),
        issue=82,
        amostras_issue=publicados,
        totais=dict(publicadas=len(publicados), pendentes=0),
        referencia_ampla="provas/federal-lacunas-catalogo/catalogo-82-resumo.json",
        reconciliacao_denominadores="provas/federal-lacunas-catalogo/catalogo-82-reconciliacao.json",
    )


def update_resumo_catalogo(manifest_docs: list) -> None:
    resumo = {}
    if CATALOGO_82_RESUMO.is_file():
        resumo = json.loads(CATALOGO_82_RESUMO.read_text(encoding="utf-8"))
    issue = resumo.get("issue_82") or {}
    amostras = []
    for e in sorted(manifest_docs, key=lambda x: int(x["norma"]["numero"])):
        doc = next(d for d in DOCS if d["slug"] == e["id"])
        amostras.append(dict(
            numero=doc["norma"]["numero"], data=doc["norma"]["data"], senado_id=doc["senado_id"],
            url=f"https://legis.senado.leg.br/norma/{doc['senado_id']}",
            estado="publicado-neste-lote", caminho=e["arquivo"],
            fonte_orgao=e["fonte"]["orgao"], fonte_url=e["fonte"]["url"],
        ))
    issue["amostras_issue"] = amostras
    issue["amostras_publicadas_neste_lote"] = len(amostras)
    issue["amostras_pendentes"] = 0
    if CATALOGO_82_RECON.is_file():
        recon = json.loads(CATALOGO_82_RECON.read_text(encoding="utf-8"))
        issue["denominadores_reconciliados"] = recon.get("periodos")
        issue["reconciliacao"] = str(CATALOGO_82_RECON.relative_to(ROOT))
    issue["limites"] = [
        "Contagens medem correspondências do catálogo capturado, não censo certificado.",
        "Anos sem resultado na API são limites da fonte, não prova de inexistência.",
        "Ementa/registro não substituem Markdown integral.",
    ]
    resumo["issue_82"] = issue
    resumo["atualizado_em"] = now_utc()
    write_json(CATALOGO_82_RESUMO, resumo)


def compute(sources: dict, fontes: dict):
    docs_out = {}
    proofs = {}
    manifest_docs = []
    for doc in DOCS:
        key = doc["fonte"]
        markdown, proof, entry, _conv = build_document(doc, sources[key], fontes[key])
        docs_out[doc["slug"]] = dict(arquivo=doc["arquivo"], markdown=markdown)
        proofs[doc["slug"]] = proof
        manifest_docs.append(entry)
    manifest = dict(
        contrato_versao=CONTRACT_VERSION,
        lote=LOTE,
        descricao=("Amostras da #82: 9 Planalto + 3 Câmara (4920/4921/4926); denominadores em federal-lacunas-catalogo."),
        gerado_em=now_utc(),
        vigencia_certificada=False,
        documentos=manifest_docs,
        limites=[
            "Lote parcial da #82; não esgota 1822–1965 nem 2010–2026.",
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
    write_json(CATALOGO, write_catalogo(manifest["documentos"]))
    update_resumo_catalogo(manifest["documentos"])
    print(f"wrote {PENDENCIAS.relative_to(ROOT)}", flush=True)


def build() -> None:
    fontes = load_fontes()
    sources = load_sources_bytes()
    for key in SOURCES:
        if key not in fontes or not fontes[key].get("utilizavel", True):
            raise SystemExit(f"fonte {key} ausente ou inutilizável")
        snap = snapshot_path(key)
        raw = read_snapshot(key)
        if nl.sha256(raw) != fontes[key]["sha256"]:
            raise SystemExit(f"{key}: sha256 diverge")
        if nl.sha256(snap.read_bytes()) != fontes[key]["sha256_snapshot_armazenado"]:
            raise SystemExit(f"{key}: snapshot xz diverge")
    docs_out, proofs, manifest = compute(sources, fontes)
    write_outputs(docs_out, proofs, manifest)
    print("build ok", flush=True)


def verify() -> None:
    fontes = load_fontes()
    sources = load_sources_bytes()
    docs_out, proofs, manifest = compute(sources, fontes)
    problems = []
    published_manifest = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    if published_manifest.get("lote") != LOTE:
        problems.append("manifesto.lote inesperado")
    if len(published_manifest.get("documentos") or []) != len(DOCS):
        problems.append("cardinalidade do manifesto diverge")
    if not PENDENCIAS.is_file():
        problems.append("PENDENCIAS-amostras.md ausente")
    if not CATALOGO_82_RECON.is_file():
        problems.append("catalogo-82-reconciliacao.json ausente")
    cat = json.loads(CATALOGO.read_text(encoding="utf-8"))
    if cat.get("totais", {}).get("publicadas") != 12 or cat.get("totais", {}).get("pendentes") != 0:
        problems.append("catalogo-pendencias não marca 12/0")
    for doc in DOCS:
        slug = doc["slug"]
        path = ROOT / doc["arquivo"]
        if not path.is_file():
            problems.append(f"{slug}: ausente")
            continue
        text = path.read_text(encoding="utf-8")
        if text != docs_out[slug]["markdown"]:
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
    if problems:
        raise SystemExit("verify falhou:\n- " + "\n- ".join(problems))
    print("verify ok", flush=True)



SENADO_LEI_DIR = LACUNAS / "senado-lei-anual"
DOCS_AVANCADOS = PROVAS / "docs-avancados.json"
RESUME_AVANCADO = PROVAS / "collect-avancado-resume.json"
MESES = [
    "", "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
]


def parse_senado_date(value: str) -> str:
    day, month, year = value.split("/")
    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"


def titulo_lei(numero: str, data: str) -> str:
    d = datetime.date.fromisoformat(data)
    return f"LEI Nº {numero}, DE {d.day} DE {MESES[d.month]} DE {d.year}"


def slug_lei(data: str, numero: str) -> str:
    return f"br-federal-lei-{data}-{numero}"


def arquivo_lei(data: str, numero: str) -> str:
    return f"federal/{slug_lei(data, numero)}.md"


def local_leis_por_identidade() -> dict[tuple[str, str], str]:
    """Mapa (numero, data) -> nome de arquivo canônico federal/br-federal-lei-*.md."""
    pat = re.compile(r"^br-federal-lei-(\d{4})-(\d{2})-(\d{2})-(\d+)(?:-.*)?\.md$")
    out = {}
    for path in (ROOT / "federal").glob("br-federal-lei-*.md"):
        m = pat.match(path.name)
        if not m:
            continue
        out[(m.group(4), f"{m.group(1)}-{m.group(2)}-{m.group(3)}")] = path.name
    return out


def load_senado_lei_periodo(ano_ini: int, ano_fim: int) -> list[dict]:
    items = []
    for year in range(ano_ini, ano_fim + 1):
        path = SENADO_LEI_DIR / f"senado-LEI-{year}.json.xz"
        if not path.is_file():
            continue
        data = json.loads(lzma.decompress(path.read_bytes()))
        docs_node = (data.get("ListaDocumento") or {}).get("documentos")
        if not isinstance(docs_node, dict):
            # anos sem documentos na resposta (string vazia etc.) — limite da fonte
            continue
        docs = docs_node.get("documento")
        if docs is None or docs == "":
            continue
        if isinstance(docs, dict):
            docs = [docs]
        if not isinstance(docs, list):
            continue
        meta = data["ListaDocumento"].get("Metadados") or {}
        for d in docs:
            tipo = d.get("tipo") or ""
            if not str(tipo).startswith("LEI") or not d.get("numero"):
                continue
            numero = str(d["numero"])
            complemento = d.get("complemento") or d.get("sequencia") or ""
            if not d.get("dataassinatura"):
                continue
            items.append(dict(
                especie=str(tipo),
                numero=numero,
                complemento=str(complemento) if complemento not in (None, "") else "",
                data=parse_senado_date(d["dataassinatura"]),
                senado_id=str(d["id"]),
                ementa=d.get("ementa") or "",
                normaNome=d.get("normaNome") or "",
                ano_catalogo=year,
                metadados_versao=meta.get("Versao"),
            ))
    by_key = {}
    for it in items:
        key = (it["especie"], it["numero"], it["complemento"], it["data"])
        by_key[key] = it
    return [by_key[k] for k in sorted(by_key, key=lambda x: (x[3], int(x[1]) if str(x[1]).isdigit() else 0, x[2]))]


def reconcile_denominadores() -> dict:
    """Reconcilia denominadores oficiais 1822–1965 e 2010–2026 (espécie+número/complemento+data)."""
    local = local_leis_por_identidade()
    periodos = {}
    amostras = {}
    anos_sem = []
    for label, a0, a1 in (("1822-1965", 1822, 1965), ("2010-2026", 2010, 2026)):
        ids = load_senado_lei_periodo(a0, a1)
        # anos cobertos no registry vs intervalo
        presentes, ausentes, insuf, so_num = [], [], [], []
        nums_dates = {}
        for it in ids:
            if it["especie"] != "LEI-n":
                # outras espécies LEI-* ficam fora do denominador LEI-n desta reconciliação
                continue
            if not str(it["numero"]).isdigit():
                insuf.append(it)
                continue
            key = (it["numero"], it["data"])
            nums_dates.setdefault(it["numero"], set()).add(it["data"])
            row = dict(**it)
            if key in local:
                row["estado"] = "presente-arquivo-local"
                row["arquivo"] = f"federal/{local[key]}"
                presentes.append(row)
            else:
                row["estado"] = "ausente-arquivo-canonic"
                row["arquivo"] = None
                ausentes.append(row)
        # coincidência só de número: ausente com mesmo número em outra data presente
        so_numero_count = 0
        for a in ausentes:
            other_dates = nums_dates.get(a["numero"]) or set()
            if any(dt != a["data"] and (a["numero"], dt) in local for dt in other_dates):
                so_numero_count += 1
        # anos sem arquivo de catálogo
        missing_years = []
        for y in range(a0, a1 + 1):
            if not (SENADO_LEI_DIR / f"senado-LEI-{y}.json.xz").is_file():
                missing_years.append(y)
        periodos[label] = dict(
            identidades=len(presentes) + len(ausentes),
            presentes=len(presentes),
            ausentes=len(ausentes),
            identidade_insuficiente=len(insuf),
            so_numero=so_numero_count,
            anos_sem_documentos=len(missing_years),
        )
        amostras[label] = ausentes[:80]
        anos_sem.extend(missing_years)
    result = dict(
        gerado_em=now_utc(),
        issue=82,
        criterio_identidade="especie+numero/complemento+data",
        fonte_catalogo="provas/federal-lacunas-catalogo/senado-lei-anual/",
        periodos=periodos,
        anos_sem_documentos_na_resposta=sorted(set(anos_sem)),
        amostras_ausentes_listadas=amostras,
        limites=[
            "Contagens medem correspondências do catálogo capturado, não censo certificado.",
            "Anos sem documentos na resposta são limites da fonte, não prova de inexistência.",
            "coincidência só de número (so_numero) exige revisão antes de fundir identidades.",
            "Não inferir inexistência por falha de transporte na coleta de íntegras.",
        ],
    )
    # Persist full ausentes 2010-2026 for collect (bounded file)
    ausentes_2010 = []
    for it in load_senado_lei_periodo(2010, 2026):
        if it["especie"] != "LEI-n" or not str(it["numero"]).isdigit():
            continue
        key = (it["numero"], it["data"])
        if key not in local:
            ausentes_2010.append(it)
    write_json(PROVAS / "ausentes-2010-2026.json", dict(
        gerado_em=now_utc(), criterio_identidade="especie+numero/complemento+data",
        total=len(ausentes_2010), itens=ausentes_2010,
    ))
    write_json(CATALOGO_82_RECON, result)
    # update resumo
    resumo = load_json(CATALOGO_82_RESUMO, default={}) or {}
    issue = resumo.get("issue_82") or {}
    issue["denominadores_reconciliados"] = periodos
    issue["reconciliacao"] = str(CATALOGO_82_RECON.relative_to(ROOT))
    issue["ausentes_2010_2026_arquivo"] = "provas/federal-amostras-82/ausentes-2010-2026.json"
    resumo["issue_82"] = issue
    resumo["atualizado_em"] = now_utc()
    write_json(CATALOGO_82_RESUMO, resumo)
    print(
        f"reconcile: 1822-1965 ausentes={periodos['1822-1965']['ausentes']} "
        f"2010-2026 ausentes={periodos['2010-2026']['ausentes']}",
        flush=True,
    )
    return result


def load_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def planalto_lei_url_candidates(numero: str, data: str) -> list[str]:
    year = int(data[:4])
    if 2007 <= year <= 2010:
        atos = ["_ato2007-2010", "_Ato2007-2010"]
    elif 2011 <= year <= 2014:
        atos = ["_ato2011-2014", "_Ato2011-2014"]
    elif 2015 <= year <= 2018:
        atos = ["_ato2015-2018", "_Ato2015-2018"]
    elif 2019 <= year <= 2022:
        atos = ["_ato2019-2022", "_Ato2019-2022"]
    elif 2023 <= year <= 2026:
        atos = ["_ato2023-2026", "_Ato2023-2026"]
    else:
        atos = [f"_ato{year}-{year}"]
    forms = [f"L{numero}", f"l{numero}"]
    out, seen = [], set()
    for ato in atos:
        for form in forms:
            for folder in ("lei", "Lei"):
                url = f"https://www.planalto.gov.br/ccivil_03/{ato}/{year}/{folder}/{form}.htm"
                if url not in seen:
                    seen.add(url)
                    out.append(url)
    # leis antigas sem ato
    if year <= 2001:
        out.extend([
            f"https://www.planalto.gov.br/ccivil_03/leis/L{numero}.htm",
            f"https://www.planalto.gov.br/ccivil_03/leis/l{numero}.htm",
        ])
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
        looks_like_gateway = b"504 Gateway Time-out" in data[:400] or b"<title>5" in data[:400]
        record["utilizavel"] = status == "200" and not looks_like_gateway and len(data) > 800
        if not record["utilizavel"]:
            record["motivo"] = f"resposta HTTP {status} sem conteúdo utilizável ({len(data)} bytes)"
    else:
        record.update(utilizavel=False, motivo=(proc.stderr or proc.stdout or "curl failed")[-500:])
    header_file.unlink(missing_ok=True)
    return record


def resolve_planalto_lei(numero: str, data: str) -> tuple[str, bytes, dict] | None:
    for url in planalto_lei_url_candidates(numero, data):
        dest = Path("/tmp") / f"planalto-L{numero}.htm"
        rec = curl_get(url, dest, max_time=90)
        if not rec.get("utilizavel"):
            continue
        data_bytes = dest.read_bytes()
        plain = nl.decode(data_bytes, "cp1252")
        if re.search(r"n[aã]o\s+encontrad", plain[:2500], re.I):
            continue
        if not re.search(r"LEI\s+(?:COMPLEMENTAR\s+)?N", plain, re.I):
            continue
        if re.search(r"<<\s*(ANEXO|TABELA)\s*>>", plain, re.I):
            continue
        m = re.search(r"LEI\s+(?:COMPLEMENTAR\s+)?N[^\n]{0,80}", plain, re.I)
        if not m:
            continue
        digits = re.sub(r"\D", "", m.group(0).split(",")[0])
        if not digits.endswith(str(int(numero))):
            continue
        if not re.search(r"(?:Art\.|Artigo)\s*\d", plain, re.I):
            continue
        return url, data_bytes, rec
    return None


def collect_avancado(periodo: str = "2010-2026", limit: int | None = None, sleep_s: float = 0.3) -> None:
    """Avança coleta das lacunas reconciliadas (prioridade 2010–2026). Retomável."""
    if periodo != "2010-2026":
        raise SystemExit("neste lote, collect-avancado prioriza apenas 2010-2026")
    reconcile_denominadores()
    payload = load_json(PROVAS / "ausentes-2010-2026.json", default={"itens": []}) or {"itens": []}
    ausentes = payload.get("itens") or []
    state = load_json(RESUME_AVANCADO, default={"done": {}, "failed": {}}) or {"done": {}, "failed": {}}
    coletados = {d["numero"] + "@" + d["data"]: d for d in (load_json(DOCS_AVANCADOS, default=[]) or [])}
    fontes = load_json(FONTES_JSON, default={}) or {}
    local = local_leis_por_identidade()
    pending = []
    for it in ausentes:
        key = it["numero"] + "@" + it["data"]
        if (it["numero"], it["data"]) in local or key in coletados or key in state.get("done", {}):
            continue
        pending.append(it)
    if limit is not None:
        pending = pending[:limit]
    print(f"collect-avancado: pendentes={len(pending)} ausentes_totais={len(ausentes)}", flush=True)
    ok = 0
    for it in pending:
        numero, data = it["numero"], it["data"]
        key_id = numero + "@" + data
        try:
            pl = resolve_planalto_lei(numero, data)
            if not pl:
                raise RuntimeError(
                    "falha de fonte/transporte Planalto para a identidade; não interpreta ausência normativa"
                )
            url, data_bytes, rec = pl
            fonte_key = f"planalto-L{numero}-{data}"
            file_name = f"planalto-L{numero}-{data}.htm"
            snap = FONTES_DIR / (file_name + ".xz")
            snap.parent.mkdir(parents=True, exist_ok=True)
            snap.write_bytes(lzma.compress(data_bytes, preset=9 | lzma.PRESET_EXTREME))
            dou = dou_aviso_from_html(data_bytes, "cp1252")
            fontes[fonte_key] = dict(
                orgao=PLANALTO, formato="html", url=url, capturado_em=rec["capturado_em"],
                user_agent=USER_AGENT, http_status=rec["http_status"],
                url_final=rec.get("url_final") or url, bytes=len(data_bytes),
                sha256=nl.sha256(data_bytes), sha256_conteudo=nl.content_sha256(data_bytes),
                utilizavel=True, dou_aviso=dou, snapshot=str(snap.relative_to(ROOT)),
                sha256_snapshot_armazenado=nl.sha256(snap.read_bytes()), charset="cp1252",
                senado_id=it["senado_id"], periodo="2010-2026",
            )
            doc_row = dict(
                slug=slug_lei(data, numero), arquivo=arquivo_lei(data, numero),
                fonte=fonte_key, fonte_url=url, fonte_file=file_name, fonte_orgao=PLANALTO,
                charset="cp1252", numero=numero, data=data, titulo=titulo_lei(numero, data),
                ementa=it.get("ementa") or "", senado_id=it["senado_id"],
                identidade="planalto", origem="collect-avancado-planalto",
                capturado_em=rec["capturado_em"],
            )
            coletados[key_id] = doc_row
            state.setdefault("done", {})[key_id] = dict(slug=doc_row["slug"], url=url, capturado_em=rec["capturado_em"])
            state.get("failed", {}).pop(key_id, None)
            ok += 1
            print(f"OK {numero} {data} bytes={len(data_bytes)}", flush=True)
        except Exception as exc:  # noqa: BLE001
            state.setdefault("failed", {})[key_id] = dict(
                erro=str(exc)[:500], em=now_utc(), senado_id=it.get("senado_id"), classe=type(exc).__name__,
            )
            print(f"FAIL {numero} {data}: {type(exc).__name__}: {exc}", flush=True)
        state["updated_em"] = now_utc()
        write_json(RESUME_AVANCADO, state)
        write_json(DOCS_AVANCADOS, [coletados[k] for k in sorted(coletados)])
        write_json(FONTES_JSON, fontes)
        time.sleep(sleep_s)
    print(f"collect-avancado fim: ok={ok} done={len(state.get('done', {}))} failed={len(state.get('failed', {}))}", flush=True)


def avancado_docs() -> list[dict]:
    rows = load_json(DOCS_AVANCADOS, default=[]) or []
    out = []
    for doc in rows:
        out.append(dict(
            slug=doc["slug"], arquivo=doc["arquivo"], fonte=doc["fonte"], senado_id=doc.get("senado_id"),
            norma=dict(tipo="lei", numero=doc["numero"], data=doc["data"], titulo=doc["titulo"],
                       ementa=doc.get("ementa") or "", denominacao=None),
            edicao=dict(tipo="historica", identidade=doc.get("identidade") or "planalto", integral=UNKNOWN),
            situacao=dict(valor="nao-informada"), title_pattern=TITLE_PATTERN,
            origem=doc.get("origem") or "collect-avancado",
        ))
    return out


def build_avancado() -> None:
    """Publica Markdown das leis avançadas (além das 12 amostras).

    Falha de cobertura fonte→Markdown não publica o corpo: registra em resume
    como falha retomável (não interpreta ausência normativa).
    """
    fontes = load_fontes()
    docs = avancado_docs()
    if not docs:
        print("build-avancado: nenhum doc em docs-avancados.json", flush=True)
        return
    state = load_json(RESUME_AVANCADO, default={"done": {}, "failed": {}}) or {"done": {}, "failed": {}}
    coletados = {d["numero"] + "@" + d["data"]: d for d in (load_json(DOCS_AVANCADOS, default=[]) or [])}
    published = 0
    skipped = 0
    for doc in docs:
        key = doc["fonte"]
        if key not in fontes or not fontes[key].get("utilizavel", True):
            raise SystemExit(f"fonte avancada {key} ausente")
        snap = ROOT / fontes[key]["snapshot"]
        raw = lzma.decompress(snap.read_bytes())
        if nl.sha256(raw) != fontes[key]["sha256"]:
            raise SystemExit(f"{key}: sha256 diverge")
        rec = fontes[key]
        SOURCES[key] = dict(
            url=rec["url"],
            file=Path(rec["snapshot"]).name.replace(".xz", ""),
            orgao=rec.get("orgao") or PLANALTO,
            formato="html",
            charset=rec.get("charset") or "cp1252",
        )
        key_id = doc["norma"]["numero"] + "@" + doc["norma"]["data"]
        try:
            markdown, proof, _entry, _conv = build_document(doc, raw, rec)
        except SystemExit as exc:
            # Cobertura/identidade insuficiente: não publicar; manter retomável.
            state.setdefault("failed", {})[key_id] = dict(
                erro=str(exc)[:500], em=now_utc(), senado_id=doc.get("senado_id"),
                classe="BuildCoverageError",
            )
            state.get("done", {}).pop(key_id, None)
            coletados.pop(key_id, None)
            skipped += 1
            print(f"SKIP {doc['slug']}: {exc}", flush=True)
            continue
        path = ROOT / doc["arquivo"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        write_json(PROVAS / f"reconciliacao-{doc['slug']}.json", proof)
        published += 1
        print(f"wrote {doc['arquivo']} ({len(markdown)} chars)", flush=True)
    state["updated_em"] = now_utc()
    write_json(RESUME_AVANCADO, state)
    write_json(DOCS_AVANCADOS, [coletados[k] for k in sorted(coletados)])
    print(f"build-avancado ok published={published} skipped={skipped}", flush=True)


def verify_avancado() -> None:
    fontes = load_fontes()
    docs = avancado_docs()
    problems = []
    for doc in docs:
        key = doc["fonte"]
        snap = ROOT / fontes[key]["snapshot"]
        raw = lzma.decompress(snap.read_bytes())
        SOURCES[key] = dict(url=fontes[key]["url"], file=Path(fontes[key]["snapshot"]).name.replace(".xz", ""),
                            orgao=fontes[key].get("orgao") or PLANALTO, formato="html",
                            charset=fontes[key].get("charset") or "cp1252")
        markdown, proof, _entry, _c = build_document(doc, raw, fontes[key])
        path = ROOT / doc["arquivo"]
        if not path.is_file():
            problems.append(f"{doc['slug']}: ausente")
            continue
        text = path.read_text(encoding="utf-8")
        if text != markdown:
            problems.append(f"{doc['slug']}: Markdown diverge")
        meta, body = nl.parse_frontmatter(text)
        if meta.get("vigencia_certificada") is not False:
            problems.append(f"{doc['slug']}: vigencia")
        if not proof["cobertura_texto"]["equivalente"]:
            problems.append(f"{doc['slug']}: cobertura")
        if "não certifica vigência" not in body:
            problems.append(f"{doc['slug']}: aviso vigência")
    if problems:
        raise SystemExit("verify-avancado falhou:\n- " + "\n- ".join(problems[:40]))
    print(f"verify-avancado ok ({len(docs)} documentos)", flush=True)




def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_fetch = sub.add_parser("fetch"); p_fetch.add_argument("dir", type=Path)
    p_ingest = sub.add_parser("ingest"); p_ingest.add_argument("dir", type=Path); p_ingest.add_argument("--capturado-em", default=None)
    sub.add_parser("build"); sub.add_parser("verify")
    sub.add_parser("reconcile")
    p_col = sub.add_parser("collect-avancado")
    p_col.add_argument("--periodo", default="2010-2026")
    p_col.add_argument("--limit", type=int, default=None)
    p_col.add_argument("--sleep", type=float, default=0.3)
    sub.add_parser("build-avancado"); sub.add_parser("verify-avancado")
    args = parser.parse_args(argv)
    if args.cmd == "fetch":
        fetch(args.dir)
    elif args.cmd == "ingest":
        ingest_capture(args.dir, args.capturado_em)
    elif args.cmd == "build":
        build()
    elif args.cmd == "verify":
        verify()
    elif args.cmd == "reconcile":
        reconcile_denominadores()
    elif args.cmd == "collect-avancado":
        collect_avancado(periodo=args.periodo, limit=args.limit, sleep_s=args.sleep)
    elif args.cmd == "build-avancado":
        build_avancado()
    elif args.cmd == "verify-avancado":
        verify_avancado()


if __name__ == "__main__":
    main()
