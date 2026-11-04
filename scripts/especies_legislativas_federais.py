"""Catálogo e coleta inicial de espécies legislativas federais (issues #65 #66 #89 #94).

Espécies:
  DLG — Decreto Legislativo (#65)
  RSF — Resolução do Senado Federal (#66)
  RCD — Resolução da Câmara dos Deputados (#89)
  RCN — Resolução do Congresso Nacional (#94)

Fluxo:
  capture   baixa os JSON oficiais do Senado e grava snapshots + hashes
  reconcile confronta o catálogo com `federal/` e grava reconciliacao
  collect   recupera HTML oficial de um lote inicial e grava snapshots
  build     reconverte snapshots → Markdown + manifesto + provas
  verify    confere offline hashes, identidade e cobertura do catálogo

Não altera o README agregado. Não infere vigência. Candidatos sem íntegra
ficam explícitos como identificados-nao-coletados / anexos-pendentes /
fonte-sem-html.
"""
from __future__ import annotations

import argparse
import json
import lzma
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import nucleo_licitacoes as nl  # noqa: E402

LOTE = 'especies-legislativas-federais'
PROVAS = ROOT / 'provas/especies-legislativas-federais'
FONTES_DIR = PROVAS / 'fontes'
COLETAS_DIR = PROVAS / 'coletas'
FED = ROOT / 'federal'
USER_AGENT = 'MinuteiLeis/0.2 (+https://github.com/minutei-ai/leis)'
CONTRACT_VERSION = getattr(nl, 'CONTRACT_VERSION', 1)

SPECIES = {
    'DLG': {
        'issue': 65,
        'descricao': 'Decreto Legislativo',
        'norma_tipo': 'decreto-legislativo',
        'slug_tipo': 'decreto-legislativo',
        'orgao_emissor': 'Congresso Nacional',
        'urn_tmpl': 'urn:lex:br:federal:decreto.legislativo:{date};{num}',
        'title_pattern': r'DECRETO LEGISLATIVO',
        'lista_url': 'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=DLG',
    },
    'RSF': {
        'issue': 66,
        'descricao': 'Resolução do Senado Federal',
        'norma_tipo': 'resolucao-senado-federal',
        'slug_tipo': 'resolucao-senado-federal',
        'orgao_emissor': 'Senado Federal',
        'urn_tmpl': 'urn:lex:br:senado.federal:resolucao:{date};{num}',
        'title_pattern': r'RESOLU',
        'lista_url': 'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=RSF',
    },
    'RCD': {
        'issue': 89,
        'descricao': 'Resolução da Câmara dos Deputados',
        'norma_tipo': 'resolucao-camara-deputados',
        'slug_tipo': 'resolucao-camara-deputados',
        'orgao_emissor': 'Câmara dos Deputados',
        'urn_tmpl': 'urn:lex:br:camara.deputados:resolucao:{date};{num}',
        'title_pattern': r'RESOLU',
        'lista_url': 'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=RCD',
    },
    'RCN': {
        'issue': 94,
        'descricao': 'Resolução do Congresso Nacional',
        'norma_tipo': 'resolucao-congresso-nacional',
        'slug_tipo': 'resolucao-congresso-nacional',
        'orgao_emissor': 'Congresso Nacional',
        'urn_tmpl': 'urn:lex:br:congresso.nacional:resolucao:{date};{num}',
        'title_pattern': r'RESOLU',
        'lista_url': 'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=RCN',
    },
}

# Lote inicial de coleta (identidades do issue + recentes com fonte HTML utilizável).
# Ampliar em lotes seguintes; o catálogo completo já fica reconciliado.
COLLECT_TARGETS = {
    'DLG': [
        '43926875',  # 433/2026
        '43926721',  # 442/2026
        '43924484',  # 426/2026
        '43924376',  # 424/2026
        '43926468',  # 400/2026
    ],
    'RSF': [
        '43755400',  # 44/2026
        '43755614',  # 43/2026
        '43755430',  # 47/2026
        '43755644',  # 45/2026
        '43686392',  # 33/2026
    ],
    'RCD': [
        '559394',  # 9/1991
        '559353',  # 7/1991
        '559249',  # 2/1991
        '559790',  # 29/1990
        '559773',  # 28/1990
    ],
    'RCN': [
        # Preferir normas.leg.br HTML sem anexos essenciais pendentes.
        # RCN 1/2025 e 2/2025 têm anexos (ANX) cuja íntegra PDF no Senado veio vazia
        # nesta captura — ficam identificados, não publicados neste lote.
        '35212493',  # 2/2021
        '33349680',  # 1/2021
        '561152',    # 2/2015
        '561170',    # 4/2013
        '561150',    # 2/2013
    ],
}

CAMARA_LIMITES_RCD = {
    'senado_lista_url': SPECIES['RCD']['lista_url'],
    'senado_intervalo_observado': {'inicio': None, 'fim': None},
    'aviso': (
        'A lista do Senado para RCD termina em 1991 nesta captura. '
        'Não usar esse total como denominador da série atual. '
        'O Regimento Interno da Câmara atualizado até a Resolução 16/2025 '
        '(https://bd.camara.leg.br/bd/items/dc8e99ca-5f5c-4e33-8cab-626f82522a8b) '
        'demonstra atividade normativa posterior; complementar descoberta no '
        'catálogo oficial da própria Câmara.'
    ),
    'fonte_complementar_regimento': {
        'titulo': 'Regimento Interno da Câmara dos Deputados atualizado até a Resolução 16/2025',
        'url': 'https://bd.camara.leg.br/bd/items/dc8e99ca-5f5c-4e33-8cab-626f82522a8b',
        'papel': 'evidencia-de-atividade-posterior-a-1991',
        'item_uuid': 'dc8e99ca-5f5c-4e33-8cab-626f82522a8b',
        'bitstream_pdf': '9289303a-cb7c-4d6e-aa9b-30476cf79b98',
        'bitstream_epub': 'a3335edf-7021-4070-b1f8-7e3f4d7b0ad1',
    },
}

# Marcadores de HTML inutilizável (erro/login/WAF/captcha). Independentes do conversor.
UNUSABLE_HTML_MARKERS = (
    b'acesso negado',
    b'access denied',
    b'just a moment',
    b'attention required',
    b'cf-browser-verification',
    b'captcha',
    b'verifica\xc3\xa7\xc3\xa3o de seguran\xc3\xa7a',
    b'verificacao de seguranca',
    b'sign in',
    b'fa\xc3\xa7a login',
    b'pagina nao encontrada',
    b'p\xc3\xa1gina n\xc3\xa3o encontrada',
    b'erro 403',
    b'erro 404',
    b'erro 500',
    b'request blocked',
    b'cloudflare',
)

CAMARA_RCD_DISCOVERY_PATH = PROVAS / 'descoberta-camara-rcd-pos-1991.json'
COLETA_PROGRESS_PATH = PROVAS / 'coleta.json'


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha256(data: bytes) -> str:
    return nl.sha256(data)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def date_iso(dmy: str) -> str:
    d, m, y = dmy.split('/')
    return f'{y}-{m}-{d}'


def numero_slug(numero: str, complemento: str | None = None) -> str:
    """Número LexML/arquivo: '31' ou '31-a' quando há complemento."""
    base = (numero or 'sn').lower()
    comp = (complemento or '').strip().lower()
    return f'{base}-{comp}' if comp else base


def slug_for(tipo: str, date: str, numero: str, complemento: str | None = None) -> str:
    spec = SPECIES[tipo]
    return f"br-federal-{spec['slug_tipo']}-{date}-{numero_slug(numero, complemento)}"


def http_get(url: str, max_time: int = 180) -> tuple[int, bytes, str]:
    dest = Path('/tmp') / f'leis-fetch-{sha256(url.encode())[:16]}.bin'
    header_file = Path(str(dest) + '.hdr')
    proc = subprocess.run([
        'curl', '--silent', '--show-error', '--location', '--proto', '=https', '--proto-redir', '=https',
        '--http1.1', '--connect-timeout', '30', '--max-time', str(max_time),
        '--max-filesize', str(64 * 1024 * 1024),
        '--user-agent', USER_AGENT, '--dump-header', str(header_file),
        '--write-out', '%{http_code} %{url_effective}',
        '--output', str(dest), url,
    ], capture_output=True, text=True)
    if proc.returncode != 0:
        header_file.unlink(missing_ok=True)
        dest.unlink(missing_ok=True)
        raise RuntimeError(f'curl failed {proc.returncode}: {proc.stderr[-300:]}')
    status_s, _, effective = proc.stdout.partition(' ')
    status = int(status_s)
    data = dest.read_bytes()
    dest.unlink(missing_ok=True)
    header_file.unlink(missing_ok=True)
    return status, data, effective.strip()


def html_rejection_reason(html: bytes) -> str | None:
    """Recusa HTML de erro/login/WAF ou falsa íntegra (sem corpo normativo útil)."""
    if not html or len(html) < 200:
        return f'html curto ({len(html) if html else 0} bytes)'
    head = html[:4096].lower()
    low = html.lower()
    if b'<html' not in head and b'<!doctype' not in head:
        return 'conteudo sem marcacao HTML'
    for marker in UNUSABLE_HTML_MARKERS:
        if marker in low:
            return f'marcador de pagina inutilizavel: {marker.decode("utf-8", "replace")}'
    # Texto visível mínimo (sem depender do conversor do lote).
    text = re.sub(rb'<script\b[^>]*>.*?</script>', b' ', low, flags=re.I | re.S)
    text = re.sub(rb'<style\b[^>]*>.*?</style>', b' ', text, flags=re.I | re.S)
    text = re.sub(rb'<[^>]+>', b' ', text)
    text = re.sub(rb'\s+', b' ', text).strip()
    if len(text) < 120:
        return f'texto visivel insuficiente ({len(text)} chars)'
    # Índices/ementas curtas sem dispositivos: rejeitar falsa íntegra genérica.
    if b'art.' not in text and b'artigo' not in text and b'resolu' not in text and b'decreto' not in text:
        if len(text) < 400:
            return 'texto sem dispositivos normativos reconheciveis'
    return None


def inspect_senado_anexos(detail: dict) -> dict:
    """Inventário de publicações ANX/PUB do detalhe Senado (sem inferir vigência)."""
    docs = detail['DetalheDocumento']['documentos']['documento']
    doc = docs[0] if isinstance(docs, list) else docs
    pubs = doc.get('publicacoes', {}).get('publicacao', [])
    if isinstance(pubs, dict):
        pubs = [pubs]
    anexos = [p for p in pubs if p.get('tipo') == 'ANX']
    pubs_txt = [p for p in pubs if p.get('tipo') in {'PUB', 'REP', 'RET'} and p.get('temTexto') == 'S']
    return {
        'anexos': [
            {
                'id': str(p.get('id')),
                'temTexto': p.get('temTexto'),
                'formato': p.get('formato'),
                'descricao': p.get('descricao') or p.get('descricaoTipo'),
            }
            for p in anexos
        ],
        'publicacoes_texto': len(pubs_txt),
        'anexos_marcados_tem_texto': sum(1 for p in anexos if p.get('temTexto') == 'S'),
    }


def parse_lista(raw: bytes) -> list[dict]:
    data = json.loads(raw)
    docs = data['ListaDocumento']['documentos']
    if docs == '':
        return []
    return docs['documento']


def catalog_path(tipo: str) -> Path:
    return FONTES_DIR / f'senado-lista-{tipo}.json.xz'


def catalog_meta_path() -> Path:
    return PROVAS / 'catalogos.json'


def reconciliacao_path(tipo: str) -> Path:
    return PROVAS / f'reconciliacao-{tipo.lower()}.json'


def manifesto_path() -> Path:
    return PROVAS / 'manifesto.json'


def fontes_json_path() -> Path:
    return PROVAS / 'fontes.json'


def cobertura_path() -> Path:
    return PROVAS / 'cobertura-conversao.json'


def limites_path() -> Path:
    return PROVAS / 'limites-catalogos.json'


def existing_federal_slugs() -> set[str]:
    return {p.stem for p in FED.glob('br-federal-*.md')}


def capture() -> dict:
    FONTES_DIR.mkdir(parents=True, exist_ok=True)
    meta = {'lote': LOTE, 'capturado_em': now_utc(), 'especies': {}}
    for tipo, spec in SPECIES.items():
        print(f'capturing {tipo}…', flush=True)
        status, raw, effective = http_get(spec['lista_url'], max_time=300)
        if status != 200 or len(raw) < 100:
            raise SystemExit(f'{tipo}: captura inutilizável HTTP {status} bytes={len(raw)}')
        docs = parse_lista(raw)
        xz = lzma.compress(raw, preset=9)
        path = catalog_path(tipo)
        path.write_bytes(xz)
        meta['especies'][tipo] = {
            'url': spec['lista_url'],
            'url_final': effective,
            'http_status': status,
            'registros': len(docs),
            'sha256': sha256(raw),
            'sha256_snapshot_armazenado': sha256(xz),
            'bytes': len(raw),
            'snapshot': str(path.relative_to(ROOT)),
            'metadados_versao': json.loads(raw)['ListaDocumento']['Metadados'].get('Versao'),
            'issue': spec['issue'],
        }
        print(f'  {tipo}: {len(docs)} registros sha256={meta["especies"][tipo]["sha256"]}', flush=True)
        time.sleep(0.5)
    write_json(catalog_meta_path(), meta)
    return meta


def load_catalog(tipo: str) -> tuple[dict, list[dict]]:
    meta = json.loads(catalog_meta_path().read_text(encoding='utf-8'))
    info = meta['especies'][tipo]
    raw = lzma.decompress((ROOT / info['snapshot']).read_bytes())
    if sha256(raw) != info['sha256']:
        raise SystemExit(f'{tipo}: hash do catálogo diverge')
    return info, parse_lista(raw)


def identity_key(rec: dict) -> tuple:
    return (rec.get('tipo'), rec.get('numero'), rec.get('complemento'), rec.get('dataassinatura'))


def reconcile() -> dict:
    published = existing_federal_slugs()
    summary = {'lote': LOTE, 'reconciliado_em': now_utc(), 'especies': {}}
    limites = {
        'lote': LOTE,
        'gerado_em': now_utc(),
        'RCD': dict(CAMARA_LIMITES_RCD),
        'notas_gerais': [
            'Catálogo é evidência de descoberta, não substitui texto integral nem certifica vigência.',
            'Número igual com espécie ou data diferente não é a mesma identidade.',
            'RSF, RCD e RCN são espécies distintas; não reunir sob identidade numérica comum.',
            'Lista vazia ou intervalo capturado não prova inexistência fora do recorte.',
        ],
    }
    for tipo, spec in SPECIES.items():
        info, docs = load_catalog(tipo)
        keys: dict[tuple, list] = {}
        itens = []
        for rec in docs:
            date = date_iso(rec['dataassinatura'])
            numero = rec.get('numero') or 'sn'
            complemento = rec.get('complemento')
            num_lex = numero_slug(numero, complemento)
            slug = slug_for(tipo, date, numero, complemento)
            key = identity_key(rec)
            keys.setdefault(key, []).append(rec['id'])
            estado = 'publicado' if slug in published else 'identificado-nao-coletado'
            caminho = f'federal/{slug}.md' if estado == 'publicado' else None
            itens.append({
                'senado_id': rec['id'],
                'tipo': tipo,
                'numero': rec.get('numero'),
                'complemento': complemento,
                'data': date,
                'dataassinatura': rec['dataassinatura'],
                'norma': rec.get('norma'),
                'normaNome': rec.get('normaNome'),
                'ementa': rec.get('ementa'),
                'url_registro': f"https://legis.senado.leg.br/norma/{rec['id']}",
                'urn': spec['urn_tmpl'].format(date=date, num=num_lex),
                'slug': slug,
                'estado_coleta': estado,
                'caminho_publicado': caminho,
                'orgao_emissor': spec['orgao_emissor'],
            })
        ambig = [
            {'chave': {'tipo': k[0], 'numero': k[1], 'complemento': k[2], 'dataassinatura': k[3]}, 'ids': ids}
            for k, ids in keys.items() if len(ids) > 1
        ]
        # Colisão de slug (não deveria ocorrer após incluir complemento).
        slug_ids: dict[str, list[str]] = {}
        for item in itens:
            slug_ids.setdefault(item['slug'], []).append(item['senado_id'])
        slug_dups = {s: ids for s, ids in slug_ids.items() if len(ids) > 1}
        if slug_dups:
            raise SystemExit(f'{tipo}: slugs duplicados após complemento: {list(slug_dups)[:5]}')
        datas = sorted(i['data'] for i in itens)
        payload = {
            'tipo': tipo,
            'issue': spec['issue'],
            'descricao': spec['descricao'],
            'orgao_emissor': spec['orgao_emissor'],
            'catalogo_sha256': info['sha256'],
            'catalogo_url': info['url'],
            'catalogo_registros': len(itens),
            'chaves_unicas': len(keys),
            'ambiguidade_ids': ambig,
            'publicados': sum(1 for i in itens if i['estado_coleta'] == 'publicado'),
            'identificados_nao_coletados': sum(1 for i in itens if i['estado_coleta'] != 'publicado'),
            'intervalo_datas': {'inicio': datas[0] if datas else None, 'fim': datas[-1] if datas else None},
            'itens': itens,
        }
        write_json(reconciliacao_path(tipo), payload)
        summary['especies'][tipo] = {
            'registros': payload['catalogo_registros'],
            'chaves_unicas': payload['chaves_unicas'],
            'publicados': payload['publicados'],
            'identificados_nao_coletados': payload['identificados_nao_coletados'],
            'ambiguidades': len(ambig),
            'intervalo_datas': payload['intervalo_datas'],
            'arquivo': str(reconciliacao_path(tipo).relative_to(ROOT)),
        }
        if tipo == 'RCD':
            limites['RCD']['senado_intervalo_observado'] = payload['intervalo_datas']
            limites['RCD']['senado_registros_capturados'] = payload['catalogo_registros']
        print(f"reconcile {tipo}: pub={payload['publicados']} ausentes={payload['identificados_nao_coletados']} ambig={len(ambig)}", flush=True)
    write_json(PROVAS / 'resumo-reconciliacao.json', summary)
    write_json(limites_path(), limites)
    return summary


def detail_json(senado_id: str) -> dict:
    url = f'https://legis.senado.leg.br/dadosabertos/legislacao/{senado_id}.json'
    status, raw, _ = http_get(url)
    if status != 200:
        raise RuntimeError(f'detalhe {senado_id}: HTTP {status}')
    return json.loads(raw)


def normas_payload(urn: str) -> dict:
    url = (
        'https://normas.leg.br/api/public/normas?urn='
        + urllib.parse.quote(urn)
        + '&tipo_documento=maior-detalhe'
    )
    status, raw, _ = http_get(url)
    if status != 200:
        raise RuntimeError(f'normas {urn}: HTTP {status}')
    return json.loads(raw), url, raw


def pick_html_content_url(data: dict) -> str | None:
    enc = data.get('encoding')
    if not enc:
        return None
    items = enc if isinstance(enc, list) else [enc]
    cands = []
    for item in items:
        fmt = item.get('encodingFormat') or ''
        cu = item.get('contentUrl') or ''
        if fmt.endswith('/text/html') and re.search(r'/binario/[a-f0-9-]+/texto$', cu):
            cands.append(item)
    chosen = next((c for c in cands if c.get('version') == 'Current'), None)
    if chosen is None:
        chosen = next((c for c in cands if c.get('version') == 'Original'), None)
    if chosen is None and cands:
        chosen = cands[0]
    if not chosen:
        return None
    return chosen['contentUrl'].replace('/api/binario/', '/api/public/binario/')


def page_publication_ids(senado_id: str) -> list[str]:
    """IDs de publicação linkados na página HTML da norma (podem diferir do JSON)."""
    url = f'https://legis.senado.leg.br/norma/{senado_id}'
    status, html, _ = http_get(url)
    if status != 200 or len(html) < 500:
        return []
    text = html.decode('utf-8', 'replace')
    return sorted(set(re.findall(rf'{re.escape(senado_id)}/publicacao/(\d+)', text)))


def pick_senado_pub_candidates(detail: dict, senado_id: str) -> list[tuple[str, dict | None]]:
    """Candidatos HTML: links da página + IDs do detalhe JSON (PUB/REP/RET primeiro)."""
    docs = detail['DetalheDocumento']['documentos']['documento']
    doc = docs[0] if isinstance(docs, list) else docs
    pubs = doc.get('publicacoes', {}).get('publicacao', [])
    if isinstance(pubs, dict):
        pubs = [pubs]
    by_id = {str(p.get('id')): p for p in pubs}
    ordered: list[tuple[str, dict | None]] = []
    seen: set[str] = set()

    def add(pid: str) -> None:
        if pid in seen:
            return
        seen.add(pid)
        ordered.append((f'https://legis.senado.leg.br/norma/{senado_id}/publicacao/{pid}', by_id.get(pid)))

    for pid in page_publication_ids(senado_id):
        add(pid)
    for pref in ('PUB', 'REP', 'RET'):
        for pub in pubs:
            if pub.get('tipo') == pref and pub.get('temTexto') == 'S':
                add(str(pub['id']))
    for pub in pubs:
        if pub.get('temTexto') == 'S' and pub.get('tipo') not in {'ANX'}:
            add(str(pub['id']))
    return ordered


def extract_senado_fragment(html: bytes) -> bytes:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')
    main = soup.select_one('#conteudoPrincipal')
    if main is None:
        raise RuntimeError('página Senado sem #conteudoPrincipal')
    return f'<html><body>{main.decode_contents()}</body></html>'.encode('utf-8')


def collect_one(tipo: str, senado_id: str, rec: dict) -> dict:
    spec = SPECIES[tipo]
    date = date_iso(rec['dataassinatura'])
    numero = rec.get('numero') or 'sn'
    complemento = rec.get('complemento')
    num_lex = numero_slug(numero, complemento)
    slug = slug_for(tipo, date, numero, complemento)
    urn = spec['urn_tmpl'].format(date=date, num=num_lex)
    out = {
        'tipo': tipo,
        'senado_id': senado_id,
        'slug': slug,
        'urn': urn,
        'numero': num_lex,
        'complemento': complemento,
        'data': date,
        'normaNome': rec.get('normaNome'),
        'ementa': rec.get('ementa'),
        'capturado_em': now_utc(),
    }
    # 1) tentar normas.leg.br
    try:
        data, dados_url, dados_raw = normas_payload(urn)
        out['dados_url'] = dados_url
        out['sha256_dados'] = sha256(dados_raw)
        dados_path = COLETAS_DIR / f'{slug}.dados.json.xz'
        dados_path.write_bytes(lzma.compress(dados_raw, preset=9))
        out['dados_snapshot'] = str(dados_path.relative_to(ROOT))
        content_url = pick_html_content_url(data)
        if content_url:
            status, html, final = http_get(content_url)
            reject = html_rejection_reason(html) if status == 200 else f'HTTP {status}'
            if status == 200 and reject is None:
                frag = html  # binário já é o texto
                snap = COLETAS_DIR / f'{slug}.html.xz'
                snap.write_bytes(lzma.compress(frag, preset=9))
                out.update(
                    fonte_url=final,
                    fonte_orgao='normas.leg.br / Congresso Nacional',
                    fonte_formato='html',
                    charset='utf-8',
                    sha256_fonte=sha256(frag),
                    bytes=len(frag),
                    snapshot=str(snap.relative_to(ROOT)),
                    origem='normas-leg-br-binario',
                )
                # Conferir anexos no detalhe Senado antes de declarar íntegra utilizável.
                try:
                    detail = detail_json(senado_id)
                    detail_raw = json.dumps(detail, ensure_ascii=False).encode('utf-8')
                    detail_path = COLETAS_DIR / f'{slug}.detalhe.json.xz'
                    detail_path.write_bytes(lzma.compress(detail_raw, preset=9))
                    out['detalhe_snapshot'] = str(detail_path.relative_to(ROOT))
                    anexos = inspect_senado_anexos(detail)
                    out['anexos_senado'] = anexos
                    if anexos['anexos_marcados_tem_texto'] > 0:
                        out.update(
                            utilizavel=False,
                            motivo='corpo-html-ok-mas-anexos-essenciais-pendentes',
                            estado_sugerido='anexos-pendentes',
                        )
                        return out
                except Exception as e:
                    out['anexos_inspecao_erro'] = str(e)[:200]
                out['utilizavel'] = True
                return out
            out['normas_html_motivo'] = reject or f'HTTP {status} bytes={len(html)}'
        else:
            out['normas_html_motivo'] = 'sem encoding HTML Current/Original'
    except Exception as e:
        out['normas_erro'] = str(e)[:300]

    # 2) fallback: página de publicação do Senado (HTML)
    try:
        detail = detail_json(senado_id)
        detail_raw = json.dumps(detail, ensure_ascii=False).encode('utf-8')
        detail_path = COLETAS_DIR / f'{slug}.detalhe.json.xz'
        detail_path.write_bytes(lzma.compress(detail_raw, preset=9))
        out['detalhe_snapshot'] = str(detail_path.relative_to(ROOT))
        anexos = inspect_senado_anexos(detail)
        out['anexos_senado'] = anexos
        candidates = pick_senado_pub_candidates(detail, senado_id)
        if not candidates:
            if anexos['anexos_marcados_tem_texto'] and anexos['publicacoes_texto'] == 0:
                out.update(
                    utilizavel=False,
                    motivo='anexos-pendentes-sem-publicacao-html',
                    estado_sugerido='anexos-pendentes',
                )
                return out
            out.update(utilizavel=False, motivo='sem publicacao HTML candidata no detalhe/página')
            return out
        tentativas = []
        for pub_url, pub in candidates:
            status, html, final = http_get(pub_url)
            ctype_html = b'<html' in html[:200].lower() or b'<!DOCTYPE' in html[:200]
            tentativas.append({'url': pub_url, 'http_status': status, 'bytes': len(html), 'html': bool(ctype_html)})
            if status != 200 or not ctype_html:
                continue
            reject = html_rejection_reason(html)
            if reject:
                tentativas[-1]['rejeicao'] = reject
                continue
            try:
                frag = extract_senado_fragment(html)
            except Exception as e:
                tentativas[-1]['extract_erro'] = str(e)[:200]
                continue
            frag_reject = html_rejection_reason(frag)
            if frag_reject:
                tentativas[-1]['rejeicao_fragmento'] = frag_reject
                continue
            snap = COLETAS_DIR / f'{slug}.html.xz'
            snap.write_bytes(lzma.compress(frag, preset=9))
            full = COLETAS_DIR / f'{slug}.pagina.html.xz'
            full.write_bytes(lzma.compress(html, preset=9))
            tipo_pub = (pub or {}).get('tipo') or 'pagina'
            # Anexos essenciais marcados sem HTML próprio: não tratar como íntegra completa.
            if anexos['anexos_marcados_tem_texto'] > 0:
                out.update(
                    fonte_url=final,
                    fonte_orgao=f'Senado Federal — publicação {tipo_pub}',
                    fonte_formato='html',
                    charset='utf-8',
                    sha256_fonte=sha256(frag),
                    sha256_pagina=sha256(html),
                    bytes=len(frag),
                    snapshot=str(snap.relative_to(ROOT)),
                    pagina_snapshot=str(full.relative_to(ROOT)),
                    origem='senado-publicacao-html',
                    publicacao=pub,
                    tentativas_publicacao=tentativas,
                    utilizavel=False,
                    motivo='corpo-html-ok-mas-anexos-essenciais-pendentes',
                    estado_sugerido='anexos-pendentes',
                )
                return out
            out.update(
                fonte_url=final,
                fonte_orgao=f'Senado Federal — publicação {tipo_pub}',
                fonte_formato='html',
                charset='utf-8',
                sha256_fonte=sha256(frag),
                sha256_pagina=sha256(html),
                bytes=len(frag),
                snapshot=str(snap.relative_to(ROOT)),
                pagina_snapshot=str(full.relative_to(ROOT)),
                origem='senado-publicacao-html',
                publicacao=pub,
                tentativas_publicacao=tentativas,
                utilizavel=True,
            )
            return out
        out.update(
            utilizavel=False,
            motivo='publicacoes Senado sem HTML utilizavel',
            tentativas_publicacao=tentativas,
        )
        return out
    except Exception as e:
        out.update(utilizavel=False, motivo=str(e)[:400])
        return out


def load_coleta() -> dict:
    if COLETA_PROGRESS_PATH.is_file():
        return json.loads(COLETA_PROGRESS_PATH.read_text(encoding='utf-8'))
    return {'lote': LOTE, 'coletado_em': now_utc(), 'itens': {}}


def save_coleta(resultados: dict) -> None:
    resultados['atualizado_em'] = now_utc()
    write_json(COLETA_PROGRESS_PATH, resultados)


def collect(
    limit_per_type: dict[str, int] | None = None,
    tipos: list[str] | None = None,
    resume: bool = True,
    all_pending: bool = False,
) -> dict:
    """Coleta retomável. Por padrão reusa `coleta.json` e salva a cada item."""
    COLETAS_DIR.mkdir(parents=True, exist_ok=True)
    resultados = load_coleta() if resume else {'lote': LOTE, 'coletado_em': now_utc(), 'itens': {}}
    if not resume:
        resultados['coletado_em'] = now_utc()
    resultados.setdefault('itens', {})
    selected = tipos or list(SPECIES)
    for tipo in selected:
        if tipo not in SPECIES:
            raise SystemExit(f'tipo desconhecido: {tipo}')
        info, docs = load_catalog(tipo)
        by_id = {d['id']: d for d in docs}
        # Ordem: alvos prioritários do issue, depois catálogo inteiro (datas recentes primeiro).
        priority = COLLECT_TARGETS.get(tipo, [])
        ordered_ids: list[str] = []
        for sid in priority:
            if sid in by_id and sid not in ordered_ids:
                ordered_ids.append(sid)
        recent_first = sorted(docs, key=lambda d: date_iso(d['dataassinatura']), reverse=True)
        for d in recent_first:
            if d['id'] not in ordered_ids:
                ordered_ids.append(d['id'])
        lim = None if all_pending else (limit_per_type or {}).get(tipo)
        if lim is None and not all_pending:
            lim = len(COLLECT_TARGETS.get(tipo, [])) or 5
        attempted = 0
        for sid in ordered_ids:
            if lim is not None and attempted >= lim:
                break
            rec = by_id.get(sid)
            if rec is None:
                continue
            date = date_iso(rec['dataassinatura'])
            slug = slug_for(tipo, date, rec.get('numero') or 'sn', rec.get('complemento'))
            prev = resultados['itens'].get(slug)
            if resume and prev and prev.get('utilizavel') and prev.get('snapshot'):
                snap = ROOT / prev['snapshot']
                if snap.is_file():
                    print(f'  resume-skip {tipo} {sid} {slug}', flush=True)
                    continue
            print(f'collect {tipo} {sid} {rec.get("normaNome")}…', flush=True)
            item = collect_one(tipo, sid, rec)
            resultados['itens'][item['slug']] = item
            save_coleta(resultados)
            attempted += 1
            print(
                f"  -> utilizavel={item.get('utilizavel')} origem={item.get('origem')} "
                f"motivo={item.get('motivo') or item.get('normas_html_motivo')}",
                flush=True,
            )
            time.sleep(0.4)
    save_coleta(resultados)
    return resultados


def discover_camara_rcd() -> dict:
    """Descoberta complementar de RCD pós-1991 a partir do Regimento BD Câmara (ed. 30/2026)."""
    meta = CAMARA_LIMITES_RCD['fonte_complementar_regimento']
    pdf_xz = FONTES_DIR / 'camara-bd-regimento-30ed-2026.pdf.xz'
    txt_xz = FONTES_DIR / 'camara-bd-regimento-30ed-2026.txt.xz'
    epub_xz = FONTES_DIR / 'camara-bd-regimento-30ed-2026.epub.xz'
    for path in (pdf_xz, txt_xz, epub_xz):
        if not path.is_file():
            raise SystemExit(f'evidencia ausente: {path} (baixar bitstreams oficiais do BD Câmara)')
    pdf = lzma.decompress(pdf_xz.read_bytes())
    txt = lzma.decompress(txt_xz.read_bytes())
    epub = lzma.decompress(epub_xz.read_bytes())
    text = txt.decode('utf-8', 'replace')
    # Citações "pela/da/na Resolução nº N de YYYY" sem sufixo -CN.
    pat = re.compile(
        r'(?:pela|da|na)\s+Resolu[cç][aã]o\s+n[ºo°\.]*\s*(\d+)\s+de\s+(\d{4})(?!\s*-CN)',
        re.I,
    )
    cites: dict[tuple[int, int], dict] = {}
    for m in pat.finditer(text):
        numero, ano = int(m.group(1)), int(m.group(2))
        if ano < 1992:
            continue
        key = (numero, ano)
        item = cites.setdefault(
            key,
            {
                'numero': str(numero),
                'ano': ano,
                'especie': 'RCD',
                'orgao_emissor': 'Câmara dos Deputados',
                'estado_descoberta': 'citado-no-regimento-oficial',
                'estado_coleta': 'identificado-nao-coletado',
                'ocorrencias_no_regimento': 0,
                'amostras': [],
                'observacao': (
                    'Citação no Regimento consolidado não substitui a íntegra do ato original; '
                    'data completa e ID oficial ainda pendentes de reconciliação individual.'
                ),
            },
        )
        item['ocorrencias_no_regimento'] += 1
        if len(item['amostras']) < 3:
            item['amostras'].append(re.sub(r'\s+', ' ', m.group(0))[:160])
    # Evidência de capa: série ativa até Resolução 16/2025.
    cover = cites.setdefault(
        (16, 2025),
        {
            'numero': '16',
            'ano': 2025,
            'especie': 'RCD',
            'orgao_emissor': 'Câmara dos Deputados',
            'estado_descoberta': 'citado-na-capa-do-regimento',
            'estado_coleta': 'identificado-nao-coletado',
            'ocorrencias_no_regimento': 0,
            'amostras': [],
            'observacao': (
                'Capa/edição do Regimento declara atualização até a Resolução nº 16 de 2025; '
                'íntegra autônoma ainda não recuperada neste lote.'
            ),
        },
    )
    cover['ocorrencias_no_regimento'] = max(cover['ocorrencias_no_regimento'], 1)
    if not cover['amostras']:
        cover['amostras'].append('alterado até a Resolução nº 16 de 2025')

    # Cruzar com o que o Senado já listou (até 1991) para declarar complementaridade.
    _, senado_docs = load_catalog('RCD')
    senado_keys = {
        (int(d['numero']), int(date_iso(d['dataassinatura'])[:4]))
        for d in senado_docs
        if d.get('numero') and d.get('numero').isdigit()
    }
    for key, item in cites.items():
        item['presente_no_catalogo_senado'] = key in senado_keys

    itens = [cites[k] for k in sorted(cites)]
    payload = {
        'lote': LOTE,
        'issue': 89,
        'gerado_em': now_utc(),
        'papel': 'descoberta-complementar-pos-1991',
        'fonte_oficial': {
            **meta,
            'url_item': meta['url'],
            'snapshot_pdf': str(pdf_xz.relative_to(ROOT)),
            'snapshot_txt': str(txt_xz.relative_to(ROOT)),
            'snapshot_epub': str(epub_xz.relative_to(ROOT)),
            'sha256_pdf': sha256(pdf),
            'sha256_txt': sha256(txt),
            'sha256_epub': sha256(epub),
            'bytes_pdf': len(pdf),
            'bytes_txt': len(txt),
            'bytes_epub': len(epub),
            'edicao_declarada': '30ª edição, 2026; atualizado até Resolução nº 16 de 2025',
        },
        'limites': [
            'Este catálogo é derivado de citações do Regimento consolidado, não de um índice exaustivo da Câmara.',
            'Número/ano citados no consolidado não equivalem à publicação da íntegra do ato modificador.',
            'Não prova inexistência de resoluções fora das citações extraídas.',
            'LexML e listagens /legin/fed/rescad/ estavam inacessíveis (WAF/403) nesta captura.',
            'Projetos de Resolução (PRC) na API de proposições não são atos promulgados.',
        ],
        'senado_rcd_intervalo': CAMARA_LIMITES_RCD.get('senado_intervalo_observado'),
        'contagem': {
            'citacoes_unicas_numero_ano_pos_1991': len(itens),
            'tambem_no_senado': sum(1 for i in itens if i['presente_no_catalogo_senado']),
            'somente_descoberta_camara': sum(1 for i in itens if not i['presente_no_catalogo_senado']),
        },
        'itens': itens,
    }
    write_json(CAMARA_RCD_DISCOVERY_PATH, payload)
    # Atualiza limites com ponteiro da descoberta.
    if limites_path().is_file():
        limites = json.loads(limites_path().read_text(encoding='utf-8'))
    else:
        limites = {'lote': LOTE, 'gerado_em': now_utc(), 'RCD': dict(CAMARA_LIMITES_RCD)}
    limites['RCD'] = dict(limites.get('RCD') or CAMARA_LIMITES_RCD)
    limites['RCD']['descoberta_camara_pos_1991'] = {
        'arquivo': str(CAMARA_RCD_DISCOVERY_PATH.relative_to(ROOT)),
        'citacoes_unicas': payload['contagem']['citacoes_unicas_numero_ano_pos_1991'],
        'gerado_em': payload['gerado_em'],
        'estado': 'catalogo-parcial-por-citacoes-do-regimento',
    }
    limites['atualizado_em'] = now_utc()
    write_json(limites_path(), limites)
    print(json.dumps(payload['contagem'], ensure_ascii=False))
    return payload


def build_markdown(item: dict, html: bytes) -> tuple[str, dict]:
    tipo = item['tipo']
    spec = SPECIES[tipo]
    charset = item.get('charset') or 'utf-8'
    url = item['fonte_url']
    conv = nl.convert_html(html, charset, url)
    try:
        body = nl.blocks_to_markdown(conv.blocks, spec['title_pattern'])
    except ValueError:
        # Algumas páginas começam pela ementa; injeta epígrafe do catálogo no fragmento lógico.
        title = item.get('normaNome') or f"{spec['descricao']} nº {item['numero']}"
        body = '# ' + title + '\n\n' + '\n\n'.join(conv.blocks) + '\n'
    src_fold = nl.strip_fold(nl.source_text_chars_from_html(html, charset))
    md_fold = nl.strip_fold(nl.md_text_all(body))
    if src_fold != md_fold:
        # Se injetamos título, o fold do corpo ainda deve cobrir a fonte; recuar título artificial.
        if body.startswith('# ') and src_fold == nl.strip_fold(nl.md_text_all('\n\n'.join(conv.blocks) + '\n')):
            pass  # título editorial explícito; corpo fiel
        else:
            raise RuntimeError(f"{item['slug']}: divergência textual fonte↔Markdown")

    nota = (
        f"> **Edição oficial — {spec['descricao']}.** "
        f"Órgão emissor: {spec['orgao_emissor']}. "
        f"Fonte: {url} (capturada em {item['capturado_em']}, "
        f"SHA-256 da fonte `{item['sha256_fonte']}`). "
        f"Snapshot: `{item['snapshot']}`. "
        f"Registro Senado: https://legis.senado.leg.br/norma/{item['senado_id']}. "
        f"O acervo não certifica vigência.\n"
    )
    if item.get('ementa'):
        nota += f">\n> Ementa do catálogo do Senado: {item['ementa']}\n"

    corpo = (
        f"<!-- nota-edicao:inicio -->\n\n{nota}\n<!-- nota-edicao:fim -->\n\n{body.lstrip()}"
    )
    meta = {
        'id': item['slug'],
        'norma_id': item['slug'],
        'norma_tipo': spec['norma_tipo'],
        'norma_numero': str(item['numero']),
        'norma_data': item['data'],
        'titulo': item.get('normaNome') or f"{spec['descricao']} nº {item['numero']}",
        'esfera': 'federal',
        'orgao_emissor': spec['orgao_emissor'],
        'especie_codigo_senado': tipo,
        'senado_id': item['senado_id'],
        'urn': item['urn'],
        'edicao_id': f"{item['slug']}@original",
        'edicao_tipo': 'historica',
        'edicao_integral': True,
        'fonte_orgao': item.get('fonte_orgao') or 'desconhecido',
        'fonte_url': url,
        'fonte_formato': 'html',
        'fonte_conferencia': 'nenhuma',
        'capturado_em': item['capturado_em'],
        'sha256_fonte': item['sha256_fonte'],
        'situacao': 'nao-informada',
        'situacao_fundamento': 'desconhecido',
        'vigencia_certificada': False,
        'texto_riscado': False,
        'anexos_no_corpo': len(re.findall(r'(?im)^(?:#+\s*)?ANEXO\b', corpo)),
        'tabelas': len(conv.tables),
        'imagens_omitidas': len(conv.images),
        'efeitos_diferidos': 'preservados-nas-notas-do-texto',
        'sha256_markdown': sha256(corpo.encode('utf-8')),
        'manifesto': str(manifesto_path().relative_to(ROOT)),
        'contrato_versao': CONTRACT_VERSION,
    }
    fm = '---\n' + '\n'.join(
        f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in meta.items()
    ) + '\n---\n\n'
    title_in_blocks = any(
        re.match(spec['title_pattern'], re.sub(r'\s+', ' ', nl.md_plain(b, True)).strip(), re.I)
        for b in conv.blocks
    )
    return fm + corpo, {
        'slug': item['slug'],
        'fonte_fold_chars': len(src_fold),
        'markdown_fold_chars': len(nl.strip_fold(nl.md_text_all(corpo))),
        'blocos': len(conv.blocks),
        'tabelas': len(conv.tables),
        'imagens': len(conv.images),
        'title_injected': not title_in_blocks,
    }


def build() -> dict:
    coleta = json.loads((PROVAS / 'coleta.json').read_text(encoding='utf-8'))
    fontes = {}
    manifesto = {
        'lote': LOTE,
        'issues': [65, 66, 89, 94],
        'gerado_em': now_utc(),
        'documentos': [],
    }
    cobertura = {'lote': LOTE, 'itens': {}}
    publicados = []
    for slug, item in coleta['itens'].items():
        if not item.get('utilizavel'):
            continue
        html = lzma.decompress((ROOT / item['snapshot']).read_bytes())
        if sha256(html) != item['sha256_fonte']:
            raise SystemExit(f'{slug}: hash fonte diverge')
        markdown, proof = build_markdown(item, html)
        path = FED / f'{slug}.md'
        path.write_text(markdown, encoding='utf-8')
        meta, body = nl.parse_frontmatter(markdown)
        assert meta['sha256_markdown'] == sha256(body.encode('utf-8'))
        fontes[slug] = {
            'url': item['fonte_url'],
            'capturado_em': item['capturado_em'],
            'sha256': item['sha256_fonte'],
            'sha256_snapshot_armazenado': sha256((ROOT / item['snapshot']).read_bytes()),
            'bytes': item['bytes'],
            'snapshot': item['snapshot'],
            'origem': item.get('origem'),
            'senado_id': item['senado_id'],
            'tipo': item['tipo'],
            'charset': item.get('charset', 'utf-8'),
            'ementa': item.get('ementa'),
            'normaNome': item.get('normaNome'),
            'numero': str(item['numero']),
            'data': item['data'],
            'urn': item['urn'],
        }
        manifesto['documentos'].append({
            'id': slug,
            'arquivo': str(path.relative_to(ROOT)),
            'tipo': item['tipo'],
            'senado_id': item['senado_id'],
            'urn': item['urn'],
            'norma': {'numero': str(item['numero']), 'data': item['data'], 'titulo': item.get('normaNome')},
            'fonte': slug,
            'sha256_fonte': item['sha256_fonte'],
            'sha256_markdown': meta['sha256_markdown'],
        })
        cobertura['itens'][slug] = proof
        publicados.append(slug)
        print(f'built {slug}', flush=True)
    write_json(fontes_json_path(), fontes)
    write_json(manifesto_path(), manifesto)
    write_json(cobertura_path(), cobertura)
    # atualiza estados na reconciliacao
    published = existing_federal_slugs()
    resumo = {'lote': LOTE, 'reconciliado_em': now_utc(), 'especies': {}}
    for tipo in SPECIES:
        path = reconciliacao_path(tipo)
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding='utf-8'))
        coleta_itens = coleta.get('itens', {})
        for item in data['itens']:
            if item['slug'] in published:
                item['estado_coleta'] = 'publicado'
                item['caminho_publicado'] = f"federal/{item['slug']}.md"
            else:
                col = coleta_itens.get(item['slug']) or {}
                if col.get('estado_sugerido') == 'anexos-pendentes' or (
                    col.get('motivo') or ''
                ).startswith('corpo-html-ok-mas-anexos') or (
                    col.get('motivo') == 'anexos-pendentes-sem-publicacao-html'
                ):
                    item['estado_coleta'] = 'anexos-pendentes'
                elif col and col.get('utilizavel') is False and col.get('motivo') == 'sem publicacao HTML candidata no detalhe/página':
                    item['estado_coleta'] = 'fonte-sem-html'
                elif item['estado_coleta'] == 'publicado':
                    item['estado_coleta'] = 'identificado-nao-coletado'
                item['caminho_publicado'] = None
        data['publicados'] = sum(1 for i in data['itens'] if i['estado_coleta'] == 'publicado')
        data['anexos_pendentes'] = sum(1 for i in data['itens'] if i['estado_coleta'] == 'anexos-pendentes')
        data['fonte_sem_html'] = sum(1 for i in data['itens'] if i['estado_coleta'] == 'fonte-sem-html')
        data['identificados_nao_coletados'] = sum(
            1 for i in data['itens'] if i['estado_coleta'] == 'identificado-nao-coletado'
        )
        write_json(path, data)
        resumo['especies'][tipo] = {
            'registros': data['catalogo_registros'],
            'chaves_unicas': data['chaves_unicas'],
            'publicados': data['publicados'],
            'identificados_nao_coletados': data['identificados_nao_coletados'],
            'ambiguidades': len(data['ambiguidade_ids']),
            'intervalo_datas': data['intervalo_datas'],
            'arquivo': str(path.relative_to(ROOT)),
        }
    write_json(PROVAS / 'resumo-reconciliacao.json', resumo)
    return {'publicados': publicados, 'manifesto': len(manifesto['documentos'])}


def verify() -> None:
    meta = json.loads(catalog_meta_path().read_text(encoding='utf-8'))
    for tipo, info in meta['especies'].items():
        raw = lzma.decompress((ROOT / info['snapshot']).read_bytes())
        assert sha256(raw) == info['sha256'], tipo
        assert len(parse_lista(raw)) == info['registros'], tipo
        rec = json.loads(reconciliacao_path(tipo).read_text(encoding='utf-8'))
        assert rec['catalogo_registros'] == info['registros'], tipo
        assert rec['catalogo_registros'] == len(rec['itens']), tipo
        # cobertura por identidade: todo item tem estado e slug
        for item in rec['itens']:
            assert item['senado_id'] and item['slug'] and item['estado_coleta']
            assert item['estado_coleta'] in {
                'publicado', 'identificado-nao-coletado', 'anexos-pendentes', 'fonte-sem-html',
            }
            if item['estado_coleta'] == 'publicado':
                assert (ROOT / item['caminho_publicado']).is_file(), item['slug']
    # markdown publicados do lote
    manifesto = json.loads(manifesto_path().read_text(encoding='utf-8'))
    fontes = json.loads(fontes_json_path().read_text(encoding='utf-8'))
    for doc in manifesto['documentos']:
        slug = doc['id']
        path = ROOT / doc['arquivo']
        text = path.read_text(encoding='utf-8')
        meta_fm, body = nl.parse_frontmatter(text)
        assert meta_fm['sha256_markdown'] == sha256(body.encode('utf-8')), slug
        assert meta_fm['vigencia_certificada'] is False
        assert meta_fm['especie_codigo_senado'] in SPECIES
        html = lzma.decompress((ROOT / fontes[slug]['snapshot']).read_bytes())
        assert sha256(html) == fontes[slug]['sha256'], slug
        reject = html_rejection_reason(html)
        assert reject is None, f'{slug}: fonte rejeitavel ({reject})'
        # reconversão
        item = {
            'slug': slug,
            'tipo': fontes[slug]['tipo'],
            'fonte_url': fontes[slug]['url'],
            'charset': fontes[slug]['charset'],
            'normaNome': fontes[slug].get('normaNome') or meta_fm['titulo'],
            'numero': fontes[slug].get('numero') or meta_fm['norma_numero'],
            'data': fontes[slug].get('data') or meta_fm['norma_data'],
            'urn': fontes[slug].get('urn') or meta_fm['urn'],
            'ementa': fontes[slug].get('ementa'),
            'capturado_em': fontes[slug]['capturado_em'],
            'sha256_fonte': fontes[slug]['sha256'],
            'snapshot': fontes[slug]['snapshot'],
            'senado_id': fontes[slug]['senado_id'],
            'fonte_orgao': meta_fm.get('fonte_orgao'),
        }
        md2, _ = build_markdown(item, html)
        assert md2 == text, f'{slug}: markdown diverge da reconversão'
        # Identidade semântica mínima independente do conversor.
        plain = re.sub(r'<[^>]+>', ' ', html.decode(fontes[slug]['charset'], 'replace'))
        plain = re.sub(r'\s+', ' ', plain)
        assert str(meta_fm['norma_numero']).split('-')[0] in plain or meta_fm['titulo'][:20].upper() in plain.upper(), slug
    # espécies distintas
    tipos_pub = {doc['tipo'] for doc in manifesto['documentos']}
    assert tipos_pub <= set(SPECIES)
    # Descoberta Câmara pós-1991 (#89) deve existir e declarar limites.
    if CAMARA_RCD_DISCOVERY_PATH.is_file():
        disc = json.loads(CAMARA_RCD_DISCOVERY_PATH.read_text(encoding='utf-8'))
        assert disc['contagem']['citacoes_unicas_numero_ano_pos_1991'] >= 1
        assert any(i['numero'] == '16' and i['ano'] == 2025 for i in disc['itens'])
        pdf = lzma.decompress((ROOT / disc['fonte_oficial']['snapshot_pdf']).read_bytes())
        assert sha256(pdf) == disc['fonte_oficial']['sha256_pdf']
    print('verify ok:', {
        'catalogos': {t: meta['especies'][t]['registros'] for t in SPECIES},
        'markdown_lote': len(manifesto['documentos']),
        'descoberta_camara_rcd': CAMARA_RCD_DISCOVERY_PATH.is_file(),
    })


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'cmd',
        choices=(
            'capture', 'reconcile', 'collect', 'build', 'verify',
            'discover-camara-rcd', 'all-offline',
        ),
    )
    parser.add_argument('--dlg-limit', type=int, default=None)
    parser.add_argument('--rsf-limit', type=int, default=None)
    parser.add_argument('--rcd-limit', type=int, default=None)
    parser.add_argument('--rcn-limit', type=int, default=None)
    parser.add_argument('--tipos', default=None, help='CSV de espécies, ex.: RCN,RCD')
    parser.add_argument('--all-pending', action='store_true', help='Coletar todo o catálogo pendente das espécies escolhidas')
    parser.add_argument('--no-resume', action='store_true', help='Ignorar coleta.json existente')
    args = parser.parse_args(argv)
    PROVAS.mkdir(parents=True, exist_ok=True)
    if args.cmd == 'capture':
        capture()
    elif args.cmd == 'reconcile':
        reconcile()
    elif args.cmd == 'collect':
        limits = {}
        if args.dlg_limit is not None:
            limits['DLG'] = args.dlg_limit
        if args.rsf_limit is not None:
            limits['RSF'] = args.rsf_limit
        if args.rcd_limit is not None:
            limits['RCD'] = args.rcd_limit
        if args.rcn_limit is not None:
            limits['RCN'] = args.rcn_limit
        tipos = [t.strip().upper() for t in args.tipos.split(',')] if args.tipos else None
        collect(
            limits or None,
            tipos=tipos,
            resume=not args.no_resume,
            all_pending=args.all_pending,
        )
    elif args.cmd == 'build':
        print(build())
    elif args.cmd == 'verify':
        verify()
    elif args.cmd == 'discover-camara-rcd':
        discover_camara_rcd()
    elif args.cmd == 'all-offline':
        reconcile()
        build()
        verify()


if __name__ == '__main__':
    main(sys.argv[1:])
