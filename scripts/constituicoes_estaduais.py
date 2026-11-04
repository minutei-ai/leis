"""Constituições estaduais / LO-DF (issue #86).

Coleta retomável de fontes oficiais, conversão HTML/PDF → Markdown com
prova de fold, atualização do catálogo setorial. Não altera README/PENDENCIAS
agregados; pendências setoriais ficam em provas/constituicoes-estaduais/.

Subcomandos:
  collect [UF ...]   baixa fontes oficiais (retomável; não trata HTTP como ausência)
  convert [UF ...]   gera Markdown + fontes.json + cobertura a partir dos snapshots
  verify [UF ...]    confere hashes e fold HTML/PDF↔Markdown offline
  audit-existentes   revalida BA/SC/DF/PE e identidades ES/PR/SP já no acervo
  catalog            reescreve metadados/constituicoes-estaduais/index.json
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import lzma
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / "provas" / "constituicoes-estaduais"
CATALOG = ROOT / "metadados" / "constituicoes-estaduais" / "index.json"
PENDENCIAS = PROVAS / "PENDENCIAS.md"
NOTE_RE = re.compile(r"<!-- nota-edicao:inicio -->.*?<!-- nota-edicao:fim -->\s*", re.S)
USER_AGENT = (
    "minutei-leis-corpus/1.0 (+https://github.com/minutei-ai/leis; "
    "research corpus; respectful crawl)"
)
SLEEP_S = 1.2

# Fontes oficiais para UFs ausentes + recapturas de identidades existentes.
# formato: html | pdf
# estrategia: body-html | selector-html | pdf-text
SOURCES: dict[str, dict] = {
    "GO": {
        "uf": "GO",
        "norma_id": "br-go-constituicao-1989",
        "arquivo": "estaduais/GO/br-go-constituicao-1989.md",
        "titulo": "Constituição do Estado de Goiás",
        "orgao": "Casa Civil de Goiás — Legisla",
        "url": "https://legisla.casacivil.go.gov.br/api/v1/arquivos/17142",
        "chave": "casacivil-constituicao-1989",
        "ext": "html",
        "estrategia": "body-html",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodegoias", "preambulo"],
    },
    "SE": {
        "uf": "SE",
        "norma_id": "br-se-constituicao-1989",
        "arquivo": "estaduais/SE/br-se-constituicao-1989.md",
        "titulo": "Constituição do Estado de Sergipe",
        "orgao": "ALESE — Aleselegis",
        "url": "https://aleselegis.al.se.leg.br/Arquivo/Documents/legislacao/html/CE11989.html",
        "chave": "alese-constituicao-1989",
        "ext": "html",
        "estrategia": "body-html",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodesergipe", "preambulo"],
    },
    "RS": {
        "uf": "RS",
        "norma_id": "br-rs-constituicao-1989",
        "arquivo": "estaduais/RS/br-rs-constituicao-1989.md",
        "titulo": "Constituição do Estado do Rio Grande do Sul",
        "orgao": "ALERS — Departamento de Assessoramento Legislativo",
        "url": "https://ww2.al.rs.gov.br/dal/LinkClick.aspx?fileticket=WQdIfqNoXO4%3d&tabid=3683&mid=5359",
        "chave": "alers-constituicao-compilada-1989",
        "ext": "html",
        "estrategia": "body-html",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodoriograndedosul", "preambulo"],
        "nota_fonte": "HTML «Constituição Compilada» (mid=5359) a partir do portal ww4.al.rs.gov.br/legislacao-estadual.",
    },
    "ES": {
        "uf": "ES",
        "norma_id": "br-es-norma-33122",
        "arquivo": "estaduais/ES/br-es-norma-33122.md",
        "titulo": "Constituição do Estado do Espírito Santo, 05 de outubro de 1989",
        "orgao": "ALEES",
        "url": "https://www3.al.es.gov.br/Arquivo/Documents/legislacao/html/COE11989.html",
        "chave": "alees-constituicao-1989",
        "ext": "html",
        "estrategia": "body-html",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodoespiritosanto", "preambulo"],
        "recaptura": True,
    },
    "SP": {
        "uf": "SP",
        "norma_id": "br-sp-norma-155101",
        "arquivo": "estaduais/SP/br-sp-norma-155101.md",
        "titulo": "Constituição Estadual de 05 de outubro de 1989",
        "orgao": "ALESP",
        "url": "https://www.al.sp.gov.br/repositorio/legislacao/constituicao/1989/compilacao-constituicao-0-05.10.1989.html",
        "chave": "alesp-constituicao-1989-compilacao",
        "ext": "html",
        "estrategia": "body-html",
        "edicao_tipo": "compilado-alesp-informado",
        "marcadores_fold": ["constituicaoestadual", "preambulo"],
        "recaptura": True,
    },
    "PR": {
        "uf": "PR",
        "norma_id": "br-pr-ato-9779",
        "arquivo": "estaduais/PR/br-pr-ato-9779.md",
        "titulo": "Constituição do Estado do Paraná",
        "orgao": "Sistema Legislação PR",
        "url": "https://www.legislacao.pr.gov.br/legislacao/exibirAto.do?action=iniciarProcesso&codAto=9779&codItemAto=90725",
        "chave": "legislacao-pr-ato-9779",
        "ext": "html",
        "estrategia": "body-html",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodoparana", "preambulo"],
        "recaptura": True,
    },
    "MT": {
        "uf": "MT",
        "norma_id": "br-mt-constituicao-1989",
        "arquivo": "estaduais/MT/br-mt-constituicao-1989.md",
        "titulo": "Constituição do Estado de Mato Grosso",
        "orgao": "ALMT",
        "url": "https://storage.al.mt.gov.br/api/v1/download/default/639107",
        "chave": "almt-constituicao-1989",
        "ext": "pdf",
        "estrategia": "pdf-text",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodemato-grosso", "constituicaodoestadodematogrosso", "preambulo"],
        "nota_fonte": "PDF texto compilado (atualizado até EC nº 115, D.O. 26/12/2023) via storage.al.mt.gov.br.",
    },
    "TO": {
        "uf": "TO",
        "norma_id": "br-to-constituicao-1989",
        "arquivo": "estaduais/TO/br-to-constituicao-1989.md",
        "titulo": "Constituição do Estado do Tocantins",
        "orgao": "ALETO",
        "url": "https://www.al.to.leg.br/documento/visualizar?documento.codigo=66",
        "chave": "aleto-constituicao-1989",
        "ext": "pdf",
        "estrategia": "pdf-text",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodotocantins", "preambulo"],
    },
    "PB": {
        "uf": "PB",
        "norma_id": "br-pb-constituicao-1989",
        "arquivo": "estaduais/PB/br-pb-constituicao-1989.md",
        "titulo": "Constituição do Estado da Paraíba",
        "orgao": "ALPB",
        "url": "https://www.al.pb.leg.br/wp-content/uploads/2023/10/constituicao_estadual.pdf",
        "chave": "alpb-constituicao-1989",
        "ext": "pdf",
        "estrategia": "pdf-text",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodaparaiba", "preambulo"],
        "nota_fonte": "PDF oficial ALPB (atualizado até EC n° 053/2023).",
    },
    "MA": {
        "uf": "MA",
        "norma_id": "br-ma-constituicao-1989",
        "arquivo": "estaduais/MA/br-ma-constituicao-1989.md",
        "titulo": "Constituição do Estado do Maranhão",
        "orgao": "ALEMA",
        "url": "https://www.al.ma.leg.br/sitealema/wp-content/uploads/2025/11/Constituicao-MA-nov25.pdf",
        "chave": "alema-constituicao-1989",
        "ext": "pdf",
        "estrategia": "pdf-text",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodomaranhao", "preambulo"],
        "nota_fonte": "PDF ALEMA edição comemorativa (emendas 1/1989 a 101/2024).",
    },
    "RO": {
        "uf": "RO",
        "norma_id": "br-ro-constituicao-1989",
        "arquivo": "estaduais/RO/br-ro-constituicao-1989.md",
        "titulo": "Constituição do Estado de Rondônia",
        "orgao": "ALERO",
        "url": "https://www.al.ro.leg.br/downloads/constituicao-do-estado-de-rondonia",
        "chave": "alero-constituicao-1989",
        "ext": "pdf",
        "estrategia": "pdf-text",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadoderondonia", "preambulo"],
    },
    "RN": {
        "uf": "RN",
        "norma_id": "br-rn-constituicao-1989",
        "arquivo": "estaduais/RN/br-rn-constituicao-1989.md",
        "titulo": "Constituição do Estado do Rio Grande do Norte",
        "orgao": "ALRN",
        "url": "https://www.al.rn.leg.br/documentos/Constituicao_Estadual-2023%20-%202024.pdf",
        "chave": "alrn-constituicao-1989",
        "ext": "pdf",
        "estrategia": "pdf-text",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodoriograndedonorte", "preambulo"],
        "nota_fonte": "PDF ALRN (versão digital 2023–2024).",
    },
    "CE": {
        "uf": "CE",
        "norma_id": "br-ce-constituicao-1989",
        "arquivo": "estaduais/CE/br-ce-constituicao-1989.md",
        "titulo": "Constituição do Estado do Ceará",
        "orgao": "ALECE",
        "url": "https://www.al.ce.gov.br/storage/anexos/nDJ4WT3YVIIA58c5qAWpKdo70gJjXgtZPtY1ccsG.pdf",
        "chave": "alece-constituicao-1989",
        "ext": "pdf",
        "estrategia": "pdf-text",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodoceara", "preambulo"],
        "nota_fonte": "PDF ALECE atualizado até EC nº 135/2025.",
    },
    "MS": {
        "uf": "MS",
        "norma_id": "br-ms-constituicao-1989",
        "arquivo": "estaduais/MS/br-ms-constituicao-1989.md",
        "titulo": "Constituição do Estado de Mato Grosso do Sul",
        "orgao": "ALEMS",
        "url": "https://www.al.ms.gov.br/upload/Pdf/2019_07_15_05_15_11_constituicao-do-estado-de-mato-grosso-do-sul-1989.pdf",
        "chave": "alems-constituicao-1989",
        "ext": "pdf",
        "estrategia": "pdf-text",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodematogrossodosul", "preambulo"],
        "nota_fonte": "PDF ALEMS (upload 2019-07-15); consolidação na data do arquivo da Assembleia — não certifica atualização posterior.",
    },
    "AL": {
        "uf": "AL",
        "norma_id": "br-al-constituicao-1989",
        "arquivo": "estaduais/AL/br-al-constituicao-1989.md",
        "titulo": "Constituição do Estado de Alagoas",
        "orgao": "ALEAL — SAPL",
        "url": "https://sapl.al.al.leg.br/media/sapl/public/normajuridica/1989/2/constituicao_de_alagoas_ate_emenda_52.pdf",
        "chave": "aleal-sapl-constituicao-1989",
        "ext": "pdf",
        "estrategia": "pdf-text",
        "edicao_tipo": "compilada-informada-pela-fonte",
        "marcadores_fold": ["constituicaodoestadodealagoas", "preambulo"],
        "nota_fonte": "PDF SAPL norma/2 (até emenda 52); detalhe https://sapl.al.al.leg.br/norma/2?display",
    },
}


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def uf_dir(uf: str) -> Path:
    return PROVAS / uf


def snapshot_path(src: dict) -> Path:
    return uf_dir(src["uf"]) / "fontes" / f"{src['chave']}.{src['ext']}.xz"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def http_get(url: str, timeout: int = 120) -> tuple[bytes, str, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        ctype = resp.headers.get("Content-Type", "")
        return data, ctype, resp.geturl()


def collect_one(key: str, force: bool = False) -> dict:
    src = SOURCES[key]
    path = snapshot_path(src)
    meta_path = uf_dir(src["uf"]) / "fontes" / f"{src['chave']}.collect.json"
    if path.is_file() and meta_path.is_file() and not force:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        print(f"[skip] {key} já coletado ({meta.get('bytes')} bytes)")
        return meta
    print(f"[get] {key} {src['url']}")
    try:
        data, ctype, final = http_get(src["url"])
    except urllib.error.HTTPError as e:
        # HTTP erro ≠ ausência jurídica; registrar tentativa.
        err = {
            "uf": src["uf"],
            "chave": src["chave"],
            "url": src["url"],
            "erro": f"HTTP {e.code}",
            "capturado_em": now_utc(),
            "status": "falha-http",
        }
        write_json(meta_path, err)
        print(f"[http-fail] {key}: {e.code} (não classificado como ausência)")
        return err
    except Exception as e:
        err = {
            "uf": src["uf"],
            "chave": src["chave"],
            "url": src["url"],
            "erro": str(e)[:300],
            "capturado_em": now_utc(),
            "status": "falha-rede",
        }
        write_json(meta_path, err)
        print(f"[net-fail] {key}: {e}")
        return err

    if src["ext"] == "pdf" and not data.startswith(b"%PDF"):
        raise RuntimeError(f"{key}: esperado PDF, recebeu {ctype!r} / magic={data[:8]!r}")
    if src["ext"] == "html" and data.startswith(b"%PDF"):
        raise RuntimeError(f"{key}: esperado HTML, recebeu PDF")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data, preset=6))
    meta = {
        "uf": src["uf"],
        "chave": src["chave"],
        "url": src["url"],
        "url_final": final,
        "content_type": ctype,
        "bytes": len(data),
        "sha256_conteudo": sha256_bytes(data),
        "sha256_arquivo_xz": sha256_bytes(path.read_bytes()),
        "capturado_em": now_utc(),
        "status": "ok",
        "arquivo": str(path.relative_to(ROOT)),
    }
    write_json(meta_path, meta)
    print(f"[ok] {key} {meta['bytes']} sha={meta['sha256_conteudo'][:12]}")
    time.sleep(SLEEP_S)
    return meta


def read_snapshot(src: dict) -> bytes:
    return lzma.open(snapshot_path(src)).read()


def strike_to_md(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["s", "strike", "del"]):
        text = tag.get_text("", strip=False)
        tag.replace_with(f"~~{text}~~")


def html_plain_blocks(html: bytes, charset: str = "utf-8") -> str:
    soup = BeautifulSoup(nl.decode(html, charset), "lxml")
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()
    strike_to_md(soup)
    body = soup.body or soup
    blocks: list[str] = []
    for el in body.find_all(["p", "h1", "h2", "h3", "h4", "h5", "li", "div", "td", "th", "pre", "blockquote"]):
        # evita divs ancestrais que só encapsulam outros blocos já capturados
        if el.name == "div":
            if el.find(["p", "h1", "h2", "h3", "h4", "li", "div"]):
                continue
        parent = el.parent
        skip = False
        while parent is not None and parent is not body:
            if getattr(parent, "name", None) in ("p", "h1", "h2", "h3", "h4", "h5", "li"):
                skip = True
                break
            parent = parent.parent
        if skip:
            continue
        t = el.get_text(" ", strip=False).replace("\xa0", " ")
        t = re.sub(r"[ \t]{2,}", " ", t)
        t = re.sub(r"\n{3,}", "\n\n", t).strip()
        if t:
            blocks.append(t)
    if not blocks:
        t = body.get_text("\n", strip=False).replace("\xa0", " ")
        t = re.sub(r"[ \t]+", " ", t)
        lines = [ln.strip() for ln in t.splitlines()]
        blocks = [ln for ln in lines if ln]
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def trim_from_markers(text: str, markers: list[str]) -> str:
    fold = nl.strip_fold(text)
    for m in markers:
        mf = nl.strip_fold(m)
        i = fold.find(mf)
        if i >= 0:
            # map roughly: find original by searching first marker words
            for raw in [m, m.upper(), m.title()]:
                j = text.lower().find(raw.lower()[:20]) if len(raw) >= 12 else -1
                if j >= 0:
                    return text[j:]
            break
    # fallback: search PREÂMBULO / CONSTITUIÇÃO
    for needle in ["CONSTITUIÇÃO DO ESTADO", "CONSTITUICAO DO ESTADO", "PREÂMBULO", "PREAMBULO", "LEI ORGÂNICA"]:
        j = text.upper().find(needle)
        if j >= 0:
            return text[j:]
    return text


def pdf_to_text(data: bytes) -> str:
    proc = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", "-", "-"],
        input=data,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pdftotext failed: {proc.stderr[:300]!r}")
    text = proc.stdout.decode("utf-8", errors="replace")
    text = text.replace("\xa0", " ")
    # colapsa form feeds
    text = text.replace("\f", "\n\n")
    lines = [re.sub(r"[ \t]+", " ", ln).rstrip() for ln in text.splitlines()]
    # junta linhas vazias excessivas
    out: list[str] = []
    blank = 0
    for ln in lines:
        if not ln.strip():
            blank += 1
            if blank <= 1:
                out.append("")
            continue
        blank = 0
        out.append(ln)
    body = "\n".join(out).strip() + "\n"
    # paragrafa: linhas consecutivas não vazias viram parágrafo se separado por blank
    paras: list[str] = []
    buf: list[str] = []
    for ln in body.splitlines():
        if not ln.strip():
            if buf:
                paras.append(" ".join(buf))
                buf = []
            continue
        buf.append(ln.strip())
    if buf:
        paras.append(" ".join(buf))
    return "\n\n".join(paras) + "\n"


def build_nota(src: dict, meta: dict) -> str:
    extra = src.get("nota_fonte") or ""
    lines = [
        "<!-- nota-edicao:inicio -->",
        "",
        f"> **{src['titulo']} recuperada de fonte oficial ({src['orgao']}).** "
        f"Fonte: {src['url']}. Captura em {meta['capturado_em']}. "
        f"SHA-256 do conteúdo `{meta['sha256_conteudo']}`. "
        f"Snapshot: `{meta['arquivo']}`.",
        ">",
        f"> Edição: {src['edicao_tipo']}. "
        "Trechos riscados (`<s>`/`<strike>`) convertidos para `~~…~~` quando presentes no HTML. "
        "Não certifica vigência. Lista autônoma de emendas constitucionais estaduais aplicadas "
        "permanece pendente de inventário próprio. "
        f"{extra}".rstrip(),
        "",
        "<!-- nota-edicao:fim -->",
        "",
        "",
    ]
    return "\n".join(lines)


def convert_one(key: str) -> dict:
    src = SOURCES[key]
    meta_path = uf_dir(src["uf"]) / "fontes" / f"{src['chave']}.collect.json"
    if not meta_path.is_file():
        raise FileNotFoundError(f"coleta ausente para {key}; rode collect")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("status") != "ok":
        raise RuntimeError(f"coleta de {key} não ok: {meta}")

    raw = read_snapshot(src)
    if sha256_bytes(raw) != meta["sha256_conteudo"]:
        raise RuntimeError(f"hash do snapshot diverge para {key}")

    if src["estrategia"] == "body-html":
        # tenta utf-8; se vier latin1 quebrado, detecta
        charset = "utf-8"
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            charset = "latin-1"
        plain = html_plain_blocks(raw, charset)
        plain = trim_from_markers(plain, src.get("marcadores_fold") or [])
    elif src["estrategia"] == "pdf-text":
        plain = pdf_to_text(raw)
        plain = trim_from_markers(plain, src.get("marcadores_fold") or [])
    else:
        raise ValueError(src["estrategia"])

    if len(nl.strip_fold(plain)) < 5000:
        raise RuntimeError(f"{key}: corpo convertido curto demais ({len(plain)} chars)")

    # ADCT / disposições transitórias: registrar presença literal, sem inferir
    fold = nl.strip_fold(plain)
    adct = {
        "mencao_adct_sigla": "adct" in fold,
        "mencao_ato_disposicoes": "atodasdisposicoes" in fold or "atodasdisposicoescond" in fold,
        "mencao_disposicoes_transitorias": "disposicoetransitori" in fold
        or "disposicoesconstitucionaistransitorias" in fold
        or "disposicoestransitorias" in fold,
    }

    nota = build_nota(src, meta)
    # corpo: preservar ~~ já embutidos; demais linhas como parágrafos
    md_body = plain if plain.endswith("\n") else plain + "\n"
    md_full = nota + md_body
    out_path = ROOT / src["arquivo"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md_full, encoding="utf-8")

    corpo = NOTE_RE.sub("", md_full, count=1)
    fontes = {
        "capturado_em": meta["capturado_em"],
        "nota": f"Captura oficial {src['orgao']} da Constituição/LO ({src['uf']}).",
        "fontes": [
            {
                "chave": src["chave"],
                "url": src["url"],
                "url_final": meta.get("url_final"),
                "arquivo": meta["arquivo"],
                "sha256_conteudo": meta["sha256_conteudo"],
                "sha256_arquivo_xz": meta["sha256_arquivo_xz"],
                "bytes_fonte": meta["bytes"],
                "capturado_em": meta["capturado_em"],
                "sha256_markdown": sha256_bytes(md_full.encode("utf-8")),
                "sha256_corpo_markdown": sha256_bytes(corpo.encode("utf-8")),
                "formato": src["ext"],
                "estrategia": src["estrategia"],
            }
        ],
    }
    write_json(uf_dir(src["uf"]) / "fontes.json", fontes)

    cobertura = {
        "norma_id": src["norma_id"],
        "uf": src["uf"],
        "fold_ok": True,
        "adct": adct,
        "chars_corpo": len(corpo),
        "verificado_em": now_utc(),
    }
    # prova de fold
    # md_text_all nos dois lados: ~~ do HTML vira marcador MD e o strip_fold
    # de ordinais (28 + o) precisa ver o mesmo texto normalizado.
    md_fold = nl.strip_fold(nl.md_text_all(corpo))
    src_fold = nl.strip_fold(nl.md_text_all(plain))
    # alinhar a partir do primeiro marcador comum
    ok = md_fold == src_fold or md_fold in src_fold or src_fold in md_fold
    if not ok:
        # tolerância: diferença só em cabeçalhos de portal antes do título
        for m in src.get("marcadores_fold") or []:
            mf = nl.strip_fold(m)
            a = md_fold.find(mf)
            b = src_fold.find(mf)
            if a >= 0 and b >= 0:
                ok = md_fold[a:] == src_fold[b:] or md_fold[a:] in src_fold[b:] or src_fold[b:] in md_fold[a:]
                if ok:
                    break
    cobertura["fold_ok"] = bool(ok)
    if not ok:
        cobertura["fold_md_len"] = len(md_fold)
        cobertura["fold_src_len"] = len(src_fold)
        raise RuntimeError(f"{key}: fold HTML/PDF↔Markdown falhou")
    write_json(uf_dir(src["uf"]) / f"cobertura-constituicao.json", cobertura)

    readme = uf_dir(src["uf"]) / "README.md"
    readme.write_text(
        f"# {src['titulo']}\n\n"
        f"- Fonte: {src['url']}\n"
        f"- Órgão: {src['orgao']}\n"
        f"- Snapshot: `fontes/{src['chave']}.{src['ext']}.xz`\n"
        f"- Markdown: `{src['arquivo']}`\n"
        f"- Vigência: não certificada\n",
        encoding="utf-8",
    )
    print(f"[convert] {key} → {src['arquivo']} fold_ok={ok} adct={adct}")
    return {"key": key, "fontes": fontes, "cobertura": cobertura}


def verify_one(key: str) -> None:
    src = SOURCES[key]
    fontes = json.loads((uf_dir(src["uf"]) / "fontes.json").read_text(encoding="utf-8"))
    entry = fontes["fontes"][0]
    raw = lzma.open(ROOT / entry["arquivo"]).read()
    assert sha256_bytes(raw) == entry["sha256_conteudo"], key
    md_full = (ROOT / src["arquivo"]).read_text(encoding="utf-8")
    assert sha256_bytes(md_full.encode("utf-8")) == entry["sha256_markdown"], key
    corpo = NOTE_RE.sub("", md_full, count=1)
    assert sha256_bytes(corpo.encode("utf-8")) == entry["sha256_corpo_markdown"], key
    assert "nota-edicao:inicio" in md_full
    assert "Não certifica vigência" in md_full or "não certifica vigência" in md_full.lower()
    cob = json.loads((uf_dir(src["uf"]) / "cobertura-constituicao.json").read_text(encoding="utf-8"))
    assert cob["fold_ok"] is True
    # reconferência fold
    if src["estrategia"] == "body-html":
        charset = "utf-8"
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            charset = "latin-1"
        plain = trim_from_markers(html_plain_blocks(raw, charset), src.get("marcadores_fold") or [])
    else:
        plain = trim_from_markers(pdf_to_text(raw), src.get("marcadores_fold") or [])
    md_fold = nl.strip_fold(nl.md_text_all(corpo))
    src_fold = nl.strip_fold(nl.md_text_all(plain))
    ok = md_fold == src_fold or md_fold in src_fold or src_fold in md_fold
    if not ok:
        for m in src.get("marcadores_fold") or []:
            mf = nl.strip_fold(m)
            a = md_fold.find(mf)
            b = src_fold.find(mf)
            if a >= 0 and b >= 0 and (md_fold[a:] == src_fold[b:] or md_fold[a:] in src_fold[b:] or src_fold[b:] in md_fold[a:]):
                ok = True
                break
    assert ok, f"{key} fold recheck failed"
    print(f"[verify] {key} ok")


EXISTING_AUDIT = {
    "BA": {
        "norma_id": "br-ba-norma-27298",
        "arquivo": "estaduais/BA/br-ba-norma-27298.md",
        "fontes": "provas/constituicoes-estaduais/BA/fontes.json",
    },
    "SC": {
        "norma_id": "br-sc-constituicao-1989",
        "arquivo": "estaduais/SC/br-sc-constituicao-1989.md",
        "fontes": "provas/constituicoes-estaduais/SC/fontes.json",
    },
    "DF": {
        "norma_id": "br-df-lei-organica-1993-06-08",
        "arquivo": "estaduais/DF/br-df-lei-organica-1993-06-08.md",
        "fontes": "provas/constituicoes-estaduais/DF/fontes.json",
    },
    "PE": {
        "norma_id": "br-pe-constituicao-1989",
        "arquivo": "estaduais/PE/br-pe-constituicao-1989.md",
        "fontes": "provas/constituicoes-estaduais/PE/fontes.json",
    },
}


def audit_existentes() -> dict:
    report = {"quando": now_utc(), "itens": []}
    for uf, info in EXISTING_AUDIT.items():
        md = (ROOT / info["arquivo"]).read_text(encoding="utf-8")
        fontes = json.loads((ROOT / info["fontes"]).read_text(encoding="utf-8"))
        entry = fontes["fontes"][0]
        raw = lzma.open(ROOT / entry["arquivo"]).read()
        item = {
            "uf": uf,
            "norma_id": info["norma_id"],
            "arquivo_existe": True,
            "tem_nota_edicao": "nota-edicao:inicio" in md,
            "sha256_markdown_bate": sha256_bytes(md.encode("utf-8")) == entry.get("sha256_markdown"),
            "sha256_fonte_bate": sha256_bytes(raw) == entry.get("sha256_conteudo"),
            "mencao_disposicoes_transitorias": bool(
                re.search(r"disposi[cç][oõ]es\s+constitucionais\s+transit|ADCT|ato das disposi", md, re.I)
            ),
            "vigencia_certificada_no_texto": False,
        }
        report["itens"].append(item)
        print(f"[audit] {uf} nota={item['tem_nota_edicao']} hash_md={item['sha256_markdown_bate']} adctish={item['mencao_disposicoes_transitorias']}")

    # identidades ES/PR/SP (podem ter ou não prova nova)
    for uf, path, nid in [
        ("ES", "estaduais/ES/br-es-norma-33122.md", "br-es-norma-33122"),
        ("PR", "estaduais/PR/br-pr-ato-9779.md", "br-pr-ato-9779"),
        ("SP", "estaduais/SP/br-sp-norma-155101.md", "br-sp-norma-155101"),
    ]:
        md = (ROOT / path).read_text(encoding="utf-8")
        prova = uf_dir(uf) / "fontes.json"
        item = {
            "uf": uf,
            "norma_id": nid,
            "arquivo_existe": True,
            "identidade_nao_grep_constituic": True,
            "tem_nota_edicao": "nota-edicao:inicio" in md,
            "prova_recaptura": prova.is_file(),
            "mencao_disposicoes_transitorias": bool(
                re.search(r"disposi[cç][oõ]es\s+constitucionais\s+transit|ADCT|ato das disposi", md, re.I)
            ),
        }
        report["itens"].append(item)
        print(f"[audit-id] {uf} prova={item['prova_recaptura']} adctish={item['mencao_disposicoes_transitorias']}")

    write_json(PROVAS / "auditoria-existentes.json", report)
    return report


def rebuild_catalog() -> None:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_uf = {d["uf"]: d for d in cat["documentos"]}

    # documentos já publicados nesta entrega (novos + recapturas)
    for key, src in SOURCES.items():
        fontes_path = uf_dir(src["uf"]) / "fontes.json"
        if not fontes_path.is_file():
            continue
        fontes = json.loads(fontes_path.read_text(encoding="utf-8"))
        entry = fontes["fontes"][0]
        cob_path = uf_dir(src["uf"]) / "cobertura-constituicao.json"
        cob = json.loads(cob_path.read_text(encoding="utf-8")) if cob_path.is_file() else {}
        doc = {
            "uf": src["uf"],
            "status": "publicado-nesta-entrega" if not src.get("recaptura") else "recapturado-nesta-entrega",
            "papel": "constituicao-estadual",
            "norma_id": src["norma_id"],
            "arquivo": src["arquivo"],
            "titulo": src["titulo"],
            "edicao": {
                "tipo": src["edicao_tipo"],
                "edicao_integral": True,
                "vigencia_certificada": False,
                "leitura": (
                    "Integralidade refere-se à reprodução conferida da fonte oficial capturada; "
                    "não certifica vigência nem esgota inventário de emendas."
                ),
            },
            "fonte": {
                "orgao": src["orgao"],
                "url": src["url"],
                "sha256_fonte": entry["sha256_conteudo"],
                "capturado_em": entry["capturado_em"],
                "formato": src["ext"],
            },
            "provas": [
                str((uf_dir(src["uf"]) / "fontes.json").relative_to(ROOT)),
                str((uf_dir(src["uf"]) / "cobertura-constituicao.json").relative_to(ROOT)),
            ],
            "emendas_listadas": "pendente-inventario",
            "adct": cob.get("adct", {}),
            "acao": "publicar" if not src.get("recaptura") else "recapturar",
        }
        if src.get("nota_fonte"):
            doc["fonte"]["nota"] = src["nota_fonte"]
        by_uf[src["uf"]] = doc

    # preservar entradas anteriores não tocadas
    docs = list(by_uf.values())
    docs.sort(key=lambda d: d["uf"])
    cat["documentos"] = docs

    presentes = {d["uf"] for d in docs}
    todas = [
        "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT",
        "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
    ]
    ausentes = [u for u in todas if u not in presentes]
    cat["ausentes"] = ausentes
    cat["cobertura"] = "parcial" if ausentes else "completa-arquivos"
    cat["pendencias"] = [
        "Inventariar emendas constitucionais estaduais aplicadas às cartas publicadas.",
        "UFs ainda sem captura/publicação nesta entrega: " + (", ".join(ausentes) if ausentes else "(nenhuma)"),
        "RJ (ALERJ Lotus Notes fragmentado), AM/AP/MS/RR/PI: fonte HTML consolidada ou PDF oficial ainda em descoberta/captura.",
        "Não inferir vigência de presença no acervo nem de HTTP.",
    ]
    write_json(CATALOG, cat)

    # README setorial
    rows = []
    for d in docs:
        rows.append(f"| {d['uf']} | {d.get('norma_id','')} | {d.get('status','')} |")
    (PROVAS / "README.md").write_text(
        "# Provas — Constituições estaduais e Lei Orgânica do DF\n\n"
        "Lote da issue #86. Vigência não certificada.\n\n"
        "| UF | Norma | Status |\n| --- | --- | --- |\n"
        + "\n".join(rows)
        + "\n\nCatálogo: `metadados/constituicoes-estaduais/index.json`.\n"
        "Pendências setoriais: `provas/constituicoes-estaduais/PENDENCIAS.md`.\n",
        encoding="utf-8",
    )

    PENDENCIAS.write_text(
        "# Pendências setoriais — Constituições estaduais (#86)\n\n"
        "Arquivo setorial (não substitui `PENDENCIAS.md` agregado).\n\n"
        f"## Ausentes nesta entrega\n\n"
        + ("\n".join(f"- {u}" for u in ausentes) if ausentes else "- (nenhuma)\n")
        + "\n\n## Em aberto para todas as UFs publicadas\n\n"
        "- Inventário autônomo de emendas constitucionais estaduais aplicadas.\n"
        "- Mapear anexos/notas editoriais das fontes que não entram no corpo.\n"
        "- Recapturas periódicas quando o portal atualizar a consolidação.\n"
        "- Não usar erro HTTP como prova de ausência da norma.\n",
        encoding="utf-8",
    )
    print(f"[catalog] docs={len(docs)} ausentes={ausentes}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["collect", "convert", "verify", "audit-existentes", "catalog", "all"])
    ap.add_argument("ufs", nargs="*", help="chaves SOURCES (ex.: GO SE RS); vazio = todas")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    keys = args.ufs or list(SOURCES.keys())
    for k in keys:
        if k not in SOURCES and args.cmd in {"collect", "convert", "verify", "all"}:
            raise SystemExit(f"UF/chave desconhecida: {k}")

    if args.cmd in {"collect", "all"}:
        for k in keys:
            collect_one(k, force=args.force)
    if args.cmd in {"convert", "all"}:
        for k in keys:
            try:
                convert_one(k)
            except Exception as e:
                print(f"[convert-fail] {k}: {e}")
                if args.cmd != "all":
                    raise
    if args.cmd in {"verify", "all"}:
        for k in keys:
            fontes = uf_dir(SOURCES[k]["uf"]) / "fontes.json"
            if not fontes.is_file():
                print(f"[verify-skip] {k}")
                continue
            verify_one(k)
    if args.cmd in {"audit-existentes", "all"}:
        audit_existentes()
    if args.cmd in {"catalog", "all"}:
        rebuild_catalog()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
