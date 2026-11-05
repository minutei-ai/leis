"""Recupera anexos RCN com PDF Senado vazio via fontes oficiais alternativas (#94).

HTTP 200 com 0 bytes no endpoint ANX do Senado é bloqueio daquela URL, não prova
de inacessibilidade da peça em todas as fontes. Este lote colaciona Câmara legin
(PDF/HTML) e publicação HTML alternativa do Senado (Sigen), preserva fac-símiles
e publica Markdown integral (corpo + anexos) sem alterar nucleo_licitacoes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import especies_legislativas_federais as especies  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/especies-legislativas-federais'
ANX_DIR = PROVAS / 'anexos-rcn'
FONTES_DIR = ANX_DIR / 'fontes'
FACSIMILE_DIR = ANX_DIR / 'facsimiles'
EVIDENCIA = ANX_DIR / 'recuperacao-fontes-alternativas.json'
BLOQUEIO = PROVAS / 'bloqueio-anexos-rcn-pdf-vazio.json'
COLETA = PROVAS / 'coleta.json'
FED = ROOT / 'federal'

# Mapa: slug → fontes alternativas oficiais verificadas nesta retomada.
ALTERNATIVAS: dict[str, dict] = {
    'br-federal-resolucao-congresso-nacional-2025-06-23-2': {
        'senado_id': '41071372',
        'senado_anx_urls_vazias': [
            'https://legis.senado.leg.br/norma/41071372/publicacao/41072651',
        ],
        'alt': {
            'orgao': 'Câmara dos Deputados — legin anexo PDF',
            'url': 'https://www2.camara.leg.br/legin/fed/rescon/2025/resolucao-2-23-junho-2025-797630-anexo-pl.pdf',
            'formato': 'pdf',
            'norma_url': 'https://www2.camara.leg.br/legin/fed/rescon/2025/resolucao-2-23-junho-2025-797630-norma-pl.html',
            'stage_pdf': 'rcn-2025-2-anx.pdf',
            'stage_facsimile': 'rcn-2025-2-anx-p1-1.png',
        },
    },
    'br-federal-resolucao-congresso-nacional-2025-03-14-1': {
        'senado_id': '40435851',
        'senado_anx_urls_vazias': [
            'https://legis.senado.leg.br/norma/40435851/publicacao/40435836',
        ],
        'alt': {
            'orgao': 'Câmara dos Deputados — legin anexo PDF / DCN',
            'url': 'https://www2.camara.leg.br/legin/fed/rescon/2025/resolucao-1-14-marco-2025-797194-anexo-pl.pdf',
            'formato': 'pdf',
            'norma_url': 'https://www2.camara.leg.br/legin/fed/rescon/2025/resolucao-1-14-marco-2025-797194-norma-pl.html',
            'nota_camara': 'Anexos I–IX também referidos no DCN nº 8, de 14/03/2025.',
            'stage_pdf': 'rcn-2025-1-anx.pdf',
            'stage_facsimile': 'rcn-2025-1-anx-p1-01.png',
        },
    },
    'br-federal-resolucao-congresso-nacional-2014-01-16-2': {
        'senado_id': '561151',
        'senado_anx_urls_vazias': [
            'https://legis.senado.leg.br/norma/561151/publicacao/36588688',
        ],
        'alt': {
            'orgao': 'Câmara dos Deputados — legin publicação original (anexo no HTML)',
            'url': 'https://www2.camara.leg.br/legin/fed/rescon/2014/resolucao-2-16-janeiro-2014-778014-publicacaooriginal-142934-pl.html',
            'formato': 'html',
            'norma_url': 'https://www2.camara.leg.br/legin/fed/rescon/2014/resolucao-2-16-janeiro-2014-778014-norma-pl.html',
            'stage_html': 'rcn-2014-2-orig.html',
            'anexo_marker': 'ESTATUTO DA ASSEMBLEIA PARLAMENTAR',
        },
    },
    'br-federal-resolucao-congresso-nacional-2013-11-22-3': {
        'senado_id': '561164',
        'senado_anx_urls_vazias': [
            'https://legis.senado.leg.br/norma/561164/publicacao/16426937',
        ],
        'alt': {
            'orgao': 'Câmara dos Deputados — legin anexo PDF',
            'url': 'https://www2.camara.leg.br/legin/fed/rescon/2013/resolucao-3-22-novembro-2013-777453-anexo-pl.pdf',
            'formato': 'pdf',
            'norma_url': 'https://www2.camara.leg.br/legin/fed/rescon/2013/resolucao-3-22-novembro-2013-777453-norma-pl.html',
            'stage_pdf': 'rcn-2013-3-anx.pdf',
            'stage_facsimile': 'rcn-2013-3-anx-p1-1.png',
            # p. 2 is visually/textually identical to p. 1; retain the original
            # three-page PDF, but transcribe only p. 1 + continuation p. 3.
            'pdf_pages': [1, 3],
            'pdf_duplicate_pages': [{
                'page': 2,
                'same_as': 1,
                'visual_sha256_identical_render': '4fdec9d8e4af918d43f81cba46b64377c2a79ba8aff3acf8f62b4cc8efec1432',
                'visual_rasterization': 'pdftoppm -f 1 -l 2 -png -r 150',
                'stage_representative_png': '/tmp/leis-rcn3-stage/rcn-2013-3-camara-page1-r150.png',
            }],
            'pdf_excerpt_start': 'Faço saber que o Congresso Nacional aprovou, e eu, Renan Calheiros, Presidente do Senado',
            'pdf_excerpt_end': r'\bTOTAL\s+121\s+121\s+242\b',
            'pdf_page_labels': ['DOU impresso p. 3', 'DOU impresso p. 4'],
            'nota_transcricao': (
                'O dump linear recuperado inclui o corpo porque as colunas do DOU '
                'intercalam esse texto com células da tabela. A publicação em Markdown '
                'transcreve visualmente somente a tabela, sem repetir o corpo. A página '
                '2 do PDF da Câmara foi omitida somente após igualdade textual e visual '
                'com a página 1. A extração textual termina antes da RCN 47/2013 e da '
                'Portaria da AGU; o PDF DOU completo é preservado separadamente.'
            ),
            'visual_crosscheck': {
                'url': 'https://www.gov.br/mme/pt-br/arquivos/do-25-11-2013-s1.pdf',
                'stage_pdf': '/tmp/leis-rcn3-stage/rcn-2013-3-dou-section1.pdf',
                'sha256': '36c70adb61c791ce3cba054bf6a91507d1f562ccf47d679ad92b6599b695b414',
                'pages_pdf': [3, 4],
                'pages_printed': [3, 4],
                'stage_textdump': '/tmp/leis-rcn3-validated-dou-3-4.txt',
                'textdump_sha256': '298c4d6bb705f54443fc3e30e612c61fc2dbc898d3ee5242ba741d18230b4af6',
                'authentication_codes': ['00012013112500003', '00012013112500004'],
                'facsimiles': [
                    {
                        'stage': '/tmp/leis-rcn3-validated-dou-003.png',
                        'page_pdf': 3,
                        'page_printed': 3,
                        'sha256': 'be383697f3b92ec1ea3f8711ca4fff9dabd5b0b42a9cacb12053c4d06e373ef8',
                    },
                    {
                        'stage': '/tmp/leis-rcn3-validated-dou-004.png',
                        'page_pdf': 4,
                        'page_printed': 4,
                        'sha256': '81b241f6540b29bd1d3368ba4265cb9be87b055005dc574473a24b7a8623b102',
                    },
                ],
            },
        },
    },
    'br-federal-resolucao-congresso-nacional-2006-12-26-2': {
        'senado_id': '561147',
        'senado_anx_urls_vazias': [
            'https://legis.senado.leg.br/norma/561147/publicacao/36751141',
        ],
        'alt': {
            'orgao': 'Senado Federal — publicação HTML alternativa do anexo (Sigen)',
            'url': 'https://legis.senado.leg.br/norma/561147/publicacao/36751146',
            'formato': 'html',
            'nota': (
                'O PDF ANX 36751141 responde HTTP 200 com 0 bytes; a publicação '
                'HTML 36751146 da mesma norma traz o Estatuto de Montevidéu.'
            ),
            'stage_html': 'rcn-2006-2-anx.html',
            'anexo_marker': 'ESTATUTO DE MONTEVID',
        },
    },
    'br-federal-resolucao-congresso-nacional-2006-12-22-1': {
        'senado_id': '561123',
        'senado_anx_urls_vazias': [
            'https://legis.senado.leg.br/norma/561123/publicacao/16426647',
        ],
        'alt': {
            'orgao': 'Câmara dos Deputados — legin anexo PDF',
            'url': 'https://www2.camara.leg.br/legin/fed/rescon/2006/resolucao-1-22-dezembro-2006-548706-anexo-pl.pdf',
            'formato': 'pdf',
            'norma_url': 'https://www2.camara.leg.br/legin/fed/rescon/2006/resolucao-1-22-dezembro-2006-548706-norma-pl.html',
            'stage_pdf': 'rcn-2006-1-anx.pdf',
            'stage_facsimile': 'rcn-2006-1-anx-p1-1.png',
        },
    },
}

STAGE = Path('/tmp/rcn-stage')


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_xz(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data, preset=9))
    return sha256(path.read_bytes())


def pdftotext(pdf: bytes, pages: list[int] | None = None) -> str:
    if pages is None:
        proc = subprocess.run(
            ['pdftotext', '-layout', '-', '-'],
            input=pdf,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(f'pdftotext falhou: {proc.stderr[:200]!r}')
        return proc.stdout.decode('utf-8', 'replace')
    rendered = []
    for page in pages:
        args = ['pdftotext', '-layout', '-f', str(page), '-l', str(page), '-', '-']
        proc = subprocess.run(args, input=pdf, capture_output=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(f'pdftotext falhou: {proc.stderr[:200]!r}')
        rendered.append(proc.stdout.decode('utf-8', 'replace').rstrip('\f'))
    return '\f'.join(rendered)


def extract_pdf_piece(text: str, start_marker: str, end_pattern: str) -> str:
    """Keep a source-bounded act/table sequence; reject ambiguous boundaries."""
    pages = text.split('\f')
    if len(pages) != 2:
        raise RuntimeError(f'intervalo PDF esperado em 2 páginas, recebido: {len(pages)}')
    first, continuation = pages
    if first.count(start_marker) != 1:
        raise RuntimeError(f'limite inicial não é único: {start_marker!r}')
    start = first.index(start_marker)
    footer = first.find('Este documento pode ser verificado', start)
    if footer < 0:
        raise RuntimeError('rodapé da primeira página não encontrado')
    matches = list(re.finditer(end_pattern, continuation, flags=re.I))
    if len(matches) != 1:
        raise RuntimeError(f'limite final não é único: {end_pattern!r}')
    end = matches[0].end()
    piece = first[start:footer].rstrip() + '\n\n' + continuation[:end].rstrip()
    if 'Nº 47, DE 2013' in piece or 'PORTARIA N' in piece:
        raise RuntimeError('recorte contém ato vizinho após o Anexo I')
    return piece


def html_to_plain(html: bytes | str) -> str:
    from bs4 import BeautifulSoup
    if isinstance(html, bytes):
        raw = html
    else:
        raw = html.encode('utf-8')
    soup = BeautifulSoup(raw, 'lxml')
    main = soup.select_one('#conteudoPrincipal') or soup.body or soup
    # remove nav/scripts
    for tag in main.find_all(['script', 'style', 'nav', 'header', 'footer']):
        tag.decompose()
    text = main.get_text('\n', strip=True)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def extract_anexo_from_html(text: str, marker: str) -> str:
    idx = text.upper().find(marker.upper())
    if idx < 0:
        # fallback: from first ANEXO heading
        m = re.search(r'(?im)\bANEXO\b', text)
        if not m:
            raise RuntimeError(f'marcador de anexo não encontrado: {marker}')
        idx = m.start()
    # include a short preamble line if ANEXO title precedes marker
    pre = text.rfind('\n', 0, idx)
    start = pre + 1 if pre >= 0 else idx
    chunk = text[start:].strip()
    # cut trailing site chrome
    for stop in ('ENGLISH', 'ESPAÑOL', 'Intranet', 'Servidor\n', 'Página inicial', 'Fale com o'):
        j = chunk.find(stop)
        if j > 500:
            chunk = chunk[:j].strip()
            break
    return chunk


def annex_markdown(title: str, plain: str, fonte_url: str, sha: str, nota: str | None = None) -> str:
    body = plain.strip()
    # Normalize excessive spaces but keep paragraphs
    lines = [re.sub(r'[ \t]+', ' ', ln).rstrip() for ln in body.splitlines()]
    body = '\n'.join(lines).strip()
    return (
        f'\n\n<!-- anexo-fonte-alternativa:inicio -->\n'
        f'> Anexo recuperado de fonte oficial alternativa (não do PDF ANX vazio do Senado). '
        f'Fonte: {fonte_url} (SHA-256 `{sha}`). '
        f'Transcrição/extração textual para colação; o fac-símile/PDF preservado nas provas prevalece em divergência visual.'
        f'{(" " + nota) if nota else ""}\n'
        f'<!-- anexo-fonte-alternativa:fim -->\n\n'
        f'# ANEXO\n\n'
        f'{body}\n'
    )


def rcn3_table_markdown() -> str:
    """Transcrição visual das células do Anexo I, em quatro painéis do DOU."""
    return '''\
## ANEXO I

**ANEXO À RESOLUÇÃO DO CONGRESSO NACIONAL Nº 1, DE 2006-CN**

| Comissão permanente | Área temática → subáreas temáticas (agrupadas como no impresso) | Apropriação | Remanejamento | Total |
|---|---|---:|---:|---:|
| CÂMARA DOS DEPUTADOS | | 76 | 76 | 152 |
| Mesa Diretora | Poderes do Estado e Representação → Câmara dos Deputados | 4 | 4 | 8 |
| Agricultura, Pecuária, Abastecimento e Desenvolvimento Rural - CAPADR | Agricultura e Desenvolvimento Agrário → Ministério da Agricultura, Pecuária e Abastecimento; Ministério da Pesca e Aquicultura; Ministério do Desenvolvimento Agrário<br>Integração Nacional e Meio Ambiente → Ministério da Integração Nacional; Ministério do Meio Ambiente | 4 | 4 | 8 |
| Amazônia, Integração Nacional e Desenvolvimento Regional - CAINDR | Fazenda, Desenvolvimento e Turismo → Ministério do Turismo<br>Integração Nacional e Meio Ambiente → Ministério da Integração Nacional; Ministério do Meio Ambiente<br>Justiça e Defesa → Ministério da Justiça | 4 | 4 | 8 |
| Ciência e Tecnologia, Comunicação e Informática - CCTCI | Educação, Cultura, Ciência e Tecnologia e Esporte → Ministério da Ciência, Tecnologia e Inovação<br>Infraestrutura → Ministério das Comunicações<br>Justiça e Defesa → Ministério da Defesa | 4 | 4 | 8 |
| Constituição e Justiça e de Cidadania - CCJC | Justiça e Defesa → Ministério da Justiça<br>Poderes do Estado e Representação → Órgãos do Ministério Público; Órgãos do Poder Judiciário; Presidência da República | 4 | 4 | 8 |
| Defesa do Consumidor - CDC | Fazenda, Desenvolvimento e Turismo → Ministério da Fazenda; Ministério do Desenvolvimento, Indústria e Comércio Exterior<br>Justiça e Defesa → Ministério da Justiça | 4 | 4 | 8 |
| Desenvolvimento Econômico, Indústria e Comércio - CDEIC | Agricultura e Desenvolvimento Agrário → Ministério da Agricultura, Pecuária e Abastecimento<br>Fazenda, Desenvolvimento e Turismo → Ministério da Fazenda; Ministério do Desenvolvimento, Indústria e Comércio Exterior | 4 | 4 | 8 |
| Desenvolvimento Urbano - CDU | Integração Nacional e Meio Ambiente → Ministério da Integração Nacional; Ministério do Meio Ambiente<br>Planejamento e Desenvolvimento Urbano → Ministério das Cidades | 4 | 4 | 8 |
| Direitos Humanos e Minorias - CDHM | Justiça e Defesa → Ministério da Justiça<br>Poderes do Estado e Representação → Presidência da República<br>Trabalho, Previdência e Assistência Social → Ministério do Desenvolvimento Social e Combate à Fome | 4 | 4 | 8 |
| Educação-CE | Educação, Cultura, Ciência e Tecnologia e Esporte → Ministério da Educação; Ministério da Cultura; Ministério da Ciência, Tecnologia e Inovação; Ministério do Esporte<br>Justiça e Defesa → Ministério da Defesa<br>Trabalho, Previdência e Assistência Social → Ministério do Trabalho e Emprego | 3 | 3 | 6 |
| Cultura -CCULT | Educação, Cultura, Ciência e Tecnologia e Esporte → Ministério da Cultura; Ministério da Educação; Ministério da Ciência, Tecnologia e Inovação; Ministério do Esporte<br>Justiça e Defesa → Ministério da Justiça | 3 | 3 | 6 |
| Finanças e Tributação- CFT | Fazenda, Desenvolvimento e Turismo → Ministério da Fazenda<br>Planejamento e Desenvolvimento Urbano → Ministério do Planejamento, Orçamento e Gestão | 3 | 3 | 6 |
| Fiscalização Financeira e Controle - CFFC | Poderes do Estado e Representação → Ministério do Planejamento, Orçamento e Gestão; Presidência da República; Tribunal de Contas da União | 4 | 4 | 8 |
| Legislação Participativa - CLP | *(células de área e subárea em branco no impresso)* | 0 | 0 | 0 |
| Meio Ambiente e Desenvolvimento Sustentável - CMADS | Educação, Cultura, Ciência e Tecnologia e Esporte → Ministério da Ciência, Tecnologia e Inovação<br>Integração Nacional e Meio Ambiente → Ministério do Meio Ambiente | 3 | 3 | 6 |
| Minas e Energia - CME | Educação, Cultura, Ciência e Tecnologia e Esporte → Ministério da Ciência, Tecnologia e Inovação<br>Infraestrutura → Ministério de Minas e Energia<br>Integração Nacional e Meio Ambiente → Ministério do Meio Ambiente | 4 | 4 | 8 |
| Relações Exteriores e de Defesa Nacional - CREDN | Justiça e Defesa → Ministério da Defesa<br>Poderes do Estado e Representação → Ministério das Relações Exteriores | 3 | 3 | 6 |
| Segurança Pública e Combate ao Crime Organizado - CSPCCO | Justiça e Defesa → Ministério da Justiça | 2 | 2 | 4 |
| Seguridade Social e Família - CSSF | Saúde → Ministério da Saúde<br>Trabalho, Previdência e Assistência Social → Ministério da Previdência Social; Ministério do Desenvolvimento Social e Combate à Fome | 4 | 4 | 8 |
| Trabalho, de Administração e Serviço Público - CTASP | Planejamento e Desenvolvimento Urbano → Ministério do Planejamento, Orçamento e Gestão<br>Trabalho, Previdência e Assistência Social → Ministério da Previdência Social; Ministério do Trabalho e Emprego | 4 | 4 | 8 |
| Turismo e Desporto - CTD | Educação, Cultura, Ciência e Tecnologia e Esporte → Ministério do Esporte<br>Fazenda, Desenvolvimento e Turismo → Ministério do Turismo | 3 | 3 | 6 |
| Viação e Transporte - CVT | Infraestrutura → Ministério dos Transportes<br>Justiça e Defesa → Ministério da Defesa<br>Poderes do Estado e Representação → Presidência da República | 4 | 4 | 8 |
| SENADO FEDERAL | | 45 | 45 | 90 |
| Mesa Diretora | Poderes do Estado e Representação → Senado Federal | 4 | 4 | 8 |
| Agricultura e Reforma Agrária - CRA | Agricultura e Desenvolvimento Agrário → Ministério da Agricultura, Pecuária e Abastecimento; Ministério da Pesca e Aquicultura; Ministério do Desenvolvimento Agrário<br>Integração Nacional e Meio Ambiente → Ministério do Meio Ambiente | 4 | 4 | 8 |
| Assuntos Econômicos - CAE | Fazenda, Desenvolvimento e Turismo → Ministério da Fazenda; Ministério do Desenvolvimento, Indústria e Comércio Exterior<br>Planejamento e Desenvolvimento Urbano → Ministério do Planejamento, Orçamento e Gestão | 4 | 4 | 8 |
| Assuntos Sociais -CAS | Saúde → Ministério da Saúde<br>Trabalho, Previdência e Assistência Social → Ministério da Previdência Social; Ministério do Desenvolvimento Social e Combate à Fome | 4 | 4 | 8 |
| Ciência, Tecnologia, Inovação, Comunicação e Informática - CCT | Agricultura e Desenvolvimento Agrário → Ministério da Agricultura, Pecuária e Abastecimento<br>Educação, Cultura, Ciência e Tecnologia e Esporte → Ministério da Ciência, Tecnologia e Inovação; Ministério da Educação<br>Infraestrutura → Ministério das Comunicações<br>Justiça e Defesa → Ministério da Defesa<br>Saúde → Ministério da Saúde | 3 | 3 | 6 |
| Constituição, Justiça e Cidadania - CCJ | Justiça e Defesa → Ministério da Justiça<br>Planejamento e Desenvolvimento Urbano → Ministério do Planejamento, Orçamento e Gestão<br>Poderes do Estado e Representação → Órgãos do Ministério Público; Órgãos do Poder Judiciário; Tribunal de Contas da União | 4 | 4 | 8 |
| Desenvolvimento Regional e Turismo - CDR | Fazenda, Desenvolvimento e Turismo → Ministério do Turismo<br>Integração Nacional e Meio Ambiente → Ministério da Integração Nacional<br>Planejamento e Desenvolvimento Urbano → Ministério das Cidades | 4 | 4 | 8 |
| Direitos Humanos e Legislação Participativa- CDH | Poderes do Estado e Representação → Órgãos do Ministério Público; Presidência da República | 3 | 3 | 6 |
| Educação, Cultura e Esporte- CE | Educação, Cultura, Ciência e Tecnologia e Esporte → Ministério da Ciência, Tecnologia e Inovação; Ministério da Cultura; Ministério da Educação; Ministério do Esporte | 4 | 4 | 8 |
| Meio Ambiente, Defesa do Consumidor e Fiscalização e Controle - CMA | Integração Nacional e Meio Ambiente → Ministério do Meio Ambiente<br>Poderes do Estado e Representação → Órgãos do Ministério Público; Tribunal de Contas da União | 4 | 4 | 8 |
| Relações Exteriores e Defesa Nacional - CRE | Justiça e Defesa → Ministério da Defesa<br>Poderes do Estado e Representação → Ministério das Relações Exteriores | 3 | 3 | 6 |
| Serviços de Infraestrutura-CI | Infraestrutura → Ministério das Comunicações; Ministério de Minas e Energia; Ministério dos Transportes<br>Poderes do Estado e Representação → Presidência da República | 4 | 4 | 8 |
| TOTAL | | 121 | 121 | 242 |
'''


def import_staged() -> dict:
    """Importa artefatos já capturados em /tmp/rcn-stage para provas/ (xz + hashes)."""
    FONTES_DIR.mkdir(parents=True, exist_ok=True)
    FACSIMILE_DIR.mkdir(parents=True, exist_ok=True)
    out = {'importado_em': now_utc(), 'itens': {}}
    for slug, cfg in ALTERNATIVAS.items():
        alt = cfg['alt']
        item = {
            'slug': slug,
            'senado_id': cfg['senado_id'],
            'senado_anx_urls_vazias': cfg['senado_anx_urls_vazias'],
            'fonte_alternativa': {
                'orgao': alt['orgao'],
                'url': alt['url'],
                'formato': alt['formato'],
            },
        }
        if alt.get('norma_url'):
            item['fonte_alternativa']['norma_url'] = alt['norma_url']
        if alt.get('nota'):
            item['fonte_alternativa']['nota'] = alt['nota']
        if alt.get('nota_camara'):
            item['fonte_alternativa']['nota_camara'] = alt['nota_camara']

        if alt['formato'] == 'pdf':
            pdf_path = STAGE / alt['stage_pdf']
            pdf = pdf_path.read_bytes()
            if len(pdf) < 1000 or pdf[:4] != b'%PDF':
                raise SystemExit(f'{slug}: PDF inválido/ausente em {pdf_path}')
            snap = FONTES_DIR / f'{slug}.anexo.pdf.xz'
            item['fonte_alternativa'].update({
                'bytes': len(pdf),
                'sha256': sha256(pdf),
                'snapshot': str(snap.relative_to(ROOT)),
                'sha256_snapshot_armazenado': write_xz(snap, pdf),
                'capturado_em': now_utc(),
            })
            duplicate_pages = []
            for duplicate in alt.get('pdf_duplicate_pages', []):
                reference = pdftotext(pdf, [duplicate['same_as']])
                repeated = pdftotext(pdf, [duplicate['page']])
                if reference != repeated:
                    raise RuntimeError(
                        f'{slug}: página {duplicate["page"]} não é idêntica '
                        f'à página {duplicate["same_as"]}'
                    )
                representative_png = Path(duplicate['stage_representative_png']).read_bytes()
                if sha256(representative_png) != duplicate['visual_sha256_identical_render']:
                    raise RuntimeError(f'{slug}: hash do PNG representante divergente')
                representative_snapshot = FACSIMILE_DIR / f'{slug}.p1-p2-identical.png.xz'
                duplicate_pages.append({
                    'page_omitted': duplicate['page'],
                    'identical_to_page': duplicate['same_as'],
                    'sha256_text_both_pages': sha256(reference.encode('utf-8')),
                    'sha256_visual_identical_render': sha256(representative_png),
                    'visual_rasterization': duplicate['visual_rasterization'],
                    'representative_snapshot': str(representative_snapshot.relative_to(ROOT)),
                    'sha256_representative_snapshot': write_xz(representative_snapshot, representative_png),
                })
            selected_pages = alt.get('pdf_pages')
            text = pdftotext(pdf, selected_pages)
            if alt.get('pdf_excerpt_start'):
                text = extract_pdf_piece(
                    text,
                    alt['pdf_excerpt_start'],
                    alt['pdf_excerpt_end'],
                )
            if selected_pages:
                item['fonte_alternativa']['paginas_pdf_transcritas'] = selected_pages
                item['fonte_alternativa']['rotulos_paginas'] = alt.get('pdf_page_labels', [])
            if duplicate_pages:
                item['fonte_alternativa']['paginas_duplicadas_omitidas'] = duplicate_pages
            txt_snap = FONTES_DIR / f'{slug}.anexo.txt.xz'
            item['transcricao'] = {
                'metodo': 'pdftotext -layout',
                'chars': len(text),
                'sha256': sha256(text.encode('utf-8')),
                'snapshot': str(txt_snap.relative_to(ROOT)),
                'sha256_snapshot_armazenado': write_xz(txt_snap, text.encode('utf-8')),
            }
            if selected_pages:
                item['transcricao']['paginas_pdf'] = selected_pages
                item['transcricao']['pagina_repetida_omitida'] = duplicate_pages
            if alt.get('visual_crosscheck'):
                visual = alt['visual_crosscheck']
                visual_pdf = Path(visual['stage_pdf']).read_bytes()
                if sha256(visual_pdf) != visual['sha256']:
                    raise RuntimeError(f'{slug}: hash da fonte DOU visual divergente')
                visual_snap = FONTES_DIR / f'{slug}.dou-section1.pdf.xz'
                visual_item = {
                    'url': visual['url'],
                    'bytes': len(visual_pdf),
                    'sha256_pdf': sha256(visual_pdf),
                    'pages_pdf': visual['pages_pdf'],
                    'pages_printed': visual['pages_printed'],
                    'authentication_codes': visual['authentication_codes'],
                    'snapshot_pdf': str(visual_snap.relative_to(ROOT)),
                    'sha256_snapshot_armazenado': write_xz(visual_snap, visual_pdf),
                    'facsimiles': [],
                }
                for proof_page in visual['facsimiles']:
                    image_bytes = Path(proof_page['stage']).read_bytes()
                    if sha256(image_bytes) != proof_page['sha256']:
                        raise RuntimeError(f'{slug}: hash de fac-símile DOU divergente')
                    image_name = f'{slug}.dou-p{proof_page["page_printed"]}.png.xz'
                    image_out = FACSIMILE_DIR / image_name
                    visual_item['facsimiles'].append({
                        'page_pdf': proof_page['page_pdf'],
                        'page_printed': proof_page['page_printed'],
                        'bytes': len(image_bytes),
                        'sha256': sha256(image_bytes),
                        'snapshot': str(image_out.relative_to(ROOT)),
                        'sha256_snapshot_armazenado': write_xz(image_out, image_bytes),
                    })
                if visual.get('stage_textdump'):
                    textdump = Path(visual['stage_textdump']).read_bytes()
                    if visual.get('textdump_sha256') and sha256(textdump) != visual['textdump_sha256']:
                        raise RuntimeError(f'{slug}: hash do dump textual DOU divergente')
                    textdump_snap = FONTES_DIR / f'{slug}.dou-p3-p4.txt.xz'
                    visual_item['textdump_pages'] = visual['pages_pdf']
                    visual_item['textdump_bytes'] = len(textdump)
                    visual_item['textdump_sha256'] = sha256(textdump)
                    visual_item['textdump_snapshot'] = str(textdump_snap.relative_to(ROOT))
                    visual_item['textdump_sha256_snapshot_armazenado'] = write_xz(
                        textdump_snap, textdump
                    )
                item['verificacao_visual_independente'] = visual_item
                if slug == 'br-federal-resolucao-congresso-nacional-2013-11-22-3':
                    table = rcn3_table_markdown().strip()
                    table_snap = FONTES_DIR / f'{slug}.anexo-tabela-visual.md.xz'
                    item['transcricao_tabela_visual'] = {
                        'metodo': 'transcricao-manual-colacionada-nos-quatro-paineis-do-facsimile',
                        'paginas_pdf': visual['pages_pdf'],
                        'facsimiles': [
                            {
                                'pagina_impressa': page['page_printed'],
                                'snapshot': str(
                                    (FACSIMILE_DIR / f'{slug}.dou-p{page["page_printed"]}.png.xz')
                                    .relative_to(ROOT)
                                ),
                                'sha256_png': page['sha256'],
                            }
                            for page in visual['facsimiles']
                        ],
                        'painéis_visuais': [
                            {'pagina_impressa': 3, 'recorte_px': [90, 805, 820, 1810],
                             'conteudo': 'cabeçalho, Mesa Diretora e CAPADR'},
                            {'pagina_impressa': 3, 'recorte_px': [855, 680, 1660, 1810],
                             'conteudo': 'CAINDR até CCULT'},
                            {'pagina_impressa': 4, 'recorte_px': [80, 120, 820, 1310],
                             'conteudo': 'continuação de CCULT, demais comissões da Câmara, Mesa Diretora e CRA do Senado'},
                            {'pagina_impressa': 4, 'recorte_px': [855, 120, 1660, 1310],
                             'conteudo': 'continuação do Senado, de CAE até CI, e total geral'},
                        ],
                        'chars': len(table),
                        'sha256': sha256(table.encode('utf-8')),
                        'snapshot': str(table_snap.relative_to(ROOT)),
                        'sha256_snapshot_armazenado': write_xz(
                            table_snap, table.encode('utf-8')
                        ),
                    }
                    item['anexo_table_plain'] = table
            if alt.get('stage_facsimile'):
                fac = STAGE / alt['stage_facsimile']
                if fac.is_file():
                    fac_bytes = fac.read_bytes()
                    fac_out = FACSIMILE_DIR / f'{slug}.p1.png.xz'
                    item['facsimile'] = {
                        'pagina': 1,
                        'bytes': len(fac_bytes),
                        'sha256': sha256(fac_bytes),
                        'snapshot': str(fac_out.relative_to(ROOT)),
                        'sha256_snapshot_armazenado': write_xz(fac_out, fac_bytes),
                        'papel': 'colacao-visual-primeira-pagina',
                    }
            item['anexo_plain'] = text
        else:
            html_path = STAGE / alt['stage_html']
            html = html_path.read_bytes()
            if len(html) < 500:
                raise SystemExit(f'{slug}: HTML inválido/ausente em {html_path}')
            snap = FONTES_DIR / f'{slug}.anexo.html.xz'
            item['fonte_alternativa'].update({
                'bytes': len(html),
                'sha256': sha256(html),
                'snapshot': str(snap.relative_to(ROOT)),
                'sha256_snapshot_armazenado': write_xz(snap, html),
                'capturado_em': now_utc(),
            })
            plain = html_to_plain(html)
            anexo = extract_anexo_from_html(plain, alt.get('anexo_marker') or 'ANEXO')
            txt_snap = FONTES_DIR / f'{slug}.anexo.txt.xz'
            item['transcricao'] = {
                'metodo': 'html-to-text+recorte-anexo',
                'chars': len(anexo),
                'sha256': sha256(anexo.encode('utf-8')),
                'snapshot': str(txt_snap.relative_to(ROOT)),
                'sha256_snapshot_armazenado': write_xz(txt_snap, anexo.encode('utf-8')),
            }
            item['anexo_plain'] = anexo
        out['itens'][slug] = item
        print(f'imported {slug} chars={len(item["anexo_plain"])} formato={alt["formato"]}', flush=True)
    # Persist without the large plain text field
    serial = {
        'importado_em': out['importado_em'],
        'aviso': (
            'HTTP 200 + PDF 0 bytes no ANX do Senado bloqueia aquela URL; '
            'não prova ausência da peça. Fontes alternativas oficiais abaixo.'
        ),
        'itens': {
            slug: {
                k: v for k, v in item.items()
                if k not in {'anexo_plain', 'anexo_table_plain'}
            }
            for slug, item in out['itens'].items()
        },
    }
    EVIDENCIA.write_text(json.dumps(serial, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return out


def load_coleta_item(slug: str) -> dict:
    coleta = json.loads(COLETA.read_text(encoding='utf-8'))
    item = coleta.get('itens', {}).get(slug)
    if not item:
        raise SystemExit(f'{slug}: ausente de coleta.json')
    return item


def build_one(slug: str, recovered: dict) -> dict:
    """Publica Markdown integral = corpo HTML já coletado + anexo da fonte alternativa."""
    col = load_coleta_item(slug)
    html = lzma.decompress((ROOT / col['snapshot']).read_bytes())
    # Forçar utilizavel temporariamente para reutilizar build_markdown
    item = dict(col)
    item['utilizavel'] = True
    item['tipo'] = 'RCN'
    md, proof = especies.build_markdown(item, html)
    meta, body = nl.parse_frontmatter(md)
    alt = recovered['fonte_alternativa']
    published_annex = recovered.get('anexo_table_plain') or recovered['anexo_plain']
    annex_note = alt.get('nota_transcricao')
    if recovered.get('anexo_table_plain'):
        annex_note = (
            'Tabela transcrita visualmente nos quatro painéis impressos das páginas 3–4 do DOU; '
            'o dump linear integral dessas páginas e o PDF original estão preservados nas provas. '
            'A disposição explicita as células mescladas sem repetir o corpo operativo do ato.'
        )
    anexo_md = annex_markdown(
        'ANEXO',
        published_annex,
        alt['url'],
        alt['sha256'],
        annex_note,
    )
    # A conversão do corpo original deixa um marcador para a tabela não
    # reconhecida. Remova o marcador e o cabeçalho vazio antes de anexar a
    # transcrição recuperada. A composição tipográfica em colunas da fonte
    # alternativa ainda exige repetir o preâmbulo/corpo para preservar células
    # que aparecem antes do título do anexo na ordem linear do PDF.
    if slug == 'br-federal-resolucao-congresso-nacional-2013-11-22-3':
        body = body.replace(r'\<\<TABELA\>\>', '').replace('<<TABELA>>', '')
        meta['tabelas'] = 1
    # Evitar duplicar se já houver ANEXO no corpo convertido
    if re.search(r'(?im)^#\s*ANEXO\b', body) and len(re.findall(r'(?im)^#\s*ANEXO\b', body)) >= 1:
        # ainda assim anexamos a peça recuperada com cabeçalho distinto se o corpo não trouxe a íntegra
        if len(re.findall(r'(?im)^#\s*ANEXO\b', body)) and len(body) < len(anexo_md):
            pass
    new_body = body.rstrip() + anexo_md
    meta['anexos_no_corpo'] = len(re.findall(r'(?im)^(?:#+\s*)?ANEXO\b', new_body))
    if recovered.get('anexo_table_plain'):
        # "ANEXO" e seu subtítulo "ANEXO I" formam uma única peça recuperada.
        meta['anexos_no_corpo'] = 1
    meta['edicao_integral'] = True
    meta['fonte_conferencia'] = [alt['url']]
    meta['sha256_markdown'] = sha256(new_body.encode('utf-8'))
    meta['anexo_fonte_alternativa_url'] = alt['url']
    meta['anexo_fonte_alternativa_sha256'] = alt['sha256']
    if alt.get('paginas_pdf_transcritas'):
        meta['anexo_fonte_alternativa_paginas_pdf'] = alt['paginas_pdf_transcritas']
        meta['anexo_paginas_duplicadas_omitidas'] = alt.get('paginas_duplicadas_omitidas', [])
    if recovered.get('verificacao_visual_independente'):
        visual = recovered['verificacao_visual_independente']
        meta['anexo_colacao_visual_independente'] = {
            'url': visual['url'],
            'sha256_pdf': visual['sha256_pdf'],
            'paginas_pdf': visual['pages_pdf'],
            'paginas_impressas': visual['pages_printed'],
            'codigos_autenticidade': visual['authentication_codes'],
            'facsimiles': [
                {
                    'pagina_impressa': page['page_printed'],
                    'sha256': page['sha256'],
                    'snapshot': page['snapshot'],
                }
                for page in visual['facsimiles']
            ],
            **({
                'dump_textual_integral': {
                    'paginas_pdf': visual['textdump_pages'],
                    'sha256': visual['textdump_sha256'],
                    'snapshot': visual['textdump_snapshot'],
                },
            } if visual.get('textdump_snapshot') else {}),
        }
    if recovered.get('transcricao_tabela_visual'):
        meta['anexo_transcricao_tabela_visual'] = recovered['transcricao_tabela_visual']
    meta['anexo_bloqueio_senado'] = (
        'PDF ANX Senado HTTP 200 com 0 bytes; peça recuperada em fonte oficial alternativa.'
    )
    fm = '---\n' + '\n'.join(
        f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in meta.items()
    ) + '\n---\n\n'
    text = fm + new_body
    path = FED / f'{slug}.md'
    path.write_text(text, encoding='utf-8')
    return {
        'slug': slug,
        'arquivo': str(path.relative_to(ROOT)),
        'sha256_markdown': meta['sha256_markdown'],
        'anexos_no_corpo': meta['anexos_no_corpo'],
        'chars_corpo': len(body),
        'chars_anexo': len(recovered['anexo_plain']),
        'proof_convert': proof,
    }


def update_lote_state(built: list[dict], recovered: dict) -> None:
    """Atualiza coleta, reconciliação, manifesto, fontes e bloqueio."""
    coleta = json.loads(COLETA.read_text(encoding='utf-8'))
    fontes = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
    manifesto = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))
    cobertura = json.loads((PROVAS / 'cobertura-conversao.json').read_text(encoding='utf-8'))
    rec = json.loads((PROVAS / 'reconciliacao-rcn.json').read_text(encoding='utf-8'))

    built_by = {b['slug']: b for b in built}
    for slug, b in built_by.items():
        col = coleta['itens'][slug]
        recovered_item = recovered['itens'][slug]
        alt = recovered_item['fonte_alternativa']
        col['utilizavel'] = True
        col['estado_sugerido'] = 'publicado'
        col['motivo'] = 'anexos-recuperados-fonte-alternativa-oficial'
        col['anexo_fonte_alternativa'] = {
            'url': alt['url'],
            'sha256': alt['sha256'],
            'orgao': alt['orgao'],
            'snapshot': alt['snapshot'],
        }
        if alt.get('paginas_pdf_transcritas'):
            col['anexo_fonte_alternativa']['paginas_pdf_transcritas'] = alt['paginas_pdf_transcritas']
        if alt.get('paginas_duplicadas_omitidas'):
            col['anexo_fonte_alternativa']['paginas_duplicadas_omitidas'] = alt['paginas_duplicadas_omitidas']
        if recovered_item.get('verificacao_visual_independente'):
            col['verificacao_visual_independente'] = recovered_item['verificacao_visual_independente']
        if recovered_item.get('transcricao_tabela_visual'):
            col['transcricao_tabela_visual'] = recovered_item['transcricao_tabela_visual']
        # fontes.json
        fontes[slug] = {
            'url': col.get('fonte_url'),
            'capturado_em': col.get('capturado_em'),
            'sha256': col.get('sha256_fonte'),
            'sha256_snapshot_armazenado': sha256((ROOT / col['snapshot']).read_bytes()),
            'bytes': col.get('bytes'),
            'snapshot': col['snapshot'],
            'origem': col.get('origem'),
            'senado_id': col['senado_id'],
            'tipo': 'RCN',
            'charset': col.get('charset', 'utf-8'),
            'ementa': col.get('ementa'),
            'normaNome': col.get('normaNome'),
            'numero': str(col.get('numero')),
            'data': col.get('data'),
            'urn': col.get('urn'),
            'anexo_fonte_alternativa': col['anexo_fonte_alternativa'],
            **({'verificacao_visual_independente': col['verificacao_visual_independente']}
               if col.get('verificacao_visual_independente') else {}),
            **({'transcricao_tabela_visual': col['transcricao_tabela_visual']}
               if col.get('transcricao_tabela_visual') else {}),
            'reconversao': 'corpo-html-mais-anexo-alternativo',
        }
        # manifesto
        manifest_entry = {
            'id': slug,
            'arquivo': b['arquivo'],
            'tipo': 'RCN',
            'senado_id': col['senado_id'],
            'urn': col.get('urn'),
            'norma': {
                'numero': str(col.get('numero')),
                'data': col.get('data'),
                'titulo': col.get('normaNome'),
            },
            'fonte': slug,
            'sha256_fonte': col.get('sha256_fonte'),
            'sha256_markdown': b['sha256_markdown'],
            'anexo_fonte_alternativa': True,
        }
        existing_index = next(
            (i for i, doc in enumerate(manifesto['documentos']) if doc['id'] == slug),
            None,
        )
        if existing_index is None:
            manifesto['documentos'].append(manifest_entry)
        else:
            manifesto['documentos'][existing_index] = manifest_entry
        cobertura['itens'][slug] = {
            **b.get('proof_convert', {}),
            'anexo_chars': b['chars_anexo'],
            'anexo_fonte_alternativa': alt['url'],
            **({'anexo_paginas_pdf_transcritas': alt['paginas_pdf_transcritas']}
               if alt.get('paginas_pdf_transcritas') else {}),
            **({'verificacao_visual_independente': recovered_item['verificacao_visual_independente']}
               if recovered_item.get('verificacao_visual_independente') else {}),
            **({'transcricao_tabela_visual': recovered_item['transcricao_tabela_visual']}
               if recovered_item.get('transcricao_tabela_visual') else {}),
        }
        # reconciliacao
        for item in rec['itens']:
            if item['slug'] == slug:
                item['estado_coleta'] = 'publicado'
                item['caminho_publicado'] = b['arquivo']
                item['anexo_recuperado_fonte_alternativa'] = True
    rec['publicados'] = sum(1 for i in rec['itens'] if i['estado_coleta'] == 'publicado')
    rec['anexos_pendentes'] = sum(1 for i in rec['itens'] if i['estado_coleta'] == 'anexos-pendentes')

    # bloqueio: manter evidência do URL vazio + apontar recuperação alternativa
    bloqueio = json.loads(BLOQUEIO.read_text(encoding='utf-8'))
    bloqueio['atualizado_em'] = now_utc()
    bloqueio['interpretacao'] = (
        'HTTP 200 application/pdf com 0 bytes é bloqueio da URL ANX do Senado, '
        'não prova de peça inacessível em todas as fontes oficiais.'
    )
    bloqueio['recuperacao_alternativa'] = {
        'evidencia': str(EVIDENCIA.relative_to(ROOT)),
        'slugs_recuperados': sorted(built_by),
        'publicados_apos_recuperacao': sorted(built_by),
    }
    # slugs ainda pendentes (nenhum se todos recuperados)
    ainda = [
        s for s in bloqueio.get('slugs_anexos_pendentes', [])
        if s not in built_by
    ]
    bloqueio['slugs_anexos_pendentes_apos_recuperacao'] = ainda
    bloqueio['slugs_anexos_pendentes'] = ainda

    COLETA.write_text(json.dumps(coleta, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (PROVAS / 'fontes.json').write_text(json.dumps(fontes, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (PROVAS / 'manifesto.json').write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (PROVAS / 'cobertura-conversao.json').write_text(
        json.dumps(cobertura, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
    )
    (PROVAS / 'reconciliacao-rcn.json').write_text(json.dumps(rec, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    BLOQUEIO.write_text(json.dumps(bloqueio, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    # resumo reconciliacao
    resumo_path = PROVAS / 'resumo-reconciliacao.json'
    if resumo_path.is_file():
        resumo = json.loads(resumo_path.read_text(encoding='utf-8'))
        resumo.setdefault('especies', {}).setdefault('RCN', {})
        resumo['especies']['RCN'].update({
            'publicados': rec['publicados'],
            'anexos_pendentes': rec['anexos_pendentes'],
            'arquivo': 'provas/especies-legislativas-federais/reconciliacao-rcn.json',
        })
        resumo_path.write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify() -> None:
    if not EVIDENCIA.is_file():
        raise SystemExit(f'evidência ausente: {EVIDENCIA}')
    ev = json.loads(EVIDENCIA.read_text(encoding='utf-8'))
    bloqueio = json.loads(BLOQUEIO.read_text(encoding='utf-8'))
    rec = json.loads((PROVAS / 'reconciliacao-rcn.json').read_text(encoding='utf-8'))
    if len(ev['itens']) != 6:
        raise SystemExit(f"esperados 6 anexos recuperados, got {len(ev['itens'])}")
    for slug, item in ev['itens'].items():
        alt = item['fonte_alternativa']
        snap = ROOT / alt['snapshot']
        raw = lzma.decompress(snap.read_bytes())
        if sha256(raw) != alt['sha256']:
            raise SystemExit(f'{slug}: hash da fonte alternativa diverge')
        if alt['bytes'] == 0:
            raise SystemExit(f'{slug}: fonte alternativa ainda vazia')
        path = FED / f'{slug}.md'
        if not path.is_file():
            raise SystemExit(f'{slug}: markdown não publicado')
        text = path.read_text(encoding='utf-8')
        meta, body = nl.parse_frontmatter(text)
        if meta['sha256_markdown'] != sha256(body.encode('utf-8')):
            raise SystemExit(f'{slug}: sha256_markdown diverge')
        if meta.get('vigencia_certificada') is True:
            raise SystemExit(f'{slug}: vigencia_certificada true')
        if 'anexo-fonte-alternativa' not in text:
            raise SystemExit(f'{slug}: marca de anexo alternativo ausente')
        if not re.search(r'(?im)^#\s*ANEXO\b', body):
            raise SystemExit(f'{slug}: heading ANEXO ausente')
        # Identidade semântica: número da resolução no corpo
        num = str(meta['norma_numero']).split('-')[0]
        fold = re.sub(r'\s+', '', body.casefold())
        # Aceita "RESOLUÇÃO Nº N", "Resolução do Congresso Nacional nº N" e "R E S O L U Ç Ã O Nº N".
        if f'resoluçãoº{num}' not in fold and f'resoluçãonº{num}' not in fold and f'resolucaon{num}' not in fold:
            if not re.search(rf'n[ºo°\.]*\s*{num}\b', body, re.I):
                raise SystemExit(f'{slug}: epígrafe da resolução ausente')
            # número presente; exigir radical "resolu" no corpo
            if 'resolu' not in fold:
                raise SystemExit(f'{slug}: epígrafe da resolução ausente')
    # reconciliacao: nenhum anexos-pendentes restante dos 6
    pend = [i['slug'] for i in rec['itens'] if i['estado_coleta'] == 'anexos-pendentes']
    for slug in ev['itens']:
        if slug in pend:
            raise SystemExit(f'{slug}: ainda anexos-pendentes na reconciliação')
        item = next(i for i in rec['itens'] if i['slug'] == slug)
        if item['estado_coleta'] != 'publicado':
            raise SystemExit(f'{slug}: estado {item["estado_coleta"]}')
    if bloqueio.get('slugs_anexos_pendentes'):
        raise SystemExit(f"bloqueio ainda lista pendentes: {bloqueio['slugs_anexos_pendentes']}")
    if 'não prova' not in bloqueio.get('interpretacao', '').lower() and 'nao prova' not in bloqueio.get('interpretacao', '').lower():
        # accept either form
        if 'prova de peça inacessível' not in bloqueio.get('interpretacao', '') and 'prova de peca inacessivel' not in bloqueio.get('interpretacao', '').lower():
            if 'inacess' not in bloqueio.get('interpretacao', '').lower():
                raise SystemExit('bloqueio sem interpretação HTTP 200 vazio ≠ ausência global')
    print('verify ok:', {
        'recuperados': len(ev['itens']),
        'rcn_publicados': rec['publicados'],
        'rcn_anexos_pendentes': rec['anexos_pendentes'],
    })


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cmd', choices=('import-staged', 'build', 'verify', 'all'))
    args = parser.parse_args(argv)
    ANX_DIR.mkdir(parents=True, exist_ok=True)
    if args.cmd in {'import-staged', 'all'}:
        recovered = import_staged()
    else:
        # reload plains from txt snapshots
        ev = json.loads(EVIDENCIA.read_text(encoding='utf-8'))
        recovered = {'itens': {}}
        for slug, item in ev['itens'].items():
            plain = lzma.decompress((ROOT / item['transcricao']['snapshot']).read_bytes()).decode('utf-8')
            recovered['itens'][slug] = {**item, 'anexo_plain': plain}
    if args.cmd in {'build', 'all'}:
        built = []
        for slug, item in recovered['itens'].items():
            built.append(build_one(slug, item))
            print(f'built {slug}', flush=True)
        update_lote_state(built, recovered)
        print(json.dumps({'publicados': [b['slug'] for b in built]}, ensure_ascii=False))
    if args.cmd in {'verify', 'all'}:
        verify()


if __name__ == '__main__':
    main(sys.argv[1:])
