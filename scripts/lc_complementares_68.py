"""Build and verify issue #68 edition and provenance records offline.

Inputs are the pinned official captures under provas/lc-complementares-68.
This module never fetches sources and never infers vigencia or historical series.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/lc-complementares-68'
FONTES_PATH = PROVAS / 'fontes.json'
RECON_PATH = PROVAS / 'reconciliacao-identidades.json'
RETIFICACAO_REL = 'federal/edicoes/br-federal-lei-complementar-1962-07-17-1-retificacao-1962-07-24.md'
CAMARA_ORIGINAL_URL = (
    'https://www2.camara.leg.br/legin/fed/leicom/1960-1969/'
    'leicomplementar-1-17-julho-1962-541564-publicacaooriginal-46773-pl.html'
)
CAMARA_RETIFICACAO_URL = (
    'https://www2.camara.leg.br/legin/fed/leicom/1960-1969/'
    'leicomplementar-1-17-julho-1962-541564-retificacao-46775-pl.html'
)
CAMARA_DADOS_URL = (
    'https://www2.camara.leg.br/legin/fed/leicom/1960-1969/'
    'leicomplementar-1-17-julho-1962-541564-norma-pl.html'
)
PLANALTO_RETIFICACAO_URL = 'https://www.planalto.gov.br/ccivil_03/leis/lcp/ret/retlcp01-62.htm'
LC62 = 'br-federal-lei-complementar-1962-07-17-1'
LC67 = 'br-federal-lei-complementar-1967-11-09-1'
LC115 = 'br-federal-lei-complementar-2002-12-26-115'
LC147 = 'br-federal-lei-complementar-2014-08-07-147'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_frontmatter(path: Path, updates: dict) -> tuple[dict, str]:
    old = path.read_text(encoding='utf-8')
    try:
        meta, body = nl.parse_frontmatter(old)
    except ValueError:
        meta, body = {}, old
    if meta is None:
        meta, body = {}, old
    meta.update(updates)
    meta['sha256_markdown'] = sha(body.encode('utf-8'))
    rendered = '---\n' + '\n'.join(
        f'{key}: {json.dumps(value, ensure_ascii=False)}' for key, value in meta.items()
    ) + '\n---\n\n' + body
    path.write_text(rendered, encoding='utf-8')
    return meta, body


def _source_text(raw: bytes) -> str:
    soup = BeautifulSoup(raw, 'lxml')
    area = soup.select_one('.documentContent')
    if area is None:
        raise ValueError('Câmara: .documentContent ausente')
    return re.sub(r'\s+', ' ', area.get_text(' ', strip=True)).strip()


def build() -> None:
    sources = json.loads(FONTES_PATH.read_text(encoding='utf-8'))
    lc62 = sources[LC62]
    original_rel = 'provas/lc-complementares-68/fontes/camara-lcp01-62-publicacao-original.html.xz'
    correction_rel = 'provas/lc-complementares-68/fontes/camara-lcp01-62-retificacao.html.xz'
    data_rel = 'provas/lc-complementares-68/fontes/camara-lcp01-62-dados-da-norma.html.xz'
    original_raw = lzma.decompress((ROOT / original_rel).read_bytes())
    correction_raw = lzma.decompress((ROOT / correction_rel).read_bytes())
    data_raw = lzma.decompress((ROOT / data_rel).read_bytes())
    original_sha = sha(original_raw)
    correction_sha = sha(correction_raw)
    original_snapshot_sha = sha((ROOT / original_rel).read_bytes())
    correction_snapshot_sha = sha((ROOT / correction_rel).read_bytes())
    data_sha = sha(data_raw)
    data_snapshot_sha = sha((ROOT / data_rel).read_bytes())
    captured_at = {
        'original': '2026-11-05T14:01:15Z',
        'retificacao': '2026-11-05T14:01:16Z',
        'dados': '2026-11-05T14:11:43Z',
    }
    lc62['dados_norma_camara'] = {
        'fonte_url': CAMARA_DADOS_URL,
        'papel': 'registro-de-origem-e-observacao-da-norma',
        'capturado_em': captured_at['dados'],
        'sha256_fonte': data_sha,
        'snapshot_html': data_rel,
        'sha256_snapshot_html': data_snapshot_sha,
        'id_norma_camara': '541564',
    }
    lc62['publicacao_original_camara'] = {
        'fonte_url': CAMARA_ORIGINAL_URL,
        'papel': 'publicacao-original-do-DOU',
        'publicacao_dou': 'Diário Oficial da União, Seção 1, 17/07/1962, p. 7597',
        'capturado_em': captured_at['original'],
        'sha256_fonte': original_sha,
        'snapshot_html': original_rel,
        'sha256_snapshot_html': original_snapshot_sha,
        'id_publicacao_camara': '46773',
    }
    lc62['retificacao_camara'] = {
        'fonte_url': CAMARA_RETIFICACAO_URL,
        'papel': 'retificacao-publicada-no-DOU',
        'publicacao_dou': 'Diário Oficial da União, Seção 1, 24/07/1962, p. 7837',
        'capturado_em': captured_at['retificacao'],
        'sha256_fonte': correction_sha,
        'snapshot_html': correction_rel,
        'sha256_snapshot_html': correction_snapshot_sha,
        'id_publicacao_camara': '46775',
        'pagina_retificacao_planalto': PLANALTO_RETIFICACAO_URL,
        'instrucoes_literais': [
            'Após a ementa, inclua-se: O Presidente da República',
            'Em seguida ao preâmbulo, exclua-se: O congresso Nacional decreta:',
        ],
        'edicao_markdown': RETIFICACAO_REL,
    }
    sources[LC62] = lc62

    issuer_evidence = {
        LC115: (
            'corpo da captura oficial Senado: “O PRESIDENTE DA REPÚBLICA … '
            'Faço saber que o Congresso Nacional decreta e eu sanciono”; '
            f"{sources[LC115]['fonte_url']} sha256={sources[LC115]['sha256_fonte']}"
        ),
        LC147: (
            'corpo da captura oficial Planalto: “A PRESIDENTA DA REPÚBLICA Faço saber '
            'que o Congresso Nacional decreta e eu sanciono”; '
            f"{sources[LC147]['fonte_url']} sha256={sources[LC147]['sha256_fonte']}"
        ),
        LC62: (
            'corpo da captura oficial Planalto: “O Presidente da República Faço saber '
            'que o Congresso Nacional decreta e eu sanciono”; '
            f"{lc62['fonte_url']} sha256={lc62['sha256_fonte']}"
        ),
    }
    for slug, record in ((LC115, sources[LC115]), (LC147, sources[LC147]), (LC62, lc62)):
        senate_ids = {LC115: '572870', LC147: '572902', LC62: '30812083'}
        source_names = {
            LC115: 'Senado Federal — normas.leg.br',
            LC147: 'Presidência da República — Planalto',
            LC62: 'Presidência da República — Planalto',
        }
        record['senadoId'] = senate_ids[slug]
        record['fonte_orgao'] = source_names[slug]
        path = ROOT / f'federal/{slug}.md'
        current, body = nl.parse_frontmatter(path.read_text(encoding='utf-8'))
        sources[slug]['sha256_markdown'] = sha(body.encode('utf-8'))
        issuer = issuer_evidence[slug]
        fields = {
            'orgao_emissor': 'Congresso Nacional',
            'edicao_tipo': 'original' if slug == LC115 else current.get('edicao_tipo', 'desconhecida'),
            'serie_historica': 'desconhecido' if slug != LC62 else 'lei-complementar-ao-ato-adicional',
            'senado_id': senate_ids[slug],
            'campo_fontes': {
                **(current.get('campo_fontes') or {}),
                'orgao_emissor': issuer,
                'fonte_orgao': f"fontes.json#{slug}.fonte_orgao / fonte_url",
                'edicao_tipo': (
                    f"fontes.json#{slug}.edicao / versao"
                    if slug != LC62 else f"fontes.json#{slug}.versao"
                ),
                'serie_historica': (
                    f"Câmara, dados da norma, observação literal ‘Publicada no DO como Lei Complementar ao Ato Adicional’; "
                    f"{CAMARA_DADOS_URL} sha256={data_sha}"
                    if slug == LC62 else 'desconhecido-explicito: nenhuma série foi comprovada nas capturas desta inclusão'
                ),
                'senado_id': f"catálogo oficial do Senado: {record.get('senadoId') or ('572870' if slug == LC115 else '572902' if slug == LC147 else '30812083')}",
            },
        }
        if slug == LC62:
            fields['relacoes'] = [{
                'tipo': 'retificacao',
                'origem': f'{LC62}@retificacao-1962-07-24',
                'destino': current.get('edicao_id') or f'{LC62}@planalto',
                'dispositivo': (
                    'DOU 24/07/1962, p. 7837: após a ementa, incluir “O Presidente da República”; '
                    'após o preâmbulo, excluir “O congresso Nacional decreta:”.'
                ),
                'escopo_cobertura': 'parcial',
            }]
            fields['campo_fontes']['relacoes'] = (
                f'{CAMARA_RETIFICACAO_URL} sha256={correction_sha}; relação literal com a edição Planalto identificada'
            )
            fields['edicao_relacionada'] = 'retificacao-1962-07-24-incorporada-no-texto-Planalto'
        path_meta, rewritten_body = write_frontmatter(path, fields)
        if rewritten_body != body:
            raise AssertionError(f'{slug}: o corpo Markdown foi alterado')
        sources[slug]['sha256_markdown'] = path_meta['sha256_markdown']

    # LC 1/1967 stays separate; its historical series and source are not inferred.
    lc67_path = ROOT / f'federal/{LC67}.md'
    lc67_old = lc67_path.read_text(encoding='utf-8')
    try:
        _, lc67_body = nl.parse_frontmatter(lc67_old)
    except ValueError:
        lc67_body = lc67_old
    _lc67_meta, rewritten_lc67_body = write_frontmatter(lc67_path, {
        'norma_id': LC67,
        'edicao_id': f'{LC67}@caminho-publicado',
        'norma_tipo': 'lei-complementar',
        'norma_numero': '1',
        'norma_data': '1967-11-09',
        'orgao_emissor': 'desconhecido',
        'fonte_orgao': 'desconhecido',
        'fonte_url': 'desconhecido',
        'edicao_tipo': 'desconhecida',
        'serie_historica': 'desconhecido',
        'situacao': 'nao-informada',
        'vigencia_certificada': False,
        'campo_fontes': {
            'norma_id': 'caminho-canonico',
            'edicao_id': 'caminho-canonico',
            'norma_tipo': 'caminho-canonico',
            'norma_numero': 'caminho-canonico-e-epigrafe-literal',
            'norma_data': 'caminho-canonico-e-epigrafe-literal',
            'orgao_emissor': 'desconhecido-explicito: nenhuma captura validada nesta entrega',
            'fonte_orgao': 'desconhecido-explicito: nenhuma captura validada nesta entrega',
            'fonte_url': 'desconhecido-explicito: nenhuma captura validada nesta entrega',
            'edicao_tipo': 'desconhecido-explicito: texto de edicao nao revalidado nesta entrega',
            'serie_historica': 'desconhecido-explicito: nao derivada do ano ou do numero',
            'situacao': 'desconhecido-explicito',
            'vigencia_certificada': 'contrato-global-sempre-false',
        },
    })
    if rewritten_lc67_body != lc67_body:
        raise AssertionError('LC 1/1967: o corpo publicado foi alterado')

    correction = _source_text(correction_raw)
    if 'Na página 7.597, 1ª coluna, após a ementa, inclua-se:' not in correction:
        raise ValueError('texto da retificação não reconhecido')
    if 'O Presidente da República - Em seguida ao preâmbulo, exclua-se:' not in correction:
        raise ValueError('instrução da retificação ausente')
    if 'O congresso Nacional decreta:' not in correction:
        raise ValueError('texto a excluir ausente da retificação')
    body = (
        '# LEI COMPLEMENTAR Nº 1, DE 17 DE JULHO DE 1962 — Retificação\n\n'
        'Complementa a organização do sistema parlamentar de Govêrno, eestabelece outras disposições.\n\n'
        '(Publicado no Diário Oficial de 17 de julho de 1962 - Seção I - Parte I)\n\n'
        'RETIFICAÇÃO\n\n'
        'Na página 7.597, 1ª coluna, após a ementa, inclua-se:\n\n'
        'O Presidente da República - Em seguida ao preâmbulo, exclua-se: '
        'O congresso Nacional decreta:\n'
    )
    ret_meta = {
        'norma_id': LC62,
        'edicao_id': f'{LC62}@retificacao-1962-07-24',
        'norma_tipo': 'lei-complementar',
        'norma_numero': '1',
        'norma_data': '1962-07-17',
        'data_publicacao': '1962-07-24',
        'titulo': 'Retificação da Lei Complementar nº 1, de 17 de julho de 1962',
        'esfera': 'federal',
        'orgao_emissor': 'desconhecido',
        'fonte_orgao': 'Câmara dos Deputados — Legislação Informatizada',
        'serie_historica': 'lei-complementar-ao-ato-adicional',
        'edicao_tipo': 'retificacao',
        'edicao_integral': True,
        'fonte_url': CAMARA_RETIFICACAO_URL,
        'capturado_em': captured_at['retificacao'],
        'sha256_fonte': correction_sha,
        'senado_id': '30812083',
        'urn': 'urn:lex:br:federal:lei.complementar:1962-07-17;1',
        'situacao': 'nao-informada',
        'vigencia_certificada': False,
        'relacoes': [{
            'tipo': 'retificacao',
            'origem': f'{LC62}@retificacao-1962-07-24',
            'destino': f'{LC62}@planalto',
            'dispositivo': 'DOU 24/07/1962, p. 7837; inclui a fórmula presidencial e exclui a duplicação do decreto do Congresso.',
            'escopo_cobertura': 'parcial',
        }],
        'campo_fontes': {
            'norma_id': 'catálogo oficial do Senado: 30812083',
            'edicao_id': f'{CAMARA_RETIFICACAO_URL}#id-publicacao-46775',
            'norma_tipo': 'catálogo oficial do Senado: LCP',
            'norma_numero': 'catálogo oficial do Senado: 30812083',
            'norma_data': 'Câmara: publicação original DOU 17/07/1962, p. 7597',
            'data_publicacao': f'{CAMARA_RETIFICACAO_URL} sha256={correction_sha}',
            'orgao_emissor': 'desconhecido-explicito: a página da retificação não identifica emissor distinto',
            'fonte_orgao': CAMARA_RETIFICACAO_URL,
            'serie_historica': f'{CAMARA_DADOS_URL} observação literal; sha256={data_sha}',
            'edicao_tipo': 'identificação literal Câmara: Retificação; DOU 24/07/1962 p. 7837',
            'edicao_integral': 'documento integral da retificação capturada',
            'fonte_url': 'frontmatter: fonte oficial da captura Câmara',
            'capturado_em': 'registro de captura local UTC',
            'sha256_fonte': 'hash SHA-256 do HTML integral da Câmara',
            'senado_id': 'catálogo oficial do Senado: 30812083',
            'urn': 'norma identificada pelo catálogo e data+número',
            'relacoes': f'{CAMARA_RETIFICACAO_URL} sha256={correction_sha}',
        },
        'sha256_markdown': sha(body.encode('utf-8')),
        'manifesto': 'provas/lc-complementares-68/reconciliacao-identidades.json',
        'contrato_versao': 1,
        'fonte_snapshot_html': lc62['retificacao_camara']['snapshot_html'],
        'sha256_snapshot_html': correction_snapshot_sha,
        'publicacao_dou': lc62['retificacao_camara']['publicacao_dou'],
    }
    path = ROOT / RETIFICACAO_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '---\n' + '\n'.join(
            f'{key}: {json.dumps(value, ensure_ascii=False)}' for key, value in ret_meta.items()
        ) + '\n---\n\n' + body,
        encoding='utf-8',
    )
    lc62['retificacao_camara']['sha256_markdown'] = ret_meta['sha256_markdown']
    lc62['retificacao_camara']['sha256_markdown_body'] = ret_meta['sha256_markdown']
    lc62['retificacao_camara']['edicao_id'] = ret_meta['edicao_id']
    lc62['retificacao_camara']['norma_id'] = ret_meta['norma_id']
    nl.write_json(FONTES_PATH, sources)

    recon = json.loads(RECON_PATH.read_text(encoding='utf-8'))
    entry = next(item for item in recon['identidades'] if item['id'] == LC62)
    entry['sha256_markdown'] = nl.sha256(nl.parse_frontmatter((ROOT / f'federal/{LC62}.md').read_text())[1].encode())
    entry['edicoes_relacionadas'] = [
        {
            'edicao_id': f'{LC62}@planalto',
            'tipo': 'consolidada',
            'arquivo': f'federal/{LC62}.md',
            'incorpora_retificacao': True,
            'prova': f"fontes.json#{LC62}.retificacao_camara e snapshot {lc62['snapshot_html']}",
        },
        {
            'edicao_id': ret_meta['edicao_id'],
            'tipo': 'retificacao',
            'arquivo': RETIFICACAO_REL,
            'publicacao_dou': lc62['retificacao_camara']['publicacao_dou'],
            'sha256_fonte': correction_sha,
            'sha256_markdown': ret_meta['sha256_markdown'],
        },
    ]
    rectification_limit = (
        'LC 1/1962: a retificação de 24/07/1962 é edição separada; o texto Planalto atual incorpora '
        'as duas instruções comparadas às capturas originais e da retificação da Câmara.'
    )
    if rectification_limit not in recon['limites']:
        recon['limites'].append(rectification_limit)
    nl.write_json(RECON_PATH, recon)


def verify() -> None:
    sources = json.loads(FONTES_PATH.read_text(encoding='utf-8'))
    lc62 = sources[LC62]
    original = lzma.decompress((ROOT / lc62['publicacao_original_camara']['snapshot_html']).read_bytes())
    correction = lzma.decompress((ROOT / lc62['retificacao_camara']['snapshot_html']).read_bytes())
    original_text = _source_text(original)
    correction_text = _source_text(correction)
    data_html = lzma.decompress((ROOT / lc62['dados_norma_camara']['snapshot_html']).read_bytes())
    data_text = re.sub(r'\s+', ' ', BeautifulSoup(data_html, 'lxml').get_text(' ', strip=True))
    current_planalto = lzma.decompress((ROOT / lc62['snapshot_html']).read_bytes())
    planalto_text = re.sub(r'\s+', ' ', BeautifulSoup(current_planalto, 'lxml').get_text(' ', strip=True))
    if sha(original) != lc62['publicacao_original_camara']['sha256_fonte']:
        raise AssertionError('hash da publicação original diverge')
    if sha(correction) != lc62['retificacao_camara']['sha256_fonte']:
        raise AssertionError('hash da retificação diverge')
    if sha(data_html) != lc62['dados_norma_camara']['sha256_fonte']:
        raise AssertionError('hash dos dados da norma Câmara diverge')
    if sha(current_planalto) != lc62['sha256_fonte']:
        raise AssertionError('hash do Planalto LC 1/1962 diverge')
    assert 'Faço saber que o Congresso Nacional decreta e eu sanciono' in original_text
    assert 'O Congresso Nacional decreta:' in original_text
    assert 'Na página 7.597, 1ª coluna, após a ementa, inclua-se:' in correction_text
    assert 'O Presidente da República - Em seguida ao preâmbulo, exclua-se:' in correction_text
    assert 'O congresso Nacional decreta:' in correction_text
    assert 'Origem: Poder Legislativo' in data_text
    assert 'Publicada no DO como Lei Complementar ao Ato Adicional.' in data_text
    assert 'O Presidente da República Faço saber que o Congresso Nacional decreta' in planalto_text
    assert 'O congresso Nacional decreta:' not in planalto_text
    for slug in (LC115, LC147, LC62):
        path = ROOT / f'federal/{slug}.md'
        meta, body = nl.parse_frontmatter(path.read_text(encoding='utf-8'))
        assert meta['orgao_emissor'] == 'Congresso Nacional'
        assert meta['fonte_orgao'] != meta['orgao_emissor']
        assert meta['campo_fontes']['orgao_emissor']
        assert meta['sha256_markdown'] == sha(body.encode('utf-8'))
        source_raw = lzma.decompress((ROOT / sources[slug]['snapshot_html']).read_bytes())
        source_text = re.sub(r'\s+', ' ', BeautifulSoup(source_raw, 'lxml').get_text(' ', strip=True))
        assert 'Congresso Nacional decreta' in source_text and 'eu sanciono' in source_text
    ret_path = ROOT / RETIFICACAO_REL
    ret_meta, ret_body = nl.parse_frontmatter(ret_path.read_text(encoding='utf-8'))
    assert ret_meta['norma_id'] == LC62
    assert ret_meta['edicao_id'] != nl.parse_frontmatter(
        (ROOT / f'federal/{LC62}.md').read_text(encoding='utf-8')
    )[0]['edicao_id']
    assert ret_meta['edicao_tipo'] == 'retificacao'
    assert ret_meta['sha256_markdown'] == sha(ret_body.encode('utf-8'))
    print('verify ok: LC115/147/1-1962 emissor e fontes; LC1/1962 original, retificação e edição Planalto')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cmd', choices=('build', 'verify'))
    args = parser.parse_args()
    build() if args.cmd == 'build' else verify()


if __name__ == '__main__':
    main()
