#!/usr/bin/env python3
"""Recuperação de peças ANEXO/TABELA via LexML → Câmara (issues #84/#95/#96).

Os marcadores `<<ANEXO>>`/`<<TABELA>>` no HTML de normas.leg.br são placeholders
oficiais (`&lt;&lt;ANEXO&gt;&gt;` no fonte), não artefato do conversor. A Câmara
costuma publicar os anexos em `.doc`/`.pdf` na ficha `*-norma-pe.html`.

Política:
- `.doc`/`.docx`: converter com LibreOffice → HTML → nucleo_licitacoes.convert_html
  e substituir marcadores na ordem; publicar só com cobertura fonte→Markdown.
- `.pdf`: capturar snapshot e metadados; não publicar OCR/layout multicoluna
  como íntegra (risco de texto falso). Status documentado na matriz.
- Planalto indisponível (conexão) não vira ausência/vigência.
"""
from __future__ import annotations

import hashlib
import lzma
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

# Marcador literal ou escapado em HTML de normas.leg.br
ANEXO_MARK = re.compile(
    r'(?:<<|&lt;&lt;)(ANEXOS?|TABELAS?|TEBELAS?)(?:\s+[IVXLC\d]+)?(?:>>|&gt;&gt;)',
    re.I,
)
ANEXO_BLOCK = re.compile(r'^<<\s*(ANEXOS?|TABELAS?|TEBELAS?)(?:\s+[IVXLC\d]+)?\s*>>\s*$', re.I)
MP_ID = re.compile(r'^br-federal-medida-provisoria-(\d{4})-(\d{2})-(\d{2})-(\d+)(?:-(\d+))?$')
DEL_ID = re.compile(r'^br-federal-decreto-lei-(\d{4})-(\d{2})-(\d{2})-(\d+)$')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def html_has_anexo_mark(text: str) -> bool:
    return bool(ANEXO_MARK.search(text))


def fetch_url(url: str, timeout: int = 120) -> tuple[bytes, dict]:
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        headers = {k.lower(): v for k, v in resp.headers.items()}
        headers['final_url'] = resp.geturl()
        headers['status'] = str(resp.status)
        return data, headers


def urn_for_mp(date: str, numero: int, reedicao=None) -> str:
    if reedicao in (None, '', '0', 0):
        return f'urn:lex:br:federal:medida.provisoria:{date};{numero}'
    return f'urn:lex:br:federal:medida.provisoria:{date};{numero}-{int(str(reedicao).strip())}'


def urn_for_del(date: str, numero: int) -> str:
    return f'urn:lex:br:federal:decreto.lei:{date};{numero}'


def parse_key_mp(key: str) -> dict | None:
    m = MP_ID.match(key)
    if not m:
        return None
    y, mo, d, num, reed = m.groups()
    return {
        'date': f'{y}-{mo}-{d}',
        'numero': int(num),
        'reedicao': int(reed) if reed else None,
        'especie': 'medida.provisoria',
    }


def parse_key_del(key: str) -> dict | None:
    m = DEL_ID.match(key)
    if not m:
        return None
    y, mo, d, num = m.groups()
    return {'date': f'{y}-{mo}-{d}', 'numero': int(num), 'especie': 'decreto.lei'}


def lexml_page_url(urn: str) -> str:
    return 'https://www.lexml.gov.br/urn/' + urn


def discover_camara_norma(key: str, especie: str = 'medida.provisoria') -> dict:
    """Resolve ficha Câmara e lista de anexos via LexML."""
    if especie == 'medida.provisoria':
        meta = parse_key_mp(key)
        if not meta:
            return {'id': key, 'status': 'id-invalido'}
        urn = urn_for_mp(meta['date'], meta['numero'], meta.get('reedicao'))
        cam_path = 'medpro'
    else:
        meta = parse_key_del(key)
        if not meta:
            return {'id': key, 'status': 'id-invalido'}
        urn = urn_for_del(meta['date'], meta['numero'])
        cam_path = 'declei'
    try:
        raw, headers = fetch_url(lexml_page_url(urn))
    except Exception as exc:  # noqa: BLE001
        return {'id': key, 'status': 'lexml-falha', 'urn': urn, 'erro': str(exc)}
    html = raw.decode('utf-8', 'replace')
    cam = re.findall(
        rf'https?://(?:www2\.)?camara\.(?:leg|gov)\.br/legin/fed/{cam_path}/[^"\s<>]+',
        html,
        re.I,
    )
    in_links = re.findall(r'https?://pesquisa\.in\.gov\.br/[^"\s<>]+', html)
    norma = None
    for link in cam:
        if 'norma-pe' in link or 'normaatualizada' in link.lower():
            norma = link
            break
    if not norma:
        for link in cam:
            mm = re.search(
                rf'((?:medida)?provisoria|(?:decreto)?lei)-.+?-\d+(?:-\d+)?(?=-publicacaooriginal|-norma|-anexo)',
                link,
                re.I,
            )
            if not mm:
                mm = re.search(r'(medidaprovisoria-.+?-\d+|decretolei-.+?-\d+)', link, re.I)
            if mm:
                base = link.rsplit('/', 1)[0]
                stem = mm.group(1)
                # prefer exact stem from filename
                m2 = re.search(r'/([^/]+?)-(?:publicacaooriginal|norma|anexo)', link, re.I)
                if m2:
                    stem = m2.group(1)
                norma = f'{base}/{stem}-norma-pe.html'
                break
    if not norma:
        return {
            'id': key,
            'status': 'sem-camara-norma',
            'urn': urn,
            'cam_links': cam[:5],
            'in_links': in_links[:3],
            'lexml_sha256': sha256(raw),
        }
    norma = norma.replace('http://', 'https://').replace('camara.gov.br', 'camara.leg.br')
    try:
        nh, _ = fetch_url(norma)
    except Exception as exc:  # noqa: BLE001
        return {
            'id': key, 'status': 'norma-falha', 'urn': urn, 'norma': norma,
            'erro': str(exc), 'in_links': in_links[:3],
        }
    nhtml = nh.decode('utf-8', 'replace')
    hrefs = sorted(set(re.findall(r'href="([^"]*anexo[^"]*)"', nhtml, re.I)))
    base = norma.rsplit('/', 1)[0]
    anexos = []
    for href in hrefs:
        if href.startswith('http'):
            anexos.append(href.replace('http://', 'https://').replace('camara.gov.br', 'camara.leg.br'))
        else:
            anexos.append(base + '/' + href.lstrip('./'))
    ext: dict[str, int] = {}
    for a in anexos:
        e = a.rsplit('.', 1)[-1].lower()
        ext[e] = ext.get(e, 0) + 1
    return {
        'id': key,
        'status': 'ok' if anexos else 'camara-sem-anexo',
        'urn': urn,
        'norma': norma,
        'anexos': anexos,
        'ext': ext,
        'n_anexos': len(anexos),
        'in_links': in_links[:3],
        'lexml_sha256': sha256(raw),
        'norma_sha256': sha256(nh),
    }


def convert_office_to_html(src: Path, out_dir: Path) -> Path:
    """LibreOffice headless → HTML. Requer `soffice` no PATH."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        'soffice', '--headless', '--convert-to', 'html:HTML',
        '--outdir', str(out_dir), str(src),
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    html = out_dir / (src.stem + '.html')
    if not html.exists():
        # LibreOffice sometimes lowercases
        cands = list(out_dir.glob(src.stem + '.*html*')) + list(out_dir.glob('*.html'))
        if not cands:
            raise FileNotFoundError(f'conversao sem html: {src}')
        html = cands[0]
    return html


def download_and_store_anexo(
    url: str,
    dest_xz: Path,
    work_dir: Path,
) -> dict:
    """Baixa peça Câmara, guarda .xz e devolve metadados + caminho HTML convertido se .doc."""
    data, headers = fetch_url(url)
    dest_xz.parent.mkdir(parents=True, exist_ok=True)
    dest_xz.write_bytes(lzma.compress(data))
    ctype = (headers.get('content-type') or '').lower()
    name = url.rstrip('/').rsplit('/', 1)[-1]
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    rec = {
        'url': url,
        'sha256': sha256(data),
        'bytes': len(data),
        'content_type': ctype,
        'ext': ext,
        'snapshot': str(dest_xz),
        'final_url': headers.get('final_url'),
    }
    if ext in ('doc', 'docx') or 'msword' in ctype or 'officedocument' in ctype:
        work_dir.mkdir(parents=True, exist_ok=True)
        raw_path = work_dir / name
        raw_path.write_bytes(data)
        html_path = convert_office_to_html(raw_path, work_dir / 'html')
        rec['html_convertido'] = html_path.read_bytes()
        rec['html_sha256'] = sha256(rec['html_convertido'])
        rec['conversao'] = 'soffice-html'
        rec['publicavel'] = True
    elif ext == 'pdf' or 'pdf' in ctype:
        rec['conversao'] = 'pdf-facsimile'
        rec['publicavel'] = False
        rec['bloqueio'] = (
            'PDF da Câmara capturado; conversão tipográfica/multicoluna DOU não '
            'certifica literalidade — não publicar como íntegra até reconversão confiável.'
        )
    else:
        rec['conversao'] = 'formato-desconhecido'
        rec['publicavel'] = False
        rec['bloqueio'] = f'extensão/ctype não suportada: {ext}/{ctype}'
    return rec


def is_anexo_marker_block(plain: str) -> bool:
    """True se o bloco convertido é só o placeholder <<ANEXO>>/<<TABELA>>."""
    compact = re.sub(r'\s+', '', plain)
    if len(compact) > 48:
        return False
    return bool(ANEXO_MARK.search(plain))


def splice_anexo_blocks(
    main_blocks: list[str],
    anexo_block_groups: list[list[str]],
    md_plain,
) -> list[str] | None:
    """Substitui blocos-placeholder pelos blocos convertidos dos anexos Câmara.

    - 1 marcador + N anexos → concatena todos no lugar do marcador
    - N marcadores + N anexos → casa na ordem
    - N marcadores + 1 anexo → primeiro recebe; demais marcadores são removidos
    - outras contagens → None (ambiguidade; manter retido)
    """
    mark_idxs = [
        i for i, b in enumerate(main_blocks)
        if is_anexo_marker_block(md_plain(b, True).strip())
    ]
    if not mark_idxs or not anexo_block_groups:
        return None

    groups = list(anexo_block_groups)
    if len(mark_idxs) == 1 and len(groups) > 1:
        merged: list[str] = []
        for g in groups:
            merged.extend(g)
        groups = [merged]
    elif len(groups) == 1 and len(mark_idxs) > 1:
        groups = groups + [[] for _ in range(len(mark_idxs) - 1)]
    elif len(mark_idxs) != len(groups):
        return None

    out: list[str] = []
    used = 0
    mark_set = set(mark_idxs)
    for i, b in enumerate(main_blocks):
        if i not in mark_set:
            out.append(b)
            continue
        plain = md_plain(b, True).strip()
        label = 'ANEXO'
        mm = ANEXO_MARK.search(plain)
        if mm:
            label = mm.group(1).upper()
        pieces = groups[used] if used < len(groups) else []
        used += 1
        if pieces:
            out.append(f'###### {label}')
            out.extend(pieces)
    return out


def diagnose_marker_in_html(html: str) -> dict:
    """Classifica placeholders oficiais no HTML normas.leg.br."""
    esc = list(re.finditer(r'&lt;&lt;(ANEXOS?|TABELAS?|TEBELAS?)(?:[^&]*)&gt;&gt;', html, re.I))
    lit = list(re.finditer(r'<<(ANEXOS?|TABELAS?|TEBELAS?)(?:[^>]*)>>', html, re.I))
    kinds: dict[str, int] = {}
    for m in esc + lit:
        k = m.group(1).upper()
        kinds[k] = kinds.get(k, 0) + 1
    trailing = ''
    last = None
    if esc:
        last = esc[-1]
    elif lit:
        last = lit[-1]
    if last:
        after = re.sub(r'<[^>]+>', ' ', html[last.end():])
        after = re.sub(r'&\w+;', ' ', after)
        trailing = re.sub(r'\s+', ' ', after).strip()[:200]
    return {
        'marcadores_escapados': len(esc),
        'marcadores_literais': len(lit),
        'kinds': kinds,
        'origem': 'placeholder-oficial-normas.leg.br' if (esc or lit) else 'ausente-no-html-bruto',
        'texto_apos_ultimo': trailing,
        'nota': (
            'Marcadores `&lt;&lt;ANEXO&gt;&gt;` são placeholders da digitação Senado/normas.leg.br '
            'indicando peça não embutida no HTML; não são gerados pelo convert_html.'
        ),
    }
