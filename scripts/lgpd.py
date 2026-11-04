#!/usr/bin/env python3
"""Catálogo temático da LGPD (Lei 13.709/2018) — edições histórica e consolidada.

Reusa o conversor HTML→Markdown de nucleo_licitacoes. Não integra o núcleo de
licitações. Fonte principal da consolidada: Câmara (norma atualizada). Conferência:
Planalto. A Lei 15.352/2026 já publicada é reutilizada/validada sem republicação.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import lzma
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

from nucleo_licitacoes import (  # noqa: E402
    UNKNOWN,
    article_proof,
    blocks_to_markdown,
    compare_articles,
    content_sha256,
    convert_html,
    coverage,
    current_text_of,
    headings,
    main_body_blocks,
    md_plain,
    parse_frontmatter,
    render_frontmatter,
    sha256,
    split_articles,
    strip_fold,
    validate_meta,
    write_json,
)

PROVAS = ROOT / 'provas' / 'lgpd'
FONTES_DIR = PROVAS / 'fontes'
MANIFESTO = ROOT / 'metadados' / 'lgpd.json'
CONTRATO = ROOT / 'metadados' / 'CONTRATO-lgpd.md'
HISTORICA = ROOT / 'federal' / 'br-federal-lei-2018-08-14-13709.md'
CONSOLIDADA = ROOT / 'federal' / 'edicoes' / 'br-federal-lei-2018-08-14-13709-consolidada.md'
MODIFICADORA = ROOT / 'federal' / 'br-federal-lei-2026-02-25-15352.md'
MP1317 = ROOT / 'federal' / 'br-federal-medida-provisoria-2025-09-17-1317.md'

CAPTURA_PADRAO = '2026-11-04T12:01:14Z'
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

SOURCES = {
    'camara-lgpd-atualizada': dict(
        url='https://www2.camara.leg.br/legin/fed/lei/2018/lei-13709-14-agosto-2018-787077-normaatualizada-pl.html',
        file='camara-lei-13709-normaatualizada.html', orgao='Câmara dos Deputados',
        formato='html', charset='utf-8'),
    'planalto-lgpd': dict(
        url='https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm',
        file='planalto-l13709.htm', orgao='Presidência da República — Planalto',
        formato='html', charset='cp1252'),
    'camara-lei-15352-original': dict(
        url='https://www2.camara.leg.br/legin/fed/lei/2026/lei-15352-25-fevereiro-2026-798731-publicacaooriginal-178208-pl.html',
        file='camara-lei-15352-publicacaooriginal.html', orgao='Câmara dos Deputados',
        formato='html', charset='utf-8'),
    'planalto-lei-15352': dict(
        url='https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2026/lei/L15352.htm',
        file='planalto-l15352.htm', orgao='Presidência da República — Planalto',
        formato='html', charset='cp1252'),
    'camara-mp-1317': dict(
        url='https://www2.camara.leg.br/legin/fed/medpro/2025/medidaprovisoria-1317-17-setembro-2025-797987-publicacaooriginal-176485-pe.html',
        file='camara-mp-1317-publicacaooriginal.html', orgao='Câmara dos Deputados',
        formato='html', charset='utf-8'),
    'planalto-mp-1317': dict(
        url='https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/Mpv/mpv1317.htm',
        file='planalto-mpv1317.htm', orgao='Presidência da República — Planalto',
        formato='html', charset='cp1252'),
}

# Dispositivos da LGPD alterados pela MP 1.317/2025 / Lei 15.352/2026 (art. 1º da modificadora).
DISPOSITIVOS_MP1317_LEI15352 = [
    dict(dispositivo='art. 5º, VIII', campo='redacao',
         trecho_esperado='Agência Nacional de Proteção de Dados (ANPD)'),
    dict(dispositivo='art. 5º, XIX', campo='redacao',
         trecho_esperado='entidade da administração pública responsável'),
    dict(dispositivo='Capítulo IX (título)', campo='titulo',
         trecho_esperado='DA AGÊNCIA NACIONAL DE PROTEÇÃO DE DADOS E DO CONSELHO NACIONAL DE PROTEÇÃO DE DADOS PESSOAIS E DA PRIVACIDADE'),
    dict(dispositivo='Capítulo IX, Seção I (título)', campo='titulo',
         trecho_esperado='Da Agência Nacional de Proteção de Dados'),
    dict(dispositivo='art. 55-A, caput', campo='redacao',
         trecho_esperado='Agência Nacional de Proteção de Dados (ANPD), autarquia de natureza especial vinculada ao Ministério da Justiça e Segurança Pública'),
    dict(dispositivo='art. 55-C, V-A', campo='redacao', trecho_esperado='Procuradoria'),
    dict(dispositivo='art. 55-C, V-B', campo='redacao', trecho_esperado='Auditoria'),
    dict(dispositivo='art. 55-C, VI', campo='redacao',
         trecho_esperado='unidades administrativas e unidades especializadas'),
]


def snapshot_path(key: str) -> Path:
    return FONTES_DIR / (SOURCES[key]['file'] + '.xz')


def read_snapshot(key: str) -> bytes:
    return lzma.decompress(snapshot_path(key).read_bytes())


def write_snapshot(key: str, data: bytes) -> None:
    path = snapshot_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME))


def parse_hdr(path: Path) -> dict:
    text = path.read_text(errors='replace')
    parts = re.split(r'\r?\n\r?\n', text.strip())
    last = parts[-1] if parts else text

    def get(name: str):
        m = re.search(rf'(?im)^{re.escape(name)}:\s*(.+)$', last)
        return m.group(1).strip() if m else None

    return {
        'cabecalho_date': get('Date'),
        'cabecalho_last_modified': get('Last-Modified'),
        'cabecalho_etag': get('ETag'),
        'cabecalho_content_type': get('Content-Type'),
    }


def import_captures(src_dir: Path, capturado_em: str) -> dict:
    fontes = {}
    for key, spec in SOURCES.items():
        raw_path = src_dir / f'{key}.bin'
        if not raw_path.is_file():
            raise FileNotFoundError(raw_path)
        data = raw_path.read_bytes()
        write_snapshot(key, data)
        meta_path = src_dir / f'{key}.meta'
        meta_line = meta_path.read_text().strip() if meta_path.is_file() else ''
        status, url_final, ctype = (meta_line.split('|', 2) + [None, None, None])[:3]
        hdr = parse_hdr(src_dir / f'{key}.hdr') if (src_dir / f'{key}.hdr').is_file() else {}
        rec = dict(
            orgao=spec['orgao'], formato=spec['formato'], url=spec['url'],
            capturado_em=capturado_em, user_agent=UA,
            http_status=int(status) if status and status.isdigit() else UNKNOWN,
            url_final=url_final or spec['url'],
            bytes=len(data), sha256=sha256(data),
            sha256_conteudo=content_sha256(data),
            utilizavel=True,
            snapshot=str(snapshot_path(key).relative_to(ROOT)),
            sha256_snapshot_armazenado=sha256(snapshot_path(key).read_bytes()),
            charset=spec['charset'],
        )
        rec.update({k: v for k, v in hdr.items() if v})
        if ctype and 'cabecalho_content_type' not in rec:
            rec['cabecalho_content_type'] = ctype
        fontes[key] = rec
    write_json(PROVAS / 'fontes.json', fontes)
    return fontes


def trim_lgpd_blocks(blocks: list[str]) -> list[str]:
    """Mantém o cabeçalho da Câmara + corpo da Lei 13.709 até as assinaturas."""
    start = next(i for i, b in enumerate(blocks) if re.match(r'^LEI\s+N', md_plain(b, True)))
    # inclui "CÂMARA..." se existir antes do título
    head = 0
    for i in range(start):
        if 'CÂMARA' in blocks[i].upper() or 'Centro de Documentação' in blocks[i]:
            head = i
            break
    bras = next(i for i, b in enumerate(blocks) if i >= start and b.startswith('Brasília'))
    end = bras + 1
    while end < len(blocks) and not re.match(r'^LEI\s+N', md_plain(blocks[end], True)):
        # assinaturas / fecho
        end += 1
        if end - bras > 20:
            break
    return blocks[head:end]


def convert_camara_lgpd(data: bytes) -> tuple[list[str], str]:
    url = SOURCES['camara-lgpd-atualizada']['url']
    conv = convert_html(data, 'utf-8', url)
    blocks = trim_lgpd_blocks(conv.blocks)
    body = blocks_to_markdown(blocks, r'^LEI\s+N')
    if not coverage(blocks, body):
        raise RuntimeError('cobertura dos blocos convertidos ≠ markdown')
    return blocks, body


def extract_device_snippets(markdown: str) -> dict:
    """Trechos literais usados nos testes e no manifesto (sem inferir vigência)."""
    out = {}
    m = re.search(
        r'VIII\s*[-–]\s*encarregado:.*?Agência Nacional de Proteção de Dados \(ANPD\);',
        markdown, re.S)
    if not m:
        raise ValueError('art. 5º, VIII consolidado não encontrado')
    out['art5_VIII'] = re.sub(r'\s+', ' ', m.group(0)).strip()

    m = re.search(
        r'XIX\s*[-–]\s*autoridade nacional:\s*entidade da administração pública responsável'
        r'.*?território nacional\.',
        markdown, re.S)
    if not m:
        raise ValueError('art. 5º, XIX consolidado não encontrado')
    out['art5_XIX'] = re.sub(r'\s+', ' ', m.group(0)).strip()

    m = re.search(
        r'CAPÍTULO IX\s*\n\s*DA AGÊNCIA NACIONAL DE PROTEÇÃO DE DADOS E DO CONSELHO '
        r'NACIONAL DE PROTEÇÃO DE DADOS PESSOAIS E DA PRIVACIDADE',
        markdown)
    if not m:
        raise ValueError('título do Capítulo IX consolidado não encontrado')
    out['cap_ix_titulo'] = re.sub(r'\s+', ' ', m.group(0)).strip()

    m = re.search(
        r'Seção I\s*\n\s*Da Agência Nacional de Proteção de Dados\b',
        markdown)
    if not m:
        raise ValueError('título da Seção I do Capítulo IX não encontrado')
    out['secao_i_titulo'] = re.sub(r'\s+', ' ', m.group(0)).strip()

    m = re.search(
        r'Art\.\s*55-A\.\s*Fica criada a Agência Nacional de Proteção de Dados \(ANPD\), '
        r'autarquia de natureza especial vinculada ao Ministério da Justiça e Segurança Pública,'
        r'.*?Distrito Federal, nos termos da Lei nº 13\.848, de 25 de junho de 2019\.',
        markdown, re.S)
    if not m:
        raise ValueError('art. 55-A consolidado não encontrado')
    out['art55A'] = re.sub(r'\s+', ' ', m.group(0)).strip()

    m = re.search(
        r'Art\.\s*55-C\.\s*A ANPD é composta de:.*?'
        r'V-A\s*[-–]\s*Procuradoria;.*?'
        r'V-B\s*[-–]\s*Auditoria; e.*?'
        r'VI\s*[-–]\s*unidades administrativas e unidades especializadas\.',
        markdown, re.S)
    if not m:
        raise ValueError('art. 55-C (V-A/V-B/VI) consolidado não encontrado')
    out['art55C'] = re.sub(r'\s+', ' ', m.group(0)).strip()

    # Notas de alteração da fonte (MP 1.317 / Lei 15.352) junto aos dispositivos-alvo.
    # Art. 55-A acumula nota longa (MP 869 → Lei 13.853 → MP 1.317 → Lei 15.352).
    for label, pattern in [
        ('nota_art5_VIII',
         r'VIII\s*[-–]\s*encarregado:.{0,800}?Medida Provisória nº 1\.317.{0,400}?Lei nº 15\.352'),
        ('nota_cap_ix',
         r'CAPÍTULO IX.{0,800}?Medida Provisória nº 1\.317.{0,400}?Lei nº 15\.352'),
        ('nota_secao_i',
         r'Seção I\s*\n\s*Da Agência Nacional.{0,800}?Medida Provisória nº 1\.317.{0,400}?Lei nº 15\.352'),
        ('nota_art55A',
         r'Art\.\s*55-A\..{0,2500}?Medida Provisória nº 1\.317.{0,400}?Lei nº 15\.352'),
        ('nota_art55C_VB',
         r'V-B\s*[-–]\s*Auditoria; e.{0,500}?Medida Provisória nº 1\.317.{0,400}?Lei nº 15\.352'),
    ]:
        m = re.search(pattern, markdown, re.S)
        if not m:
            raise ValueError(f'nota de alteração ausente: {label}')
        out[label] = True
    return out


def historical_alerts() -> str:
    return (
        '<!-- nota-edicao:inicio -->\n\n'
        '> **Edição histórica — não é a edição consolidada.** Este arquivo preserva, sem '
        'alterações de corpo, a redação da Lei nº 13.709/2018 (LGPD) que já estava no acervo '
        f'(SHA-256 do corpo preservado abaixo). A fonte oficial e a data de captura desse texto '
        'não foram registradas (`desconhecido` no cabeçalho). Ele **não** incorpora as alterações '
        'da Medida Provisória nº 1.317/2025 convertida na Lei nº 15.352/2026.\n'
        '>\n'
        '> **Alerta por dispositivo (recuperação desta edição):** art. 5º, VIII; art. 5º, XIX; '
        'título do Capítulo IX; título da Seção I do Capítulo IX; art. 55-A, caput; art. 55-C, '
        'V-A/V-B/VI — nesta edição ainda figuram redações anteriores (ex.: “Autoridade Nacional '
        'de Proteção de Dados”), enquanto a edição consolidada e a Lei nº 15.352/2026 trazem '
        '“Agência Nacional de Proteção de Dados” nos dispositivos que a fonte alterou. Não se '
        'renomeia mecanicamente toda ocorrência de “Autoridade”/“autoridade nacional”: a fonte '
        'mantém “autoridade nacional” no art. 5º, XIX, e a modificadora ainda usa “Autoridade '
        'Nacional de Proteção de Dados” em dispositivos transitórios (ex.: arts. 15 e 15, parágrafo '
        'único, da Lei 15.352).\n'
        '>\n'
        '> A edição consolidada, conferida integralmente contra a Câmara (norma atualizada) e '
        'reconciliada com o Planalto, está em '
        '`edicoes/br-federal-lei-2018-08-14-13709-consolidada.md`. A Lei modificadora já '
        'publicada no acervo é `../br-federal-lei-2026-02-25-15352.md`. A presença deste arquivo '
        'não indica vigência.\n\n'
        '<!-- nota-edicao:fim -->\n\n'
    )


def consolidada_note(fontes: dict) -> str:
    cam = fontes['camara-lgpd-atualizada']
    pla = fontes['planalto-lgpd']
    return (
        '<!-- nota-edicao:inicio -->\n\n'
        '> **Edição consolidada — Câmara dos Deputados (norma atualizada).** Fonte: '
        f'{cam["url"]} (capturada em {cam["capturado_em"]}, SHA-256 da fonte '
        f'`{cam["sha256"]}`). O acervo não certifica vigência.\n'
        '>\n'
        f'> Conferida artigo a artigo com {pla["url"]} '
        f'(SHA-256 `{pla["sha256"]}`; ver `provas/lgpd/reconciliacao-br-federal-lei-2018-08-14-13709-consolidada.json`). '
        'Divergências de forma/segmentação entre Câmara e Planalto ficam explícitas na prova; '
        'não foram misturadas redações.\n'
        '>\n'
        '> Alterações da Medida Provisória nº 1.317/2025 convertida na Lei nº 15.352/2026 '
        '(art. 5º, VIII e XIX; títulos do Capítulo IX e da Seção I; art. 55-A; art. 55-C, V-A/V-B/VI) '
        'constam com as notas de alteração da própria fonte. A modificadora publicada no acervo é '
        '`../br-federal-lei-2026-02-25-15352.md` (anexos tabulares da Lei 15.352 estão no snapshot '
        'do Planalto em `provas/lgpd/fontes/`; o Markdown já publicado da modificadora não os '
        'reproduz — limite explícito, sem republicar a norma).\n'
        '>\n'
        '> Edição histórica preservada em `../br-federal-lei-2018-08-14-13709.md`. Texto entre '
        '`~~` (se houver) é redação superada/vetada/revogada que a fonte mantém riscada.\n\n'
        '<!-- nota-edicao:fim -->\n\n'
    )


def build_historica(corpo_original: str) -> tuple[str, dict]:
    corpo_hash = sha256(corpo_original.encode('utf-8'))
    note = historical_alerts()
    body = note + corpo_original
    if not body.endswith('\n'):
        body += '\n'
    meta = dict(
        id='br-federal-lei-2018-08-14-13709',
        norma_id='br-federal-lei-2018-08-14-13709',
        norma_tipo='lei',
        norma_numero='13709',
        norma_data='2018-08-14',
        titulo='LEI Nº 13.709, DE 14 DE AGOSTO DE 2018',
        esfera='federal',
        edicao_id='br-federal-lei-2018-08-14-13709@historica-fonte-desconhecida',
        edicao_tipo='historica',
        edicao_integral=UNKNOWN,
        edicao_relacionada='br-federal-lei-2018-08-14-13709-consolidada',
        fonte_orgao=UNKNOWN,
        fonte_url=UNKNOWN,
        fonte_formato=UNKNOWN,
        fonte_conferencia=UNKNOWN,
        capturado_em=UNKNOWN,
        sha256_fonte=UNKNOWN,
        situacao='nao-informada',
        situacao_fundamento=UNKNOWN,
        vigencia_certificada=False,
        texto_riscado=False,
        anexos_no_corpo=0,
        tabelas=0,
        imagens_omitidas=0,
        efeitos_diferidos='nao-aplicavel-sem-notas-na-edicao',
        sha256_corpo_preservado=corpo_hash,
        sha256_markdown=sha256(body.encode('utf-8')),
        manifesto='metadados/lgpd.json',
        contrato_versao=1,
    )
    errors = validate_meta(meta, 'lgpd-historica')
    if errors:
        raise RuntimeError('meta histórica inválida: ' + '; '.join(errors))
    return render_frontmatter(meta) + body, meta


def build_consolidada(body_md: str, fontes: dict, stats: dict) -> tuple[str, dict]:
    note = consolidada_note(fontes)
    # body_md já começa com possíveis linhas da Câmara + # LEI...
    text_body = note + body_md
    if not text_body.endswith('\n'):
        text_body += '\n'
    cam = fontes['camara-lgpd-atualizada']
    meta = dict(
        id='br-federal-lei-2018-08-14-13709-consolidada',
        norma_id='br-federal-lei-2018-08-14-13709',
        norma_tipo='lei',
        norma_numero='13709',
        norma_data='2018-08-14',
        titulo='LEI Nº 13.709, DE 14 DE AGOSTO DE 2018',
        esfera='federal',
        edicao_id='br-federal-lei-2018-08-14-13709@consolidada-camara',
        edicao_tipo='consolidada',
        edicao_integral=True,
        edicao_relacionada='br-federal-lei-2018-08-14-13709',
        fonte_orgao='Câmara dos Deputados',
        fonte_url=SOURCES['camara-lgpd-atualizada']['url'],
        fonte_formato='html',
        fonte_conferencia=[SOURCES['planalto-lgpd']['url']],
        capturado_em=cam['capturado_em'],
        sha256_fonte=cam['sha256'],
        situacao='nao-informada',
        situacao_fundamento=UNKNOWN,
        vigencia_certificada=False,
        texto_riscado=bool(stats.get('trechos_riscados')),
        anexos_no_corpo=0,
        tabelas=int(stats.get('tabelas_markdown', 0) + stats.get('tabelas_html', 0)),
        imagens_omitidas=int(stats.get('imagens_omitidas', 0)),
        efeitos_diferidos='preservados-nas-notas-do-texto',
        sha256_markdown=sha256(text_body.encode('utf-8')),
        manifesto='metadados/lgpd.json',
        contrato_versao=1,
    )
    errors = validate_meta(meta, 'lgpd-consolidada')
    # fonte_conferencia não pode repetir fonte_url — validate_meta do núcleo pode checar isso
    if meta['fonte_url'] in meta['fonte_conferencia']:
        raise RuntimeError('fonte_conferencia repete fonte_url')
    if errors:
        # sha256_corpo_preservado é opcional; demais erros falham
        fatal = [e for e in errors if 'sha256_corpo_preservado' not in e]
        if fatal:
            raise RuntimeError('meta consolidada inválida: ' + '; '.join(fatal))
    return render_frontmatter(meta) + text_body, meta


def validate_modificadora(fontes: dict) -> dict:
    """Reutiliza o Markdown já publicado; valida dispositivos-alvo e registra anexos ausentes."""
    if not MODIFICADORA.is_file():
        raise FileNotFoundError(MODIFICADORA)
    text = MODIFICADORA.read_text(encoding='utf-8')
    sha = sha256(text.encode('utf-8'))
    checks = {
        'arquivo': str(MODIFICADORA.relative_to(ROOT)),
        'sha256_markdown_publicado': sha,
        'contem_art55A_agencia': 'Agência Nacional de Proteção de Dados (ANPD), autarquia de natureza especial vinculada ao Ministério da Justiça e Segurança Pública' in text,
        'contem_art5_VIII_agencia': 'Agência Nacional de Proteção de Dados (ANPD)' in text and 'encarregado' in text,
        'contem_cap_ix_agencia': 'DA AGÊNCIA NACIONAL DE PROTEÇÃO DE DADOS' in text,
        'contem_secao_i_agencia': 'Da Agência Nacional de Proteção de Dados' in text,
        'contem_VB_auditoria': 'V-B' in text and 'Auditoria' in text,
        'preserva_autoridade_em_transicao': 'Autoridade Nacional de Proteção de Dados' in text,
        'anexos_tabulares_no_markdown_publicado': bool(re.search(r'(?m)^ANEXO\s+[IVX]+\b', text)),
        'anexos_tabulares_no_snapshot_planalto': True,  # verificado abaixo
        'limite': (
            'O Markdown publicado de br-federal-lei-2026-02-25-15352.md não reproduz as tabelas '
            'dos Anexos I–III; os bytes oficiais estão em provas/lgpd/fontes/planalto-l15352.htm.xz '
            'para reconversão offline. A norma não foi republicada neste PR.'
        ),
    }
    pla = read_snapshot('planalto-lei-15352')
    pla_text = pla.decode('cp1252', errors='replace')
    checks['anexos_tabulares_no_snapshot_planalto'] = all(
        f'ANEXO {n}' in pla_text.upper().replace('  ', ' ') or f'Anexo {n}' in pla_text
        for n in ('I', 'II', 'III')
    ) or (pla_text.upper().count('ANEXO') >= 3 and pla_text.lower().count('<table') >= 1)
    # Cámara original also alters LGPD
    cam = read_snapshot('camara-lei-15352-original').decode('utf-8', errors='replace')
    checks['camara_original_contem_art55A'] = 'Art. 55-A' in cam and 'Agência Nacional' in cam
    required = [
        'contem_art55A_agencia', 'contem_art5_VIII_agencia', 'contem_cap_ix_agencia',
        'contem_secao_i_agencia', 'contem_VB_auditoria', 'preserva_autoridade_em_transicao',
        'camara_original_contem_art55A',
    ]
    missing = [k for k in required if not checks[k]]
    if missing:
        raise RuntimeError('validação da Lei 15.352 falhou: ' + ', '.join(missing))
    checks['fontes'] = {
        'camara-lei-15352-original': fontes['camara-lei-15352-original']['sha256'],
        'planalto-lei-15352': fontes['planalto-lei-15352']['sha256'],
    }
    return checks


def historica_vs_consolidada(hist_corpo: str, cons_blocks: list[str]) -> dict:
    # Compare current texts: historical markdown blocks vs consolidada blocks
    # Historical has no frontmatter in hist_corpo
    hist_blocks = [p for p in re.split(r'\n\n+', hist_corpo.strip()) if p.strip()]
    # Prefer article_proof machinery on synthetic blocks
    ap, arts_h, arts_c = article_proof(hist_blocks, cons_blocks)
    # Focus devices
    foco = {}
    for key in ['5', '55-A', '55-C']:
        if key in arts_h and key in arts_c:
            ht = strip_fold(''.join(current_text_of(arts_h[key])))
            ct = strip_fold(''.join(current_text_of(arts_c[key])))
            foco[key] = dict(
                identicos=ht == ct,
                historica_tem_autoridade_nacional_de_protecao='autoridadenacionaldeprotecaodedados' in ht,
                consolidada_tem_agencia_nacional_de_protecao='agencianacionaldeprotecaodedados' in ct,
            )
    return dict(
        descricao=(
            'Artigos da edição consolidada (Câmara, texto em vigor segundo a fonte, sem riscados '
            'e sem notas) contra a edição histórica preservada.'
        ),
        historica=str(HISTORICA.relative_to(ROOT)),
        historica_sha256_corpo=sha256(hist_corpo.encode('utf-8')),
        consolidada=str(CONSOLIDADA.relative_to(ROOT)),
        sha256_fonte_consolidada=json.loads((PROVAS / 'fontes.json').read_text())['camara-lgpd-atualizada']['sha256'],
        artigos_fonte_historica=ap['artigos_fonte_conferencia'],
        artigos_fonte_consolidada=ap['artigos_fonte_principal'],
        artigos_apenas_na_consolidada=ap['apenas_na_principal'],
        artigos_apenas_na_historica=ap['apenas_na_conferencia'],
        artigos_identicos=ap['identicos'],
        artigos_alterados=[d['artigo'] for d in ap['divergentes']],
        divergencias_de_forma=ap['divergencias_de_forma'],
        divergencias_substanciais=ap['divergencias_substanciais'],
        foco_dispositivos_mp1317_lei15352=foco,
        detalhe_alterados=ap['divergentes'][:40],
    )


def build_manifesto(fontes: dict, meta_h: dict, meta_c: dict, snippets: dict,
                     reconciliacao: dict, hist_vs_cons: dict, val_mod: dict) -> dict:
    return dict(
        contrato='metadados/CONTRATO-lgpd.md',
        contrato_versao=1,
        descricao=(
            'Catálogo temático da LGPD (Lei 13.709/2018) e vínculos com a MP 1.317/2025 e a '
            'Lei 15.352/2026. Separado do núcleo de licitações.'
        ),
        vigencia_certificada=False,
        documentos={
            'br-federal-lei-2018-08-14-13709': dict(
                arquivo=str(HISTORICA.relative_to(ROOT)),
                edicao_tipo='historica',
                meta=meta_h,
                alerta_por_dispositivo={
                    'art. 5º, VIII': 'redação anterior à Lei 15.352/2026 (Autoridade Nacional…)',
                    'art. 5º, XIX': 'redação anterior (órgão…); consolidada: entidade…',
                    'Capítulo IX (título)': 'redação anterior (Autoridade Nacional…)',
                    'Capítulo IX, Seção I': 'redação anterior (Da Autoridade Nacional…)',
                    'art. 55-A': 'redação anterior à Lei 15.352/2026',
                    'art. 55-C, V-B': 'ausente nesta edição; consolidada inclui Auditoria',
                },
            ),
            'br-federal-lei-2018-08-14-13709-consolidada': dict(
                arquivo=str(CONSOLIDADA.relative_to(ROOT)),
                edicao_tipo='consolidada',
                meta=meta_c,
                dispositivos_conferidos=snippets,
                reconciliacao='provas/lgpd/reconciliacao-br-federal-lei-2018-08-14-13709-consolidada.json',
            ),
            'br-federal-lei-2026-02-25-15352': dict(
                arquivo=str(MODIFICADORA.relative_to(ROOT)),
                papel='modificadora',
                republicada_neste_catalogo=False,
                validacao=val_mod,
            ),
            'br-federal-medida-provisoria-2025-09-17-1317': dict(
                arquivo=str(MP1317.relative_to(ROOT)) if MP1317.is_file() else UNKNOWN,
                papel='medida-provisoria-convertida',
                snapshot_camara='provas/lgpd/fontes/camara-mp-1317-publicacaooriginal.html.xz',
                snapshot_planalto='provas/lgpd/fontes/planalto-mpv1317.htm.xz',
            ),
        },
        relacoes=[
            dict(
                tipo='alteracao',
                origem='br-federal-lei-2026-02-25-15352',
                destino='br-federal-lei-2018-08-14-13709',
                edicao_destino='br-federal-lei-2018-08-14-13709-consolidada',
                dispositivos=[d['dispositivo'] for d in DISPOSITIVOS_MP1317_LEI15352],
                fundamento='art. 1º da Lei nº 15.352/2026 (conversão da MP nº 1.317/2025)',
                prova_fontes=['camara-lgpd-atualizada', 'camara-lei-15352-original', 'planalto-lei-15352'],
            ),
            dict(
                tipo='alteracao',
                origem='br-federal-medida-provisoria-2025-09-17-1317',
                destino='br-federal-lei-2018-08-14-13709',
                edicao_destino='br-federal-lei-2018-08-14-13709-consolidada',
                dispositivos=[d['dispositivo'] for d in DISPOSITIVOS_MP1317_LEI15352],
                fundamento='MP nº 1.317/2025, convertida na Lei nº 15.352/2026 (notas da Câmara)',
                prova_fontes=['camara-lgpd-atualizada', 'camara-mp-1317', 'planalto-mp-1317'],
            ),
        ],
        escopo_cobertura=dict(
            estado='parcial',
            descricao=(
                'LGPD consolidada integral (Câmara) com conferência Planalto; edição histórica '
                'preservada; Lei 15.352 reutilizada sem republicação (anexos tabulares só no '
                'snapshot Planalto). Não cobre todo o direito de proteção de dados.'
            ),
        ),
        desconhecidos=[
            'fonte/captura originais da edição histórica da LGPD',
            'vigência/eficácia residual de dispositivos não alterados — não certificada',
            'anexos tabulares da Lei 15.352 no Markdown já publicado da modificadora',
        ],
        historica_vs_consolidada='provas/lgpd/historica-vs-consolidada-13709.json',
        fontes='provas/lgpd/fontes.json',
        reconciliacao_resumo={
            'identicos': reconciliacao.get('identicos'),
            'divergentes': len(reconciliacao.get('divergentes', [])),
            'divergencias_de_forma': reconciliacao.get('divergencias_de_forma'),
            'divergencias_substanciais': reconciliacao.get('divergencias_substanciais'),
            'apenas_na_principal': reconciliacao.get('apenas_na_principal'),
            'apenas_na_conferencia': reconciliacao.get('apenas_na_conferencia'),
        },
        hist_vs_cons_foco=hist_vs_cons.get('foco_dispositivos_mp1317_lei15352'),
    )


def cmd_import(args):
    capturado_em = args.capturado_em or CAPTURA_PADRAO
    fontes = import_captures(Path(args.src), capturado_em)
    print(f'importadas {len(fontes)} fontes em {PROVAS / "fontes.json"}')


def cmd_build(args):
    fontes = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
    # Corpo histórico: se o arquivo já tem frontmatter, extrai o corpo após a nota;
    # senão usa o arquivo inteiro como corpo original a preservar.
    raw = HISTORICA.read_text(encoding='utf-8')
    if raw.startswith('---\n'):
        _, body = parse_frontmatter(raw)
        m = re.search(r'<!-- nota-edicao:fim -->\n\n(.*)\Z', body, re.S)
        if not m:
            raise RuntimeError('edição histórica com cabeçalho sem nota-edicao')
        corpo_original = m.group(1)
    else:
        corpo_original = raw if raw.endswith('\n') else raw + '\n'

    cam_data = read_snapshot('camara-lgpd-atualizada')
    if sha256(cam_data) != fontes['camara-lgpd-atualizada']['sha256']:
        raise RuntimeError('snapshot Câmara diverge de fontes.json')
    pla_data = read_snapshot('planalto-lgpd')
    if sha256(pla_data) != fontes['planalto-lgpd']['sha256']:
        raise RuntimeError('snapshot Planalto diverge de fontes.json')

    conv = convert_html(cam_data, 'utf-8', SOURCES['camara-lgpd-atualizada']['url'])
    blocks = trim_lgpd_blocks(conv.blocks)
    body_md = blocks_to_markdown(blocks, r'^LEI\s+N')
    if not coverage(blocks, body_md):
        raise RuntimeError('falha de cobertura Câmara→Markdown')

    snippets = extract_device_snippets(body_md)

    # Reconciliação Câmara (principal) × Planalto (conferência)
    pla_conv = convert_html(pla_data, 'cp1252', SOURCES['planalto-lgpd']['url'])
    reconciliacao, arts_cam, arts_pla = article_proof(blocks, pla_conv.blocks)
    # Registrar divergências conhecidas de forma (não misturar redações)
    reconciliacao['fonte_principal'] = 'camara-lgpd-atualizada'
    reconciliacao['fonte_conferencia'] = 'planalto-lgpd'
    reconciliacao['tratamento'] = (
        'Markdown consolidado segue a Câmara (norma atualizada). Divergências de forma/'
        'segmentação com o Planalto permanecem explícitas; redações não foram combinadas.'
    )
    write_json(PROVAS / 'reconciliacao-br-federal-lei-2018-08-14-13709-consolidada.json', reconciliacao)

    hist_text, meta_h = build_historica(corpo_original)
    cons_text, meta_c = build_consolidada(body_md, fontes, conv.stats)
    # Recalcula sha256_markdown após saber o body final (já feito em build_*)

    CONSOLIDADA.parent.mkdir(parents=True, exist_ok=True)
    HISTORICA.write_text(hist_text, encoding='utf-8')
    CONSOLIDADA.write_text(cons_text, encoding='utf-8')

    # Prova: markdown consolidado reconvertível a partir do snapshot (cobertura)
    cobertura = dict(
        equivalente=coverage(blocks, body_md),
        sha256_blocos=sha256('\n\n'.join(blocks).encode('utf-8')),
        sha256_corpo_markdown_sem_nota=sha256(body_md.encode('utf-8')),
        n_blocos=len(blocks),
        prova='reconversão offline: lzma.open(snapshot) → convert_html → trim → blocks_to_markdown ≡ corpo',
    )
    write_json(PROVAS / 'cobertura-conversao-camara.json', cobertura)

    hist_vs = historica_vs_consolidada(corpo_original, blocks)
    write_json(PROVAS / 'historica-vs-consolidada-13709.json', hist_vs)

    val_mod = validate_modificadora(fontes)
    write_json(PROVAS / 'validacao-lei-15352.json', val_mod)

    manifesto = build_manifesto(fontes, meta_h, meta_c, snippets, reconciliacao, hist_vs, val_mod)
    write_json(MANIFESTO, manifesto)

    # Dispositivos-alvo para testes
    write_json(PROVAS / 'dispositivos-alvo-mp1317-lei15352.json', dict(
        dispositivos=DISPOSITIVOS_MP1317_LEI15352,
        snippets=snippets,
        notas_camara_presentes={k: snippets[k] for k in snippets if k.startswith('nota_')},
    ))

    print('histórico', meta_h['sha256_corpo_preservado'])
    print('consolidada', meta_c['sha256_markdown'], 'fonte', meta_c['sha256_fonte'])
    print('reconciliacao identicos', reconciliacao['identicos'],
          'divergentes', len(reconciliacao['divergentes']))


def cmd_verify(args):
    problems = []
    fontes = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
    for key, rec in fontes.items():
        data = read_snapshot(key)
        if sha256(data) != rec['sha256']:
            problems.append(f'{key}: sha256 snapshot ≠ fontes.json')
        if content_sha256(data) != rec.get('sha256_conteudo'):
            problems.append(f'{key}: sha256_conteudo diverge')
        snap = snapshot_path(key)
        if sha256(snap.read_bytes()) != rec.get('sha256_snapshot_armazenado'):
            problems.append(f'{key}: sha256_snapshot_armazenado diverge')

    meta_h, body_h = parse_frontmatter(HISTORICA.read_text(encoding='utf-8'))
    m = re.search(r'<!-- nota-edicao:fim -->\n\n(.*)\Z', body_h, re.S)
    if not m:
        problems.append('histórica: nota-edicao ausente')
        corpo = ''
    else:
        corpo = m.group(1)
        if sha256(corpo.encode('utf-8')) != meta_h.get('sha256_corpo_preservado'):
            problems.append('histórica: sha256_corpo_preservado diverge do corpo')
        if 'Alerta por dispositivo' not in body_h:
            problems.append('histórica: alerta por dispositivo ausente')
        if 'Autoridade Nacional de Proteção de Dados (ANPD)' not in corpo:
            problems.append('histórica: corpo não preserva redação Autoridade no art. 55-A')

    meta_c, body_c = parse_frontmatter(CONSOLIDADA.read_text(encoding='utf-8'))
    if meta_c.get('sha256_markdown') != sha256(body_c.encode('utf-8')):
        problems.append('consolidada: sha256_markdown diverge')
    if meta_c.get('sha256_fonte') != fontes['camara-lgpd-atualizada']['sha256']:
        problems.append('consolidada: sha256_fonte ≠ captura Câmara')
    if meta_c.get('fonte_url') in (meta_c.get('fonte_conferencia') or []):
        problems.append('consolidada: fonte_conferencia repete fonte_url')

    # Reconversão integral offline
    cam = read_snapshot('camara-lgpd-atualizada')
    conv = convert_html(cam, 'utf-8', SOURCES['camara-lgpd-atualizada']['url'])
    blocks = trim_lgpd_blocks(conv.blocks)
    body_md = blocks_to_markdown(blocks, r'^LEI\s+N')
    if not body_md.endswith('\n'):
        body_md += '\n'
    # corpo publicado = nota + body_md
    if '<!-- nota-edicao:fim -->' not in body_c:
        problems.append('consolidada: nota-edicao ausente')
    else:
        published_corpo = body_c.split('<!-- nota-edicao:fim -->\n\n', 1)[1]
        if published_corpo != body_md:
            problems.append('consolidada: corpo ≠ reconversão byte a byte do snapshot Câmara')

    if not coverage(blocks, body_md):
        problems.append('cobertura convert_html falhou')

    try:
        snippets = extract_device_snippets(body_md)
    except ValueError as e:
        problems.append(f'dispositivos: {e}')
        snippets = {}

    # Negativo: histórica não deve passar nos trechos consolidados-alvo
    if corpo:
        if 'Agência Nacional de Proteção de Dados (ANPD), autarquia de natureza especial vinculada ao Ministério da Justiça' in corpo:
            problems.append('histórica já contém redação consolidada do art. 55-A (sobrescrita?)')
        if re.search(r'VIII\s*[-–]\s*encarregado:.*?Agência Nacional de Proteção de Dados \(ANPD\)', corpo, re.S):
            problems.append('histórica já contém art. 5º VIII com Agência (sobrescrita?)')

    val = validate_modificadora(fontes)
    if val.get('anexos_tabulares_no_markdown_publicado'):
        # not a problem — just unexpected; keep explicit
        pass

    # Manifesto
    man = json.loads(MANIFESTO.read_text(encoding='utf-8'))
    if man['documentos']['br-federal-lei-2018-08-14-13709']['meta']['sha256_corpo_preservado'] != meta_h.get('sha256_corpo_preservado'):
        problems.append('manifesto: hash histórica diverge')
    if not man['relacoes']:
        problems.append('manifesto: relações ausentes')

    if problems:
        print('VERIFY FAIL')
        for p in problems:
            print(' -', p)
        sys.exit(1)
    print('VERIFY OK', len(snippets), 'snippets', meta_c['edicao_id'])


def main():
    parser = argparse.ArgumentParser(description='LGPD — catálogo temático')
    sub = parser.add_subparsers(dest='cmd', required=True)
    p_imp = sub.add_parser('import-captures')
    p_imp.add_argument('--src', required=True)
    p_imp.add_argument('--capturado-em', default=None)
    p_imp.set_defaults(func=cmd_import)
    p_build = sub.add_parser('build')
    p_build.set_defaults(func=cmd_build)
    p_ver = sub.add_parser('verify')
    p_ver.set_defaults(func=cmd_verify)
    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
