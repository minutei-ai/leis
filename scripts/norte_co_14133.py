#!/usr/bin/env python3
"""Verificação setorial do recorte Norte/CO Lei 14.133 (issues #73/#101).

Offline: confere Markdown publicados, notas, hashes em provas e inventário
setorial. Não altera inventários compartilhados nem README agregado.

Uso:
  python3 scripts/norte_co_14133.py verify
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import nucleo_licitacoes as nl  # noqa: E402

INDEX = ROOT / 'metadados/norte-co-14133/index.json'
TENTATIVAS = ROOT / 'metadados/norte-co-14133/tentativas.json'
PROVAS = ROOT / 'provas/norte-co-14133'

PUBLICADOS = [
    {
        'norma_id': 'br-ac-decreto-2023-11-22-11363',
        'arquivo': 'estaduais/AC/br-ac-decreto-2023-11-22-11363.md',
        'provas': 'provas/norte-co-14133/AC',
        'carater': 'regulamento-geral-estadual',
        'marcador': r'DECRETO\s+N[ºo°\. ]*11\.?363',
    },
    {
        'norma_id': 'br-mt-decreto-2022-11-23-1525',
        'arquivo': 'estaduais/MT/br-mt-decreto-2022-11-23-1525.md',
        'provas': 'provas/norte-co-14133/MT',
        'carater': 'regulamento-geral-estadual',
        'marcador': r'DECRETO\s+N[ºo°\. ]*1\.?525',
    },
    {
        'norma_id': 'br-ms-decreto-2023-03-09-16122',
        'arquivo': 'estaduais/MS/br-ms-decreto-2023-03-09-16122.md',
        'provas': 'provas/norte-co-14133/MS',
        'carater': 'especifico-srp-arts-82-a-86',
        'marcador': r'DECRETO\s+N[ºo°\. ]*16\.?122',
    },
    {
        'norma_id': 'br-ap-decreto-2023-03-08-1716',
        'arquivo': 'estaduais/AP/br-ap-decreto-2023-03-08-1716.md',
        'provas': 'provas/norte-co-14133/AP',
        'carater': 'especifico-srp-arts-82-a-86',
        'marcador': r'DECRETO\s+N[ºo°\. ]*1\.?716',
    },
    {
        'norma_id': 'br-municipal-1100205-decreto-2023-03-30-18892',
        'arquivo': 'municipais/1100205/br-municipal-1100205-decreto-2023-03-30-18892.md',
        'provas': 'provas/norte-co-14133/RO-porto-velho',
        'carater': 'regulamento-geral-municipal',
        'marcador': r'DECRETO\s+N[ºo°\. ]*18\.?892',
    },
    {
        'norma_id': 'br-municipal-1100205-lei-organica-1990-03-27',
        'arquivo': 'municipais/1100205/br-municipal-1100205-lei-organica-1990-03-27.md',
        'provas': 'provas/norte-co-14133/RO-porto-velho-lo',
        'carater': 'lei-organica-municipal',
        'marcador': r'PRE[ÂA]MBULO',
        'min_arts': 40,
    },
    {
        'norma_id': 'br-municipal-1400100-lei-organica-1992-07-11',
        'arquivo': 'municipais/1400100/br-municipal-1400100-lei-organica-1992-07-11.md',
        'provas': 'provas/norte-co-14133/RR-boa-vista-lo',
        'carater': 'lei-organica-municipal',
        'marcador': r'PRE[ÂA]MBULO',
        'min_arts': 40,
    },
]

REUSO = [
    'estaduais/AM/br-am-decreto-2023-03-10-47133.md',
    'estaduais/DF/br-df-decreto-2023-03-16-44330.md',
    'estaduais/DF/br-df-lei-organica-1993-06-08.md',
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def erros_norma(spec: dict) -> list[str]:
    errs: list[str] = []
    path = ROOT / spec['arquivo']
    if not path.is_file():
        return [f"{spec['norma_id']}: arquivo ausente"]
    raw = path.read_text(encoding='utf-8')
    if '<!-- nota-edicao:inicio -->' not in raw or '<!-- nota-edicao:fim -->' not in raw:
        errs.append(f"{spec['norma_id']}: nota-edicao ausente")
    corpo = nl.strip_note(raw)
    if not re.search(spec['marcador'], corpo, re.I):
        errs.append(f"{spec['norma_id']}: marcador identidade ausente no corpo")
    min_arts = spec.get('min_arts')
    if min_arts:
        arts = len(re.findall(r'(?m)^Art\.\s*\d+', corpo))
        if arts < min_arts:
            errs.append(f"{spec['norma_id']}: poucos artigos ({arts} < {min_arts})")
    provas = ROOT / spec['provas']
    fontes = provas / 'fontes.json'
    if not fontes.is_file():
        errs.append(f"{spec['norma_id']}: fontes.json ausente")
        return errs
    data = json.loads(fontes.read_text(encoding='utf-8'))
    entries = data.get('fontes') or []
    if not entries:
        errs.append(f"{spec['norma_id']}: fontes vazias")
    md_sha = sha256_bytes(path.read_bytes())
    matched = False
    for f in entries:
        if f.get('sha256_markdown') == md_sha:
            matched = True
        snap = f.get('arquivo')
        if snap:
            sp = ROOT / snap
            if not sp.is_file():
                errs.append(f"{spec['norma_id']}: snapshot ausente {snap}")
            else:
                # xz readable
                try:
                    lzma.open(sp, 'rb').read(16)
                except Exception as exc:  # noqa: BLE001
                    errs.append(f"{spec['norma_id']}: snapshot xz ilegível ({exc})")
        if f.get('sha256_conteudo') and len(f['sha256_conteudo']) != 64:
            errs.append(f"{spec['norma_id']}: sha256_conteudo inválido")
    if not matched:
        # allow corpo hash match if markdown hash field missing on multi-fonte
        corpo_sha = sha256_bytes(corpo.encode('utf-8'))
        if not any(f.get('sha256_corpo_markdown') == corpo_sha or f.get('sha256_markdown') == md_sha for f in entries):
            errs.append(f"{spec['norma_id']}: hash markdown não confere com fontes.json")
    fold = nl.strip_fold(corpo)
    if len(fold) < 200:
        errs.append(f"{spec['norma_id']}: strip_fold curto demais ({len(fold)})")
    return errs


def verify() -> int:
    errs: list[str] = []
    if not INDEX.is_file():
        print('FAIL: index.json ausente', file=sys.stderr)
        return 1
    index = json.loads(INDEX.read_text(encoding='utf-8'))
    if index.get('issues') != [73, 101]:
        errs.append('index.issues != [73, 101]')
    if sorted(index.get('recorte_ufs') or []) != sorted(['AC','AM','AP','PA','RO','RR','TO','GO','MT','MS','DF']):
        errs.append('recorte_ufs incompleto')
    resumo = index.get('resumo') or {}
    # exact-status classification (no substring 'geral' trap)
    for uf in resumo.get('ufs_com_geral_estado') or []:
        row = next(u for u in index['ufs'] if u['uf'] == uf)
        if row['status_acervo_estado'] not in {'decreto-geral-publicado', 'decreto-geral-publicado-reuso'}:
            errs.append(f'resumo.ufs_com_geral_estado inclui {uf} indevidamente')
    for bad in ['AP', 'MS', 'PA', 'RO', 'RR', 'TO', 'GO']:
        if bad in (resumo.get('ufs_com_geral_estado') or []) and bad not in {'AM'}:
            # AP/MS are especifico; others sem geral
            row = next(u for u in index['ufs'] if u['uf'] == bad)
            if 'geral-publicado' not in row['status_acervo_estado']:
                errs.append(f'resumo classifica {bad} como geral indevidamente')

    if not TENTATIVAS.is_file():
        errs.append('tentativas.json ausente')
    else:
        tent = json.loads(TENTATIVAS.read_text(encoding='utf-8'))
        itens = tent.get('tentativas') if isinstance(tent, dict) else tent
        if not itens or len(itens) < 5:
            errs.append('tentativas.json com poucas entradas')

    for spec in PUBLICADOS:
        errs.extend(erros_norma(spec))

    for rel in REUSO:
        if not (ROOT / rel).is_file():
            errs.append(f'reuso ausente: {rel}')

    # TO evidence of block must exist
    to_fontes = PROVAS / 'TO' / 'fontes.json'
    if not to_fontes.is_file():
        errs.append('provas TO (bloqueio 6606) ausentes')

    if errs:
        print('FAIL norte-co-14133:')
        for e in errs:
            print(' -', e)
        return 1
    print(f'OK norte-co-14133: {len(PUBLICADOS)} normas novas + reuso AM/DF; inventário {len(index["ufs"])} UFs')
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in {'verify'}:
        print(__doc__)
        return 2
    return verify()


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
