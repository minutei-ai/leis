"""Publicação do CTN (Lei 5.172/1966) e da Lei do SUS (8.080/1990).

Lote independente do núcleo de licitações: reutiliza o conversor HTML→Markdown
de `nucleo_licitacoes` sem alterar o gerador nem o manifesto daquele núcleo.

Subcomandos:
  fetch DIR   captura as fontes oficiais e grava DIR/fetch.json
  build       reconverte snapshots → Markdown, manifesto e provas
  verify      confere offline Markdown, hashes e cobertura fonte→Markdown
"""
from __future__ import annotations

import argparse
import datetime
import json
import lzma
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/nucleo-federal-ctn-sus'
FONTES_DIR = PROVAS / 'fontes'
MANIFESTO = PROVAS / 'manifesto.json'
FONTES_JSON = PROVAS / 'fontes.json'
UNKNOWN = nl.UNKNOWN
PLANALTO = nl.PLANALTO
USER_AGENT = nl.USER_AGENT
CONTRACT_VERSION = nl.CONTRACT_VERSION

SOURCES = {
    'planalto-l5172compilado': dict(
        url='https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm',
        file='planalto-l5172compilado.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-l8080': dict(
        url='https://www.planalto.gov.br/ccivil_03/leis/l8080.htm',
        file='planalto-l8080.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
}

DOCS = [
    dict(
        slug='br-federal-lei-1966-10-25-5172',
        arquivo='federal/br-federal-lei-1966-10-25-5172.md',
        fonte='planalto-l5172compilado',
        norma=dict(
            tipo='lei', numero='5172', data='1966-10-25',
            titulo='LEI Nº 5.172, DE 25 DE OUTUBRO DE 1966',
            ementa=('Dispõe sobre o Sistema Tributário Nacional e institui normas gerais de '
                    'direito tributário aplicáveis à União, Estados e Municípios.'),
            denominacao='Código Tributário Nacional'),
        edicao=dict(tipo='consolidada', identidade='compilado-planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'^LEI(?: COMPLEMENTAR)? N',
    ),
    dict(
        slug='br-federal-lei-1990-09-19-8080',
        arquivo='federal/br-federal-lei-1990-09-19-8080.md',
        fonte='planalto-l8080',
        norma=dict(
            tipo='lei', numero='8080', data='1990-09-19',
            titulo='LEI Nº 8.080, DE 19 DE SETEMBRO DE 1990',
            ementa=('Dispõe sobre as condições para a promoção, proteção e recuperação da saúde, '
                    'a organização e o funcionamento dos serviços correspondentes e dá outras '
                    'providências.')),
        edicao=dict(tipo='consolidada', identidade='planalto', integral=True),
        situacao=dict(valor='nao-informada'),
        title_pattern=r'^LEI(?: COMPLEMENTAR)? N',
    ),
]


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def snapshot_path(key: str) -> Path:
    return FONTES_DIR / (SOURCES[key]['file'] + '.xz')


def read_snapshot(key: str) -> bytes:
    return lzma.decompress(snapshot_path(key).read_bytes())


def write_snapshot(key: str, data: bytes) -> None:
    path = snapshot_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + '\n', encoding='utf-8')


def dou_aviso_from_html(data: bytes, charset: str) -> str | None:
    """Extrai o aviso DOU/retificação do rodapé do Planalto, tolerando quebras e tags no HTML."""
    text = nl.decode(data, charset)
    m = re.search(r'Este texto não substitui.{0,400}?(?:</(?:p|font|small)>|$)', text, flags=re.I | re.S)
    if not m:
        return None
    plain = re.sub(r'<[^>]+>', ' ', m.group(0))
    plain = re.sub(r'\s+', ' ', plain).strip()
    # Normalizar para a forma canônica usada nas notas.
    m2 = re.search(
        r'Este texto não substitui o publicado no DOU de\s+(\d{1,2}\.\d{1,2}\.\d{4})'
        r'(?:\s+e\s+retificado em\s+(\d{1,2}\.\d{1,2}\.\d{4}))?',
        plain, flags=re.I)
    if not m2:
        return plain or None
    aviso = f'Este texto não substitui o publicado no DOU de {m2.group(1)}'
    if m2.group(2):
        aviso += f' e retificado em {m2.group(2)}'
    return aviso


def fetch(dest: Path) -> dict:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, spec in SOURCES.items():
        target = dest / spec['file']
        header_file = dest / (spec['file'] + '.headers')
        captured = now_utc()
        proc = subprocess.run([
            'curl', '--silent', '--show-error', '--location', '--http1.1',
            '--proto', '=https', '--proto-redir', '=https',
            '--connect-timeout', '30', '--max-time', '180',
            '--max-filesize', str(64 * 1024 * 1024),
            '--user-agent', USER_AGENT, '--dump-header', str(header_file),
            '--write-out', '%{http_code} %{url_effective}',
            '--output', str(target), spec['url'],
        ], capture_output=True, text=True)
        record = dict(url=spec['url'], capturado_em=captured, curl_exit=proc.returncode, user_agent=USER_AGENT)
        if proc.returncode == 0:
            status, _, effective = proc.stdout.partition(' ')
            record.update(http_status=int(status), url_final=effective)
            data = target.read_bytes()
            record.update(bytes=len(data), sha256=nl.sha256(data), sha256_conteudo=nl.content_sha256(data))
            raw_headers = header_file.read_bytes().decode('latin-1').replace('\r\n', '\n')
            final_block = [b for b in raw_headers.split('\n\n') if b.strip()][-1:] or ['']
            for line in final_block[0].splitlines():
                name, _, value = line.partition(':')
                if name.lower() in ('last-modified', 'etag', 'content-type', 'date'):
                    record['cabecalho_' + name.lower().replace('-', '_')] = value.strip()
            looks_like_gateway = b'504 Gateway Time-out' in data[:400] or b'<title>5' in data[:400]
            record['utilizavel'] = status == '200' and not looks_like_gateway and len(data) > 1000
            if record['utilizavel']:
                record['dou_aviso'] = dou_aviso_from_html(data, spec['charset'])
            else:
                record['motivo'] = f'resposta HTTP {status} sem conteúdo utilizável ({len(data)} bytes)'
        else:
            record.update(utilizavel=False, motivo=proc.stderr.strip()[-500:])
        header_file.unlink(missing_ok=True)
        records[key] = record
        print(f'{key}: {record.get("http_status")} {record.get("bytes")} utilizável={record["utilizavel"]}', flush=True)
    write_json(dest / 'fetch.json', records)
    return records


def ingest_capture(capture_dir: Path, capturado_em: str | None = None) -> dict:
    """Grava snapshots + fontes.json a partir de um diretório de captura já baixado."""
    capture_dir = Path(capture_dir)
    fontes = {}
    stamp = capturado_em
    if stamp is None:
        stamp_file = capture_dir / 'capturado_em.txt'
        stamp = stamp_file.read_text(encoding='utf-8').strip() if stamp_file.exists() else now_utc()
    for key, spec in SOURCES.items():
        raw_path = capture_dir / spec['file']
        if not raw_path.is_file():
            raise SystemExit(f'captura ausente: {raw_path}')
        data = raw_path.read_bytes()
        write_snapshot(key, data)
        headers_path = capture_dir / (spec['file'] + '.headers')
        record = dict(
            orgao=spec['orgao'], formato=spec['formato'], url=spec['url'],
            capturado_em=stamp, user_agent=USER_AGENT, http_status=200,
            url_final=spec['url'], bytes=len(data), sha256=nl.sha256(data),
            sha256_conteudo=nl.content_sha256(data), utilizavel=True,
            dou_aviso=dou_aviso_from_html(data, spec['charset']),
            snapshot=str(snapshot_path(key).relative_to(ROOT)),
            sha256_snapshot_armazenado=nl.sha256(snapshot_path(key).read_bytes()),
            charset=spec['charset'],
        )
        if headers_path.is_file():
            raw_headers = headers_path.read_bytes().decode('latin-1').replace('\r\n', '\n')
            final_block = [b for b in raw_headers.split('\n\n') if b.strip()][-1:] or ['']
            for line in final_block[0].splitlines():
                name, _, value = line.partition(':')
                if name.lower() in ('last-modified', 'etag', 'content-type', 'date'):
                    record['cabecalho_' + name.lower().replace('-', '_')] = value.strip()
            # Prefer HTTP Date from response when present for correlation; keep capturado_em as batch stamp.
        fontes[key] = record
        print(f'ingest {key}: {record["bytes"]} sha256={record["sha256"][:16]}…', flush=True)
    write_json(FONTES_JSON, fontes)
    return fontes


def load_fontes() -> dict:
    return json.loads(FONTES_JSON.read_text(encoding='utf-8'))


def load_sources_bytes() -> dict:
    return {key: read_snapshot(key) for key in SOURCES}


def edition_note(doc: dict, rec: dict, conv: nl.Converter) -> str:
    norma = doc['norma']
    lines = [
        (f'**Edição consolidada — {rec["orgao"]}.** Fonte: {rec["url"]} '
         f'(capturada em {rec["capturado_em"]}, SHA-256 da fonte `{rec["sha256"]}`, '
         f'SHA-256 do conteúdo sem script de proteção `{rec["sha256_conteudo"]}`). '
         f'Snapshot: `{rec["snapshot"]}`. O acervo não certifica vigência.'),
    ]
    if doc['slug'].endswith('5172'):
        lines.append(
            'Edição **compilada** do Planalto (`l5172compilado.htm`), denominada Código Tributário Nacional '
            'na própria fonte. Notas de alteração, remissões, tabelas e trechos riscados da página foram '
            'preservados literalmente.')
    else:
        lines.append(
            'Edição publicada pelo Planalto (`l8080.htm`). Notas de alteração, remissões, mensagem de veto '
            'e trechos riscados da página foram preservados literalmente.')
    lines.append(
        'Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial mantém riscada; '
        'não é dispositivo em vigor. A presença deste arquivo no acervo não indica vigência.')
    if rec.get('dou_aviso'):
        lines.append(rec['dou_aviso'])
    lines.append(
        f'Prova de cobertura fonte→Markdown e reconversão: '
        f'`provas/nucleo-federal-ctn-sus/reconciliacao-{doc["slug"]}.json`.')
    if conv.images:
        lines.append(
            f'{len(conv.images)} imagem(ns) institucional(is) do cabeçalho da página foram omitidas do '
            'Markdown (brasão/logotipo sem texto jurídico).')
    if conv.stats['tabelas_markdown'] or conv.stats['tabelas_html']:
        n = conv.stats['tabelas_markdown'] + conv.stats['tabelas_html']
        lines.append(f'{n} tabela(s) da fonte foram convertidas para Markdown/`<table>` no corpo.')
    return nl.note_block(lines)


def build_document(doc: dict, data: bytes, rec: dict) -> tuple[str, dict, dict, nl.Converter]:
    spec = SOURCES[doc['fonte']]
    conv = nl.convert_html(data, spec['charset'], spec['url'])
    body = nl.blocks_to_markdown(conv.blocks, doc['title_pattern'])
    # Cobertura independente: texto bruto da fonte == texto do Markdown (após normalização).
    src = nl.strip_fold(nl.source_text_chars_from_html(data, spec['charset']))
    md_all = nl.strip_fold(nl.md_text_all(body))
    coverage_ok = src == md_all
    arts, order = nl.split_articles(conv.blocks)
    anexos = sum(1 for b in conv.blocks if re.match(r'^ANEXO\b', nl.md_plain(b, True).strip(), re.I))
    note = edition_note(doc, rec, conv)
    # Inserir nota editorial imediatamente após o H1 (pode haver preâmbulo institucional antes).
    if '# ' not in body:
        raise SystemExit(f'{doc["slug"]}: título H1 ausente após conversão')
    title_at = body.index('# ') if body.startswith('# ') else body.index('\n# ') + 1
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
        edicao_relacionada=None,
        fonte_orgao=PLANALTO,
        fonte_url=spec['url'],
        fonte_formato='html',
        fonte_conferencia='nenhuma',
        capturado_em=rec['capturado_em'],
        sha256_fonte=rec['sha256'],
        situacao=doc['situacao']['valor'],
        situacao_fundamento=UNKNOWN,
        vigencia_certificada=False,
        texto_riscado=conv.stats['trechos_riscados'] > 0,
        anexos_no_corpo=anexos,
        tabelas=conv.stats['tabelas_markdown'] + conv.stats['tabelas_html'],
        imagens_omitidas=len(conv.images),
        efeitos_diferidos='preservados-nas-notas-do-texto',
        sha256_markdown=nl.sha256(published_body.encode('utf-8')),
        manifesto=str(MANIFESTO.relative_to(ROOT)),
        contrato_versao=CONTRACT_VERSION,
    )
    errors = nl.validate_meta(meta, doc['slug'])
    if errors:
        raise SystemExit('metadados inválidos:\n' + '\n'.join(errors))

    markdown = nl.render_frontmatter(meta) + published_body
    # Recompute sha over body after frontmatter is known to match parse convention:
    # sha256_markdown = hash of everything after frontmatter (inclui nota).
    _, body_only = nl.parse_frontmatter(markdown)
    meta['sha256_markdown'] = nl.sha256(body_only.encode('utf-8'))
    markdown = nl.render_frontmatter(meta) + body_only

    proof = dict(
        documento=doc['slug'],
        fonte_principal=doc['fonte'],
        sha256_fonte_principal=rec['sha256'],
        sha256_conteudo=rec['sha256_conteudo'],
        capturado_em=rec['capturado_em'],
        url=spec['url'],
        snapshot=rec['snapshot'],
        sha256_snapshot_armazenado=rec['sha256_snapshot_armazenado'],
        fontes_conferencia=[],
        cobertura_texto=dict(
            descricao=('texto integral da página da fonte (sem imagens) == texto do Markdown publicado '
                       '(corpo convertido, sem nota de edição), após normalização'),
            equivalente=coverage_ok,
            caracteres_normalizados_fonte=len(src),
            caracteres_normalizados_markdown=len(md_all),
            metodo='strip_fold(source_text_chars_from_html) == strip_fold(md_text_all(body_convertido))',
        ),
        conversao=dict(
            **conv.stats,
            imagens=conv.images,
            tabelas=conv.tables,
            blocos=len(conv.blocks),
            artigos=len(order),
            primeiros_artigos=order[:5],
            ultimos_artigos=order[-5:],
            titulos_e_capitulos=len(nl.headings(nl.main_body_blocks(conv.blocks))),
        ),
        identidade=dict(
            norma_id=doc['slug'],
            numero=norma['numero'],
            data=norma['data'],
            titulo_fonte=norma['titulo'],
            ementa=norma['ementa'],
            denominacao=norma.get('denominacao'),
            edicao=doc['edicao'],
        ),
        limites=[
            'Fonte única (Planalto); fonte_conferencia=nenhuma — sem conferência artigo a artigo com segunda fonte oficial nesta entrega.',
            'Edição consolidada/compilada do Planalto; não é publicação original do DOU nem edição histórica isolada.',
            'O acervo não certifica vigência nem reconstrói texto ausente a partir de citações.',
            'Imagens institucionais do cabeçalho foram omitidas; tabelas/notas/riscados da fonte foram preservados.',
        ],
    )
    if not coverage_ok:
        raise SystemExit(f'{doc["slug"]}: cobertura fonte→Markdown falhou')

    entry = dict(
        id=doc['slug'],
        arquivo=doc['arquivo'],
        norma=norma,
        edicao=dict(tipo='consolidada', integral=True, identidade=doc['edicao']['identidade'], edicao_id=edicao_id),
        situacao=doc['situacao'],
        fonte=dict(
            chave=doc['fonte'], orgao=PLANALTO, url=spec['url'], formato='html',
            capturado_em=rec['capturado_em'], sha256=rec['sha256'],
            sha256_conteudo=rec['sha256_conteudo'], snapshot=rec['snapshot'],
            sha256_snapshot_armazenado=rec['sha256_snapshot_armazenado'],
            dou_aviso=rec.get('dou_aviso'),
        ),
        prova=f'provas/nucleo-federal-ctn-sus/reconciliacao-{doc["slug"]}.json',
        sha256_markdown=meta['sha256_markdown'],
        estrutura=dict(
            blocos=len(conv.blocks), artigos=len(order),
            tabelas=meta['tabelas'], anexos_no_corpo=anexos,
            imagens_omitidas=meta['imagens_omitidas'],
            texto_riscado=meta['texto_riscado'],
        ),
    )
    return markdown, proof, entry, conv


def compute(sources: dict, fontes: dict):
    docs_out = {}
    proofs = {}
    manifest_docs = []
    for doc in DOCS:
        key = doc['fonte']
        markdown, proof, entry, _conv = build_document(doc, sources[key], fontes[key])
        docs_out[doc['slug']] = dict(arquivo=doc['arquivo'], markdown=markdown, meta=nl.parse_frontmatter(markdown)[0])
        proofs[doc['slug']] = proof
        manifest_docs.append(entry)
    manifest = dict(
        contrato_versao=CONTRACT_VERSION,
        lote='nucleo-federal-ctn-sus',
        descricao=('CTN (Lei 5.172/1966, edição compilada do Planalto) e Lei 8.080/1990 (organização do SUS), '
                   'recuperados integralmente das fontes oficiais do Planalto. Lote independente do núcleo de licitações.'),
        gerado_em=now_utc(),
        vigencia_certificada=False,
        documentos=manifest_docs,
        limites=[
            'Não altera scripts/nucleo_licitacoes.py nem metadados/nucleo-licitacoes.json.',
            'Não atualiza README agregado nem matriz global de cobertura (integração pelo orquestrador).',
            'CDC/ECA/LGPD/benefícios/Maria da Penha ficam fora deste lote.',
            'Sem segunda fonte oficial de conferência nesta entrega.',
        ],
    )
    return docs_out, proofs, manifest


def write_outputs(docs_out, proofs, manifest) -> None:
    for slug, item in docs_out.items():
        path = ROOT / item['arquivo']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['markdown'], encoding='utf-8')
        print(f'wrote {item["arquivo"]} ({len(item["markdown"])} chars)', flush=True)
    for slug, proof in proofs.items():
        write_json(PROVAS / f'reconciliacao-{slug}.json', proof)
    write_json(MANIFESTO, manifest)
    write_json(PROVAS / 'ferramentas.json', nl.tool_versions())


def build() -> None:
    fontes = load_fontes()
    sources = load_sources_bytes()
    for key in SOURCES:
        if key not in fontes or not fontes[key].get('utilizavel', True):
            raise SystemExit(f'fonte {key} ausente ou inutilizável em {FONTES_JSON}')
        snap = snapshot_path(key)
        if not snap.is_file():
            raise SystemExit(f'snapshot ausente: {snap}')
        raw = read_snapshot(key)
        if nl.sha256(raw) != fontes[key]['sha256']:
            raise SystemExit(f'{key}: sha256 do snapshot diverge de fontes.json')
        if nl.sha256(snap.read_bytes()) != fontes[key]['sha256_snapshot_armazenado']:
            raise SystemExit(f'{key}: sha256_snapshot_armazenado diverge')
    docs_out, proofs, manifest = compute(sources, fontes)
    write_outputs(docs_out, proofs, manifest)
    print('build ok', flush=True)


def verify() -> None:
    fontes = load_fontes()
    sources = load_sources_bytes()
    docs_out, proofs, manifest = compute(sources, fontes)
    problems = []

    published_manifest = json.loads(MANIFESTO.read_text(encoding='utf-8'))
    if published_manifest.get('lote') != 'nucleo-federal-ctn-sus':
        problems.append('manifesto.lote inesperado')
    if len(published_manifest.get('documentos') or []) != len(DOCS):
        problems.append('manifesto.documentos com cardinalidade divergente')

    for doc in DOCS:
        slug = doc['slug']
        path = ROOT / doc['arquivo']
        if not path.is_file():
            problems.append(f'{slug}: arquivo ausente')
            continue
        text = path.read_text(encoding='utf-8')
        meta, body = nl.parse_frontmatter(text)
        expected_md = docs_out[slug]['markdown']
        if text != expected_md:
            problems.append(f'{slug}: Markdown publicado diverge da reconversão integral')
        if meta.get('sha256_markdown') != nl.sha256(body.encode('utf-8')):
            problems.append(f'{slug}: sha256_markdown não confere com o corpo')
        if meta.get('vigencia_certificada') is not False:
            problems.append(f'{slug}: vigencia_certificada deve ser false')
        if meta.get('fonte_conferencia') != 'nenhuma':
            problems.append(f'{slug}: fonte_conferencia esperada "nenhuma" neste lote')
        proof_path = PROVAS / f'reconciliacao-{slug}.json'
        published_proof = json.loads(proof_path.read_text(encoding='utf-8'))
        # Campos voláteis de conversão (imagens com URLs) devem bater após recomputo.
        recomputed = proofs[slug]
        if not recomputed['cobertura_texto']['equivalente']:
            problems.append(f'{slug}: cobertura fonte→Markdown falsa no recomputo')
        if published_proof.get('cobertura_texto', {}).get('equivalente') is not True:
            problems.append(f'{slug}: prova publicada sem cobertura equivalente')
        if published_proof.get('sha256_fonte_principal') != fontes[doc['fonte']]['sha256']:
            problems.append(f'{slug}: sha256_fonte_principal da prova diverge')
        # Identidade canônica no corpo
        if doc['norma']['titulo'].split(',')[0] not in body and doc['norma']['titulo'] not in body:
            # H1 may omit trailing period variants; require number + year markers
            if doc['norma']['numero'] not in re.sub(r'\D', '', body[:500]):
                problems.append(f'{slug}: identidade numérica não encontrada no corpo')
        # Ausência de certificação de vigência na nota
        if 'não certifica vigência' not in body and 'nao certifica vigencia' not in nl.strip_fold(body):
            problems.append(f'{slug}: nota de edição sem aviso de não-certificação de vigência')

        # Snapshot integrity
        key = doc['fonte']
        raw = sources[key]
        if nl.sha256(raw) != fontes[key]['sha256']:
            problems.append(f'{key}: snapshot sha256 diverge')
        if nl.content_sha256(raw) != fontes[key]['sha256_conteudo']:
            problems.append(f'{key}: content sha256 diverge')

    # Confirm these IDs are exactly the two intended and no CDC/ECA/LGPD paths touched by this verify.
    expected_slugs = {d['slug'] for d in DOCS}
    if expected_slugs != {'br-federal-lei-1966-10-25-5172', 'br-federal-lei-1990-09-19-8080'}:
        problems.append('catálogo DOCS deste lote foi alterado além de CTN/SUS')

    if problems:
        raise SystemExit('verify falhou:\n- ' + '\n- '.join(problems))
    print('verify ok', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    p_fetch = sub.add_parser('fetch', help='captura fontes oficiais')
    p_fetch.add_argument('dir', type=Path)
    p_ingest = sub.add_parser('ingest', help='grava snapshots a partir de captura local')
    p_ingest.add_argument('dir', type=Path)
    p_ingest.add_argument('--capturado-em', default=None)
    sub.add_parser('build', help='reconverte e escreve Markdown/provas')
    sub.add_parser('verify', help='confere offline')
    args = parser.parse_args(argv)
    if args.cmd == 'fetch':
        fetch(args.dir)
    elif args.cmd == 'ingest':
        ingest_capture(args.dir, args.capturado_em)
    elif args.cmd == 'build':
        build()
    elif args.cmd == 'verify':
        verify()
    else:
        parser.error(args.cmd)


if __name__ == '__main__':
    main()
