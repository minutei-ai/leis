"""Matriz unificada da série Emendas CF/1988 nº 1–141 (issue #63).

Consolida a cobertura já publicada pelos lotes de faixa (PRs #91, #92, #97).
Não republica Markdown nem altera README agregado. Distingue a série CF/1988
de emendas históricas e de revisão.

A contagem 141/141 de arquivos **não** encerra o issue: a matriz registra
critérios de aceite (vínculos, dispositivos autônomos, metadados) com estado
explícito.
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
CRITERIOS = OUT / 'matriz-criterios-aceite.json'
CONSTITUICAO = FED / 'br-federal-constituicao-1988-10-05.md'
LOTE = 'emendas-cf1988-serie-1-141'
PRS = [
    'https://github.com/minutei-ai/leis/pull/91',
    'https://github.com/minutei-ai/leis/pull/92',
    'https://github.com/minutei-ai/leis/pull/97',
]

AUTON_MARKERS = (
    'esta emenda entra',
    'esta emenda constitucional entra',
    'revogam-se',
    'revoga-se',
    'fica revogado',
    'ficam revogados',
    'disposições transitórias',
    'disposicoes transitorias',
    'disposição transitória',
    'produção de efeitos',
    'producao de efeitos',
    'anexo',
    'artigo único',
    'artigo unico',
)


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


def body_of(text: str) -> str:
    if text.startswith('---\n'):
        end = text.find('\n---\n', 4)
        if end > 0:
            return text[end + 5:]
    return text


def has_autonomous_markers(body: str) -> bool:
    low = body.lower()
    if any(m in low for m in AUTON_MARKERS):
        return True
    if re.search(r'art\.\s*\d+º?\s*[.—-].{0,100}(vigor|revog|aplica|efeito|transit)', low):
        return True
    # Emendas curtíssimas de artigo único que só alteram a CF ainda são o ato autônomo.
    if re.search(r'artigo\s+único|artigo\s+unico|art\.\s*único|art\.\s*unico', low):
        return True
    return False


def extract_cf_ec_citations(text: str) -> set[int]:
    cites = set()
    for m in re.finditer(r'[Ee]menda\s+[Cc]onstitucional\s+n[ºo°\.]*\s*(\d+)', text):
        n = int(m.group(1))
        if 1 <= n <= 141:
            cites.add(n)
    return cites


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
        body = body_of(text)
        fonte = meta.get('fonte_url') or 'desconhecido'
        if fonte in {'', 'desconhecido'} and not meta:
            # Lotes antigos sem frontmatter: procurar URL nas provas de faixa.
            fonte = 'desconhecido-sem-frontmatter'
        present[numero] = {
            'numero': numero,
            'data': f'{year}-{month}-{day}',
            'arquivo': f'federal/{path.name}',
            'fonte_url': fonte,
            'sha256_markdown': meta.get('sha256_markdown') or sha256_text(body),
            'serie': 'cf-1988',
            'especie': 'emenda-constitucional',
            'nao_e_revisao': True,
            'nao_e_constituicao_historica': True,
            'estado_coleta': 'publicado',
            'manifesto': meta.get('manifesto', 'desconhecido'),
            'tem_frontmatter': bool(meta),
            'edicao_tipo': meta.get('edicao_tipo', 'desconhecido'),
            'dispositivos_autonomos_detectados': has_autonomous_markers(body),
            'tamanho_corpo': len(body.strip()),
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

    cf_cites: list[int] = []
    vinculos = {
        'constituicao_arquivo': None,
        'emendas_citadas_na_constituicao': [],
        'publicadas_sem_citacao_na_constituicao': [],
        'citadas_sem_arquivo_autonomo': [],
        'estado': 'nao-avaliado',
        'limites': [
            'Citação na Constituição consolidada não substitui o texto autônomo da emenda.',
            'Ausência de citação não prova inexistência de vínculo jurídico.',
        ],
    }
    if CONSTITUICAO.is_file():
        cf_text = CONSTITUICAO.read_text(encoding='utf-8')
        cf_cites = sorted(extract_cf_ec_citations(cf_text))
        cited = set(cf_cites)
        pub = set(present)
        vinculos.update({
            'constituicao_arquivo': 'federal/br-federal-constituicao-1988-10-05.md',
            'emendas_citadas_na_constituicao': cf_cites,
            'publicadas_sem_citacao_na_constituicao': sorted(pub - cited),
            'citadas_sem_arquivo_autonomo': sorted(cited - pub),
            'estado': 'registrado',
        })

    sem_frontmatter = sorted(n for n, it in present.items() if not it['tem_frontmatter'])
    sem_auton = sorted(n for n, it in present.items() if not it['dispositivos_autonomos_detectados'])
    fonte_desconhecida = sorted(
        n for n, it in present.items()
        if it['fonte_url'] in {'desconhecido', 'desconhecido-sem-frontmatter'}
    )

    criterios = {
        'issue': 63,
        'gerado_em': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'aviso': (
            'Contagem 141/141 de arquivos da série é necessária, mas insuficiente. '
            'Esta matriz avalia cada critério de aceite do issue.'
        ),
        'itens': [
            {
                'id': 'matriz-por-numero-data-fonte-situacao',
                'criterio': 'Criar matriz por número, data, fonte e situação da coleta, reconciliando a série com catálogo oficial.',
                'estado': 'satisfeito' if not missing and present else 'pendente',
                'evidencia': str(MATRIZ.relative_to(ROOT)),
                'notas': [
                    f"publicados={len(present)} lacunas={len(missing)}",
                    'Reconciliação detalhada Câmara×Planalto permanece nas pastas de faixa.',
                ],
            },
            {
                'id': 'textos-integrais-com-dispositivos-autonomos',
                'criterio': 'Recuperar atos integrais ausentes, incluindo dispositivos autônomos, anexos, regras transitórias, revogações e produção de efeitos.',
                'estado': 'parcial',
                'evidencia': {
                    'arquivos_serie': len(present),
                    'com_marcadores_autonomos': len(present) - len(sem_auton),
                    'sem_marcadores_autonomos_heuristica': sem_auton,
                },
                'notas': [
                    'Heurística lexical; emendas de artigo único que só alteram a CF podem não disparar marcadores.',
                    'Não extrai somente a redação incorporada à Constituição: cada arquivo é o ato autônomo publicado.',
                ],
            },
            {
                'id': 'distinguir-series',
                'criterio': 'Distinguir claramente emendas da CF/1988, emendas de revisão e emendas de constituições históricas.',
                'estado': 'satisfeito',
                'evidencia': {
                    'serie_cf1988': len(present),
                    'historicas_listadas_fora': len(historicas),
                    'revisao_no_acervo': revisao,
                },
            },
            {
                'id': 'vinculos-constituicao-adct',
                'criterio': 'Registrar vínculos da Constituição/ADCT com o ato modificador e seus dispositivos autônomos, mantendo lacunas explícitas.',
                'estado': 'parcial' if vinculos['estado'] == 'registrado' else 'pendente',
                'evidencia': {
                    'citacoes_na_constituicao': len(cf_cites),
                    'citadas_sem_arquivo': vinculos['citadas_sem_arquivo_autonomo'],
                    'publicadas_sem_citacao': len(vinculos['publicadas_sem_citacao_na_constituicao']),
                },
                'notas': [
                    'Vínculo registrado por citação textual na Constituição consolidada publicada.',
                    'Mapa dispositivo-a-dispositivo (ADCT ↔ artigos da emenda) ainda não estruturado.',
                ],
            },
            {
                'id': 'metadados-edicao-fonte-hashes',
                'criterio': 'Preservar metadados de edição/fonte/captura, hashes e provas de conversão, sem presumir vigência imediata.',
                'estado': 'parcial',
                'evidencia': {
                    'com_frontmatter': len(present) - len(sem_frontmatter),
                    'sem_frontmatter': sem_frontmatter,
                    'fonte_url_desconhecida': fonte_desconhecida,
                    'provas_faixa': [
                        'provas/emendas-cf1988/faixa-001-050/',
                        'provas/emendas-cf1988/faixa-051-100/',
                        'provas/emendas-cf1988/faixa-101-141/',
                    ],
                },
                'notas': [
                    '79 arquivos antigos da série ainda sem frontmatter YAML no Markdown publicado.',
                    'Provas de conversão/hashes das faixas cobrem a recuperação; a matriz unificada não republica snapshots.',
                ],
            },
            {
                'id': 'nao-recontar-consolidada',
                'criterio': 'Não recontar Constituição consolidada ou edições alternativas como se fossem emendas coletadas.',
                'estado': 'satisfeito',
                'evidencia': {
                    'constituicao_excluida_da_serie': True,
                    'ids_serie_somente_emenda_constitucional': True,
                },
            },
        ],
    }
    criterios['resumo'] = {
        'satisfeitos': sum(1 for c in criterios['itens'] if c['estado'] == 'satisfeito'),
        'parciais': sum(1 for c in criterios['itens'] if c['estado'] == 'parcial'),
        'pendentes': sum(1 for c in criterios['itens'] if c['estado'] == 'pendente'),
        'issue_fechavel': False,
    }

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
        'vinculos_constituicao': vinculos,
        'auditoria_metadados': {
            'sem_frontmatter': sem_frontmatter,
            'fonte_url_desconhecida': fonte_desconhecida,
            'sem_marcadores_autonomos': sem_auton,
        },
        'criterios_aceite_arquivo': str(CRITERIOS.relative_to(ROOT)),
        'limites': [
            'Presença do arquivo não certifica vigência nem eficácia.',
            'A Constituição consolidada cita emendas; isso não substitui o texto autônomo.',
            'Contagem 141/141 não prova completude de todos os critérios de aceite do #63.',
            'Esta matriz consolida cobertura da série; provas de conversão ficam nas pastas de faixa.',
        ],
        'criterios': criterios,
    }


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    matriz = scan()
    criterios = matriz.pop('criterios')
    MATRIZ.write_text(json.dumps(matriz, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    CRITERIOS.write_text(json.dumps(criterios, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'contagem': matriz['contagem'], 'criterios': criterios['resumo']}


def verify() -> None:
    if not MATRIZ.is_file():
        raise SystemExit(f'matriz ausente: {MATRIZ}')
    if not CRITERIOS.is_file():
        raise SystemExit(f'matriz de critérios ausente: {CRITERIOS}')
    published = json.loads(MATRIZ.read_text(encoding='utf-8'))
    criterios = json.loads(CRITERIOS.read_text(encoding='utf-8'))
    fresh = scan()
    fresh_crit = fresh.pop('criterios')
    if published['recuperados'] != fresh['recuperados']:
        raise SystemExit('matriz desatualizada: recuperados divergem do acervo')
    if published['lacunas'] != fresh['lacunas']:
        raise SystemExit('matriz desatualizada: lacunas divergem do acervo')
    if published['contagem']['publicados'] != 141 or fresh['contagem']['lacunas'] != 0:
        raise SystemExit(f"série incompleta: {fresh['contagem']}")
    # Critérios: não aceitar fechamento falso do issue.
    if criterios.get('resumo', {}).get('issue_fechavel') is True:
        raise SystemExit('matriz de critérios marca issue fechável sem autorização explícita')
    if criterios['resumo']['satisfeitos'] != fresh_crit['resumo']['satisfeitos']:
        raise SystemExit('resumo de critérios desatualizado; rode build')
    # Constituição não pode estar na série.
    ids = {item['arquivo'] for item in published['itens']}
    if 'federal/br-federal-constituicao-1988-10-05.md' in ids:
        raise SystemExit('Constituição consolidada contada como emenda')
    print('verify ok:', {
        'contagem': fresh['contagem'],
        'criterios': criterios['resumo'],
        'vinculos': published.get('vinculos_constituicao', {}).get('estado'),
    })


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cmd', choices=('build', 'verify', 'scan'))
    args = parser.parse_args(argv)
    if args.cmd == 'build':
        print(json.dumps(build(), ensure_ascii=False))
    elif args.cmd == 'verify':
        verify()
    else:
        m = scan()
        print(json.dumps({
            'contagem': m['contagem'],
            'criterios': m['criterios']['resumo'],
            'auditoria_metadados': {
                k: len(v) for k, v in m['auditoria_metadados'].items()
            },
        }, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1:])
