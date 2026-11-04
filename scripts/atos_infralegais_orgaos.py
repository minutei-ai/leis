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
SLUG_RDC = 'br-federal-rdc-anvisa-2002-02-21-50'
SLUG_RFB_V = 'br-federal-in-rfb-2022-10-17-2110'
SLUG_RFB_O = 'br-federal-in-rfb-2022-10-17-2110-original'
SLUG_CMN = 'br-federal-resolucao-cmn-2021-11-25-4966'
EXPECTED = [SLUG_RDC, SLUG_RFB_V, SLUG_RFB_O, SLUG_CMN]


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


def verify_doc(errors: list[str], docs: dict, slug: str, norma_tipo: str, orgao: str) -> None:
    if slug not in docs:
        errors.append(f'{slug} ausente do manifesto')
        return
    doc = docs[slug]
    path = ROOT / doc['arquivo']
    if not path.is_file():
        errors.append(f'{slug}: arquivo ausente')
        return
    text = path.read_text(encoding='utf-8')
    meta, body = parse_frontmatter(text)
    if meta.get('norma_tipo') != norma_tipo:
        errors.append(f'{slug}: norma_tipo deve ser {norma_tipo}')
    if meta.get('orgao_emissor') != orgao:
        errors.append(f'{slug}: orgao_emissor deve ser {orgao}')
    if meta.get('vigencia_certificada') is not False:
        errors.append(f'{slug}: vigencia_certificada deve ser false')
    if sha256(body.encode('utf-8')) != meta.get('sha256_markdown'):
        errors.append(f'{slug}: sha256_markdown diverge')
    if not re.search(r'(?m)^Art\.\s*1', body):
        errors.append(f'{slug}: Art. 1 ausente')
    if orgao not in slug:
        errors.append(f'{slug}: órgão ausente do id')


def verify() -> list[str]:
    errors: list[str] = []
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    fontes = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
    if manifest.get('vigencia_certificada') is not False:
        errors.append('vigencia_certificada do manifesto deve ser false')
    for org in ('anvisa', 'rfb', 'cmn-bcb'):
        if org not in manifest.get('catalogo_orgaos', {}):
            errors.append(f'catalogo_orgaos.{org} ausente')
        else:
            cat = manifest['catalogo_orgaos'][org]
            if not cat.get('fontes_oficiais'):
                errors.append(f'{org}: fontes_oficiais vazias')
            if not cat.get('ainda_nao_inventariado'):
                errors.append(f'{org}: ainda_nao_inventariado ausente')
            if cat.get('cobertura_completa'):
                errors.append(f'{org}: não declarar cobertura_completa')

    docs = {d['id']: d for d in manifest.get('documentos') or []}
    if sorted(docs) != sorted(EXPECTED):
        errors.append(f'documentos esperados {EXPECTED}, obtidos {sorted(docs)}')

    verify_doc(errors, docs, SLUG_RDC, 'rdc', 'anvisa')
    verify_doc(errors, docs, SLUG_RFB_V, 'in', 'rfb')
    verify_doc(errors, docs, SLUG_RFB_O, 'in', 'rfb')
    verify_doc(errors, docs, SLUG_CMN, 'resolucao-cmn', 'cmn')

    # RDC specifics
    if SLUG_RDC in docs:
        path = ROOT / docs[SLUG_RDC]['arquivo']
        text = path.read_text(encoding='utf-8')
        meta, body = parse_frontmatter(text)
        if meta.get('tabelas', 0) < 40:
            errors.append('esperadas dezenas de tabelas da RDC 50')
        if 'fac-simile:inicio' not in body:
            errors.append('fac-símile normativo ausente do Markdown')
        if '<table' not in body and body.count('| ---') < 5:
            errors.append('RDC 50 sem tabelas pesquisáveis no Markdown')
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
        else:
            snap = ROOT / fonte['snapshot']
            raw = lzma.decompress(snap.read_bytes())
            if sha256(raw) != fonte['sha256']:
                errors.append('snapshot HTML RDC diverge')
            conv = nl.convert_html(raw, fonte.get('charset') or 'latin-1', fonte['url'])
            recon = nl.blocks_to_markdown(conv.blocks, r'^RESOLUÇÃO')
            if not re.search(r'(?m)^Art\.\s*1', recon):
                errors.append('reconversão RDC sem Art. 1')
        rec = json.loads((PROVAS / f'reconciliacao-{SLUG_RDC}.json').read_text(encoding='utf-8'))
        audit = rec.get('auditoria_tabelas_diagrama') or {}
        if audit.get('soma_tabelas_pesquisaveis', 0) < 40:
            errors.append('auditoria RDC: tabelas pesquisáveis insuficientes')
        if not audit.get('conteudo_celulas_pesquisavel'):
            errors.append('auditoria RDC: células devem ser pesquisáveis')

    # RFB snapshots + distinct editions
    for key in ('rfb-2110-vigente-json', 'rfb-2110-original-json', 'rfb-2110-multivigente-json', 'rfb-2110-shell', 'rfb-2110-dou'):
        if key not in fontes:
            errors.append(f'{key} ausente de fontes.json')
            continue
        sp = ROOT / fontes[key]['snapshot']
        if not sp.is_file():
            errors.append(f'{key}: snapshot ausente')
        else:
            raw = lzma.decompress(sp.read_bytes())
            if sha256(raw) != fontes[key]['sha256']:
                errors.append(f'{key}: sha256 diverge')
    if SLUG_RFB_V in docs and SLUG_RFB_O in docs:
        v = (ROOT / docs[SLUG_RFB_V]['arquivo']).read_text(encoding='utf-8')
        o = (ROOT / docs[SLUG_RFB_O]['arquivo']).read_text(encoding='utf-8')
        _, bv = parse_frontmatter(v)
        _, bo = parse_frontmatter(o)
        if bv == bo:
            errors.append('edições RFB vigente e original não devem ser idênticas')
        if 'sijut-vigente' not in v or 'sijut-original' not in o:
            errors.append('edicao_id SIJUT ausente nas INs RFB')

    # CMN
    for key in ('cmn-4966-dou', 'cmn-4966-shell'):
        if key not in fontes:
            errors.append(f'{key} ausente de fontes.json')
            continue
        sp = ROOT / fontes[key]['snapshot']
        if not sp.is_file():
            errors.append(f'{key}: snapshot ausente')
        else:
            raw = lzma.decompress(sp.read_bytes())
            if sha256(raw) != fontes[key]['sha256']:
                errors.append(f'{key}: sha256 diverge')
    if SLUG_CMN in docs:
        text = (ROOT / docs[SLUG_CMN]['arquivo']).read_text(encoding='utf-8')
        if 'instrumento financeiro' not in text.lower():
            errors.append('CMN 4966 sem menção a instrumentos financeiros')
        if 'resolucao-cmn' not in text:
            errors.append('CMN sem norma_tipo resolucao-cmn no frontmatter')

    # Residual access notes — never falso negativo
    pend = manifest.get('pendencias_acesso') or []
    if len(pend) < 1:
        errors.append('pendencias residuais de acesso (BCB SPA / SIJUT shell) ausentes')
    for p in pend:
        if p.get('estado_acesso') in (None, 'inexistente'):
            errors.append(f"{p.get('tema') or p.get('slug_previsto')}: estado_acesso inválido")
        leitura = p.get('leitura', '')
        if 'inexist' not in leitura.lower():
            errors.append(f"{p.get('tema') or p.get('slug_previsto')}: leitura deve negar inexistência por falha de acesso")

    escopo = manifest.get('escopo') or {}
    if escopo.get('nao_cataloga_como_cobertura_completa') is not True and escopo.get('estado') != 'parcial':
        errors.append('escopo deve declarar parcialidade / não-cobertura completa')
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
