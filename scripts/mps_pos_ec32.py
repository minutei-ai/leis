#!/usr/bin/env python3
"""Medidas provisórias pós-EC 32 — issue #84.

 reconcilia o catálogo Senado (tipo=MPV) com o acervo local para a série
sem reedição a partir de 11/09/2001, coleta íntegras via normas.leg.br e
publica Markdown quando a fonte não traz marcadores `<<ANEXO*>>`/`<<TABELA*>>`.

Marcadores `&lt;&lt;ANEXO&gt;&gt;` no HTML de normas.leg.br são placeholders
oficiais (peças ausentes no HTML), não artefato do conversor. O subcomando
`recover` busca anexos na Câmara via LexML e só publica quando a conversão
`.doc`→HTML→Markdown tem cobertura; PDFs multicoluna ficam documentados.

Não infere conversão/rejeição/eficácia sem vínculo documentado na fonte.
Não funde com o lote pré-EC32 (#95). README agregado fica com o orquestrador.

Subcomandos:
  reconcile   compara catálogo Senado × federal/ → matriz de lacunas
  fetch       baixa metadados+HTML das ausências (limite opcional; retomável)
  recover     recupera anexos Câmara para retidos por marcador
  build       publica Markdown íntegros + registra retenções
  verify      confere snapshots e arquivos publicados
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import lzma
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import nucleo_licitacoes as nl  # noqa: E402
import mps_anexo_recovery as ar  # noqa: E402

PROVAS = ROOT / 'provas' / 'mps-pos-ec32'
FONTES_DIR = PROVAS / 'fontes'
ANEXOS_DIR = PROVAS / 'anexos-camara'
FONTES_JSON = PROVAS / 'fontes.json'
MATRIZ = PROVAS / 'matriz-lote.json'
CATALOGO_SNAP = PROVAS / 'catalogo-senado-mpv-pos.json'
COBERTURA = PROVAS / 'cobertura-conversao.json'
DIAG_MARK = PROVAS / 'diagnostico-marcadores.json'
DISCOVERY = PROVAS / 'descoberta-camara-anexos.json'
RECOVER_RES = PROVAS / 'recuperacao-anexos.json'
FEDERAL = ROOT / 'federal'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
CORTE = datetime.date(2001, 9, 11)
ANEXO_MARK = ar.ANEXO_MARK
# Fonte normas.leg.br: N + ordinal em <sup>o</sup> vira "No"; também "N.", "N°", "No-".
MP_TITLE_RE = r'^MEDIDA PROVIS[ÓO]RIA\s+N[º°oO.\-\s]*\d'
MP_FILE = re.compile(
    r'^br-federal-medida-provisoria-(\d{4})-(\d{2})-(\d{2})-(\d+)(?:-(\d+))?\.md$'
)


def blocks_have_anexo(blocks: list[str]) -> bool:
    """Detecta marcadores <<ANEXO>>/<<TABELA>> no HTML bruto ou após convert_html."""
    for b in blocks:
        plain = nl.md_plain(b, True)
        if ANEXO_MARK.search(plain) or ANEXO_MARK.search(b):
            return True
    return False


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


def parse_date(s: str) -> datetime.date | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def local_post_ec32() -> dict[int, list[dict]]:
    """Mapa numero_base → arquivos locais da série pós-corte sem reedição fundida."""
    out: dict[int, list[dict]] = {}
    for p in FEDERAL.glob('br-federal-medida-provisoria-*.md'):
        m = MP_FILE.match(p.name)
        if not m:
            continue
        y, mo, d, num, reed = m.groups()
        y, mo, d, num = int(y), int(mo), int(d), int(num)
        dt = datetime.date(y, mo, d)
        if dt < CORTE:
            continue
        # reedicao no nome = série histórica (pré-numeração única), fora deste lote
        if reed is not None:
            continue
        out.setdefault(num, []).append({
            'path': p.name,
            'data': dt.isoformat(),
            'numero': num,
        })
    return out


def load_senado_mpv_catalog(force: bool = False) -> list[dict]:
    if CATALOGO_SNAP.exists() and not force:
        return json.loads(CATALOGO_SNAP.read_text())
    url = 'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=MPV'
    data, headers = fetch_url(url)
    payload = json.loads(data.decode('utf-8'))
    docs = payload['ListaDocumento']['documentos']['documento']
    if isinstance(docs, dict):
        docs = [docs]
    write_json(CATALOGO_SNAP, {
        'capturado_em': utc_now(),
        'url': url,
        'sha256': sha256(data),
        'bytes': len(data),
        'status': headers.get('status'),
        'total_registros': len(docs),
        'documentos': docs,
    })
    return json.loads(CATALOGO_SNAP.read_text())


def senado_pos_entries(catalog: dict) -> list[dict]:
    out = []
    for doc in catalog['documentos']:
        tipo = doc.get('tipo') or ''
        # preservar tipo literal; série pós-EC32 operacional = data >= corte e sem reedicao
        reed = doc.get('reedicao')
        if reed not in (None, '', '0', 0):
            continue
        dt = parse_date(doc.get('dataassinatura') or '')
        if dt is None or dt < CORTE:
            continue
        try:
            num = int(str(doc.get('numero')).strip())
        except (TypeError, ValueError):
            continue
        out.append({
            'senado_id': str(doc.get('id')),
            'tipo': tipo,
            'numero': num,
            'reedicao': reed,
            'data': dt.isoformat(),
            'norma': doc.get('norma'),
            'normaNome': doc.get('normaNome'),
            'ementa': doc.get('ementa'),
            'apelido': doc.get('apelido'),
        })
    return out


def cmd_reconcile(force_catalog: bool = False) -> None:
    catalog = load_senado_mpv_catalog(force=force_catalog)
    if isinstance(catalog, list):
        raise SystemExit('catalogo inesperado')
    entries = senado_pos_entries(catalog)
    local = local_post_ec32()
    ausencias = []
    presentes = []
    revisao = []
    for e in sorted(entries, key=lambda x: (x['numero'], x['data'])):
        hits = local.get(e['numero'], [])
        exact = [h for h in hits if h['data'] == e['data']]
        if exact:
            presentes.append({**e, 'arquivo': exact[0]['path'], 'status': 'presente'})
        elif hits:
            revisao.append({
                **e,
                'status': 'mesmo-numero-outra-identidade',
                'arquivos_locais': hits,
            })
        else:
            ausencias.append({**e, 'status': 'ausente-canonico'})
    matriz = {
        'corte_operacional': CORTE.isoformat(),
        'nota_corte': (
            'Corte operacional de descoberta pós-EC 32; não afirma vigência nem '
            'esgota reedições de 2001 anteriores ao corte (lote #95).'
        ),
        'catalogo_sha256': catalog['sha256'],
        'catalogo_total_mpv': catalog['total_registros'],
        'pos_corte_sem_reedicao': len(entries),
        'presentes': len(presentes),
        'ausentes_canonicos': len(ausencias),
        'revisao_mesmo_numero': len(revisao),
        'ausencias': ausencias,
        'revisao': revisao,
        # presentes omitidos por tamanho; contagem acima basta
    }
    write_json(MATRIZ, matriz)
    write_json(PROVAS / 'ausencias.json', ausencias)
    write_json(PROVAS / 'revisao-mesmo-numero.json', revisao)
    print(
        f"pos={len(entries)} presentes={len(presentes)} "
        f"ausentes={len(ausencias)} revisao={len(revisao)}"
    )


def normas_detail(date: str, numero: int) -> dict | None:
    urn = f'urn:lex:br:federal:medida.provisoria:{date};{numero}'
    url = (
        'https://normas.leg.br/api/public/normas?urn='
        + urllib.parse.quote(urn)
        + '&tipo_documento=maior-detalhe'
    )
    data, _ = fetch_url(url)
    if not data or len(data) < 100:
        return None
    try:
        return json.loads(data.decode('utf-8'))
    except json.JSONDecodeError:
        return None


def content_url_from_detail(detail: dict) -> tuple[str | None, dict | None]:
    enc = detail.get('encoding')
    encs = enc if isinstance(enc, list) else ([enc] if isinstance(enc, dict) else [])
    for e in encs:
        if not isinstance(e, dict):
            continue
        cu = e.get('contentUrl')
        if not cu:
            continue
        if '/api/binario/' in cu and '/api/public/binario/' not in cu:
            cu = cu.replace('/api/binario/', '/api/public/binario/')
        return cu, e
    return None, None


def coverage_safe(blocks: list[str], markdown_body: str) -> bool:
    from_blocks = nl.strip_fold('\n'.join(nl.md_plain(b, True) for b in blocks))
    produced = nl.strip_fold(re.sub(r'^# ', '', nl.md_plain(markdown_body, True), flags=re.M))
    return from_blocks == produced


def cmd_fetch(limit: int | None, only_numbers: list[int] | None) -> None:
    if not MATRIZ.exists():
        cmd_reconcile()
    matriz = json.loads(MATRIZ.read_text())
    ausencias = matriz['ausencias']
    FONTES_DIR.mkdir(parents=True, exist_ok=True)
    fontes = json.loads(FONTES_JSON.read_text()) if FONTES_JSON.exists() else {}
    if only_numbers:
        want = set(only_numbers)
        ausencias = [a for a in ausencias if a['numero'] in want]
    else:
        # retomada: não rebaixar o que já tem snapshot
        ausencias = [
            a for a in ausencias
            if f"br-federal-medida-provisoria-{a['data']}-{a['numero']}" not in fontes
        ]
    if limit is not None:
        ausencias = ausencias[:limit]
    resultados = list(
        json.loads((PROVAS / 'fetch-resultados.json').read_text())
        if (PROVAS / 'fetch-resultados.json').exists() else []
    )
    resultados = [r for r in resultados if r.get('id') in fontes]
    for a in ausencias:
        num, date = a['numero'], a['data']
        key = f'br-federal-medida-provisoria-{date}-{num}'
        print('fetch', key, flush=True)
        detail = normas_detail(date, num)
        if not detail or not detail.get('legislationIdentifier'):
            resultados.append({**a, 'id': key, 'status': 'metadados-indisponiveis'})
            continue
        # vínculos documentados na fonte (sem inferir)
        gerado = detail.get('legislationGeneratedProcess')
        vinculos = []
        if isinstance(gerado, dict):
            vinculos.append({
                'tipo': 'legislationGeneratedProcess',
                'name': gerado.get('name'),
                'id': gerado.get('@id'),
            })
        cu, enc_meta = content_url_from_detail(detail)
        if not cu:
            resultados.append({
                **a, 'id': key, 'status': 'sem-contentUrl',
                'urn': detail.get('legislationIdentifier'),
                'vinculos_fonte': vinculos,
            })
            continue
        try:
            html, headers = fetch_url(cu)
        except Exception as exc:  # noqa: BLE001
            resultados.append({
                **a, 'id': key, 'status': 'falha-download',
                'erro': str(exc), 'contentUrl': cu,
                'urn': detail.get('legislationIdentifier'),
                'vinculos_fonte': vinculos,
            })
            continue
        ctype = (headers.get('content-type') or '').lower()
        if 'html' not in ctype and not html.lstrip().startswith((b'<', b'\xef\xbb\xbf<')):
            resultados.append({
                **a, 'id': key, 'status': 'formato-nao-html',
                'content_type': ctype, 'bytes': len(html),
                'urn': detail.get('legislationIdentifier'),
                'vinculos_fonte': vinculos,
            })
            continue
        text_probe = html.decode('utf-8', 'replace')
        snap = FONTES_DIR / f'{key}.html.xz'
        snap.write_bytes(lzma.compress(html))
        meta_path = FONTES_DIR / f'{key}.dados.json.xz'
        meta_path.write_bytes(lzma.compress(json.dumps(detail, ensure_ascii=False).encode()))
        has_mark = ar.html_has_anexo_mark(text_probe)
        status = 'retido-marcador-anexo-tabela' if has_mark else 'capturado'
        fontes[key] = {
            'url': cu,
            'sha256_fonte': sha256(html),
            'bytes': len(html),
            'capturado_em': utc_now(),
            'snapshot': str(snap.relative_to(ROOT)),
            'dados_snapshot': str(meta_path.relative_to(ROOT)),
            'status': status,
            'urn': detail.get('legislationIdentifier'),
            'vinculos_fonte': vinculos,
            'headline': detail.get('headline'),
            'diagnostico_marcador': ar.diagnose_marker_in_html(text_probe) if has_mark else None,
            'encoding_meta': {
                k: enc_meta.get(k) for k in (
                    'version', 'additionalType', 'datePublished', 'name', 'encodingFormat'
                ) if enc_meta
            },
        }
        resultados.append({
            **a, 'id': key, 'status': status,
            'urn': detail.get('legislationIdentifier'),
            'vinculos_fonte': vinculos,
        })
        print(' ', status, key, len(html))
    write_json(FONTES_JSON, fontes)
    write_json(PROVAS / 'fetch-resultados.json', resultados)
    print('fontes', len(fontes), 'resultados', len(resultados))


def build_mp_markdown(key: str, rec: dict, anexo_groups: list[list[str]] | None = None,
                      anexo_meta: list[dict] | None = None) -> dict:
    raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
    if sha256(raw) != rec['sha256_fonte']:
        raise ValueError(f'hash snapshot {key}')
    text = raw.decode('utf-8', 'replace')
    conv = nl.convert_html(raw, 'utf-8', rec['url'])
    blocks = list(conv.blocks)
    anexos_no_corpo = 0
    recuperado = False
    if anexo_groups:
        spliced = ar.splice_anexo_blocks(blocks, anexo_groups, nl.md_plain)
        if spliced is None:
            return {
                'id': key,
                'status': 'retido-ambiguidade-anexo',
                'n_marcadores': sum(
                    1 for b in blocks
                    if ar.is_anexo_marker_block(nl.md_plain(b, True).strip())
                ),
                'n_anexos': len(anexo_groups),
            }
        blocks = spliced
        anexos_no_corpo = len(anexo_groups)
        recuperado = True
    elif ar.html_has_anexo_mark(text) or blocks_have_anexo(blocks):
        return {
            'id': key,
            'status': 'retido-marcador-anexo-tabela',
            'origem': 'pos-conversao' if not ar.html_has_anexo_mark(text) else 'html-oficial',
            'diagnostico_marcador': ar.diagnose_marker_in_html(text),
        }
    # drop control marker block if present
    blocks = [
        b for b in blocks
        if not re.match(r'^###MPV-', nl.md_plain(b, True).strip())
    ]
    if blocks_have_anexo(blocks):
        return {'id': key, 'status': 'retido-marcador-anexo-tabela', 'origem': 'pos-splice'}
    title_re = MP_TITLE_RE
    try:
        body = nl.blocks_to_markdown(blocks, title_re)
    except ValueError:
        return {'id': key, 'status': 'retido-titulo-nao-encontrado',
                'blocos_amostra': [nl.md_plain(b, True)[:80] for b in blocks[:5]]}
    if not coverage_safe(blocks, body):
        raise ValueError(f'cobertura falhou {key}')
    # identity from key
    m = re.match(r'br-federal-medida-provisoria-(\d{4}-\d{2}-\d{2})-(\d+)$', key)
    date, num = m.group(1), m.group(2)
    vinculos = rec.get('vinculos_fonte') or []
    vinculo_txt = 'nenhum vínculo de conversão/geração informado na captura.'
    if vinculos:
        parts = [f"{v.get('name') or ''} ({v.get('id') or ''})".strip() for v in vinculos]
        vinculo_txt = 'Vínculos declarados na fonte (sem inferência de vigência): ' + '; '.join(parts)
    anexo_nota = ''
    if recuperado and anexo_meta:
        linhas = []
        for a in anexo_meta:
            linhas.append(
                f"`{a.get('url')}` (SHA-256 `{a.get('sha256')}`, "
                f"snapshot `{a.get('snapshot_rel', a.get('snapshot'))}`)"
            )
        anexo_nota = (
            ">\n> Anexos recuperados da Câmara dos Deputados (ficha LexML→norma-pe), "
            "convertidos de `.doc` via LibreOffice→HTML→Markdown, substituindo o "
            "placeholder oficial de anexo/tabela do HTML normas.leg.br:\n> - "
            + "\n> - ".join(linhas) + "\n"
        )
    note = (
        f"> **Medida Provisória nº {int(num)} de {date} — publicação original (normas.leg.br/Senado)**"
        f"{' com anexos Câmara' if recuperado else ''}.** "
        f"Fonte corpo: {rec['url']} (capturada em {rec['capturado_em']}, SHA-256 `{rec['sha256_fonte']}`). "
        f"Snapshot: `{rec['snapshot']}`. O acervo não certifica vigência.\n"
        f">\n"
        f"> Série pós-EC 32/2001 (numeração contínua sem reedição). Não fundir com MPs/reedições "
        f"anteriores a 11/09/2001 (issue #95).\n"
        f">\n"
        f"> {vinculo_txt}\n"
        f"{anexo_nota}"
        f">\n"
        f"> Situação parlamentar, conversão em lei, rejeição ou perda de eficácia exigem evidência "
        f"própria; ausência de arquivo ou tipo de catálogo não as substitui.\n"
    )
    sha_md = sha256(body.encode('utf-8'))
    fm_fields = {
        'id': key,
        'norma_id': key,
        'norma_tipo': 'medida-provisoria',
        'norma_numero': str(int(num)),
        'norma_data': date,
        'titulo': rec.get('headline') or f'Medida Provisória nº {int(num)} de {date}',
        'esfera': 'federal',
        'edicao_id': f'{key}@publicacao-original-senado'
        + ('+anexos-camara' if recuperado else ''),
        'edicao_tipo': 'historica',
        'edicao_integral': True,
        'edicao_relacionada': 'nenhuma',
        'fonte_orgao': 'Senado Federal / Portal das Normas'
        + (' + Câmara dos Deputados (anexos)' if recuperado else ''),
        'fonte_url': rec['url'],
        'fonte_formato': 'html' + ('+doc' if recuperado else ''),
        'fonte_conferencia': 'camara-anexos-doc' if recuperado else 'nenhuma',
        'capturado_em': rec['capturado_em'],
        'sha256_fonte': rec['sha256_fonte'],
        'situacao': 'nao-informada',
        'situacao_fundamento': 'desconhecido',
        'vigencia_certificada': False,
        'texto_riscado': False,
        'anexos_no_corpo': anexos_no_corpo,
        'tabelas': sum(1 for b in blocks if '<table' in b.lower()),
        'imagens_omitidas': len(getattr(conv, 'images', []) or []),
        'efeitos_diferidos': 'preservados-nas-notas-do-texto',
        'sha256_markdown': sha_md,
        'manifesto': 'provas/mps-pos-ec32/matriz-publicacao.json',
        'contrato_versao': 1,
        'serie_historica': 'medida-provisoria-pos-ec32',
        'urn': rec.get('urn') or f'urn:lex:br:federal:medida.provisoria:{date};{num}',
    }
    fm = '---\n' + '\n'.join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in fm_fields.items()) + '\n---\n'
    doc = fm + '\n<!-- nota-edicao:inicio -->\n\n' + note + '\n<!-- nota-edicao:fim -->\n\n' + body
    out = FEDERAL / f'{key}.md'
    out.write_text(doc)
    return {
        'id': key,
        'status': 'publicado',
        'path': str(out.relative_to(ROOT)),
        'sha256_markdown_corpo': sha_md,
        'sha256_arquivo': sha256(doc.encode()),
        'blocos': len(blocks),
        'vinculos_fonte': vinculos,
        'anexos_recuperados': anexos_no_corpo,
        'recuperado_camara': recuperado,
    }


def cmd_recover(limit: int | None, only_numbers: list[int] | None, doc_only: bool = True) -> None:
    """Descobre e baixa anexos Câmara; publica quando .doc converte com cobertura."""
    if not FONTES_JSON.exists():
        raise SystemExit('fetch/build antes de recover')
    fontes = json.loads(FONTES_JSON.read_text())
    pub_path = PROVAS / 'matriz-publicacao.json'
    if not pub_path.exists():
        cmd_build()
    pub = json.loads(pub_path.read_text())
    retidos = [
        r for r in pub.get('retidos', [])
        if r.get('status') == 'retido-marcador-anexo-tabela'
    ]
    if only_numbers:
        want = set(only_numbers)
        retidos = [r for r in retidos if int(r['id'].rsplit('-', 1)[-1]) in want]
    if limit is not None:
        retidos = retidos[:limit]

    ANEXOS_DIR.mkdir(parents=True, exist_ok=True)
    discovery = json.loads(DISCOVERY.read_text()) if DISCOVERY.exists() else {}
    recover_log = json.loads(RECOVER_RES.read_text()) if RECOVER_RES.exists() else {}
    diag = json.loads(DIAG_MARK.read_text()) if DIAG_MARK.exists() else {}
    publicados_novos = []
    ainda_retidos = []

    for item in retidos:
        key = item['id']
        rec = fontes.get(key)
        if not rec or 'snapshot' not in rec:
            ainda_retidos.append({**item, 'status': 'sem-fonte-local'})
            continue
        raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
        text = raw.decode('utf-8', 'replace')
        diag[key] = ar.diagnose_marker_in_html(text)
        print('recover', key, flush=True)
        disc = discovery.get(key) or ar.discover_camara_norma(key)
        discovery[key] = {k: v for k, v in disc.items() if k != 'anexos' or True}
        if disc.get('status') not in ('ok',) or not disc.get('anexos'):
            ainda_retidos.append({
                **item,
                'status': 'retido-sem-anexo-camara',
                'descoberta': disc.get('status'),
                'diagnostico_marcador': diag[key],
                'bloqueios': {
                    'planalto': 'conexão resetada neste host (2026-11-04); não inferir ausência',
                    'camara': disc.get('status'),
                },
            })
            recover_log[key] = {'status': 'sem-anexo-camara', 'descoberta': disc}
            print('  SEM anexo Câmara', disc.get('status'))
            continue

        anexos_urls = list(disc['anexos'])
        if doc_only:
            anexos_urls = [u for u in anexos_urls if u.lower().endswith(('.doc', '.docx'))]
        if not anexos_urls:
            pdfs = [u for u in disc['anexos'] if u.lower().endswith('.pdf')]
            # ainda captura PDFs para prova, sem publicar
            pdf_meta = []
            with tempfile.TemporaryDirectory() as td:
                td_path = Path(td)
                for i, url in enumerate(pdfs):
                    name = url.rstrip('/').rsplit('/', 1)[-1]
                    dest = ANEXOS_DIR / f'{key}.{i}.{name}.xz'
                    try:
                        meta = ar.download_and_store_anexo(url, dest, td_path / f'w{i}')
                    except Exception as exc:  # noqa: BLE001
                        pdf_meta.append({'url': url, 'erro': str(exc)})
                        continue
                    rel = str(dest.relative_to(ROOT))
                    pdf_meta.append({
                        'url': url, 'sha256': meta['sha256'], 'bytes': meta['bytes'],
                        'snapshot': rel, 'publicavel': False, 'bloqueio': meta.get('bloqueio'),
                    })
            ainda_retidos.append({
                **item,
                'status': 'retido-anexo-pdf-layout-pendente',
                'diagnostico_marcador': diag[key],
                'anexos_pdf': pdf_meta,
                'norma_camara': disc.get('norma'),
            })
            recover_log[key] = {'status': 'pdf-pendente', 'anexos': pdf_meta, 'descoberta': disc}
            print('  PDF pendente', len(pdf_meta))
            continue

        groups: list[list[str]] = []
        meta_list: list[dict] = []
        try:
            with tempfile.TemporaryDirectory() as td:
                td_path = Path(td)
                for i, url in enumerate(anexos_urls):
                    name = url.rstrip('/').rsplit('/', 1)[-1]
                    dest = ANEXOS_DIR / f'{key}.{i}.{name}.xz'
                    meta = ar.download_and_store_anexo(url, dest, td_path / f'w{i}')
                    if not meta.get('publicavel') or not meta.get('html_convertido'):
                        raise RuntimeError(meta.get('bloqueio') or 'anexo não publicável')
                    conv = nl.convert_html(meta['html_convertido'], 'utf-8', url)
                    groups.append(conv.blocks)
                    rel = str(dest.relative_to(ROOT))
                    meta_list.append({
                        'url': url,
                        'sha256': meta['sha256'],
                        'bytes': meta['bytes'],
                        'html_sha256': meta.get('html_sha256'),
                        'snapshot_rel': rel,
                        'conversao': meta.get('conversao'),
                    })
            info = build_mp_markdown(key, rec, anexo_groups=groups, anexo_meta=meta_list)
        except Exception as exc:  # noqa: BLE001
            ainda_retidos.append({
                **item, 'status': 'falha-recuperacao', 'erro': str(exc),
                'diagnostico_marcador': diag[key], 'norma_camara': disc.get('norma'),
            })
            recover_log[key] = {'status': 'falha', 'erro': str(exc), 'descoberta': disc}
            print('  FAIL', exc)
            continue

        if info['status'] != 'publicado':
            ainda_retidos.append({**info, 'diagnostico_marcador': diag[key]})
            recover_log[key] = {'status': info['status'], 'info': info, 'anexos': meta_list}
            print('  RETIDO', info['status'])
        else:
            publicados_novos.append(info)
            fontes[key] = {
                **rec,
                'status': 'capturado-com-anexos-camara',
                'anexos_camara': meta_list,
                'norma_camara': disc.get('norma'),
            }
            recover_log[key] = {'status': 'publicado', 'anexos': meta_list, 'path': info['path']}
            print('  PUB', key, 'anexos', len(meta_list))

    # reúne publicados anteriores + novos; retidos = não recuperados nesta rodada
    # + retidos de outros status que não entraram no filtro
    pub_anteriores = [
        p for p in pub.get('publicados', [])
        if p['id'] not in {x['id'] for x in publicados_novos}
    ]
    outros_retidos = [
        r for r in pub.get('retidos', [])
        if r.get('status') != 'retido-marcador-anexo-tabela'
        or (
            only_numbers is None
            and limit is None
            and r['id'] not in {x.get('id') for x in ainda_retidos}
            and r['id'] not in {x['id'] for x in publicados_novos}
            and r['id'] not in {x['id'] for x in retidos}
        )
    ]
    # quando recover parcial (limit/numbers), preservar retidos não visitados
    visitados = {r['id'] for r in retidos}
    preservados = [
        r for r in pub.get('retidos', [])
        if r['id'] not in visitados and r['id'] not in {x['id'] for x in publicados_novos}
    ]
    all_pub = pub_anteriores + publicados_novos
    all_ret = ainda_retidos + preservados
    # dedupe retidos by id preferring newer
    seen = set()
    ret_final = []
    for r in all_ret:
        if r['id'] in seen:
            continue
        seen.add(r['id'])
        ret_final.append(r)

    write_json(FONTES_JSON, fontes)
    write_json(DISCOVERY, discovery)
    write_json(RECOVER_RES, recover_log)
    write_json(DIAG_MARK, diag)
    write_json(PROVAS / 'matriz-publicacao.json', {
        'publicados': all_pub,
        'retidos': ret_final,
        'n_publicados': len(all_pub),
        'n_retidos': len(ret_final),
        'recuperados_camara_nesta_rodada': len(publicados_novos),
    })
    write_json(COBERTURA, {
        p['id']: {'cobertura': True, 'sha256_markdown_corpo': p['sha256_markdown_corpo']}
        for p in all_pub
    })
    _write_limites(all_pub, ret_final)
    _write_readme()
    print(
        f"recover: publicados_novos={len(publicados_novos)} "
        f"retidos={len(ret_final)} total_pub={len(all_pub)}"
    )


def _write_limites(pub: list, retidos: list) -> None:
    from collections import Counter
    matriz = json.loads(MATRIZ.read_text()) if MATRIZ.exists() else {}
    write_json(PROVAS / 'limites.json', {
        'issue': 84,
        'matriz_resumo': {
            'ausentes_canonicos': matriz.get('ausentes_canonicos'),
            'catalogo_sha256': matriz.get('catalogo_sha256'),
            'catalogo_total_mpv': matriz.get('catalogo_total_mpv'),
            'corte_operacional': matriz.get('corte_operacional', CORTE.isoformat()),
            'nota_corte': matriz.get('nota_corte'),
            'pos_corte_sem_reedicao': matriz.get('pos_corte_sem_reedicao'),
            'presentes': matriz.get('presentes'),
            'revisao_mesmo_numero': matriz.get('revisao_mesmo_numero'),
        },
        'n_publicados': len(pub),
        'n_retidos': len(retidos),
        'recuperados_camara': sum(1 for p in pub if p.get('recuperado_camara') or p.get('anexos_recuperados')),
        'nota': (
            'Marcadores <<ANEXO>>/<<TABELA>> no HTML normas.leg.br são placeholders oficiais '
            '(&lt;&lt;ANEXO&gt;&gt;). Recuperação via LexML→Câmara .doc; PDFs DOU multicoluna '
            'permanecem retidos sem publicar íntegra falsa. Planalto indisponível neste host '
            'não implica ausência da norma.'
        ),
        'regras': [
            'Não inferir vigência/completude de presença de arquivo ou HTTP.',
            '<<ANEXO>>/<<TABELA>> na conversão retêm a norma até peça oficial recuperada.',
            'PDF Câmara capturado fica em provas/anexos-camara/ sem virar Markdown até layout confiável.',
            'Provas privadas fora do repo público; divergências literais preservadas.',
        ],
        'retidos_por_status': dict(Counter(r.get('status') for r in retidos)),
    })


def _write_readme() -> None:
    (PROVAS / 'README.md').write_text(
        '# Provas — MPs pós-EC 32 (issue #84)\n\n'
        'Reconcilia o catálogo `tipo=MPV` do Senado com o acervo, coleta íntegras via '
        'normas.leg.br e recupera anexos da Câmara quando o HTML traz placeholder '
        '`<<ANEXO>>`/`<<TABELA>>` (peça real ausente no HTML, não bug do conversor).\n\n'
        '```bash\n'
        'python3 scripts/mps_pos_ec32.py reconcile\n'
        'python3 scripts/mps_pos_ec32.py fetch          # retomável\n'
        'python3 scripts/mps_pos_ec32.py recover        # anexos .doc Câmara\n'
        'python3 scripts/mps_pos_ec32.py build\n'
        'python3 scripts/mps_pos_ec32.py verify\n'
        '```\n\n'
        'Corte operacional: data ≥ 11/09/2001 e sem campo `reedicao`. Lote histórico: #95.\n'
        'Ver `limites.json`, `diagnostico-marcadores.json`, `descoberta-camara-anexos.json`.\n'
    )


def cmd_build() -> None:
    if not FONTES_JSON.exists():
        raise SystemExit('fetch antes de build')
    fontes = json.loads(FONTES_JSON.read_text())
    pub = []
    retidos = []
    for key, rec in sorted(fontes.items()):
        status = rec.get('status')
        if status == 'capturado-com-anexos-camara':
            # republica com anexos já baixados
            groups: list[list[str]] = []
            meta = rec.get('anexos_camara') or []
            try:
                with tempfile.TemporaryDirectory() as td:
                    td_path = Path(td)
                    for i, a in enumerate(meta):
                        snap = ROOT / a['snapshot_rel']
                        data = lzma.decompress(snap.read_bytes())
                        if sha256(data) != a['sha256']:
                            raise ValueError(f'hash anexo {a["url"]}')
                        name = a['url'].rstrip('/').rsplit('/', 1)[-1]
                        raw_path = td_path / name
                        raw_path.write_bytes(data)
                        html_path = ar.convert_office_to_html(raw_path, td_path / f'h{i}')
                        conv = nl.convert_html(html_path.read_bytes(), 'utf-8', a['url'])
                        groups.append(conv.blocks)
                info = build_mp_markdown(key, rec, anexo_groups=groups, anexo_meta=meta)
            except Exception as exc:  # noqa: BLE001
                retidos.append({'id': key, 'status': 'falha-reconversao-anexo', 'erro': str(exc)})
                print('FAIL', key, exc)
                continue
        elif status in ('retido-marcador-anexo-tabela',):
            # tenta build simples (vai reter) — recover é o caminho
            try:
                info = build_mp_markdown(key, rec)
            except Exception as exc:  # noqa: BLE001
                retidos.append({'id': key, 'status': 'falha-conversao', 'erro': str(exc)})
                continue
        elif status != 'capturado':
            retidos.append({'id': key, 'status': status, 'urn': rec.get('urn'),
                            'vinculos_fonte': rec.get('vinculos_fonte')})
            continue
        else:
            try:
                info = build_mp_markdown(key, rec)
            except Exception as exc:  # noqa: BLE001
                retidos.append({'id': key, 'status': 'falha-conversao', 'erro': str(exc)})
                print('FAIL', key, exc)
                continue
        if info['status'] != 'publicado':
            retidos.append(info)
            print('RETIDO', key, info['status'])
        else:
            pub.append(info)
            print('PUB', key)
    write_json(PROVAS / 'matriz-publicacao.json', {
        'publicados': pub,
        'retidos': retidos,
        'n_publicados': len(pub),
        'n_retidos': len(retidos),
    })
    write_json(COBERTURA, {
        p['id']: {'cobertura': True, 'sha256_markdown_corpo': p['sha256_markdown_corpo']}
        for p in pub
    })
    _write_limites(pub, retidos)
    _write_readme()
    print('publicados', len(pub), 'retidos', len(retidos))


def cmd_verify() -> None:
    pub = json.loads((PROVAS / 'matriz-publicacao.json').read_text())
    fontes = json.loads(FONTES_JSON.read_text())
    errors = []
    for item in pub['publicados']:
        path = ROOT / item['path']
        if not path.exists():
            errors.append(f'ausente {item["id"]}')
            continue
        text = path.read_text()
        if 'medida-provisoria-pos-ec32' not in text:
            errors.append(f'{item["id"]}: serie ausente')
        if 'vigencia_certificada' not in text:
            errors.append(f'{item["id"]}: vigencia_certificada ausente')
        if '<<ANEXO>>' in text or '<<TABELA>>' in text:
            errors.append(f'{item["id"]}: marcador residual')
        rec = fontes[item['id']]
        raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
        if sha256(raw) != rec['sha256_fonte']:
            errors.append(f'{item["id"]}: snapshot')
        for a in rec.get('anexos_camara') or []:
            snap = ROOT / a['snapshot_rel']
            if not snap.exists():
                errors.append(f'{item["id"]}: anexo ausente {a["snapshot_rel"]}')
                continue
            if sha256(lzma.decompress(snap.read_bytes())) != a['sha256']:
                errors.append(f'{item["id"]}: hash anexo {a["url"]}')
        m = re.search(r'<!-- nota-edicao:fim -->\n\n([\s\S]+)\Z', text)
        if not m:
            errors.append(f'{item["id"]}: corpo')
            continue
        if sha256(m.group(1).encode()) != item['sha256_markdown_corpo']:
            errors.append(f'{item["id"]}: sha corpo')
        print('OK', item['id'])
    if errors:
        print('FALHAS:')
        for e in errors:
            print(' -', e)
        raise SystemExit(1)
    print('verify ok', len(pub['publicados']))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['reconcile', 'fetch', 'recover', 'build', 'verify'])
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--numbers', default=None, help='lista CSV de números')
    ap.add_argument('--refresh-catalog', action='store_true')
    ap.add_argument(
        '--include-pdf', action='store_true',
        help='em recover, tenta também PDF (ainda não publica layout duvidoso)',
    )
    args = ap.parse_args()
    if args.cmd == 'reconcile':
        cmd_reconcile(force_catalog=args.refresh_catalog)
    elif args.cmd == 'fetch':
        nums = [int(x) for x in args.numbers.split(',')] if args.numbers else None
        cmd_fetch(limit=args.limit, only_numbers=nums)
    elif args.cmd == 'recover':
        nums = [int(x) for x in args.numbers.split(',')] if args.numbers else None
        cmd_recover(limit=args.limit, only_numbers=nums, doc_only=not args.include_pdf)
    elif args.cmd == 'build':
        cmd_build()
    else:
        cmd_verify()


if __name__ == '__main__':
    main()
