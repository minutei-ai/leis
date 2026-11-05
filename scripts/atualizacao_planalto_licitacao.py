"""Atualização Planalto das quatro normas de licitação da issue #93.

Decretos 11.246/2022 e 11.878/2024; Leis 12.527/2011 (LAI) e 12.462/2011 (RDC).
Lote independente do núcleo de licitações: reutiliza convert_html sem alterar
o gerador/manifesto daquele núcleo.

Subcomandos:
  ingest DIR   grava snapshots + fontes.json a partir de capturas locais
  build        reconverte snapshots → Markdown, manifesto e provas
  verify       confere offline Markdown, hashes, regressões e status da MP 1.349
"""
from __future__ import annotations

import argparse
import datetime
import json
import lzma
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/atualizacao-planalto-licitacao'
FONTES_DIR = PROVAS / 'fontes'
MANIFESTO = PROVAS / 'manifesto.json'
FONTES_JSON = PROVAS / 'fontes.json'
CONTRATO = ROOT / 'metadados/CONTRATO-atualizacao-planalto-licitacao.md'
MANIFESTO_META = ROOT / 'metadados/atualizacao-planalto-licitacao.json'
UNKNOWN = nl.UNKNOWN
PLANALTO = nl.PLANALTO
USER_AGENT = nl.USER_AGENT
CONTRACT_VERSION = 1
LOTE = 'atualizacao-planalto-licitacao'

SOURCES = {
    'planalto-d11246': dict(
        url='https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2022/decreto/D11246.htm',
        file='planalto-d11246.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-d11878': dict(
        url='https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2024/decreto/d11878.htm',
        file='planalto-d11878.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-l12527': dict(
        url='https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm',
        file='planalto-l12527.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-l12462': dict(
        url='https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12462.htm',
        file='planalto-l12462.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
}

# Evidência Senado/Congresso sobre a MP 1.349/2026 (art. 63 § 17 da Lei 12.462).
MP1349_STATUS = dict(
    materia_codigo='173530',
    processo_id='9029245',
    identificacao='MPV 1349/2026',
    url_materia='https://legis.senado.leg.br/dadosabertos/materia/173530.json',
    url_processo='https://legis.senado.leg.br/dadosabertos/processo/9029245.json',
    indicador_tramitando='Não',
    situacao_atual='SEM EFICÁCIA',
    sigla_situacao_atual='SEFICA',
    data_situacao_atual='2026-08-06',
    decisao=dict(
        data='2026-08-04',
        sigla='PERDA_EFICACIA',
        descricao=('Perda de eficácia, em decorrência do término do prazo '
                   'para sua votação no Congresso'),
    ),
    destino=dict(sigla='ARQUIVO', descricao='Ao arquivo'),
    leitura=(
        'O Planalto ainda exibe o § 17 do art. 63 da Lei 12.462 com nota da MP 1.349/2026. '
        'O Senado/Congresso registra perda de eficácia em 2026-08-04 (SEFICA). '
        'O acervo reproduz a compilação do Planalto e registra a perda de eficácia; '
        'não certifica vigência residual do § 17 nem reconstrói lei de conversão inexistente.'
    ),
)

DOCS = [
    dict(
        slug='br-federal-decreto-2022-10-27-11246',
        arquivo='federal/br-federal-decreto-2022-10-27-11246.md',
        fonte='planalto-d11246',
        norma=dict(
            tipo='decreto', numero='11246', data='2022-10-27',
            titulo='DECRETO Nº 11.246, DE 27 DE OUTUBRO DE 2022',
            ementa=('Regulamenta o disposto no § 3º do art. 8º da Lei nº 14.133, de 1º de abril '
                    'de 2021, para dispor sobre as regras de atuação do agente de contratação '
                    'e da equipe de apoio, regras de designação do gestor e fiscais de contratos '
                    'e regras sobre a atuação da comissão de contratação.')),
        title_pattern=r'^DECRETO',
        regressao=[
            dict(nome='art8-par1-gestores', pattern=r'§ 1º.*os gestores e os fiscais de contratos'),
            dict(nome='nota-13031', pattern=r'Decreto nº 13\.031'),
            dict(nome='art25-gestor-setorial', pattern=r'gestor setorial'),
            dict(nome='fisc-admin-nota', pattern=r'III - fiscalização administrativa[\s\S]{0,900}Decreto nº 13\.031'),
        ],
    ),
    dict(
        slug='br-federal-decreto-2024-01-09-11878',
        arquivo='federal/br-federal-decreto-2024-01-09-11878.md',
        fonte='planalto-d11878',
        norma=dict(
            tipo='decreto', numero='11878', data='2024-01-09',
            titulo='DECRETO Nº 11.878, DE 9 DE JANEIRO DE 2024',
            ementa=('Regulamenta o art. 79, caput, incisos I a III, da Lei nº 14.133, de 1º de '
                    'abril de 2021, para dispor sobre o procedimento auxiliar de credenciamento.')),
        title_pattern=r'^DECRETO',
        regressao=[
            dict(nome='art1-incisos', pattern=r'art\. 79, caput, incisos I a III'),
            dict(nome='nota-13106', pattern=r'Decreto nº 13\.106'),
        ],
    ),
    dict(
        slug='br-federal-lei-2011-11-18-12527',
        arquivo='federal/br-federal-lei-2011-11-18-12527.md',
        fonte='planalto-l12527',
        norma=dict(
            tipo='lei', numero='12527', data='2011-11-18',
            titulo='LEI Nº 12.527, DE 18 DE NOVEMBRO DE 2011',
            ementa=('Regula o acesso a informações previsto no inciso XXXIII do art. 5º, no '
                    'inciso II do § 3º do art. 37 e no § 2º do art. 216 da Constituição Federal; '
                    'altera a Lei nº 8.112, de 11 de dezembro de 1990; altera a Lei nº 8.159, '
                    'de 8 de janeiro de 1991; e dá outras providências.')),
        title_pattern=r'^LEI',
        regressao=[
            dict(nome='art-8a', pattern=r'Art\. 8º-A\.'),
            dict(nome='art-8b', pattern=r'Art\. 8º-B'),
            dict(nome='nota-15141', pattern=r'Lei nº 15\.141'),
        ],
    ),
    dict(
        slug='br-federal-lei-2011-08-04-12462',
        arquivo='federal/br-federal-lei-2011-08-04-12462.md',
        fonte='planalto-l12462',
        norma=dict(
            tipo='lei', numero='12462', data='2011-08-04',
            titulo='LEI Nº 12.462, DE 4 DE AGOSTO DE 2011',
            ementa=('Institui o Regime Diferenciado de Contratações Públicas - RDC; altera a '
                    'Lei nº 10.683, de 28 de maio de 2003; e dá outras providências.')),
        title_pattern=r'^LEI',
        regressao=[
            dict(nome='art63-par17', pattern=r'§ 17\..*capital de giro'),
            dict(nome='nota-mp1349', pattern=r'Medida Provisória nº 1\.349'),
        ],
    ),
]


def now_utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def snapshot_path(key: str) -> Path:
    return FONTES_DIR / f'{SOURCES[key]["file"]}.xz'


def read_snapshot(key: str) -> bytes:
    return lzma.decompress(snapshot_path(key).read_bytes())


def ingest(src_dir: Path) -> dict:
    """Ingere capturas locais nomeadas como nos SOURCES['file']."""
    FONTES_DIR.mkdir(parents=True, exist_ok=True)
    fontes = {}
    captured = now_utc()
    mapping = {
        'planalto-d11246': 'D11246.htm',
        'planalto-d11878': 'd11878.htm',
        'planalto-l12527': 'l12527.htm',
        'planalto-l12462': 'l12462.htm',
    }
    for key, fname in mapping.items():
        spec = SOURCES[key]
        raw = (src_dir / fname).read_bytes()
        if len(raw) < 1000:
            raise SystemExit(f'{fname}: captura vazia ou incompleta ({len(raw)} bytes)')
        snap = snapshot_path(key)
        xz = lzma.compress(raw)
        snap.write_bytes(xz)
        fontes[key] = dict(
            url=spec['url'], orgao=spec['orgao'], formato=spec['formato'],
            charset=spec['charset'], capturado_em=captured, user_agent=USER_AGENT,
            bytes=len(raw), sha256=nl.sha256(raw), sha256_conteudo=nl.content_sha256(raw),
            snapshot=str(snap.relative_to(ROOT)),
            sha256_snapshot_armazenado=nl.sha256(xz), utilizavel=True,
        )
        print(f'ingest {key}: {len(raw)} sha256={fontes[key]["sha256"][:16]}…', flush=True)
    write_json(FONTES_JSON, fontes)
    return fontes


def load_fontes() -> dict:
    return json.loads(FONTES_JSON.read_text(encoding='utf-8'))


def historica_path(slug: str) -> str:
    return f'federal/edicoes/{slug}-historica.md'


def edition_note(doc: dict, rec: dict, conv: nl.Converter) -> str:
    hist = historica_path(doc['slug'])
    lines = [
        (f'**Edição consolidada — {rec["orgao"]} (lote {LOTE}, issue #93).** Fonte: {rec["url"]} '
         f'(capturada em {rec["capturado_em"]}, SHA-256 da fonte `{rec["sha256"]}`, '
         f'SHA-256 do conteúdo sem script de proteção `{rec["sha256_conteudo"]}`). '
         f'Snapshot: `{rec["snapshot"]}`. O acervo não certifica vigência.'),
        ('Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial mantém '
         'riscada; não é dispositivo em vigor. Notas de alteração da fonte foram preservadas.'),
        (f'A edição anterior deste caminho está preservada como edição histórica em `{hist}` '
         f'(autenticada também por SHA-256 em '
         '`provas/atualizacao-planalto-licitacao/baseline-edicao-anterior.json`); '
         'não foi apagada silenciosamente.'),
    ]
    if doc['slug'].endswith('12462'):
        lines.append(
            '**MP 1.349/2026 e o § 17 do art. 63:** o Planalto inclui o § 17 com nota da '
            f'MP 1.349/2026. O Senado registra `{MP1349_STATUS["situacao_atual"]}` '
            f'({MP1349_STATUS["decisao"]["sigla"]}) em {MP1349_STATUS["decisao"]["data"]} — '
            f'{MP1349_STATUS["decisao"]["descricao"]}. {MP1349_STATUS["leitura"]}'
        )
    lines.append(
        f'Prova: `provas/{LOTE}/reconciliacao-{doc["slug"]}.json`. Contrato: '
        '`metadados/CONTRATO-atualizacao-planalto-licitacao.md`.')
    if conv.images:
        lines.append(
            f'{len(conv.images)} imagem(ns) institucional(is) do cabeçalho foram omitidas '
            '(brasão/logotipo sem texto jurídico).')
    return nl.note_block(lines)


def build_document(doc: dict, data: bytes, rec: dict):
    spec = SOURCES[doc['fonte']]
    conv = nl.convert_html(data, spec['charset'], spec['url'])
    body = nl.blocks_to_markdown(conv.blocks, doc['title_pattern'])
    src = nl.strip_fold(nl.source_text_chars_from_html(data, spec['charset']))
    md_all = nl.strip_fold(nl.md_text_all(body))
    coverage_ok = src == md_all
    arts, order = nl.split_articles(conv.blocks)
    anexos = sum(1 for b in conv.blocks if re.match(r'^ANEXO\b', nl.md_plain(b, True).strip(), re.I))
    note = edition_note(doc, rec, conv)
    if '# ' not in body:
        raise SystemExit(f'{doc["slug"]}: título H1 ausente após conversão')
    title_at = 0 if body.startswith('# ') else body.index('\n# ') + 1
    title_end = body.index('\n\n', title_at)
    head, rest = body[:title_end], body[title_end + 2:]
    published_body = head + '\n\n' + note + '\n\n' + rest
    if not published_body.endswith('\n'):
        published_body += '\n'

    norma = doc['norma']
    edicao_id = f'{doc["slug"]}@consolidada-planalto'
    meta = dict(
        id=doc['slug'],
        norma_id=doc['slug'],
        norma_tipo=norma['tipo'],
        norma_numero=norma['numero'],
        norma_data=norma['data'],
        titulo=norma['titulo'],
        esfera='federal',
        edicao_id=edicao_id,
        edicao_tipo='consolidada',
        edicao_integral=True,
        edicao_relacionada=f'{doc["slug"]}-historica',
        fonte_orgao=spec['orgao'],
        fonte_url=spec['url'],
        fonte_formato='html',
        fonte_conferencia='nenhuma',
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
        sha256_markdown=nl.sha256(published_body.encode('utf-8')),
        manifesto=str(MANIFESTO_META.relative_to(ROOT)),
        contrato_versao=CONTRACT_VERSION,
    )
    errors = nl.validate_meta(meta, doc['slug'])
    if errors:
        raise SystemExit('metadados inválidos:\n' + '\n'.join(errors))

    markdown = nl.render_frontmatter(meta) + published_body
    _, body_only = nl.parse_frontmatter(markdown)
    meta['sha256_markdown'] = nl.sha256(body_only.encode('utf-8'))
    markdown = nl.render_frontmatter(meta) + body_only

    # regressão checks on published body
    fails = []
    for reg in doc['regressao']:
        if not re.search(reg['pattern'], body_only, re.I | re.S):
            fails.append(reg['nome'])
    if fails:
        raise SystemExit(f'{doc["slug"]}: regressão falhou: {fails}')

    proof = dict(
        documento=doc['slug'],
        fonte_principal=doc['fonte'],
        sha256_fonte_principal=rec['sha256'],
        sha256_conteudo=rec['sha256_conteudo'],
        capturado_em=rec['capturado_em'],
        url=spec['url'],
        snapshot=rec['snapshot'],
        sha256_snapshot_armazenado=rec['sha256_snapshot_armazenado'],
        cobertura_texto=dict(
            equivalente=coverage_ok,
            caracteres_normalizados_fonte=len(src),
            caracteres_normalizados_markdown=len(md_all),
            metodo='strip_fold(source_text_chars_from_html) == strip_fold(md_text_all(body_convertido))',
        ),
        conversao=dict(**conv.stats, imagens=conv.images, tabelas=conv.tables,
                       blocos=len(conv.blocks), artigos=len(order)),
        regressao=[{**r, 'ok': True} for r in doc['regressao']],
        identidade=dict(norma_id=doc['slug'], numero=norma['numero'], data=norma['data'],
                        titulo=norma['titulo'], ementa=norma['ementa']),
        limites=[
            'Fonte única (Planalto); fonte_conferencia=nenhuma.',
            'Edição consolidada do Planalto; não é fac-símile do DOU original.',
            f'Edição histórica anterior em {historica_path(doc["slug"])}.',
            'situacao=nao-informada; vigencia_certificada=false.',
            'Imagens institucionais omitidas; notas/riscados/tabelas preservados.',
        ],
    )
    if doc['slug'].endswith('12462'):
        proof['mp_1349_status'] = MP1349_STATUS
        proof['limites'].append(
            '§ 17 reproduzido conforme Planalto; perda de eficácia da MP 1.349/2026 '
            'registrada a partir do Senado/Congresso (não inferida).')
    if not coverage_ok:
        raise SystemExit(f'{doc["slug"]}: cobertura fonte→Markdown falhou '
                         f'({len(src)} vs {len(md_all)})')

    entry = dict(
        id=doc['slug'], arquivo=doc['arquivo'], norma=norma,
        edicao=dict(tipo='consolidada', integral=True, identidade='consolidada-planalto',
                    edicao_id=edicao_id, relacionada=f'{doc["slug"]}-historica',
                    historica=historica_path(doc['slug'])),
        situacao=dict(valor='nao-informada'),
        fonte=dict(chave=doc['fonte'], orgao=spec['orgao'], url=spec['url'], formato='html',
                   capturado_em=rec['capturado_em'], sha256=rec['sha256'],
                   sha256_conteudo=rec['sha256_conteudo'], snapshot=rec['snapshot'],
                   sha256_snapshot_armazenado=rec['sha256_snapshot_armazenado']),
        prova=f'provas/{LOTE}/reconciliacao-{doc["slug"]}.json',
        sha256_markdown=meta['sha256_markdown'],
        regressao=[r['nome'] for r in doc['regressao']],
    )
    return markdown, proof, entry


def compute(sources: dict, fontes: dict):
    docs_out, proofs, manifest_docs = {}, {}, []
    for doc in DOCS:
        key = doc['fonte']
        markdown, proof, entry = build_document(doc, sources[key], fontes[key])
        docs_out[doc['slug']] = dict(arquivo=doc['arquivo'], markdown=markdown,
                                     meta=nl.parse_frontmatter(markdown)[0])
        proofs[doc['slug']] = proof
        manifest_docs.append(entry)
    manifest = dict(
        contrato_versao=CONTRACT_VERSION,
        lote=LOTE,
        issue=93,
        descricao=('Atualização da redação compilada do Planalto para os Decretos 11.246/2022 e '
                   '11.878/2024 e as Leis 12.527/2011 e 12.462/2011, com notas de alteração e '
                   'registro da perda de eficácia da MP 1.349/2026.'),
        gerado_em=now_utc(),
        vigencia_certificada=False,
        mp_1349_status=MP1349_STATUS,
        baseline_edicao_anterior='provas/atualizacao-planalto-licitacao/baseline-edicao-anterior.json',
        documentos=manifest_docs,
    )
    return docs_out, proofs, manifest


def write_outputs(docs_out, proofs, manifest):
    PROVAS.mkdir(parents=True, exist_ok=True)
    for slug, payload in docs_out.items():
        path = ROOT / payload['arquivo']
        path.write_text(payload['markdown'], encoding='utf-8')
        write_json(PROVAS / f'reconciliacao-{slug}.json', proofs[slug])
        print(f'wrote {path}', flush=True)
    write_json(MANIFESTO, manifest)
    write_json(MANIFESTO_META, manifest)
    readme = PROVAS / 'README.md'
    readme.write_text(
        '# Atualização Planalto — Decretos 11.246/11.878 e Leis 12.527/12.462 (issue #93)\n\n'
        'Reconversão integral das páginas compiladas do Planalto. O acervo não certifica vigência.\n\n'
        '## Conteúdo\n\n'
        '- `fontes.json` e `fontes/*.htm.xz` — capturas e hashes\n'
        '- `reconciliacao-*.json` — cobertura fonte→Markdown e regressões\n'
        '- `baseline-edicao-anterior.json` e `edicoes-anteriores/*.md.xz` — autenticação da edição anterior\n'
        '- `federal/edicoes/*-historica.md` — edição histórica consultável (padrão #33/#59)\n'
        '- `manifesto.json` — catálogo do lote, inclusive status da MP 1.349/2026\n\n'
        '## MP 1.349/2026\n\n'
        f'- Situação no Senado: **{MP1349_STATUS["situacao_atual"]}** '
        f'({MP1349_STATUS["decisao"]["sigla"]}) em {MP1349_STATUS["decisao"]["data"]}.\n'
        f'- {MP1349_STATUS["leitura"]}\n\n'
        '## Conferência\n\n'
        '```bash\n'
        '/home/yorizel/.local/bin/resource-run --wait python3 scripts/atualizacao_planalto_licitacao.py verify\n'
        '/home/yorizel/.local/bin/resource-run --wait python3 -m unittest tests.test_atualizacao_planalto_licitacao -v\n'
        '```\n',
        encoding='utf-8',
    )
    CONTRATO.write_text(
        '# Contrato — atualização Planalto de normas de licitação (issue #93)\n\n'
        'Vale para os quatro Markdown atualizados neste lote. Cabeçalho `---` com campos planos; '
        'detalhe em [`atualizacao-planalto-licitacao.json`](atualizacao-planalto-licitacao.json).\n\n'
        '## Regras\n\n'
        '- `vigencia_certificada` é sempre `false`; `situacao` permanece `nao-informada`.\n'
        '- Edição `consolidada` do Planalto no caminho canônico; a edição anterior permanece '
        'como `historica` em `federal/edicoes/*-historica.md`, autenticada também em '
        '`provas/atualizacao-planalto-licitacao/baseline-edicao-anterior.json`.\n'
        '- Texto riscado (`~~…~~`) e notas de alteração vêm da fonte; não se combina redação '
        'com Câmara/Senado neste lote.\n'
        '- Lei 12.462: o § 17 permanece como no Planalto; a perda de eficácia da MP 1.349/2026 '
        'é evidência do Senado/Congresso registrada no manifesto e na nota de edição.\n'
        '- Imagens institucionais do cabeçalho são omitidas; tabelas e anexos textuais permanecem.\n'
        f'- `contrato_versao`: {CONTRACT_VERSION}.\n',
        encoding='utf-8',
    )


def build():
    fontes = load_fontes()
    sources = {k: read_snapshot(k) for k in SOURCES}
    docs_out, proofs, manifest = compute(sources, fontes)
    write_outputs(docs_out, proofs, manifest)
    print('build ok', flush=True)


def verify_mp1349_evidence():
    """Recalcula a situação da MP a partir das duas respostas oficiais preservadas."""
    evidence = json.loads((PROVAS / 'mp1349-evidencia-status.json').read_text(encoding='utf-8'))
    payloads = {}
    for kind, rec in evidence['fontes'].items():
        compressed = (ROOT / rec['snapshot']).read_bytes()
        assert nl.sha256(compressed) == rec['sha256_xz'], kind
        raw = lzma.decompress(compressed)
        assert nl.sha256(raw) == rec['sha256'] and len(raw) == rec['bytes'], kind
        assert rec['url'] == MP1349_STATUS[f'url_{kind}'], kind
        payloads[kind] = json.loads(raw)
    materia = payloads['materia']['DetalheMateria']['Materia']
    identity = materia['IdentificacaoMateria']
    assert identity['CodigoMateria'] == MP1349_STATUS['materia_codigo']
    assert identity['IdentificacaoProcesso'] == MP1349_STATUS['processo_id']
    assert identity['DescricaoIdentificacaoMateria'] == MP1349_STATUS['identificacao']
    assert identity['IndicadorTramitando'] == MP1349_STATUS['indicador_tramitando']
    decision = materia['DecisaoEDestino']['Decisao']
    for source, field in [('Data', 'data'), ('Sigla', 'sigla'), ('Descricao', 'descricao')]:
        assert decision[source] == MP1349_STATUS['decisao'][field], field
    processo = payloads['processo']
    assert str(processo['id']) == MP1349_STATUS['processo_id']
    assert str(processo['codigoMateria']) == MP1349_STATUS['materia_codigo']
    assert processo['identificacao'] == MP1349_STATUS['identificacao']
    for source, field in [('situacaoAtual', 'situacao_atual'),
                          ('siglaSituacaoAtual', 'sigla_situacao_atual'),
                          ('dataSituacaoAtual', 'data_situacao_atual')]:
        assert processo[source] == MP1349_STATUS[field], field
    assert processo['deliberacao']['siglaTipo'] == decision['Sigla']
    assert processo['deliberacao']['data'] == decision['Data']
    return payloads


def verify():
    verify_mp1349_evidence()
    fontes = load_fontes()
    sources = {k: read_snapshot(k) for k in SOURCES}
    docs_out, proofs, manifest = compute(sources, fontes)
    problems = []
    for key, rec in fontes.items():
        raw = sources[key]
        if nl.sha256(raw) != rec['sha256']:
            problems.append(f'{key}: sha256 diverge')
        if nl.content_sha256(raw) != rec['sha256_conteudo']:
            problems.append(f'{key}: content sha256 diverge')
        if nl.sha256(snapshot_path(key).read_bytes()) != rec['sha256_snapshot_armazenado']:
            problems.append(f'{key}: snapshot xz hash diverge')
    for slug, payload in docs_out.items():
        published = (ROOT / payload['arquivo']).read_text(encoding='utf-8')
        if published != payload['markdown']:
            problems.append(f'{slug}: Markdown publicado diverge da reconversão')
        meta, body = nl.parse_frontmatter(published)
        if meta.get('vigencia_certificada') is not False:
            problems.append(f'{slug}: vigencia_certificada deve ser false')
        if meta.get('situacao') != 'nao-informada':
            problems.append(f'{slug}: situacao deve ser nao-informada')
        if meta.get('sha256_markdown') != nl.sha256(body.encode('utf-8')):
            problems.append(f'{slug}: sha256_markdown diverge')
        doc = next(d for d in DOCS if d['slug'] == slug)
        for reg in doc['regressao']:
            if not re.search(reg['pattern'], body, re.I | re.S):
                problems.append(f'{slug}: regressão {reg["nome"]} ausente')
    # MP status locked in manifesto
    st = manifest.get('mp_1349_status') or {}
    if st.get('decisao', {}).get('sigla') != 'PERDA_EFICACIA':
        problems.append('manifesto: MP 1349 sem PERDA_EFICACIA')
    if st.get('situacao_atual') != 'SEM EFICÁCIA':
        problems.append('manifesto: MP 1349 situacao_atual inesperada')
    baseline_path = PROVAS / 'baseline-edicao-anterior.json'
    if not baseline_path.is_file():
        problems.append('baseline-edicao-anterior.json ausente')
    else:
        baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
        for slug, info in baseline.get('documentos', {}).items():
            hist = ROOT / historica_path(slug)
            if not hist.is_file():
                problems.append(f'{slug}: edição histórica ausente em {historica_path(slug)}')
                continue
            meta, body = nl.parse_frontmatter(hist.read_text(encoding='utf-8'))
            if meta.get('edicao_tipo') != 'historica':
                problems.append(f'{slug}: edição histórica sem edicao_tipo=historica')
            if meta.get('vigencia_certificada') is not False:
                problems.append(f'{slug}: histórica com vigencia_certificada != false')
            if meta.get('situacao') != 'nao-informada':
                problems.append(f'{slug}: histórica com situacao != nao-informada')
            if meta.get('sha256_corpo_preservado') != info.get('sha256'):
                problems.append(f'{slug}: sha256_corpo_preservado diverge do baseline')
            if meta.get('sha256_markdown') != nl.sha256(body.encode('utf-8')):
                problems.append(f'{slug}: histórica sha256_markdown diverge')
            xz = PROVAS / 'edicoes-anteriores' / f'{slug}.md.xz'
            if not xz.is_file():
                problems.append(f'{slug}: snapshot da edição anterior ausente')
            else:
                raw = lzma.decompress(xz.read_bytes())
                if nl.sha256(raw) != info.get('sha256'):
                    problems.append(f'{slug}: snapshot da edição anterior diverge do baseline')
            pub_meta = nl.parse_frontmatter((ROOT / next(
                d['arquivo'] for d in DOCS if d['slug'] == slug)).read_text(encoding='utf-8'))[0]
            if pub_meta.get('edicao_relacionada') != f'{slug}-historica':
                problems.append(f'{slug}: consolidada sem edicao_relacionada histórica')
    if problems:
        raise SystemExit('verify falhou:\n' + '\n'.join(problems))
    print('verify ok', flush=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    ing = sub.add_parser('ingest')
    ing.add_argument('dir', type=Path)
    sub.add_parser('build')
    sub.add_parser('verify')
    args = p.parse_args(argv)
    if args.cmd == 'ingest':
        ingest(args.dir)
    elif args.cmd == 'build':
        build()
    elif args.cmd == 'verify':
        verify()


if __name__ == '__main__':
    main()
