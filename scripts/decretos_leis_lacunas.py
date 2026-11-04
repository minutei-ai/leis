#!/usr/bin/env python3
"""Lacunas de decretos-leis — issue #96.

 reconcilia catálogo Senado tipo=DEL (inclui subtipo DEL-mpv) com o acervo.
Preserva ambiguidades de número/data/série em revisão; não reescreve arquivos
existentes para forçar encaixe.

Subcomandos: reconcile | fetch | recover | build | verify
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

PROVAS = ROOT / 'provas' / 'decretos-leis-lacunas'
FONTES_DIR = PROVAS / 'fontes'
ANEXOS_DIR = PROVAS / 'anexos-camara'
FONTES_JSON = PROVAS / 'fontes.json'
MATRIZ = PROVAS / 'matriz-lote.json'
CATALOGO = PROVAS / 'catalogo-senado-del.json'
DISCOVERY = PROVAS / 'descoberta-camara-anexos.json'
RECOVER_RES = PROVAS / 'recuperacao-anexos.json'
DIAG_MARK = PROVAS / 'diagnostico-marcadores.json'
FEDERAL = ROOT / 'federal'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
ANEXO_MARK = ar.ANEXO_MARK
# Epígrafe literal pode ser "DECRETO-LEI" ou, em divergência da fonte, "Decreto nº …"
# com corpo que se autodenomina Decreto-lei — preservar a redação literal.
DEL_TITLE_RE = (
    r'^(?:DECRETO[\s\-‑]?LEI|Decreto[\s\-‑]?[Ll]ei|DECRETO LEI|'
    r'Decreto)\s+n'
)
DEL_FILE = re.compile(r'^br-federal-decreto-lei-(\d{4})-(\d{2})-(\d{2})-(\d+)\.md$')


def blocks_have_anexo(blocks: list[str]) -> bool:
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


def parse_date(s: str):
    if not s:
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


def local_by_numero() -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for p in FEDERAL.glob('br-federal-decreto-lei-*.md'):
        m = DEL_FILE.match(p.name)
        if not m:
            continue
        y, mo, d, num = map(int, m.groups())
        out.setdefault(num, []).append({'path': p.name, 'data': f'{y:04d}-{mo:02d}-{d:02d}', 'numero': num})
    return out


def load_catalog(force=False) -> dict:
    if CATALOGO.exists() and not force:
        return json.loads(CATALOGO.read_text())
    url = 'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=DEL'
    data, headers = fetch_url(url)
    payload = json.loads(data.decode('utf-8'))
    docs = payload['ListaDocumento']['documentos']['documento']
    if isinstance(docs, dict):
        docs = [docs]
    obj = {
        'capturado_em': utc_now(), 'url': url, 'sha256': sha256(data),
        'bytes': len(data), 'status': headers.get('status'),
        'total_registros': len(docs), 'documentos': docs,
        'sha256_conferencia_issue': 'd8dd952923a609fe964938da7623622ff0bff94f8279daa2fa5ad14e3ce0b94d',
    }
    obj['sha256_bate_com_issue'] = obj['sha256'] == obj['sha256_conferencia_issue']
    write_json(CATALOGO, obj)
    return obj


def cmd_reconcile(force=False) -> None:
    PROVAS.mkdir(parents=True, exist_ok=True)
    cat = load_catalog(force=force)
    local = local_by_numero()
    ausentes, presentes, revisao = [], [], []
    subtipos = {}
    for doc in cat['documentos']:
        tipo = doc.get('tipo') or 'DEL'
        subtipos[tipo] = subtipos.get(tipo, 0) + 1
        dt = parse_date(doc.get('dataassinatura') or '')
        try:
            num = int(str(doc.get('numero')).strip())
        except (TypeError, ValueError):
            revisao.append({'senado_id': doc.get('id'), 'motivo': 'numero-invalido', 'tipo': tipo})
            continue
        if dt is None:
            revisao.append({'senado_id': doc.get('id'), 'numero': num, 'motivo': 'data-ausente', 'tipo': tipo})
            continue
        date = dt.isoformat()
        fid = f'br-federal-decreto-lei-{date}-{num}'
        entry = {
            'senado_id': str(doc.get('id')), 'tipo': tipo, 'numero': num, 'data': date,
            'id': fid, 'norma': doc.get('norma'), 'normaNome': doc.get('normaNome'),
        }
        hits = local.get(num, [])
        exact = [h for h in hits if h['data'] == date]
        if exact:
            presentes.append(entry)
        elif hits:
            revisao.append({**entry, 'motivo': 'mesmo-numero-outra-identidade', 'arquivos_locais': hits})
        else:
            ausentes.append(entry)
    write_json(MATRIZ, {
        'catalogo_sha256': cat['sha256'],
        'sha256_bate_com_issue': cat.get('sha256_bate_com_issue'),
        'total_registros': cat['total_registros'],
        'subtipos': subtipos,
        'presentes': len(presentes),
        'ausentes_canonicos': len(ausentes),
        'revisao_mesmo_numero': len(revisao),
        'nota': (
            'Preservar DEL vs DEL-mpv. Não fundir documentos nem atribuir efeitos só pelo rótulo. '
            'Número coincidente exige revisão, não correção automática de arquivo existente.'
        ),
    })
    write_json(PROVAS / 'ausencias.json', ausentes)
    write_json(PROVAS / 'revisao-mesmo-numero.json', revisao)
    (PROVAS / 'README.md').write_text(
        '# Provas — Decretos-leis lacunas (#96)\n\n'
        '```bash\n'
        'python3 scripts/decretos_leis_lacunas.py reconcile\n'
        'python3 scripts/decretos_leis_lacunas.py fetch --limit 40\n'
        'python3 scripts/decretos_leis_lacunas.py build\n'
        'python3 scripts/decretos_leis_lacunas.py verify\n'
        '```\n'
    )
    print(f"ausentes={len(ausentes)} presentes={len(presentes)} revisao={len(revisao)} subtipos={subtipos}")


def urn_for(date: str, numero: int) -> str:
    return f'urn:lex:br:federal:decreto.lei:{date};{numero}'


def normas_detail(urn: str):
    url = 'https://normas.leg.br/api/public/normas?urn=' + urllib.parse.quote(urn) + '&tipo_documento=maior-detalhe'
    data, _ = fetch_url(url)
    if not data or len(data) < 100:
        return None
    try:
        return json.loads(data.decode('utf-8'))
    except json.JSONDecodeError:
        return None


def content_url(detail: dict):
    enc = detail.get('encoding')
    encs = enc if isinstance(enc, list) else ([enc] if isinstance(enc, dict) else [])
    for e in encs:
        if isinstance(e, dict) and e.get('contentUrl'):
            cu = e['contentUrl']
            if '/api/binario/' in cu and '/api/public/binario/' not in cu:
                cu = cu.replace('/api/binario/', '/api/public/binario/')
            return cu
    return None


def coverage_safe(blocks, body):
    from_blocks = nl.strip_fold('\n'.join(nl.md_plain(b, True) for b in blocks))
    produced = nl.strip_fold(re.sub(r'^# ', '', nl.md_plain(body, True), flags=re.M))
    return from_blocks == produced


def cmd_fetch(limit=None) -> None:
    if not (PROVAS / 'ausencias.json').exists():
        cmd_reconcile()
    ausencias = json.loads((PROVAS / 'ausencias.json').read_text())
    FONTES_DIR.mkdir(parents=True, exist_ok=True)
    fontes = json.loads(FONTES_JSON.read_text()) if FONTES_JSON.exists() else {}
    pending = [a for a in ausencias if a['id'] not in fontes]
    if limit is not None:
        pending = pending[:limit]
    results = list(json.loads((PROVAS / 'fetch-resultados.json').read_text()) if (PROVAS / 'fetch-resultados.json').exists() else [])
    results = [r for r in results if r.get('id') in fontes]
    for a in pending:
        key = a['id']
        urn = urn_for(a['data'], a['numero'])
        print('fetch', key, a.get('tipo'), flush=True)
        detail = normas_detail(urn)
        if not detail or not detail.get('legislationIdentifier'):
            results.append({**a, 'status': 'metadados-indisponiveis', 'urn_tentada': urn})
            continue
        cu = content_url(detail)
        if not cu:
            results.append({**a, 'status': 'sem-contentUrl', 'urn': detail.get('legislationIdentifier')})
            continue
        try:
            html, headers = fetch_url(cu)
        except Exception as exc:  # noqa: BLE001
            results.append({**a, 'status': 'falha-download', 'erro': str(exc)})
            continue
        ctype = (headers.get('content-type') or '').lower()
        if 'html' not in ctype and not html.lstrip().startswith((b'<', b'\xef\xbb\xbf<')):
            results.append({**a, 'status': 'formato-nao-html', 'content_type': ctype})
            continue
        text = html.decode('utf-8', 'replace')
        has_mark = ar.html_has_anexo_mark(text)
        status = 'retido-marcador-anexo-tabela' if has_mark else 'capturado'
        snap = FONTES_DIR / f'{key}.html.xz'
        snap.write_bytes(lzma.compress(html))
        fontes[key] = {
            'url': cu, 'sha256_fonte': sha256(html), 'bytes': len(html),
            'capturado_em': utc_now(), 'snapshot': str(snap.relative_to(ROOT)),
            'status': status, 'urn': detail.get('legislationIdentifier'),
            'headline': detail.get('headline'), 'tipo': a.get('tipo'),
            'numero': a['numero'], 'data': a['data'],
            'diagnostico_marcador': ar.diagnose_marker_in_html(text) if has_mark else None,
        }
        results.append({**a, 'status': status})
        print(' ', status, key, len(html))
    write_json(FONTES_JSON, fontes)
    write_json(PROVAS / 'fetch-resultados.json', results)


def build_one(key, rec, anexo_groups=None, anexo_meta=None):
    raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
    if sha256(raw) != rec['sha256_fonte']:
        raise ValueError('hash')
    text = raw.decode('utf-8', 'replace')
    conv = nl.convert_html(raw, 'utf-8', rec['url'])
    blocks = list(conv.blocks)
    recuperado = False
    anexos_no_corpo = 0
    if anexo_groups:
        spliced = ar.splice_anexo_blocks(blocks, anexo_groups, nl.md_plain)
        if spliced is None:
            return {'id': key, 'status': 'retido-ambiguidade-anexo'}
        blocks = spliced
        recuperado = True
        anexos_no_corpo = len(anexo_groups)
    elif ar.html_has_anexo_mark(text) or blocks_have_anexo(blocks):
        return {
            'id': key, 'status': 'retido-marcador-anexo-tabela',
            'origem': 'html-oficial' if ar.html_has_anexo_mark(text) else 'pos-conversao',
            'diagnostico_marcador': ar.diagnose_marker_in_html(text),
        }
    blocks = [b for b in blocks if not re.match(r'^###DEL-', nl.md_plain(b, True).strip())]
    if blocks_have_anexo(blocks):
        return {'id': key, 'status': 'retido-marcador-anexo-tabela', 'origem': 'pos-splice'}
    try:
        body = nl.blocks_to_markdown(blocks, DEL_TITLE_RE)
    except ValueError:
        return {'id': key, 'status': 'retido-titulo-nao-encontrado',
                'blocos_amostra': [nl.md_plain(b, True)[:80] for b in blocks[:5]]}
    if not coverage_safe(blocks, body):
        if recuperado:
            raise ValueError('cobertura')
        body = nl.blocks_to_markdown(conv.blocks, DEL_TITLE_RE)
        if not coverage_safe(conv.blocks, body):
            raise ValueError('cobertura')
        blocks = conv.blocks
    h1 = next((ln[2:].strip() for ln in body.splitlines() if ln.startswith('# ')), '')
    epigrafe_nota = ''
    if h1 and re.match(r'^Decreto\s+n', h1, re.I) and not re.search(r'decreto[\s\-‑]?lei', h1, re.I):
        epigrafe_nota = (
            f">\n> Divergência literal da fonte: epígrafe «{h1}» enquanto o catálogo Senado "
            f"e o corpo tratam a norma como decreto-lei; a redação da epígrafe é preservada "
            f"sem correção editorial.\n"
        )
    anexo_nota = ''
    if recuperado and anexo_meta:
        linhas = [
            f"`{a.get('url')}` (SHA-256 `{a.get('sha256')}`, snapshot `{a.get('snapshot_rel')}`)"
            for a in anexo_meta
        ]
        anexo_nota = (
            ">\n> Anexos recuperados da Câmara (LexML→norma-pe), `.doc`→HTML→Markdown:\n> - "
            + "\n> - ".join(linhas) + "\n"
        )
    note = (
        f"> **Decreto-Lei nº {rec['numero']} de {rec['data']} — publicação original"
        f"{' com anexos Câmara' if recuperado else ''}.** "
        f"Fonte: {rec['url']} (capturada em {rec['capturado_em']}, SHA-256 `{rec['sha256_fonte']}`). "
        f"Snapshot: `{rec['snapshot']}`. O acervo não certifica vigência.\n"
        f">\n"
        f"> Tipo de catálogo Senado: `{rec.get('tipo')}`. Subtipo `DEL-mpv` (se aplicável) é preservado; "
        f"vínculos de conversão em MPV exigem evidência própria, sem fusão de documentos.\n"
        f"{epigrafe_nota}{anexo_nota}"
        f">\n"
        f"> Filtros #70 / rastreador #83.\n"
    )
    sha_md = sha256(body.encode())
    fields = {
        'id': key, 'norma_id': key, 'norma_tipo': 'decreto-lei',
        'norma_numero': str(rec['numero']), 'norma_data': rec['data'],
        'titulo': rec.get('headline') or key, 'esfera': 'federal',
        'edicao_id': f'{key}@publicacao-original-senado' + ('+anexos-camara' if recuperado else ''),
        'edicao_tipo': 'historica',
        'edicao_integral': True, 'edicao_relacionada': 'nenhuma',
        'fonte_orgao': 'Senado Federal / Portal das Normas'
        + (' + Câmara dos Deputados (anexos)' if recuperado else ''),
        'fonte_url': rec['url'],
        'fonte_formato': 'html' + ('+doc' if recuperado else ''),
        'fonte_conferencia': 'camara-anexos-doc' if recuperado else 'nenhuma',
        'capturado_em': rec['capturado_em'], 'sha256_fonte': rec['sha256_fonte'],
        'situacao': 'nao-informada', 'situacao_fundamento': 'desconhecido',
        'vigencia_certificada': False, 'texto_riscado': False,
        'anexos_no_corpo': anexos_no_corpo,
        'tabelas': sum(1 for b in blocks if '<table' in b.lower()),
        'imagens_omitidas': len(getattr(conv, 'images', []) or []),
        'efeitos_diferidos': 'preservados-nas-notas-do-texto',
        'sha256_markdown': sha_md, 'manifesto': 'provas/decretos-leis-lacunas/matriz-publicacao.json',
        'contrato_versao': 1, 'serie_historica': 'decreto-lei',
        'urn': rec.get('urn'), 'tipo_catalogo': rec.get('tipo'),
    }
    fm = '---\n' + '\n'.join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in fields.items()) + '\n---\n'
    doc = fm + '\n<!-- nota-edicao:inicio -->\n\n' + note + '\n<!-- nota-edicao:fim -->\n\n' + body
    (FEDERAL / f'{key}.md').write_text(doc)
    return {
        'id': key, 'status': 'publicado', 'path': f'federal/{key}.md',
        'sha256_markdown_corpo': sha_md, 'tipo': rec.get('tipo'),
        'recuperado_camara': recuperado, 'anexos_recuperados': anexos_no_corpo,
    }


def _capture_pdf_snapshots(key: str, pdf_urls: list[str]) -> list[dict]:
    """Baixa PDFs Câmara para prova; nunca marca publicável."""
    pdf_meta: list[dict] = []
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        for i, url in enumerate(pdf_urls):
            name = url.rstrip('/').rsplit('/', 1)[-1]
            dest = ANEXOS_DIR / f'{key}.{i}.{name}.xz'
            try:
                meta = ar.download_and_store_anexo(url, dest, td_path / f'w{i}')
            except Exception as exc:  # noqa: BLE001
                pdf_meta.append({'url': url, 'erro': str(exc)})
                continue
            pdf_meta.append({
                'url': url,
                'sha256': meta['sha256'],
                'bytes': meta['bytes'],
                'snapshot': str(dest.relative_to(ROOT)),
                'publicavel': False,
                'bloqueio': meta.get('bloqueio') or (
                    'PDF da Câmara capturado; conversão tipográfica/multicoluna '
                    'CLBR/DOU não certifica literalidade — não publicar como íntegra '
                    'até reconversão confiável.'
                ),
            })
    return pdf_meta


def cmd_recover(limit=None, doc_only=True):
    if not FONTES_JSON.exists():
        raise SystemExit('fetch/build antes')
    fontes = json.loads(FONTES_JSON.read_text())
    pub = json.loads((PROVAS / 'matriz-publicacao.json').read_text())
    # Inclui pdf-pendente sem snapshot para completar captura responsável.
    retidos = [
        r for r in pub.get('retidos', [])
        if r.get('status') == 'retido-marcador-anexo-tabela'
        or (
            r.get('status') == 'retido-anexo-pdf-layout-pendente'
            and not r.get('anexos_pdf')
        )
    ]
    if limit is not None:
        retidos = retidos[:limit]
    ANEXOS_DIR.mkdir(parents=True, exist_ok=True)
    discovery = json.loads(DISCOVERY.read_text()) if DISCOVERY.exists() else {}
    recover_log = json.loads(RECOVER_RES.read_text()) if RECOVER_RES.exists() else {}
    diag = json.loads(DIAG_MARK.read_text()) if DIAG_MARK.exists() else {}
    novos, ainda = [], []
    for item in retidos:
        key = item['id']
        rec = fontes.get(key)
        if not rec:
            ainda.append({**item, 'status': 'sem-fonte-local'}); continue
        raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
        diag[key] = ar.diagnose_marker_in_html(raw.decode('utf-8', 'replace'))
        print('recover', key, flush=True)
        disc = discovery.get(key) or ar.discover_camara_norma(key, especie='decreto.lei')
        discovery[key] = disc
        if disc.get('status') != 'ok' or not disc.get('anexos'):
            ainda.append({
                **item,
                'status': 'retido-sem-anexo-camara',
                'descoberta': disc.get('status'),
                'diagnostico_marcador': diag[key],
                'norma_camara': disc.get('norma'),
            })
            recover_log[key] = {'status': 'sem-anexo-camara', 'descoberta': disc}
            continue
        urls = [u for u in disc['anexos'] if (not doc_only) or u.lower().endswith(('.doc', '.docx'))]
        if not urls:
            pdfs = [u for u in disc['anexos'] if u.lower().endswith('.pdf')]
            pdf_meta = _capture_pdf_snapshots(key, pdfs)
            ainda.append({
                **item,
                'status': 'retido-anexo-pdf-layout-pendente',
                'diagnostico_marcador': diag[key],
                'anexos_pdf': pdf_meta,
                'norma_camara': disc.get('norma'),
            })
            recover_log[key] = {'status': 'pdf-pendente', 'anexos': pdf_meta, 'descoberta': disc}
            print('  PDF pendente', len(pdf_meta))
            continue
        try:
            groups, meta_list = [], []
            with tempfile.TemporaryDirectory() as td:
                td_path = Path(td)
                for i, url in enumerate(urls):
                    name = url.rstrip('/').rsplit('/', 1)[-1]
                    dest = ANEXOS_DIR / f'{key}.{i}.{name}.xz'
                    meta = ar.download_and_store_anexo(url, dest, td_path / f'w{i}')
                    if not meta.get('publicavel'):
                        raise RuntimeError(meta.get('bloqueio') or 'não publicável')
                    groups.append(nl.convert_html(meta['html_convertido'], 'utf-8', url).blocks)
                    meta_list.append({
                        'url': url, 'sha256': meta['sha256'], 'bytes': meta['bytes'],
                        'html_sha256': meta.get('html_sha256'),
                        'snapshot_rel': str(dest.relative_to(ROOT)),
                    })
            info = build_one(key, rec, anexo_groups=groups, anexo_meta=meta_list)
        except Exception as exc:  # noqa: BLE001
            ainda.append({
                **item, 'status': 'falha-recuperacao', 'erro': str(exc),
                'diagnostico_marcador': diag[key], 'norma_camara': disc.get('norma'),
            })
            recover_log[key] = {'status': 'falha', 'erro': str(exc)}
            print('  FAIL', exc); continue
        if info['status'] != 'publicado':
            ainda.append(info); print('  RETIDO', info['status'])
        else:
            novos.append(info)
            fontes[key] = {**rec, 'status': 'capturado-com-anexos-camara', 'anexos_camara': meta_list}
            recover_log[key] = {'status': 'publicado', 'anexos': meta_list}
            print('  PUB', key)
    visitados = {r['id'] for r in retidos}
    preservados = [r for r in pub.get('retidos', []) if r['id'] not in visitados]
    all_pub = [p for p in pub.get('publicados', []) if p['id'] not in {n['id'] for n in novos}] + novos
    all_ret = ainda + preservados
    write_json(FONTES_JSON, fontes)
    write_json(DISCOVERY, discovery)
    write_json(RECOVER_RES, recover_log)
    write_json(DIAG_MARK, diag)
    write_json(PROVAS / 'matriz-publicacao.json', {
        'publicados': all_pub, 'retidos': all_ret,
        'n_publicados': len(all_pub), 'n_retidos': len(all_ret),
        'recuperados_camara_nesta_rodada': len(novos),
    })
    write_json(PROVAS / 'limites.json', {
        'issue': 96,
        'matriz_resumo': json.loads(MATRIZ.read_text()) if MATRIZ.exists() else {},
        'n_publicados': len(all_pub), 'n_retidos': len(all_ret),
        'nota': (
            'Epígrafes «Decreto nº» divergentes preservadas. Marcadores oficiais; '
            'anexos .doc Câmara publicados; PDF retido. DEL vs DEL-mpv sem fusão.'
        ),
        'regras': [
            'Não inferir vigência de HTTP/arquivo.',
            'Número coincidente exige revisão, não correção automática.',
            '<<ANEXO>> retém até peça oficial recuperada.',
        ],
        'retidos_por_status': {
            s: sum(1 for r in all_ret if r.get('status') == s)
            for s in sorted({r.get('status') for r in all_ret})
        },
    })
    print(f'recover del: novos={len(novos)} retidos={len(all_ret)} pub={len(all_pub)}')


def cmd_build():
    fontes = json.loads(FONTES_JSON.read_text())
    pub, ret = [], []
    for key, rec in sorted(fontes.items()):
        st = rec.get('status')
        if st == 'capturado-com-anexos-camara':
            try:
                groups, meta = [], rec.get('anexos_camara') or []
                with tempfile.TemporaryDirectory() as td:
                    td_path = Path(td)
                    for i, a in enumerate(meta):
                        data = lzma.decompress((ROOT / a['snapshot_rel']).read_bytes())
                        if sha256(data) != a['sha256']:
                            raise ValueError('hash anexo')
                        name = a['url'].rstrip('/').rsplit('/', 1)[-1]
                        raw_path = td_path / name
                        raw_path.write_bytes(data)
                        html_path = ar.convert_office_to_html(raw_path, td_path / f'h{i}')
                        groups.append(nl.convert_html(html_path.read_bytes(), 'utf-8', a['url']).blocks)
                info = build_one(key, rec, anexo_groups=groups, anexo_meta=meta)
            except Exception as e:  # noqa: BLE001
                ret.append({'id': key, 'status': 'falha-reconversao-anexo', 'erro': str(e)}); continue
        elif st != 'capturado':
            ret.append({'id': key, 'status': st}); continue
        else:
            try:
                info = build_one(key, rec)
            except Exception as e:  # noqa: BLE001
                ret.append({'id': key, 'status': 'falha-conversao', 'erro': str(e)})
                print('FAIL', key, e); continue
        (pub if info['status'] == 'publicado' else ret).append(info)
        print(info['status'][:3].upper(), key)
    write_json(PROVAS / 'matriz-publicacao.json', {
        'publicados': pub, 'retidos': ret, 'n_publicados': len(pub), 'n_retidos': len(ret),
    })
    write_json(PROVAS / 'limites.json', {
        'issue': 96,
        'matriz_resumo': json.loads(MATRIZ.read_text()) if MATRIZ.exists() else {},
        'n_publicados': len(pub), 'n_retidos': len(ret),
        'nota': 'Fetch retomável; recover anexos Câmara; epígrafes divergentes preservadas.',
        'regras': [
            'Não inferir vigência de HTTP/arquivo.',
            'Número coincidente exige revisão, não correção automática.',
            '<<ANEXO>> retém até peça oficial recuperada.',
        ],
        'retidos_por_status': {
            s: sum(1 for r in ret if r.get('status') == s)
            for s in sorted({r.get('status') for r in ret})
        },
    })


def cmd_verify():
    pub = json.loads((PROVAS / 'matriz-publicacao.json').read_text())
    fontes = json.loads(FONTES_JSON.read_text())
    errors = []
    for item in pub['publicados']:
        path = ROOT / item['path']
        if not path.exists():
            errors.append(f'ausente {item["id"]}')
            continue
        text = path.read_text()
        if 'vigencia_certificada' not in text:
            errors.append(f'{item["id"]}: vigencia')
        if '<<ANEXO>>' in text or '<<TABELA>>' in text:
            errors.append(f'{item["id"]}: marcador residual')
        rec = fontes[item['id']]
        raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
        if sha256(raw) != rec['sha256_fonte']:
            errors.append(f'{item["id"]}: snapshot')
        print('OK', item['id'])
    if errors:
        for e in errors:
            print(' -', e)
        raise SystemExit(1)
    print('verify ok', len(pub['publicados']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['reconcile', 'fetch', 'recover', 'build', 'verify'])
    ap.add_argument('--limit', type=int)
    ap.add_argument('--refresh-catalog', action='store_true')
    args = ap.parse_args()
    if args.cmd == 'reconcile':
        cmd_reconcile(force=args.refresh_catalog)
    elif args.cmd == 'fetch':
        cmd_fetch(args.limit)
    elif args.cmd == 'recover':
        cmd_recover(limit=args.limit)
    elif args.cmd == 'build':
        cmd_build()
    else:
        cmd_verify()


if __name__ == '__main__':
    main()
