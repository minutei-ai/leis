#!/usr/bin/env python3
"""MPs e reedições anteriores a 11/09/2001 — issue #95.

Lote histórico distinto da #84. Preserva numero+reedicao na identidade
(ex.: 2229-43). Não funde com a série pós-EC 32.

Subcomandos: reconcile | fetch | build | verify
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import lzma
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas' / 'mps-pre-ec32'
FONTES_DIR = PROVAS / 'fontes'
FONTES_JSON = PROVAS / 'fontes.json'
MATRIZ = PROVAS / 'matriz-lote.json'
CATALOGO = PROVAS / 'catalogo-senado-mpv-pre.json'
FEDERAL = ROOT / 'federal'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
CORTE = datetime.date(2001, 9, 11)
ANEXO_MARK = re.compile(r'<<(ANEXOS?|TABELAS?|TEBELAS?)>>', re.I)
MP_TITLE_RE = r'^MEDIDA PROVIS[ÓO]RIA\s+N[º°oO.\-\s]*\d'
MP_FILE = re.compile(
    r'^br-federal-medida-provisoria-(\d{4})-(\d{2})-(\d{2})-(\d+)(?:-(\d+))?\.md$'
)


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


def local_index() -> dict[str, list[dict]]:
    """Chave: numero ou numero-reedicao."""
    out: dict[str, list[dict]] = {}
    for p in FEDERAL.glob('br-federal-medida-provisoria-*.md'):
        m = MP_FILE.match(p.name)
        if not m:
            continue
        y, mo, d, num, reed = m.groups()
        dt = datetime.date(int(y), int(mo), int(d))
        key = f'{int(num)}-{int(reed)}' if reed else str(int(num))
        out.setdefault(key, []).append({'path': p.name, 'data': dt.isoformat(), 'numero': int(num), 'reedicao': reed})
    return out


def load_catalog(force=False) -> dict:
    # reutiliza snapshot da #84 se existir e for fresco o bastante
    shared = ROOT / 'provas' / 'mps-pos-ec32' / 'catalogo-senado-mpv-pos.json'
    if CATALOGO.exists() and not force:
        return json.loads(CATALOGO.read_text())
    if shared.exists() and not force:
        src = json.loads(shared.read_text())
        write_json(CATALOGO, {**src, 'reusado_de': str(shared.relative_to(ROOT))})
        return json.loads(CATALOGO.read_text())
    url = 'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=MPV'
    data, headers = fetch_url(url)
    payload = json.loads(data.decode('utf-8'))
    docs = payload['ListaDocumento']['documentos']['documento']
    if isinstance(docs, dict):
        docs = [docs]
    obj = {
        'capturado_em': utc_now(),
        'url': url,
        'sha256': sha256(data),
        'bytes': len(data),
        'status': headers.get('status'),
        'total_registros': len(docs),
        'documentos': docs,
    }
    write_json(CATALOGO, obj)
    return obj


def identity_key(numero: int, reedicao) -> str:
    if reedicao in (None, '', '0', 0):
        return str(numero)
    return f'{numero}-{int(str(reedicao).strip())}'


def file_id(date: str, numero: int, reedicao) -> str:
    if reedicao in (None, '', '0', 0):
        return f'br-federal-medida-provisoria-{date}-{numero}'
    return f'br-federal-medida-provisoria-{date}-{numero}-{int(str(reedicao).strip())}'


def cmd_reconcile(force=False) -> None:
    PROVAS.mkdir(parents=True, exist_ok=True)
    cat = load_catalog(force=force)
    local = local_index()
    ausentes, presentes, revisao = [], [], []
    for doc in cat['documentos']:
        dt = parse_date(doc.get('dataassinatura') or '')
        if dt is None or dt >= CORTE:
            continue
        try:
            num = int(str(doc.get('numero')).strip())
        except (TypeError, ValueError):
            revisao.append({'doc_id': doc.get('id'), 'motivo': 'numero-invalido', 'tipo': doc.get('tipo')})
            continue
        reed = doc.get('reedicao')
        key = identity_key(num, reed)
        date = dt.isoformat()
        fid = file_id(date, num, reed)
        entry = {
            'senado_id': str(doc.get('id')),
            'tipo': doc.get('tipo'),
            'numero': num,
            'reedicao': reed,
            'chave': key,
            'data': date,
            'id': fid,
            'norma': doc.get('norma'),
            'normaNome': doc.get('normaNome'),
        }
        hits = local.get(key, [])
        exact = [h for h in hits if h['data'] == date]
        if exact or fid in {h['path'][:-3] for h in hits}:
            presentes.append(entry)
        elif hits:
            revisao.append({**entry, 'motivo': 'mesmo-numero-outra-identidade', 'arquivos_locais': hits})
        else:
            # também verificar se arquivo com data existe sob outro reed
            ausentes.append(entry)
    write_json(MATRIZ, {
        'corte_operacional': CORTE.isoformat(),
        'nota': (
            'Lote histórico separado da #84. Preservar reedicao na identidade. '
            'Corte é operacional; não afirma vigência nem resultado parlamentar.'
        ),
        'catalogo_sha256': cat['sha256'],
        'pre_corte': len(ausentes) + len(presentes) + len(revisao),
        'presentes': len(presentes),
        'ausentes_canonicos': len(ausentes),
        'revisao_mesmo_numero': len(revisao),
    })
    write_json(PROVAS / 'ausencias.json', ausentes)
    write_json(PROVAS / 'revisao-mesmo-numero.json', revisao)
    (PROVAS / 'README.md').write_text(
        '# Provas — MPs/reedições anteriores a 11/09/2001 (#95)\n\n'
        'Série histórica distinta da #84. Identidade composta `numero[-reedicao]`.\n\n'
        '```bash\n'
        'python3 scripts/mps_pre_ec32.py reconcile\n'
        'python3 scripts/mps_pre_ec32.py fetch --limit 40\n'
        'python3 scripts/mps_pre_ec32.py build\n'
        'python3 scripts/mps_pre_ec32.py verify\n'
        '```\n'
    )
    print(f"ausentes={len(ausentes)} presentes={len(presentes)} revisao={len(revisao)}")


def urn_for(date: str, numero: int, reedicao) -> str:
    if reedicao in (None, '', '0', 0):
        return f'urn:lex:br:federal:medida.provisoria:{date};{numero}'
    return f'urn:lex:br:federal:medida.provisoria:{date};{numero}-{int(str(reedicao).strip())}'


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
    results = [r for r in results if r.get('id') in fontes]  # keep prior
    for a in pending:
        key = a['id']
        urn = urn_for(a['data'], a['numero'], a.get('reedicao'))
        print('fetch', key, flush=True)
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
        status = 'retido-marcador-anexo-tabela' if ANEXO_MARK.search(html.decode('utf-8', 'replace')) else 'capturado'
        snap = FONTES_DIR / f'{key}.html.xz'
        snap.write_bytes(lzma.compress(html))
        fontes[key] = {
            'url': cu, 'sha256_fonte': sha256(html), 'bytes': len(html),
            'capturado_em': utc_now(), 'snapshot': str(snap.relative_to(ROOT)),
            'status': status, 'urn': detail.get('legislationIdentifier'),
            'headline': detail.get('headline'), 'numero': a['numero'],
            'reedicao': a.get('reedicao'), 'data': a['data'], 'tipo': a.get('tipo'),
        }
        results.append({**a, 'status': status})
        print(' ', status, key, len(html))
    write_json(FONTES_JSON, fontes)
    write_json(PROVAS / 'fetch-resultados.json', results)


def build_one(key, rec):
    raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
    if sha256(raw) != rec['sha256_fonte']:
        raise ValueError('hash')
    if ANEXO_MARK.search(raw.decode('utf-8', 'replace')):
        return {'id': key, 'status': 'retido-marcador-anexo-tabela'}
    conv = nl.convert_html(raw, 'utf-8', rec['url'])
    if blocks_have_anexo(conv.blocks):
        return {'id': key, 'status': 'retido-marcador-anexo-tabela', 'origem': 'pos-conversao'}
    blocks = [b for b in conv.blocks if not re.match(r'^###MPV-', nl.md_plain(b, True).strip())]
    try:
        body = nl.blocks_to_markdown(blocks, MP_TITLE_RE)
    except ValueError:
        return {'id': key, 'status': 'retido-titulo-nao-encontrado',
                'blocos_amostra': [nl.md_plain(b, True)[:80] for b in blocks[:5]]}
    if not coverage_safe(blocks, body):
        body = nl.blocks_to_markdown(conv.blocks, MP_TITLE_RE)
        if not coverage_safe(conv.blocks, body):
            raise ValueError('cobertura')
        blocks = conv.blocks
    reed = rec.get('reedicao')
    reed_txt = f", reedição {reed}" if reed not in (None, '', '0', 0) else ''
    note = (
        f"> **Medida Provisória nº {rec['numero']}{reed_txt} de {rec['data']} — publicação original.** "
        f"Fonte: {rec['url']} (capturada em {rec['capturado_em']}, SHA-256 `{rec['sha256_fonte']}`). "
        f"Snapshot: `{rec['snapshot']}`. O acervo não certifica vigência.\n"
        f">\n"
        f"> Série histórica pré-EC 32/2001 (issue #95). Tipo de catálogo: `{rec.get('tipo')}`. "
        f"Não fundir com a numeração contínua pós-11/09/2001 (#84).\n"
        f">\n"
        f"> Conversão/efeitos somente com evidência documentada; filtros #70 / rastreador #83.\n"
    )
    sha_md = sha256(body.encode())
    fields = {
        'id': key, 'norma_id': key, 'norma_tipo': 'medida-provisoria',
        'norma_numero': str(rec['numero']) + (f"-{int(str(reed).strip())}" if reed not in (None, '', '0', 0) else ''),
        'norma_data': rec['data'], 'titulo': rec.get('headline') or key, 'esfera': 'federal',
        'edicao_id': f'{key}@publicacao-original-senado', 'edicao_tipo': 'historica',
        'edicao_integral': True, 'edicao_relacionada': 'nenhuma',
        'fonte_orgao': 'Senado Federal / Portal das Normas', 'fonte_url': rec['url'],
        'fonte_formato': 'html', 'fonte_conferencia': 'nenhuma',
        'capturado_em': rec['capturado_em'], 'sha256_fonte': rec['sha256_fonte'],
        'situacao': 'nao-informada', 'situacao_fundamento': 'desconhecido',
        'vigencia_certificada': False, 'texto_riscado': False, 'anexos_no_corpo': 0,
        'tabelas': sum(1 for b in blocks if '<table' in b.lower()),
        'imagens_omitidas': len(getattr(conv, 'images', []) or []),
        'efeitos_diferidos': 'preservados-nas-notas-do-texto',
        'sha256_markdown': sha_md, 'manifesto': 'provas/mps-pre-ec32/matriz-publicacao.json',
        'contrato_versao': 1, 'serie_historica': 'medida-provisoria-pre-ec32',
        'urn': rec.get('urn'), 'tipo_catalogo': rec.get('tipo'),
    }
    fm = '---\n' + '\n'.join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in fields.items()) + '\n---\n'
    doc = fm + '\n<!-- nota-edicao:inicio -->\n\n' + note + '\n<!-- nota-edicao:fim -->\n\n' + body
    (FEDERAL / f'{key}.md').write_text(doc)
    return {'id': key, 'status': 'publicado', 'path': f'federal/{key}.md', 'sha256_markdown_corpo': sha_md}


def cmd_build():
    fontes = json.loads(FONTES_JSON.read_text())
    pub, ret = [], []
    for key, rec in sorted(fontes.items()):
        if rec.get('status') != 'capturado':
            ret.append({'id': key, 'status': rec.get('status')})
            continue
        try:
            info = build_one(key, rec)
        except Exception as exc:  # noqa: BLE001
            ret.append({'id': key, 'status': 'falha-conversao', 'erro': str(exc)})
            print('FAIL', key, exc)
            continue
        (pub if info['status'] == 'publicado' else ret).append(info)
        print(info['status'].upper()[:3], key)
    write_json(PROVAS / 'matriz-publicacao.json', {'publicados': pub, 'retidos': ret, 'n_publicados': len(pub), 'n_retidos': len(ret)})


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
        if 'medida-provisoria-pre-ec32' not in text:
            errors.append(f'{item["id"]}: serie')
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
    ap.add_argument('cmd', choices=['reconcile', 'fetch', 'build', 'verify'])
    ap.add_argument('--limit', type=int)
    ap.add_argument('--refresh-catalog', action='store_true')
    args = ap.parse_args()
    if args.cmd == 'reconcile':
        cmd_reconcile(force=args.refresh_catalog)
    elif args.cmd == 'fetch':
        cmd_fetch(args.limit)
    elif args.cmd == 'build':
        cmd_build()
    else:
        cmd_verify()


if __name__ == '__main__':
    main()
