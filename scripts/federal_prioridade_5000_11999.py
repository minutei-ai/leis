"""Lote prioritário e reconciliação retomável da série 5.000–11.999 (#71).

Publica as normas essenciais da lista prioritária a partir do Planalto, com
cobertura fonte→Markdown integral. Inclui normalização tipográfica de ordinais
partido do Planalto (ex.: Lei 9.784 `1o`/`1oo`) sem enfraquecer a validação.

Também expõe reconciliação e coleta retomável da série 5.000–11.999 contra o
catálogo anual do Senado (1966–2009), sem parar em amostras.

Reutiliza `nucleo_licitacoes.convert_html` sem alterar aquele gerador.
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

PROVAS = ROOT / "provas/federal-prioridade-5000-11999"
FONTES_DIR = PROVAS / "fontes"
MANIFESTO = PROVAS / "manifesto.json"
FONTES_JSON = PROVAS / "fontes.json"
PENDENCIAS = PROVAS / "PENDENCIAS-prioridade.md"
CATALOGO_PRIORIDADES = PROVAS / "prioridades-catalogo.json"
SENADO_ANUAL_DIR = PROVAS / "senado-anual"
SERIE_ESTADO_DIR = PROVAS / "serie-estado"
SERIE_CATALOGO = PROVAS / "catalogo-serie-reconciliacao.json"
SERIE_ESTADO_JSON = SERIE_ESTADO_DIR / "collect-state.json"
UNKNOWN = nl.UNKNOWN
PLANALTO = nl.PLANALTO
USER_AGENT = nl.USER_AGENT
CONTRACT_VERSION = nl.CONTRACT_VERSION
LOTE = "federal-prioridade-5000-11999"
TITLE_PATTERN = r"^LEI(?: COMPLEMENTAR)? N"
SERIE_MIN = 5000
SERIE_MAX = 11999
SERIE_ANOS = range(1966, 2010)

# Ordinal tipográfico partido do Planalto → "Nº " (cp1252), sem reeditar o jurídico.
_ORD_BYTE = "º".encode("cp1252")
_NBSP = b"\xa0"
_ORDINAL_TAG_RE = re.compile(
    rb"(\d)"
    rb"(?:\s*</?(?:sup|u|b|i|strong|em|font|span|small|a)(?:\s[^>]*)?>)*\s*"
    rb"(?:<(?:sup|u)(?:\s[^>]*)?>\s*(?:<(?:span|font|b|i)(?:\s[^>]*)?>\s*)*)+"
    rb"o\s*"
    rb"(?:</(?:span|font|b|i|sup|u|small)>\s*)+",
    re.I,
)
_ORDINAL_CHAR_GLUE_RE = re.compile(rb"(\d)" + re.escape(_ORD_BYTE) + rb"(?=[A-Za-z])")


def normalize_planalto_ordinals(data: bytes) -> bytes:
    """Junta ordinal partido em tags e evita colar º na palavra seguinte.

    Markup-only: não altera o texto jurídico além da tipografia ordinal do Planalto.
    """
    data = data.replace(b"&nbsp;", b" ").replace(b"&NBSP;", b" ").replace(_NBSP, b" ")
    prev = None
    cur = data
    while prev != cur:
        prev = cur
        cur = _ORDINAL_TAG_RE.sub(lambda m: m.group(1) + _ORD_BYTE + b" ", cur)
        cur = _ORDINAL_CHAR_GLUE_RE.sub(lambda m: m.group(1) + _ORD_BYTE + b" ", cur)
    return cur


def load_prioridades_catalogo() -> dict:
    if not CATALOGO_PRIORIDADES.is_file():
        raise SystemExit(f"catálogo ausente: {CATALOGO_PRIORIDADES}")
    return json.loads(CATALOGO_PRIORIDADES.read_text(encoding="utf-8"))


def _doc_from_entry(entry: dict) -> dict:
    numero = str(entry["numero"])
    data = entry["data"]
    edicao = entry.get("edicao") or "historica"
    key = f"planalto-L{numero}"
    slug = f"br-federal-lei-{data}-{numero}"
    if edicao == "consolidada":
        edicao_meta = dict(tipo="consolidada", identidade="compilado-planalto", integral=True)
    else:
        edicao_meta = dict(tipo="historica", identidade="planalto", integral=UNKNOWN)
    return dict(
        slug=slug,
        arquivo=f"federal/{slug}.md",
        fonte=key,
        senado_id=entry.get("senado_id"),
        norma=dict(
            tipo="lei",
            numero=numero,
            data=data,
            titulo=entry.get("titulo") or f"LEI Nº {numero}, DE {data}",
            ementa=entry.get("ementa") or "",
            denominacao=None,
        ),
        edicao=edicao_meta,
        situacao=dict(valor="nao-informada"),
        title_pattern=TITLE_PATTERN,
        normalize_ordinals=bool(entry.get("normalize_ordinals", True)),
    )


def _source_from_entry(entry: dict) -> dict:
    numero = str(entry["numero"])
    return dict(
        url=entry["url"],
        file=entry["file"],
        orgao=PLANALTO,
        formato="html",
        charset="cp1252",
        normalize_ordinals=bool(entry.get("normalize_ordinals", True)),
    )


_CAT = load_prioridades_catalogo()
JA_NO_ACERVO = list(_CAT.get("ja_no_acervo") or [])
_ENTRIES = list(_CAT["documentos"])
SOURCES = {f"planalto-L{e['numero']}": _source_from_entry(e) for e in _ENTRIES}
DOCS = [_doc_from_entry(e) for e in _ENTRIES]
# Prioridades da lista essencial ainda sem arquivo canônico neste lote / acervo.
PRIORIDADE_RESTANTE: list[int] = []  # preenchido em write_pendencias / verify


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def snapshot_path(key: str) -> Path:
    return FONTES_DIR / (SOURCES[key]["file"] + ".xz")


def read_snapshot(key: str) -> bytes:
    return lzma.decompress(snapshot_path(key).read_bytes())


def source_bytes(key: str) -> bytes:
    data = read_snapshot(key)
    if SOURCES[key].get("normalize_ordinals"):
        return normalize_planalto_ordinals(data)
    return data


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


def _curl_fetch(url: str, dest: Path, header_file: Path) -> dict:
    captured = now_utc()
    proc = subprocess.run(
        [
            "curl", "--silent", "--show-error", "--location", "--http1.1",
            "--proto", "=https", "--proto-redir", "=https",
            "--connect-timeout", "30", "--max-time", "300",
            "--max-filesize", str(64 * 1024 * 1024),
            "--user-agent", USER_AGENT, "--dump-header", str(header_file),
            "--write-out", "%{http_code} %{url_effective}",
            "--output", str(dest), url,
        ],
        capture_output=True,
        text=True,
    )
    record = dict(url=url, capturado_em=captured, curl_exit=proc.returncode, user_agent=USER_AGENT)
    if proc.returncode == 0:
        status, _, effective = proc.stdout.partition(" ")
        record.update(http_status=int(status) if status.isdigit() else status, url_final=effective.strip())
        data = dest.read_bytes() if dest.is_file() else b""
        record.update(bytes=len(data), sha256=nl.sha256(data), sha256_conteudo=nl.content_sha256(data))
        looks_like_gateway = b"504 Gateway Time-out" in data[:400] or b"<title>5" in data[:400]
        record["utilizavel"] = (
            str(record["http_status"]) == "200"
            and not looks_like_gateway
            and len(data) > 800
            and bool(re.search(br"LEI|Lei", data[:5000]))
        )
        if record["utilizavel"]:
            record["dou_aviso"] = dou_aviso_from_html(data, "cp1252")
        else:
            record["motivo"] = (
                f"resposta HTTP {record['http_status']} sem conteúdo utilizável ({len(data)} bytes)"
            )
    else:
        record.update(utilizavel=False, motivo=(proc.stderr or "")[-500:])
    return record


def fetch(dest: Path, resume: bool = True) -> dict:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, spec in SOURCES.items():
        target = dest / spec["file"]
        header_file = dest / (spec["file"] + ".headers")
        if resume and target.is_file() and target.stat().st_size > 800:
            data = target.read_bytes()
            if re.search(br"LEI|Lei", data[:5000]):
                records[key] = dict(
                    url=spec["url"], capturado_em=now_utc(), curl_exit=0, user_agent=USER_AGENT,
                    http_status=200, url_final=spec["url"], bytes=len(data),
                    sha256=nl.sha256(data), sha256_conteudo=nl.content_sha256(data),
                    utilizavel=True, retomado=True,
                    dou_aviso=dou_aviso_from_html(data, spec["charset"]),
                )
                print(f"{key}: retomado {len(data)} bytes", flush=True)
                continue
        record = _curl_fetch(spec["url"], target, header_file)
        header_file.unlink(missing_ok=True)
        records[key] = record
        print(
            f"{key}: {record.get('http_status')} {record.get('bytes')} "
            f"utilizável={record['utilizavel']}",
            flush=True,
        )
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
            normalizacao_ordinal_planalto=bool(spec.get("normalize_ordinals")),
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
    return {key: source_bytes(key) for key in SOURCES}


def edition_note(doc: dict, rec: dict, conv: nl.Converter) -> str:
    edicao = doc["edicao"]["tipo"]
    label = "Edição consolidada" if edicao == "consolidada" else "Edição histórica"
    lines = [
        (
            f"**{label} — {rec['orgao']}.** Fonte: {rec['url']} "
            f"(capturada em {rec['capturado_em']}, SHA-256 da fonte `{rec['sha256']}`, "
            f"SHA-256 do conteúdo sem script de proteção `{rec['sha256_conteudo']}`). "
            f"Snapshot: `{rec['snapshot']}`. O acervo não certifica vigência."
        ),
        (
            "Página oficial do Planalto. Notas, remissões, tabelas e trechos riscados da "
            "página foram preservados literalmente. Não é republicação isolada do DOU."
        ),
        (
            "Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial "
            "mantém riscada; não é dispositivo em vigor. A presença deste arquivo no acervo "
            "não indica vigência."
        ),
    ]
    if SOURCES[doc["fonte"]].get("normalize_ordinals"):
        lines.append(
            "Ordinais tipográficos partidos do Planalto "
            "(`N<sup><u>o</u></sup>` / variantes com `<span>`/`&nbsp;`) foram normalizados "
            "para `Nº ` antes da conversão e da cobertura fonte→Markdown, sem reeditar o "
            "texto jurídico."
        )
    if rec.get("dou_aviso"):
        lines.append(rec["dou_aviso"])
    lines.append(
        f"Prova de cobertura fonte→Markdown e reconversão: "
        f"`provas/{LOTE}/reconciliacao-{doc['slug']}.json`."
    )
    if conv.images:
        lines.append(
            f"{len(conv.images)} imagem(ns) institucional(is) do cabeçalho da página foram omitidas do "
            "Markdown (brasão/logotipo sem texto jurídico)."
        )
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
        normalizacao_ordinal_planalto=bool(spec.get("normalize_ordinals")),
        cobertura_texto=dict(
            descricao=(
                "texto integral da página da fonte (sem imagens) == texto do Markdown publicado "
                "(corpo convertido, sem nota de edição), após normalização tipográfica de ordinais "
                "e strip_fold"
            ),
            equivalente=coverage_ok,
            caracteres_normalizados_fonte=len(src),
            caracteres_normalizados_markdown=len(md_all),
            metodo=(
                "strip_fold(source_text_chars_from_html(normalize_planalto_ordinals(raw))) == "
                "strip_fold(md_text_all(body_convertido))"
            ),
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
            senado_id=doc.get("senado_id"),
        ),
        limites=[
            "Fonte única nesta entrega (Planalto); fonte_conferencia=nenhuma.",
            "O acervo não certifica vigência.",
            "Imagens institucionais do cabeçalho foram omitidas; tabelas/notas/riscados preservados.",
            "Normalização ordinal é tipográfica (markup Planalto); não altera dispositivos.",
            "Série completa 5.000–11.999 segue em catalogo-serie-reconciliacao.json / collect-serie.",
        ],
    )
    if not coverage_ok:
        raise SystemExit(f"{doc['slug']}: cobertura fonte→Markdown falhou")

    entry = dict(
        id=doc["slug"],
        arquivo=doc["arquivo"],
        norma=norma,
        edicao=dict(
            tipo=edicao_tipo, integral=edicao_integral,
            identidade=doc["edicao"]["identidade"], edicao_id=edicao_id,
        ),
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


def _canonical_present_numbers() -> set[str]:
    present = set()
    federal = ROOT / "federal"
    if not federal.is_dir():
        return present
    for p in federal.glob("br-federal-lei-*-*-*-*.md"):
        m = re.search(r"-(\d+)\.md$", p.name)
        if m:
            present.add(m.group(1))
    return present


def write_pendencias(manifest_docs: list) -> str:
    published = {e["norma"]["numero"] for e in manifest_docs}
    present = _canonical_present_numbers()
    restante = []
    for e in _ENTRIES:
        n = str(e["numero"])
        if n not in published and n not in JA_NO_ACERVO and n not in present:
            restante.append(int(n))
    global PRIORIDADE_RESTANTE
    PRIORIDADE_RESTANTE = sorted(restante)

    lines = [
        "# Pendências — prioridade #71 (faixa 5.000–11.999)",
        "",
        "Lista de normas essenciais da #71. Cada número tem arquivo canônico neste acervo,",
        "aparece como já coberto por outro lote, ou permanece pendente com a fonte consultada.",
        "",
        f"Gerado em {now_utc()}. Não certifica vigência nem completa a série inteira do catálogo.",
        "",
        "## Publicadas neste lote",
        "",
        "| Número | Arquivo | Fonte |",
        "| --- | --- | --- |",
    ]
    for e in sorted(manifest_docs, key=lambda x: int(x["norma"]["numero"])):
        lines.append(f"| {e['norma']['numero']} | `{e['arquivo']}` | {e['fonte']['url']} |")
    lines += [
        "",
        "## Já no acervo (outros lotes; não republicadas)",
        "",
        "| Número | Observação |",
        "| --- | --- |",
    ]
    for n in JA_NO_ACERVO:
        lines.append(f"| {n} | Presente em `federal/` por lote anterior (#62 / núcleos). |")
    lines += [
        "",
        "## Pendentes da lista prioritária",
        "",
        "| Número | Fonte consultada | Estado |",
        "| --- | --- | --- |",
    ]
    if PRIORIDADE_RESTANTE:
        for n in PRIORIDADE_RESTANTE:
            lines.append(
                f"| {n} | Planalto / Senado (catálogo LEI) | Identificada no catálogo; íntegra ainda não "
                f"publicada neste lote. Próxima captura: página oficial do Planalto ou encoding normas.leg.br. |"
            )
    else:
        lines.append("| — | — | Nenhuma pendência restante na lista prioritária essencial. |")
    lines += [
        "",
        "## Série 5.000–11.999",
        "",
        "A reconciliação por identidade do catálogo Senado (1966–2009) e a coleta retomável",
        "estão em `catalogo-serie-reconciliacao.json` e `serie-estado/`. Ausência de arquivo",
        "canônico ou falha de transporte não prova inexistência da lei.",
        "",
        "## Limites",
        "",
        "- A ausência de arquivo canônico não prova inexistência da lei.",
        "- Resposta HTTP vazia/bloqueada não entra como inexistência.",
        "- Lei modificadora pode ser publicada com relação pendente à base; não gera consolidação automática.",
        "",
    ]
    return "\n".join(lines)


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
        descricao=(
            "Lote prioritário da #71: leis ordinárias federais essenciais da faixa "
            "5.000–11.999 recuperadas do Planalto com cobertura integral "
            "(inclui normalização tipográfica de ordinais)."
        ),
        gerado_em=now_utc(),
        vigencia_certificada=False,
        documentos=manifest_docs,
        ja_no_acervo=JA_NO_ACERVO,
        prioridade_restante=PRIORIDADE_RESTANTE,
        catalogo_prioridades=str(CATALOGO_PRIORIDADES.relative_to(ROOT)),
        catalogo_serie=str(SERIE_CATALOGO.relative_to(ROOT)),
        limites=[
            "Lista prioritária essencial; série ampla em catalogo-serie-reconciliacao.json.",
            "Não altera nucleo_licitacoes nem README agregado.",
            "Sem segunda fonte de conferência nesta entrega.",
            "Normalização ordinal é tipográfica (markup), não jurídica.",
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
    # pendências antes de gravar manifesto (preenche PRIORIDADE_RESTANTE)
    pend_text = write_pendencias(manifest["documentos"])
    manifest["prioridade_restante"] = PRIORIDADE_RESTANTE
    write_json(MANIFESTO, manifest)
    write_json(PROVAS / "ferramentas.json", nl.tool_versions())
    PENDENCIAS.write_text(pend_text, encoding="utf-8")
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
    if not CATALOGO_PRIORIDADES.is_file():
        problems.append("prioridades-catalogo.json ausente")
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
        # Lei 9784: regressão do bug 1o/1oo
        if doc["norma"]["numero"] == "9784":
            if proofs[slug]["cobertura_texto"]["equivalente"] is not True:
                problems.append("9784: cobertura 1o/1oo ainda falha")
            if not pub.get("normalizacao_ordinal_planalto"):
                problems.append("9784: prova sem marcação de normalização ordinal")
    # Aceite: cada entrada do catálogo prioritário publicada OU já no acervo OU em PENDENCIAS.
    pend_text = PENDENCIAS.read_text(encoding="utf-8")
    published_nums = {d["norma"]["numero"] for d in DOCS}
    for e in _ENTRIES:
        n = str(e["numero"])
        if n in published_nums or n in JA_NO_ACERVO:
            continue
        if str(n) not in pend_text:
            problems.append(f"prioridade {n}: ausente de PENDENCIAS e do lote")
    if problems:
        raise SystemExit("verify falhou:\n- " + "\n- ".join(problems))
    print("verify ok", flush=True)


# ---------------------------------------------------------------------------
# Série 5.000–11.999: reconciliação + coleta retomável
# ---------------------------------------------------------------------------


def _iter_senado_lei_docs(year: int):
    path = SENADO_ANUAL_DIR / f"senado-LEI-{year}.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    docs = data.get("ListaDocumento", {}).get("documentos", {})
    if isinstance(docs, dict):
        docs = docs.get("documento", [])
    if isinstance(docs, dict):
        docs = [docs]
    return docs or []


def _parse_senado_date(value: str | None) -> str | None:
    if not value:
        return None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", value.strip())
    if not m:
        return None
    d, mo, y = m.groups()
    return f"{y}-{int(mo):02d}-{int(d):02d}"


def _numero_digits(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(c for c in value if c.isdigit())
    return digits or None


def reconcile_serie() -> dict:
    """Reconciliа identidades LEI do Senado (1966–2009) na faixa 5k–12k com federal/."""
    present_files = {}
    for p in (ROOT / "federal").glob("br-federal-lei-*-*-*-*.md"):
        m = re.match(r"br-federal-lei-(\d{4}-\d{2}-\d{2})-(\d+)\.md$", p.name)
        if not m:
            continue
        data, numero = m.group(1), m.group(2)
        n = int(numero)
        if SERIE_MIN <= n <= SERIE_MAX:
            present_files.setdefault(numero, []).append(dict(arquivo=str(p.relative_to(ROOT)), data=data))

    identidades = []
    revisao = []
    for year in SERIE_ANOS:
        for d in _iter_senado_lei_docs(year):
            numero = _numero_digits(d.get("numero"))
            if not numero:
                revisao.append(dict(motivo="numero-ausente", year=year, raw=d.get("id")))
                continue
            n = int(numero)
            if n < SERIE_MIN or n > SERIE_MAX:
                continue
            data = _parse_senado_date(d.get("dataassinatura") or d.get("dataAssinatura"))
            senado_id = str(d.get("id"))
            hits = present_files.get(numero, [])
            exact = [h for h in hits if data and h["data"] == data]
            if exact:
                estado = "presente-exato"
                caminho = exact[0]["arquivo"]
            elif hits:
                estado = "revisao-data-divergente"
                caminho = hits[0]["arquivo"]
                revisao.append(dict(
                    motivo="mesmo-numero-outra-data", senado_id=senado_id, numero=numero,
                    data_catalogo=data, caminhos=[h["arquivo"] for h in hits],
                ))
            else:
                estado = "ausente-canonico"
                caminho = None
            identidades.append(dict(
                senado_id=senado_id,
                tipo="LEI",
                numero=numero,
                data=data,
                ano_catalogo=year,
                ementa=(d.get("ementa") or "")[:300],
                url_senado=f"https://legis.senado.leg.br/norma/{senado_id}",
                estado_coleta=estado,
                caminho_publicado=caminho,
            ))

    totais = dict(
        identidades_catalogo_faixa=len(identidades),
        presente_exato=sum(1 for i in identidades if i["estado_coleta"] == "presente-exato"),
        revisao_data_divergente=sum(1 for i in identidades if i["estado_coleta"] == "revisao-data-divergente"),
        ausente_canonico=sum(1 for i in identidades if i["estado_coleta"] == "ausente-canonico"),
        revisao_registros=len(revisao),
        anos_catalogo=list(SERIE_ANOS),
        faixa=[SERIE_MIN, SERIE_MAX],
    )
    catalogo = dict(
        fonte_catalogo="https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=LEI&ano=AAAA",
        snapshots_dir=str(SENADO_ANUAL_DIR.relative_to(ROOT)),
        gerado_em=now_utc(),
        criterio=(
            "Correspondência por espécie LEI + número + dataassinatura na faixa 5000–11999; "
            "IDs do Senado preservados; falha de transporte não vira ausência; "
            "ementa/registro não substituem íntegra."
        ),
        totais=totais,
        revisao=revisao[:500],
        identidades=identidades,
    )
    write_json(SERIE_CATALOGO, catalogo)
    print(
        f"reconcile-serie: {totais['identidades_catalogo_faixa']} identidades; "
        f"presentes={totais['presente_exato']} ausentes={totais['ausente_canonico']} "
        f"revisão-data={totais['revisao_data_divergente']}",
        flush=True,
    )
    return catalogo


def _planalto_candidates(numero: int, year: int | None, data: str | None) -> list[str]:
    n = numero
    y = year or (int(data[:4]) if data else None)
    dotted = f"{n // 1000}.{n % 1000:03d}" if n >= 1000 else str(n)
    urls = [
        f"https://www.planalto.gov.br/ccivil_03/leis/L{n}.htm",
        f"https://www.planalto.gov.br/ccivil_03/leis/l{n}.htm",
        f"https://www.planalto.gov.br/ccivil_03/leis/L{n}compilada.htm",
        f"https://www.planalto.gov.br/ccivil_03/leis/L{n}Compilado.htm",
        f"https://www.planalto.gov.br/ccivil_03/leis/L{n}compilado.htm",
        f"https://www.planalto.gov.br/ccivil_03/leis/L{n}cons.htm",
    ]
    if y:
        urls += [
            f"https://www.planalto.gov.br/ccivil_03/leis/leis_{y}/l{n}.htm",
            f"https://www.planalto.gov.br/ccivil_03/leis/leis_{y}/L{n}.htm",
            f"https://www.planalto.gov.br/ccivil_03/leis/{y}/l{n}.htm",
            f"https://www.planalto.gov.br/ccivil_03/leis/{y}/L{n}.htm",
            f"https://www.planalto.gov.br/ccivil_03/leis/{y}/l{dotted}.htm",
            f"https://www.planalto.gov.br/ccivil_03/leis/{y}/L{dotted}.htm",
        ]
        # Pastas _ato* só existem para o intervalo do mandato; não gerar URLs absurdas.
        if 1999 <= y <= 2001:
            urls += [
                f"https://www.planalto.gov.br/ccivil_03/_ato1999-2001/{y}/lei/l{n}.htm",
                f"https://www.planalto.gov.br/ccivil_03/_ato1999-2001/{y}/lei/l{dotted}.htm",
            ]
        elif 2002 <= y <= 2003:
            urls += [
                f"https://www.planalto.gov.br/ccivil_03/_ato2002-2003/{y}/lei/l{n}.htm",
                f"https://www.planalto.gov.br/ccivil_03/_Ato2002-2003/{y}/Lei/L{n}.htm",
            ]
        elif 2004 <= y <= 2006:
            urls += [
                f"https://www.planalto.gov.br/ccivil_03/_ato2004-2006/{y}/lei/l{n}.htm",
                f"https://www.planalto.gov.br/ccivil_03/_ato2004-2006/{y}/lei/l{dotted}.htm",
                f"https://www.planalto.gov.br/ccivil_03/_ato2004-2006/{y}/lei/l{dotted}compilado.htm",
                f"https://www.planalto.gov.br/ccivil_03/_Ato2004-2006/{y}/Lei/L{n}.htm",
            ]
        elif 2007 <= y <= 2010:
            urls += [
                f"https://www.planalto.gov.br/ccivil_03/_ato2007-2010/{y}/lei/l{n}.htm",
                f"https://www.planalto.gov.br/ccivil_03/_Ato2007-2010/{y}/Lei/L{n}.htm",
            ]
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def collect_serie(limit: int | None = None, resume: bool = True) -> dict:
    """Coleta retomável Planalto para identidades ausentes do catálogo da série."""
    if not SERIE_CATALOGO.is_file():
        reconcile_serie()
    catalogo = json.loads(SERIE_CATALOGO.read_text(encoding="utf-8"))
    SERIE_ESTADO_DIR.mkdir(parents=True, exist_ok=True)
    state = {}
    if resume and SERIE_ESTADO_JSON.is_file():
        state = json.loads(SERIE_ESTADO_JSON.read_text(encoding="utf-8"))

    def _skip_row(sid: str) -> bool:
        st = state.get(sid) or {}
        if st.get("ok"):
            return True
        # 404 esgotado e adiamentos de onda ficam no estado; falha de transporte é retomável.
        status = st.get("status")
        if status in {"http-404-esgotado", "adiado-onda-pos-1990"}:
            return True
        return False

    pending = [
        row for row in catalogo["identidades"]
        if row["estado_coleta"] == "ausente-canonico" and not _skip_row(row["senado_id"])
    ]
    if limit is not None:
        pending = pending[:limit]

    capture_dir = SERIE_ESTADO_DIR / "capturas"
    capture_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    ok_count = 0
    for row in pending:
        sid = row["senado_id"]
        numero = int(row["numero"])
        year = row.get("ano_catalogo")
        file_name = f"planalto-L{numero}-{sid}.htm"
        dest = capture_dir / file_name
        header = capture_dir / (file_name + ".headers")
        found = None
        attempts = []
        for url in _planalto_candidates(numero, year, row.get("data")):
            rec = _curl_fetch(url, dest, header)
            attempts.append(dict(url=url, status=rec.get("http_status"), bytes=rec.get("bytes"),
                                 utilizavel=rec.get("utilizavel"), motivo=rec.get("motivo")))
            print(f"serie {numero} {sid}: {rec.get('http_status')} {rec.get('bytes')} {url}", flush=True)
            if rec.get("utilizavel"):
                found = dict(url=url, effective=rec.get("url_final"), bytes=rec.get("bytes"),
                             sha256=rec.get("sha256"), capturado_em=rec.get("capturado_em"),
                             file=str(dest.relative_to(ROOT)))
                break
        header.unlink(missing_ok=True)
        if found:
            state[sid] = dict(
                ok=True, numero=str(numero), data=row.get("data"), ano=year,
                ementa=row.get("ementa"), **found, attempts=attempts[:8],
            )
            ok_count += 1
        else:
            statuses = {str(a.get("status")) for a in attempts}
            status = "http-404-esgotado" if statuses <= {"404"} and attempts else "falha-transporte-ou-url"
            state[sid] = dict(
                ok=False, status=status, numero=str(numero), data=row.get("data"), ano=year,
                attempts=attempts[:12],
                leitura=(
                    "HTTP 404 em todos os candidatos tentados não prova inexistência; "
                    "permanece pendente de outra URL oficial ou nova captura."
                    if status == "http-404-esgotado"
                    else "Falha de transporte/URL; não classificar como ausência normativa."
                ),
            )
        done += 1
        write_json(SERIE_ESTADO_JSON, state)
    summary = dict(
        gerado_em=now_utc(),
        processados=done,
        ok=ok_count,
        estado=str(SERIE_ESTADO_JSON.relative_to(ROOT)),
        pendentes_restantes=sum(
            1 for row in catalogo["identidades"]
            if row["estado_coleta"] == "ausente-canonico"
            and not (state.get(row["senado_id"], {}) or {}).get("ok")
        ),
    )
    write_json(SERIE_ESTADO_DIR / "collect-summary.json", summary)
    print(f"collect-serie: processados={done} ok={ok_count} pendentes≈{summary['pendentes_restantes']}", flush=True)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_fetch = sub.add_parser("fetch")
    p_fetch.add_argument("dir", type=Path)
    p_fetch.add_argument("--no-resume", action="store_true")
    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("dir", type=Path)
    p_ingest.add_argument("--capturado-em", default=None)
    sub.add_parser("build")
    sub.add_parser("verify")
    sub.add_parser("reconcile-serie")
    p_collect = sub.add_parser("collect-serie")
    p_collect.add_argument("--limit", type=int, default=None)
    p_collect.add_argument("--no-resume", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "fetch":
        fetch(args.dir, resume=not args.no_resume)
    elif args.cmd == "ingest":
        ingest_capture(args.dir, args.capturado_em)
    elif args.cmd == "build":
        build()
    elif args.cmd == "verify":
        verify()
    elif args.cmd == "reconcile-serie":
        reconcile_serie()
    elif args.cmd == "collect-serie":
        collect_serie(limit=args.limit, resume=not args.no_resume)


if __name__ == "__main__":
    main()
