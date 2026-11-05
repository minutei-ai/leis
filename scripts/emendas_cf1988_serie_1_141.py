"""Matriz unificada da série Emendas CF/1988 nº 1–141 (issue #63).

Consolida a cobertura já publicada pelos lotes de faixa (PRs #91, #92, #97).
Não altera README agregado. Distingue a série CF/1988 de emendas históricas e
de revisão.

Além da contagem 141/141, este lote:
- acrescenta frontmatter contrato_versao=1 aos Markdown sem metadados;
- registra mapa Constituição/ADCT → ato/dispositivos autônomos (escopo literal do issue);
- mantém issue_fechavel=false até critérios restantes e revisão humana.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FED = ROOT / 'federal'
PROVAS = ROOT / 'provas/emendas-cf1988'
OUT = PROVAS / 'serie-1-141'
MATRIZ = OUT / 'matriz-serie.json'
CRITERIOS = OUT / 'matriz-criterios-aceite.json'
MAPA = OUT / 'mapa-constituicao-adct-dispositivos.json'
MANIFESTO_FM = OUT / 'manifesto-frontmatter.json'
FONTES_CONFERENCIA = OUT / 'fontes-conferencia/fontes-conferencia.json'
CONSTITUICAO = FED / 'br-federal-constituicao-1988-10-05.md'
LOTE = 'emendas-cf1988-serie-1-141'
CONTRACT_VERSION = 1
PRS = [
    'https://github.com/minutei-ai/leis/pull/91',
    'https://github.com/minutei-ai/leis/pull/92',
    'https://github.com/minutei-ai/leis/pull/97',
]

AUTON_MARKERS = (
    'esta emenda entra',
    'esta emenda constitucional entra',
    'revogam-se',
    'revoga-se',
    'fica revogado',
    'ficam revogados',
    'disposições transitórias',
    'disposicoes transitorias',
    'disposição transitória',
    'produção de efeitos',
    'producao de efeitos',
    'anexo',
    'artigo único',
    'artigo unico',
)

FAIXA_001_050_MATRIZ = PROVAS / 'faixa-001-050/matriz-lote.json'
FAIXA_001_050_FONTES = PROVAS / 'faixa-001-050/fontes.json'


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_frontmatter(text: str) -> dict:
    if not text.startswith('---\n'):
        return {}
    end = text.find('\n---\n', 4)
    if end < 0:
        return {}
    meta = {}
    for line in text[4:end].splitlines():
        if ':' not in line:
            continue
        key, _, value = line.partition(':')
        raw = value.strip()
        try:
            meta[key.strip()] = json.loads(raw)
        except Exception:
            meta[key.strip()] = raw.strip('"')
    return meta


def body_of(text: str) -> str:
    if text.startswith('---\n'):
        end = text.find('\n---\n', 4)
        if end > 0:
            body = text[end + 5:]
            # Linha em branco editorial após o fence não integra o corpo hasheado.
            if body.startswith('\n'):
                body = body[1:]
            return body
    return text


def dump_frontmatter(meta: dict) -> str:
    lines = ['---']
    for key, value in meta.items():
        lines.append(f'{key}: {json.dumps(value, ensure_ascii=False)}')
    lines.append('---\n\n')
    return '\n'.join(lines)


def has_autonomous_markers(body: str) -> bool:
    low = body.lower()
    if any(m in low for m in AUTON_MARKERS):
        return True
    if re.search(r'art\.\s*\d+º?\s*[.—-].{0,100}(vigor|revog|aplica|efeito|transit)', low):
        return True
    if re.search(r'\bvedad[ao]\b.{0,160}medida provis[oó]ria|\bproibid[ao]\b.{0,160}medida provis[oó]ria', low):
        return True
    if re.search(r'artigo\s+único|artigo\s+unico|art\.\s*único|art\.\s*unico', low):
        return True
    return False


def extract_cf_ec_citations(text: str) -> set[int]:
    cites = set()
    for m in re.finditer(r'[Ee]menda\s+[Cc]onstitucional\s+n[ºo°\.]*\s*(\d+)', text):
        n = int(m.group(1))
        if 1 <= n <= 141:
            cites.add(n)
    return cites


def split_cf_adct(text: str) -> tuple[str, str]:
    m = re.search(r'ATO DAS DISPOSI[ÇC][ÕO]ES CONSTITUCIONAIS TRANSIT[ÓO]RIAS', text, re.I)
    if not m:
        return text, ''
    return text[:m.start()], text[m.start():]


def _autonomous_device_role(article_text: str) -> str | None:
    """Classifica proibições expressas fora de uma cláusula de alteração CF/ADCT."""
    low = article_text.lower()
    prohibition = re.search(
        r'\bvedad[ao]\b.{0,180}medida provis[oó]ria|'
        r'\bproibid[ao]\b.{0,180}medida provis[oó]ria',
        low,
    )
    if not prohibition:
        return None
    # A proibição do EC 7/Art. 2º está dentro do art. 246 incluído na CF. O
    # mesmo vale para qualquer cláusula que introduz redação constitucional.
    introduces_cf_text = re.search(
        r'passa(?:m)? a vigorar|fica(?:m)? inclu[ií]d[oa]s?|inclua-se|'
        r'acrescent(?:a|e)(?:-se)?|introduz(?:ido|ida)|com a seguinte redação',
        low,
    )
    return None if introduces_cf_text else 'proibicao-autonoma'


def extract_dispositivos_autonomos(dispositivos: dict) -> list[dict]:
    return [
        artigo for artigo in dispositivos['artigos']
        if artigo['papel'] in {
            'producao-efeitos-ou-vigencia-textual',
            'revogacao',
            'transitorio-autonomo',
            'proibicao-autonoma',
            'dispositivo-autonomo-regra-nao-classificada',
        }
    ] + [
        {'dispositivo': anexo['dispositivo'], 'papel': 'anexo', 'trecho_inicial': anexo['trecho_inicial']}
        for anexo in dispositivos['anexos']
    ]


def _mask_quoted_text(text: str) -> str:
    """Masks paired quoted spans while preserving offsets and line boundaries."""
    chars = list(text)
    i = 0
    while i < len(text):
        opener = text[i]
        preferred, fallback = {
            '“': ('”', '"'),
            '"': ('"', '”'),
            '‘': ('’', "'"),
        }.get(opener, (None, None))
        if preferred is None:
            i += 1
            continue
        j = text.find(preferred, i + 1)
        if j < 0 and fallback is not None:
            j = text.find(fallback, i + 1)
        if j < 0 or j >= len(text):
            i += 1
            continue
        for k in range(i, j + 1):
            if chars[k] != '\n':
                chars[k] = ' '
        i = j + 1
    return ''.join(chars)


def _classify_article(article_text: str) -> tuple[str, str, str]:
    """Classifies only from literal, unquoted wording; does not infer legal effects."""
    outer = _mask_quoted_text(article_text)
    low = outer.lower()
    amendment = re.search(
        r'passa(?:m)?\s+a\s+vigorar|fica(?:m)?\s+inclu[ií]d[oa]s?|'
        r'acrescent(?:a|e)(?:-se)?|é\s+acrescid[oa]|'
        r'dá\s+nova\s+redação|alter(?:a|am)\s+(?:o|a|os|as)\s+', low,
    )
    if amendment:
        return ('altera-cf-ou-adct', 'expressão operacional literal: ' + outer[amendment.start():amendment.end()].strip(), 'texto-exterior-a-citacao')
    if re.search(r'entra(?:r)?\s+em\s+vigor|produ[cç][aã]o\s+de\s+efeitos|aplica-se', low):
        return ('producao-efeitos-ou-vigencia-textual', 'regra literal de vigência/efeitos no artigo', 'texto-exterior-a-citacao')
    if re.search(r'\brevog(?:a|am|ado|ada|ados|adas)\b', low):
        return ('revogacao', 'regra literal de revogação no artigo', 'texto-exterior-a-citacao')
    if re.search(r'\bvedad[ao]\b.{0,180}medida provis[oó]ria|\bproibid[ao]\b.{0,180}medida provis[oó]ria', low):
        return ('proibicao-autonoma', 'proibição de medida provisória expressa fora de redação inserida', 'texto-exterior-a-citacao')
    if re.search(r'disposi[cç][oõ]es?\s+transit', low):
        return ('transitorio-autonomo', 'referência literal a disposições transitórias no artigo', 'texto-exterior-a-citacao')
    return ('dispositivo-autonomo-regra-nao-classificada', 'artigo principal segmentado fora de aspas; nenhuma regra de classificação literal reconhecida', 'revisao-explicita-sem-inferencia-de-efeito')


def extract_dispositivos_emenda(body: str) -> dict:
    """Segmenta artigos e marca classes literais, sem inferir vigência."""
    # Inline formatting must not split an article label (`<strong>Art</strong>.`)
    # or insert spaces into `Artigo Único`. Preserve block boundaries and strip
    # indentation, which occurs in the inherited EC 9/12/44 bodies.
    plain = re.sub(r'(?i)<br\b[^>]*>', '\n', body)
    plain = re.sub(r'(?i)</?(?:p|div|tr|table|li|h[1-6])\b[^>]*>', '\n', plain)
    plain = re.sub(r'<[^>]+>', '', plain)
    plain = html.unescape(plain)
    plain = re.sub(r'\*\*|__|`', '', plain)
    # Some captured HTML places the next main article on the same line as a
    # closing quotation. Restore that structural boundary before masking the
    # inserted text, so Article 3 after a quoted Article 1 is still found.
    plain = re.sub(
        r'([”"])(?:[ \t]*\([A-Z]+\))?\s+(?=Art(?:igo)?[ \t]*\.?[ \t]*(?:único|unico|\d+[ºo°]?)(?:[ \t]*\.)?\b)',
        r'\1\n',
        plain,
    )
    # Legacy HTML sometimes joins the promulgation preamble and Article 1 in
    # one paragraph without a block tag.
    plain = re.sub(
        r'(?i)(promulgam[^\n]{0,240}:)[ \t]+(?=Art(?:igo)?[ \t]*\.?[ \t]*(?:único|unico|\d+[ºo°]?)(?:[ \t]*\.)?\b)',
        r'\1\n',
        plain,
    )
    plain = '\n'.join(line.strip() for line in plain.splitlines())
    article_start = r'(?:Art(?:igo)?[ \t]*\.?[ \t]*)(único|unico|\d+[ºo°]?)'
    outside_quotes = _mask_quoted_text(plain)
    starts = list(re.finditer(rf'(?im)^[ \t]*(?:#+[ \t]*)?{article_start}[ \t]*\.?', outside_quotes))
    annex_starts = [m.start() for m in re.finditer(r'(?im)^[ \t]*(?:#+[ \t]*)?ANEXO\b', outside_quotes)]
    arts = []
    for index, m in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(plain)
        next_annex = next((pos for pos in annex_starts if pos > m.start()), None)
        if next_annex is not None:
            end = min(end, next_annex)
        article_text = plain[m.start():end].strip()
        num = m.group(1)
        trecho = re.sub(r'\s+', ' ', article_text).strip()[:400]
        papel, regra, hierarquia = _classify_article(article_text)
        low = article_text.lower()
        nested_insertions = []
        for quoted in re.finditer(r'[“\"](.*?)[”\"]', article_text, re.S):
            introduction = article_text[:quoted.start()].lower()
            insertion_rule = re.search(
                r'(?:passa(?:m)?\s+a\s+vigorar|fica(?:m)?\s+inclu[ií]d[oa]s?|'
                r'acrescent(?:a|e)(?:-se)?|é\s+acrescid[oa]|'
                r'dá\s+nova\s+redação|com\s+a\s+seguinte\s+redação|'
                r'(?:os|as)\s+seguintes\s+artigos)',
                introduction,
            )
            if not insertion_rule:
                continue
            quoted_text = quoted.group(1)
            nested_heads = list(re.finditer(
                r'(?im)^[ \t]*(?:Art(?:igo)?[ \t]*\.?[ \t]*)(único|unico|\d+[ºo°]?)[ \t]*\.?',
                quoted_text,
            ))
            for nested_index, nested in enumerate(nested_heads):
                nested_end = nested_heads[nested_index + 1].start() if nested_index + 1 < len(nested_heads) else len(quoted_text)
                nested_insertions.append({
                    'dispositivo': f'Art. {nested.group(1)}',
                    'papel': 'texto-de-redacao-inserida-citada',
                    'hierarquia': 'conteudo-citado-dentro-do-artigo-principal',
                    'trecho_auditado': re.sub(r'\s+', ' ', quoted_text[nested.start():nested_end]).strip()[:400],
                    'regra_classificacao': 'cabeçalho dentro de aspas sob expressão literal introdutória: ' + article_text[insertion_rule.start():insertion_rule.end()],
                })
        alvo = []
        if re.search(r'\bADCT\b|disposi[cç][oõ]es constitucionais transit', low):
            alvo.append('ADCT')
        if re.search(r'constitui[cç][aã]o(?:\s+federal)?|\bart\.?\s*\d+', low):
            if 'ADCT' not in alvo or 'constitui' in low:
                alvo.append('CF')
        arts.append({
            'dispositivo': f'Art. {num}',
            'papel': papel,
            'regra_classificacao': regra,
            'hierarquia': hierarquia,
            'alvos_mencionados': alvo or ['desconhecido'],
            'trecho_inicial': trecho[:240],
            'trecho_auditado': trecho,
            'redacao_inserida_citada': nested_insertions,
        })
    anexos = []
    for m in re.finditer(r'(?im)^[ \t]*(?:#+[ \t]*)?ANEXO\b(.*)$', plain):
        anexos.append({'dispositivo': 'ANEXO', 'trecho_inicial': re.sub(r'\s+', ' ', m.group(0)).strip()[:240]})
    return {
        'artigos': arts,
        'anexos': anexos,
        'tem_marcadores_autonomos': has_autonomous_markers(body),
    }


def load_faixa_001_050_provenance() -> dict[int, dict]:
    out: dict[int, dict] = {}
    if not FAIXA_001_050_MATRIZ.is_file() or not FAIXA_001_050_FONTES.is_file():
        return out
    matriz = json.loads(FAIXA_001_050_MATRIZ.read_text(encoding='utf-8'))
    fontes = json.loads(FAIXA_001_050_FONTES.read_text(encoding='utf-8'))
    for item in matriz.get('itens', []):
        n = int(item['numero'])
        if item.get('situacao_coleta') != 'publicada':
            continue
        key = f'camara-ec-{n:03d}-publicacaooriginal'
        fonte = fontes.get(key) or {}
        planalto_key = f'planalto-ec-{n:03d}'
        planalto = fontes.get(planalto_key) or {}
        conf = []
        if planalto.get('url') and planalto.get('utilizavel'):
            conf.append(planalto['url'])
        out[n] = {
            'fonte_orgao': 'Câmara dos Deputados',
            'fonte_url': item.get('url_camara') or fonte.get('url') or 'desconhecido',
            'fonte_formato': 'html',
            'fonte_conferencia': conf if conf else 'nenhuma',
            'capturado_em': fonte.get('capturado_em') or 'desconhecido',
            'sha256_fonte': fonte.get('sha256') or 'desconhecido',
            'edicao_tipo': 'historica',
            'edicao_integral': True if fonte.get('sha256') else 'desconhecido',
            'snapshot': fonte.get('snapshot'),
            'origem_metadados': 'faixa-001-050',
            'titulo_sugerido': None,
            'ementa': item.get('ementa'),
        }
    return out


def planalto_emc_url(n: int) -> str:
    return f'https://www.planalto.gov.br/ccivil_03/constituicao/emendas/emc/emc{n}.htm'


def build_meta_for_body(path: Path, body: str, prov: dict | None) -> dict:
    m = re.fullmatch(
        r'br-federal-emenda-constitucional-(\d{4})-(\d{2})-(\d{2})-(\d+)\.md',
        path.name,
    )
    assert m
    year, month, day, numero = m.group(1), m.group(2), m.group(3), int(m.group(4))
    slug = path.stem
    data = f'{year}-{month}-{day}'
    titulo = f'EMENDA CONSTITUCIONAL Nº {numero}, DE {day}/{month}/{year}'
    # tentar epígrafe do corpo
    mt = re.search(rf'EMENDA CONSTITUCIONAL Nº\s*{numero}\b[^\n]*', body, re.I)
    if mt:
        titulo = re.sub(r'<[^>]+>', '', mt.group(0)).strip()
    anexos = len(re.findall(r'(?im)^(?:#+\s*)?ANEXO\b', body))
    tabelas = body.count('<table') + len(re.findall(r'(?m)^\s*\|.+\|', body)) // 3
    if prov:
        fonte_orgao = prov['fonte_orgao']
        fonte_url = prov['fonte_url']
        fonte_formato = prov.get('fonte_formato') or 'html'
        fonte_conferencia = prov.get('fonte_conferencia') or 'nenhuma'
        capturado_em = prov.get('capturado_em') or 'desconhecido'
        sha256_fonte = prov.get('sha256_fonte') or 'desconhecido'
        edicao_tipo = prov.get('edicao_tipo') or 'historica'
        edicao_integral = prov.get('edicao_integral', 'desconhecido')
        origem = prov.get('origem_metadados') or 'desconhecido'
    else:
        # Corpo preservado no acervo antes do contrato; captura original não registrada.
        fonte_orgao = 'desconhecido'
        fonte_url = 'desconhecido'
        fonte_formato = 'desconhecido'
        fonte_conferencia = [planalto_emc_url(numero)]
        capturado_em = 'desconhecido'
        sha256_fonte = 'desconhecido'
        edicao_tipo = 'historica'
        edicao_integral = 'desconhecido'
        origem = 'corpo-preservado-pre-metadados'
    meta = {
        'id': slug,
        'norma_id': slug,
        'norma_tipo': 'emenda-constitucional',
        'norma_numero': str(numero),
        'norma_data': data,
        'titulo': titulo,
        'esfera': 'federal',
        'edicao_id': f'{slug}@historica-acervo',
        'edicao_tipo': edicao_tipo,
        'edicao_integral': edicao_integral,
        'fonte_orgao': fonte_orgao,
        'fonte_url': fonte_url,
        'fonte_formato': fonte_formato,
        'fonte_conferencia': fonte_conferencia,
        'capturado_em': capturado_em,
        'sha256_fonte': sha256_fonte,
        'situacao': 'nao-informada',
        'situacao_fundamento': 'desconhecido',
        'vigencia_certificada': False,
        'texto_riscado': '~~' in body,
        'anexos_no_corpo': anexos,
        'tabelas': tabelas,
        'imagens_omitidas': 0,
        'efeitos_diferidos': 'preservados-nas-notas-do-texto',
        'sha256_markdown': sha256_text(body),
        'manifesto': str(MANIFESTO_FM.relative_to(ROOT)),
        'contrato_versao': CONTRACT_VERSION,
        'metadados_origem': origem,
    }
    return meta


def ensure_frontmatter(dry_run: bool = False) -> dict:
    """Acrescenta frontmatter contrato aos MD da série sem cabeçalho; preserva o corpo."""
    OUT.mkdir(parents=True, exist_ok=True)
    faixa_prov = load_faixa_001_050_provenance()
    updated = []
    skipped = []
    for path in sorted(FED.glob('br-federal-emenda-constitucional-*.md')):
        m = re.fullmatch(
            r'br-federal-emenda-constitucional-(\d{4})-(\d{2})-(\d{2})-(\d+)\.md',
            path.name,
        )
        if not m or int(m.group(1)) < 1988:
            continue
        numero = int(m.group(4))
        if not (1 <= numero <= 141):
            continue
        text = path.read_text(encoding='utf-8')
        if text.startswith('---\n'):
            skipped.append(numero)
            continue
        body = text if text.endswith('\n') else text + '\n'
        # Preservar bytes do corpo: se o arquivo não termina com \n, manter como está
        body_raw = text
        meta = build_meta_for_body(path, body_raw, faixa_prov.get(numero))
        # sha256 do corpo exatamente como publicado
        meta['sha256_markdown'] = sha256_text(body_raw)
        new_text = dump_frontmatter(meta) + body_raw
        if not dry_run:
            path.write_text(new_text, encoding='utf-8')
        updated.append({
            'numero': numero,
            'arquivo': f'federal/{path.name}',
            'metadados_origem': meta['metadados_origem'],
            'fonte_url': meta['fonte_url'],
            'sha256_markdown': meta['sha256_markdown'],
            'capturado_em': meta['capturado_em'],
        })
    manifesto = {
        'lote': LOTE,
        'papel': 'frontmatter-serie-1-141',
        'issue': 63,
        'gerado_em': now_utc(),
        'contrato_versao': CONTRACT_VERSION,
        'aviso': (
            'Frontmatter acrescentado sem alterar o corpo jurídico. '
            'capturado_em/sha256_fonte=desconhecido quando a captura original do corpo '
            'publicado não estava registrada; fonte_conferencia pode apontar URL oficial '
            'Planalto só para conferência, sem atribuir captura retroativa.'
        ),
        'atualizados': updated,
        'ja_com_frontmatter': skipped,
        'contagem': {
            'atualizados': len(updated),
            'ja_com_frontmatter': len(skipped),
        },
    }
    if not dry_run:
        MANIFESTO_FM.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifesto


def build_mapa_vinculos(present: dict[int, dict]) -> dict:
    cf_text = CONSTITUICAO.read_text(encoding='utf-8') if CONSTITUICAO.is_file() else ''
    cf_part, adct_part = split_cf_adct(cf_text)
    cites_cf = extract_cf_ec_citations(cf_part)
    cites_adct = extract_cf_ec_citations(adct_part)
    itens = []
    for n in range(1, 142):
        info = present.get(n)
        if not info:
            itens.append({
                'emenda': n,
                'estado': 'lacuna-arquivo-autonomo',
                'citada_na_constituicao': n in cites_cf,
                'citada_no_adct': n in cites_adct,
                'arquivo': None,
                'dispositivos_autonomos': [],
                'lacunas': ['texto-autonomo-ausente'],
            })
            continue
        body = body_of((ROOT / info['arquivo']).read_text(encoding='utf-8'))
        disp = extract_dispositivos_emenda(body)
        autonomos = extract_dispositivos_autonomos(disp)
        # Emenda é sempre o ato autônomo; dispositivos que só alteram CF/ADCT também vinculam.
        itens.append({
            'emenda': n,
            'estado': 'mapeado',
            'arquivo': info['arquivo'],
            'citada_na_constituicao': n in cites_cf,
            'citada_no_adct': n in cites_adct,
            'dispositivos_do_ato': disp['artigos'],
            'dispositivos_autonomos': autonomos,
            'anexos_no_ato': disp['anexos'],
            'tem_marcadores_autonomos': disp['tem_marcadores_autonomos'],
            'lacunas': (
                [] if disp['artigos'] or disp['tem_marcadores_autonomos']
                else ['dispositivos-nao-segmentados-heuristicamente']
            ),
        })
    return {
        'lote': LOTE,
        'issue': 63,
        'gerado_em': now_utc(),
        'escopo': (
            'Mapa Constituição/ADCT → emenda autônoma e dispositivos do ato. '
            'Não é mapa artigo-a-artigo de toda a CF; respeita o critério literal do issue #63.'
        ),
        'constituicao_arquivo': 'federal/br-federal-constituicao-1988-10-05.md' if CONSTITUICAO.is_file() else None,
        'contagem': {
            'emendas': 141,
            'citadas_na_cf': len(cites_cf),
            'citadas_no_adct': len(cites_adct),
            'com_dispositivos_autonomos_detectados': sum(1 for i in itens if i.get('dispositivos_autonomos')),
            'com_lacuna_segmentacao': sum(1 for i in itens if i.get('lacunas')),
            'dispositivos_com_revisao_explicita': sum(
                1 for item in itens for artigo in item.get('dispositivos_do_ato', [])
                if artigo.get('hierarquia') == 'revisao-explicita-sem-inferencia-de-efeito'
            ),
            'redacoes_inseridas_citadas': sum(
                len(artigo.get('redacao_inserida_citada', []))
                for item in itens for artigo in item.get('dispositivos_do_ato', [])
            ),
            'dispositivos_por_papel': {
                papel: sum(
                    1 for item in itens for artigo in item.get('dispositivos_do_ato', [])
                    if artigo.get('papel') == papel
                )
                for papel in sorted({
                    artigo.get('papel')
                    for item in itens for artigo in item.get('dispositivos_do_ato', [])
                })
            },
        },
        'limites': [
            'Citação na Constituição/ADCT não substitui o texto autônomo da emenda.',
            'Ausência de citação não prova inexistência de vínculo jurídico.',
            'Segmentação de dispositivos é heurística sobre o Markdown publicado; não certifica vigência.',
            'Não se impõe mapa dispositivo-a-dispositivo além do vínculo ato ↔ CF/ADCT exigido pelo issue.',
        ],
        'itens': itens,
    }


def load_fontes_conferencia_atual() -> dict[int, dict]:
    """Retorna provas atuais de conferência, sem preencher origem histórica desconhecida."""
    if not FONTES_CONFERENCIA.is_file():
        return {}
    data = json.loads(FONTES_CONFERENCIA.read_text(encoding='utf-8'))
    return {int(item['emenda']): item for item in data.get('fontes', [])}


def load_reconciled_source_numbers() -> set[int]:
    """Numbers with preserved official captures and article reconciliation."""
    import lzma

    proven = set()
    sources = [
        (PROVAS / 'faixa-001-050/fontes.json', PROVAS / 'faixa-001-050/reconciliacao-camara-planalto.json'),
        (PROVAS / 'faixa-051-100/fontes.json', PROVAS / 'faixa-051-100'),
        (PROVAS / 'faixa-101-141/fontes.json', PROVAS / 'faixa-101-141'),
    ]
    for source_file, reconciliation in sources:
        if not source_file.is_file():
            continue
        data = json.loads(source_file.read_text(encoding='utf-8'))
        official_nums = set()
        for key, value in data.items():
            match = re.search(r'(?:planalto-emc|camara-ec-)(\d+)', key)
            if match and value.get('snapshot') and (ROOT / value['snapshot']).is_file():
                official_nums.add(int(match.group(1)))
        if reconciliation.is_file():
            reconciled = set(map(int, json.loads(reconciliation.read_text(encoding='utf-8'))))
        else:
            reconciled = {
                int(match.group(1)) for path in reconciliation.glob('reconciliacao-*.json')
                if (match := re.search(r'-(\d+)\.json$', path.name))
            }
        proven.update(official_nums & reconciled)
    current = load_fontes_conferencia_atual()
    rec_path = OUT / 'fontes-conferencia/reconciliacao-artigos.json'
    if rec_path.is_file():
        reconciled_current = {int(item['emenda']) for item in json.loads(rec_path.read_text(encoding='utf-8')).get('items', [])}
        proven.update(n for n, item in current.items() if n in reconciled_current and (ROOT / item['snapshot']).is_file())
    legacy_manifest_path = OUT / 'fontes-conferencia/fontes-conferencia-legados-1-106.json'
    legacy_reconciliation_path = OUT / 'fontes-conferencia/reconciliacao-artigos-legados-1-106.json'
    if legacy_manifest_path.is_file() and legacy_reconciliation_path.is_file():
        legacy = json.loads(legacy_manifest_path.read_text(encoding='utf-8'))
        recs = {int(item['emenda']) for item in json.loads(legacy_reconciliation_path.read_text(encoding='utf-8')).get('items', [])}
        for entry in legacy.get('fontes', []):
            n = int(entry['emenda'])
            if n not in recs:
                continue
            capture = entry['fonte_legislativa']
            stored = (ROOT / capture['snapshot']).read_bytes()
            raw = lzma.decompress(stored)
            if sha256_bytes(stored) == capture['sha256_snapshot_armazenado'] and sha256_bytes(raw) == capture['sha256_fonte']:
                proven.add(n)
    ec1_path = OUT / 'fontes-conferencia/conferencia-senado-ec1.json'
    if ec1_path.is_file() and legacy_reconciliation_path.is_file():
        ec1 = json.loads(ec1_path.read_text(encoding='utf-8'))
        recs = {int(item['emenda']) for item in json.loads(legacy_reconciliation_path.read_text(encoding='utf-8')).get('items', [])}
        if 1 in recs:
            valid = True
            for capture in ec1['capturas'].values():
                stored = (ROOT / capture['snapshot']).read_bytes()
                raw = lzma.decompress(stored)
                valid &= sha256_bytes(stored) == capture['sha256_snapshot_armazenado'] and sha256_bytes(raw) == capture['sha256_fonte']
            if valid:
                proven.add(1)
    return proven


def scan() -> dict:
    present: dict[int, dict] = {}
    for path in sorted(FED.glob('br-federal-emenda-constitucional-*.md')):
        m = re.fullmatch(
            r'br-federal-emenda-constitucional-(\d{4})-(\d{2})-(\d{2})-(\d+)\.md',
            path.name,
        )
        if not m:
            continue
        year, month, day, numero = int(m[1]), m[2], m[3], int(m[4])
        if year < 1988 or not (1 <= numero <= 141):
            continue
        text = path.read_text(encoding='utf-8')
        meta = parse_frontmatter(text)
        body = body_of(text)
        fonte = meta.get('fonte_url') or 'desconhecido'
        if fonte in {'', 'desconhecido'} and not meta:
            fonte = 'desconhecido-sem-frontmatter'
        present[numero] = {
            'numero': numero,
            'data': f'{year}-{month}-{day}',
            'arquivo': f'federal/{path.name}',
            'fonte_url': fonte,
            'fonte_conferencia': meta.get('fonte_conferencia', 'desconhecido'),
            'sha256_markdown': meta.get('sha256_markdown') or sha256_text(body),
            'serie': 'cf-1988',
            'especie': 'emenda-constitucional',
            'nao_e_revisao': True,
            'nao_e_constituicao_historica': True,
            'estado_coleta': 'publicado',
            'manifesto': meta.get('manifesto', 'desconhecido'),
            'tem_frontmatter': bool(meta),
            'edicao_tipo': meta.get('edicao_tipo', 'desconhecido'),
            'contrato_versao': meta.get('contrato_versao'),
            'dispositivos_autonomos_detectados': has_autonomous_markers(body),
            'tamanho_corpo': len(body.strip()),
        }

    historicas = []
    for path in sorted(FED.glob('br-federal-emenda-constitucional-*.md')):
        m = re.fullmatch(
            r'br-federal-emenda-constitucional-(\d{4})-(\d{2})-(\d{2})-(\d+)\.md',
            path.name,
        )
        if m and int(m[1]) < 1988:
            historicas.append({
                'numero': int(m[4]),
                'data': f'{m[1]}-{m[2]}-{m[3]}',
                'arquivo': f'federal/{path.name}',
                'serie': 'constituicao-historica',
            })

    revisao = sorted(p.name for p in FED.glob('br-federal-emenda*') if 'revis' in p.name.lower())
    missing = sorted(set(range(1, 142)) - set(present))

    mapa = build_mapa_vinculos(present)
    fontes_conferencia_atual = load_fontes_conferencia_atual()
    for numero, item in present.items():
        current = fontes_conferencia_atual.get(numero)
        if current:
            item['prova_conferencia_atual'] = {
                'manifesto': str(FONTES_CONFERENCIA.relative_to(ROOT)),
                'url': current['url'],
                'snapshot': current['snapshot'],
                'sha256_fonte': current['sha256_fonte'],
                'sha256_snapshot_armazenado': current['sha256_snapshot_armazenado'],
                'capturado_em': current['capturado_em'],
            }
    cf_cites = sorted({i['emenda'] for i in mapa['itens'] if i.get('citada_na_constituicao')})
    adct_cites = sorted({i['emenda'] for i in mapa['itens'] if i.get('citada_no_adct')})
    pub = set(present)
    vinculos = {
        'constituicao_arquivo': 'federal/br-federal-constituicao-1988-10-05.md' if CONSTITUICAO.is_file() else None,
        'emendas_citadas_na_constituicao': cf_cites,
        'emendas_citadas_no_adct': adct_cites,
        'publicadas_sem_citacao_na_constituicao': sorted(pub - set(cf_cites) - set(adct_cites)),
        'citadas_sem_arquivo_autonomo': sorted((set(cf_cites) | set(adct_cites)) - pub),
        'mapa_arquivo': str(MAPA.relative_to(ROOT)),
        'estado': 'registrado-com-mapa' if CONSTITUICAO.is_file() else 'nao-avaliado',
        'limites': mapa['limites'],
    }

    sem_frontmatter = sorted(n for n, it in present.items() if not it['tem_frontmatter'])
    sem_contrato = sorted(
        n for n, it in present.items()
        if not it['tem_frontmatter'] or it.get('contrato_versao') not in {1, '1', CONTRACT_VERSION}
    )
    sem_auton = sorted(n for n, it in present.items() if not it['dispositivos_autonomos_detectados'])
    fonte_desconhecida = sorted(
        n for n, it in present.items()
        if it['fonte_url'] in {'desconhecido', 'desconhecido-sem-frontmatter'}
    )

    meta_estado = 'satisfeito' if not sem_frontmatter and not sem_contrato else 'parcial'
    vinculo_estado = (
        'satisfeito' if vinculos['estado'] == 'registrado-com-mapa' else (
            'parcial' if vinculos['estado'].startswith('registrado') else 'pendente'
        )
    )
    # Textos: 141 atos publicados; mapa de dispositivos estruturado.
    textos_estado = 'satisfeito' if not missing and present and not mapa['contagem']['com_lacuna_segmentacao'] else 'pendente'

    criterios = {
        'issue': 63,
        'gerado_em': now_utc(),
        'aviso': (
            'Contagem 141/141 de arquivos da série é necessária, mas insuficiente. '
            'Esta matriz avalia cada critério de aceite do issue.'
        ),
        'itens': [
            {
                'id': 'matriz-por-numero-data-fonte-situacao',
                'criterio': 'Criar matriz por número, data, fonte e situação da coleta, reconciliando a série com catálogo oficial.',
                'estado': 'satisfeito' if not missing and present else 'pendente',
                'evidencia': str(MATRIZ.relative_to(ROOT)),
                'notas': [
                    f"publicados={len(present)} lacunas={len(missing)}",
                    'Reconciliação detalhada Câmara×Planalto permanece nas pastas de faixa.',
                ],
            },
            {
                'id': 'textos-integrais-com-dispositivos-autonomos',
                'criterio': 'Recuperar atos integrais ausentes, incluindo dispositivos autônomos, anexos, regras transitórias, revogações e produção de efeitos.',
                'estado': textos_estado,
                'evidencia': {
                    'arquivos_serie': len(present),
                    'com_marcadores_autonomos': len(present) - len(sem_auton),
                    'sem_marcadores_autonomos_heuristica': sem_auton,
                    'lacunas_segmentacao': mapa['contagem']['com_lacuna_segmentacao'],
                    'mapa_dispositivos': str(MAPA.relative_to(ROOT)),
                    'reconciliacao_artigos_fontes_conferidas': str(
                        (OUT / 'fontes-conferencia/reconciliacao-artigos.json').relative_to(ROOT)
                    ),
                    'capturas_oficiais_legados_adicionais': str(
                        (OUT / 'fontes-conferencia/fontes-conferencia-legados-1-106.json').relative_to(ROOT)
                    ),
                },
                'notas': [
                    'Cada arquivo é o ato autônomo publicado (não só a redação incorporada à CF).',
                    'Dispositivos autônomos/anexos/revogações/efeitos estão no mapa por emenda.',
                    'A conferência literal de EC 9, 12 e 44 está registrada por dispositivo; diferenças tipográficas não alteram o Markdown legado.',
                    'Cobertura textual mede recuperação e mapeamento dos atos; não certifica equivalência a uma captura histórica.',
                    'Nenhuma lacuna do mapa é convertida em afirmação de ausência legal sem prova.',
                ],
            },
            {
                'id': 'classificacao-literal-sem-inferencia',
                'criterio': 'Expor os trechos e a regra literal de classificação por dispositivo, mantendo os casos não classificados disponíveis para revisão sem inferir efeito jurídico.',
                'estado': 'parcial' if mapa['contagem']['dispositivos_com_revisao_explicita'] else 'satisfeito',
                'evidencia': {
                    'dispositivos_com_trecho_regra_e_hierarquia': sum(
                        len(item.get('dispositivos_do_ato', [])) for item in mapa['itens']
                    ),
                    'revisao_explicita_sem_inferencia': mapa['contagem']['dispositivos_com_revisao_explicita'],
                    'itens_disponiveis_no_mapa': True,
                    'mapa': str(MAPA.relative_to(ROOT)),
                },
                'notas': [
                    'Revisão de classificação não reduz a cobertura textual nem remove trechos do mapa.',
                    'Trechos citados permanecem subordinados ao dispositivo introdutório; não são contados como artigos principais.',
                ],
            },
            {
                'id': 'conferencia-atual-das-edicoes-sem-substituicao',
                'criterio': 'Preservar capturas oficiais atuais e confrontos literais sem atribuí-los à proveniência original desconhecida nem substituir silenciosamente textos legados.',
                'estado': 'parcial' if len(load_reconciled_source_numbers()) < 141 else 'satisfeito',
                'evidencia': {
                    'atos_com_captura_oficial_e_reconciliacao_com_hash_validado': len(load_reconciled_source_numbers()),
                    'total': 141,
                    'conferencias_adicionais_legadas': str((OUT / 'fontes-conferencia/reconciliacao-artigos-legados-1-106.json').relative_to(ROOT)),
                    'proveniencia_original_desconhecida_preservada': True,
                },
                'notas': [
                    'Conferência atual é evidência separada; não preenche fonte_url, data ou hash originais desconhecidos.',
                    'Diferenças literais e pareamentos pendentes permanecem registradas; nenhum corpo legado é substituído por equivalência presumida.',
                ],
            },
            {
                'id': 'distinguir-series',
                'criterio': 'Distinguir claramente emendas da CF/1988, emendas de revisão e emendas de constituições históricas.',
                'estado': 'satisfeito',
                'evidencia': {
                    'serie_cf1988': len(present),
                    'historicas_listadas_fora': len(historicas),
                    'revisao_no_acervo': revisao,
                },
            },
            {
                'id': 'vinculos-constituicao-adct',
                'criterio': 'Registrar vínculos da Constituição/ADCT com o ato modificador e seus dispositivos autônomos, mantendo lacunas explícitas.',
                'estado': vinculo_estado,
                'evidencia': {
                    'citacoes_na_constituicao': len(cf_cites),
                    'citacoes_no_adct': len(adct_cites),
                    'citadas_sem_arquivo': vinculos['citadas_sem_arquivo_autonomo'],
                    'publicadas_sem_citacao': len(vinculos['publicadas_sem_citacao_na_constituicao']),
                    'mapa': str(MAPA.relative_to(ROOT)),
                },
                'notas': [
                    'Mapa CF/ADCT → ato/dispositivos em mapa-constituicao-adct-dispositivos.json.',
                    'Escopo literal do issue: vínculo com o ato modificador e dispositivos autônomos; sem mapa CF inteira.',
                ],
            },
            {
                'id': 'metadados-edicao-fonte-hashes',
                'criterio': 'Preservar metadados de edição/fonte/captura, hashes e provas de conversão, sem presumir vigência imediata.',
                'estado': meta_estado,
                'evidencia': {
                    'com_frontmatter': len(present) - len(sem_frontmatter),
                    'sem_frontmatter': sem_frontmatter,
                    'sem_contrato_versao_1': sem_contrato,
                    'fonte_url_desconhecida': fonte_desconhecida,
                    'manifesto_frontmatter': str(MANIFESTO_FM.relative_to(ROOT)) if MANIFESTO_FM.is_file() else None,
                    'conferencias_atuais': str(FONTES_CONFERENCIA.relative_to(ROOT)) if FONTES_CONFERENCIA.is_file() else None,
                    'provas_faixa': [
                        'provas/emendas-cf1988/faixa-001-050/',
                        'provas/emendas-cf1988/faixa-051-100/',
                        'provas/emendas-cf1988/faixa-101-141/',
                    ],
                },
                'notas': [
                    'Frontmatter contrato_versao=1 nos Markdown da série; corpo jurídico preservado.',
                    'Captura original desconhecida permanece explícita (não inventada).',
                    'Capturas atuais de conferência têm hash próprio e não substituem a proveniência original desconhecida.',
                    'vigencia_certificada permanece false.',
                ],
            },
            {
                'id': 'nao-recontar-consolidada',
                'criterio': 'Não recontar Constituição consolidada ou edições alternativas como se fossem emendas coletadas.',
                'estado': 'satisfeito',
                'evidencia': {
                    'constituicao_excluida_da_serie': True,
                    'ids_serie_somente_emenda_constitucional': True,
                },
            },
        ],
    }
    criterios['resumo'] = {
        'satisfeitos': sum(1 for c in criterios['itens'] if c['estado'] == 'satisfeito'),
        'parciais': sum(1 for c in criterios['itens'] if c['estado'] == 'parcial'),
        'pendentes': sum(1 for c in criterios['itens'] if c['estado'] == 'pendente'),
        'issue_fechavel': False,
    }

    return {
        'lote': LOTE,
        'issue': 63,
        'gerado_em': now_utc(),
        'escopo': 'Textos autônomos das Emendas Constitucionais nº 1 a 141 à CF/1988',
        'fora_de_escopo': [
            'emendas constitucionais de revisão (emecrv)',
            'emendas a constituições históricas (data < 1988)',
            'Constituição consolidada / ADCT como substituto da emenda',
        ],
        'numeros_alvo': list(range(1, 142)),
        'recuperados': sorted(present),
        'lacunas': missing,
        'contagem': {
            'alvo': 141,
            'publicados': len(present),
            'lacunas': len(missing),
        },
        'lotes_faixa_preexistentes': {
            'faixa-001-050': 'provas/emendas-cf1988/faixa-001-050/',
            'faixa-051-100': 'provas/emendas-cf1988/faixa-051-100/',
            'faixa-101-141': 'provas/emendas-cf1988/faixa-101-141/',
            'prs_merged': PRS,
        },
        'emendas_historicas_no_acervo_nao_contam_nesta_serie': historicas,
        'emendas_revisao_no_acervo': revisao,
        'itens': [present[n] for n in sorted(present)],
        'vinculos_constituicao': vinculos,
        'auditoria_metadados': {
            'sem_frontmatter': sem_frontmatter,
            'sem_contrato_versao_1': sem_contrato,
            'fonte_url_desconhecida': fonte_desconhecida,
            'sem_marcadores_autonomos': sem_auton,
        },
        'mapa_vinculos': mapa,
        'criterios_aceite_arquivo': str(CRITERIOS.relative_to(ROOT)),
        'limites': [
            'Presença do arquivo não certifica vigência nem eficácia.',
            'A Constituição consolidada cita emendas; isso não substitui o texto autônomo.',
            'Contagem 141/141 não prova completude de todos os critérios de aceite do #63.',
            'Esta matriz consolida cobertura da série; provas de conversão ficam nas pastas de faixa.',
        ],
        'criterios': criterios,
    }


def build() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    matriz = scan()
    criterios = matriz.pop('criterios')
    mapa = matriz.pop('mapa_vinculos')
    MAPA.write_text(json.dumps(mapa, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    MATRIZ.write_text(json.dumps(matriz, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    CRITERIOS.write_text(json.dumps(criterios, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {
        'contagem': matriz['contagem'],
        'criterios': criterios['resumo'],
        'mapa': mapa['contagem'],
        'auditoria_metadados': {k: len(v) for k, v in matriz['auditoria_metadados'].items()},
    }


def verify() -> None:
    if not MATRIZ.is_file():
        raise SystemExit(f'matriz ausente: {MATRIZ}')
    if not CRITERIOS.is_file():
        raise SystemExit(f'matriz de critérios ausente: {CRITERIOS}')
    if not MAPA.is_file():
        raise SystemExit(f'mapa de vínculos ausente: {MAPA}')
    published = json.loads(MATRIZ.read_text(encoding='utf-8'))
    criterios = json.loads(CRITERIOS.read_text(encoding='utf-8'))
    mapa = json.loads(MAPA.read_text(encoding='utf-8'))
    fresh = scan()
    fresh_crit = fresh.pop('criterios')
    fresh_mapa = fresh.pop('mapa_vinculos')
    if published['recuperados'] != fresh['recuperados']:
        raise SystemExit('matriz desatualizada: recuperados divergem do acervo')
    if published['lacunas'] != fresh['lacunas']:
        raise SystemExit('matriz desatualizada: lacunas divergem do acervo')
    if published['contagem']['publicados'] != 141 or fresh['contagem']['lacunas'] != 0:
        raise SystemExit(f"série incompleta: {fresh['contagem']}")
    if criterios.get('resumo', {}).get('issue_fechavel') is True:
        raise SystemExit('matriz de critérios marca issue fechável sem autorização explícita')
    if criterios['resumo']['satisfeitos'] != fresh_crit['resumo']['satisfeitos']:
        raise SystemExit('resumo de critérios desatualizado; rode build')
    if mapa['contagem']['emendas'] != 141:
        raise SystemExit('mapa incompleto')
    # Todo MD da série precisa de frontmatter contrato após ensure-frontmatter.
    sem_fm = fresh['auditoria_metadados']['sem_frontmatter']
    if sem_fm:
        raise SystemExit(f'ainda há MD sem frontmatter: {sem_fm[:10]}… total={len(sem_fm)}')
    ids = {item['arquivo'] for item in published['itens']}
    if 'federal/br-federal-constituicao-1988-10-05.md' in ids:
        raise SystemExit('Constituição consolidada contada como emenda')
    # Integridade: sha256_markdown do frontmatter = hash do corpo.
    for item in fresh['itens']:
        path = ROOT / item['arquivo']
        text = path.read_text(encoding='utf-8')
        meta = parse_frontmatter(text)
        body = body_of(text)
        if meta.get('sha256_markdown') != sha256_text(body):
            raise SystemExit(f"{item['arquivo']}: sha256_markdown diverge do corpo")
        if meta.get('vigencia_certificada') is True:
            raise SystemExit(f"{item['arquivo']}: vigencia_certificada não pode ser true")
        if meta.get('contrato_versao') not in {1, CONTRACT_VERSION}:
            raise SystemExit(f"{item['arquivo']}: contrato_versao ausente/ inválido")
    print('verify ok:', {
        'contagem': fresh['contagem'],
        'criterios': criterios['resumo'],
        'vinculos': published.get('vinculos_constituicao', {}).get('estado'),
        'mapa': fresh_mapa['contagem'],
    })


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        'cmd',
        choices=('build', 'verify', 'scan', 'ensure-frontmatter', 'mapa'),
    )
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    if args.cmd == 'ensure-frontmatter':
        print(json.dumps(ensure_frontmatter(dry_run=args.dry_run), ensure_ascii=False))
    elif args.cmd == 'mapa':
        present = scan()
        mapa = present['mapa_vinculos']
        OUT.mkdir(parents=True, exist_ok=True)
        MAPA.write_text(json.dumps(mapa, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(mapa['contagem'], ensure_ascii=False))
    elif args.cmd == 'build':
        print(json.dumps(build(), ensure_ascii=False))
    elif args.cmd == 'verify':
        verify()
    else:
        m = scan()
        print(json.dumps({
            'contagem': m['contagem'],
            'criterios': m['criterios']['resumo'],
            'auditoria_metadados': {
                k: len(v) for k, v in m['auditoria_metadados'].items()
            },
            'mapa': m['mapa_vinculos']['contagem'],
        }, ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1:])
