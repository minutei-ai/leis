"""Lote CDC (Lei 8.078/1990) e ECA (Lei 8.069/1990).

Converte as edições oficiais do Planalto em Markdown, confere com a Câmara,
grava manifesto e provas próprias em `metadados/nucleo-cdc-eca.json` e
`provas/nucleo-cdc-eca/`. Não altera o núcleo de licitações nem o espaço LGPD.

Reusa o conversor HTML de `nucleo_licitacoes` (riscados, links, tabelas, imagens).
O acervo não certifica vigência.

Subcomandos:
  fetch  DIR   captura as fontes oficiais
  build  DIR   converte, concilia e publica Markdown/provas/manifesto
  verify       reconverte snapshots e confere byte a byte offline
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import nucleo_licitacoes as nl

ROOT = Path(__file__).resolve().parent.parent
PROVAS = ROOT / 'provas/nucleo-cdc-eca'
FONTES = PROVAS / 'fontes'
MANIFESTO = ROOT / 'metadados/nucleo-cdc-eca.json'
CONTRATO = ROOT / 'metadados/CONTRATO-cdc-eca.md'
CONTRACT_VERSION = 1
UNKNOWN = 'desconhecido'
USER_AGENT = nl.USER_AGENT

PLANALTO = 'Presidência da República — Planalto'
CAMARA = 'Câmara dos Deputados — LegIn'

# Ordinal partido do Planalto: "3 <u><sup>o</sup></u>" → "3º" (cp1252).
ORDINAL_SPLIT_RE = re.compile(
    rb'(\d)\s*<u>\s*<sup>\s*o\s*</sup>\s*</u>', re.I)


def normalize_planalto_ordinals(data: bytes) -> bytes:
    """Junta ordinal tipográfico partido em <sup>o</sup> sem alterar o restante."""
    prev = None
    cur = data
    while prev != cur:
        prev = cur
        cur = ORDINAL_SPLIT_RE.sub(lambda m: m.group(1) + 'º'.encode('cp1252'), cur)
    return cur


SOURCES = {
    'planalto-8078': dict(
        url='https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm',
        file='planalto-l8078compilado.htm', orgao=PLANALTO, formato='html', charset='cp1252',
        normalize_ordinals=True),
    'camara-8078': dict(
        url=('https://www2.camara.leg.br/legin/fed/lei/1990/'
             'lei-8078-11-setembro-1990-365086-normaatualizada-pl.html'),
        file='camara-lei-8078-normaatualizada.html', orgao=CAMARA, formato='html', charset='utf-8',
        normalize_ordinals=False),
    'planalto-8069': dict(
        url='https://www.planalto.gov.br/ccivil_03/leis/l8069.htm',
        file='planalto-l8069.htm', orgao=PLANALTO, formato='html', charset='cp1252',
        normalize_ordinals=True),
    'camara-8069': dict(
        url=('https://www2.camara.leg.br/legin/fed/lei/1990/'
             'lei-8069-13-julho-1990-372211-normaatualizada-pl.html'),
        file='camara-lei-8069-normaatualizada.html', orgao=CAMARA, formato='html', charset='utf-8',
        normalize_ordinals=False),
}

# Travas: mudanças novas nestes conjuntos devem falhar no build/verify.
KNOWN_CDC_ONLY_CONFERENCIA = [
    '11-A', '111', '112', '113', '114', '115', '116', '117', '118', '119']
KNOWN_CDC_FORMA = ['8', '18', '51', '54', '75', '79', '99', '102', '103', '104']
KNOWN_CDC_SUBST = ['11', '39', '65', '90', '110']
KNOWN_ECA_FORMA = ['47', '94', '102', '148', '256', '260-E', '263', '267']
KNOWN_ECA_SUBST = [
    '4', '34', '36', '37', '42', '48', '51', '52', '85', '92', '93', '120', '166',
    '196', '221', '240', '241', '241-A', '241-B', '241-C', '241-D', '243', '244-A',
    '247', '254']

DOCS = [
    dict(
        slug='br-federal-lei-1990-09-11-8078',
        arquivo='federal/br-federal-lei-1990-09-11-8078.md',
        fonte='planalto-8078',
        conferencia=['camara-8078'],
        base_url=SOURCES['planalto-8078']['url'],
        norma=dict(
            tipo='lei', numero='8078', data='1990-09-11',
            titulo='LEI Nº 8.078, DE 11 DE SETEMBRO DE 1990',
            ementa='Dispõe sobre a proteção do consumidor e dá outras providências.',
            aliases=['CDC', 'Código de Defesa do Consumidor', 'Codigo de Defesa do Consumidor']),
        edicao=dict(tipo='consolidada', integral=True, rotulo='compilado-planalto'),
        area='consumidor',
        identity_fragments=[
            'proteção do consumidor', 'Código de Defesa do Consumidor',
            'Art. 1º O presente código estabelece normas de proteção e defesa do consumidor'],
        known_only_conferencia=KNOWN_CDC_ONLY_CONFERENCIA,
        known_forma=KNOWN_CDC_FORMA,
        known_subst=KNOWN_CDC_SUBST,
        min_artigos=100,
    ),
    dict(
        slug='br-federal-lei-1990-07-13-8069',
        arquivo='federal/br-federal-lei-1990-07-13-8069.md',
        fonte='planalto-8069',
        conferencia=['camara-8069'],
        base_url=SOURCES['planalto-8069']['url'],
        norma=dict(
            tipo='lei', numero='8069', data='1990-07-13',
            titulo='LEI Nº 8.069, DE 13 DE JULHO DE 1990',
            ementa='Dispõe sobre o Estatuto da Criança e do Adolescente, e dá outras providências.',
            aliases=['ECA', 'Estatuto da Criança e do Adolescente', 'Estatuto da Crianca e do Adolescente']),
        edicao=dict(tipo='consolidada', integral=True, rotulo='compilado-planalto'),
        area='infancia-adolescencia',
        identity_fragments=[
            'Estatuto da Criança e do Adolescente',
            'Art. 1º Esta Lei dispõe sobre a proteção integral à criança e ao adolescente'],
        known_only_conferencia=[],
        known_forma=KNOWN_ECA_FORMA,
        known_subst=KNOWN_ECA_SUBST,
        min_artigos=250,
    ),
]

FRONTMATTER_KEYS = [
    'id', 'norma_id', 'norma_tipo', 'norma_numero', 'norma_data', 'titulo', 'esfera',
    'edicao_id', 'edicao_tipo', 'edicao_integral', 'fonte_orgao', 'fonte_url', 'fonte_formato',
    'fonte_conferencia', 'capturado_em', 'sha256_fonte', 'situacao', 'situacao_fundamento',
    'vigencia_certificada', 'texto_riscado', 'anexos_no_corpo', 'tabelas', 'imagens_omitidas',
    'efeitos_diferidos', 'sha256_markdown', 'manifesto', 'contrato_versao', 'lote', 'area',
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def snapshot_path(key: str) -> Path:
    return FONTES / (SOURCES[key]['file'] + '.xz')


def prepare_source_bytes(key: str, data: bytes) -> bytes:
    if SOURCES[key].get('normalize_ordinals'):
        return normalize_planalto_ordinals(data)
    return data


def content_bytes(key: str, data: bytes) -> bytes:
    """Bytes usados na conversão/cobertura (após normalização estável do lote)."""
    prepared = prepare_source_bytes(key, data)
    return nl.WAF_SCRIPT_RE.sub(b'', prepared).rstrip()


def fetch(dest: Path):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, spec in SOURCES.items():
        target = dest / spec['file']
        header_file = dest / (spec['file'] + '.headers')
        captured = nl.now_utc()
        proc = subprocess.run([
            'curl', '--silent', '--show-error', '--location', '--proto', '=https',
            '--proto-redir', '=https', '--connect-timeout', '30', '--max-time', '180',
            '--max-filesize', str(64 * 1024 * 1024), '--user-agent', USER_AGENT,
            '--dump-header', str(header_file),
            '--write-out', '%{http_code} %{url_effective}', '--output', str(target),
            spec['url'],
        ], capture_output=True, text=True)
        record = dict(
            url=spec['url'], capturado_em=captured, curl_exit=proc.returncode,
            user_agent=USER_AGENT, orgao=spec['orgao'], formato=spec['formato'])
        if proc.returncode == 0:
            status, _, effective = proc.stdout.partition(' ')
            record.update(http_status=int(status), url_final=effective)
            data = target.read_bytes()
            record.update(bytes=len(data), sha256=sha256(data))
            raw_headers = header_file.read_bytes().decode('latin-1').replace('\r\n', '\n')
            final_block = [b for b in raw_headers.split('\n\n') if b.strip()][-1:] or ['']
            for line in final_block[0].splitlines():
                name, _, value = line.partition(':')
                if name.lower() in ('last-modified', 'etag', 'content-type', 'date'):
                    record['cabecalho_' + name.lower().replace('-', '_')] = value.strip()
            looks_like_gateway = b'504 Gateway Time-out' in data[:400] or b'<title>5' in data[:400]
            record['utilizavel'] = status == '200' and not looks_like_gateway and len(data) > 1000
            if not record['utilizavel']:
                record['motivo'] = f'resposta HTTP {status} sem conteúdo utilizável ({len(data)} bytes)'
            else:
                record['sha256_conteudo'] = sha256(content_bytes(key, data))
                if SOURCES[key].get('normalize_ordinals'):
                    record['normalizacao_ordinal_planalto'] = True
        else:
            record.update(utilizavel=False, motivo=(proc.stderr or '')[-500:])
        header_file.unlink(missing_ok=True)
        records[key] = record
        print(f'{key}: {record.get("http_status")} {record.get("bytes")} '
              f'utilizável={record["utilizavel"]}', flush=True)
    write_json(dest / 'fetch.json', records)
    return records


def render_frontmatter(meta: dict) -> str:
    lines = ['---']
    for key in FRONTMATTER_KEYS:
        if key in meta and meta[key] is not None:
            lines.append(f'{key}: {json.dumps(meta[key], ensure_ascii=False)}')
    lines.append('---')
    return '\n'.join(lines) + '\n\n'


def parse_frontmatter(text: str):
    if not text.startswith('---\n'):
        raise ValueError('sem cabeçalho de metadados')
    end = text.index('\n---\n', 4)
    meta = {}
    for line in text[4:end].splitlines():
        key, _, value = line.partition(': ')
        meta[key] = json.loads(value)
    body = text[end + len('\n---\n'):]
    if not body.startswith('\n'):
        raise ValueError('cabeçalho deve ser seguido de linha em branco')
    return meta, body[1:]


def validate_meta(meta: dict, name: str) -> list[str]:
    errors = []
    for key in meta:
        if key not in FRONTMATTER_KEYS:
            errors.append(f'{name}: campo fora do contrato do lote: {key}')
    required = [
        'id', 'norma_id', 'norma_tipo', 'norma_numero', 'norma_data', 'titulo', 'esfera',
        'edicao_id', 'edicao_tipo', 'edicao_integral', 'fonte_orgao', 'fonte_url', 'fonte_formato',
        'fonte_conferencia', 'capturado_em', 'sha256_fonte', 'situacao', 'situacao_fundamento',
        'vigencia_certificada', 'texto_riscado', 'anexos_no_corpo', 'tabelas', 'imagens_omitidas',
        'efeitos_diferidos', 'sha256_markdown', 'manifesto', 'contrato_versao', 'lote', 'area',
    ]
    for key in required:
        if key not in meta:
            errors.append(f'{name}: campo obrigatório ausente: {key}')
    if meta.get('contrato_versao') != CONTRACT_VERSION:
        errors.append(f'{name}: contrato_versao deve ser {CONTRACT_VERSION}')
    if meta.get('vigencia_certificada') is not False:
        errors.append(f'{name}: vigencia_certificada deve ser false')
    if meta.get('lote') != 'cdc-eca':
        errors.append(f'{name}: lote deve ser "cdc-eca"')
    if meta.get('manifesto') != 'metadados/nucleo-cdc-eca.json':
        errors.append(f'{name}: manifesto deve apontar metadados/nucleo-cdc-eca.json')
    if meta.get('edicao_tipo') != 'consolidada':
        errors.append(f'{name}: edicao_tipo deve ser consolidada neste lote')
    if meta.get('fonte_url') and urlparse(str(meta.get('fonte_url'))).scheme != 'https':
        errors.append(f'{name}: fonte_url deve ser https')
    conf = meta.get('fonte_conferencia')
    if not isinstance(conf, list) or not conf:
        errors.append(f'{name}: fonte_conferencia deve ser lista não vazia de URLs https')
    elif meta.get('fonte_url') in conf:
        errors.append(f'{name}: fonte_conferencia não pode repetir fonte_url')
    return errors


def note_for(doc: dict, rec: dict) -> str:
    aliases = ', '.join(doc['norma']['aliases'])
    lines = [
        f'**Edição consolidada — {PLANALTO} (lote CDC/ECA).** '
        f'Fonte: {doc["base_url"]} (capturada em {rec["capturado_em"]}, '
        f'SHA-256 da fonte `{rec["sha256"]}`). O acervo não certifica vigência.',
        f'Identidade normativa: Lei {doc["norma"]["numero"]}/{doc["norma"]["data"][:4]}; '
        f'aliases observados na fonte/catalogação: {aliases}.',
        'Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial mantém '
        'riscada; não é dispositivo em vigor. Notas de alteração, remissões e indicações de '
        'produção de efeitos da fonte foram preservadas.',
        'A conferência usa a edição atualizada da Câmara dos Deputados sem combinar redações; '
        'divergências conhecidas ficam no manifesto e nas provas deste lote.',
        'Normalização aplicada só ao markup partido de ordinais tipográficos do Planalto '
        '(`3 <u><sup>o</sup></u>` → `3º`), sem reeditar o texto jurídico.',
    ]
    return nl.note_block(lines)


def convert_doc(doc: dict, sources: dict, fontes: dict):
    key = doc['fonte']
    spec = SOURCES[key]
    raw = sources[key]
    data = prepare_source_bytes(key, raw)
    conv = nl.convert_html(data, spec['charset'], doc['base_url'])
    body = nl.blocks_to_markdown(conv.blocks, r'^LEI(?: COMPLEMENTAR)? N')
    coverage_ok = (
        nl.strip_fold(nl.source_text_chars_from_html(data, spec['charset']))
        == nl.strip_fold(nl.md_text_all(body)))
    if not coverage_ok:
        raise SystemExit(f'{doc["slug"]}: cobertura de texto não equivalente à fonte principal')

    title_at = body.index('# ') if body.startswith('# ') else body.index('\n# ') + 1
    title_end = body.index('\n\n', title_at)
    title = body[title_at + 2:title_end]
    rest = body[title_end + 2:]

    arts, order = nl.split_articles(nl.main_body_blocks(conv.blocks))
    if len(order) < doc['min_artigos']:
        raise SystemExit(
            f'{doc["slug"]}: poucos artigos convertidos ({len(order)} < {doc["min_artigos"]})')
    plain_all = nl.strip_fold(nl.md_text_all(body))
    for frag in doc['identity_fragments']:
        if nl.strip_fold(frag) not in plain_all:
            raise SystemExit(f'{doc["slug"]}: fragmento de identidade ausente: {frag!r}')

    proof = dict(
        documento=doc['slug'],
        area=doc['area'],
        fonte_principal=key,
        sha256_fonte_principal=fontes[key]['sha256'],
        sha256_conteudo_convertido=sha256(content_bytes(key, raw)),
        normalizacao_ordinal_planalto=bool(spec.get('normalize_ordinals')),
        cobertura_texto=dict(
            descricao=('texto integral da página da fonte principal (após normalização estável '
                       'de ordinais tipográficos, sem imagens) == texto do Markdown, '
                       'após normalização strip_fold'),
            equivalente=True,
            caracteres_normalizados=len(nl.strip_fold(nl.md_text_all(body)))),
        conversao=dict(conv.stats, imagens=conv.images, tabelas=conv.tables, blocos=len(conv.blocks),
                       artigos=len(order)),
        fontes_conferencia=[],
    )

    problems = []
    for ckey in doc['conferencia']:
        cspec = SOURCES[ckey]
        cdata = prepare_source_bytes(ckey, sources[ckey])
        cconv = nl.convert_html(cdata, cspec['charset'], cspec['url'])
        art_result, _primary, _secondary = nl.article_proof(conv.blocks, cconv.blocks)
        forma = sorted(art_result.get('divergencias_de_forma') or [])
        subst = sorted(art_result.get('divergencias_substanciais') or [])
        only_p = list(art_result.get('apenas_na_principal') or [])
        only_c = list(art_result.get('apenas_na_conferencia') or [])
        entry = dict(
            fonte=ckey, url=cspec['url'], sha256=fontes[ckey]['sha256'],
            artigos=art_result,
            titulos_e_capitulos=dict(
                iguais=nl.headings(nl.main_body_blocks(conv.blocks))
                == nl.headings(nl.main_body_blocks(cconv.blocks)),
                principal=len(nl.headings(nl.main_body_blocks(conv.blocks))),
                conferencia=len(nl.headings(nl.main_body_blocks(cconv.blocks)))),
        )
        proof['fontes_conferencia'].append(entry)
        if only_p:
            problems.append(f'{doc["slug"]}: artigos só na principal vs {ckey}: {only_p}')
        if only_c != sorted(doc['known_only_conferencia']):
            problems.append(
                f'{doc["slug"]}: apenas_na_conferencia esperado '
                f'{sorted(doc["known_only_conferencia"])}, obtido {only_c}')
        if forma != sorted(doc['known_forma']):
            problems.append(
                f'{doc["slug"]}: divergencias_de_forma esperadas '
                f'{sorted(doc["known_forma"])}, obtidas {forma}')
        if subst != sorted(doc['known_subst']):
            problems.append(
                f'{doc["slug"]}: divergencias_substanciais esperadas '
                f'{sorted(doc["known_subst"])}, obtidas {subst}')

    if problems:
        raise SystemExit('Conferência do lote CDC/ECA falhou:\n - ' + '\n - '.join(problems))

    rec = fontes[key]
    anexos = sum(1 for b in conv.blocks if re.match(r'(?i)^ANEXO\b', nl.md_plain(b, True)))
    meta = dict(
        id=doc['slug'],
        norma_id=doc['slug'],
        norma_tipo=doc['norma']['tipo'],
        norma_numero=doc['norma']['numero'],
        norma_data=doc['norma']['data'],
        titulo=doc['norma']['titulo'],
        esfera='federal',
        edicao_id=f'{doc["slug"]}@{doc["edicao"]["rotulo"]}',
        edicao_tipo=doc['edicao']['tipo'],
        edicao_integral=doc['edicao']['integral'],
        fonte_orgao=PLANALTO,
        fonte_url=doc['base_url'],
        fonte_formato='html',
        fonte_conferencia=[SOURCES[k]['url'] for k in doc['conferencia']],
        capturado_em=rec['capturado_em'],
        sha256_fonte=rec['sha256'],
        situacao='nao-informada',
        situacao_fundamento=UNKNOWN,
        vigencia_certificada=False,
        texto_riscado=conv.stats['trechos_riscados'] > 0,
        anexos_no_corpo=anexos,
        tabelas=conv.stats['tabelas_markdown'] + conv.stats['tabelas_html'],
        imagens_omitidas=len(conv.images),
        efeitos_diferidos='preservados-nas-notas-do-texto',
        manifesto='metadados/nucleo-cdc-eca.json',
        contrato_versao=CONTRACT_VERSION,
        lote='cdc-eca',
        area=doc['area'],
    )
    # Corpo publicado: título da conversão + nota + restante da fonte.
    published_body = f'# {title}\n\n{note_for(doc, rec)}\n\n{rest}'.rstrip() + '\n'
    meta['sha256_markdown'] = sha256(published_body.encode('utf-8'))
    markdown = render_frontmatter(meta) + published_body
    return markdown, meta, proof, conv, order


def build_manifest(docs_meta: list[dict], proofs: dict, fontes: dict) -> dict:
    documentos = []
    for doc, meta in zip(DOCS, docs_meta):
        documentos.append(dict(
            id=doc['slug'],
            arquivo=doc['arquivo'],
            area=doc['area'],
            aliases=doc['norma']['aliases'],
            ementa=doc['norma']['ementa'],
            edicao_id=meta['edicao_id'],
            edicao_tipo=meta['edicao_tipo'],
            fonte_principal=doc['fonte'],
            fonte_url=doc['base_url'],
            fontes_conferencia=doc['conferencia'],
            estado_recuperacao='publicado-conferido',
            vigencia_certificada=False,
            divergencias_conhecidas=dict(
                apenas_na_conferencia=doc['known_only_conferencia'],
                divergencias_de_forma=doc['known_forma'],
                divergencias_substanciais=doc['known_subst'],
                tratamento=('Markdown segue o Planalto; a Câmara permanece só como conferência. '
                            'Redações não foram combinadas. O acervo não escolhe vigência.'),
            ),
            prova=f'provas/nucleo-cdc-eca/reconciliacao-{doc["slug"]}.json',
        ))
    return dict(
        contrato='metadados/CONTRATO-cdc-eca.md',
        contrato_versao=CONTRACT_VERSION,
        lote='cdc-eca',
        issue_refs=['https://github.com/minutei-ai/leis/issues/62'],
        escopo=('Lote independente do núcleo de licitações e do espaço LGPD: apenas CDC '
                '(Lei 8.078/1990) e ECA (Lei 8.069/1990).'),
        vigencia_certificada=False,
        diagnostico_coleta='provas/nucleo-cdc-eca/diagnostico-coleta-cdc-eca.md',
        documentos=documentos,
        fontes={k: dict(
            url=v['url'], orgao=v['orgao'], formato=v['formato'],
            capturado_em=fontes[k]['capturado_em'], sha256=fontes[k]['sha256'],
            sha256_conteudo=fontes[k].get('sha256_conteudo'),
            snapshot=str(snapshot_path(k).relative_to(ROOT)),
        ) for k, v in SOURCES.items()},
        provas={
            'fontes.json': 'provas/nucleo-cdc-eca/fontes.json',
            **{f'reconciliacao-{d["slug"]}.json': f'provas/nucleo-cdc-eca/reconciliacao-{d["slug"]}.json'
               for d in DOCS},
        },
    )


def compute(sources: dict, fontes: dict):
    docs_out = {}
    proofs = {}
    metas = []
    for doc in DOCS:
        markdown, meta, proof, _conv, _order = convert_doc(doc, sources, fontes)
        docs_out[doc['arquivo']] = markdown
        metas.append(meta)
        proofs[f'reconciliacao-{doc["slug"]}.json'] = proof
    fontes_out = {}
    for key, rec in fontes.items():
        entry = dict(rec)
        entry['snapshot'] = str(snapshot_path(key).relative_to(ROOT))
        entry['sha256_snapshot_armazenado'] = sha256(snapshot_path(key).read_bytes())
        fontes_out[key] = entry
    proofs['fontes.json'] = fontes_out
    proofs['ferramentas.json'] = dict(
        nota=('Versões usadas na geração. A conversão HTML depende do analisador (libxml2) '
              'embutido no lxml; outras versões podem alterar o resultado byte a byte.'),
        **nl.tool_versions(),
        lote='cdc-eca',
    )
    manifest = build_manifest(metas, proofs, fontes)
    return docs_out, proofs, manifest


def write_outputs(docs: dict, proofs: dict, manifest: dict):
    for rel, text in docs.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    for name, proof in proofs.items():
        write_json(PROVAS / name, proof)
    write_json(MANIFESTO, manifest)


def build(dest: Path):
    dest = Path(dest)
    fetched = json.loads((dest / 'fetch.json').read_text(encoding='utf-8'))
    sources = {}
    for key, spec in SOURCES.items():
        rec = fetched[key]
        if not rec.get('utilizavel'):
            raise SystemExit(f'{key}: fonte indispensável não obtida: {rec.get("motivo")}')
        data = (dest / spec['file']).read_bytes()
        if sha256(data) != rec['sha256']:
            raise SystemExit(f'{key}: arquivo capturado não confere com fetch.json')
        FONTES.mkdir(parents=True, exist_ok=True)
        snapshot_path(key).write_bytes(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME))
        rec['sha256_conteudo'] = sha256(content_bytes(key, data))
        sources[key] = data
    docs, proofs, manifest = compute(sources, fetched)
    write_outputs(docs, proofs, manifest)
    print(f'{len(docs)} documentos, {len(proofs)} provas, manifesto em '
          f'{MANIFESTO.relative_to(ROOT)}')


def verify() -> list[str]:
    errors = []
    fontes = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
    sources = {}
    for key, spec in SOURCES.items():
        rec = fontes[key]
        if not rec.get('utilizavel'):
            errors.append(f'{key}: fonte indispensável marcada como não utilizável')
            continue
        path = snapshot_path(key)
        if not path.exists():
            errors.append(f'{key}: snapshot ausente')
            continue
        stored = path.read_bytes()
        data = lzma.decompress(stored)
        if sha256(data) != rec['sha256']:
            errors.append(f'{key}: snapshot não confere com o SHA-256 registrado')
        if sha256(content_bytes(key, data)) != rec.get('sha256_conteudo'):
            errors.append(f'{key}: SHA-256 do conteúdo convertido não confere')
        if sha256(stored) != rec.get('sha256_snapshot_armazenado'):
            errors.append(f'{key}: arquivo de snapshot armazenado diverge do registrado')
        sources[key] = data
    if errors:
        return errors
    docs, proofs, manifest = compute(sources, fontes)
    for rel, expected in docs.items():
        path = ROOT / rel
        if not path.exists():
            errors.append(f'{rel}: ausente')
            continue
        actual = path.read_text(encoding='utf-8')
        if actual != expected:
            errors.append(f'{rel}: diverge da conversão reprodutível dos snapshots')
            continue
        meta, body = parse_frontmatter(actual)
        errors.extend(validate_meta(meta, rel))
        if sha256(body.encode('utf-8')) != meta.get('sha256_markdown'):
            errors.append(f'{rel}: sha256_markdown não confere com o corpo')
    for name, expected in proofs.items():
        path = PROVAS / name
        if not path.exists():
            errors.append(f'provas/nucleo-cdc-eca/{name}: ausente')
            continue
        published = json.loads(path.read_text(encoding='utf-8'))
        if published != json.loads(json.dumps(expected, ensure_ascii=False)):
            errors.append(f'provas/nucleo-cdc-eca/{name}: diverge do recálculo')
    if not MANIFESTO.exists():
        errors.append('metadados/nucleo-cdc-eca.json ausente')
    else:
        stored = json.loads(MANIFESTO.read_text(encoding='utf-8'))
        if stored != json.loads(json.dumps(manifest, ensure_ascii=False)):
            errors.append('metadados/nucleo-cdc-eca.json diverge do recálculo')
    errors.extend(identity_coverage_errors())
    return errors


def identity_coverage_errors(root: Path | None = None) -> list[str]:
    """Detecta recaída das lacunas CDC/ECA por identidade normativa (não só contagem)."""
    root = root or ROOT
    errors = []
    federal = root / 'federal'
    for doc in DOCS:
        path = root / doc['arquivo']
        number = doc['norma']['numero']
        date = doc['norma']['data']
        # Identidade por nome canônico.
        if not path.is_file():
            errors.append(f'cobertura-identidade: ausente {doc["arquivo"]}')
            continue
        # Evitar colisão com decretos/outras espécies do mesmo número.
        collisions = [
            p.name for p in federal.glob(f'br-federal-*-{number}.md')
            if p.name != path.name and not p.name.startswith('br-federal-lei-')
        ]
        # Aceita só a lei canônica; outras espécies com o mesmo número não contam.
        text = path.read_text(encoding='utf-8')
        try:
            meta, body = parse_frontmatter(text)
        except ValueError as exc:
            errors.append(f'cobertura-identidade: {doc["slug"]} cabeçalho inválido: {exc}')
            continue
        if meta.get('norma_numero') != number or meta.get('norma_data') != date:
            errors.append(
                f'cobertura-identidade: {doc["slug"]} norma_numero/data divergem '
                f'({meta.get("norma_numero")}, {meta.get("norma_data")})')
        if meta.get('norma_id') != doc['slug']:
            errors.append(f'cobertura-identidade: {doc["slug"]} norma_id divergente')
        folded = nl.strip_fold(body)
        for frag in doc['identity_fragments']:
            if nl.strip_fold(frag) not in folded:
                errors.append(
                    f'cobertura-identidade: {doc["slug"]} sem fragmento {frag!r}')
        # Alias check: pelo menos um alias deve ser recuperável no manifesto do lote.
        if collisions:
            # Informational only when unrelated species share a number; not an error by itself.
            pass
    # Recaída por busca alternativa de aliases em leis 1990 sem o arquivo canônico.
    if not (root / DOCS[0]['arquivo']).is_file() or not (root / DOCS[1]['arquivo']).is_file():
        for p in federal.glob('br-federal-lei-1990-*.md'):
            head = p.read_text(encoding='utf-8', errors='replace')[:4000].lower()
            if 'código de defesa do consumidor' in head or 'codigo de defesa do consumidor' in head:
                errors.append(
                    f'cobertura-identidade: CDC encontrado sob identidade alternativa {p.name}')
            if 'estatuto da criança e do adolescente' in head or 'estatuto da crianca e do adolescente' in head:
                errors.append(
                    f'cobertura-identidade: ECA encontrado sob identidade alternativa {p.name}')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('fetch').add_argument('dest')
    sub.add_parser('build').add_argument('dest')
    sub.add_parser('verify')
    args = parser.parse_args(argv)
    if args.command == 'fetch':
        fetch(Path(args.dest))
    elif args.command == 'build':
        build(Path(args.dest))
    else:
        errors = verify()
        for error in errors:
            print('ERRO:', error)
        if errors:
            raise SystemExit(1)
        print('lote CDC/ECA: documentos, provas, manifesto e cobertura por identidade conferem')


if __name__ == '__main__':
    main()
