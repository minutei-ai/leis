#!/usr/bin/env python3
"""Atos infralegais por órgão — issue #75."""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import sys
from pathlib import Path

import nucleo_licitacoes as nl

ROOT = Path(__file__).resolve().parent.parent
PROVAS = ROOT / 'provas/atos-infralegais-orgaos'
MANIFEST = ROOT / 'metadados/atos-infralegais-orgaos.json'
SLUG = 'br-federal-rdc-anvisa-2002-02-21-50'


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


def verify() -> list[str]:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    fontes = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
    if manifest.get('vigencia_certificada') is not False:
        errors.append('vigencia_certificada do manifesto deve ser false')
    if 'anvisa' not in manifest.get('catalogo_orgaos', {}):
        errors.append('catalogo_orgaos.anvisa ausente')
    if 'rfb' not in manifest.get('catalogo_orgaos', {}):
        errors.append('catalogo_orgaos.rfb ausente')
    if 'cmn-bcb' not in manifest.get('catalogo_orgaos', {}):
        errors.append('catalogo_orgaos.cmn-bcb ausente')
    pend = manifest.get('pendencias_acesso') or []
    if len(pend) < 2:
        errors.append('RFB e CMN devem estar em pendencias_acesso')
    for p in pend:
        if p.get('estado_acesso') in (None, 'inexistente'):
            errors.append(f"{p.get('slug_previsto')}: estado_acesso inválido")
        if 'não' not in p.get('leitura', '').lower().replace('nao', 'não') and 'inexist' not in p.get('leitura', '').lower():
            # require explicit non-existence disclaimer
            if 'inexistência' not in p.get('leitura', '') and 'inexistencia' not in p.get('leitura', '').lower():
                errors.append(f"{p.get('slug_previsto')}: leitura deve negar inexistência por falha de acesso")

    docs = {d['id']: d for d in manifest.get('documentos') or []}
    if SLUG not in docs:
        errors.append(f'{SLUG} ausente do manifesto')
        return errors
    doc = docs[SLUG]
    path = ROOT / doc['arquivo']
    if not path.is_file():
        errors.append(f'{SLUG}: arquivo ausente')
        return errors
    text = path.read_text(encoding='utf-8')
    meta, body = parse_frontmatter(text)
    if meta.get('norma_tipo') != 'rdc':
        errors.append('norma_tipo deve ser rdc')
    if meta.get('orgao_emissor') != 'anvisa':
        errors.append('orgao_emissor deve ser anvisa')
    if meta.get('vigencia_certificada') is not False:
        errors.append('vigencia_certificada deve ser false')
    if sha256(body.encode('utf-8')) != meta.get('sha256_markdown'):
        errors.append('sha256_markdown diverge')
    if meta.get('tabelas', 0) < 40:
        errors.append('esperadas dezenas de tabelas da RDC 50')
    if 'fac-simile:inicio' not in body:
        errors.append('fac-símile normativo ausente do Markdown')
    fig = PROVAS / 'fac-similes/rdc-anvisa-50-2002-fig1.jpg'
    if not fig.is_file():
        errors.append('arquivo do fac-símile ausente')
    else:
        fig_meta = fontes.get('fac_simile_rdc50_fig1') or {}
        if fig_meta.get('sha256') and sha256(fig.read_bytes()) != fig_meta['sha256']:
            errors.append('sha256 do fac-símile diverge')
    fonte = fontes.get('rdc50-anvisa-bvs')
    if not fonte:
        errors.append('fonte rdc50 ausente')
        return errors
    snap = ROOT / fonte['snapshot']
    raw = lzma.decompress(snap.read_bytes())
    if sha256(raw) != fonte['sha256']:
        errors.append('snapshot HTML diverge')
    conv = nl.convert_html(raw, fonte.get('charset') or 'latin-1', fonte['url'])
    recon = nl.blocks_to_markdown(conv.blocks, r'^RESOLUÇÃO')
    if not re.search(r'(?m)^Art\.\s*1', recon):
        errors.append('reconversão sem Art. 1')
    # shells de evidência
    for key in ('rfb-2110-shell', 'cmn-4966-shell'):
        if key not in fontes:
            errors.append(f'{key} ausente de fontes.json')
            continue
        sp = ROOT / fontes[key]['snapshot']
        if not sp.is_file():
            errors.append(f'{key}: snapshot ausente')
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] != 'verify':
        print('uso: atos_infralegais_orgaos.py verify', file=sys.stderr)
        return 2
    errors = verify()
    if errors:
        for e in errors:
            print('ERRO:', e, file=sys.stderr)
        return 1
    print('OK: atos infralegais por órgão conferidos')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
