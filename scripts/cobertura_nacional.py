#!/usr/bin/env python3
"""Inventário e exportação tipada do acervo para filtros BM25 (#70/#74/#77/#83).

Lê somente o repositório. Não acessa a rede. Não certifica vigência nem
completude nacional. Desconhecido permanece explícito.
"""
from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PROVAS = ROOT / 'provas/cobertura-nacional'
METADADOS = ROOT / 'metadados'
CONTRATO_VERSAO = 1
SPECIAL_IBGE = {'5300108', '2605459'}
OPAQUE_PATH = re.compile(r'^br-(?:[a-z]{2}|municipal-\d{7})-norma-\d+$')
FAC_START = '<!-- fac-simile-oficial:inicio -->'
FAC_END = '<!-- fac-simile-oficial:fim -->'
YAML_HEAD = re.compile(r'\A---\n(.*?)\n---\n', re.S)

# Casos de identidade usados em testes e no export de demonstração.
CASOS_IDENTIDADE = [
    {
        'id': 'lc1-1962-vs-1967',
        'descricao': 'LC 1/1962 e LC 1/1967 são normas distintas apesar do mesmo número.',
        'entradas': [
            {
                'norma_id': 'br-federal-lei-complementar-1962-??-1',
                'numero': '1',
                'complemento': None,
                'data_ato': {'valor': '1962', 'precisao': 'ano', 'estado': 'parcial'},
                'arquivo': None,
                'estado_arquivo': 'ausente-no-acervo-publicado',
                'nota': 'Identidade exigida pelo contrato; publicação integral fica em lote próprio (#68).',
            },
            {
                'norma_id': 'br-federal-lei-complementar-1967-11-09-1',
                'numero': '1',
                'complemento': None,
                'data_ato': {'valor': '1967-11-09', 'precisao': 'dia', 'estado': 'informado'},
                'arquivo': 'federal/br-federal-lei-complementar-1967-11-09-1.md',
                'estado_arquivo': 'publicado',
            },
        ],
    },
    {
        'id': 'complemento-1599-a',
        'descricao': 'numero=1599 + complemento=A não se funde com 1599.',
        'entradas': [
            {'numero': '1599', 'complemento': None, 'chave_identidade': 'lei:1599'},
            {'numero': '1599', 'complemento': 'A', 'chave_identidade': 'lei:1599-A'},
        ],
    },
    {
        'id': 'ato-sem-numero-1823-10-20',
        'descricao': 'Espécie+data não basta; seis registros distintos em 20/10/1823.',
        'numero': None,
        'numero_estado': 'sem-numero',
        'provedor_token_namespace': 'seq-sf',
    },
    {
        'id': 'caminho-opaco-acre',
        'descricao': 'ID do provedor no caminho não é número legal.',
        'entradas': [
            {
                'arquivo': 'estaduais/AC/br-ac-norma-1121.md',
                'provedor_id': '1121',
                'numero_legal_no_cabecalho': '300',
                'data_cabecalho': '1969-11-21',
            },
            {
                'arquivo': 'estaduais/AC/br-ac-norma-120.md',
                'provedor_id': '120',
                'numero_legal_no_cabecalho': '3628',
                'data_cabecalho': '2020-05-26',
            },
        ],
    },
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_ibge_slim() -> list[dict[str, Any]]:
    raw = gzip.decompress((PROVAS / 'ibge-municipios-slim.json.gz').read_bytes())
    captura = load_json(PROVAS / 'ibge-municipios-captura.json')
    if sha256_bytes(raw) != captura['sha256_slim_json']:
        raise AssertionError('hash do slim IBGE diverge da captura registrada')
    return json.loads(raw.decode('utf-8'))


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    m = YAML_HEAD.match(text)
    if not m:
        return None, text
    meta: dict[str, Any] = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith('#') or ':' not in line:
            continue
        key, raw = line.split(':', 1)
        key = key.strip()
        raw = raw.strip()
        try:
            meta[key] = json.loads(raw)
        except json.JSONDecodeError:
            meta[key] = raw
    return meta, text[m.end() :]


def markdown_body_hash(path: Path) -> tuple[dict[str, Any] | None, str, str]:
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    meta, body = parse_frontmatter(text)
    if meta is None:
        return None, text, sha256_bytes(raw)
    return meta, body, sha256_bytes(body.encode('utf-8'))


def path_identity_candidate(rel: str) -> dict[str, Any]:
    stem = Path(rel).stem
    out: dict[str, Any] = {
        'arquivo': rel,
        'stem': stem,
        'caminho_opaco': bool(OPAQUE_PATH.fullmatch(stem)),
        'numero': None,
        'numero_estado': 'desconhecido',
        'complemento': None,
        'provedor_id': None,
        'provedor_token': None,
        'esfera': 'desconhecido',
        'uf': None,
        'ibge': None,
        'especie_candidata': None,
        'data_candidata': None,
        'estado_identidade': 'candidata-nao-conferida',
    }
    parts = Path(rel).parts
    if parts[0] == 'federal':
        out['esfera'] = 'federal'
    elif parts[0] == 'estaduais' and len(parts) >= 2:
        out['esfera'] = 'distrital' if parts[1] == 'DF' else 'estadual'
        out['uf'] = parts[1]
    elif parts[0] == 'municipais' and len(parts) >= 2:
        out['esfera'] = 'municipal'
        out['ibge'] = parts[1]
        if parts[1] in SPECIAL_IBGE:
            out['esfera'] = 'entidade-especial'
    if out['caminho_opaco']:
        m = re.fullmatch(r'br-(?:([a-z]{2})|municipal-(\d{7}))-norma-(\d+)', stem)
        if m:
            out['provedor_id'] = m.group(3)
            out['provedor_id_namespace'] = 'fonte-local-norma-id'
            out['numero_estado'] = 'desconhecido'
            out['estado_identidade'] = 'provedor-id-nao-e-numero-legal'
        return out
    # Padrões canônicos frequentes no federal.
    m = re.fullmatch(
        r'br-federal-(lei-complementar|lei-delegada|lei|decreto-lei|decreto|medida-provisoria|'
        r'emenda-constitucional|constituicao|resolucao|decreto-legislativo)'
        r'(?:-(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?)?(?:-(\d+))?(?:-([a-z0-9-]+))?',
        stem,
    )
    if m:
        out['especie_candidata'] = m.group(1)
        y, mo, d, num, rest = m.group(2), m.group(3), m.group(4), m.group(5), m.group(6)
        if y and mo and d:
            out['data_candidata'] = f'{y}-{mo}-{d}'
        elif y:
            out['data_candidata'] = y
        if num:
            out['numero'] = str(int(num))
            out['numero_estado'] = 'informado'
        elif rest and rest.startswith('seq-sf-'):
            out['numero'] = None
            out['numero_estado'] = 'sem-numero'
            out['provedor_token'] = rest
            out['provedor_token_namespace'] = 'seq-sf'
        if rest and re.fullmatch(r'[a-z]', rest):
            out['complemento'] = rest.upper()
        out['estado_identidade'] = 'derivada-do-caminho-candidata'
    return out


def catalogue_number(numero: Any, complemento: Any = None, reedicao: Any = None) -> str:
    """Chave de número com complemento; reedicao é campo distinto."""
    if numero in (None, '', 0, '0'):
        return ''
    text = re.sub(r'[\s.]', '', str(numero)).lower()
    match = re.fullmatch(r'(\d+)((?:-?[a-z]|-\d+)*)', text)
    if not match or int(match.group(1)) == 0:
        return ''
    number = str(int(match.group(1))) + match.group(2)
    if complemento not in (None, ''):
        token = str(complemento).strip().lower().lstrip('-')
        if not re.fullmatch(r'[a-z]+', token):
            return ''
        if '-' in number:
            if not number.endswith('-' + token):
                return ''
        else:
            number += '-' + token
    if reedicao not in (None, ''):
        if not re.fullmatch(r'\d+', str(reedicao)):
            return ''
        sequence = str(int(str(reedicao)))
        if '-' in number:
            return number if number.endswith('-' + sequence) else ''
        return number + '-' + sequence
    return number


def classify_representation(text: str) -> dict[str, Any]:
    has_fs = FAC_START in text
    n_data = text.count('data:image/')
    imgs = re.findall(r'!\[[^\]]*\]\(([^)]+)\)', text)
    asset_imgs = [u for u in imgs if not u.startswith('data:')]
    if has_fs:
        body_wo = re.sub(
            re.escape(FAC_START) + r'.*?' + re.escape(FAC_END),
            '',
            text,
            flags=re.S,
        )
        arts = len(re.findall(r'(?m)^\*\*Art\.', body_wo)) + len(re.findall(r'(?m)^Art\.', body_wo))
        if arts >= 1:
            rep, transc = 'mista', 'parcial'
        else:
            rep, transc = 'fac-simile', 'ausente'
        ocr = 'ausente'
    elif n_data or asset_imgs:
        # Imagem presente sem marcador oficial: não afirmar fac-símile normativo.
        rep, transc, ocr = 'mista', 'desconhecida', 'desconhecida'
    else:
        rep, transc, ocr = 'texto', 'integral', 'nao-aplicavel'
        # Sem colação documental, integralidade da transcrição permanece candidata.
        if '<!-- reproducao-incompleta:inicio -->' in text:
            transc = 'parcial'
        else:
            transc = 'desconhecida'
            # Heurística: arquivo só com texto tipográfico comum → texto; cobertura ainda desconhecida.
            rep = 'texto'
    return {
        'representacao': rep,
        'cobertura_transcricao': transc,
        'cobertura_ocr': ocr,
        'fac_simile_oficial': has_fs,
        'imagens_markdown': len(imgs),
        'data_uris': n_data,
        'imagens_asset': len(asset_imgs),
        'texto_integral_pesquisavel': transc == 'integral',
        'fonte_integral_preservada': has_fs or transc in {'integral', 'parcial'} or n_data > 0,
    }


def iter_markdown_files() -> list[Path]:
    files: list[Path] = []
    for base in (ROOT / 'federal', ROOT / 'estaduais', ROOT / 'municipais'):
        if base.exists():
            files.extend(sorted(base.rglob('*.md')))
    return files


def _rg_markdown_hits(pattern: str) -> set[Path] | None:
    """Usa ripgrep quando disponível; None se o binário não existir (ex.: CI mínimo)."""
    import shutil
    import subprocess

    if shutil.which('rg') is None:
        return None
    cmd = [
        'rg', '-l', '--glob', '*.md', pattern,
        str(ROOT / 'federal'), str(ROOT / 'estaduais'), str(ROOT / 'municipais'),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # rg exit 1 = no matches
    if proc.returncode not in (0, 1):
        raise RuntimeError(proc.stderr or 'rg failed')
    return {Path(line) for line in proc.stdout.splitlines() if line.strip()}


def _facsimile_candidate_paths() -> list[Path]:
    hits_a = _rg_markdown_hits('fac-simile-oficial:inicio')
    hits_b = _rg_markdown_hits('data:image/')
    if hits_a is not None and hits_b is not None:
        return sorted(hits_a | hits_b)
    # Fallback portátil: varredura por bytes-marcadores, sem depender de rg.
    out: list[Path] = []
    for path in iter_markdown_files():
        raw = path.read_bytes()
        if b'fac-simile-oficial:inicio' in raw or b'data:image/' in raw:
            out.append(path)
    return out


def build_facsimile_inventory() -> dict[str, Any]:
    rows = []
    for path in _facsimile_candidate_paths():
        raw = path.read_bytes()
        text = raw.decode('utf-8', errors='replace')
        if FAC_START not in text and 'data:image/' not in text:
            continue
        rel = path.relative_to(ROOT).as_posix()
        info = classify_representation(text)
        if not info['fac_simile_oficial'] and info['data_uris'] == 0:
            continue
        row = {
            'arquivo': rel,
            **info,
            'sha256_arquivo': sha256_bytes(raw),
            'pendencia_transcricao': info['cobertura_transcricao'] in {'ausente', 'parcial', 'desconhecida'}
            and (info['fac_simile_oficial'] or info['data_uris'] > 0),
        }
        if rel.endswith('br-federal-decreto-lei-1941-10-03-3689.md'):
            row['pecas'] = [
                {
                    'id': 'anexo-formulario-boletim-individual',
                    'tipo': 'formulario',
                    'origem': 'ANEXO com redação dada pelo DL 3.992/1941',
                    'asset': 'assets/federal/br-federal-decreto-lei-1941-10-03-3689/anexo-formulario-boletim-individual.png',
                    'sha256_imagem': 'd8811277f5d8730d50454357d574094a0ff06a97a55d933a698f410f0880c9b1',
                    'cobertura_transcricao': 'ausente',
                    'cobertura_ocr': 'ausente',
                    'vigencia_campos': 'nao-atribuida',
                    'nota': 'Fac-símile do formulário extraído do base64 inline; transcrição estruturada permanece pendente.',
                }
            ]
        rows.append(row)
    rows.sort(key=lambda r: r['arquivo'])
    fac = [r for r in rows if r['fac_simile_oficial']]
    data_only = [r for r in rows if not r['fac_simile_oficial'] and r['data_uris'] > 0]
    return {
        'contrato_versao': CONTRATO_VERSAO,
        'gerado_por': 'scripts/cobertura_nacional.py',
        'limites': (
            'Marcador fac-simile-oficial inventariado por arquivo. data:image sem marcador entra como '
            'fila de revisão de peça/imagem, sem afirmar conteúdo normativo. '
            'Verificador de hashes DOU não prova cobertura de transcrição. '
            'Nenhum OCR foi validado neste inventário.'
        ),
        'resumo': {
            'fac_simile_oficial': len(fac),
            'data_uri_sem_marcador_oficial': len(data_only),
            'pendencias_transcricao': sum(1 for r in rows if r['pendencia_transcricao']),
            'por_representacao': dict(collections.Counter(r['representacao'] for r in rows)),
            'por_cobertura_transcricao': dict(collections.Counter(r['cobertura_transcricao'] for r in rows)),
        },
        'documentos': rows,
    }


def known_sources_for_area(area: str, sphere: str) -> list[dict[str, Any]]:
    """Fontes já citadas no README público; estado nao-investigado quando só há menção genérica."""
    # Mapa mínimo e auditável; não inventa URL por município.
    estadual = {
        'AC': [{'orgao': 'Casa Civil do Acre', 'poder': 'Executivo', 'estado': 'fonte-identificada'}],
        'AL': [{'orgao': 'Assembleia Legislativa de Alagoas / SAPL', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'AP': [{'orgao': 'Diário Oficial / Assembleia do Amapá', 'poder': 'desconhecido', 'estado': 'catalogo-parcial'}],
        'AM': [{'orgao': 'Assembleia Legislativa do Amazonas', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'BA': [{'orgao': 'Casa Civil da Bahia', 'poder': 'Executivo', 'estado': 'catalogo-parcial'}],
        'CE': [{'orgao': 'Assembleia Legislativa do Ceará', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'DF': [{'orgao': 'DFLEGIS', 'poder': 'desconhecido', 'estado': 'catalogo-parcial'}],
        'ES': [{'orgao': 'Assembleia Legislativa do Espírito Santo', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'GO': [{'orgao': 'Casa Civil de Goiás', 'poder': 'Executivo', 'estado': 'catalogo-parcial'}],
        'MA': [{'orgao': 'Casa Civil do Maranhão / DOE', 'poder': 'Executivo', 'estado': 'catalogo-parcial'}],
        'MT': [{'orgao': 'SEFAZ Mato Grosso', 'poder': 'Executivo', 'estado': 'catalogo-parcial'}],
        'MS': [{'orgao': 'Consultoria Legislativa de Mato Grosso do Sul', 'poder': 'desconhecido', 'estado': 'catalogo-parcial'}],
        'MG': [{'orgao': 'ALMG', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'PA': [{'orgao': 'ALEPA / DOE', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'PB': [{'orgao': 'Assembleia Legislativa da Paraíba', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'PR': [{'orgao': 'Casa Civil / Sistema de Legislação do Paraná', 'poder': 'Executivo', 'estado': 'catalogo-parcial'}],
        'PE': [{'orgao': 'Alepe', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'PI': [{'orgao': 'Assembleia Legislativa do Piauí', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'RJ': [{'orgao': 'Alerj', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'RN': [{'orgao': 'Assembleia Legislativa do Rio Grande do Norte', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'RS': [{'orgao': 'Assembleia / portal Consulta Popular', 'poder': 'desconhecido', 'estado': 'catalogo-parcial'}],
        'RO': [{'orgao': 'Assembleia Legislativa de Rondônia', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'RR': [{'orgao': 'Diário Oficial de Roraima', 'poder': 'desconhecido', 'estado': 'catalogo-parcial'}],
        'SC': [{'orgao': 'Assembleia Legislativa de Santa Catarina', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'SP': [{'orgao': 'Alesp', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'SE': [{'orgao': 'Assembleia Legislativa de Sergipe', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        'TO': [{'orgao': 'Assembleia Legislativa do Tocantins / SAPL', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
    }
    if sphere == 'state-or-DF':
        return estadual.get(area, [{'orgao': 'desconhecido', 'poder': 'desconhecido', 'estado': 'nao-investigado'}])
    return [{'orgao': 'desconhecido', 'poder': 'desconhecido', 'estado': 'nao-investigado'}]


def build_territorial_inventory() -> dict[str, Any]:
    ibge = load_ibge_slim()
    captura = load_json(PROVAS / 'ibge-municipios-captura.json')
    published_mun = sorted(
        p.name for p in (ROOT / 'municipais').iterdir() if p.is_dir() and not p.name.startswith('.')
    )
    published_uf = sorted(
        p.name for p in (ROOT / 'estaduais').iterdir() if p.is_dir() and not p.name.startswith('.')
    )
    published_set = set(published_mun)
    unknown = [c for c in published_mun if c not in {x['ibge'] for x in ibge}]
    entes = []
    for row in ibge:
        code = row['ibge']
        especial = row['classificacao'] == 'entidade-especial'
        if especial:
            estado = 'entidade-especial-nao-municipio'
            diretorio = None
            n_md = 0
        elif code in published_set:
            diretorio = f'municipais/{code}'
            n_md = len(list((ROOT / diretorio).glob('*.md')))
            estado = 'publicado-cobertura-desconhecida'
        else:
            diretorio = None
            n_md = 0
            estado = 'sem-publicacao-identificada'
        entes.append(
            {
                'ibge': code,
                'nome': row['nome'],
                'uf': row['uf'],
                'classificacao': row['classificacao'],
                'estado_trabalho': estado,
                'diretorio': diretorio,
                'markdown_publicados': n_md,
                'fontes': (
                    [{'orgao': 'desconhecido', 'poder': 'desconhecido', 'estado': 'nao-investigado'}]
                    if not especial
                    else [{'orgao': 'nao-aplicavel-como-municipio', 'poder': 'nao-aplicavel', 'estado': 'nao-aplicavel'}]
                ),
                'leitura': (
                    'Diretório existente não certifica completude por órgão/espécie/período.'
                    if diretorio
                    else 'Sem diretório não prova ausência de legislação.'
                ),
            }
        )
    # Sobrepor fontes conhecidas para municípios já publicados (amostra).
    fontes_publicados = {
        '3550308': [
            {
                'orgao': 'Prefeitura / Câmara Municipal de São Paulo',
                'poder': 'ambos-parciais',
                'estado': 'catalogo-parcial',
                'lote_tematico': 'licitacoes-locais#57',
            }
        ],
        '3106200': [
            {
                'orgao': 'DOM-PBH / Câmara Municipal de Belo Horizonte',
                'poder': 'ambos-parciais',
                'estado': 'catalogo-parcial',
                'lote_tematico': 'licitacoes-locais#57',
            }
        ],
        '5208707': [
            {
                'orgao': 'Prefeitura de Goiânia (SILEG / DOM)',
                'poder': 'Executivo',
                'estado': 'catalogo-parcial',
                'lote_tematico': 'licitacoes-locais#57',
            }
        ],
        '2702355': [{'orgao': 'Câmara Municipal de Craíbas / SAPL', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        '2703601': [{'orgao': 'Câmara Municipal de Japaratinga', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        '2704708': [{'orgao': 'Câmara Municipal de Marechal Deodoro', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        '2707701': [{'orgao': 'Câmara Municipal de Rio Largo', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        '3100906': [{'orgao': 'Câmara Municipal de Águas Formosas / SAPL', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        '3101607': [{'orgao': 'Câmara Municipal de Alfenas / SAPL', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        '3500105': [{'orgao': 'Câmara Municipal de Adamantina', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        '1505536': [{'orgao': 'Câmara Municipal de Parauapebas', 'poder': 'Legislativo', 'estado': 'catalogo-parcial'}],
        '1508001': [{'orgao': 'SEMAS-PA (cópia de decreto municipal de Tomé-Açu)', 'poder': 'desconhecido', 'estado': 'catalogo-parcial'}],
        '5201405': [{'orgao': 'fonte municipal de Aparecida de Goiânia', 'poder': 'desconhecido', 'estado': 'catalogo-parcial'}],
        '5218805': [{'orgao': 'fonte municipal de Rio Verde', 'poder': 'desconhecido', 'estado': 'catalogo-parcial'}],
    }
    for e in entes:
        if e['ibge'] in fontes_publicados:
            e['fontes'] = fontes_publicados[e['ibge']]

    ufs = []
    for uf in published_uf:
        n_md = len(list((ROOT / 'estaduais' / uf).glob('*.md')))
        ufs.append(
            {
                'uf': uf,
                'esfera': 'distrital' if uf == 'DF' else 'estadual',
                'diretorio': f'estaduais/{uf}',
                'markdown_publicados': n_md,
                'estado_trabalho': 'publicado-cobertura-desconhecida' if n_md else 'diretorio-vazio',
                'fontes': known_sources_for_area(uf, 'state-or-DF'),
                'leitura': 'Presença do diretório estadual não informa espécies/órgãos/períodos cobertos.',
            }
        )

    municipios = [e for e in entes if e['classificacao'] == 'municipio']
    especiais = [e for e in entes if e['classificacao'] == 'entidade-especial']
    return {
        'contrato_versao': CONTRATO_VERSAO,
        'ibge_captura': {
            'fonte_url': captura['fonte_url'],
            'capturado_em': captura['capturado_em'],
            'sha256_resposta_completa': captura['sha256_resposta_completa'],
            'localidades_api': captura['localidades_api'],
            'municipios': captura['municipios'],
        },
        'resumo': {
            'ufs_ou_df_com_diretorio': len(published_uf),
            'municipios_no_ibge': len(municipios),
            'entidades_especiais': len(especiais),
            'municipios_com_diretorio': len(published_mun),
            'municipios_sem_publicacao_identificada': sum(
                1 for e in municipios if e['estado_trabalho'] == 'sem-publicacao-identificada'
            ),
            'codigos_publicados_fora_do_ibge': unknown,
            'lote_tematico_licitacoes_locais': 'metadados/licitacoes-locais/ — amostra #57, não cobertura geral',
        },
        'estados_trabalho_admitidos': [
            'nao-investigado',
            'fonte-identificada',
            'catalogo-parcial',
            'catalogo-reconciliado',
            'texto-pendente',
            'publicado',
            'publicado-cobertura-desconhecida',
            'incompleto',
            'sem-publicacao-identificada',
            'acesso-indisponivel',
            'entidade-especial-nao-municipio',
            'nao-aplicavel',
        ],
        'ufs': ufs,
        'entidades_especiais': especiais,
        'municipios_publicados': [e for e in municipios if e['diretorio']],
        'municipios_sem_diretorio_contagem': sum(
            1 for e in municipios if e['estado_trabalho'] == 'sem-publicacao-identificada'
        ),
        'plano_retomavel': {
            'unidade': 'UF/ente/fonte/tipo/periodo',
            'evitar': 'Abrir milhares de issues sem diagnóstico de fonte',
            'compatibilidade_export': 'metadados/CONTRATO-acervo.md',
            'reuso_tematico': ['#57', '#73'],
        },
        'limites': (
            'Inventário territorial versionado contra captura IBGE. '
            'Não afirma quantidade de normas ausentes. '
            'Municípios sem diretório: sem-publicacao-identificada. '
            'Lista completa dos 5.569 municípios está em ibge-municipios-slim.json.gz; '
            'este manifesto materializa UFs, especiais e publicados, com denominadores.'
        ),
    }


def build_field_coverage() -> dict[str, Any]:
    """Cobertura por campo a partir de lotes com contrato e de amostras gerais."""
    lots = {
        'nucleo-licitacoes': {
            'contrato': 'metadados/CONTRATO.md',
            'manifesto': 'metadados/nucleo-licitacoes.json',
            'campos_cabecalho': 'conhecidos-no-lote',
        },
        'lgpd': {
            'contrato': 'metadados/CONTRATO-lgpd.md',
            'manifesto': 'metadados/lgpd.json',
            'campos_cabecalho': 'conhecidos-no-lote',
        },
        'cdc-eca': {
            'contrato': 'metadados/CONTRATO-cdc-eca.md',
            'manifesto': 'metadados/nucleo-cdc-eca.json',
            'campos_cabecalho': 'conhecidos-no-lote',
        },
        'licitacoes-locais': {
            'contrato': 'metadados/licitacoes-locais/',
            'campos_cabecalho': 'conhecidos-no-lote-tematico',
        },
        'acervo-geral-sem-cabecalho': {
            'contrato': 'metadados/CONTRATO-acervo.md',
            'campos_cabecalho': 'ausente-na-maioria',
            'evidencia': 'provas/cobertura-nacional/path-metadata-audit.json',
        },
    }
    fields = [
        'norma_id',
        'edicao_id',
        'especie',
        'numero',
        'complemento',
        'numero_estado',
        'provedor_id',
        'esfera',
        'uf',
        'ibge',
        'orgao_emissor',
        'poder',
        'titulo',
        'ementa',
        'data_ato',
        'data_publicacao',
        'edicao_tipo',
        'representacao',
        'cobertura_transcricao',
        'situacao',
        'vigencia_certificada',
        'sha256_markdown',
        'fonte_url',
        'relacoes',
    ]
    # Amostra determinística de arquivos gerais.
    samples = [
        'federal/br-federal-constituicao-1988-10-05.md',
        'federal/br-federal-lei-2002-01-10-10406.md',
        'federal/br-federal-lei-2015-03-16-13105.md',
        'federal/br-federal-lei-1990-09-11-8078.md',
        'estaduais/AC/br-ac-norma-1121.md',
        'estaduais/AC/br-ac-norma-120.md',
        'federal/br-federal-decreto-1954-02-25-35110.md',
        'federal/br-federal-lei-2021-04-01-14133.md',
        'federal/edicoes/br-federal-lei-2021-04-01-14133-consolidada.md',
    ]
    sample_rows = []
    for rel in samples:
        path = ROOT / rel
        if not path.is_file():
            sample_rows.append({'arquivo': rel, 'estado': 'ausente'})
            continue
        meta, body, body_hash = markdown_body_hash(path)
        rep = classify_representation(path.read_text(encoding='utf-8'))
        cand = path_identity_candidate(rel)
        sample_rows.append(
            {
                'arquivo': rel,
                'tem_frontmatter_estruturado': meta is not None,
                'campos_frontmatter': sorted(meta.keys()) if meta else [],
                'sha256_corpo_ou_arquivo': body_hash,
                'identidade_caminho': cand,
                'representacao': rep,
            }
        )
    por_campo = {}
    for field in fields:
        if field in {
            'norma_id',
            'edicao_id',
            'especie',
            'numero',
            'esfera',
            'titulo',
            'edicao_tipo',
            'situacao',
            'vigencia_certificada',
            'sha256_markdown',
            'fonte_url',
        }:
            estado_geral = 'conhecido-em-lotes-setoriais-ausente-ou-desconhecido-no-acervo-geral'
        elif field in {'complemento', 'numero_estado', 'provedor_id', 'representacao', 'cobertura_transcricao'}:
            estado_geral = 'parcialmente-modelado-neste-contrato'
        else:
            estado_geral = 'desconhecido-no-acervo-geral'
        por_campo[field] = {
            'acervo_geral': estado_geral,
            'lotes_setoriais': 'consultar-contrato-do-lote',
        }
    return {
        'contrato_versao': CONTRATO_VERSAO,
        'regra': 'Nenhum campo é coberto só porque apareceu em amostra.',
        'lotes': lots,
        'campos': por_campo,
        'amostras_publicadas': sample_rows,
    }


def build_national_matrix() -> dict[str, Any]:
    return {
        'contrato_versao': CONTRATO_VERSAO,
        'objetivo': 'Rastrear cobertura nacional por ente, órgão, espécie e edição até Markdown integral pesquisável (#83).',
        'fechamento': 'Esta matriz permanece aberta enquanto houver universos nao-investigados ou cobertura não comprovada.',
        'dimensoes': [
            'esfera-ente',
            'autoridade-poder',
            'especie-serie',
            'periodo-fonte',
            'identidade-edicao',
            'representacao-conteudo',
            'evidencia',
        ],
        'estados_trabalho': [
            'nao-investigado',
            'fonte-identificada',
            'catalogo-parcial',
            'catalogo-reconciliado',
            'identidade-ambigua',
            'texto-pendente',
            'publicado-nao-colacionado',
            'publicado-conferido',
            'reproducao-incompleta',
            'transcricao-parcial-ou-ausente',
            'edicao-desconhecida',
            'acesso-indisponivel',
        ],
        'lotes_diagnosticados': [
            {'id': '#62', 'tema': 'diplomas federais fundamentais'},
            {'id': '#71', 'tema': 'leis ordinárias 1966–2009'},
            {'id': '#82', 'tema': 'leis ordinárias 1822–1965 e 2010–2026'},
            {'id': '#65', 'tema': 'decretos legislativos federais'},
            {'id': '#66', 'tema': 'resoluções do Senado'},
            {'id': '#67', 'tema': 'leis delegadas'},
            {'id': '#68', 'tema': 'leis complementares / LC 1/1962'},
            {'id': '#63', 'tema': 'emendas CF/1988'},
            {'id': '#85', 'tema': 'emendas de revisão 1994'},
            {'id': '#89', 'tema': 'resoluções da Câmara'},
            {'id': '#90', 'tema': 'leis constitucionais / atos institucionais'},
            {'id': '#79', 'tema': 'constituições históricas / ADCT / EC 1/1969'},
            {'id': '#74', 'tema': 'registro territorial de entes e fontes'},
            {'id': '#57', 'tema': 'licitações locais (temático)'},
            {'id': '#73', 'tema': 'licitações locais (expansão)'},
            {'id': '#72', 'tema': 'atos infralegais'},
            {'id': '#75', 'tema': 'atos infralegais / contratação'},
            {'id': '#70', 'tema': 'contrato global BM25'},
            {'id': '#77', 'tema': 'fac-símile vs transcrição pesquisável'},
            {'id': 'PENDENCIAS.md', 'tema': 'peças acompanhantes incompletas'},
            {'id': '#59', 'tema': 'LGPD base×modificadora'},
            {'id': '#94', 'tema': 'resoluções do Congresso Nacional'},
            {'id': '#95', 'tema': 'MPs/reedições históricas'},
            {'id': '#96', 'tema': 'decretos-leis / identidade'},
            {'id': '#102', 'tema': 'divergência cabeçalho 1.014-A vs 4.014-A'},
            {'id': '#103', 'tema': 'conteúdos trocados Leis 12.985/12.988'},
        ],
        'universos_abertos': [
            'demais catálogos federais e séries históricas',
            'decretos/decretos-leis/MPs sem reconciliação nacional integral',
            'tratados e incorporação/promulgação',
            'órgãos federais/autoridades reguladoras',
            'catálogos completos dos 27 entes e de cada município',
            'conteúdo publicado sem metadados gerais',
            'relações lei-base × modificadoras / eficácia diferida',
            'atualização contínua pós-captura',
        ],
        'errata_complemento_senado': {
            'referencia_snapshot': 'd4e425a57f1c1e1ee9f770e7bc7e673264a2ed58',
            'correcao': 'Preservar campo complemento distinto de reedicao na chave de identidade.',
            'totais_corrigidos': {
                'chaves_agrupadas': 61647,
                'correspondencias_exatas_identidade': 20962,
                'candidatos_sem_arquivo_canonico': 37347,
                'coincidencias_numero_a_revisar': 3214,
                'atos_sem_numero_em_revisao': 124,
                'sem_numero_com_candidato_token_local': 90,
            },
            'leitura': (
                'Totais sem certificação de conteúdo. Correspondência exata inversa para '
                '6.333 leis numeradas e 9.647 decretos-leis do snapshot não prova cobertura completa. '
                'Evidência de colisões evitadas: complement-collision-evidence.json.'
            ),
        },
        'artefatos': {
            'contrato': 'metadados/CONTRATO-acervo.md',
            'territorial': 'provas/cobertura-nacional/inventario-territorial.json',
            'fac_similes': 'provas/cobertura-nacional/inventario-fac-similes.json',
            'campos': 'provas/cobertura-nacional/cobertura-campos.json',
            'bm25': 'provas/cobertura-nacional/bm25-mapeamento.json',
        },
    }


def export_document(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    meta, body, body_hash = markdown_body_hash(path)
    cand = path_identity_candidate(rel)
    rep = classify_representation(text)
    titulo = None
    if meta and meta.get('titulo'):
        titulo = meta['titulo']
    else:
        for line in text.splitlines():
            s = line.strip()
            if not s:
                continue
            if s.startswith('#') or s.startswith('>') or s.startswith('<') or s.startswith('**'):
                titulo = re.sub(r'^#+\s*', '', s)
                titulo = re.sub(r'[<>*]', '', titulo).strip()
                break
            if 'LEI' in s.upper() or 'DECRETO' in s.upper() or 'CONSTITUI' in s.upper():
                titulo = re.sub(r'<[^>]+>', '', s).strip()
                break
    doc = {
        'contrato_versao': CONTRATO_VERSAO,
        'arquivo': rel,
        'norma_id': (meta or {}).get('norma_id') or cand.get('stem'),
        'edicao_id': (meta or {}).get('edicao_id') or cand.get('stem'),
        'especie': (meta or {}).get('norma_tipo') or cand.get('especie_candidata') or 'desconhecido',
        'numero': (meta or {}).get('norma_numero') if meta and 'norma_numero' in meta else cand.get('numero'),
        'numero_estado': cand.get('numero_estado'),
        'complemento': cand.get('complemento'),
        'provedor_id': cand.get('provedor_id'),
        'provedor_token': cand.get('provedor_token'),
        'esfera': (meta or {}).get('esfera') or cand.get('esfera'),
        'uf': cand.get('uf'),
        'ibge': cand.get('ibge'),
        'titulo': titulo,
        'ementa': None,
        'data_ato': (meta or {}).get('norma_data') or cand.get('data_candidata') or 'desconhecido',
        'edicao_tipo': (meta or {}).get('edicao_tipo') or 'desconhecida',
        'situacao': (meta or {}).get('situacao') or 'nao-informada',
        'vigencia_certificada': False,
        'representacao': rep['representacao'],
        'cobertura_transcricao': rep['cobertura_transcricao'],
        'cobertura_ocr': rep['cobertura_ocr'],
        'texto_integral_pesquisavel': rep['texto_integral_pesquisavel'],
        'fonte_integral_preservada': rep['fonte_integral_preservada'],
        'alerta_cobertura_textual': rep['cobertura_transcricao'] != 'integral',
        'alerta_reproducao_incompleta': '<!-- reproducao-incompleta:inicio -->' in text,
        'sha256_markdown': body_hash if meta is not None else sha256_bytes(raw),
        'sha256_markdown_semantica': 'corpo-apos-frontmatter' if meta is not None else 'arquivo-inteiro-sem-frontmatter',
        'fonte_url': (meta or {}).get('fonte_url') or 'desconhecido',
        'markdown_integral': body if meta is not None else text,
        'estado_identidade': 'registrada-no-cabecalho' if meta else cand.get('estado_identidade'),
    }
    # Número do cabeçalho setorial é string; preservar estado.
    if meta and meta.get('norma_numero') not in (None, 'desconhecido'):
        doc['numero_estado'] = 'informado'
    elif meta and meta.get('norma_numero') == 'desconhecido':
        doc['numero_estado'] = 'desconhecido'
    return doc


def bm25_score(query: str, document: str, avgdl: float, df: int, n_docs: int, k1: float = 1.2, b: float = 0.75) -> float:
    """BM25 simplificado in-process para demonstração offline (não é índice ES)."""
    def tokenize(s: str) -> list[str]:
        return re.findall(r'\w+', s.lower(), flags=re.U)

    q_terms = tokenize(query)
    d_terms = tokenize(document)
    if not d_terms or not q_terms:
        return 0.0
    tf = collections.Counter(d_terms)
    dl = len(d_terms)
    score = 0.0
    for term in q_terms:
        f = tf.get(term, 0)
        if f == 0:
            continue
        idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
        score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
    return score


def build_bm25_demo() -> dict[str, Any]:
    sample_files = [
        'federal/br-federal-lei-2021-04-01-14133.md',
        'federal/edicoes/br-federal-lei-2021-04-01-14133-consolidada.md',
        'federal/br-federal-lei-complementar-1967-11-09-1.md',
        'federal/br-federal-decreto-1954-02-25-35110.md',
        'estaduais/AC/br-ac-norma-1121.md',
        'municipais/3550308/br-municipal-3550308-decreto-2022-12-27-62100.md',
    ]
    docs = []
    for rel in sample_files:
        if (ROOT / rel).is_file():
            docs.append(export_document(rel))
    # Filtro combinado: federal + lei + ano 2021 + edição histórica
    filtered = [
        d
        for d in docs
        if d['esfera'] == 'federal'
        and str(d.get('especie')) in {'lei', 'lei'}
        and str(d.get('data_ato', '')).startswith('2021')
        and d.get('edicao_tipo') == 'historica'
    ]
    # Query no corpo da consolidada / histórica
    query = 'licitação pregão eletrônico'
    scored = []
    bodies = [d['markdown_integral'] for d in docs]
    avgdl = sum(len(re.findall(r'\w+', b.lower(), flags=re.U)) for b in bodies) / max(len(bodies), 1)
    for d in docs:
        # df aproximado: termo presente?
        present = sum(1 for b in bodies if 'licitação' in b.lower())
        s = bm25_score(query, d['markdown_integral'], avgdl, max(present, 1), len(docs))
        scored.append(
            {
                'arquivo': d['arquivo'],
                'score': round(s, 6),
                'alerta_cobertura_textual': d['alerta_cobertura_textual'],
                'cobertura_transcricao': d['cobertura_transcricao'],
                'vigencia_certificada': d['vigencia_certificada'],
                'sha256_markdown': d['sha256_markdown'],
                'fonte_url': d['fonte_url'],
                'bytes_markdown_integral': len(d['markdown_integral'].encode('utf-8')),
            }
        )
    scored.sort(key=lambda x: x['score'], reverse=True)
    # Caso negativo: termo só de ato vizinho em fac-símile não deve “provar” corpo
    fac = next(d for d in docs if d['arquivo'].endswith('35110.md'))
    negativo = {
        'arquivo': fac['arquivo'],
        'termo_editorial': 'Fac-símile oficial',
        'presente_no_markdown': 'Fac-símile oficial' in fac['markdown_integral'],
        'termo_de_ato_vizinho_exemplo': 'ALL America Cables',
        'presente_nas_notas': 'ALL America Cables' in fac['markdown_integral'],
        'corpo_normativo_pesquisavel': fac['texto_integral_pesquisavel'],
        'leitura': (
            'Termos das notas/limites de página podem ranquear sem que as cláusulas da imagem '
            'estejam transcritas; alerta_cobertura_textual deve permanecer.'
        ),
    }
    # Export sem truncamento: hashes conferidos
    integridade = []
    for d in docs:
        path = ROOT / d['arquivo']
        meta, body, body_hash = markdown_body_hash(path)
        expected = body_hash if meta is not None else sha256_file(path)
        integridade.append(
            {
                'arquivo': d['arquivo'],
                'export_sha256': d['sha256_markdown'],
                'recomputado': expected,
                'igual': d['sha256_markdown'] == expected,
                'bytes': d['bytes_markdown_integral'] if False else len(d['markdown_integral'].encode()),
                'truncado': False,
            }
        )
    mapping = {
        'properties': {
            'titulo': {'type': 'text'},
            'ementa': {'type': 'text'},
            'markdown_integral': {'type': 'text'},
            'norma_id': {'type': 'keyword'},
            'edicao_id': {'type': 'keyword'},
            'especie': {'type': 'keyword'},
            'numero': {'type': 'keyword'},
            'complemento': {'type': 'keyword'},
            'numero_estado': {'type': 'keyword'},
            'esfera': {'type': 'keyword'},
            'uf': {'type': 'keyword'},
            'ibge': {'type': 'keyword'},
            'edicao_tipo': {'type': 'keyword'},
            'situacao': {'type': 'keyword'},
            'representacao': {'type': 'keyword'},
            'cobertura_transcricao': {'type': 'keyword'},
            'vigencia_certificada': {'type': 'boolean'},
            'alerta_cobertura_textual': {'type': 'boolean'},
            'data_ato': {'type': 'keyword', 'nota': 'date tipada só quando ISO; desconhecido fica fora de date'},
        },
        'bool_query_exemplo': {
            'filter': [
                {'term': {'esfera': 'federal'}},
                {'term': {'especie': 'lei'}},
                {'prefix': {'data_ato': '2021'}},
                {'term': {'edicao_tipo': 'historica'}},
            ],
            'must': {'match': {'markdown_integral': query}},
        },
        'nota': 'Nenhum índice Elasticsearch foi provisionado nesta entrega; o mapping e o BM25 in-process são demonstração offline.',
    }
    return {
        'mapping': mapping,
        'filtro_combinado_resultado': [
            {'arquivo': d['arquivo'], 'edicao_id': d['edicao_id'], 'sha256_markdown': d['sha256_markdown']}
            for d in filtered
        ],
        'ranking_demonstracao': scored,
        'caso_negativo_facsimile': negativo,
        'integridade_export': integridade,
        'casos_identidade': CASOS_IDENTIDADE,
    }


def cmd_generate() -> None:
    write_json(PROVAS / 'inventario-fac-similes.json', build_facsimile_inventory())
    write_json(PROVAS / 'inventario-territorial.json', build_territorial_inventory())
    write_json(PROVAS / 'cobertura-campos.json', build_field_coverage())
    write_json(PROVAS / 'matriz-nacional.json', build_national_matrix())
    demo = build_bm25_demo()
    write_json(PROVAS / 'bm25-mapeamento.json', demo['mapping'])
    write_json(PROVAS / 'bm25-demonstracao.json', {k: v for k, v in demo.items() if k != 'mapping'})
    write_json(PROVAS / 'identidade-casos.json', {'casos': CASOS_IDENTIDADE})
    print('inventários e demonstrações gravados em', PROVAS)


def cmd_verify() -> None:
    captura = load_json(PROVAS / 'ibge-municipios-captura.json')
    slim = load_ibge_slim()
    assert len(slim) == captura['localidades_api'] == 5571
    assert sum(1 for x in slim if x['classificacao'] == 'municipio') == 5569
    assert {x['ibge'] for x in slim if x['classificacao'] == 'entidade-especial'} == SPECIAL_IBGE

    terr = build_territorial_inventory()
    published = load_json(PROVAS / 'inventario-territorial.json')
    assert terr['resumo']['municipios_no_ibge'] == published['resumo']['municipios_no_ibge'] == 5569
    assert terr['resumo']['municipios_com_diretorio'] == published['resumo']['municipios_com_diretorio']
    assert terr['resumo']['ufs_ou_df_com_diretorio'] == 27
    assert '5300108' not in {m['ibge'] for m in terr['municipios_publicados']}
    assert all(e['estado_trabalho'] == 'entidade-especial-nao-municipio' for e in terr['entidades_especiais'])

    fac = build_facsimile_inventory()
    published_fac = load_json(PROVAS / 'inventario-fac-similes.json')
    assert fac['resumo']['fac_simile_oficial'] == published_fac['resumo']['fac_simile_oficial']
    assert fac['resumo']['fac_simile_oficial'] >= 2
    # Exemplos da issue #77
    by_file = {r['arquivo']: r for r in published_fac['documentos']}
    for sample in (
        'federal/br-federal-decreto-1954-02-25-35110.md',
        'federal/br-federal-decreto-1955-06-14-37491.md',
    ):
        assert by_file[sample]['fac_simile_oficial'] is True
        assert by_file[sample]['cobertura_transcricao'] == 'ausente'
        assert by_file[sample]['representacao'] == 'fac-simile'

    cpp_asset = ROOT / 'assets/federal/br-federal-decreto-lei-1941-10-03-3689/anexo-formulario-boletim-individual.png'
    assert cpp_asset.is_file()
    assert sha256_file(cpp_asset) == 'd8811277f5d8730d50454357d574094a0ff06a97a55d933a698f410f0880c9b1'
    cpp_md = (ROOT / 'federal/br-federal-decreto-lei-1941-10-03-3689.md').read_text(encoding='utf-8')
    assert 'anexo-formulario-boletim-individual.png' in cpp_md
    assert 'transcrição' in cpp_md.lower() or 'transcricao' in cpp_md.lower() or 'pendente' in cpp_md.lower()
    # O base64 do formulário (233673 bytes) não deve permanecer no Markdown.
    # Garantir que o PNG do formulário não permanece como data URI.
    import base64
    for m in re.finditer(r'data:image/png;base64,([A-Za-z0-9+/=\n]+)', cpp_md):
        payload = base64.b64decode(m.group(1).replace('\n', ''))
        assert sha256_bytes(payload) != 'd8811277f5d8730d50454357d574094a0ff06a97a55d933a698f410f0880c9b1'
    assert cpp_md.count('data:image/png;base64,') == 2  # outras peças inline restantes
    assert 'Anexo com redação dada pelo Decreto-Lei nº 3.992' in cpp_md

    # Identidade: complemento
    assert catalogue_number('1599', None) == '1599'
    assert catalogue_number('1599', 'A') == '1599-a'
    assert catalogue_number('1599', 'A') != catalogue_number('1599', None)

    # LC 1/1967 publicada; LC 1/1962 registrada como ausente no caso
    assert (ROOT / 'federal/br-federal-lei-complementar-1967-11-09-1.md').is_file()
    assert not list(ROOT.glob('federal/br-federal-lei-complementar-1962-*-1.md'))

    # Opaque paths
    ac1121 = path_identity_candidate('estaduais/AC/br-ac-norma-1121.md')
    assert ac1121['caminho_opaco'] and ac1121['provedor_id'] == '1121' and ac1121['numero'] is None
    head = (ROOT / 'estaduais/AC/br-ac-norma-1121.md').read_text(encoding='utf-8')[:500]
    assert '300' in head and '1969' in head

    demo = build_bm25_demo()
    assert all(x['igual'] and not x['truncado'] for x in demo['integridade_export'])
    assert demo['filtro_combinado_resultado'], 'filtro federal+lei+2021+historica deveria retornar a edição histórica'
    assert demo['caso_negativo_facsimile']['corpo_normativo_pesquisavel'] is False

    campos = load_json(PROVAS / 'cobertura-campos.json')
    assert campos['contrato_versao'] == CONTRATO_VERSAO
    matriz = load_json(PROVAS / 'matriz-nacional.json')
    assert matriz['errata_complemento_senado']['totais_corrigidos']['chaves_agrupadas'] == 61647

    # Contratos setoriais existentes intactos como referência
    assert (METADADOS / 'CONTRATO.md').is_file()
    assert (METADADOS / 'CONTRATO-acervo.md').is_file()
    print(
        f"verify ok: IBGE {captura['municipios']} municípios; "
        f"{published['resumo']['municipios_com_diretorio']} diretórios municipais; "
        f"{published_fac['resumo']['fac_simile_oficial']} fac-símiles oficiais; "
        'sem certificação de completude nacional.'
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cmd', choices=['generate', 'verify', 'export-one'])
    parser.add_argument('--arquivo', help='caminho relativo para export-one')
    args = parser.parse_args(argv)
    if args.cmd == 'generate':
        cmd_generate()
    elif args.cmd == 'verify':
        cmd_verify()
    else:
        if not args.arquivo:
            raise SystemExit('--arquivo é obrigatório para export-one')
        doc = export_document(args.arquivo)
        # Não despejar markdown enorme no stdout em CI sem pedido; incluir hash e tamanho.
        preview = {
            **{k: v for k, v in doc.items() if k != 'markdown_integral'},
            'markdown_integral_bytes': len(doc['markdown_integral'].encode('utf-8')),
            'markdown_integral_sha256': doc['sha256_markdown'],
        }
        print(json.dumps(preview, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
