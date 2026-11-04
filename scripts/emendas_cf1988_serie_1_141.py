"""Matriz unificada da série Emendas CF/1988 nº 1–141 (issue #63).

Consolida a cobertura já publicada pelos lotes de faixa (PRs #91, #92, #97).
Não republica Markdown nem altera README agregado. Distingue a série CF/1988
de emendas históricas e de revisão.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FED = ROOT / 'federal'
PROVAS = ROOT / 'provas/emendas-cf1988'
OUT = PROVAS / 'serie-1-141'
MATRIZ = OUT / 'matriz-serie.json'
LOTE = 'emendas-cf1988-serie-1-141'
PRS = [
    'https://github.com/minutei-ai/leis/pull/91',
    'https://github.com/minutei-ai/leis/pull/92',
    'https://github.com/minutei-ai/leis/pull/97',
]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith('---\n'):
        return {}
    end = text.find('\n---\n', 4)
    if end < 0:
        return {}
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        meta[key.strip()] = value.strip().strip('"')
    return meta


def scan() -> dict:
    present: dict[int, dict] = {}
    for path in sorted(FED.glob('br-federal-emenda-constitucional-*.md')):
        m = re.fullmatch(
            r'br-federal-emenda-constitucional-(\d{4})-(\d{2})-(\d{2})-(\d+)\.md',
            path.name,
        )
        if not m:
            continue
        year, month, day, numero = int(m[1]), m[2], m[3], int(m[4])
        if year < 1988 or not (1 <= numero <= 141):
            continue
        text = path.read_text(encoding='utf-8')
        meta = parse_frontmatter(text)
        body = text
        if text.startswith('---\n'):
            end = text.find('\n---\n', 4)
            if end > 0:
                body = text[end + 5:]
        present[numero] = {
            'numero': numero,
            'data': f'{year}-{month}-{day}',
            'arquivo': f'federal/{path.name}',
            'fonte_url': meta.get('fonte_url', 'desconhecido'),
            'sha256_markdown': meta.get('sha256_markdown') or sha256_text(body),
            'serie': 'cf-1988',
            'especie': 'emenda-constitucional',
            'nao_e_revisao': True,
            'nao_e_constituicao_historica': True,
            'estado_coleta': 'publicado',
            'manifesto': meta.get('manifesto', 'desconhecido'),
        }

    historicas = []
    for path in sorted(FED.glob('br-federal-emenda-constitucional-*.md')):
        m = re.fullmatch(
            r'br-federal-emenda-constitucional-(\d{4})-(\d{2})-(\d{2})-(\d+)\.md',
            path.name,
        )
        if m and int(m[1]) < 1988:
            historicas.append({
                'numero': int(m[4]),
                'data': f'{m[1]}-{m[2]}-{m[3]}',
                'arquivo': f'federal/{path.name}',
                'serie': 'constituicao-historica',
            })

    revisao = sorted(p.name for p in FED.glob('br-federal-emenda*') if 'revis' in p.name.lower())
    missing = sorted(set(range(1, 142)) - set(present))
    return {
        'lote': LOTE,
        'issue': 63,
        'gerado_em': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'escopo': 'Textos autônomos das Emendas Constitucionais nº 1 a 141 à CF/1988',
        'fora_de_escopo': [
            'emendas constitucionais de revisão (emecrv)',
            'emendas a constituições históricas (data < 1988)',
            'Constituição consolidada / ADCT como substituto da emenda',
        ],
        'numeros_alvo': list(range(1, 142)),
        'recuperados': sorted(present),
        'lacunas': missing,
        'contagem': {
            'alvo': 141,
            'publicados': len(present),
            'lacunas': len(missing),
        },
        'lotes_faixa_preexistentes': {
            'faixa-001-050': 'provas/emendas-cf1988/faixa-001-050/',
            'faixa-051-100': 'provas/emendas-cf1988/faixa-051-100/',
            'faixa-101-141': 'provas/emendas-cf1988/faixa-101-141/',
            'prs_merged': PRS,
        },
        'emendas_historicas_no_acervo_nao_contam_nesta_serie': historicas,
        'emendas_revisao_no_acervo': revisao,
        'itens': [present[n] for n in sorted(present)],
        'limites': [
            'Presença do arquivo não certifica vigência nem eficácia.',
            'A Constituição consolidada cita emendas; isso não substitui o texto autônomo.',
            'Esta matriz consolida cobertura da série; provas de conversão ficam nas pastas de faixa.',
        ],
    }


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    matriz = scan()
    MATRIZ.write_text(json.dumps(matriz, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return matriz


def verify() -> None:
    if not MATRIZ.is_file():
        raise SystemExit(f'matriz ausente: {MATRIZ}')
    published = json.loads(MATRIZ.read_text(encoding='utf-8'))
    fresh = scan()
    if published['recuperados'] != fresh['recuperados']:
        raise SystemExit('matriz desatualizada: recuperados divergem do acervo')
    if published['lacunas'] != fresh['lacunas']:
        raise SystemExit('matriz desatualizada: lacunas divergem do acervo')
    if published['contagem']['publicados'] != 141 or fresh['contagem']['lacunas'] != 0:
        raise SystemExit(f"série incompleta: {fresh['contagem']}")
    print('verify ok:', fresh['contagem'])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cmd', choices=('build', 'verify', 'scan'))
    args = parser.parse_args(argv)
    if args.cmd == 'build':
        m = build()
        print(json.dumps(m['contagem'], ensure_ascii=False))
    elif args.cmd == 'verify':
        verify()
    else:
        print(json.dumps(scan()['contagem'], ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1:])
