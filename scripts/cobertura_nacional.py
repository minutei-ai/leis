#!/usr/bin/env python3
"""Inventário e exportação tipada do acervo para filtros BM25 (#70/#74/#77/#83).

Lê somente o repositório. Não acessa a rede. Não certifica vigência nem
completude nacional. Desconhecido permanece explícito.

Exportação do acervo geral: manifesto/sidecars JSONL streaming (não reescreve
Markdown em massa). Frontmatter existente (lotes setoriais + piloto) é reutilizado.
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
import time
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent.parent
PROVAS = ROOT / 'provas/cobertura-nacional'
METADADOS = ROOT / 'metadados'
EXPORT_DIR = PROVAS / 'export-acervo'
CONTRATO_VERSAO = 1
SPECIAL_IBGE = {'5300108', '2605459'}
OPAQUE_PATH = re.compile(r'^br-(?:[a-z]{2}|municipal-\d{7})-norma-\d+$')
FAC_START = '<!-- fac-simile-oficial:inicio -->'
FAC_END = '<!-- fac-simile-oficial:fim -->'
YAML_HEAD = re.compile(r'\A---\n(.*?)\n---\n', re.S)
EXPORT_SCHEMA_VERSION = 2
DEFAULT_SHARD_SIZE = 10000
TITLE_SCAN_CHARS = 8000

# Campos inventariados no relatório de cobertura do acervo completo.
CAMPOS_INVENTARIO = [
    'norma_id',
    'edicao_id',
    'especie',
    'numero',
    'complemento',
    'numero_estado',
    'provedor_id',
    'provedor_token',
    'esfera',
    'uf',
    'ibge',
    'orgao_emissor',
    'fonte_orgao',
    'poder',
    'ambito_aplicacao',
    'serie_historica',
    'senado_id',
    'urn',
    'relacoes',
    'titulo',
    'ementa',
    'data_ato',
    'edicao_tipo',
    'situacao',
    'representacao',
    'cobertura_transcricao',
    'vigencia_certificada',
    'fonte_url',
    'sha256_markdown',
    'fonte_do_campo',
    'estado_identidade',
]

# Casos de identidade usados em testes e no export de demonstração.
CASOS_IDENTIDADE = [
    {
        'id': 'lc1-1962-vs-1967',
        'descricao': 'LC 1/1962 e LC 1/1967 são normas distintas apesar do mesmo número.',
        'entradas': [
            {
                'norma_id': 'br-federal-lei-complementar-1962-07-17-1',
                'numero': '1',
                'complemento': None,
                'data_ato': {'valor': '1962', 'precisao': 'ano', 'estado': 'parcial'},
                'arquivo': 'federal/br-federal-lei-complementar-1962-07-17-1.md',
                'serie_historica': {'valor': 'lei-complementar-ao-ato-adicional', 'estado': 'informado'},
                'estado_arquivo': 'publicado',
            },
            {
                'norma_id': 'br-federal-lei-complementar-1967-11-09-1',
                'numero': '1',
                'complemento': None,
                'data_ato': {'valor': '1967-11-09', 'precisao': 'dia', 'estado': 'informado'},
                'arquivo': 'federal/br-federal-lei-complementar-1967-11-09-1.md',
                'serie_historica': {'valor': 'desconhecido', 'estado': 'desconhecido'},
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
    body = text[m.end() :]
    if body.startswith('\n'):
        # Exclude the blank separator line after frontmatter, matching the
        # owner parser and the sha256_markdown semantics used in Markdown files.
        body = body[1:]
    return meta, body


ACERVO_COMMENT = re.compile(r'<!--\s*metadados-acervo\s*\n(.*?)\n\s*-->', re.S)


def parse_acervo_comment(text: str) -> dict[str, Any]:
    """Lê os metadados de controle do comentário HTML, sem interpretar YAML."""
    match = ACERVO_COMMENT.search(text)
    if not match:
        return {}
    meta: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        if ':' not in line:
            continue
        key, raw = line.split(':', 1)
        key, raw = key.strip(), raw.strip()
        if not key:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            value = raw
        # This contract accepts only scalar JSON values; unquoted labels remain strings.
        if isinstance(value, (dict, list)):
            continue
        meta[key] = value
    return meta


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

    def _apply_date_number(y, mo, d, num, rest) -> None:
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

    # Padrões canônicos frequentes no federal.
    m = re.fullmatch(
        r'br-federal-(lei-complementar|lei-delegada|lei|decreto-lei|decreto|medida-provisoria|'
        r'emenda-constitucional|constituicao|resolucao|decreto-legislativo)'
        r'(?:-(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?)?(?:-(\d+))?(?:-([a-z0-9-]+))?',
        stem,
    )
    if m:
        out['especie_candidata'] = m.group(1)
        _apply_date_number(m.group(2), m.group(3), m.group(4), m.group(5), m.group(6))
        return out

    # Municipal canônico: br-municipal-IBGE-especie-YYYY-MM-DD-numero…
    m = re.fullmatch(
        r'br-municipal-(\d{7})-(lei-complementar|lei|decreto-lei|decreto|resolucao|emenda)'
        r'(?:-(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?)?(?:-(\d+))?(?:-([a-z0-9-]+))?',
        stem,
    )
    if m:
        out['ibge'] = m.group(1)
        out['especie_candidata'] = m.group(2)
        _apply_date_number(m.group(3), m.group(4), m.group(5), m.group(6), m.group(7))
        return out

    # Estadual/distrital canônico (não opaco): br-uf-especie-…
    m = re.fullmatch(
        r'br-([a-z]{2})-(lei-complementar|lei|decreto-lei|decreto|resolucao|constituicao|'
        r'emenda-constitucional)'
        r'(?:-(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?)?(?:-(\d+))?(?:-([a-z0-9-]+))?',
        stem,
    )
    if m:
        out['uf'] = m.group(1).upper()
        out['especie_candidata'] = m.group(2)
        _apply_date_number(m.group(3), m.group(4), m.group(5), m.group(6), m.group(7))
        return out

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
                    'cobertura_transcricao': 'parcial',
                    'cobertura_ocr': 'nao-aplicavel',
                    'vigencia_campos': 'nao-atribuida',
                    'transcricao': 'assets/federal/br-federal-decreto-lei-1941-10-03-3689/anexo-formulario-boletim-individual-transcricao.md',
                    'metodo': 'colacao-visual-do-fac-simile-oficial',
                    'nota': 'Estrutura tipográfica colacionada visualmente; campos em branco preservados; não é OCR.',
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
        'acervo-geral-piloto': {
            'contrato': 'metadados/CONTRATO-acervo.md',
            'manifesto': 'metadados/acervo-geral-piloto.json',
            'campos_cabecalho': 'conhecidos-com-campo_fontes-no-piloto',
        },
        'acervo-geral-export-sidecar': {
            'contrato': 'metadados/CONTRATO-acervo.md',
            'manifesto': 'provas/cobertura-nacional/export-acervo-manifesto.json',
            'inventario': 'provas/cobertura-nacional/inventario-campos-acervo.json',
            'campos_cabecalho': 'inventariados-no-export-completo-com-proveniencia',
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
        'fonte_orgao',
        'serie_historica',
        'senado_id',
        'urn',
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
            {'id': '#102', 'tema': 'divergência cabeçalho 1.014-A vs 4.014-A',
             'estado': 'caso-e-lote-delimitado-colacionados'},
            {'id': '#103', 'tema': 'conteúdos trocados Leis 12.985/12.988',
             'estado': 'duas-identidades-corrigidas-e-colacionadas'},
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
            'campos_acervo_completo': 'provas/cobertura-nacional/inventario-campos-acervo.json',
            'export_acervo_manifesto': 'provas/cobertura-nacional/export-acervo-manifesto.json',
            'bm25': 'provas/cobertura-nacional/bm25-mapeamento.json',
            'bm25_filtros_integrados': 'provas/cobertura-nacional/bm25-filtros-integrados.json',
            'fontes_jurisdicao': 'provas/cobertura-nacional/registro-fontes-jurisdicao.json',
            'reconciliacao_especies': 'provas/cobertura-nacional/reconciliacao-especies-publicadas.json',
            'piloto_cabecalhos': 'metadados/acervo-geral-piloto.json',
            'cpp_formulario': 'provas/cobertura-nacional/cpp-anexo-formulario.json',
        },
        'avanco_desde_inventario_inicial': [
            'piloto de 4 cabeçalhos gerais com campo_fontes (#70)',
            'export sidecar JSONL streaming do acervo completo + inventário por campo (#70)',
            'registro de fontes por UF + municípios publicados (#74)',
            'colação visual estrutural do formulário CPP (#77)',
            'contagem federal por espécie + casos #102/#103 colacionados e bloqueios remanescentes (#83)',
        ],
    }


def _extract_titulo(meta: dict[str, Any] | None, text: str) -> tuple[Any, str]:
    """Retorna (titulo, fonte). Título literal só do frontmatter ou cabeçalho escaneado."""
    if meta and meta.get('titulo') not in (None, '', 'desconhecido'):
        return meta['titulo'], 'frontmatter'
    # Escaneia só o prefixo do corpo (após frontmatter) — não inventa espécie/número.
    head = text[:TITLE_SCAN_CHARS]
    for line in head.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith('#') or s.startswith('>') or s.startswith('<') or s.startswith('**'):
            titulo = re.sub(r'^#+\s*', '', s)
            titulo = re.sub(r'[<>*]', '', titulo).strip()
            if titulo:
                return titulo, 'cabecalho-literal'
            continue
        if 'LEI' in s.upper() or 'DECRETO' in s.upper() or 'CONSTITUI' in s.upper():
            titulo = re.sub(r'<[^>]+>', '', s).strip()
            if titulo:
                return titulo, 'cabecalho-literal'
    return None, 'desconhecido-explicito'


def _estado_campo_valor(field: str, value: Any, doc: dict[str, Any]) -> str:
    """Classifica o estado de conhecimento de um valor exportado (não inventa)."""
    if field == 'vigencia_certificada':
        return 'conhecido' if value is False else 'conflitante'
    if field == 'fonte_do_campo':
        return 'conhecido' if isinstance(value, dict) and value else 'ausente'
    if field == 'sha256_markdown':
        return 'conhecido' if value else 'ausente'
    if field in {'uf', 'ibge'}:
        esfera = doc.get('esfera')
        if value not in (None, '', 'desconhecido'):
            return 'conhecido'
        if field == 'uf' and esfera == 'federal':
            return 'nao-aplicavel'
        if field == 'ibge' and esfera in {'federal', 'estadual', 'distrital'}:
            return 'nao-aplicavel'
        return 'desconhecido' if value in (None, '', 'desconhecido') else 'conhecido'
    if field == 'complemento':
        if value not in (None, ''):
            return 'conhecido'
        # Ausência de complemento é legítima; não confundir com desconhecido.
        return 'nao-aplicavel'
    if field == 'provedor_token':
        if value not in (None, ''):
            return 'conhecido'
        return 'nao-aplicavel'
    if field == 'provedor_id':
        if value not in (None, ''):
            return 'conhecido'
        return 'ausente'
    if field == 'numero':
        estado = doc.get('numero_estado')
        if estado == 'sem-numero':
            return 'nao-aplicavel' if value is None else 'conflitante'
        if estado == 'desconhecido':
            return 'desconhecido'
        if value not in (None, '', 'desconhecido'):
            return 'conhecido'
        return 'desconhecido'
    if field == 'ementa':
        if value in (None, '', 'desconhecido'):
            return 'desconhecido'
        return 'conhecido'
    if field in {'orgao_emissor', 'poder', 'ambito_aplicacao'}:
        if value in (None, '', 'desconhecido', 'nao-informado'):
            return 'desconhecido'
        return 'conhecido'
    if field == 'especie':
        if value in (None, '', 'desconhecido'):
            return 'desconhecido'
        fonte = (doc.get('fonte_do_campo') or {}).get('especie', '')
        if fonte.startswith('caminho') and 'registrada' not in str(doc.get('estado_identidade', '')):
            return 'conhecido'  # candidata tipada, ainda com proveniência de caminho
        return 'conhecido'
    if field == 'data_ato':
        if value in (None, '', 'desconhecido'):
            return 'desconhecido'
        return 'conhecido'
    if field == 'titulo':
        if value in (None, '', 'desconhecido'):
            return 'desconhecido'
        return 'conhecido'
    if field == 'situacao':
        if value in (None, '', 'nao-informada', 'desconhecido'):
            return 'desconhecido'
        return 'conhecido'
    if field == 'edicao_tipo':
        if value in (None, '', 'desconhecida', 'desconhecido'):
            return 'desconhecido'
        return 'conhecido'
    if field == 'fonte_url':
        if value in (None, '', 'desconhecido'):
            return 'desconhecido'
        return 'conhecido'
    if field == 'estado_identidade':
        return 'conhecido' if value else 'ausente'
    if value in (None, '', 'desconhecido'):
        return 'desconhecido'
    return 'conhecido'


def export_document(rel: str, *, include_markdown: bool = True) -> dict[str, Any]:
    """Exporta metadados tipados de uma edição.

    Por padrão inclui `markdown_integral` (consumidores BM25). Para varredura
    massiva use `include_markdown=False` — o corpo permanece no arquivo
    publicado e o hash/bytes permitem recuperação sem truncamento.
    """
    path = ROOT / rel
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    meta, body = parse_frontmatter(text)
    acervo_meta = parse_acervo_comment(text)
    if meta is None:
        body = text
        body_hash = sha256_bytes(raw)
        hash_semantica = 'arquivo-inteiro-sem-frontmatter'
    else:
        body_hash = sha256_bytes(body.encode('utf-8'))
        hash_semantica = 'corpo-apos-frontmatter'
    excluded_note = (
        acervo_meta.get('tipo_conteudo') == 'nota_edicao'
        and acervo_meta.get('status_publicacao') == 'nao_publicado_integra'
        and acervo_meta.get('edicao_integral') is False
        and acervo_meta.get('excluir_denominador_integra') is True
    )
    if excluded_note:
        # Keep the source artifact hash/size, while exporting no editorial note as law.
        body = ''
    partial_legal_body = (
        not excluded_note
        and meta is not None
        and meta.get('edicao_integral') is False
    )
    cand = path_identity_candidate(rel)
    rep = classify_representation(text)
    titulo, titulo_fonte = _extract_titulo(meta, body if meta is not None else text)

    # Papel jurídico e canal de captura são campos distintos. A fonte de
    # captura nunca substitui o emissor do ato; emissor sem prova fica explícito.
    orgao = (meta or {}).get('orgao_emissor') or 'desconhecido'
    fonte_orgao = (meta or {}).get('fonte_orgao') or 'desconhecido'
    poder = (meta or {}).get('poder') or 'desconhecido'
    ambito = (meta or {}).get('ambito_aplicacao') or 'desconhecido'
    ementa = (meta or {}).get('ementa')
    if ementa in (None, ''):
        ementa = None

    numero: Any
    if meta and 'norma_numero' in meta:
        numero = meta.get('norma_numero')
        if numero == 'desconhecido':
            numero_estado = 'desconhecido'
        elif numero is None:
            # null no frontmatter = ato sem número só se marcado; senão desconhecido
            numero_estado = meta.get('numero_estado') or 'desconhecido'
        else:
            numero_estado = meta.get('numero_estado') or 'informado'
    else:
        numero = cand.get('numero')
        numero_estado = cand.get('numero_estado')

    # Caminho opaco: provedor_id nunca vira numero.
    if cand.get('caminho_opaco') and not (meta and 'norma_numero' in meta):
        numero = None
        numero_estado = 'desconhecido'

    estado_identidade = (
        'registrada-no-cabecalho'
        if meta
        else cand.get('estado_identidade')
    )
    # Identidade verificada só com frontmatter/contrato; caminho canônico permanece candidata.
    if meta and meta.get('estado_identidade'):
        estado_identidade = meta['estado_identidade']

    doc: dict[str, Any] = {
        'contrato_versao': CONTRATO_VERSAO,
        'export_schema_versao': EXPORT_SCHEMA_VERSION,
        'arquivo': rel,
        'norma_id': (meta or {}).get('norma_id') or cand.get('stem'),
        'edicao_id': (meta or {}).get('edicao_id') or cand.get('stem'),
        'especie': (meta or {}).get('norma_tipo') or cand.get('especie_candidata') or 'desconhecido',
        'numero': numero,
        'numero_estado': numero_estado,
        'complemento': (meta or {}).get('complemento') if meta and 'complemento' in meta else cand.get('complemento'),
        'provedor_id': cand.get('provedor_id'),
        'provedor_token': cand.get('provedor_token'),
        'esfera': (meta or {}).get('esfera') or cand.get('esfera'),
        'uf': (meta or {}).get('uf') if meta and meta.get('uf') is not None else cand.get('uf'),
        'ibge': (meta or {}).get('ibge') if meta and meta.get('ibge') is not None else cand.get('ibge'),
        'orgao_emissor': orgao,
        'fonte_orgao': fonte_orgao,
        'poder': poder,
        'ambito_aplicacao': ambito,
        'titulo': titulo,
        'ementa': ementa,
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
        'sha256_markdown': body_hash,
        'sha256_markdown_semantica': hash_semantica,
        'markdown_integral_bytes': len(body.encode('utf-8')),
        'fonte_url': (meta or {}).get('fonte_url') or 'desconhecido',
        'estado_identidade': estado_identidade,
        'tem_frontmatter': meta is not None,
        'armazenamento_metadados': 'frontmatter' if meta is not None else 'sidecar-export',
    }
    # Keep structured source identifiers and relation assertions when a source
    # record supplies them. The exporter preserves assertions; it does not
    # derive legal effects or destinations.
    for key in ('serie_historica', 'senado_id', 'urn', 'relacoes'):
        if meta and key in meta:
            doc[key] = meta[key]
    if acervo_meta:
        for key in (
            'status_publicacao', 'edicao_integral', 'corpo_status', 'tipo_conteudo',
            'excluir_denominador_integra', 'nao_reclassificar_por_hash_ou_presenca', 'issue',
        ):
            if key in acervo_meta:
                doc[key] = acervo_meta[key]
        doc['sha256_arquivo_origem'] = sha256_bytes(raw)
        doc['bytes_arquivo_origem'] = len(raw)
        doc['corpo_legal_integral_pendente'] = excluded_note or partial_legal_body
    if partial_legal_body:
        doc['corpo_legal_integral_pendente'] = True
        doc['edicao_integral'] = False
        doc['excluir_denominador_integra'] = True
        doc['corpo_status'] = (meta or {}).get('corpo_status') or 'parcial'
        doc['status_publicacao'] = (meta or {}).get('status_publicacao') or 'publicado-corpo-parcial'
    if excluded_note:
        doc['texto_integral_pesquisavel'] = False
        doc['fonte_integral_preservada'] = False
        doc['cobertura_transcricao'] = 'ausente'
        doc['alerta_cobertura_textual'] = True
        doc['markdown_integral_bytes'] = 0
    elif partial_legal_body:
        doc['texto_integral_pesquisavel'] = False
        doc['fonte_integral_preservada'] = True
        doc['cobertura_transcricao'] = 'parcial'
        doc['alerta_cobertura_textual'] = True

    campo_fontes: dict[str, Any] = {}
    if meta and isinstance(meta.get('campo_fontes'), dict):
        campo_fontes.update(meta['campo_fontes'])

    def _src(field: str, default: str) -> str:
        return campo_fontes.get(field, default)

    doc['fonte_do_campo'] = {
        'norma_id': _src('norma_id', 'frontmatter' if meta and meta.get('norma_id') else 'caminho'),
        'edicao_id': _src('edicao_id', 'frontmatter' if meta and meta.get('edicao_id') else 'caminho'),
        'especie': _src(
            'norma_tipo',
            'frontmatter'
            if meta and meta.get('norma_tipo')
            else ('caminho-canonico' if cand.get('especie_candidata') else 'desconhecido-explicito'),
        ),
        'numero': _src(
            'norma_numero',
            'frontmatter'
            if meta and 'norma_numero' in (meta or {})
            else (
                'caminho-canonico'
                if cand.get('numero') is not None
                else ('sem-numero' if cand.get('numero_estado') == 'sem-numero' else 'desconhecido-explicito')
            ),
        ),
        'complemento': _src(
            'complemento',
            'frontmatter'
            if meta and 'complemento' in (meta or {})
            else ('caminho-canonico' if cand.get('complemento') else 'nao-aplicavel'),
        ),
        'esfera': _src('esfera', 'frontmatter' if meta and meta.get('esfera') else 'caminho'),
        'uf': _src('uf', 'frontmatter' if meta and meta.get('uf') is not None else (
            'caminho' if cand.get('uf') else 'nao-aplicavel'
        )),
        'ibge': _src('ibge', 'frontmatter' if meta and meta.get('ibge') is not None else (
            'caminho' if cand.get('ibge') else 'nao-aplicavel'
        )),
        'orgao_emissor': _src(
            'orgao_emissor',
            'frontmatter' if meta and meta.get('orgao_emissor') else 'desconhecido-explicito',
        ),
        'fonte_orgao': _src(
            'fonte_orgao',
            'frontmatter' if meta and meta.get('fonte_orgao') else 'desconhecido-explicito',
        ),
        'poder': _src('poder', 'frontmatter' if meta and meta.get('poder') else 'desconhecido-explicito'),
        'ambito_aplicacao': _src(
            'ambito_aplicacao',
            'frontmatter' if meta and meta.get('ambito_aplicacao') else 'desconhecido-explicito',
        ),
        'titulo': _src('titulo', titulo_fonte),
        'ementa': _src('ementa', 'frontmatter' if ementa is not None else 'desconhecido-explicito'),
        'data_ato': _src(
            'norma_data',
            'frontmatter'
            if meta and meta.get('norma_data')
            else ('caminho-canonico' if cand.get('data_candidata') else 'desconhecido-explicito'),
        ),
        'edicao_tipo': _src(
            'edicao_tipo',
            'frontmatter' if meta and meta.get('edicao_tipo') else 'desconhecido-explicito',
        ),
        'fonte_url': _src(
            'fonte_url',
            'frontmatter' if meta and meta.get('fonte_url') else 'desconhecido-explicito',
        ),
        'situacao': _src(
            'situacao',
            'frontmatter' if meta and meta.get('situacao') else 'desconhecido-explicito',
        ),
        'representacao': 'classificador-local',
        'cobertura_transcricao': 'classificador-local',
        'vigencia_certificada': 'contrato-global-sempre-false',
        'markdown_integral': (
            'nota-editorial-excluida-corpo-integral-pendente'
            if excluded_note else 'arquivo-publicado'
        ),
    }
    for key in ('serie_historica', 'senado_id', 'urn', 'relacoes'):
        if meta and key in meta:
            doc['fonte_do_campo'][key] = _src(
                key,
                'frontmatter' if meta.get(key) not in (None, '', []) else 'desconhecido-explicito',
            )
    if meta and meta.get('provedor_id') is not None:
        doc['provedor_id'] = meta['provedor_id']
        doc['fonte_do_campo']['provedor_id'] = _src('provedor_id', 'frontmatter')
    elif cand.get('provedor_id') is not None:
        doc['fonte_do_campo']['provedor_id'] = 'caminho-opaco'
    else:
        doc['fonte_do_campo']['provedor_id'] = 'ausente'

    if include_markdown:
        doc['markdown_integral'] = body
    return doc


def iter_markdown_rels() -> list[str]:
    return [p.relative_to(ROOT).as_posix() for p in iter_markdown_files()]


def iter_export_records(
    *,
    include_markdown: bool = False,
    paths: list[str] | None = None,
) -> Iterator[dict[str, Any]]:
    """Gera um registro tipado por edição, sem acumular corpos em memória."""
    rels = paths if paths is not None else iter_markdown_rels()
    for rel in rels:
        yield export_document(rel, include_markdown=include_markdown)


def _checkpoint_path(out_dir: Path) -> Path:
    return out_dir / 'checkpoint.json'


def _load_checkpoint(out_dir: Path) -> dict[str, Any]:
    path = _checkpoint_path(out_dir)
    if path.is_file():
        return load_json(path)
    return {
        'schema_versao': EXPORT_SCHEMA_VERSION,
        'next_index': 0,
        'shards': [],
        'processados': 0,
        'bytes_jsonl': 0,
    }


def _write_checkpoint(out_dir: Path, data: dict[str, Any]) -> None:
    write_json(_checkpoint_path(out_dir), data)


def export_acervo_streaming(
    *,
    out_dir: Path | None = None,
    shard_size: int = DEFAULT_SHARD_SIZE,
    resume: bool = True,
    include_markdown: bool = False,
    limit: int | None = None,
) -> dict[str, Any]:
    """Exporta o acervo inteiro em shards JSONL.gz retomáveis.

    Não carrega o corpus em memória: um arquivo por vez. Por padrão omite o
    corpo Markdown do JSONL (sidecar de metadados); a íntegra permanece no
    `.md` publicado e é recuperável por `arquivo` + `sha256_markdown`.
    """
    out_dir = out_dir or EXPORT_DIR
    shards_dir = out_dir / 'shards'
    shards_dir.mkdir(parents=True, exist_ok=True)
    rels = iter_markdown_rels()
    if limit is not None:
        rels = rels[:limit]
    total = len(rels)
    ckpt = _load_checkpoint(out_dir) if resume else {
        'schema_versao': EXPORT_SCHEMA_VERSION,
        'next_index': 0,
        'shards': [],
        'processados': 0,
        'bytes_jsonl': 0,
    }
    start = int(ckpt.get('next_index') or 0)
    if start > total:
        start = 0
        ckpt = {
            'schema_versao': EXPORT_SCHEMA_VERSION,
            'next_index': 0,
            'shards': [],
            'processados': 0,
            'bytes_jsonl': 0,
        }

    inventory_counts: dict[str, collections.Counter] = {
        field: collections.Counter() for field in CAMPOS_INVENTARIO
    }
    # Reprocessar inventário do zero a cada corrida completa; em resume parcial
    # o inventário final é recalculado ao concluir.
    identity_counts: collections.Counter = collections.Counter()
    storage_counts: collections.Counter = collections.Counter()
    esfera_counts: collections.Counter = collections.Counter()
    numero_estado_counts: collections.Counter = collections.Counter()
    opaque_provider_not_number = 0
    t0 = time.time()

    shard_idx = len(ckpt.get('shards') or [])
    current_lines = 0
    gz = None
    shard_path: Path | None = None
    shard_raw = 0

    def _open_shard(idx: int):
        nonlocal gz, shard_path, shard_raw, current_lines
        shard_path = shards_dir / f'shard-{idx:05d}.jsonl.gz'
        gz = gzip.open(shard_path, 'wt', encoding='utf-8', compresslevel=6)
        shard_raw = 0
        current_lines = 0

    def _close_shard():
        nonlocal gz, shard_idx, shard_raw, current_lines
        if gz is None or shard_path is None:
            return
        gz.close()
        gz = None
        digest = sha256_file(shard_path)
        ckpt.setdefault('shards', []).append(
            {
                'arquivo': shard_path.relative_to(out_dir).as_posix(),
                'registros': current_lines,
                'sha256': digest,
                'bytes': shard_path.stat().st_size,
            }
        )
        shard_idx += 1
        current_lines = 0
        shard_raw = 0

    if start < total:
        _open_shard(shard_idx)

    for i in range(start, total):
        rel = rels[i]
        doc = export_document(rel, include_markdown=include_markdown)
        line = json.dumps(doc, ensure_ascii=False, separators=(',', ':'))
        assert gz is not None
        gz.write(line + '\n')
        shard_raw += len(line) + 1
        current_lines += 1
        ckpt['bytes_jsonl'] = int(ckpt.get('bytes_jsonl') or 0) + len(line) + 1
        ckpt['processados'] = i + 1
        ckpt['next_index'] = i + 1

        identity_counts[str(doc.get('estado_identidade'))] += 1
        storage_counts[str(doc.get('armazenamento_metadados'))] += 1
        esfera_counts[str(doc.get('esfera'))] += 1
        numero_estado_counts[str(doc.get('numero_estado'))] += 1
        if (
            doc.get('provedor_id') is not None
            and doc.get('numero') is not None
            and str(doc['provedor_id']) == str(doc['numero'])
            and not doc.get('tem_frontmatter')
            and path_identity_candidate(rel).get('caminho_opaco')
        ):
            opaque_provider_not_number += 1

        for field in CAMPOS_INVENTARIO:
            inventory_counts[field][_estado_campo_valor(field, doc.get(field), doc)] += 1

        if current_lines >= shard_size:
            _close_shard()
            _write_checkpoint(out_dir, ckpt)
            if i + 1 < total:
                _open_shard(shard_idx)

    if gz is not None:
        _close_shard()

    elapsed = time.time() - t0

    # Resume parcial: reconta inventário a partir dos shards (sem corpos).
    if start > 0 and ckpt['processados'] == total:
        inventory_counts = {field: collections.Counter() for field in CAMPOS_INVENTARIO}
        identity_counts = collections.Counter()
        storage_counts = collections.Counter()
        esfera_counts = collections.Counter()
        numero_estado_counts = collections.Counter()
        opaque_provider_not_number = 0
        for shard in ckpt.get('shards') or []:
            with gzip.open(out_dir / shard['arquivo'], 'rt', encoding='utf-8') as fh:
                for line in fh:
                    doc = json.loads(line)
                    identity_counts[str(doc.get('estado_identidade'))] += 1
                    storage_counts[str(doc.get('armazenamento_metadados'))] += 1
                    esfera_counts[str(doc.get('esfera'))] += 1
                    numero_estado_counts[str(doc.get('numero_estado'))] += 1
                    if (
                        doc.get('provedor_id') is not None
                        and doc.get('numero') is not None
                        and str(doc['provedor_id']) == str(doc['numero'])
                        and not doc.get('tem_frontmatter')
                        and path_identity_candidate(doc['arquivo']).get('caminho_opaco')
                    ):
                        opaque_provider_not_number += 1
                    for field in CAMPOS_INVENTARIO:
                        inventory_counts[field][_estado_campo_valor(field, doc.get(field), doc)] += 1

    inventario = {
        'contrato_versao': CONTRATO_VERSAO,
        'export_schema_versao': EXPORT_SCHEMA_VERSION,
        'regra': (
            'Nenhum campo é coberto só porque apareceu em amostra. '
            'Contagens abaixo percorrem todas as edições publicadas no export.'
        ),
        'escolha_armazenamento': {
            'metadados_acervo_geral': 'sidecar-export-jsonl',
            'frontmatter': 'reutilizado-quando-ja-presente',
            'markdown_corpos': 'nao-reescrevidos-em-massa',
        },
        'total_edicoes': ckpt['processados'],
        'por_campo': {
            field: dict(counter) for field, counter in inventory_counts.items()
        },
        'por_estado_identidade': dict(identity_counts),
        'por_armazenamento_metadados': dict(storage_counts),
        'por_esfera': dict(esfera_counts),
        'por_numero_estado': dict(numero_estado_counts),
        'anomalias': {
            'provedor_id_igual_numero_sem_frontmatter': opaque_provider_not_number,
        },
        'limites': (
            'Identidade derivada só do caminho permanece candidata. '
            'orgao_emissor/poder/ambito_aplicacao/serie sem prova ficam desconhecidos. '
            'Presença no export não certifica vigência.'
        ),
    }

    manifesto = {
        'contrato_versao': CONTRATO_VERSAO,
        'export_schema_versao': EXPORT_SCHEMA_VERSION,
        'gerado_por': 'scripts/cobertura_nacional.py export-acervo',
        'include_markdown': include_markdown,
        'shard_size': shard_size,
        'total_edicoes': ckpt['processados'],
        'total_esperado': total,
        'completo': ckpt['processados'] == total,
        'bytes_jsonl_nao_comprimidos': ckpt.get('bytes_jsonl'),
        'shards': ckpt.get('shards') or [],
        'elapsed_seconds': round(elapsed, 3),
        'checkpoint': 'checkpoint.json',
        'inventario_campos': 'inventario-campos-acervo.json',
        'recuperacao_integra': {
            'modo': 'arquivo-publicado+sha256_markdown',
            'nota': (
                'Consumidor BM25 obtém markdown_integral via export-one/--include-markdown '
                'ou lendo o Markdown publicado e conferindo o hash; sidecars não truncam o corpo.'
            ),
        },
        'filtros_bm25': [
            'esfera',
            'especie',
            'orgao_emissor',
            'fonte_orgao',
            'serie_historica',
            'senado_id',
            'urn',
            'numero',
            'complemento',
            'numero_estado',
            'uf',
            'ibge',
            'edicao_tipo',
            'data_ato',
            'representacao',
            'cobertura_transcricao',
            'edicao_id',
            'norma_id',
        ],
    }
    write_json(out_dir / 'manifesto.json', manifesto)
    write_json(out_dir / 'inventario-campos-acervo.json', inventario)
    # Cópia estável em provas/ só no export canônico (não em fixtures de teste).
    if out_dir.resolve() == EXPORT_DIR.resolve():
        write_json(PROVAS / 'export-acervo-manifesto.json', manifesto)
        write_json(PROVAS / 'inventario-campos-acervo.json', inventario)
    _write_checkpoint(out_dir, {**ckpt, 'completo': manifesto['completo']})
    return {'manifesto': manifesto, 'inventario': inventario}


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




def build_jurisdiction_sources() -> dict[str, Any]:
    """Registro de fontes por jurisdição a partir de coletores/README já citados.

    Não consulta a rede. Não infere ausência de legislação por falta de pasta
    nem por erro HTTP. Municípios sem diretório ficam nao-investigado.
    """
    # URLs e órgãos já presentes em coletores/leis (scripts) e memórias de lote.
    ufs: dict[str, list[dict[str, Any]]] = {
        'AC': [
            {'orgao': 'Casa Civil do Acre', 'poder': 'Executivo', 'papel': 'compilado-estadual',
             'estado': 'fonte-identificada', 'evidencia': 'coletores/COBERTURA.md + known_sources_for_area'},
        ],
        'AL': [
            {'orgao': 'Assembleia Legislativa de Alagoas / SAPL', 'poder': 'Legislativo',
             'url_descoberta': 'https://sapl.al.al.leg.br', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores/scripts/alagoas.ts'},
        ],
        'AM': [
            {'orgao': 'Assembleia Legislativa do Amazonas / SAPL', 'poder': 'Legislativo',
             'url_descoberta': 'https://sapl.al.am.leg.br', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores/scripts/amazonas.ts'},
        ],
        'AP': [
            {'orgao': 'Diário Oficial / Assembleia do Amapá', 'poder': 'desconhecido',
             'estado': 'catalogo-parcial', 'evidencia': 'known_sources_for_area'},
        ],
        'BA': [
            {'orgao': 'Casa Civil da Bahia', 'poder': 'Executivo', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores/catalogos/bahia + COBERTURA.md'},
        ],
        'CE': [
            {'orgao': 'Assembleia Legislativa do Ceará', 'poder': 'Legislativo',
             'estado': 'catalogo-parcial', 'evidencia': 'known_sources_for_area'},
        ],
        'DF': [
            {'orgao': 'DFLEGIS', 'poder': 'desconhecido', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores/scripts/distrito-federal.ts'},
        ],
        'ES': [
            {'orgao': 'Assembleia Legislativa do Espírito Santo', 'poder': 'Legislativo',
             'estado': 'catalogo-parcial', 'evidencia': 'known_sources_for_area'},
        ],
        'GO': [
            {'orgao': 'Casa Civil de Goiás', 'poder': 'Executivo', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores/COBERTURA.md'},
        ],
        'MA': [
            {'orgao': 'Casa Civil do Maranhão / DOE', 'poder': 'Executivo', 'estado': 'catalogo-parcial',
             'evidencia': 'known_sources_for_area'},
        ],
        'MG': [
            {'orgao': 'ALMG / dados abertos', 'poder': 'Legislativo',
             'url_descoberta': 'https://dadosabertos.almg.gov.br/', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores/scripts/almg.ts'},
        ],
        'MS': [
            {'orgao': 'Consultoria Legislativa de Mato Grosso do Sul', 'poder': 'desconhecido',
             'estado': 'catalogo-parcial', 'evidencia': 'known_sources_for_area'},
        ],
        'MT': [
            {'orgao': 'SEFAZ Mato Grosso', 'poder': 'Executivo', 'estado': 'catalogo-parcial',
             'evidencia': 'known_sources_for_area'},
        ],
        'PA': [
            {'orgao': 'ALEPA / DOE', 'poder': 'Legislativo', 'estado': 'catalogo-parcial',
             'evidencia': 'known_sources_for_area'},
        ],
        'PB': [
            {'orgao': 'Assembleia Legislativa da Paraíba', 'poder': 'Legislativo',
             'estado': 'catalogo-parcial', 'evidencia': 'known_sources_for_area'},
        ],
        'PR': [
            {'orgao': 'Casa Civil / Sistema de Legislação do Paraná', 'poder': 'Executivo',
             'url_descoberta': 'https://www.legislacao.pr.gov.br/', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores + leis-pr-legislacao-urls'},
        ],
        'PE': [
            {'orgao': 'Alepe', 'poder': 'Legislativo', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores/COBERTURA.md'},
        ],
        'PI': [
            {'orgao': 'Assembleia Legislativa do Piauí / SAPL', 'poder': 'Legislativo',
             'estado': 'catalogo-parcial', 'evidencia': 'coletores README Piauí'},
        ],
        'RJ': [
            {'orgao': 'Alerj', 'poder': 'Legislativo', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores/COBERTURA.md'},
        ],
        'RN': [
            {'orgao': 'Assembleia Legislativa do Rio Grande do Norte', 'poder': 'Legislativo',
             'estado': 'catalogo-parcial', 'evidencia': 'coletores/COBERTURA.md'},
        ],
        'RS': [
            {'orgao': 'Assembleia / portal Consulta Popular', 'poder': 'desconhecido',
             'estado': 'catalogo-parcial', 'evidencia': 'known_sources_for_area'},
        ],
        'RO': [
            {'orgao': 'Assembleia Legislativa de Rondônia', 'poder': 'Legislativo',
             'estado': 'catalogo-parcial', 'evidencia': 'known_sources_for_area'},
        ],
        'RR': [
            {'orgao': 'Diário Oficial de Roraima', 'poder': 'desconhecido',
             'estado': 'catalogo-parcial', 'evidencia': 'known_sources_for_area'},
        ],
        'SC': [
            {'orgao': 'Assembleia Legislativa de Santa Catarina', 'poder': 'Legislativo',
             'estado': 'catalogo-parcial', 'evidencia': 'coletores/COBERTURA.md'},
        ],
        'SP': [
            {'orgao': 'Alesp', 'poder': 'Legislativo', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores/scripts/alesp.ts + catalogos/alesp'},
            {'orgao': 'Prefeitura / Câmara Municipal de São Paulo (PMSP)', 'poder': 'ambos-parciais',
             'estado': 'catalogo-parcial', 'escopo': 'municipio-3550308',
             'evidencia': 'coletores/catalogos/pmsp'},
        ],
        'SE': [
            {'orgao': 'Assembleia Legislativa de Sergipe', 'poder': 'Legislativo',
             'estado': 'catalogo-parcial', 'evidencia': 'known_sources_for_area'},
        ],
        'TO': [
            {'orgao': 'Assembleia Legislativa do Tocantins / SAPL', 'poder': 'Legislativo',
             'url_descoberta': 'https://sapl.al.to.leg.br', 'estado': 'catalogo-parcial',
             'evidencia': 'coletores/scripts/admit-tocantins*'},
        ],
    }
    federal = [
        {'orgao': 'Senado Federal — Dados Abertos / Normas', 'poder': 'Legislativo',
         'url_descoberta': 'https://legis.senado.leg.br/dadosabertos/', 'estado': 'catalogo-parcial',
         'evidencia': 'coletores/catalogos/senado'},
        {'orgao': 'Presidência da República — Planalto', 'poder': 'Executivo',
         'url_descoberta': 'https://www.planalto.gov.br/ccivil_03/', 'estado': 'fonte-identificada',
         'evidencia': 'lotes setoriais / fontes/*.json'},
        {'orgao': 'Câmara dos Deputados — Legislação Informatizada', 'poder': 'Legislativo',
         'url_descoberta': 'https://www2.camara.leg.br/atividade-legislativa/legislacao',
         'estado': 'fonte-identificada', 'evidencia': 'diplomas fundamentais / CPP'},
    ]
    municipais_publicados = {
        '3550308': [{'orgao': 'Prefeitura / Câmara Municipal de São Paulo', 'poder': 'ambos-parciais',
                     'estado': 'catalogo-parcial', 'evidencia': 'licitacoes-locais + catalogos/pmsp'}],
        '3106200': [{'orgao': 'DOM-PBH / Câmara Municipal de Belo Horizonte', 'poder': 'ambos-parciais',
                     'url_descoberta': 'https://api-dom.pbh.gov.br/api', 'estado': 'catalogo-parcial',
                     'evidencia': 'leis-dom-pbh-api + licitacoes-locais'}],
        '5208707': [{'orgao': 'Prefeitura de Goiânia (SILEG / DOM)', 'poder': 'Executivo',
                     'estado': 'catalogo-parcial', 'evidencia': 'licitacoes-locais/GO'}],
        '2702355': [{'orgao': 'Câmara Municipal de Craíbas / SAPL', 'poder': 'Legislativo',
                     'estado': 'catalogo-parcial', 'evidencia': 'leis-craibas'}],
        '2703601': [{'orgao': 'Câmara Municipal de Japaratinga', 'poder': 'Legislativo',
                     'estado': 'catalogo-parcial', 'evidencia': 'inventario-territorial'}],
        '2704708': [{'orgao': 'Câmara Municipal de Marechal Deodoro', 'poder': 'Legislativo',
                     'estado': 'catalogo-parcial', 'evidencia': 'inventario-territorial'}],
        '2707701': [{'orgao': 'Câmara Municipal de Rio Largo', 'poder': 'Legislativo',
                     'estado': 'catalogo-parcial', 'evidencia': 'inventario-territorial'}],
        '3100906': [{'orgao': 'Câmara Municipal de Águas Formosas / SAPL', 'poder': 'Legislativo',
                     'estado': 'catalogo-parcial', 'evidencia': 'coletores aguas-formosas'}],
        '3101607': [{'orgao': 'Câmara Municipal de Alfenas / SAPL', 'poder': 'Legislativo',
                     'url_descoberta': 'https://sapl.alfenas.mg.leg.br', 'estado': 'catalogo-parcial',
                     'evidencia': 'coletores/scripts/alfenas.ts'}],
        '3500105': [{'orgao': 'Câmara Municipal de Adamantina', 'poder': 'Legislativo',
                     'estado': 'catalogo-parcial', 'evidencia': 'inventario-territorial'}],
        '1505536': [{'orgao': 'Câmara Municipal de Parauapebas', 'poder': 'Legislativo',
                     'estado': 'catalogo-parcial', 'evidencia': 'inventario-territorial'}],
        '1508001': [{'orgao': 'SEMAS-PA (cópia de decreto municipal de Tomé-Açu)', 'poder': 'desconhecido',
                     'estado': 'catalogo-parcial', 'evidencia': 'inventario-territorial'}],
        '5201405': [{'orgao': 'fonte municipal de Aparecida de Goiânia', 'poder': 'desconhecido',
                     'estado': 'catalogo-parcial', 'evidencia': 'inventario-territorial'}],
        '5218805': [{'orgao': 'fonte municipal de Rio Verde', 'poder': 'desconhecido',
                     'estado': 'catalogo-parcial', 'evidencia': 'inventario-territorial'}],
    }
    # Descoberta municipal genérica por UF: portal Interlegis SAPL como pista, sem afirmar cobertura.
    descoberta_municipal = {
        'pista': 'Interlegis lista órgãos com SAPL por UF; presença na lista ≠ catálogo reconciliado.',
        'url_indice': 'https://www12.senado.leg.br/interlegis/orgaosatendidos?servico=SAPL',
        'estado': 'nao-investigado-para-municipios-sem-diretorio',
        'leitura': (
            'Falta de pasta em municipais/ ou HTTP de portal fora do ar não prova inexistência '
            'de legislação municipal. Investigação segue por UF/ente/fonte/tipo/período.'
        ),
    }
    published = sorted(
        p.name for p in (ROOT / 'municipais').iterdir() if p.is_dir() and not p.name.startswith('.')
    )
    return {
        'contrato_versao': CONTRATO_VERSAO,
        'issue': '#74',
        'federal': federal,
        'ufs': {uf: fontes for uf, fontes in sorted(ufs.items())},
        'municipios_publicados': {
            code: municipais_publicados.get(code, [{'orgao': 'desconhecido', 'poder': 'desconhecido', 'estado': 'nao-investigado'}])
            for code in published
        },
        'municipios_sem_diretorio': {
            'contagem': 5569 - len(published),
            'estado_trabalho': 'sem-publicacao-identificada',
            'fontes': [{'orgao': 'desconhecido', 'poder': 'desconhecido', 'estado': 'nao-investigado'}],
            'descoberta': descoberta_municipal,
            'nao_inferir': [
                'ausencia-por-falta-de-pasta',
                'ausencia-por-erro-http',
                'inexistencia-por-catalogo-vazio',
            ],
        },
        'dependencias_coleta_regional': [
            'Outros agentes expandem coleta estadual/municipal e limpeza de corpos.',
            'Este registro só amplia metadados/fontes; não altera Markdown regional além do piloto #70 e do anexo CPP #77.',
        ],
        'limites': (
            'Registro versionado de fontes já identificadas nos coletores/provas. '
            'Não é censo de todos os portais municipais do Brasil.'
        ),
    }


def build_species_reconciliation() -> dict[str, Any]:
    """Contagem de arquivos publicados por espécie candidata do caminho (#83)."""
    counts: dict[str, int] = collections.Counter()
    edicoes = 0
    for path in sorted((ROOT / 'federal').glob('br-federal-*.md')):
        cand = path_identity_candidate(path.relative_to(ROOT).as_posix())
        key = cand.get('especie_candidata') or 'caminho-nao-classificado'
        counts[key] += 1
    if (ROOT / 'federal/edicoes').is_dir():
        edicoes = len(list((ROOT / 'federal/edicoes').glob('*.md')))
    errata = {
        'leis_numeradas_snapshot_correspondencia_inversa': 6333,
        'decretos_leis_snapshot_correspondencia_inversa': 9647,
        'referencia_snapshot': 'd4e425a57f1c1e1ee9f770e7bc7e673264a2ed58',
    }
    published_lei = counts.get('lei', 0)
    published_dl = counts.get('decreto-lei', 0)
    mg_inventory = load_json(ROOT / 'provas/identidade-federal-99-102-103/mg-orfaos-inventario.json')
    mg_pending = len(mg_inventory['pendentes'])
    return {
        'contrato_versao': CONTRATO_VERSAO,
        'issue': '#83',
        'escopo': 'federal/ — contagem por espécie candidata do caminho; sem certificar conteúdo.',
        'publicados_por_especie_caminho': dict(sorted(counts.items())),
        'edicoes_alternativas_em_federal_edicoes': edicoes,
        'errata_complemento_senado_totais': errata,
        'leituras': [
            {
                'especie': 'decreto-lei',
                'publicados': published_dl,
                'errata_correspondencia_inversa': errata['decretos_leis_snapshot_correspondencia_inversa'],
                'delta_arquivos_vs_errata': published_dl - errata['decretos_leis_snapshot_correspondencia_inversa'],
                'nota': 'A contagem atual inclui lotes posteriores ao snapshot; presença não certifica colação de conteúdo (#96 permanece).',
            },
            {
                'especie': 'lei',
                'publicados': published_lei,
                'errata_correspondencia_inversa': errata['leis_numeradas_snapshot_correspondencia_inversa'],
                'delta_arquivos_vs_errata': published_lei - errata['leis_numeradas_snapshot_correspondencia_inversa'],
                'nota': (
                    'Delta inclui atos admitidos após o snapshot da errata e não prova cobertura '
                    'do catálogo Senado nem ausência de candidatos sem arquivo.'
                ),
            },
        ],
        'casos_colacionados': [
            {
                'id': '#102',
                'tema': 'divergência cabeçalho 1.014-A vs identidade 4.014-A/1942',
                'estado': 'variante-da-fonte-preservada; edicao-Camara-publicada',
                'escopo': '4.014-A e lote delimitado dos três exemplos; demais candidatos não certificados',
                'provas': [
                    'provas/identidade-federal-99-102-103/NOTA-DIVERGENCIA-4014-A.md',
                    'provas/identidade-federal-99-102-103/divergencias-cabecalho-lote.md',
                ],
                'pr': 111,
            },
            {
                'id': '#103',
                'tema': 'conteúdos reciprocamente trocados Leis 12.985 e 12.988/2014',
                'estado': 'corpos-corrigidos; conversao-integral-recalculada',
                'escopo': 'somente as duas identidades; não certifica outras normas ou vigência',
                'provas': ['provas/identidade-federal-99-102-103/prova-conversao-12985-12988.json'],
                'pr': 128,
            },
        ],
        'blockers_concretos': [
            {
                'id': '#96',
                'tema': 'demais lacunas e divergências de identidade dos decretos-leis',
                'estado': 'reconciliacao-incompleta',
                'acao': 'colação por identidade, complemento, data e série; não forçar título ao caminho',
            },
            {
                'id': '#99',
                'tema': f'{mg_pending} corpos MG ainda não recuperados e duplicatas com ressalvas',
                'corpos_mg_pendentes': mg_pending,
                'inventario': 'provas/identidade-federal-99-102-103/mg-orfaos-inventario.json',
                'estado': 'corpos-pendentes; notas-nao-equivalem-a-integra',
                'acao': 'recuperar fonte oficial e conferir corpo; preservar exclusões do denominador integral',
            },
            {
                'id': '#77',
                'tema': 'fac-símiles com cobertura_transcricao ausente/parcial',
                'estado': 'transcricao-parcial-ou-ausente',
                'acao': 'colher visualmente peça a peça; CPP formulário avançou para parcial estrutural',
            },
            {
                'id': '#74',
                'tema': '5.555 municípios sem diretório + órgãos/espécies/períodos dos publicados',
                'estado': 'nao-investigado / publicado-cobertura-desconhecida',
                'acao': 'investigação por UF/ente/fonte; registro-fontes-jurisdicao.json é ponto de partida',
            },
            {
                'id': '#70',
                'tema': 'export tipado BM25 do acervo geral',
                'estado': 'export-sidecar-streaming',
                'acao': (
                    'Sidecars JSONL + inventário por campo no acervo completo; '
                    'frontmatter só onde já existe; sem inventar órgão/série/âmbito'
                ),
            },
        ],
        'limites': 'Contagem de caminhos ≠ reconciliação de identidade jurídica completa.',
    }


def apply_bm25_filters(docs: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Aplica filtros exatos tipados (keyword) separados do ranking textual."""
    out = []
    for d in docs:
        if d.get('corpo_legal_integral_pendente') or d.get('excluir_denominador_integra') is True:
            continue
        ok = True
        for key, expected in filters.items():
            if key == 'data_ato_prefix':
                if not str(d.get('data_ato', '')).startswith(str(expected)):
                    ok = False
                    break
                continue
            if key == 'data_ato_intervalo':
                inicio, fim = expected
                val = str(d.get('data_ato') or '')
                if val in ('', 'desconhecido') or not (inicio <= val <= fim):
                    ok = False
                    break
                continue
            if d.get(key) != expected:
                ok = False
                break
        if ok:
            out.append(d)
    return out


def iter_export_shards(out_dir: Path | None = None) -> Iterator[dict[str, Any]]:
    """Lê registros do export sidecar sem carregar todos os shards de uma vez."""
    out_dir = out_dir or EXPORT_DIR
    manifesto_path = out_dir / 'manifesto.json'
    if not manifesto_path.is_file():
        return
        yield  # pragma: no cover — torna a função um gerador mesmo sem shards
    manifesto = load_json(manifesto_path)
    for shard in manifesto.get('shards') or []:
        path = out_dir / shard['arquivo']
        if not path.is_file():
            continue
        with gzip.open(path, 'rt', encoding='utf-8') as fh:
            for line in fh:
                if line.strip():
                    yield json.loads(line)


def verify_bm25_filters_integrated(out_dir: Path | None = None) -> dict[str, Any]:
    """Verifica filtros BM25 sobre o export (sidecars) + entrega da íntegra.

    Não basta a demonstração isolada de meia dúzia de arquivos: confere
    combinações de filtro no fluxo de exportação e a recuperação do Markdown
    integral por hash.
    """
    out_dir = out_dir or EXPORT_DIR
    # Casos de filtro exigidos pelo aceite #70.
    cases = [
        {
            'id': 'federal-lei-2021-historica',
            'filters': {
                'esfera': 'federal',
                'especie': 'lei',
                'data_ato_prefix': '2021',
                'edicao_tipo': 'historica',
            },
            'expect_min': 1,
            'must_include_arquivo': 'federal/br-federal-lei-2021-04-01-14133.md',
        },
        {
            'id': 'resolucao-congresso-emissor-separado-da-fonte',
            'filters': {
                'esfera': 'federal',
                'especie': 'resolucao-congresso-nacional',
                'orgao_emissor': 'Congresso Nacional',
            },
            'expect_min': 1,
            'must_include_arquivo': 'federal/br-federal-resolucao-congresso-nacional-1983-10-20-1.md',
            'must_exclude_norma_id_substring': 'resolucao-senado-federal',
        },
        {
            'id': 'resolucao-senado-permanece-especie-distinta',
            'filters': {
                'esfera': 'federal',
                'especie': 'resolucao-senado-federal',
                'orgao_emissor': 'Senado Federal',
            },
            'expect_min': 1,
            'must_include_arquivo': 'federal/br-federal-resolucao-senado-federal-2019-11-01-29.md',
            'must_exclude_norma_id_substring': 'resolucao-congresso-nacional',
        },
        {
            'id': 'federal-lei-complementar-numero-1-1967',
            'filters': {
                'esfera': 'federal',
                'especie': 'lei-complementar',
                'numero': '1',
                'data_ato_prefix': '1967',
            },
            'expect_min': 1,
            'must_include_arquivo': 'federal/br-federal-lei-complementar-1967-11-09-1.md',
            'must_exclude_norma_id_substring': '1962',
        },
        {
            'id': 'lc1-1962-serie-data-distintas-da-lc1-1967',
            'filters': {
                'esfera': 'federal',
                'especie': 'lei-complementar',
                'serie_historica': 'lei-complementar-ao-ato-adicional',
                'numero': '1',
                'data_ato': '1962-07-17',
            },
            'expect_min': 1,
            'must_include_arquivo': 'federal/br-federal-lei-complementar-1962-07-17-1.md',
            'must_exclude_arquivo': 'federal/br-federal-lei-complementar-1967-11-09-1.md',
        },
        {
            'id': 'acre-opaco-provedor-nao-e-numero',
            'filters': {
                'esfera': 'estadual',
                'uf': 'AC',
                'provedor_id': '1121',
            },
            'expect_min': 1,
            'must_include_arquivo': 'estaduais/AC/br-ac-norma-1121.md',
            'assert_numero': '300',
        },
        {
            'id': 'municipal-ibge-decreto',
            'filters': {
                'esfera': 'municipal',
                'ibge': '3550308',
                'especie': 'decreto',
            },
            'expect_min': 1,
            'must_include_arquivo': 'municipais/3550308/br-municipal-3550308-decreto-2022-12-27-62100.md',
        },
        {
            'id': 'facsimile-nao-texto-integral',
            'filters': {
                'representacao': 'fac-simile',
                'cobertura_transcricao': 'ausente',
            },
            'expect_min': 1,
            'must_include_arquivo': 'federal/br-federal-decreto-1954-02-25-35110.md',
        },
        {
            'id': 'ato-sem-numero-seq-sf',
            'filters': {
                'numero_estado': 'sem-numero',
                'esfera': 'federal',
            },
            'expect_min': 1,
        },
    ]

    # Carrega metadados dos arquivos-alvo + amostra do export se existir.
    target_rels = sorted(
        {
            c['must_include_arquivo']
            for c in cases
            if c.get('must_include_arquivo')
        }
        | {
            'federal/edicoes/br-federal-lei-2021-04-01-14133-consolidada.md',
            'federal/br-federal-decreto-1823-01-09-seq-sf-1.md',
            'federal/br-federal-resolucao-congresso-nacional-1983-10-20-1.md',
            'federal/br-federal-resolucao-senado-federal-2019-11-01-29.md',
            'federal/br-federal-lei-complementar-1962-07-17-1.md',
            'federal/br-federal-lei-complementar-1967-11-09-1.md',
        }
    )
    docs_by_arquivo = {}
    for rel in target_rels:
        if (ROOT / rel).is_file():
            docs_by_arquivo[rel] = export_document(rel, include_markdown=True)

    # Integração com sidecars: se manifesto completo existir, filtra no stream.
    stream_hits: dict[str, list[str]] = {c['id']: [] for c in cases}
    manifesto_path = out_dir / 'manifesto.json'
    streamed = 0
    if manifesto_path.is_file():
        manifesto = load_json(manifesto_path)
        if manifesto.get('completo'):
            for doc in iter_export_shards(out_dir):
                streamed += 1
                for case in cases:
                    matched = apply_bm25_filters([doc], case['filters'])
                    if matched:
                        stream_hits[case['id']].append(doc['arquivo'])

    results = []
    for case in cases:
        # Base: documentos alvo carregados com íntegra.
        pool = list(docs_by_arquivo.values())
        filtered = apply_bm25_filters(pool, case['filters'])
        arquivos = {d['arquivo'] for d in filtered}
        if stream_hits[case['id']]:
            arquivos |= set(stream_hits[case['id']])
        entry = {
            'id': case['id'],
            'filters': case['filters'],
            'hits': sorted(arquivos),
            'hit_count': len(arquivos),
            'ok': len(arquivos) >= case['expect_min'],
        }
        must = case.get('must_include_arquivo')
        if must:
            entry['must_include_ok'] = must in arquivos
            entry['ok'] = entry['ok'] and entry['must_include_ok']
            exclude = case.get('must_exclude_norma_id_substring')
            if exclude:
                entry['must_exclude_ok'] = not any(exclude in rel for rel in arquivos)
                entry['ok'] = entry['ok'] and entry['must_exclude_ok']
            exclude_file = case.get('must_exclude_arquivo')
            if exclude_file:
                entry['must_exclude_file_ok'] = exclude_file not in arquivos
                entry['ok'] = entry['ok'] and entry['must_exclude_file_ok']
            if must in docs_by_arquivo:
                doc = docs_by_arquivo[must]
                meta, body, body_hash = markdown_body_hash(ROOT / must)
                entry['integra'] = {
                    'sha256_ok': doc['sha256_markdown'] == body_hash,
                    'corpo_igual': doc.get('markdown_integral') == body,
                    'bytes': doc.get('markdown_integral_bytes'),
                    'truncado': False,
                    'fonte_citada': doc.get('fonte_url'),
                    'vigencia_certificada': doc.get('vigencia_certificada'),
                }
                entry['ok'] = entry['ok'] and entry['integra']['sha256_ok'] and entry['integra']['corpo_igual']
                if 'assert_numero' in case:
                    entry['numero_ok'] = str(doc.get('numero')) == str(case['assert_numero'])
                    entry['provedor_distinto'] = str(doc.get('provedor_id')) != str(doc.get('numero'))
                    entry['ok'] = entry['ok'] and entry['numero_ok'] and entry['provedor_distinto']
        if case.get('must_exclude_norma_id_substring'):
            sub = case['must_exclude_norma_id_substring']
            entry['exclude_ok'] = all(sub not in (d.get('norma_id') or '') for d in filtered)
            entry['ok'] = entry['ok'] and entry['exclude_ok']
        results.append(entry)

    # Correlação dispositivo/fonte: fac-símile filtrado não vira texto integral.
    fac = docs_by_arquivo.get('federal/br-federal-decreto-1954-02-25-35110.md')
    correlacao = {
        'facsimile_arquivo': 'federal/br-federal-decreto-1954-02-25-35110.md',
        'texto_integral_pesquisavel': False if not fac else fac['texto_integral_pesquisavel'],
        'alerta_cobertura_textual': True if not fac else fac['alerta_cobertura_textual'],
        'ok': bool(fac) and fac['texto_integral_pesquisavel'] is False and fac['alerta_cobertura_textual'] is True,
    }

    return {
        'stream_registros_lidos': streamed,
        'casos': results,
        'correlacao_representacao': correlacao,
        'todos_ok': all(r['ok'] for r in results) and correlacao['ok'],
    }


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
            docs.append(export_document(rel, include_markdown=True))
    # Filtro combinado: federal + lei + ano 2021 + edição histórica
    filtered = apply_bm25_filters(
        docs,
        {
            'esfera': 'federal',
            'especie': 'lei',
            'data_ato_prefix': '2021',
            'edicao_tipo': 'historica',
        },
    )
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
            'orgao_emissor': {'type': 'keyword'},
            'fonte_orgao': {'type': 'keyword'},
            'serie_historica': {'type': 'keyword'},
            'senado_id': {'type': 'keyword'},
            'urn': {'type': 'keyword'},
            'relacoes': {
                'type': 'nested',
                'properties': {
                    'tipo': {'type': 'keyword'},
                    'origem': {'type': 'keyword'},
                    'destino': {'type': 'keyword'},
                    'dispositivo': {'type': 'keyword'},
                    'escopo_cobertura': {'type': 'keyword'},
                },
            },
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
            'corpo_status': {'type': 'keyword'},
            'status_publicacao': {'type': 'keyword'},
            'edicao_integral': {'type': 'boolean'},
            'corpo_legal_integral_pendente': {'type': 'boolean'},
            'excluir_denominador_integra': {'type': 'boolean'},
            'texto_integral_pesquisavel': {'type': 'boolean'},
            'fonte_integral_preservada': {'type': 'boolean'},
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
            'must_not': [
                {'term': {'corpo_legal_integral_pendente': True}},
                {'term': {'excluir_denominador_integra': True}},
                {'term': {'texto_integral_pesquisavel': False}},
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
    write_json(PROVAS / 'registro-fontes-jurisdicao.json', build_jurisdiction_sources())
    write_json(PROVAS / 'reconciliacao-especies-publicadas.json', build_species_reconciliation())
    write_json(PROVAS / 'matriz-nacional.json', build_national_matrix())
    demo = build_bm25_demo()
    write_json(PROVAS / 'bm25-mapeamento.json', demo['mapping'])
    write_json(PROVAS / 'bm25-demonstracao.json', {k: v for k, v in demo.items() if k != 'mapping'})
    write_json(PROVAS / 'identidade-casos.json', {'casos': CASOS_IDENTIDADE})
    filtros = verify_bm25_filters_integrated()
    write_json(PROVAS / 'bm25-filtros-integrados.json', filtros)
    print('inventários e demonstrações gravados em', PROVAS)


def cmd_export_acervo(
    *,
    resume: bool = True,
    shard_size: int = DEFAULT_SHARD_SIZE,
    include_markdown: bool = False,
    limit: int | None = None,
) -> None:
    result = export_acervo_streaming(
        resume=resume,
        shard_size=shard_size,
        include_markdown=include_markdown,
        limit=limit,
    )
    filtros = verify_bm25_filters_integrated()
    write_json(PROVAS / 'bm25-filtros-integrados.json', filtros)
    man = result['manifesto']
    inv = result['inventario']
    print(
        f"export-acervo: {man['total_edicoes']}/{man['total_esperado']} "
        f"completo={man['completo']} shards={len(man['shards'])} "
        f"anomalia_provedor_numero={inv['anomalias']['provedor_id_igual_numero_sem_frontmatter']} "
        f"bm25_filtros_ok={filtros['todos_ok']}"
    )


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

    published_fac = load_json(PROVAS / 'inventario-fac-similes.json')
    assert published_fac['resumo']['fac_simile_oficial'] >= 2
    # Exemplos da issue #77 — conferir arquivos vivos + linhas do inventário publicado.
    by_file = {r['arquivo']: r for r in published_fac['documentos']}
    for sample in (
        'federal/br-federal-decreto-1954-02-25-35110.md',
        'federal/br-federal-decreto-1955-06-14-37491.md',
    ):
        assert by_file[sample]['fac_simile_oficial'] is True
        assert by_file[sample]['cobertura_transcricao'] == 'ausente'
        assert by_file[sample]['representacao'] == 'fac-simile'
        live = classify_representation((ROOT / sample).read_text(encoding='utf-8'))
        assert live['fac_simile_oficial'] is True
        assert live['cobertura_transcricao'] == 'ausente'
        assert live['representacao'] == 'fac-simile'
        assert by_file[sample]['sha256_arquivo'] == sha256_file(ROOT / sample)

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

    # LC 1/1962 e LC 1/1967 têm o mesmo número, mas são normas distintas.
    lc1962 = export_document('federal/br-federal-lei-complementar-1962-07-17-1.md')
    lc1967 = export_document('federal/br-federal-lei-complementar-1967-11-09-1.md')
    assert lc1962['norma_id'] != lc1967['norma_id']
    assert lc1962['numero'] == lc1967['numero'] == '1'
    assert lc1962['data_ato'] != lc1967['data_ato']

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

    # Piloto de cabeçalhos gerais (#70): corpo preservado + proveniência
    piloto = load_json(METADADOS / 'acervo-geral-piloto.json')
    assert len(piloto['documentos']) >= 4
    for item in piloto['documentos']:
        rel = item['arquivo']
        meta, body, body_hash = markdown_body_hash(ROOT / rel)
        assert meta is not None, rel
        assert body_hash == item['sha256_corpo_antes_depois'], rel
        assert isinstance(meta.get('campo_fontes'), dict) and meta['campo_fontes']
        assert meta.get('vigencia_certificada') is False
        exported = export_document(rel)
        assert exported['sha256_markdown'] == body_hash
        assert exported['markdown_integral'] == body
        assert 'fonte_do_campo' in exported
        assert exported['fonte_do_campo']['vigencia_certificada'] == 'contrato-global-sempre-false'
        if meta.get('provedor_id'):
            assert exported.get('numero') == meta.get('norma_numero')
            assert str(exported.get('provedor_id')) == str(meta['provedor_id'])
            assert exported.get('numero') != str(meta['provedor_id'])

    # Fontes por jurisdição (#74)
    fontes = load_json(PROVAS / 'registro-fontes-jurisdicao.json')
    assert len(fontes['ufs']) == 27
    assert 'nao_inferir' in fontes['municipios_sem_diretorio']
    assert 'ausencia-por-falta-de-pasta' in fontes['municipios_sem_diretorio']['nao_inferir']
    assert 'ausencia-por-erro-http' in fontes['municipios_sem_diretorio']['nao_inferir']
    assert set(fontes['municipios_publicados']) == {
        p.name for p in (ROOT / 'municipais').iterdir() if p.is_dir() and not p.name.startswith('.')
    }

    # CPP formulário (#77): colação visual parcial
    cpp = load_json(PROVAS / 'cpp-anexo-formulario.json')
    assert cpp['cobertura_transcricao'] == 'parcial'
    assert cpp['metodo_transcricao'] == 'colacao-visual-do-fac-simile-oficial'
    transc = ROOT / cpp['transcricao']
    assert transc.is_file()
    assert sha256_file(transc) == cpp['sha256_transcricao']
    assert 'colação visual' in transc.read_text(encoding='utf-8').lower() or 'colacao visual' in transc.read_text(encoding='utf-8').lower()
    assert 'BOLETIM INDIVIDUAL' in transc.read_text(encoding='utf-8')
    cpp_md = (ROOT / 'federal/br-federal-decreto-lei-1941-10-03-3689.md').read_text(encoding='utf-8')
    assert 'anexo-formulario-boletim-individual-transcricao.md' in cpp_md
    assert 'cobertura_transcricao=parcial' in cpp_md

    # Reconciliação de espécies (#83)
    recon = load_json(PROVAS / 'reconciliacao-especies-publicadas.json')
    assert recon == build_species_reconciliation(), 'reconciliação desatualizada — rode generate'
    resolved_ids = {b['id'] for b in recon['casos_colacionados']}
    assert {'#102', '#103'} <= resolved_ids
    assert not {'#102', '#103'} & {b['id'] for b in recon['blockers_concretos']}
    for case in recon['casos_colacionados']:
        assert all((ROOT / path).is_file() for path in case['provas'])
    assert 'avanco_desde_inventario_inicial' in matriz

    # Export sidecar / inventário do acervo completo (#70)
    total_md = len(iter_markdown_rels())
    inv_path = PROVAS / 'inventario-campos-acervo.json'
    man_path = PROVAS / 'export-acervo-manifesto.json'
    assert inv_path.is_file(), 'inventario-campos-acervo.json ausente — rode export-acervo'
    assert man_path.is_file(), 'export-acervo-manifesto.json ausente — rode export-acervo'
    inventario = load_json(inv_path)
    manifesto = load_json(man_path)
    assert inventario['total_edicoes'] == total_md
    assert manifesto['total_edicoes'] == total_md
    assert manifesto['completo'] is True
    assert inventario['escolha_armazenamento']['metadados_acervo_geral'] == 'sidecar-export-jsonl'
    assert inventario['escolha_armazenamento']['markdown_corpos'] == 'nao-reescrevidos-em-massa'
    assert inventario['anomalias']['provedor_id_igual_numero_sem_frontmatter'] == 0
    # Cobertura por campo: todo campo inventariado tem contagem que soma o total.
    for field, states in inventario['por_campo'].items():
        assert sum(states.values()) == total_md, field
    # Número legal nunca é ID opaco sem frontmatter (amostra AC).
    ac_doc = export_document('estaduais/AC/br-ac-norma-1121.md', include_markdown=False)
    assert str(ac_doc['provedor_id']) == '1121'
    assert str(ac_doc['numero']) == '300'
    assert ac_doc['numero'] != ac_doc['provedor_id']
    # Sem markdown no sidecar: íntegra recuperável do arquivo + hash.
    assert 'markdown_integral' not in ac_doc or ac_doc.get('markdown_integral') is None
    full = export_document('estaduais/AC/br-ac-norma-1121.md', include_markdown=True)
    meta, body, body_hash = markdown_body_hash(ROOT / 'estaduais/AC/br-ac-norma-1121.md')
    assert full['markdown_integral'] == body
    assert full['sha256_markdown'] == body_hash == ac_doc['sha256_markdown']

    # Filtros BM25 integrados (não só demo isolada)
    filtros = verify_bm25_filters_integrated()
    assert filtros['todos_ok'], filtros
    published_filtros = PROVAS / 'bm25-filtros-integrados.json'
    if published_filtros.is_file():
        prev = load_json(published_filtros)
        assert prev.get('todos_ok') is True

    # Se shards locais existem, confere contagem e hashes dos shards.
    if (EXPORT_DIR / 'manifesto.json').is_file():
        live_man = load_json(EXPORT_DIR / 'manifesto.json')
        assert live_man['total_edicoes'] == total_md
        n_shard_docs = 0
        for shard in live_man.get('shards') or []:
            sp = EXPORT_DIR / shard['arquivo']
            assert sp.is_file()
            assert sha256_file(sp) == shard['sha256']
            with gzip.open(sp, 'rt', encoding='utf-8') as fh:
                for line in fh:
                    if line.strip():
                        n_shard_docs += 1
                        row = json.loads(line)
                        assert 'markdown_integral' not in row
                        assert row.get('vigencia_certificada') is False
                        assert 'fonte_do_campo' in row
        assert n_shard_docs == total_md

    print(
        f"verify ok: IBGE {captura['municipios']} municípios; "
        f"{published['resumo']['municipios_com_diretorio']} diretórios municipais; "
        f"{published_fac['resumo']['fac_simile_oficial']} fac-símiles oficiais; "
        f"piloto_cabecalhos={len(piloto['documentos'])}; "
        f"export_acervo={manifesto['total_edicoes']}; "
        f"bm25_filtros_ok={filtros['todos_ok']}; "
        'sem certificação de completude nacional.'
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'cmd',
        choices=['generate', 'verify', 'export-one', 'export-acervo'],
    )
    parser.add_argument('--arquivo', help='caminho relativo para export-one')
    parser.add_argument('--include-markdown', action='store_true', help='incluir corpo no JSONL (pesado)')
    parser.add_argument('--no-resume', action='store_true', help='reinicia export-acervo do zero')
    parser.add_argument('--shard-size', type=int, default=DEFAULT_SHARD_SIZE)
    parser.add_argument('--limit', type=int, default=None, help='limite de edições (testes)')
    args = parser.parse_args(argv)
    if args.cmd == 'generate':
        cmd_generate()
    elif args.cmd == 'verify':
        cmd_verify()
    elif args.cmd == 'export-acervo':
        cmd_export_acervo(
            resume=not args.no_resume,
            shard_size=args.shard_size,
            include_markdown=args.include_markdown,
            limit=args.limit,
        )
    else:
        if not args.arquivo:
            raise SystemExit('--arquivo é obrigatório para export-one')
        doc = export_document(args.arquivo, include_markdown=args.include_markdown)
        if args.include_markdown:
            preview = {
                **{k: v for k, v in doc.items() if k != 'markdown_integral'},
                'markdown_integral_bytes': len(doc['markdown_integral'].encode('utf-8')),
                'markdown_integral_sha256': doc['sha256_markdown'],
            }
        else:
            preview = doc
        print(json.dumps(preview, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
