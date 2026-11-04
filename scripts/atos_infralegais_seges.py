#!/usr/bin/env python3
"""Atos infralegais SEGES/ME/MGI — issue #72."""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import sys
from pathlib import Path

import nucleo_licitacoes as nl

ROOT = Path(__file__).resolve().parent.parent
PROVAS = ROOT / 'provas/atos-infralegais-seges'
MANIFEST = ROOT / 'metadados/atos-infralegais-seges.json'
TITLE_RE = r'^INSTRUÇÃO NORMATIVA'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_frontmatter(text: str):
    if not text.startswith('---\n'):
        raise ValueError('sem cabeçalho')
    end = text.index('\n---\n', 4)
    meta = {}
    for line in text[4:end].splitlines():
        key, _, value = line.partition(': ')
        meta[key] = json.loads(value)
    body = text[end + len('\n---\n'):]
    if body.startswith('\n'):
        body = body[1:]
    return meta, body


def extract_fragment(raw: bytes) -> bytes:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw, 'lxml')
    h1 = soup.select_one('h1')
    title = re.sub(r'\s+', ' ', h1.get_text(' ', strip=True)) if h1 else ''
    title = re.sub(r'\s*[—\-].*Portal de Compras.*$', '', title).strip()
    node = soup.select_one('#parent-fieldname-text')
    if node is None:
        raise RuntimeError('sem #parent-fieldname-text')
    return f'<html><body><p>{title}</p>{node.decode_contents()}</body></html>'.encode('utf-8')


def verify() -> list[str]:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    fontes = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
    if manifest.get('vigencia_certificada') is not False:
        errors.append('manifesto.vigencia_certificada deve ser false')
    if len(manifest.get('documentos') or []) != 6:
        errors.append('esperados 6 documentos publicados')
    pend = manifest.get('pendencias_acesso') or []
    if not any(p.get('norma_numero') == '5' for p in pend):
        errors.append('IN 5/2017 deve permanecer em pendencias_acesso')
    for doc in manifest['documentos']:
        slug = doc['id']
        path = ROOT / doc['arquivo']
        if not path.is_file():
            errors.append(f'{slug}: arquivo ausente')
            continue
        if not re.match(r'^br-federal-in-[a-z0-9-]+-\d{4}-\d{2}-\d{2}-\d+$', slug):
            errors.append(f'{slug}: fora do padrão de nome com órgão')
        text = path.read_text(encoding='utf-8')
        meta, body = parse_frontmatter(text)
        if meta.get('norma_tipo') != 'in':
            errors.append(f'{slug}: norma_tipo deve ser in')
        if meta.get('vigencia_certificada') is not False:
            errors.append(f'{slug}: vigencia_certificada deve ser false')
        if not meta.get('orgao_emissor'):
            errors.append(f'{slug}: orgao_emissor ausente')
        if not meta.get('lei_regulamentada'):
            errors.append(f'{slug}: lei_regulamentada ausente')
        if sha256(body.encode('utf-8')) != meta.get('sha256_markdown'):
            errors.append(f'{slug}: sha256_markdown diverge do corpo')
        if doc.get('sha256_markdown') != meta.get('sha256_markdown'):
            errors.append(f'{slug}: manifesto sha256_markdown diverge')
        fonte = fontes.get(doc['fonte'])
        if not fonte:
            errors.append(f'{slug}: fonte ausente em fontes.json')
            continue
        snap = ROOT / fonte['snapshot']
        if not snap.is_file():
            errors.append(f'{slug}: snapshot ausente')
            continue
        raw = lzma.decompress(snap.read_bytes())
        if sha256(raw) != fonte['sha256']:
            errors.append(f'{slug}: sha256 da fonte diverge do snapshot')
            continue
        frag = extract_fragment(raw)
        conv = nl.convert_html(frag, 'utf-8', fonte['url'])
        recon = nl.blocks_to_markdown(conv.blocks, TITLE_RE)
        if 'INSTRUÇÃO NORMATIVA' not in recon.split('\n', 1)[0].upper():
            errors.append(f'{slug}: reconversão sem título de IN')
        if not re.search(r'(?m)^Art\.\s*1', recon):
            errors.append(f'{slug}: reconversão sem Art. 1')
        # Corpo publicado inclui nota editorial; a reconversão do fragmento é o núcleo.
        if 'Art. 1' not in body:
            errors.append(f'{slug}: Markdown publicado sem Art. 1')
        proof_path = ROOT / doc['prova']
        if not proof_path.is_file():
            errors.append(f'{slug}: prova ausente')
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] != 'verify':
        print('uso: atos_infralegais_seges.py verify', file=sys.stderr)
        return 2
    errors = verify()
    if errors:
        for e in errors:
            print('ERRO:', e, file=sys.stderr)
        return 1
    print('OK: atos infralegais SEGES conferidos')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
