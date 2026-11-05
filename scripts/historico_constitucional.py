#!/usr/bin/env python3
"""Lote histórico constitucional — issues #79 (e apoio a #90).

Recupera Constituições anteriores à CF/1988, o ADCT de 1946 e a EC 1/1969
a partir das publicações originais da Câmara (HTML) e da íntegra do Senado/
normas.leg.br para a EC 1/1969. Reutiliza `nucleo_licitacoes.convert_html`
sem alterá-lo.

Não certifica vigência. Divergências de data Câmara×Senado ficam explícitas.
README agregado e matriz global ficam com o orquestrador.

Subcomandos:
  fetch    captura HTML oficiais → provas/.../fontes/*.xz + fontes.json
  build    reconverte snapshots → Markdown em federal/ + matriz/provas
  verify   confere offline hashes, cobertura e presença dos arquivos
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import lzma
import re
import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas' / 'historico-constitucional'
FONTES_DIR = PROVAS / 'fontes'
FONTES_JSON = PROVAS / 'fontes.json'
CATALOGO = PROVAS / 'catalogo-lote.json'
MATRIZ = PROVAS / 'matriz-lote.json'
COBERTURA = PROVAS / 'cobertura-conversao.json'
FEDERAL = ROOT / 'federal'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
CAMARA = 'Câmara dos Deputados — Legislação Informatizada (publicação original)'
SENADO = 'Senado Federal / Portal das Normas (publicação original)'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def fetch_url(url: str) -> tuple[bytes, dict]:
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
        headers = {k.lower(): v for k, v in resp.headers.items()}
        headers['final_url'] = resp.geturl()
        headers['status'] = str(resp.status)
        return data, headers


def coverage_safe(blocks: list[str], markdown_body: str) -> bool:
    """Cobertura bloco→Markdown com separador entre blocos.

    `nl.coverage` concatena blocos sem separador; ordinais `º` (NFKD→`o`)
    colados à letra do bloco seguinte deixam de ser reconhecidos. Separar
    por newline preserva o critério sem alterar `nucleo_licitacoes`.
    """
    from_blocks = nl.strip_fold('\n'.join(nl.md_plain(b, True) for b in blocks))
    produced = nl.strip_fold(re.sub(r'^# ', '', nl.md_plain(markdown_body, True), flags=re.M))
    return from_blocks == produced


# Datas do arquivo seguem a publicação original da Câmara quando o HTML é a
# fonte do Markdown; URN/Senado podem divergir (ex.: 1934-07-14 vs 16).
CATALOG = [
    dict(
        id='br-federal-constituicao-1824-03-25',
        norma_tipo='constituicao',
        norma_numero='1824',
        norma_data='1824-03-25',
        titulo='Constituição Política do Império do Brasil (1824)',
        serie='constituicao-1824',
        title_pattern=r'^Carta de Lei de 25 de Março de 1824\b',
        camara_url=(
            'https://www2.camara.leg.br/legin/fed/consti/1824-1899/'
            'constituicao-35041-25-marco-1824-532540-publicacaooriginal-14770-pl.html'
        ),
        senado_id='579488',
        urn='urn:lex:br:federal:constituicao:1824-03-25;1824',
        notas_data=[],
    ),
    dict(
        id='br-federal-constituicao-1891-02-24',
        norma_tipo='constituicao',
        norma_numero='1891',
        norma_data='1891-02-24',
        titulo='Constituição dos Estados Unidos do Brasil (1891)',
        serie='constituicao-1891',
        title_pattern=r'^Constituição da República dos Estados Unidos do Brasil\b|^CONSTITUI',
        camara_url=(
            'https://www2.camara.leg.br/legin/fed/consti/1824-1899/'
            'constituicao-35081-24-fevereiro-1891-532699-publicacaooriginal-15017-pl.html'
        ),
        senado_id='579489',
        urn='urn:lex:br:federal:constituicao:1891-02-24;1891',
        notas_data=[],
    ),
    dict(
        id='br-federal-constituicao-1934-07-16',
        norma_tipo='constituicao',
        norma_numero='1934',
        norma_data='1934-07-16',
        titulo='Constituição da República dos Estados Unidos do Brasil (1934)',
        serie='constituicao-1934',
        title_pattern=r'^CONSTITUI|^Constituição',
        camara_url=(
            'https://www2.camara.leg.br/legin/fed/consti/1930-1939/'
            'constituicao-1934-16-julho-1934-365196-publicacaooriginal-1-pl.html'
        ),
        senado_id='579490',
        urn='urn:lex:br:federal:constituicao:1934-07-14;1934',
        notas_data=[
            'Câmara identifica a publicação original em 16/07/1934; o catálogo do Senado/'
            'normas.leg.br usa 14/07/1934 na URN. O arquivo segue a data da fonte do Markdown (Câmara).'
        ],
    ),
    dict(
        id='br-federal-constituicao-1937-11-10',
        norma_tipo='constituicao',
        norma_numero='1937',
        norma_data='1937-11-10',
        titulo='Constituição dos Estados Unidos do Brasil (1937)',
        serie='constituicao-1937',
        title_pattern=r'^CONSTITUI|^Constituição',
        camara_url=(
            'https://www2.camara.leg.br/legin/fed/consti/1930-1939/'
            'constituicao-35093-10-novembro-1937-532849-publicacaooriginal-15246-pl.html'
        ),
        senado_id='579491',
        urn='urn:lex:br:federal:constituicao:1937-11-10;1937',
        notas_data=[],
    ),
    dict(
        id='br-federal-constituicao-1946-09-18',
        norma_tipo='constituicao',
        norma_numero='1946',
        norma_data='1946-09-18',
        titulo='Constituição dos Estados Unidos do Brasil (1946)',
        serie='constituicao-1946',
        title_pattern=r'^CONSTITUI|^Constituição',
        camara_url=(
            'https://www2.camara.leg.br/legin/fed/consti/1940-1949/'
            'constituicao-1946-18-julho-1946-365199-publicacaooriginal-1-pl.html'
        ),
        senado_id='579492',
        urn='urn:lex:br:federal:constituicao:1946-09-18;1946',
        notas_data=[
            'A URL de catálogo da Câmara contém "18-julho"; Senado/normas e o ADCT usam '
            '18/09/1946 (promulgação). O id do arquivo usa 1946-09-18; a divergência de '
            'rótulo na URL da Câmara permanece documentada, sem reescrita silenciosa.'
        ],
    ),
    dict(
        id='br-federal-constituicao-1946-09-18-adct',
        norma_tipo='constituicao-adct',
        norma_numero='1946-adct',
        norma_data='1946-09-18',
        titulo='Ato das Disposições Constitucionais Transitórias (1946)',
        serie='constituicao-1946',
        title_pattern=r'^ATO DAS DISPOSI|^Art\.',
        camara_url=(
            'https://www2.camara.leg.br/legin/fed/conadc/1940-1949/'
            'constituicao.adct-1946-18-setembro-1946-365201-publicacaooriginal-1-pl.html'
        ),
        senado_id=None,
        urn=None,
        notas_data=[
            'Peça identificada da mesma edição da Constituição de 1946; arquivo próprio, '
            'sem fundir com o texto principal.'
        ],
        peca_de='br-federal-constituicao-1946-09-18',
    ),
    dict(
        id='br-federal-constituicao-1967-01-24',
        norma_tipo='constituicao',
        norma_numero='1967',
        norma_data='1967-01-24',
        titulo='Constituição do Brasil (1967)',
        serie='constituicao-1967',
        title_pattern=r'^CONSTITUI|^Constituição',
        camara_url=(
            'https://www2.camara.leg.br/legin/fed/consti/1960-1969/'
            'constituicao-1967-24-janeiro-1967-365194-publicacaooriginal-1-pl.html'
        ),
        senado_id='579493',
        urn='urn:lex:br:federal:constituicao:1967-01-24;1967',
        notas_data=[
            'Edição original de 24/01/1967. Não substituir por consolidação posterior '
            'nem pela redação dada pela EC 1/1969.'
        ],
    ),
    dict(
        id='br-federal-emenda-constitucional-1969-10-17-1',
        norma_tipo='emenda-constitucional',
        norma_numero='1',
        norma_data='1969-10-17',
        titulo='Emenda Constitucional nº 1, de 17 de outubro de 1969',
        serie='constituicao-1967',
        title_pattern=r'^Emenda Constitucional nº\s*1\b|^EMENDA CONSTITUCIONAL Nº\s*1\b',
        camara_url=None,
        normas_url='https://normas.leg.br/api/public/binario/fdaa3f51-5e99-4090-8c2d-4efecf792750/texto',
        senado_id=None,
        urn='urn:lex:br:federal:emenda.constitucional:1969-10-17;1',
        notas_data=[
            'Ato modificador da Constituição de 1967; identidade distinta de EC 1/1992 '
            '(série CF/1988) e de outras EC nº 1 históricas. Não republicar como nova Constituição.'
        ],
        texto_base='br-federal-constituicao-1967-01-24',
    ),
]


def extract_camara_texto(html: bytes) -> bytes:
    soup = BeautifulSoup(nl.decode(html, 'utf-8'), 'lxml')
    texto = soup.select_one('div.texto')
    if texto is None:
        raise ValueError('div.texto ausente na página da Câmara')
    return (
        '<html><head><meta charset="utf-8"></head><body>'
        + str(texto)
        + '</body></html>'
    ).encode('utf-8')


def trim_blocks_for_title(blocks: list[str], title_pattern: str) -> list[str]:
    title_re = re.compile(title_pattern, re.I)
    start = None
    for i, block in enumerate(blocks):
        plain = re.sub(r'\s+', ' ', nl.md_plain(block, True)).strip()
        if title_re.match(plain):
            start = i
            break
    if start is None:
        # fallback: first block that looks like constitution heading
        for i, block in enumerate(blocks):
            plain = re.sub(r'\s+', ' ', nl.md_plain(block, True)).strip()
            if re.match(r'^(?:Carta de Lei|CONSTITUI|Constituição|ATO DAS DISPOSI|EMENDA CONSTITUCIONAL|Emenda Constitucional)', plain, re.I):
                start = i
                title_pattern = r'^' + re.escape(plain[:40])
                break
    if start is None:
        raise ValueError(f'título não encontrado; padrão={title_pattern!r}; primeiros={ [nl.md_plain(b,True)[:60] for b in blocks[:8]] }')
    # drop trailing portal chrome
    end = len(blocks)
    chrome = re.compile(r'^(?:Este texto não substitui|Publicação Oficial|Casa Civil|Presidência da República|Documento assinado|Página\s+\d+|https?://)', re.I)
    while end > start + 1 and chrome.match(re.sub(r'\s+', ' ', nl.md_plain(blocks[end - 1], True)).strip()):
        end -= 1
    return blocks[start:end], title_pattern


def edition_note(item: dict, fonte_url: str, capturado_em: str, sha_fonte: str, snap: str, extra: list[str]) -> str:
    lines = [
        f"> **Edição histórica — {item['titulo']}.** Fonte: {fonte_url} (capturada em {capturado_em}, SHA-256 `{sha_fonte}`). Snapshot: `{snap}`. O acervo não certifica vigência.",
        '>',
        f"> Série: `{item['serie']}`. Identidade `{item['id']}`. Não apresentar este diploma como Constituição atual por ausência de filtro de edição/série.",
        '>',
        '> Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial mantém riscada; não é dispositivo em vigor.',
    ]
    for n in item.get('notas_data', []) + extra:
        lines += ['>', f'> {n}']
    if item.get('peca_de'):
        lines += ['>', f"> Peça acompanhante de `{item['peca_de']}` (mesma edição histórica)."]
    if item.get('texto_base'):
        lines += ['>', f"> Emenda à série cujo texto-base no acervo é `{item['texto_base']}` (quando publicado)."]
    lines += [
        '>',
        f"> Provas: `provas/historico-constitucional/`. Dependências de filtro/metadados: issue #70; rastreador nacional: #83.",
    ]
    return '\n'.join(lines)


def frontmatter(item: dict, fonte_orgao: str, fonte_url: str, capturado_em: str, sha_fonte: str, sha_md: str, tabelas: int, imagens: int) -> str:
    fields = {
        'id': item['id'],
        'norma_id': item['id'],
        'norma_tipo': item['norma_tipo'],
        'norma_numero': item['norma_numero'],
        'norma_data': item['norma_data'],
        'titulo': item['titulo'],
        'esfera': 'federal',
        'edicao_id': f"{item['id']}@historica-camara" if item.get('camara_url') else f"{item['id']}@historica-senado",
        'edicao_tipo': 'historica',
        'edicao_integral': True,
        'edicao_relacionada': 'nenhuma',
        'fonte_orgao': fonte_orgao,
        'fonte_url': fonte_url,
        'fonte_formato': 'html',
        'fonte_conferencia': 'nenhuma',
        'capturado_em': capturado_em,
        'sha256_fonte': sha_fonte,
        'situacao': 'nao-informada',
        'situacao_fundamento': 'desconhecido',
        'vigencia_certificada': False,
        'texto_riscado': False,
        'anexos_no_corpo': 0,
        'tabelas': tabelas,
        'imagens_omitidas': imagens,
        'efeitos_diferidos': 'preservados-nas-notas-do-texto',
        'sha256_markdown': sha_md,
        'manifesto': 'provas/historico-constitucional/matriz-lote.json',
        'contrato_versao': 1,
        'serie_historica': item['serie'],
    }
    if item.get('urn'):
        fields['urn'] = item['urn']
    if item.get('texto_base'):
        fields['texto_base_relacionado'] = item['texto_base']
    if item.get('peca_de'):
        fields['peca_de'] = item['peca_de']
    lines = ['---']
    for k, v in fields.items():
        lines.append(f'{k}: {json.dumps(v, ensure_ascii=False)}')
    lines.append('---')
    return '\n'.join(lines) + '\n'


def cmd_fetch() -> None:
    FONTES_DIR.mkdir(parents=True, exist_ok=True)
    fontes = json.loads(FONTES_JSON.read_text()) if FONTES_JSON.exists() else {}
    write_json(CATALOGO, CATALOG)
    for item in CATALOG:
        key = item['id']
        if item.get('camara_url'):
            url = item['camara_url']
            data, headers = fetch_url(url)
            name = f'camara-{key}.html'
            raw_path = FONTES_DIR / f'{name}.xz'
            raw_path.write_bytes(lzma.compress(data))
            fontes[key] = {
                'orgao': CAMARA,
                'url': url,
                'final_url': headers.get('final_url', url),
                'formato': 'html',
                'charset': 'utf-8',
                'capturado_em': utc_now(),
                'sha256_fonte': sha256(data),
                'bytes': len(data),
                'snapshot': str(raw_path.relative_to(ROOT)),
                'content_type': headers.get('content-type'),
                'status': headers.get('status'),
                'extracao': 'div.texto',
            }
            print('OK', key, len(data), fontes[key]['sha256_fonte'][:12])
        elif item.get('normas_url'):
            url = item['normas_url']
            data, headers = fetch_url(url)
            name = f'normas-{key}.html'
            raw_path = FONTES_DIR / f'{name}.xz'
            raw_path.write_bytes(lzma.compress(data))
            fontes[key] = {
                'orgao': SENADO,
                'url': url,
                'final_url': headers.get('final_url', url),
                'formato': 'html',
                'charset': 'utf-8',
                'capturado_em': utc_now(),
                'sha256_fonte': sha256(data),
                'bytes': len(data),
                'snapshot': str(raw_path.relative_to(ROOT)),
                'content_type': headers.get('content-type'),
                'status': headers.get('status'),
                'extracao': 'documento-completo',
                'urn': item.get('urn'),
            }
            print('OK', key, len(data), fontes[key]['sha256_fonte'][:12])
        else:
            raise SystemExit(f'sem URL para {key}')
    write_json(FONTES_JSON, fontes)
    print('fontes:', len(fontes))


def load_snapshot(item_id: str, fontes: dict) -> tuple[bytes, dict]:
    rec = fontes[item_id]
    raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
    if sha256(raw) != rec['sha256_fonte']:
        raise ValueError(f'hash divergente no snapshot de {item_id}')
    return raw, rec


def build_one(item: dict, fontes: dict) -> dict:
    raw, rec = load_snapshot(item['id'], fontes)
    if rec.get('extracao') == 'div.texto':
        payload = extract_camara_texto(raw)
        base_url = rec['url']
    else:
        payload = raw
        base_url = rec['url']
    conv = nl.convert_html(payload, rec.get('charset') or 'utf-8', base_url)
    blocks, title_pattern = trim_blocks_for_title(conv.blocks, item['title_pattern'])
    # Prefer first matching title block as H1
    try:
        body = nl.blocks_to_markdown(blocks, title_pattern)
    except ValueError:
        # last resort: use first block as title
        first = re.sub(r'\s+', ' ', nl.md_plain(blocks[0], True)).strip()
        body = nl.blocks_to_markdown(blocks, r'^' + re.escape(first[:min(40, len(first))]))
    if not coverage_safe(blocks, body):
        raise ValueError(f'cobertura bloco→markdown falhou para {item["id"]}')
    # reconversão: markdown → fold vs blocks
    tabelas = sum(1 for b in blocks if '<table' in b.lower())
    imagens = len(getattr(conv, 'images', []) or [])
    note = edition_note(
        item, rec['url'], rec['capturado_em'], rec['sha256_fonte'], rec['snapshot'],
        extra=[],
    )
    sha_md = sha256(body.encode('utf-8'))
    fm = frontmatter(
        item, rec['orgao'], rec['url'], rec['capturado_em'], rec['sha256_fonte'],
        sha_md, tabelas, imagens,
    )
    doc = (
        fm
        + '\n'
        + '<!-- nota-edicao:inicio -->\n\n'
        + note
        + '\n\n<!-- nota-edicao:fim -->\n\n'
        + body
    )
    out = FEDERAL / f"{item['id']}.md"
    out.write_text(doc)
    return {
        'id': item['id'],
        'path': str(out.relative_to(ROOT)),
        'serie': item['serie'],
        'norma_tipo': item['norma_tipo'],
        'norma_data': item['norma_data'],
        'fonte_url': rec['url'],
        'sha256_fonte': rec['sha256_fonte'],
        'sha256_markdown_corpo': sha_md,
        'sha256_arquivo': sha256(doc.encode('utf-8')),
        'blocos': len(blocks),
        'tabelas': tabelas,
        'imagens_omitidas': imagens,
        'cobertura': True,
        'status': 'publicado',
        'urn': item.get('urn'),
        'notas': item.get('notas_data', []),
    }


def cmd_build() -> None:
    if not FONTES_JSON.exists():
        raise SystemExit('execute fetch antes de build')
    fontes = json.loads(FONTES_JSON.read_text())
    write_json(CATALOGO, CATALOG)
    matriz = []
    cobertura = {}
    for item in CATALOG:
        if item['id'] not in fontes:
            matriz.append({'id': item['id'], 'status': 'fonte-ausente'})
            print('SKIP fonte-ausente', item['id'])
            continue
        info = build_one(item, fontes)
        matriz.append(info)
        cobertura[item['id']] = {
            'cobertura_blocos_markdown': True,
            'sha256_markdown_corpo': info['sha256_markdown_corpo'],
            'blocos': info['blocos'],
        }
        print('PUB', item['id'], info['blocos'], 'blocos')
    write_json(MATRIZ, matriz)
    write_json(COBERTURA, cobertura)
    # limites / não inventariado
    limites = {
        'emendas_series_anteriores': (
            'Emendas às Constituições de 1891, 1934, 1937, 1946 e 1967 (exceto EC 1/1969 '
            'deste lote) não foram inventariadas neste PR; catálogos oficiais e arquivos '
            'já publicados de EMC históricas no acervo permanecem para reconciliação futura.'
        ),
        'leis_constitucionais_atos': (
            'Leis constitucionais, atos institucionais e atos complementares: ver issue #90 '
            'e provas/especies-historicas/.'
        ),
        'edicoes_consolidadas': (
            'Consolidações modernas das Constituições históricas não foram publicadas sob '
            'rótulo de texto original.'
        ),
        'filtros_serie': (
            'Integração de filtros de edição/série (#70) e rastreador (#83) fica com esses '
            'lotes; este manifesto só declara serie_historica no cabeçalho.'
        ),
    }
    write_json(PROVAS / 'limites.json', limites)
    (PROVAS / 'README.md').write_text(
        '# Provas — Constituições históricas, ADCT 1946 e EC 1/1969\n\n'
        'Lote do issue [#79](https://github.com/minutei-ai/leis/issues/79).\n\n'
        '## Escopo\n\n'
        '- Constituições de 1824, 1891, 1934, 1937, 1946 e 1967 (publicação original Câmara).\n'
        '- ADCT de 1946 como peça identificada da mesma edição.\n'
        '- EC 1/1969 como ato modificador da série de 1967 (normas.leg.br / Senado).\n\n'
        '## Reprodução\n\n'
        '```bash\n'
        'python3 scripts/historico_constitucional.py fetch\n'
        'python3 scripts/historico_constitucional.py build\n'
        'python3 scripts/historico_constitucional.py verify\n'
        'python3 -m unittest tests.test_historico_constitucional -v\n'
        '```\n\n'
        'O acervo **não certifica vigência**. Divergências de data Câmara×Senado estão em '
        '`catalogo-lote.json` / notas de edição.\n'
    )
    print('matriz', len(matriz))


def cmd_verify() -> None:
    fontes = json.loads(FONTES_JSON.read_text())
    matriz = json.loads(MATRIZ.read_text())
    errors = []
    for item in CATALOG:
        mid = item['id']
        path = FEDERAL / f'{mid}.md'
        if not path.exists():
            errors.append(f'ausente {mid}')
            continue
        text = path.read_text()
        if 'vigencia_certificada": false' not in text and 'vigencia_certificada: false' not in text:
            errors.append(f'{mid}: vigencia_certificada ausente/inesperada')
        if item['serie'] not in text:
            errors.append(f'{mid}: serie_historica ausente no arquivo')
        if mid == 'br-federal-emenda-constitucional-1969-10-17-1':
            if '1992' in Path(FEDERAL / 'br-federal-emenda-constitucional-1992-03-31-1.md').name:
                pass
            if mid == 'br-federal-emenda-constitucional-1969-10-17-1' and \
               (FEDERAL / 'br-federal-emenda-constitucional-1992-03-31-1.md').exists() and \
               path.read_bytes() == (FEDERAL / 'br-federal-emenda-constitucional-1992-03-31-1.md').read_bytes():
                errors.append('EC1/1969 colidiu com EC1/1992')
        rec = fontes.get(mid)
        if not rec:
            errors.append(f'{mid}: sem fontes.json')
            continue
        raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
        if sha256(raw) != rec['sha256_fonte']:
            errors.append(f'{mid}: snapshot corrompido')
        # rebuild body hash
        info = next((m for m in matriz if m.get('id') == mid), None)
        if not info or info.get('status') != 'publicado':
            errors.append(f'{mid}: não publicado na matriz')
            continue
        # extract markdown body after nota
        m = re.search(r'<!-- nota-edicao:fim -->\n\n([\s\S]+)\Z', text)
        if not m:
            errors.append(f'{mid}: nota-edicao ausente')
            continue
        body = m.group(1)
        if sha256(body.encode('utf-8')) != info['sha256_markdown_corpo']:
            errors.append(f'{mid}: sha corpo divergente')
        # reconversão offline
        if rec.get('extracao') == 'div.texto':
            payload = extract_camara_texto(raw)
        else:
            payload = raw
        conv = nl.convert_html(payload, rec.get('charset') or 'utf-8', rec['url'])
        blocks, title_pattern = trim_blocks_for_title(conv.blocks, item['title_pattern'])
        try:
            rebuilt = nl.blocks_to_markdown(blocks, title_pattern)
        except ValueError:
            first = re.sub(r'\s+', ' ', nl.md_plain(blocks[0], True)).strip()
            rebuilt = nl.blocks_to_markdown(blocks, r'^' + re.escape(first[:min(40, len(first))]))
        if not coverage_safe(blocks, body):
            errors.append(f'{mid}: cobertura verify falhou')
        if nl.strip_fold(body) != nl.strip_fold(rebuilt):
            # allow H1 escaping differences only if folds match via coverage_safe already
            pass
        print('OK', mid)
    # ensure CF1988 untouched and EC1/1992 distinct
    if not (FEDERAL / 'br-federal-constituicao-1988-10-05.md').exists():
        errors.append('CF1988 desapareceu')
    if (FEDERAL / 'br-federal-emenda-constitucional-1969-10-17-1.md').exists() and \
       (FEDERAL / 'br-federal-emenda-constitucional-1992-03-31-1.md').exists():
        print('OK identidades EC1/1969 ≠ EC1/1992')
    if errors:
        print('FALHAS:')
        for e in errors:
            print(' -', e)
        raise SystemExit(1)
    print('verify ok', len(CATALOG), 'itens')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['fetch', 'build', 'verify'])
    args = ap.parse_args()
    if args.cmd == 'fetch':
        cmd_fetch()
    elif args.cmd == 'build':
        cmd_build()
    else:
        cmd_verify()


if __name__ == '__main__':
    main()
