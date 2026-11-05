"""Série federal de leis delegadas (LDL 1–13) — issue #67.

Publica as 12 identidades do catálogo do Senado ainda sem arquivo canônico,
a partir das páginas oficiais do Planalto (`ccivil_03/leis/ldl/ldlNN.htm`).
A LDL 7 já publicada permanece no caminho canônico existente; este lote
registra-a no catálogo de reconciliação sem republicá-la.

Reutiliza o conversor HTML→Markdown de `nucleo_licitacoes` sem alterar aquele
gerador. Subcomandos: fetch, ingest, build, verify.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import lzma
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/leis-delegadas'
FONTES_DIR = PROVAS / 'fontes'
MANIFESTO = PROVAS / 'manifesto.json'
FONTES_JSON = PROVAS / 'fontes.json'
CATALOGO_JSON = PROVAS / 'catalogo-reconciliacao.json'
SENADO_LDL_JSON = PROVAS / 'senado-LDL.json'
UNKNOWN = nl.UNKNOWN
PLANALTO = nl.PLANALTO
USER_AGENT = nl.USER_AGENT
CONTRACT_VERSION = nl.CONTRACT_VERSION
LOTE = 'leis-delegadas'
TITLE_PATTERN = r'^LEI DELEGADA'
SENADO_LDL_URL = 'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=LDL'
# Hash da captura de 04/11/2026 citada na #67 (evidência do relatório de auditoria).
SENADO_LDL_SHA256_ISSUE = '844bbf47c712be30b98b57f3c4912945fc5f7ecc58e1381e13ed95f256b271d8'

# Identidades do catálogo Senado (espécie + número + data). LDL 7 já no acervo.
CATALOGO = [
    dict(numero='1', data='1962-09-25', senado_id='572934',
         ementa='Cria cargos de Ministros extraordinários e dá outras providências.'),
    dict(numero='2', data='1962-09-26', senado_id='572935',
         ementa=('Altera a Lei nº 1.506, de 19 de dezembro de 1951, dando-lhe nova '
                 'redação, e adota outras providências.')),
    dict(numero='3', data='1962-09-26', senado_id='572936',
         ementa=('Altera dispositivos do Decreto número 1.102, de 21 de novembro de '
                 '1903, e dá outras providências.')),
    dict(numero='4', data='1962-09-26', senado_id='572937',
         ementa=('Dispõe sôbre a intervenção no domínio econômico para assegurar a '
                 'livre distribuição de produtos necessários ao consumo do povo.')),
    dict(numero='5', data='1962-09-26', senado_id='572938',
         ementa=('Organiza a Superintendência Nacional do Abastecimento (SUNAB) e '
                 'dá outras providências.')),
    dict(numero='6', data='1962-09-26', senado_id='572939',
         ementa=('Autoriza a constituição da Companhia Brasileira de Alimentos e '
                 'dá outras providências.')),
    dict(numero='7', data='1962-09-26', senado_id='572940',
         ementa=('Autoriza a constituição da Companhia Brasileira de Armazenamento '
                 'e dá outras providências.'),
         preexistente=True),
    dict(numero='8', data='1962-10-11', senado_id='572941',
         ementa=('Cria o Fundo Federal Agropecuário (FFAP), no Ministério da '
                 'Agricultura e dá outras providências.')),
    dict(numero='9', data='1962-10-11', senado_id='572942',
         ementa='Reorganiza o Ministério da Agricultura e dá outras providências.'),
    dict(numero='10', data='1962-10-11', senado_id='572943',
         ementa=('Cria a Superintendência do Desenvolvimento da Pesca e dá outras '
                 'providências.')),
    dict(numero='11', data='1962-10-11', senado_id='572944',
         ementa='Cria a Superintendência de Política Agrária (SUPRA) e dá outras providências.'),
    dict(numero='12', data='1992-08-07', senado_id='572945',
         ementa=('Dispõe sobre a instituição de Gratificação de Atividade Militar '
                 'para os servidores militares federais das Forças Armadas.')),
    dict(numero='13', data='1992-08-27', senado_id='572946',
         ementa=('Institui Gratificações de Atividade para os servidores civis do '
                 'Poder Executivo, revê vantagens e dá outras providências.')),
]


def slug_for(item: dict) -> str:
    return f"br-federal-lei-delegada-{item['data']}-{item['numero']}"


def arquivo_for(item: dict) -> str:
    return f"federal/{slug_for(item)}.md"


def fonte_key(numero: str) -> str:
    return f"planalto-ldl{int(numero):02d}"


def planalto_url(numero: str) -> str:
    return f"https://www.planalto.gov.br/ccivil_03/leis/ldl/ldl{int(numero):02d}.htm"


def planalto_file(numero: str) -> str:
    return f"planalto-ldl{int(numero):02d}.htm"


def titulo_for(item: dict) -> str:
    d = datetime.date.fromisoformat(item['data'])
    meses = [
        '', 'JANEIRO', 'FEVEREIRO', 'MARÇO', 'ABRIL', 'MAIO', 'JUNHO',
        'JULHO', 'AGOSTO', 'SETEMBRO', 'OUTUBRO', 'NOVEMBRO', 'DEZEMBRO',
    ]
    return f"LEI DELEGADA Nº {item['numero']}, DE {d.day} DE {meses[d.month]} DE {d.year}"


SOURCES = {
    fonte_key(item['numero']): dict(
        url=planalto_url(item['numero']),
        file=planalto_file(item['numero']),
        orgao=PLANALTO,
        formato='html',
        charset='cp1252',
        numero=item['numero'],
    )
    for item in CATALOGO
    if not item.get('preexistente')
}

DOCS = [
    dict(
        slug=slug_for(item),
        arquivo=arquivo_for(item),
        fonte=fonte_key(item['numero']),
        senado_id=item['senado_id'],
        norma=dict(
            tipo='lei-delegada',
            numero=item['numero'],
            data=item['data'],
            titulo=titulo_for(item),
            ementa=item['ementa'],
            denominacao=None,
        ),
        edicao=dict(tipo='historica', identidade='planalto-ldl', integral=UNKNOWN),
        situacao=dict(valor='nao-informada'),
        title_pattern=TITLE_PATTERN,
    )
    for item in CATALOGO
    if not item.get('preexistente')
]


def now_utc() -> str:
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dou_aviso_from_html(data: bytes, charset: str) -> str | None:
    text = nl.decode(data, charset)
    m = re.search(r'Este texto não substitui.{0,500}?(?:</(?:p|font|small)>|$)', text, flags=re.I | re.S)
    if not m:
        return None
    plain = re.sub(r'<[^>]+>', ' ', m.group(0))
    plain = plain.replace('\xa0', ' ').replace('&nbsp;', ' ')
    plain = re.sub(r'\s+', ' ', plain).strip()
    plain = re.sub(r'\s+\*.*$', '', plain).strip()
    if not plain.lower().startswith('este texto não substitui'):
        return None
    return plain or None


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
            record['utilizavel'] = status == '200' and not looks_like_gateway and len(data) > 500
            if record['utilizavel']:
                record['dou_aviso'] = dou_aviso_from_html(data, spec['charset'])
            else:
                record['motivo'] = f'resposta HTTP {status} sem conteúdo utilizável ({len(data)} bytes)'
        else:
            record.update(utilizavel=False, motivo=proc.stderr.strip()[-500:])
        header_file.unlink(missing_ok=True)
        records[key] = record
        print(f'{key}: {record.get("http_status")} {record.get("bytes")} utilizável={record["utilizavel"]}', flush=True)

    # Catálogo Senado (identidades; não substitui texto integral).
    cat_path = dest / 'senado-LDL.json'
    captured = now_utc()
    proc = subprocess.run([
        'curl', '--silent', '--show-error', '--location', '--http1.1',
        '--proto', '=https', '--proto-redir', '=https',
        '--connect-timeout', '30', '--max-time', '120',
        '--user-agent', USER_AGENT,
        '--write-out', '%{http_code}',
        '--output', str(cat_path), SENADO_LDL_URL,
    ], capture_output=True, text=True)
    cat_rec = dict(url=SENADO_LDL_URL, capturado_em=captured, curl_exit=proc.returncode, user_agent=USER_AGENT)
    if proc.returncode == 0 and cat_path.is_file():
        data = cat_path.read_bytes()
        cat_rec.update(
            http_status=int(proc.stdout.strip() or '0'),
            bytes=len(data),
            sha256=sha256_bytes(data),
            sha256_issue_referencia=SENADO_LDL_SHA256_ISSUE,
            coincidente_com_issue=(sha256_bytes(data) == SENADO_LDL_SHA256_ISSUE),
            utilizavel=proc.stdout.strip() == '200' and len(data) > 100,
        )
    else:
        cat_rec.update(utilizavel=False, motivo=proc.stderr.strip()[-500:])
    records['senado-LDL'] = cat_rec
    print(f'senado-LDL: {cat_rec.get("http_status")} sha={cat_rec.get("sha256", "")[:16]}…', flush=True)
    write_json(dest / 'fetch.json', records)
    return records


def ingest_capture(capture_dir: Path, capturado_em: str | None = None) -> dict:
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
        fontes[key] = record
        print(f'ingest {key}: {record["bytes"]} sha256={record["sha256"][:16]}…', flush=True)

    cat_src = capture_dir / 'senado-LDL.json'
    if not cat_src.is_file():
        # Preferência: cópia auditada com o SHA da #67.
        audited = Path('/home/yorizel/.local/share/codex-artifacts/leis-audit-2026-11-04/senado-LDL.json')
        if audited.is_file():
            cat_src = audited
        else:
            raise SystemExit('senado-LDL.json ausente na captura')
    cat_data = cat_src.read_bytes()
    SENADO_LDL_JSON.write_bytes(cat_data)
    fontes['senado-LDL'] = dict(
        orgao='Senado Federal',
        formato='json',
        url=SENADO_LDL_URL,
        capturado_em=stamp,
        bytes=len(cat_data),
        sha256=sha256_bytes(cat_data),
        sha256_issue_referencia=SENADO_LDL_SHA256_ISSUE,
        coincidente_com_issue=(sha256_bytes(cat_data) == SENADO_LDL_SHA256_ISSUE),
        snapshot=str(SENADO_LDL_JSON.relative_to(ROOT)),
        utilizavel=True,
        papel='catalogo-identidades',
    )
    write_json(FONTES_JSON, fontes)
    return fontes


def load_fontes() -> dict:
    return json.loads(FONTES_JSON.read_text(encoding='utf-8'))


def load_sources_bytes() -> dict:
    return {key: read_snapshot(key) for key in SOURCES}


def edition_note(doc: dict, rec: dict, conv: nl.Converter) -> str:
    lines = [
        (f'**Edição histórica — {rec["orgao"]}.** Fonte: {rec["url"]} '
         f'(capturada em {rec["capturado_em"]}, SHA-256 da fonte `{rec["sha256"]}`, '
         f'SHA-256 do conteúdo sem script de proteção `{rec["sha256_conteudo"]}`). '
         f'Snapshot: `{rec["snapshot"]}`. O acervo não certifica vigência.'),
        ('Página oficial do Planalto (`ldlNN.htm`). Notas, remissões, tabelas e trechos '
         'riscados da página foram preservados literalmente. Não é republicação do DOU '
         'nem consolidação certificada de toda a cadeia de alterações.'),
        ('Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial '
         'mantém riscada; não é dispositivo em vigor. A presença deste arquivo no acervo '
         'não indica vigência.'),
    ]
    if rec.get('dou_aviso'):
        lines.append(rec['dou_aviso'])
    lines.append(
        f'Prova de cobertura fonte→Markdown e reconversão: '
        f'`provas/{LOTE}/reconciliacao-{doc["slug"]}.json`.')
    lines.append(
        f'Identidade do catálogo Senado: id `{doc["senado_id"]}` '
        f'(https://legis.senado.leg.br/norma/{doc["senado_id"]}).')
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
    src = nl.strip_fold(nl.source_text_chars_from_html(data, spec['charset']))
    md_all = nl.strip_fold(nl.md_text_all(body))
    coverage_ok = src == md_all
    arts, order = nl.split_articles(conv.blocks)
    anexos = sum(1 for b in conv.blocks if re.match(r'^ANEXO\b', nl.md_plain(b, True).strip(), re.I))
    note = edition_note(doc, rec, conv)
    if '# ' not in body:
        raise SystemExit(f'{doc["slug"]}: título H1 ausente após conversão')
    title_at = body.index('# ') if body.startswith('# ') else body.index('\n# ') + 1
    title_end = body.index('\n\n', title_at)
    head, rest = body[:title_end], body[title_end + 2:]
    published_body = head + '\n\n' + note + '\n\n' + rest
    if not published_body.endswith('\n'):
        published_body += '\n'

    norma = doc['norma']
    edicao_id = f'{doc["slug"]}@historica-planalto'
    meta = dict(
        id=doc['slug'],
        norma_id=doc['slug'],
        norma_tipo=norma['tipo'],
        norma_numero=norma['numero'],
        norma_data=norma['data'],
        titulo=norma['titulo'],
        esfera='federal',
        edicao_id=edicao_id,
        edicao_tipo='historica',
        edicao_integral=UNKNOWN,
        edicao_relacionada=None,
        fonte_orgao=spec['orgao'],
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
    _, body_only = nl.parse_frontmatter(markdown)
    meta['sha256_markdown'] = nl.sha256(body_only.encode('utf-8'))
    markdown = nl.render_frontmatter(meta) + body_only

    proof = dict(
        documento=doc['slug'],
        fonte_principal=doc['fonte'],
        senado_id=doc['senado_id'],
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
            tipo='lei-delegada',
            numero=norma['numero'],
            data=norma['data'],
            titulo_fonte=norma['titulo'],
            ementa=norma['ementa'],
            edicao=doc['edicao'],
            senado_id=doc['senado_id'],
            senado_url=f'https://legis.senado.leg.br/norma/{doc["senado_id"]}',
        ),
        limites=[
            'Fonte única nesta entrega (Planalto); fonte_conferencia=nenhuma.',
            'Edição histórica da página do Planalto; não é publicação original do DOU isolada.',
            'O acervo não certifica vigência nem reconstrói texto ausente a partir de citações.',
            'Imagens institucionais do cabeçalho foram omitidas; tabelas/notas/riscados da fonte foram preservados.',
            'Catálogo Senado prova identidade; ementa/registro não substituem o Markdown integral.',
        ],
    )
    if not coverage_ok:
        raise SystemExit(f'{doc["slug"]}: cobertura fonte→Markdown falhou')

    entry = dict(
        id=doc['slug'],
        arquivo=doc['arquivo'],
        senado_id=doc['senado_id'],
        norma=norma,
        edicao=dict(
            tipo='historica', integral=UNKNOWN, identidade=doc['edicao']['identidade'],
            edicao_id=edicao_id),
        situacao=doc['situacao'],
        fonte=dict(
            chave=doc['fonte'], orgao=spec['orgao'], url=spec['url'], formato='html',
            capturado_em=rec['capturado_em'], sha256=rec['sha256'],
            sha256_conteudo=rec['sha256_conteudo'], snapshot=rec['snapshot'],
            sha256_snapshot_armazenado=rec['sha256_snapshot_armazenado'],
            dou_aviso=rec.get('dou_aviso'),
        ),
        prova=f'provas/{LOTE}/reconciliacao-{doc["slug"]}.json',
        sha256_markdown=meta['sha256_markdown'],
        estrutura=dict(
            blocos=len(conv.blocks), artigos=len(order),
            tabelas=meta['tabelas'], anexos_no_corpo=anexos,
            imagens_omitidas=meta['imagens_omitidas'],
            texto_riscado=meta['texto_riscado'],
        ),
    )
    return markdown, proof, entry, conv


def build_catalogo_reconciliacao(manifest_docs: list) -> dict:
    publicados = {e['senado_id']: e for e in manifest_docs}
    linhas = []
    for item in CATALOGO:
        slug = slug_for(item)
        path = arquivo_for(item)
        exists = (ROOT / path).is_file()
        if item.get('preexistente'):
            estado = 'presente-preexistente' if exists else 'ausente-inesperado'
            linhas.append(dict(
                senado_id=item['senado_id'],
                tipo='LDL',
                numero=item['numero'],
                data=item['data'],
                norma_nome=f"Lei Delegada nº {item['numero']} de {item['data'][8:10]}/{item['data'][5:7]}/{item['data'][:4]}",
                ementa=item['ementa'],
                url_senado=f'https://legis.senado.leg.br/norma/{item["senado_id"]}',
                url_planalto=planalto_url(item['numero']),
                estado_coleta=estado,
                caminho_publicado=path if exists else None,
                slug=slug,
                neste_lote=False,
                observacao=('Arquivo canônico já existia no acervo antes deste lote; '
                            'não republicado aqui. Texto prévio sem manifesto deste lote.'),
            ))
        else:
            pub = publicados.get(item['senado_id'])
            estado = 'publicado' if pub and exists else 'nao-recuperado'
            linhas.append(dict(
                senado_id=item['senado_id'],
                tipo='LDL',
                numero=item['numero'],
                data=item['data'],
                norma_nome=f"Lei Delegada nº {item['numero']} de {item['data'][8:10]}/{item['data'][5:7]}/{item['data'][:4]}",
                ementa=item['ementa'],
                url_senado=f'https://legis.senado.leg.br/norma/{item["senado_id"]}',
                url_planalto=planalto_url(item['numero']),
                estado_coleta=estado,
                caminho_publicado=path if exists else None,
                slug=slug,
                neste_lote=True,
                prova=(pub or {}).get('prova'),
                sha256_markdown=(pub or {}).get('sha256_markdown'),
            ))
    return dict(
        fonte_catalogo=SENADO_LDL_URL,
        sha256_catalogo_issue=SENADO_LDL_SHA256_ISSUE,
        gerado_em=now_utc(),
        criterio=('Correspondência por espécie LDL + número + dataassinatura; '
                  'IDs do Senado preservados; ementa não substitui íntegra.'),
        totais=dict(
            identidades_catalogo=len(CATALOGO),
            publicadas_neste_lote=sum(1 for L in linhas if L.get('neste_lote') and L['estado_coleta'] == 'publicado'),
            preexistentes=sum(1 for L in linhas if L['estado_coleta'] == 'presente-preexistente'),
            nao_recuperadas=sum(1 for L in linhas if L['estado_coleta'] == 'nao-recuperado'),
        ),
        identidades=linhas,
    )


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
    catalogo = build_catalogo_reconciliacao(manifest_docs)
    # Para o catálogo no compute (antes de write), marque caminhos como previstos.
    for linha in catalogo['identidades']:
        if linha.get('neste_lote'):
            linha['estado_coleta'] = 'publicado'
            linha['caminho_publicado'] = arquivo_for(next(
                i for i in CATALOGO if i['senado_id'] == linha['senado_id']))
    catalogo['totais']['publicadas_neste_lote'] = sum(
        1 for L in catalogo['identidades'] if L.get('neste_lote'))
    catalogo['totais']['nao_recuperadas'] = 0
    manifest = dict(
        contrato_versao=CONTRACT_VERSION,
        lote=LOTE,
        descricao=('Série federal de leis delegadas: 12 identidades do catálogo Senado '
                   'recuperadas integralmente do Planalto; LDL 7 pré-existente registrada '
                   'no catálogo de reconciliação. Issue #67.'),
        gerado_em=now_utc(),
        vigencia_certificada=False,
        documentos=manifest_docs,
        catalogo_reconciliacao=str(CATALOGO_JSON.relative_to(ROOT)),
        limites=[
            'Não altera scripts/nucleo_licitacoes.py nem metadados/nucleo-licitacoes.json.',
            'LDL 7 pré-existente não é republicada neste lote.',
            'Sem segunda fonte oficial de conferência nesta entrega.',
            'Catálogo Senado é denominador de identidades; não prova íntegra nem vigência.',
        ],
    )
    return docs_out, proofs, manifest, catalogo


def write_outputs(docs_out, proofs, manifest, catalogo) -> None:
    for slug, item in docs_out.items():
        path = ROOT / item['arquivo']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['markdown'], encoding='utf-8')
        print(f'wrote {item["arquivo"]} ({len(item["markdown"])} chars)', flush=True)
    for slug, proof in proofs.items():
        write_json(PROVAS / f'reconciliacao-{slug}.json', proof)
    # Recalcula estados do catálogo com arquivos já gravados.
    catalogo = build_catalogo_reconciliacao(manifest['documentos'])
    write_json(CATALOGO_JSON, catalogo)
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
    docs_out, proofs, manifest, catalogo = compute(sources, fontes)
    write_outputs(docs_out, proofs, manifest, catalogo)
    print('build ok', flush=True)


def verify() -> None:
    fontes = load_fontes()
    sources = load_sources_bytes()
    docs_out, proofs, manifest, catalogo = compute(sources, fontes)
    problems = []

    published_manifest = json.loads(MANIFESTO.read_text(encoding='utf-8'))
    if published_manifest.get('lote') != LOTE:
        problems.append('manifesto.lote inesperado')
    if len(published_manifest.get('documentos') or []) != len(DOCS):
        problems.append('manifesto.documentos com cardinalidade divergente')

    published_catalogo = json.loads(CATALOGO_JSON.read_text(encoding='utf-8'))
    if published_catalogo.get('totais', {}).get('identidades_catalogo') != 13:
        problems.append('catálogo de reconciliação não tem 13 identidades')
    if published_catalogo.get('sha256_catalogo_issue') != SENADO_LDL_SHA256_ISSUE:
        problems.append('sha256 do catálogo da issue não preservado')

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
        if meta.get('norma_tipo') != 'lei-delegada':
            problems.append(f'{slug}: norma_tipo deve ser lei-delegada')
        if meta.get('edicao_tipo') != 'historica':
            problems.append(f'{slug}: edicao_tipo deve ser historica')
        if meta.get('fonte_conferencia') != 'nenhuma':
            problems.append(f'{slug}: fonte_conferencia esperada "nenhuma" neste lote')
        proof_path = PROVAS / f'reconciliacao-{slug}.json'
        published_proof = json.loads(proof_path.read_text(encoding='utf-8'))
        recomputed = proofs[slug]
        if not recomputed['cobertura_texto']['equivalente']:
            problems.append(f'{slug}: cobertura fonte→Markdown falsa no recomputo')
        if published_proof.get('cobertura_texto', {}).get('equivalente') is not True:
            problems.append(f'{slug}: prova publicada sem cobertura equivalente')
        if published_proof.get('sha256_fonte_principal') != fontes[doc['fonte']]['sha256']:
            problems.append(f'{slug}: sha256_fonte_principal da prova diverge')
        if 'não certifica vigência' not in body and 'nao certifica vigencia' not in nl.strip_fold(body):
            problems.append(f'{slug}: nota de edição sem aviso de não-certificação de vigência')

        key = doc['fonte']
        raw = sources[key]
        if nl.sha256(raw) != fontes[key]['sha256']:
            problems.append(f'{key}: snapshot sha256 diverge')
        if nl.content_sha256(raw) != fontes[key]['sha256_conteudo']:
            problems.append(f'{key}: content sha256 diverge')

    # Cobertura por identidade do catálogo (aceite #67).
    for item in CATALOGO:
        path = ROOT / arquivo_for(item)
        if not path.is_file():
            problems.append(f'identidade {item["senado_id"]} (LDL {item["numero"]}): arquivo canônico ausente')

    if SENADO_LDL_JSON.is_file():
        cat_sha = sha256_bytes(SENADO_LDL_JSON.read_bytes())
        if fontes.get('senado-LDL', {}).get('sha256') != cat_sha:
            problems.append('senado-LDL.json diverge de fontes.json')
        if cat_sha != SENADO_LDL_SHA256_ISSUE and fontes.get('senado-LDL', {}).get('coincidente_com_issue') is True:
            problems.append('marcação coincidente_com_issue inconsistente')
    else:
        problems.append('senado-LDL.json ausente nas provas')

    if len(DOCS) != 12:
        problems.append('catálogo DOCS deste lote deve ter exatamente 12 publicações novas')

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
