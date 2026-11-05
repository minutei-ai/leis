"""Transcrição verificada do anexo oficial da RSF 13/2018.

O HTML da publicação Senado contém os arts. 1º–3º; o Anexo é publicado no
Suplemento Único do DSF nº 86, preservado aqui como PDF original. A transcrição
Markdown foi conferida visualmente nas páginas tabulares do fac-símile.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SLUG = 'br-federal-resolucao-senado-federal-2018-06-25-13'
PROOF_DIR = ROOT / 'provas/especies-legislativas-federais/anexos-rsf/rsf-2018-13'
PDF_PATH = PROOF_DIR / 'rsf13-dsf-suplemento-86.pdf'
MARKDOWN_PATH = PROOF_DIR / 'anexo-transcrito.md'
PROOF_PATH = PROOF_DIR / 'transcricao.json'
PDF_URL = 'https://legis.senado.leg.br/norma/27410175/publicacao/27411313'
PDF_SHA256 = '9d71bc6e759d122452e4b9988cd889ff391e90ea5b682ff7acdd7a7716acdb7e'
PDF_BYTES = 33_178_282
PDF_CAPTURED_AT = '2026-11-05T12:51:16Z'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def proof() -> dict:
    return json.loads(PROOF_PATH.read_text(encoding='utf-8'))


def verify() -> dict:
    """Fail closed if the source, transcript, or visual evidence changed."""
    raw_pdf = PDF_PATH.read_bytes()
    if len(raw_pdf) != PDF_BYTES or sha256(raw_pdf) != PDF_SHA256:
        raise AssertionError('PDF original RSF 13/2018 diverge do snapshot autenticado')
    data = proof()
    if data['fonte_pdf']['url'] != PDF_URL or data['fonte_pdf']['sha256'] != PDF_SHA256:
        raise AssertionError('identidade/proveniência do PDF do anexo diverge')
    if data['fonte_pdf']['bytes'] != PDF_BYTES or data['fonte_pdf']['paginas_pdf'] != 261:
        raise AssertionError('limites do PDF do anexo divergem')
    if data['fonte_pdf']['capturado_em'] != PDF_CAPTURED_AT:
        raise AssertionError('data de captura do PDF do anexo diverge')
    if data['paginas_transcritas_pdf'] != list(range(1, 262)):
        raise AssertionError('a transcrição não cobre todas as páginas do anexo')
    expected_table_pages = list(range(176, 215))
    if data['facsimiles_tabelas_pdf'] != expected_table_pages:
        raise AssertionError('fac-símiles tabulares incompletos')
    if [entry['pagina_pdf'] for entry in data['facsimiles']] != expected_table_pages:
        raise AssertionError('inventário de imagens fac-símile não cobre as páginas tabulares')
    for entry in data['facsimiles']:
        raster = PROOF_DIR / entry['arquivo']
        if sha256(raster.read_bytes()) != entry['sha256']:
            raise AssertionError(f"fac-símile diverge: {entry['arquivo']}")
    annex = MARKDOWN_PATH.read_bytes()
    if sha256(annex) != data['transcricao']['sha256']:
        raise AssertionError('hash da transcrição do anexo diverge')
    return data


def append_to_body(slug: str, body: str) -> tuple[str, dict | None]:
    if slug != SLUG:
        return body, None
    data = verify()
    annex = MARKDOWN_PATH.read_text(encoding='utf-8').strip()
    if '<!-- anexo-rsf-2018-13:inicio -->' not in annex or \
            '<!-- anexo-rsf-2018-13:fim -->' not in annex:
        raise AssertionError('marcadores do anexo RSF 13/2018 ausentes')
    result = body.rstrip() + '\n\n' + annex + '\n'
    metadata = {
        'anexo_pdf_url': PDF_URL,
        'anexo_pdf_sha256': PDF_SHA256,
        'anexo_pdf_bytes': PDF_BYTES,
        'anexo_pdf_capturado_em': PDF_CAPTURED_AT,
        'anexo_pdf_snapshot': str(PDF_PATH.relative_to(ROOT)),
        'anexo_pdf_paginas': 261,
        'anexo_pdf_paginas_transcritas': [1, 261],
        'anexo_pdf_publicacao_id': '27411313',
        'anexo_transcricao_sha256': data['transcricao']['sha256'],
        'anexo_facsimiles_tabulares_pdf': [176, 214],
    }
    return result, metadata


if __name__ == '__main__':
    result = verify()
    print(json.dumps({
        'slug': SLUG,
        'source_sha256': PDF_SHA256,
        'pages': result['fonte_pdf']['paginas_pdf'],
        'transcript_sha256': result['transcricao']['sha256'],
        'table_facsimiles': len(result['facsimiles']),
    }, ensure_ascii=False))
