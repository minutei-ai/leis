"""Amostras da issue #82: lacunas pontuais 2010–2026 e 1965.

Publica as amostras da issue cuja página do Planalto respondeu com HTML
utilizável e cobertura fonte→Markdown integral. Três leis de 1965 sem
página Planalto nesta captura ficam registradas em PENDENCIAS.

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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / "provas/federal-amostras-82"
FONTES_DIR = PROVAS / "fontes"
MANIFESTO = PROVAS / "manifesto.json"
FONTES_JSON = PROVAS / "fontes.json"
PENDENCIAS = PROVAS / "PENDENCIAS-amostras.md"
CATALOGO = PROVAS / "catalogo-pendencias.json"
UNKNOWN = nl.UNKNOWN
PLANALTO = nl.PLANALTO
USER_AGENT = nl.USER_AGENT
CONTRACT_VERSION = nl.CONTRACT_VERSION
LOTE = "federal-amostras-82"
TITLE_PATTERN = r"^LEI(?: COMPLEMENTAR)? N"

AMOSTRAS_PENDENTES = [{'numero': '4921', 'data': '1965-12-23', 'senado_id': '546778', 'url': 'https://legis.senado.leg.br/norma/546778', 'motivo': 'Planalto L4921.htm HTTP 404 nesta captura; íntegra ainda não recuperada'}, {'numero': '4920', 'data': '1965-12-23', 'senado_id': '546777', 'url': 'https://legis.senado.leg.br/norma/546777', 'motivo': 'Planalto L4920.htm HTTP 404 nesta captura; íntegra ainda não recuperada'}, {'numero': '4926', 'data': '1965-12-23', 'senado_id': '546783', 'url': 'https://legis.senado.leg.br/norma/546783', 'motivo': 'Planalto L4926.htm HTTP 404 nesta captura; íntegra ainda não recuperada'}]

SOURCES = {
    'planalto-L15103': dict(url='https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/lei/L15103.htm', file='planalto-L15103.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L14950': dict(url='https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/L14950.htm', file='planalto-L14950.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L14847': dict(url='https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/L14847.htm', file='planalto-L14847.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L14823': dict(url='https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/lei/L14823.htm', file='planalto-L14823.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L14642': dict(url='https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2023/lei/L14642.htm', file='planalto-L14642.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L14087': dict(url='https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/L14087.htm', file='planalto-L14087.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L14059': dict(url='https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/L14059.htm', file='planalto-L14059.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L13898': dict(url='https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/lei/L13898.htm', file='planalto-L13898.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-L4923': dict(url='https://www.planalto.gov.br/ccivil_03/leis/L4923.htm', file='planalto-L4923.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
}

DOCS = [
    dict(
        slug='br-federal-lei-2025-01-22-15103',
        arquivo='federal/br-federal-lei-2025-01-22-15103.md',
        fonte='planalto-L15103',
        senado_id='40306198',
        norma=dict(
            tipo='lei', numero='15103', data='2025-01-22',
            titulo='LEI Nº 15103, DE 22 DE JANEIRO DE 2025',
            ementa='Institui o Programa de Aceleração da Transição Energética (Paten); e altera as Leis nºs 13.988, de 14 de abril de 2020, 11.484, de 31 de maio de 2007, 9.991, de 24 de julho de 2000, e 9.478, de 6 de agosto de 1997.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-2024-08-02-14950',
        arquivo='federal/br-federal-lei-2024-08-02-14950.md',
        fonte='planalto-L14950',
        senado_id='39410175',
        norma=dict(
            tipo='lei', numero='14950', data='2024-08-02',
            titulo='LEI Nº 14950, DE 2 DE AGOSTO DE 2024',
            ementa='Altera a Lei nº 8.069, de 13 de julho de 1990 (Estatuto da Criança e do Adolescente), para dispor sobre o direito da criança e do adolescente de visitação à mãe ou ao pai internados em instituição de saúde',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-2024-04-25-14847',
        arquivo='federal/br-federal-lei-2024-04-25-14847.md',
        fonte='planalto-L14847',
        senado_id='38377648',
        norma=dict(
            tipo='lei', numero='14847', data='2024-04-25',
            titulo='LEI Nº 14847, DE 25 DE ABRIL DE 2024',
            ementa='Altera a Lei nº 8.080, de 19 de setembro de 1990 (Lei Orgânica da Saúde), para dispor sobre o atendimento de mulheres vítimas de violência em ambiente privativo e individualizado nos serviços de saúde prestados no âmbito do Sistema Único de Saúde.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-2024-02-29-14823',
        arquivo='federal/br-federal-lei-2024-02-29-14823.md',
        fonte='planalto-L14823',
        senado_id='38231098',
        norma=dict(
            tipo='lei', numero='14823', data='2024-02-29',
            titulo='LEI Nº 14823, DE 29 DE FEVEREIRO DE 2024',
            ementa='Abre crédito extraordinário em favor dos Ministérios da Defesa, da Integração e do Desenvolvimento Regional e do Desenvolvimento e Assistência Social, Família e Combate à Fome, no valor de R$ 360.900.000,00 (trezentos e sessenta milhões e novecentos mil reais), para os fins que especifica.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-2023-08-01-14642',
        arquivo='federal/br-federal-lei-2023-08-01-14642.md',
        fonte='planalto-L14642',
        senado_id='37441123',
        norma=dict(
            tipo='lei', numero='14642', data='2023-08-01',
            titulo='LEI Nº 14642, DE 1 DE AGOSTO DE 2023',
            ementa='Denomina João Batista Menegatti o viaduto localizado na rodovia BR-282, na travessia urbana do Município de Xanxerê, Estado de Santa Catarina.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-2020-11-17-14087',
        arquivo='federal/br-federal-lei-2020-11-17-14087.md',
        fonte='planalto-L14087',
        senado_id='32929356',
        norma=dict(
            tipo='lei', numero='14087', data='2020-11-17',
            titulo='LEI Nº 14087, DE 17 DE NOVEMBRO DE 2020',
            ementa='Abre ao Orçamento Fiscal da União, em favor da Justiça Federal, crédito suplementar no valor de R$ 6.194.427,00, para reforço de dotações constantes da Lei Orçamentária vigente.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-2020-09-22-14059',
        arquivo='federal/br-federal-lei-2020-09-22-14059.md',
        fonte='planalto-L14059',
        senado_id='32789770',
        norma=dict(
            tipo='lei', numero='14059', data='2020-09-22',
            titulo='LEI Nº 14059, DE 22 DE SETEMBRO DE 2020',
            ementa='Altera as L eis nºs 9.264, de 7 de fevereiro de 1996 , 11.134, de 15 de julho de 2005 , 11.361, de 19 de outubro de 2006 , e 13.328, de 29 de julho de 2016 , para aumentar a remuneração da Polícia Militar, do Corpo de Bombeiros Militar e da Polícia Civil do Distrito Federal e da Polícia Militar e do Corpo de Bombeiros Militar dos extintos Territórios Federais e pa',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-2019-11-11-13898',
        arquivo='federal/br-federal-lei-2019-11-11-13898.md',
        fonte='planalto-L13898',
        senado_id='31666914',
        norma=dict(
            tipo='lei', numero='13898', data='2019-11-11',
            titulo='LEI Nº 13898, DE 11 DE NOVEMBRO DE 2019',
            ementa='Dispõe sobre as diretrizes para a elaboração e a execução da Lei Orçamentária de 2020 e dá outras providências.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    ),
    dict(
        slug='br-federal-lei-1965-12-23-4923',
        arquivo='federal/br-federal-lei-1965-12-23-4923.md',
        fonte='planalto-L4923',
        senado_id='546780',
        norma=dict(
            tipo='lei', numero='4923', data='1965-12-23',
            titulo='LEI Nº 4923, DE 23 DE DEZEMBRO DE 1965',
            ementa='Institui o Cadastro Permanente das Admissões e Dispensas de Empregados, Estabelece Medidas Contra o Desemprego e de Assistência aos Desempregados, e dá outras Providências.',
            denominacao=None),
        edicao=dict(tipo='historica', identidade='planalto', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
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
        headers_path = capture_dir / (spec["file"] + ".headers")
        record = dict(
            orgao=spec["orgao"], formato=spec["formato"], url=spec["url"],
            capturado_em=stamp, user_agent=USER_AGENT, http_status=200,
            url_final=spec["url"], bytes=len(data), sha256=nl.sha256(data),
            sha256_conteudo=nl.content_sha256(data), utilizavel=True,
            dou_aviso=dou_aviso_from_html(data, spec["charset"]),
            snapshot=str(snapshot_path(key).relative_to(ROOT)),
            sha256_snapshot_armazenado=nl.sha256(snapshot_path(key).read_bytes()),
            charset=spec["charset"],
        )
        if headers_path.is_file():
            raw_headers = headers_path.read_bytes().decode("latin-1").replace("\r\n", "\n")
            final_block = [b for b in raw_headers.split("\n\n") if b.strip()][-1:] or [""]
            for line in final_block[0].splitlines():
                name, _, value = line.partition(":")
                if name.lower() in ("last-modified", "etag", "content-type", "date"):
                    record["cabecalho_" + name.lower().replace("-", "_")] = value.strip()
        fontes[key] = record
        print(f"ingest {key}: {record['bytes']} sha256={record['sha256'][:16]}…", flush=True)
    write_json(FONTES_JSON, fontes)
    return fontes


def load_fontes() -> dict:
    return json.loads(FONTES_JSON.read_text(encoding="utf-8"))


def load_sources_bytes() -> dict:
    return {key: read_snapshot(key) for key in SOURCES}


def edition_note(doc: dict, rec: dict, conv: nl.Converter) -> str:
    edicao = doc["edicao"]["tipo"]
    label = "Edição consolidada" if edicao == "consolidada" else "Edição histórica"
    lines = [
        (f"**{label} — {rec['orgao']}.** Fonte: {rec['url']} "
         f"(capturada em {rec['capturado_em']}, SHA-256 da fonte `{rec['sha256']}`, "
         f"SHA-256 do conteúdo sem script de proteção `{rec['sha256_conteudo']}`). "
         f"Snapshot: `{rec['snapshot']}`. O acervo não certifica vigência."),
        ("Página oficial do Planalto. Notas, remissões, tabelas e trechos riscados da "
         "página foram preservados literalmente. Não é republicação isolada do DOU."),
        ("Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial "
         "mantém riscada; não é dispositivo em vigor. A presença deste arquivo no acervo "
         "não indica vigência."),
    ]
    if rec.get("dou_aviso"):
        lines.append(rec["dou_aviso"])
    lines.append(
        f"Prova de cobertura fonte→Markdown e reconversão: "
        f"`provas/{LOTE}/reconciliacao-{doc['slug']}.json`.")
    if conv.images:
        lines.append(
            f"{len(conv.images)} imagem(ns) institucional(is) do cabeçalho da página foram omitidas do "
            "Markdown (brasão/logotipo sem texto jurídico).")
    if conv.stats["tabelas_markdown"] or conv.stats["tabelas_html"]:
        n = conv.stats["tabelas_markdown"] + conv.stats["tabelas_html"]
        lines.append(f"{n} tabela(s) da fonte foram convertidas para Markdown/`<table>` no corpo.")
    return nl.note_block(lines)


def build_document(doc: dict, data: bytes, rec: dict):
    spec = SOURCES[doc["fonte"]]
    conv = nl.convert_html(data, spec["charset"], spec["url"])
    body = nl.blocks_to_markdown(conv.blocks, doc["title_pattern"])
    src = nl.strip_fold(nl.source_text_chars_from_html(data, spec["charset"]))
    md_all = nl.strip_fold(nl.md_text_all(body))
    coverage_ok = src == md_all
    _arts, order = nl.split_articles(conv.blocks)
    anexos = sum(1 for b in conv.blocks if re.match(r"^ANEXO\b", nl.md_plain(b, True).strip(), re.I))
    note = edition_note(doc, rec, conv)
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
    if edicao_tipo == "consolidada":
        edicao_id = f"{doc['slug']}@consolidada-planalto"
        edicao_integral = True
    else:
        edicao_id = f"{doc['slug']}@historica-planalto"
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
            descricao=("texto integral da página da fonte (sem imagens) == texto do Markdown publicado "
                       "(corpo convertido, sem nota de edição), após normalização"),
            equivalente=coverage_ok,
            caracteres_normalizados_fonte=len(src),
            caracteres_normalizados_markdown=len(md_all),
            metodo="strip_fold(source_text_chars_from_html) == strip_fold(md_text_all(body_convertido))",
        ),
        conversao=dict(
            **conv.stats,
            imagens=conv.images,
            tabelas=conv.tables,
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
        ),
        limites=[
            "Fonte única nesta entrega (Planalto); fonte_conferencia=nenhuma.",
            "O acervo não certifica vigência.",
            "Imagens institucionais do cabeçalho foram omitidas; tabelas/notas/riscados preservados.",
            "Lote parcial da #71; demais prioridades em PENDENCIAS-prioridade.md.",
        ],
    )
    if not coverage_ok:
        raise SystemExit(f"{doc['slug']}: cobertura fonte→Markdown falhou")

    entry = dict(
        id=doc["slug"],
        arquivo=doc["arquivo"],
        norma=norma,
        edicao=dict(tipo=edicao_tipo, integral=edicao_integral, identidade=doc["edicao"]["identidade"], edicao_id=edicao_id),
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
        "Amostras listadas na issue. Cada uma tem Markdown integral neste lote",
        "ou permanece pendente com a fonte consultada.",
        "",
        f"Gerado em {now_utc()}. Não esgota as 2.589 (1822–1965) + 172 (2010–2026) identidades.",
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
        "| Número | Data | Senado | Estado |",
        "| --- | --- | --- | --- |",
    ]
    for p in AMOSTRAS_PENDENTES:
        lines.append(
            f"| {p['numero']} | {p['data']} | [{p['senado_id']}]({p['url']}) | {p['motivo']} |"
        )
    lines += [
        "",
        "## Catálogo amplo",
        "",
        "Resumo do denominador e lotes futuros: `provas/federal-lacunas-catalogo/catalogo-82-resumo.json`.",
        "",
        "## Limites",
        "",
        "- Catálogo Senado é denominador de identidades; ementa não substitui íntegra.",
        "- HTTP 404 do Planalto não prova inexistência da lei; busca continua em normas.leg.br/Câmara.",
        "- Trabalhos da #71 (1966–2009) e #62 ficam separados.",
        "",
    ]
    return "\n".join(lines)


def write_catalogo(manifest_docs: list) -> dict:
    publicados = []
    for e in manifest_docs:
        doc = next(d for d in DOCS if d["slug"] == e["id"])
        publicados.append(dict(
            senado_id=doc["senado_id"], numero=doc["norma"]["numero"], data=doc["norma"]["data"],
            estado="publicado", caminho=e["arquivo"], url_planalto=e["fonte"]["url"],
            url_senado=f"https://legis.senado.leg.br/norma/{doc['senado_id']}",
        ))
    pend = [dict(**p, estado="nao-recuperado-planalto-404") for p in AMOSTRAS_PENDENTES]
    return dict(
        lote=LOTE,
        gerado_em=now_utc(),
        issue=82,
        amostras_issue=publicados + pend,
        totais=dict(publicadas=len(publicados), pendentes=len(pend)),
        referencia_ampla="provas/federal-lacunas-catalogo/catalogo-82-resumo.json",
    )



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
        descricao=("Amostras da #82 recuperadas do Planalto; catálogo amplo de pendências em provas/federal-lacunas-catalogo/."),
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
        problems.append("PENDENCIAS-prioridade.md ausente")
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_fetch = sub.add_parser("fetch"); p_fetch.add_argument("dir", type=Path)
    p_ingest = sub.add_parser("ingest"); p_ingest.add_argument("dir", type=Path); p_ingest.add_argument("--capturado-em", default=None)
    sub.add_parser("build"); sub.add_parser("verify")
    args = parser.parse_args(argv)
    if args.cmd == "fetch":
        fetch(args.dir)
    elif args.cmd == "ingest":
        ingest_capture(args.dir, args.capturado_em)
    elif args.cmd == "build":
        build()
    elif args.cmd == "verify":
        verify()


if __name__ == "__main__":
    main()
