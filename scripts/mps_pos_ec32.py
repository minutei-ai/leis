#!/usr/bin/env python3
"""Medidas provisórias pós-EC 32 — issue #84.

 reconcilia o catálogo Senado (tipo=MPV) com o acervo local para a série
sem reedição a partir de 11/09/2001, coleta íntegras via normas.leg.br e
publica Markdown quando a fonte não traz marcadores `<<ANEXO*>>`/`<<TABELA*>>`.

Não infere conversão/rejeição/eficácia sem vínculo documentado na fonte.
Não funde com o lote pré-EC32 (#95). README agregado fica com o orquestrador.

Subcomandos:
  reconcile   compara catálogo Senado × federal/ → matriz de lacunas
  fetch       baixa metadados+HTML das ausências (limite opcional)
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
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas' / 'mps-pos-ec32'
FONTES_DIR = PROVAS / 'fontes'
FONTES_JSON = PROVAS / 'fontes.json'
MATRIZ = PROVAS / 'matriz-lote.json'
CATALOGO_SNAP = PROVAS / 'catalogo-senado-mpv-pos.json'
COBERTURA = PROVAS / 'cobertura-conversao.json'
FEDERAL = ROOT / 'federal'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
CORTE = datetime.date(2001, 9, 11)
ANEXO_MARK = re.compile(r'<<(ANEXOS?|TABELAS?|TEBELAS?)>>', re.I)
# Fonte normas.leg.br: N + ordinal em <sup>o</sup> vira "No"; também "N.", "N°", "No-".
MP_TITLE_RE = r'^MEDIDA PROVIS[ÓO]RIA\s+N[º°oO.\-\s]*\d'
MP_FILE = re.compile(
    r'^br-federal-medida-provisoria-(\d{4})-(\d{2})-(\d{2})-(\d+)(?:-(\d+))?\.md$'
)


def blocks_have_anexo(blocks: list[str]) -> bool:
    """Detecta marcadores <<ANEXO>>/<<TABELA>> no HTML bruto ou após convert_html (às vezes escapados)."""
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
    if only_numbers:
        want = set(only_numbers)
        ausencias = [a for a in ausencias if a['numero'] in want]
    if limit is not None:
        ausencias = ausencias[:limit]
    FONTES_DIR.mkdir(parents=True, exist_ok=True)
    fontes = json.loads(FONTES_JSON.read_text()) if FONTES_JSON.exists() else {}
    resultados = []
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
        if ANEXO_MARK.search(text_probe):
            snap = FONTES_DIR / f'{key}.html.xz'
            snap.write_bytes(lzma.compress(html))
            fontes[key] = {
                'url': cu,
                'sha256_fonte': sha256(html),
                'bytes': len(html),
                'capturado_em': utc_now(),
                'snapshot': str(snap.relative_to(ROOT)),
                'status': 'retido-marcador-anexo-tabela',
                'urn': detail.get('legislationIdentifier'),
                'vinculos_fonte': vinculos,
                'headline': detail.get('headline'),
            }
            resultados.append({
                **a, 'id': key, 'status': 'retido-marcador-anexo-tabela',
                'urn': detail.get('legislationIdentifier'),
                'vinculos_fonte': vinculos,
            })
            print('  RETIDO marcador', key)
            continue
        snap = FONTES_DIR / f'{key}.html.xz'
        snap.write_bytes(lzma.compress(html))
        meta_path = FONTES_DIR / f'{key}.dados.json.xz'
        meta_path.write_bytes(lzma.compress(json.dumps(detail, ensure_ascii=False).encode()))
        fontes[key] = {
            'url': cu,
            'sha256_fonte': sha256(html),
            'bytes': len(html),
            'capturado_em': utc_now(),
            'snapshot': str(snap.relative_to(ROOT)),
            'dados_snapshot': str(meta_path.relative_to(ROOT)),
            'status': 'capturado',
            'urn': detail.get('legislationIdentifier'),
            'vinculos_fonte': vinculos,
            'headline': detail.get('headline'),
            'encoding_meta': {
                k: enc_meta.get(k) for k in (
                    'version', 'additionalType', 'datePublished', 'name', 'encodingFormat'
                ) if enc_meta
            },
        }
        resultados.append({**a, 'id': key, 'status': 'capturado'})
        print('  OK', key, len(html))
    write_json(FONTES_JSON, fontes)
    write_json(PROVAS / 'fetch-resultados.json', resultados)
    print('fontes', len(fontes), 'resultados', len(resultados))


def build_mp_markdown(key: str, rec: dict) -> dict:
    raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
    if sha256(raw) != rec['sha256_fonte']:
        raise ValueError(f'hash snapshot {key}')
    if ANEXO_MARK.search(raw.decode('utf-8', 'replace')):
        return {'id': key, 'status': 'retido-marcador-anexo-tabela'}
    conv = nl.convert_html(raw, 'utf-8', rec['url'])
    if blocks_have_anexo(conv.blocks):
        return {'id': key, 'status': 'retido-marcador-anexo-tabela', 'origem': 'pos-conversao'}
    # drop control marker block if present
    blocks = [
        b for b in conv.blocks
        if not re.match(r'^###MPV-', nl.md_plain(b, True).strip())
    ]
    title_re = MP_TITLE_RE
    try:
        body = nl.blocks_to_markdown(blocks, title_re)
    except ValueError:
        return {'id': key, 'status': 'retido-titulo-nao-encontrado',
                'blocos_amostra': [nl.md_plain(b, True)[:80] for b in blocks[:5]]}
    if not coverage_safe(blocks, body):
        # try with original blocks including marker
        body = nl.blocks_to_markdown(conv.blocks, title_re)
        if not coverage_safe(conv.blocks, body):
            raise ValueError(f'cobertura falhou {key}')
        blocks = conv.blocks
    # identity from key
    m = re.match(r'br-federal-medida-provisoria-(\d{4}-\d{2}-\d{2})-(\d+)$', key)
    date, num = m.group(1), m.group(2)
    vinculos = rec.get('vinculos_fonte') or []
    vinculo_txt = 'nenhum vínculo de conversão/geração informado na captura.'
    if vinculos:
        parts = [f"{v.get('name') or ''} ({v.get('id') or ''})".strip() for v in vinculos]
        vinculo_txt = 'Vínculos declarados na fonte (sem inferência de vigência): ' + '; '.join(parts)
    note = (
        f"> **Medida Provisória nº {int(num)} de {date} — publicação original (normas.leg.br/Senado).** "
        f"Fonte: {rec['url']} (capturada em {rec['capturado_em']}, SHA-256 `{rec['sha256_fonte']}`). "
        f"Snapshot: `{rec['snapshot']}`. O acervo não certifica vigência.\n"
        f">\n"
        f"> Série pós-EC 32/2001 (numeração contínua sem reedição). Não fundir com MPs/reedições "
        f"anteriores a 11/09/2001 (issue #95).\n"
        f">\n"
        f"> {vinculo_txt}\n"
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
        'edicao_id': f'{key}@publicacao-original-senado',
        'edicao_tipo': 'historica',
        'edicao_integral': True,
        'edicao_relacionada': 'nenhuma',
        'fonte_orgao': 'Senado Federal / Portal das Normas',
        'fonte_url': rec['url'],
        'fonte_formato': 'html',
        'fonte_conferencia': 'nenhuma',
        'capturado_em': rec['capturado_em'],
        'sha256_fonte': rec['sha256_fonte'],
        'situacao': 'nao-informada',
        'situacao_fundamento': 'desconhecido',
        'vigencia_certificada': False,
        'texto_riscado': False,
        'anexos_no_corpo': 0,
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
    }


def cmd_build() -> None:
    if not FONTES_JSON.exists():
        raise SystemExit('fetch antes de build')
    fontes = json.loads(FONTES_JSON.read_text())
    pub = []
    retidos = []
    for key, rec in sorted(fontes.items()):
        if rec.get('status') == 'retido-marcador-anexo-tabela':
            retidos.append({'id': key, 'status': rec['status'], 'urn': rec.get('urn'),
                            'vinculos_fonte': rec.get('vinculos_fonte')})
            continue
        if rec.get('status') != 'capturado':
            retidos.append({'id': key, 'status': rec.get('status')})
            continue
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
    write_json(COBERTURA, {p['id']: {'cobertura': True, 'sha256_markdown_corpo': p['sha256_markdown_corpo']} for p in pub})
    (PROVAS / 'README.md').write_text(
        '# Provas — MPs pós-EC 32 (issue #84)\n\n'
        'Reconcilia o catálogo `tipo=MPV` do Senado com o acervo, coleta íntegras via '
        'normas.leg.br e publica apenas textos sem marcadores `<<ANEXO>>`/`<<TABELA>>`.\n\n'
        '```bash\n'
        'python3 scripts/mps_pos_ec32.py reconcile\n'
        'python3 scripts/mps_pos_ec32.py fetch --limit 50\n'
        'python3 scripts/mps_pos_ec32.py build\n'
        'python3 scripts/mps_pos_ec32.py verify\n'
        '```\n\n'
        'Corte operacional: data ≥ 11/09/2001 e sem campo `reedicao`. Lote histórico: #95.\n'
    )
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
        if 'serie_historica": "medida-provisoria-pos-ec32"' not in text and \
           "serie_historica: \"medida-provisoria-pos-ec32\"" not in text:
            # json.dumps in yaml line
            if 'medida-provisoria-pos-ec32' not in text:
                errors.append(f'{item["id"]}: serie ausente')
        if 'vigencia_certificada' not in text:
            errors.append(f'{item["id"]}: vigencia_certificada ausente')
        rec = fontes[item['id']]
        raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
        if sha256(raw) != rec['sha256_fonte']:
            errors.append(f'{item["id"]}: snapshot')
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
    ap.add_argument('cmd', choices=['reconcile', 'fetch', 'build', 'verify'])
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--numbers', default=None, help='lista CSV de números')
    ap.add_argument('--refresh-catalog', action='store_true')
    args = ap.parse_args()
    if args.cmd == 'reconcile':
        cmd_reconcile(force_catalog=args.refresh_catalog)
    elif args.cmd == 'fetch':
        nums = [int(x) for x in args.numbers.split(',')] if args.numbers else None
        cmd_fetch(limit=args.limit, only_numbers=nums)
    elif args.cmd == 'build':
        cmd_build()
    else:
        cmd_verify()


if __name__ == '__main__':
    main()
