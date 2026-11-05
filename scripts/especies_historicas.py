#!/usr/bin/env python3
"""Leis constitucionais, atos institucionais e atos complementares — issue #90.

 reconcilia catálogos Senado (LCT, AIT, ACP) com o acervo, coleta íntegras via
normas.leg.br e publica Markdown com série/espécie próprias (sem misturar com
lei complementar ou emendas CF/1988).

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

PROVAS = ROOT / 'provas' / 'especies-historicas'
FONTES_DIR = PROVAS / 'fontes'
FONTES_JSON = PROVAS / 'fontes.json'
MATRIZ = PROVAS / 'matriz-lote.json'
FEDERAL = ROOT / 'federal'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
ANEXO_MARK = re.compile(r'<<(ANEXOS?|TABELAS?|TEBELAS?)>>', re.I)

ESPECIES = {
    'LCT': {
        'nome': 'lei-constitucional',
        'serie': 'lei-constitucional-1938-1946',
        'file_prefix': 'br-federal-lei-constitucional',
        'urn_tipo': 'lei.constitucional',
        'title_pattern': r'^LEI CONSTITUCIONAL|^Lei Constitucional',
        'expected_sha256_issue': '39a92fe7581ab9feade8903f6e70bcd076752ae666db7d48d32d49eedd0a5f70',
    },
    'AIT': {
        'nome': 'ato-institucional',
        'serie': 'ato-institucional-1964-1969',
        'file_prefix': 'br-federal-ato-institucional',
        'urn_tipo': 'ato.institucional',
        'title_pattern': r'^ATO INSTITUCIONAL|^Ato Institucional',
        'expected_sha256_issue': 'c2e50078b395601ed704d2f2e56ba26708416259930295e207f39dfc40e0f37f',
    },
    'ACP': {
        'nome': 'ato-complementar',
        'serie': 'ato-complementar-1965-1978',
        'file_prefix': 'br-federal-ato-complementar',
        'urn_tipo': 'ato.complementar',
        # Fonte Sigen às vezes traz grafia histórica «acto» (com c) e caixa mista.
        'title_pattern': r'^(?:ATO|ACTO)\s+COMPLEMENTAR',
        'expected_sha256_issue': '58396a2129d0134ec5fc177b8dc6104b3d65f67ce8e68f466af6ec7c0bd3aa1c',
    },
}


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


def local_ids(prefix: str) -> set[str]:
    return {p.stem for p in FEDERAL.glob(f'{prefix}-*.md')}


def fetch_catalog(tipo: str) -> dict:
    path = PROVAS / f'catalogo-senado-{tipo.lower()}.json'
    if path.exists():
        return json.loads(path.read_text())
    url = f'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo={tipo}'
    data, headers = fetch_url(url)
    payload = json.loads(data.decode('utf-8'))
    docs = payload['ListaDocumento']['documentos']['documento']
    if isinstance(docs, dict):
        docs = [docs]
    obj = {
        'tipo': tipo,
        'url': url,
        'capturado_em': utc_now(),
        'sha256': sha256(data),
        'bytes': len(data),
        'status': headers.get('status'),
        'total': len(docs),
        'documentos': docs,
    }
    write_json(path, obj)
    return obj


def make_id(prefix: str, date: str, numero: str) -> str:
    return f'{prefix}-{date}-{numero}'


def cmd_reconcile() -> None:
    PROVAS.mkdir(parents=True, exist_ok=True)
    resumo = {}
    ausencias_all = []
    for tipo, meta in ESPECIES.items():
        cat = fetch_catalog(tipo)
        local = local_ids(meta['file_prefix'])
        ausentes = []
        presentes = []
        revisao = []
        for doc in cat['documentos']:
            dt = parse_date(doc.get('dataassinatura') or '')
            num_raw = str(doc.get('numero') or '').strip()
            if not dt or not num_raw:
                revisao.append({'doc': doc, 'motivo': 'identidade-insuficiente'})
                continue
            date = dt.isoformat()
            fid = make_id(meta['file_prefix'], date, num_raw)
            entry = {
                'tipo_catalogo': tipo,
                'especie': meta['nome'],
                'serie': meta['serie'],
                'senado_id': str(doc.get('id')),
                'numero': num_raw,
                'data': date,
                'norma': doc.get('norma'),
                'normaNome': doc.get('normaNome'),
                'id': fid,
            }
            if fid in local:
                presentes.append(entry)
            else:
                # mesmo número em outra data?
                same_num = [p for p in local if p.endswith(f'-{num_raw}')]
                if same_num:
                    revisao.append({**entry, 'arquivos_locais': same_num, 'motivo': 'mesmo-numero-outra-data'})
                else:
                    ausentes.append(entry)
        resumo[tipo] = {
            'catalogo_total': cat['total'],
            'catalogo_sha256': cat['sha256'],
            'sha256_conferencia_issue': meta['expected_sha256_issue'],
            'sha256_bate_com_issue': cat['sha256'] == meta['expected_sha256_issue'],
            'presentes': len(presentes),
            'ausentes': len(ausentes),
            'revisao': len(revisao),
        }
        write_json(PROVAS / f'ausencias-{tipo.lower()}.json', ausentes)
        write_json(PROVAS / f'revisao-{tipo.lower()}.json', revisao)
        ausencias_all.extend(ausentes)
        print(tipo, resumo[tipo])
    write_json(MATRIZ, {'especies': resumo, 'nota': (
        'Catálogo oficial é evidência de descoberta, não substitui íntegra nem certifica vigência. '
        'Lei constitucional ≠ lei complementar; ato complementar ≠ ato institucional.'
    )})
    write_json(PROVAS / 'ausencias.json', ausencias_all)
    (PROVAS / 'README.md').write_text(
        '# Provas — Leis constitucionais, atos institucionais e atos complementares (#90)\n\n'
        'Espécies distintas com séries próprias. Dependem dos textos-base históricos da #79 '
        'quando houver vínculo; filtros #70 / rastreador #83 ficam com esses lotes.\n\n'
        '```bash\n'
        'python3 scripts/especies_historicas.py reconcile\n'
        'python3 scripts/especies_historicas.py fetch --limit 30\n'
        'python3 scripts/especies_historicas.py build\n'
        'python3 scripts/especies_historicas.py verify\n'
        '```\n'
    )


def urn_for(meta: dict, date: str, numero: str) -> str:
    return f"urn:lex:br:federal:{meta['urn_tipo']}:{date};{numero}"


def normas_detail(urn: str) -> dict | None:
    """Tenta Portal das Normas; histórico LCT/AIT/ACP em geral não está indexado lá."""
    url = (
        'https://normas.leg.br/api/public/normas?urn='
        + urllib.parse.quote(urn)
        + '&tipo_documento=maior-detalhe'
    )
    try:
        data, _ = fetch_url(url)
    except Exception:  # noqa: BLE001
        return None
    if not data or len(data) < 100:
        return None
    try:
        return json.loads(data.decode('utf-8'))
    except json.JSONDecodeError:
        return None


def content_url(detail: dict) -> str | None:
    enc = detail.get('encoding')
    encs = enc if isinstance(enc, list) else ([enc] if isinstance(enc, dict) else [])
    for e in encs:
        if isinstance(e, dict) and e.get('contentUrl'):
            cu = e['contentUrl']
            if '/api/binario/' in cu and '/api/public/binario/' not in cu:
                cu = cu.replace('/api/binario/', '/api/public/binario/')
            return cu
    return None


def senado_sigen_pub_url(senado_id: str) -> str | None:
    """Resolve o link «Ver texto no Sigen» em legis.senado.leg.br/norma/{id}."""
    page_url = f'https://legis.senado.leg.br/norma/{senado_id}'
    html, _ = fetch_url(page_url)
    text = html.decode('utf-8', 'replace')
    # Prefer explicit Sigen / texto links pointing to /norma/{id}/publicacao/{pub}
    candidates = re.findall(
        rf'(?:https://legis\.senado\.leg\.br)?/norma/{re.escape(senado_id)}/publicacao/(\d+)',
        text,
    )
    # Also bare "{id}/publicacao/{pub}"
    candidates += re.findall(rf'{re.escape(senado_id)}/publicacao/(\d+)', text)
    # Deduplicate preserving order
    seen = set()
    pubs = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            pubs.append(p)
    for pub in pubs:
        url = f'https://legis.senado.leg.br/norma/{senado_id}/publicacao/{pub}'
        try:
            body, headers = fetch_url(url)
        except Exception:  # noqa: BLE001
            continue
        if not body or len(body) < 500:
            continue
        # Conteúdo normativo típico traz a epígrafe da espécie
        probe = body.decode('utf-8', 'replace').upper()
        if any(k in probe for k in ('LEI CONSTITUCIONAL', 'ATO INSTITUCIONAL', 'ATO COMPLEMENTAR')):
            return url
        # Aceitar se houver bloco legislativo genérico substancial
        if 'ART.' in probe or 'ARTIGO' in probe:
            return url
    return None


def coverage_safe(blocks, markdown_body):
    from_blocks = nl.strip_fold('\n'.join(nl.md_plain(b, True) for b in blocks))
    produced = nl.strip_fold(re.sub(r'^# ', '', nl.md_plain(markdown_body, True), flags=re.M))
    return from_blocks == produced


def trim_species_blocks(blocks: list[str], title_pattern: str) -> tuple[list[str], str]:
    """Remove chrome do portal Senado e corta a partir do título da espécie."""
    title_re = re.compile(title_pattern, re.I)
    start = None
    for i, block in enumerate(blocks):
        plain = re.sub(r'\s+', ' ', nl.md_plain(block, True)).strip()
        if title_re.match(plain):
            start = i
            break
    if start is None:
        raise ValueError('título da espécie não encontrado nos blocos')
    end = len(blocks)
    chrome = re.compile(
        r'^(?:Este texto não substitui|Publicação Oficial|Detalhes da Norma|'
        r'Pular para|Menu |Atividade Legislativa|Casa Civil|https?://|Página\s+\d+)',
        re.I,
    )
    while end > start + 1 and chrome.match(re.sub(r'\s+', ' ', nl.md_plain(blocks[end - 1], True)).strip()):
        end -= 1
    return blocks[start:end], title_pattern


def blocks_have_anexo(blocks: list[str]) -> bool:
    for b in blocks:
        plain = nl.md_plain(b, True)
        if ANEXO_MARK.search(plain) or ANEXO_MARK.search(b):
            return True
    return False


def cmd_fetch(limit: int | None, tipos: list[str] | None) -> None:
    if not (PROVAS / 'ausencias.json').exists():
        cmd_reconcile()
    ausencias = json.loads((PROVAS / 'ausencias.json').read_text())
    if tipos:
        ausencias = [a for a in ausencias if a['tipo_catalogo'] in tipos]
    FONTES_DIR.mkdir(parents=True, exist_ok=True)
    fontes = json.loads(FONTES_JSON.read_text()) if FONTES_JSON.exists() else {}
    # Ignora entradas vazias/anteriores de falha de normas.leg.br sem snapshot
    pending = [a for a in ausencias if a['id'] not in fontes or not (ROOT / (fontes[a['id']].get('snapshot') or 'missing')).exists()]
    if limit is not None:
        pending = pending[:limit]
    results = []
    for a in pending:
        meta = ESPECIES[a['tipo_catalogo']]
        urn = urn_for(meta, a['data'], a['numero'])
        key = a['id']
        print('fetch', key, flush=True)
        cu = None
        headline = a.get('normaNome')
        fonte_canal = None
        # 1) Portal das Normas (raro para estas espécies históricas)
        detail = normas_detail(urn)
        if detail and detail.get('legislationIdentifier'):
            cu = content_url(detail)
            headline = detail.get('headline') or headline
            if cu:
                fonte_canal = 'normas.leg.br'
                urn = detail.get('legislationIdentifier') or urn
        # 2) Fallback oficial: texto Sigen em legis.senado.leg.br/norma/{id}/publicacao/{pub}
        if not cu:
            sid = str(a.get('senado_id') or '')
            if not sid:
                results.append({**a, 'status': 'sem-senado-id', 'urn_tentada': urn})
                continue
            try:
                cu = senado_sigen_pub_url(sid)
            except Exception as exc:  # noqa: BLE001
                results.append({**a, 'status': 'falha-resolver-sigen', 'erro': str(exc), 'urn_tentada': urn})
                continue
            if not cu:
                results.append({**a, 'status': 'texto-sigen-indisponivel', 'urn_tentada': urn, 'senado_id': sid})
                continue
            fonte_canal = 'senado-sigen'
        try:
            html, headers = fetch_url(cu)
        except Exception as exc:  # noqa: BLE001
            results.append({**a, 'status': 'falha-download', 'erro': str(exc), 'url': cu})
            continue
        ctype = (headers.get('content-type') or '').lower()
        if 'html' not in ctype and not html.lstrip().startswith((b'<', b'\xef\xbb\xbf<')):
            results.append({**a, 'status': 'formato-nao-html', 'content_type': ctype, 'bytes': len(html), 'url': cu})
            continue
        status = 'capturado'
        if ANEXO_MARK.search(html.decode('utf-8', 'replace')):
            status = 'retido-marcador-anexo-tabela'
        snap = FONTES_DIR / f'{key}.html.xz'
        snap.write_bytes(lzma.compress(html))
        fontes[key] = {
            'url': cu,
            'sha256_fonte': sha256(html),
            'bytes': len(html),
            'capturado_em': utc_now(),
            'snapshot': str(snap.relative_to(ROOT)),
            'status': status,
            'urn': urn,
            'headline': headline,
            'tipo_catalogo': a['tipo_catalogo'],
            'especie': meta['nome'],
            'serie': meta['serie'],
            'numero': a['numero'],
            'data': a['data'],
            'senado_id': a.get('senado_id'),
            'fonte_canal': fonte_canal,
        }
        results.append({**a, 'status': status, 'urn': urn, 'fonte_canal': fonte_canal, 'url': cu})
        print(' ', status, key, fonte_canal, len(html))
    write_json(FONTES_JSON, fontes)
    write_json(PROVAS / 'fetch-resultados.json', results)


def build_one(key: str, rec: dict) -> dict:
    meta = ESPECIES[rec['tipo_catalogo']]
    raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
    if sha256(raw) != rec['sha256_fonte']:
        raise ValueError('hash')
    if ANEXO_MARK.search(raw.decode('utf-8', 'replace')):
        return {'id': key, 'status': 'retido-marcador-anexo-tabela'}
    conv = nl.convert_html(raw, 'utf-8', rec['url'])
    if blocks_have_anexo(conv.blocks):
        return {'id': key, 'status': 'retido-marcador-anexo-tabela', 'origem': 'pos-conversao'}
    try:
        blocks, title_pat = trim_species_blocks(conv.blocks, meta['title_pattern'])
    except ValueError as exc:
        return {'id': key, 'status': 'retido-titulo-nao-encontrado', 'erro': str(exc),
                'blocos_amostra': [nl.md_plain(b, True)[:80] for b in conv.blocks[:8]]}
    body = nl.blocks_to_markdown(blocks, title_pat)
    if not coverage_safe(blocks, body):
        raise ValueError('cobertura')
    canal = rec.get('fonte_canal') or 'senado'
    orgao = (
        'Senado Federal — Legislação / Sigen (publicação original)'
        if canal == 'senado-sigen'
        else 'Senado Federal / Portal das Normas'
    )
    note = (
        f"> **{rec.get('headline') or key} — publicação original ({orgao}).** "
        f"Fonte: {rec['url']} (capturada em {rec['capturado_em']}, SHA-256 `{rec['sha256_fonte']}`). "
        f"Snapshot: `{rec['snapshot']}`. O acervo não certifica vigência.\n"
        f">\n"
        f"> Espécie: `{meta['nome']}` / série `{meta['serie']}`. Não misturar com lei complementar "
        f"nem com emendas à CF/1988. Denominação e texto seguem a fonte, sem normalização editorial "
        f"de natureza jurídica. Canal de captura: `{canal}` "
        f"(normas.leg.br não indexa a maioria destas espécies históricas).\n"
        f">\n"
        f"> Relações com textos-base históricos (#79) e efeitos só com evidência própria; "
        f"filtros #70 / rastreador #83.\n"
    )
    sha_md = sha256(body.encode())
    fields = {
        'id': key,
        'norma_id': key,
        'norma_tipo': meta['nome'],
        'norma_numero': str(rec['numero']),
        'norma_data': rec['data'],
        'titulo': rec.get('headline') or key,
        'esfera': 'federal',
        'edicao_id': f'{key}@publicacao-original-senado',
        'edicao_tipo': 'historica',
        'edicao_integral': True,
        'edicao_relacionada': 'nenhuma',
        'fonte_orgao': orgao,
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
        'manifesto': 'provas/especies-historicas/matriz-publicacao.json',
        'contrato_versao': 1,
        'serie_historica': meta['serie'],
        'urn': rec.get('urn'),
        'senado_id': rec.get('senado_id'),
        'fonte_canal': canal,
    }
    fm = '---\n' + '\n'.join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in fields.items()) + '\n---\n'
    doc = fm + '\n<!-- nota-edicao:inicio -->\n\n' + note + '\n<!-- nota-edicao:fim -->\n\n' + body
    (FEDERAL / f'{key}.md').write_text(doc)
    return {'id': key, 'status': 'publicado', 'path': f'federal/{key}.md',
            'sha256_markdown_corpo': sha_md, 'especie': meta['nome'], 'serie': meta['serie']}


def cmd_build() -> None:
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
        if info['status'] == 'publicado':
            pub.append(info)
            print('PUB', key)
        else:
            ret.append(info)
    write_json(PROVAS / 'matriz-publicacao.json', {
        'publicados': pub, 'retidos': ret,
        'n_publicados': len(pub), 'n_retidos': len(ret),
    })


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
        if item['serie'] not in text:
            errors.append(f'{item["id"]}: serie')
        if 'vigencia_certificada' not in text:
            errors.append(f'{item["id"]}: vigencia')
        rec = fontes[item['id']]
        raw = lzma.decompress((ROOT / rec['snapshot']).read_bytes())
        if sha256(raw) != rec['sha256_fonte']:
            errors.append(f'{item["id"]}: snapshot')
        print('OK', item['id'])
    # garantir que não há colisão de nome com lei complementar
    for item in pub['publicados']:
        if 'lei-complementar' in item['id']:
            errors.append(f'id inválido {item["id"]}')
    if errors:
        for e in errors:
            print(' -', e)
        raise SystemExit(1)
    print('verify ok', len(pub['publicados']))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['reconcile', 'fetch', 'build', 'verify'])
    ap.add_argument('--limit', type=int)
    ap.add_argument('--tipos', default=None, help='CSV LCT,AIT,ACP')
    args = ap.parse_args()
    tipos = args.tipos.split(',') if args.tipos else None
    if args.cmd == 'reconcile':
        cmd_reconcile()
    elif args.cmd == 'fetch':
        cmd_fetch(args.limit, tipos)
    elif args.cmd == 'build':
        cmd_build()
    else:
        cmd_verify()


if __name__ == '__main__':
    main()
