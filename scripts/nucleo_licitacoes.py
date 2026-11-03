"""Núcleo de legislação de licitações: conversão, conferência e metadados.

Converte as edições oficiais capturadas (HTML do Planalto e da Câmara dos
Deputados) em Markdown, concilia o resultado com uma segunda fonte oficial e
gera o manifesto de metadados. Só usa a biblioteca padrão e, para o HTML,
BeautifulSoup/lxml. Nenhuma etapa afirma vigência: situação e eficácia só
entram quando a fonte as informa, e o restante fica explicitamente
"desconhecido".

Subcomandos:
  fetch  DIR           captura as fontes e grava DIR/fetch.json
  build  DIR           converte, concilia e (re)escreve Markdown, manifesto e provas
  verify               confere offline Markdown, manifesto e provas publicados
"""
import argparse
import base64
import datetime
import difflib
import hashlib
import html as htmllib
import json
import lzma
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
PROVAS = ROOT / 'provas/nucleo-licitacoes'
FONTES = PROVAS / 'fontes'
MANIFESTO = ROOT / 'metadados/nucleo-licitacoes.json'
UNKNOWN = 'desconhecido'
USER_AGENT = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/124.0 Safari/537.36')
CONTRACT_VERSION = 1

# --------------------------------------------------------------------------
# Catálogo das fontes e dos documentos
# --------------------------------------------------------------------------

PLANALTO = 'Presidência da República — Planalto'
CAMARA = 'Câmara dos Deputados — LegIn'

SOURCES = {
    'planalto-14133': dict(
        url='https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm',
        file='planalto-l14133.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'camara-14133-pdf': dict(
        url='https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-normaatualizada-pl.pdf',
        file='camara-lei-14133-normaatualizada.pdf', orgao=CAMARA, formato='pdf'),
    'camara-14133-html': dict(
        url='https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-normaatualizada-pl.html',
        file='camara-lei-14133-normaatualizada.html', orgao=CAMARA, formato='html', charset='utf-8',
        opcional=True),
    'camara-lc123': dict(
        url='https://www2.camara.leg.br/legin/fed/leicom/2006/leicomplementar-123-14-dezembro-2006-548099-normaatualizada-pl.html',
        file='camara-lc-123-normaatualizada.html', orgao=CAMARA, formato='html', charset='utf-8'),
    'planalto-lc123': dict(
        url='https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp123.htm',
        file='planalto-lcp123.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'camara-13303': dict(
        url='https://www2.camara.leg.br/legin/fed/lei/2016/lei-13303-30-junho-2016-783296-normaatualizada-pl.html',
        file='camara-lei-13303-normaatualizada.html', orgao=CAMARA, formato='html', charset='utf-8'),
    'planalto-13303': dict(
        url='https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/lei/l13303.htm',
        file='planalto-l13303.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-8666': dict(
        url='https://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm',
        file='planalto-l8666cons.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-10520': dict(
        url='https://www.planalto.gov.br/ccivil_03/leis/2002/l10520.htm',
        file='planalto-l10520.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-lc238': dict(
        url='https://www.planalto.gov.br/ccivil_03/leis/lcp/Lcp238.htm',
        file='planalto-lcp238.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    'planalto-lc227': dict(
        url='https://www.planalto.gov.br/ccivil_03/leis/lcp/Lcp227.htm',
        file='planalto-lcp227.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
    # Publicação original citada na nota do art. 87-B da LC 123; capturada como evidência da
    # procedência da nota. O HTML da Câmara desta página não segmenta artigos em blocos
    # utilizáveis para conferência artigo a artigo; o Markdown publicado segue o Planalto.
    'camara-lc227': dict(
        url=('https://www2.camara.leg.br/legin/fed/leicom/2026/'
             'leicomplementar-227-13-janeiro-2026-798657-publicacaooriginal-177770-pl.html'),
        file='camara-lc-227-publicacaooriginal.html', orgao=CAMARA, formato='html', charset='utf-8'),
    'planalto-lc198': dict(
        url='https://www.planalto.gov.br/ccivil_03/leis/lcp/Lcp198.htm',
        file='planalto-lcp198.htm', orgao=PLANALTO, formato='html', charset='cp1252'),
}

HISTORIC_14133 = 'federal/br-federal-lei-2021-04-01-14133.md'
# O corpo da edição histórica da Lei 14.133 não pode ser alterado: este é o SHA-256 do arquivo no commit auditado.
HISTORIC_14133_SHA256 = 'a8549ba1e3d54fd562afb29cb102bb97f1fb61c8bb4283e3eb4aab629fc193e1'
BASELINE_COMMIT = '0638c91461ea0a3f8bbae9cb88ddfdebe38a67e9'
# SHA-256 dos arquivos no commit auditado (BASELINE_COMMIT), antes desta alteração.
LC123_PATH = 'federal/br-federal-lei-complementar-2006-12-14-123.md'
LC123_PROOF_NAME = 'lc123-anterior-vs-nova.json'
LC123_BASELINE_REL = 'provas/nucleo-licitacoes/baselines/lc123-edicao-auditada.md'
LC123_BASELINE_META_REL = 'provas/nucleo-licitacoes/baselines/lc123-edicao-auditada.json'
LC123_BASELINE_PAPEL = 'baseline-texto-auditado'
BASELINE_SHA256 = {
    'federal/br-federal-lei-2021-04-01-14133.md': HISTORIC_14133_SHA256,
    'federal/br-federal-lei-2016-06-30-13303.md': '8dfe72c14107eed49d27ed6ace922ec19b63879bb2e133147c1155eeac845875',
    LC123_PATH: 'b31d0e6a2e50918a661db65da1c79886d8a40d848aa7e3c8ff6698bfa7ea8fb7',
}

DOCS = [
    dict(slug='br-federal-lei-2021-04-01-14133', arquivo=HISTORIC_14133, modo='historica'),
    dict(slug='br-federal-lei-2021-04-01-14133-consolidada',
         arquivo='federal/edicoes/br-federal-lei-2021-04-01-14133-consolidada.md', modo='converter',
         fonte='planalto-14133', conferencia=['camara-14133-pdf'], base_url=SOURCES['planalto-14133']['url'],
         norma=dict(tipo='lei', numero='14133', data='2021-04-01',
                    titulo='LEI Nº 14.133, DE 1º DE ABRIL DE 2021',
                    ementa='Lei de Licitações e Contratos Administrativos.'),
         edicao=dict(tipo='consolidada', integral=True), situacao=dict(valor='nao-informada')),
    dict(slug='br-federal-lei-complementar-2006-12-14-123',
         arquivo='federal/br-federal-lei-complementar-2006-12-14-123.md', modo='converter',
         fonte='camara-lc123', conferencia=['planalto-lc123'], base_url=SOURCES['camara-lc123']['url'],
         norma=dict(tipo='lei-complementar', numero='123', data='2006-12-14',
                    titulo='LEI COMPLEMENTAR Nº 123, DE 14 DE DEZEMBRO DE 2006',
                    ementa='Estatuto Nacional da Microempresa e da Empresa de Pequeno Porte.'),
         edicao=dict(tipo='consolidada', integral=True), situacao=dict(valor='nao-informada')),
    dict(slug='br-federal-lei-complementar-2006-12-14-123-planalto',
         arquivo='federal/edicoes/br-federal-lei-complementar-2006-12-14-123-planalto.md', modo='converter',
         fonte='planalto-lc123', conferencia=['camara-lc123'], base_url=SOURCES['planalto-lc123']['url'],
         norma=dict(tipo='lei-complementar', numero='123', data='2006-12-14',
                    titulo='LEI COMPLEMENTAR Nº 123, DE 14 DE DEZEMBRO DE 2006',
                    ementa='Estatuto Nacional da Microempresa e da Empresa de Pequeno Porte.'),
         edicao=dict(tipo='consolidada', integral=True), situacao=dict(valor='nao-informada')),
    dict(slug='br-federal-lei-complementar-2026-10-21-238',
         arquivo='federal/br-federal-lei-complementar-2026-10-21-238.md', modo='converter',
         fonte='planalto-lc238', conferencia=[], base_url=SOURCES['planalto-lc238']['url'],
         norma=dict(tipo='lei-complementar', numero='238', data='2026-10-21',
                    titulo='LEI COMPLEMENTAR Nº 238, DE 21 DE OUTUBRO DE 2026',
                    ementa=('Altera a Lei Complementar nº 123, de 14 de dezembro de 2006 (Lei do Simples Nacional), '
                            'para atualizar o limite de receita bruta anual e o número de empregados do '
                            'Microempreendedor Individual (MEI), conceder remissão de créditos de titularidade da '
                            'União de sua responsabilidade e dispor sobre a aplicação da medida.')),
         edicao=dict(tipo='consolidada', integral=True), situacao=dict(valor='nao-informada')),
    dict(slug='br-federal-lei-complementar-2026-01-13-227',
         arquivo='federal/br-federal-lei-complementar-2026-01-13-227.md', modo='converter',
         fonte='planalto-lc227', conferencia=[], base_url=SOURCES['planalto-lc227']['url'],
         norma=dict(tipo='lei-complementar', numero='227', data='2026-01-13',
                    titulo='LEI COMPLEMENTAR Nº 227, DE 13 DE JANEIRO DE 2026',
                    ementa=('Institui o Comitê Gestor do Imposto sobre Bens e Serviços (CGIBS); dispõe sobre o '
                            'processo administrativo tributário do Imposto sobre Bens e Serviços (IBS) e sobre a '
                            'distribuição do produto da arrecadação do IBS aos entes federativos; institui normais '
                            'gerais relativas ao Imposto sobre Transmissão Causa mortis e Doação de Quaisquer Bens '
                            'ou Direitos (ITCMD); altera a Lei nº 5.172, de 25 de outubro de 1966 (Código Tributário '
                            'Nacional), a Lei nº 1.079, de 10 de abril de 1950, a Lei nº 9.430, de 27 de dezembro de '
                            '1996, a Lei nº 10.893, de 13 julho de 2004, a Lei nº 14.113, de 25 de dezembro de 2020, '
                            'a Lei Complementar nº 63, de 11 de janeiro de 1990, a Lei Complementar nº 87, de 13 de '
                            'setembro de 1996 (Lei Kandir), a Lei Complementar nº 123, de 14 de dezembro de 2006, a '
                            'Lei Complementar nº 141, de 13 de janeiro de 2012, a Lei Complementar nº 192, de 11 de '
                            'março de 2022, a Lei Complementar nº 214, de 16 de janeiro de 2025, o Decreto-Lei nº 37, '
                            'de 18 de novembro de 1966, e o Decreto nº 70.235, de 6 de março de 1972; e revoga '
                            'dispositivos da Lei nº 10.833, de 29 de dezembro de 2003, e da Medida Provisória '
                            'nº 2.158-35, de 24 de agosto de 2001.')),
         edicao=dict(tipo='consolidada', integral=True), situacao=dict(valor='nao-informada')),
    dict(slug='br-federal-lei-2016-06-30-13303',
         arquivo='federal/br-federal-lei-2016-06-30-13303.md', modo='conferida',
         fonte='camara-13303', conferencia=['planalto-13303'], base_url=SOURCES['camara-13303']['url'],
         norma=dict(tipo='lei', numero='13303', data='2016-06-30',
                    titulo='LEI Nº 13.303, DE 30 DE JUNHO DE 2016',
                    ementa='Estatuto jurídico da empresa pública, da sociedade de economia mista e de suas subsidiárias.'),
         edicao=dict(tipo='consolidada', integral=True), situacao=dict(valor='nao-informada')),
    dict(slug='br-federal-lei-1993-06-21-8666',
         arquivo='federal/br-federal-lei-1993-06-21-8666.md', modo='converter',
         fonte='planalto-8666', conferencia=[], base_url=SOURCES['planalto-8666']['url'],
         norma=dict(tipo='lei', numero='8666', data='1993-06-21',
                    titulo='LEI Nº 8.666, DE 21 DE JUNHO DE 1993',
                    ementa='Regulamenta o art. 37, inciso XXI, da Constituição Federal, institui normas para licitações e contratos da Administração Pública.'),
         edicao=dict(tipo='consolidada', integral=True),
         situacao=dict(valor='revogada',
                       fundamento=('Cabeçalho da fonte: "(Revogado pela Lei nº 14.133, de 2021)"; '
                                   'Lei 14.133, art. 193, I (arts. 89 a 108 na publicação da Lei 14.133) e '
                                   'art. 193, II, a, com a redação da LC 198/2023 (revogação em 30 de dezembro de 2023). '
                                   'Cronologia estruturada em eventos_revogacao do manifesto.'),
                       revogada_por='br-federal-lei-2021-04-01-14133', data_revogacao='2023-12-30')),
    dict(slug='br-federal-lei-2002-07-17-10520',
         arquivo='federal/br-federal-lei-2002-07-17-10520.md', modo='converter',
         fonte='planalto-10520', conferencia=[], base_url=SOURCES['planalto-10520']['url'],
         norma=dict(tipo='lei', numero='10520', data='2002-07-17',
                    titulo='LEI Nº 10.520, DE 17 DE JULHO DE 2002',
                    ementa='Institui, no âmbito da União, Estados, Distrito Federal e Municípios, a modalidade de licitação denominada pregão.'),
         edicao=dict(tipo='consolidada', integral=True),
         situacao=dict(valor='revogada',
                       fundamento='Cabeçalho da fonte: "(Revogado pela Lei nº 14.133, de 2021)"; '
                                  'Lei 14.133, art. 193, II, b, com a redação da LC 198/2023: revogação em 30 de dezembro de 2023.',
                       revogada_por='br-federal-lei-2021-04-01-14133', data_revogacao='2023-12-30')),
]

# --------------------------------------------------------------------------
# Utilidades de hash e E/S
# --------------------------------------------------------------------------


def sha256(data):
    return hashlib.sha256(data).hexdigest()


WAF_SCRIPT_RE = re.compile(rb'<script[^>]*>\s*\(function\(\)\{var\s+f5_cspm.*?</script>', re.S)


def content_sha256(data):
    """SHA-256 do conteúdo sem o script de proteção (F5) que o Planalto injeta e que muda a cada resposta."""
    return sha256(WAF_SCRIPT_RE.sub(b'', data).rstrip())


def now_utc():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + '\n', encoding='utf-8')


def snapshot_path(key):
    spec = SOURCES[key]
    return FONTES / (spec['file'] + ('.xz' if spec['formato'] == 'html' else ''))


def read_snapshot(key):
    path = snapshot_path(key)
    data = path.read_bytes()
    return lzma.decompress(data) if path.suffix == '.xz' else data


def write_snapshot(key, data):
    path = snapshot_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(lzma.compress(data, preset=9 | lzma.PRESET_EXTREME) if path.suffix == '.xz' else data)


# --------------------------------------------------------------------------
# Captura
# --------------------------------------------------------------------------


def fetch(dest):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    records = {}
    for key, spec in SOURCES.items():
        target = dest / spec['file']
        header_file = dest / (spec['file'] + '.headers')
        captured = now_utc()
        proc = subprocess.run([
            'curl', '--silent', '--show-error', '--location', '--proto', '=https', '--proto-redir', '=https',
            '--connect-timeout', '30', '--max-time', '180', '--max-filesize', str(64 * 1024 * 1024),
            '--user-agent', USER_AGENT, '--dump-header', str(header_file),
            '--write-out', '%{http_code} %{url_effective}', '--output', str(target), spec['url'],
        ], capture_output=True, text=True)
        record = dict(url=spec['url'], capturado_em=captured, curl_exit=proc.returncode, user_agent=USER_AGENT)
        if proc.returncode == 0:
            status, _, effective = proc.stdout.partition(' ')
            record.update(http_status=int(status), url_final=effective)
            data = target.read_bytes()
            record.update(bytes=len(data), sha256=sha256(data))
            raw_headers = header_file.read_bytes().decode('latin-1').replace('\r\n', '\n')
            final_block = [b for b in raw_headers.split('\n\n') if b.strip()][-1:] or ['']  # resposta após redirecionamentos
            for line in final_block[0].splitlines():
                name, _, value = line.partition(':')
                if name.lower() in ('last-modified', 'etag', 'content-type', 'date'):
                    record['cabecalho_' + name.lower().replace('-', '_')] = value.strip()
            looks_like_gateway_error = b'504 Gateway Time-out' in data[:400] or b'<title>5' in data[:400]
            record['utilizavel'] = status == '200' and not looks_like_gateway_error and len(data) > 1000
            if not record['utilizavel']:
                record['motivo'] = f'resposta HTTP {status} sem conteúdo utilizável ({len(data)} bytes)'
        else:
            record.update(utilizavel=False, motivo=proc.stderr.strip()[-500:])
        header_file.unlink(missing_ok=True)
        records[key] = record
        print(f'{key}: {record.get("http_status")} {record.get("bytes")} utilizável={record["utilizavel"]}', flush=True)
    write_json(dest / 'fetch.json', records)
    return records


# --------------------------------------------------------------------------
# HTML -> blocos -> Markdown
# --------------------------------------------------------------------------

from bs4 import BeautifulSoup, NavigableString, Tag  # noqa: E402

LIGATURES = {'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi', 'ﬄ': 'ffl', 'ﬅ': 'st', 'ﬆ': 'st'}
STRIKE_TAGS = {'strike', 's', 'del'}
BLOCK_TAGS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'pre', 'dt', 'dd'}
SKIP_TAGS = {'script', 'style', 'head', 'title', 'meta', 'noscript'}


def decode(data, charset):
    return data.decode(charset, errors='strict')


def clean_text(text):
    text = text.replace('\xa0', ' ').replace('​', '').replace('\xad', '').replace('\r', '')
    for lig, repl in LIGATURES.items():
        text = text.replace(lig, repl)
    return text


def is_struck_style(tag):
    style = tag.get('style') or ''
    return 'line-through' in style.replace(' ', '')


class Converter:
    """Converte uma página HTML em lista de blocos Markdown, registrando o que não é texto."""

    def __init__(self, base_url):
        self.base_url = base_url
        self.blocks = []
        self.images = []
        self.tables = []
        self.stats = dict(trechos_riscados=0, links=0, tabelas_markdown=0, tabelas_html=0)

    # ---- inline ----
    def escape(self, text):
        text = text.replace('\\', '\\\\')
        for ch in '*_[]<>`~|':
            text = text.replace(ch, '\\' + ch)
        return text

    def inline(self, node, struck=False):
        parts = []
        for child in node.children:
            if isinstance(child, NavigableString):
                if type(child).__name__ in ('Comment', 'Doctype', 'CData', 'ProcessingInstruction'):
                    continue
                parts.append(self.escape(clean_text(str(child))))
            elif isinstance(child, Tag):
                parts.append(self.inline_tag(child, struck))
        return ''.join(parts)

    def inline_tag(self, tag, struck):
        name = tag.name
        if name in SKIP_TAGS:
            return ''
        if name == 'br':
            return ' '
        if name == 'img':
            self.record_image(tag)
            return ''
        now_struck = name in STRIKE_TAGS or is_struck_style(tag)
        if now_struck and not struck:
            inner = self.inline(tag, True)
            lead = inner[:len(inner) - len(inner.lstrip())]
            trail = inner[len(inner.rstrip()):]
            core = inner.strip()
            if not core:
                return inner
            self.stats['trechos_riscados'] += 1
            return f'{lead}~~{core}~~{trail}'
        if name == 'sup':
            text = clean_text(tag.get_text()).strip()
            if text in ('o', 'º', 'O'):
                return 'º'
            if text in ('a', 'ª'):
                return 'ª'
            return f'<sup>{htmllib.escape(text)}</sup>' if text else ''
        if name == 'sub':
            text = clean_text(tag.get_text()).strip()
            return f'<sub>{htmllib.escape(text)}</sub>' if text else ''
        if name == 'a':
            inner = self.inline(tag, struck)
            href = tag.get('href')
            if not href or href.startswith('#') or href.lower().startswith(('javascript:', 'mailto:')):
                return inner
            if not inner.strip():
                return inner
            url = urljoin(self.base_url, href.strip().replace(' ', '%20'))
            if urlparse(url).scheme not in ('http', 'https'):
                return inner
            self.stats['links'] += 1
            lead = inner[:len(inner) - len(inner.lstrip())]
            trail = inner[len(inner.rstrip()):]
            return f'{lead}[{inner.strip()}]({url}){trail}'
        return self.inline(tag, struck)

    def record_image(self, tag):
        src = tag.get('src') or ''
        record = dict(alt=(tag.get('alt') or '').strip() or UNKNOWN, largura=tag.get('width') or UNKNOWN,
                      altura=tag.get('height') or UNKNOWN)
        if src.startswith('data:'):
            header, _, payload = src.partition(',')
            raw = base64.b64decode(payload) if ';base64' in header else payload.encode()
            record.update(origem='embutida', tipo_midia=header[5:].split(';')[0], bytes=len(raw), sha256=sha256(raw))
        else:
            record.update(origem=urljoin(self.base_url, src), tipo_midia=UNKNOWN)
        record['tratamento'] = ('omitida do Markdown; elemento institucional/decorativo sem texto jurídico '
                                'associado (cabeçalho da página da fonte)')
        self.images.append(record)

    # ---- blocos ----
    def walk(self, node, pending):
        for child in list(node.children):
            if isinstance(child, NavigableString):
                if type(child).__name__ in ('Comment', 'Doctype'):
                    continue
                pending.append(child)
                continue
            if not isinstance(child, Tag) or child.name in SKIP_TAGS:
                continue
            if child.name in BLOCK_TAGS:
                self.flush(pending)
                self.emit(self.inline(child))
            elif child.name == 'table':
                self.flush(pending)
                self.table(child)
            elif child.name == 'hr':
                self.flush(pending)
            elif child.name == 'img':
                self.record_image(child)
            elif child.find(BLOCK_TAGS | {'table'}):
                self.flush(pending)
                self.walk(child, pending)
                self.flush(pending)
            else:
                pending.append(child)

    def flush(self, pending):
        if not pending:
            return
        text = ''.join(self.escape(clean_text(str(n))) if isinstance(n, NavigableString)
                       else self.inline_tag(n, False) for n in pending)
        pending.clear()
        self.emit(text)

    def emit(self, text):
        text = re.sub(r'\s+', ' ', text).strip()
        # Une trechos riscados adjacentes preservando o espaço entre eles
        # (`~~§ 4º~~ ~~Os…~~` → `~~§ 4º Os…~~`); sem isso o espaço some e a
        # cobertura do texto diverge da página (ordinais + palavra seguinte).
        text = re.sub(r'~~(\s*)~~', lambda m: m.group(1), text).strip()
        if not text:
            return
        # Evita que o início da linha seja lido como marcação Markdown.
        text = re.sub(r'^(\d+)([.)])(\s)', r'\1\\\2\3', text)
        text = re.sub(r'^([+\-])(\s)', r'\\\1\2', text)
        text = re.sub(r'^(#{1,6}|=+)(\s|$)', r'\\\1\2', text)
        self.blocks.append(text)

    def table(self, table):
        rows = table.find_all('tr')
        if len(rows) <= 1:
            # Tabela de diagramação (um só quadro): vale o conteúdo, não a grade.
            pending = []
            for cell in table.find_all(['td', 'th']):
                self.walk(cell, pending)
                self.flush(pending)
            return
        grid = []
        has_span = False
        for tr in rows:
            cells = []
            for cell in tr.find_all(['td', 'th'], recursive=False) or tr.find_all(['td', 'th']):
                text = re.sub(r'\s+', ' ', self.inline(cell)).strip()
                rowspan = int(cell.get('rowspan') or 1)
                colspan = int(cell.get('colspan') or 1)
                has_span |= rowspan > 1 or colspan > 1
                cells.append((text, rowspan, colspan, cell.name == 'th'))
            grid.append(cells)
        self.tables.append(dict(linhas=len(grid), colunas_max=max(len(r) for r in grid), com_mesclagem=has_span))
        if has_span:
            self.stats['tabelas_html'] += 1
            lines = ['<table>']
            for r_index, cells in enumerate(grid):
                lines.append('<tr>' + ''.join(
                    '<{t}{rs}{cs}>{c}</{t}>'.format(
                        t='th' if (th or r_index == 0) else 'td',
                        rs=f' rowspan="{rs}"' if rs > 1 else '', cs=f' colspan="{cs}"' if cs > 1 else '',
                        c=htmllib.escape(self.unescape_md(re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', text)), quote=False))
                    for text, rs, cs, th in cells) + '</tr>')
            lines.append('</table>')
            self.blocks.append('\n'.join(lines))
            return
        self.stats['tabelas_markdown'] += 1
        width = max(len(r) for r in grid)
        lines = []
        for r_index, cells in enumerate(grid):
            texts = [t for t, *_ in cells] + [''] * (width - len(cells))  # '|' já escapado em inline()
            lines.append('| ' + ' | '.join(texts) + ' |')
            if r_index == 0:
                lines.append('|' + ' --- |' * width)
        self.blocks.append('\n'.join(lines))

    @staticmethod
    def unescape_md(text):
        return re.sub(r'\\([\\*_\[\]<>`~|])', r'\1', text)


def convert_html(data, charset, base_url):
    soup = BeautifulSoup(decode(data, charset), 'lxml')
    conv = Converter(base_url)
    pending = []
    conv.walk(soup, pending)  # a página do Planalto pode ter mais de um <body> (ex.: promulgação das partes vetadas)
    conv.flush(pending)
    return conv


def blocks_to_markdown(blocks, title_pattern):
    """Primeiro bloco que casa com o título vira H1 (texto simples); os demais são parágrafos."""
    out = []
    used = False
    for block in blocks:
        plain = re.sub(r'\s+', ' ', md_plain(block, True)).strip()
        if not used and re.match(title_pattern, plain, re.I):
            out.append('# ' + re.sub(r'([*_\[\]<>`~|])', r'\\\1', plain))
            used = True
        else:
            out.append(block)
    if not used:
        raise ValueError('título da norma não encontrado nos blocos convertidos')
    return '\n\n'.join(out) + '\n'


# --------------------------------------------------------------------------
# Normalização e conferência
# --------------------------------------------------------------------------

NOTE_LEADERS = (r'“?caput”?', r'redação', r'nova redação', r'incluíd[oa]s?', r'acrescid[oa]s?', r'revogad[oa]s?',
                r'vide', r'vigência', r'produção', r'promulgação', r'regulamento', r'renumerad[oa]s?',
                r'parágrafo', r'inciso', r'alínea', r'anexo', r'expressão', r'item', r'artigo', r'capítulo', r'título',
                r'seção', r'subseção', r'letra', r'número', r'texto', r'declarad[oa]', r'dispositivo', r'suspens',
                r'prejudicad', r'vigent', r'efeitos?', r'ementa', r'epígrafe', r'tabela', r'quadro', r'republic',
                r'convers', r'mensagem', r'retificad', r'norma', r'prazo', r'dispositivos?', r'nota')
NOTE_RE = re.compile(r'^\(\s*(?:' + '|'.join(NOTE_LEADERS) + r')\b', re.I)


def strip_fold(text):
    text = clean_text(text)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r'(?<=\d)\s*[oº°ª](?![a-z0-9])', ' ', text)  # indicador ordinal: "4º", "4o", "4 o"
    return re.sub(r'[^0-9a-z]+', '', text)


TRAILING_LABEL_RE = re.compile(r'^\s*(?:Vigência encerrada|Vigência|Produção de efeitos?|Regulamento)(?![\wÀ-ÿ])', re.I)
VETO_NOTE_RE = re.compile(r'\(\s*VETADO\s+(?:na|no|pela|pelo)\b[^()]*\)', re.I)


def strip_notes(text):
    """Remove notas editoriais entre parênteses (histórico de alterações, remissões, efeitos).

    "(VETADO ...)" é conservado: a Câmara anota o veto com a lei, o Planalto não; ambos viram "(VETADO)".
    """
    text = VETO_NOTE_RE.sub('(VETADO)', text)
    out = []
    i = 0
    while i < len(text):
        if text[i] == '(' and NOTE_RE.match(text[i:i + 60]):
            depth = 0
            j = i
            while j < len(text):
                if text[j] == '(':
                    depth += 1
                elif text[j] == ')':
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            i = j + 1
            while True:  # rótulos que o Planalto escreve após a nota ("Vigência", "Produção de efeitos")
                label = TRAILING_LABEL_RE.match(text[i:])
                if not label:
                    break
                i += label.end()
            continue
        out.append(text[i])
        i += 1
    return ''.join(out)


def _strip_html_tags_preserving_escaped_angles(text):
    """Remove tags HTML literais sem tratar `\\<`/`\\>` do Markdown como marcação."""
    text = text.replace('\\<', '\0LT\0').replace('\\>', '\0GT\0')
    text = re.sub(r'<[^>]+>', ' ', text)
    return text.replace('\0LT\0', '<').replace('\0GT\0', '>')


def md_plain(block, keep_struck):
    """Texto simples de um bloco Markdown; opcionalmente descarta o riscado."""
    if not keep_struck:
        block = re.sub(r'~~.*?~~', ' ', block, flags=re.S)
    block = block.replace('~~', '')
    # Rótulos de navegação do Planalto ("Vigência", "Regulamento"...) são ligações, não texto da norma.
    block = re.sub(r'\[\(?(?:Vigência encerrada|Vigência|Produção de efeitos?|Regulamento)\.?\)?\]\([^)]*\)', ' ', block)
    block = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', block)
    block = block.replace('Vigência encerrada', ' ')
    block = re.sub(r'(?<=\s)(?:Vigência|Produção de efeitos?)(?=\s*(?:\(|$))', ' ', block)
    block = _strip_html_tags_preserving_escaped_angles(block)
    block = re.sub(r'\\([\\*_\[\]`~|.\-+#)])', r'\1', block)
    return block


ART_RE = re.compile(r'^\s*Art\.?\s*(\d+)\s*(?:[ºo°]|\\?\.)?\s*(?:[-–]\s*([A-Z]{1,2}))?\b')


def article_key(text):
    m = re.match(r'^\s*Art\.?\s*(\d+)\s*[ºo°ª]?\s*(?:[-–]\s*([A-Z]{1,2})\b)?', text)
    if not m:
        return None
    return m.group(1) + ('-' + m.group(2) if m.group(2) else '')


def mark_quoted(blocks):
    """Trechos que citam outra lei (ex.: art. 178 da Lei 14.133 insere artigos no Código Penal).

    As fontes não repetem as aspas em cada parágrafo; o trecho entre a abertura e o fechamento pertence
    ao artigo que o cita e não pode ser confundido com artigo da própria norma.
    """
    marked = []
    quoted = False
    for block in blocks:
        plain = md_plain(block, True).strip()
        opens = plain[:1] in ('"', '“')
        if opens:
            quoted = True
        marked.append(('“' + block) if quoted and not opens else block)
        closes = re.search(r'[”"]\s*(?:\([^()]*\)\s*)?$', plain)
        if quoted and closes and (not opens or len(plain) > 3):
            quoted = False
    return marked


def split_articles(blocks):
    """Agrupa blocos por artigo, na ordem do documento.

    O Planalto repete o artigo quando a redação muda (a anterior aparece riscada); todas as ocorrências
    vão para a mesma chave, em ordem. Retorna (dict chave -> blocos, ordem de primeira aparição).
    """
    articles = {}
    order = []
    current = None
    for block in mark_quoted(blocks):
        key = article_key(md_plain(block, True).strip())
        if key is not None:
            if key not in articles:
                articles[key] = []
                order.append(key)
            current = key
        if current is not None:
            articles[current].append(block)
    return articles, order


MARKER_ONLY_RE = re.compile(
    r'^\s*(?:Art\.?\s*\d+\s*[ºo°]?(?:\s*-\s*[A-Z]{1,2})?|§\s*\d+\s*[ºo°]?(?:\s*-\s*[A-Z]{1,2})?|Parágrafo único|'
    r'[IVXLCDM]+(?:\s*-\s*[A-Z]{1,2})?\s*[-–]?|[a-z]{1,2}\))?\s*[.;:]*\s*$')


def current_text_of(blocks):
    """Texto em vigor segundo a fonte: sem trechos riscados, notas editoriais e dispositivos só com marca.

    O Planalto risca o dispositivo revogado/vetado inteiro; a Câmara mantém a marca ("§ 8º (Revogado...)").
    Os dois deixam de contar aqui, para que a comparação meça o texto e não a forma de exibir a revogação.
    """
    out = []
    for block in blocks:
        text = strip_notes(md_plain(block, keep_struck=False))
        text = re.sub(r'\(\s*vetad[oa]\s*\)\.?', ' ', text, flags=re.I)
        if MARKER_ONLY_RE.match(text):
            continue
        out.append(text)
    return out


def main_body_blocks(blocks, start_pattern=r'^\s*(Art\.?\s*1\b|CAP[ÍI]TULO I\b|T[ÍI]TULO I\b)', stop_pattern=r'^Brasília,'):
    started = False
    out = []
    for block in blocks:
        text = md_plain(block, True)
        if not started and re.match(start_pattern, text, re.I):
            started = True
        if started:
            if re.match(stop_pattern, text):
                break
            out.append(block)
    return out


def pdf_text(data):
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'in.pdf'
        path.write_bytes(data)
        out = subprocess.run(['pdftotext', '-layout', '-enc', 'UTF-8', str(path), '-'], capture_output=True,
                             check=True).stdout.decode('utf-8')
    return out


def pdf_articles(text):
    """Segmenta o texto da Câmara (PDF) por artigo, descartando cabeçalho e assinatura."""
    lines = [l.rstrip() for l in text.replace('\f', '\n').splitlines()]
    paragraphs = []
    for line in lines:
        if not line.strip():
            continue
        if re.match(r'^\s{6,}\S', line) or not paragraphs:
            paragraphs.append(line.strip())
        else:
            paragraphs[-1] += ' ' + line.strip()
    return split_articles(main_body_blocks(paragraphs))


def compare_articles(primary, secondary):
    """Compara texto vigente artigo a artigo. Retorna dict com contagens e divergências."""
    a_articles, a_order = primary
    b_articles, b_order = secondary
    result = dict(artigos_fonte_principal=len(a_order), artigos_fonte_conferencia=len(b_order),
                  apenas_na_principal=[k for k in a_order if k not in b_articles],
                  apenas_na_conferencia=[k for k in b_order if k not in a_articles], identicos=0, divergentes=[])
    for key in a_order:
        if key not in b_articles:
            continue
        a = strip_fold(''.join(current_text_of(a_articles[key])))
        b = strip_fold(''.join(current_text_of(b_articles[key])))
        if a == b:
            result['identicos'] += 1
        else:
            ratio = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
            matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
            diffs = [dict(operacao=op, principal=a[i1:i2][:160], conferencia=b[j1:j2][:160],
                          contexto=a[max(0, i1 - 40):i1] + '|' + a[i2:i2 + 40])
                     for op, i1, i2, j1, j2 in matcher.get_opcodes() if op != 'equal'][:6]
            result['divergentes'].append(dict(artigo=key, similaridade=round(ratio, 4), diferencas=diffs))
    return result


def coverage(blocks, markdown_body):
    """Prova de cobertura: o texto normalizado dos blocos convertidos equivale ao do Markdown publicado."""
    from_blocks = strip_fold(''.join(md_plain(b, True) for b in blocks))
    produced = strip_fold(re.sub(r'^# ', '', md_plain(markdown_body, True), flags=re.M))
    return from_blocks == produced


def source_text_chars(data, charset):
    """Texto bruto da fonte, sem interpretação de blocos: base independente para a cobertura."""
    soup = BeautifulSoup(decode(data, charset), 'lxml')
    for tag in soup(list(SKIP_TAGS)):
        tag.decompose()
    return strip_fold(soup.get_text(' '))


HEADING_RE = re.compile(r'^(?:LIVRO|T[ÍI]TULO|CAP[ÍI]TULO|SE[ÇC][ÃA]O|SUBSE[ÇC][ÃA]O|PARTE)\s+(?:[IVXLCDM]+|\d+|[ÚU]NIC[OA])(?:-[A-Z])?\b', re.I)


def headings(blocks):
    """Sequência de títulos/capítulos/seções (marca + denominação) fora de citações de outras leis."""
    out = []
    plain = [re.sub(r'\s+', ' ', md_plain(b, False)).strip() for b in mark_quoted(blocks)]
    for index, text in enumerate(plain):
        match = HEADING_RE.match(text)
        if not match or text.startswith('“') or len(text) > 150 or re.search(r'[.;:]\s', text + ' '):
            continue
        name = ''
        if not text[match.end():].strip():  # denominação em linha própria
            name = next((t for t in plain[index + 1:index + 3] if t and not NOTE_RE.match(t)), '')
        out.append(strip_fold(text + ' ' + strip_notes(name)))
    return out


def md_text_all(markdown):
    """Todo o texto de um Markdown deste acervo (inclui riscado e rótulos), sem sintaxe."""
    text = markdown.replace('~~', '')
    text = re.sub(r'\[((?:[^\[\]\\]|\\.)*)\]\([^)]*\)', r'\1', text)
    text = _strip_html_tags_preserving_escaped_angles(text)
    text = htmllib.unescape(text)
    return re.sub(r'\\([\\*_\[\]`~|.\-+#)])', r'\1', text)


# --------------------------------------------------------------------------
# Metadados do documento (cabeçalho YAML plano; valores em JSON)
# --------------------------------------------------------------------------

FRONTMATTER_KEYS = [
    'id', 'norma_id', 'norma_tipo', 'norma_numero', 'norma_data', 'titulo', 'esfera',
    'edicao_id', 'edicao_tipo', 'edicao_integral', 'edicao_relacionada',
    'fonte_orgao', 'fonte_url', 'fonte_formato', 'fonte_conferencia',
    'capturado_em', 'sha256_fonte',
    'situacao', 'situacao_fundamento', 'vigencia_certificada',
    'texto_riscado', 'anexos_no_corpo', 'tabelas', 'imagens_omitidas', 'efeitos_diferidos',
    'sha256_corpo_preservado', 'sha256_markdown', 'manifesto', 'contrato_versao',
]
REQUIRED_NOT_NULL = set(FRONTMATTER_KEYS) - {'sha256_corpo_preservado', 'edicao_relacionada', 'fonte_conferencia'}
SITUACOES = {'revogada', 'nao-informada', 'vigente-informada'}
EDICOES = {'historica', 'consolidada'}
SHA_RE = re.compile(r'^[0-9a-f]{64}$')


def render_frontmatter(meta):
    lines = ['---']
    for key in FRONTMATTER_KEYS:
        if key in meta and meta[key] is not None:
            lines.append(f'{key}: {json.dumps(meta[key], ensure_ascii=False)}')
    lines.append('---')
    return '\n'.join(lines) + '\n\n'


def parse_frontmatter(text):
    if not text.startswith('---\n'):
        raise ValueError('sem cabeçalho de metadados')
    end = text.index('\n---\n', 4)
    meta = {}
    for line in text[4:end].splitlines():
        key, _, value = line.partition(': ')
        meta[key] = json.loads(value)
    body = text[end + len('\n---\n'):]
    if not body.startswith('\n'):
        raise ValueError('cabeçalho deve ser seguido de linha em branco')
    return meta, body[1:]


def validate_meta(meta, name='documento'):
    """Contrato de metadados. Devolve a lista de violações (vazia quando válido)."""
    errors = []
    for key in meta:
        if key not in FRONTMATTER_KEYS:
            errors.append(f'{name}: campo fora do contrato: {key}')
    for key in REQUIRED_NOT_NULL:
        if key not in meta:
            errors.append(f'{name}: campo obrigatório ausente: {key} (use "{UNKNOWN}" quando não for conhecido)')
    if meta.get('contrato_versao') != CONTRACT_VERSION:
        errors.append(f'{name}: contrato_versao deve ser {CONTRACT_VERSION}')
    if meta.get('edicao_tipo') not in EDICOES:
        errors.append(f'{name}: edicao_tipo inválido: {meta.get("edicao_tipo")!r}')
    if meta.get('situacao') not in SITUACOES:
        errors.append(f'{name}: situacao inválida: {meta.get("situacao")!r}')
    if meta.get('vigencia_certificada') is not False:
        errors.append(f'{name}: vigencia_certificada deve ser false; o acervo não certifica vigência')
    if meta.get('edicao_integral') not in (True, False, UNKNOWN):
        errors.append(f'{name}: edicao_integral deve ser true, false ou "{UNKNOWN}"')
    for key in ('sha256_markdown', 'sha256_fonte', 'sha256_corpo_preservado'):
        value = meta.get(key)
        if value is not None and value != UNKNOWN and not SHA_RE.match(str(value)):
            errors.append(f'{name}: {key} não é SHA-256 hexadecimal nem "{UNKNOWN}"')
    if meta.get('capturado_em') != UNKNOWN and not re.match(r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$', str(meta.get('capturado_em'))):
        errors.append(f'{name}: capturado_em deve ser UTC (AAAA-MM-DDThh:mm:ssZ) ou "{UNKNOWN}"')
    if meta.get('fonte_url') != UNKNOWN and urlparse(str(meta.get('fonte_url'))).scheme != 'https':
        errors.append(f'{name}: fonte_url deve ser https ou "{UNKNOWN}"')
    if meta.get('situacao') == 'revogada' and meta.get('situacao_fundamento') in (None, UNKNOWN):
        errors.append(f'{name}: situacao revogada exige situacao_fundamento')
    if meta.get('edicao_tipo') == 'historica' and meta.get('edicao_integral') is True:
        errors.append(f'{name}: edição histórica não pode declarar integralidade consolidada')
    fonte_url = meta.get('fonte_url')
    conferencia = meta.get('fonte_conferencia')
    if isinstance(conferencia, list) and fonte_url and fonte_url != UNKNOWN:
        if fonte_url in conferencia:
            errors.append(f'{name}: fonte_conferencia não pode repetir a URL de fonte_url')
    return errors


# --------------------------------------------------------------------------
# Notas editoriais no corpo (delimitadas, para que a verificação as separe do texto da fonte)
# --------------------------------------------------------------------------

NOTE_OPEN = '<!-- nota-edicao:inicio -->'
NOTE_CLOSE = '<!-- nota-edicao:fim -->'


def note_block(lines):
    quoted = '\n>\n'.join('> ' + line for line in lines)
    return f'{NOTE_OPEN}\n\n{quoted}\n\n{NOTE_CLOSE}'


def strip_note(markdown):
    return re.sub(re.escape(NOTE_OPEN) + r'.*?' + re.escape(NOTE_CLOSE) + r'\n*', '', markdown, flags=re.S)


def date_br(iso):
    year, month, day = iso.split('-')
    return f'{int(day)}/{int(month)}/{year}'


# --------------------------------------------------------------------------
# Cálculo de todos os artefatos (usado por build e por verify: mesma lógica, mesmos bytes)
# --------------------------------------------------------------------------

# Divergências conhecidas por documento. A Lei 14.133 usa o formato legado (string por
# artigo). A LC 123 usa o formato estruturado por dispositivo: {dispositivo, fontes,
# descricao, tratamento, natureza}. Ver metadados/CONTRATO.md.
KNOWN_DIVERGENCES = {
    'br-federal-lei-2021-04-01-14133-consolidada': {
        '121': 'O PDF da Câmara repete "§ 4º § 4º" (erro tipográfico na fonte de conferência); o Planalto traz um único § 4º. '
               'O texto publicado segue o Planalto.',
    },
    'br-federal-lei-complementar-2006-12-14-123': {
        '47': {
            'dispositivo': 'art. 47, caput',
            'fontes': ['camara-lc123', 'planalto-lc123'],
            'descricao': ('Na edição da Câmara o caput tem a redação anterior à LC 147/2014; '
                          'o Planalto apresenta a nova redação.'),
            'tratamento': ('O Markdown segue a fonte principal (Câmara). A divergência fica no '
                           'manifesto e no aviso editorial; nenhuma redação é escolhida silenciosamente.'),
            'natureza': 'juridica',
        },
        '87-B': {
            'dispositivo': 'art. 87-B',
            'fontes': ['camara-lc123', 'planalto-lc123'],
            'descricao': ('Consta da edição da Câmara como art. 87-B com a nota literal da própria Câmara: '
                          'acrescido pela LC 214/2025, produzindo efeitos a partir de 1º/1/2027, e revogado pela '
                          'LC 227/2026. Não aparece na página do Planalto conferida. A data 1º/1/2027 na nota '
                          'refere-se aos efeitos da inclusão pela LC 214; a LC 227, art. 181, IV, "a", revoga o '
                          'art. 87-B sem atribuir essa data à revogação (outras alíneas do mesmo inciso trazem '
                          'datas próprias: 30/11/2026 e 1º/1/2033).'),
            'tratamento': ('O Markdown segue a fonte principal (Câmara) e preserva a nota completa do dispositivo. '
                           'O alerta fica no manifesto e no aviso editorial; o texto integral da LC 227 está em '
                           'federal/br-federal-lei-complementar-2026-01-13-227.md. O acervo não afirma vigência '
                           'nem escolhe a ausência do Planalto.'),
            'natureza': 'juridica',
        },
    },
    'br-federal-lei-complementar-2006-12-14-123-planalto': {
        '47': {
            'dispositivo': 'art. 47, caput',
            'fontes': ['camara-lc123', 'planalto-lc123'],
            'descricao': ('Na edição da Câmara o caput tem a redação anterior à LC 147/2014; '
                          'o Planalto apresenta a nova redação (e conserva riscada a anterior).'),
            'tratamento': ('O Markdown segue a fonte principal (Planalto). A divergência fica no '
                           'manifesto e no aviso editorial; nenhuma redação é escolhida silenciosamente.'),
            'natureza': 'juridica',
        },
        '87-B': {
            'dispositivo': 'art. 87-B',
            'fontes': ['camara-lc123', 'planalto-lc123'],
            'descricao': ('Consta da edição da Câmara (acrescido pela LC 214/2025, com nota de efeitos '
                          'e revogação pela LC 227/2026) e não aparece na página do Planalto conferida.'),
            'tratamento': ('O Markdown segue a fonte principal (Planalto), onde o art. 87-B não aparece. '
                           'O alerta fica no manifesto e no aviso editorial; o acervo não afirma vigência '
                           'nem escolhe a presença da Câmara.'),
            'natureza': 'juridica',
        },
    },
}
# Lei 13.303: divergências de forma revisadas entre o corpo preservado (Câmara) e o Planalto.
# São diferenças tipográficas/editoriais de um caractere após normalização; a auditoria não
# encontrou divergência de conteúdo. Qualquer divergência nova ou substancial bloqueia.
L13303_SLUG = 'br-federal-lei-2016-06-30-13303'
L13303_FORM_DIVERGENCES = ('9', '18', '24', '88')
L13303_FORM_FINGERPRINTS = {
    '9': dict(principal_sha256='bd98d974ddf7b155bf01eec4d75c4e7c5b9c781014b46626fd2dc2273728c072',
                   conferencia_sha256='2030f8b713583cf2f63228bd1901d590c7aa9d67237ae1efdcbef90e3fac98cb'),
    '18': dict(principal_sha256='196c3dc8fcc871205f702d0df4082fb1e026c9d78381bb29a53494885bd2220a',
                   conferencia_sha256='7666fe7ec4cf1f5047f0d10b0f0eb0f422a9e6225c629850da3dea2ff767b7c1'),
    '24': dict(principal_sha256='96a6e3aa7ce9d750fd835005c5c5a65097b22223de88db2fb3116a191922caff',
                   conferencia_sha256='c611062beec58512ff135bc190fe5b1e29dcf35de0704238e18780a0251b4118'),
    '88': dict(principal_sha256='a2cd823b9661ae3898dc9c55a02aba91967b6e589f24d7fb4a42e87f700c6445',
                   conferencia_sha256='7360500f64e351d3433a407254da586b8d7238bbebb27d2246005111ae900eae'),
}

# Impressões digitais do texto vigente (strip_fold + current_text_of) da diferença revisada do art. 121.
# Qualquer outra alteração nesse artigo invalida a exceção; não basta o número do artigo.
KNOWN_DIVERGENCE_FINGERPRINTS = {
    'br-federal-lei-2021-04-01-14133-consolidada': {
        '121': dict(
            principal_sha256='eb5e9fd12a114b6de71a92bd12c887fec154f722ddf7f69a0bf8490e6581d8fe',
            conferencia_sha256='455a156aa97a41b6de3ec9dd48e67f6cbc79c52d35e51d8bc1086e2a0508edfc',
            diferenca_esperada=dict(operacao='insert', principal='', conferencia='4'),
        ),
    },
}
LC123_NOTE_ARTICLES = ('47', '87-B')  # divergências entre Planalto e Câmara descritas no aviso editorial; build exige que persistam
LC123_SLUG = 'br-federal-lei-complementar-2006-12-14-123'
LC123_PLANALTO_SLUG = 'br-federal-lei-complementar-2006-12-14-123-planalto'
LC123_PLANALTO_ARQUIVO = 'federal/edicoes/br-federal-lei-complementar-2006-12-14-123-planalto.md'
# Exceções revisadas da LC 123: vinculadas ao conteúdo exato da diferença, nunca só ao número do artigo.
# principal/conferencia = SHA-256 do texto vigente; raw_principal = SHA-256 do texto bruto (inclui vetos/notas).
LC123_REVIEWED_EXCEPTIONS = {
    'divergencias_substanciais': {
        '47': dict(
            classe='divergencia_conhecida',
            motivo='Art. 47, caput: Câmara com redação anterior à LC 147/2014; Planalto com a nova redação.',
            principal_sha256='a285fcbef64f87ddd5d8c897de3764331d04194d4b55f823cb5b534cc7d4c8b1',
            conferencia_sha256='5301aa4e86316b0becfd6bbc7f41608c73e3b392c08a909266e0608fc2230aba',
        ),
    },
    'divergencias_editoriais': {
        '63': dict(
            classe='editorial',
            motivo='Planalto inclui no art. 63 o rótulo "CAPÍTULO X / DO ESTÍMULO À INOVAÇÃO / Seção I / Disposições Gerais"; '
                   'na Câmara esse rótulo aparece após o art. 63-E.',
            principal_sha256='2d08d8f7c8dc8e14388835a2bc4f5ad31d7f912936565a100fdbca172e600e71',
            conferencia_sha256='a07ef12db53a913e4eb3a3e1220df5e115964fb860d489b17bc75bdd811c441f',
        ),
        '64': dict(
            classe='editorial',
            motivo='Câmara traz a denominação da seção com nota de redação da LC 167/2019; Planalto não.',
            principal_sha256='658b8957ce3a702cc2e012b743f3853221c22f7a16887f30facefaca311b1d21',
            conferencia_sha256='b9c33eaacb7fd6e248fdf4c3b874bdd07ee00c21a6e684c0df0132a224e4f322',
        ),
        '89': dict(
            classe='editorial',
            motivo='Página do Planalto anexa ao art. 89 o bloco de assinaturas e a nota de republicação; a Câmara encerra no dispositivo.',
            principal_sha256='6d3deda4c45fdfb942df26001a74371a2c4a52a9a7025812ac5a9c1f87663051',
            conferencia_sha256='0e0051dea4943f17e4335f39d6f90b331a44eba820daecf48725c6aeb191dc8f',
        ),
    },
    'divergencias_de_forma': {
        '1': dict(principal_sha256='b84f18bdb56a6c33b3ef2c4dd46f012132a91c977b8df8225ed449082770a1a6',
                  conferencia_sha256='883c85d023c190f2a7c3a231e0d48b7861c8c544f1c766a0d28bff1ab62616cb'),
        '3': dict(principal_sha256='52e6adf21281e5576733f4918bf24eeacf64337c0f186cb99ebd738d679d818c',
                  conferencia_sha256='567b14bfef638e66cd95a09d2121f6d9e3a884075f7cabce9b43edf6a0b89489'),
        '9': dict(principal_sha256='7a3a511807a5ac14c71b365de1b5ba395fafd8499b3c400d8d5bb09ef471ef5b',
                  conferencia_sha256='f8bfb410e0f3087af09a205a0db1137263c12a7cf2f2e9c3a6356ce20247956e'),
        '13': dict(principal_sha256='9c69802cca12bed319e6bcb1bf309a9a4a256ed90d9256edff553005365bb7ac',
                   conferencia_sha256='759f838c98a956c25f75678605f56acce543a532824bf05bfdc5d9171dc84d63'),
        '17': dict(principal_sha256='84a56c37fa118403d6202a9d773be22d1799e5cf1fd6a92db56e478a23b2068b',
                   conferencia_sha256='0c7931e3ec2905d328715d5dee06d7c98804c9e886e92d0f2a4617c13975c258'),
        '18': dict(principal_sha256='20b021aaea06aa428a77f8df3c70dfe46dd3f47da6c02b6bea0e917ea07b29b0',
                   conferencia_sha256='79a91c35d48861d815a68ec425ac9a7457475abe16b5fcbece4739d91303ee87'),
        '18-A': dict(principal_sha256='97f449247425d065c9845c728441bebd5e40d7d94d21890dcbddb92c07a1b51f',
                     conferencia_sha256='9a8f3380ecf748b6b01308f8a35a5cafc8d6d90681ae06e2d5d5efc0601ccfab'),
        '25': dict(principal_sha256='35500bb6c3b293d9b99697ad93540e8b4c8b7e8d484467ac3e615dea94a4c2bb',
                   conferencia_sha256='80d48f2f202b331d30ce19e42daa64685fc7b52d4083c69d8cef58e29e758f58'),
        '68': dict(principal_sha256='0aab0285bf6533ff007808e4c4351f69fb72096ae8bf88d07265499389aed35d',
                   conferencia_sha256='cef4f4cba0c8b522dcfecf8ad4d7cda3d6f96399f649855013dd53e285d4ce55'),
        '74': dict(principal_sha256='dbbdaaa62b1e2ff6b2c5f8f074fe2ed521d49cf72b6bc26edf5176479952a0e7',
                   conferencia_sha256='7e08fd88acc65d9f22a0ae54367464f15aea0e8fa156eba2dabb67a306872bed'),
        '79-D': dict(principal_sha256='a41b6cd98f7ae05661830ae13f5aeb26fc576e23e07e377e2891b63828062576',
                     conferencia_sha256='c30ff4cfc52e97695b658d7793f57c09a772b3e26bc9a774e99bd5537d9e0208'),
    },
    'dispositivos_exclusivos_principal': {
        '63-A': dict(
            classe='veto',
            motivo='Marcador de veto da LC 155/2016 presente só na Câmara.',
            raw_principal_sha256='bfc32c32af02cd23146483f6175c5c5d68767fba09cf851f3e2b7b23b76315a3',
            principal_sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        ),
        '63-B': dict(
            classe='veto',
            motivo='Marcador de veto da LC 155/2016 presente só na Câmara.',
            raw_principal_sha256='fb59cd344a11f1d0f930b27dac68fa7fdb686f94f9b6f04f29de6b632800601e',
            principal_sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        ),
        '63-C': dict(
            classe='veto',
            motivo='Marcador de veto da LC 155/2016 presente só na Câmara.',
            raw_principal_sha256='4720a7d51731e47c73c7b345527808ec48e8ad3f344a8d7128173be84ce03a00',
            principal_sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        ),
        '63-D': dict(
            classe='veto',
            motivo='Marcador de veto da LC 155/2016 presente só na Câmara.',
            raw_principal_sha256='f9686788168c3243436d75d6eff6c683013056298c19ecfe7f6676f5db9e276e',
            principal_sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        ),
        '63-E': dict(
            classe='veto',
            motivo='Marcador de veto da LC 155/2016; na Câmara o rótulo do Capítulo X segue anexado a este dispositivo.',
            raw_principal_sha256='14ba19689783a21e69eb6f60331a5b7356d8fea0cfa9c78253049fd57c13021a',
            principal_sha256='4b414418e530bb4040edde91c9273bdb0f2e763ff135e025a275738d58168936',
        ),
        '87-B': dict(
            classe='divergencia_conhecida',
            motivo='Art. 87-B (LC 214/2025, revogado pela LC 227/2026) consta da Câmara e não aparece no Planalto conferido.',
            raw_principal_sha256='33ee094d086baa864954d8bc9d20029e3a895a39a485a9cd5f2721cade63a937',
            principal_sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        ),
    },
    'dispositivos_exclusivos_conferencia': {},
}
# Diferenças que o comparador marca como "substanciais" por tamanho, mas que são de estrutura/editorial.
LC123_EDITORIAL = {
    '63': ('Diferença de títulos/seções e notação de veto adjacentes ao artigo entre Câmara e Planalto; '
           'o dispositivo normativo do art. 63 coincide.'),
    '64': ('Nota de denominação de seção presente numa fonte e ausente ou distinta na outra; '
           'o dispositivo normativo do art. 64 coincide.'),
    '89': ('Fecho, assinaturas e cabeçalhos de anexos absorvidos no artigo na página do Planalto; '
           'o dispositivo normativo do art. 89 coincide.'),
}
LC123_VETO_MARKERS = ('63-A', '63-B', '63-C', '63-D', '63-E')
LC123_VETO_MARKER_NOTE = (
    'Marcador de veto na edição da Câmara (Lei Complementar nº 155, de 27/10/2016); '
    'não é conteúdo normativo novo. Ausente na página do Planalto conferida.'
)
DIVERGENCIA_FIELDS = ('dispositivo', 'fontes', 'descricao', 'tratamento', 'natureza')

HISTORIC_NOTE = [
    '**Edição histórica — não é a edição consolidada.** Este arquivo preserva, sem alterações, a redação da Lei nº 14.133/2021 '
    'que já estava no acervo. A fonte oficial e a data de captura desse texto não foram registradas '
    '(valores "desconhecido" no cabeçalho). Ele não incorpora alterações posteriores; por exemplo: as partes vetadas e '
    'promulgadas (arts. 37, § 2º; 54, § 1º; 115, § 4º; 175, § 2º), os arts. 44-A e 184-A e a redação do art. 193, II, '
    'dada pela Lei Complementar nº 198/2023.',
    'A edição consolidada, reconciliada com a fonte oficial, está em `edicoes/br-federal-lei-2021-04-01-14133-consolidada.md`. '
    'A presença deste arquivo no acervo não indica vigência.',
]


def edition_note(doc, rec, extra=()):
    spec_name = SOURCES[doc['fonte']]['orgao']
    lines = [f'**Edição {doc["edicao"]["tipo"]} — {spec_name}.** Fonte: {rec["url"]} (capturada em {rec["capturado_em"]}, '
             f'SHA-256 da fonte `{rec["sha256"]}`). O acervo não certifica vigência.']
    lines += list(extra)
    return note_block(lines)


def read_baseline(path_in_repo):
    """Corpo de um arquivo do acervo, sem cabeçalho de metadados nem aviso de edição histórica."""
    text = (ROOT / path_in_repo).read_text(encoding='utf-8')
    if text.startswith('---\n'):
        _, text = parse_frontmatter(text)
    return strip_note(text)


def preserved_blocks(markdown):
    """Blocos do corpo preservado, sem imagens embutidas em data-URI."""
    return [b for b in re.split(r'\n\s*\n', markdown) if b.strip() and not b.startswith('![](data:')]


def measure_preserved_structure(markdown):
    """Contagens estruturais medidas no corpo preservado (não constantes fixas)."""
    blocks = preserved_blocks(markdown)
    anexos = sum(1 for b in blocks if re.match(r'^ANEXO\b', md_plain(b, True).strip(), re.I))
    tabelas = 0
    for block in blocks:
        stripped = block.strip()
        if stripped.startswith('<table'):
            tabelas += 1
        elif stripped.startswith('|') and re.search(r'^\|\s*---', block, re.M):
            tabelas += 1
    imagens = len(re.findall(r'!\[[^\]]*\]\(data:', markdown))
    return dict(
        texto_riscado='~~' in markdown,
        anexos_no_corpo=anexos,
        tabelas=tabelas,
        imagens_embutidas=imagens,
        titulos_e_capitulos=len(headings(main_body_blocks(blocks))),
        blocos=len(blocks),
    )


def non_article_blocks(blocks):
    """Blocos do corpo principal que não iniciam artigo (títulos, ementa estrutural, notas soltas)."""
    out = []
    for block in main_body_blocks(blocks):
        plain = re.sub(r'\s+', ' ', md_plain(block, True)).strip()
        if article_key(plain) is not None:
            continue
        out.append(strip_fold(strip_notes(plain)))
    return out


def full_body_coverage(preserved_md, source_blocks_list):
    """Cobertura integral: texto normalizado do corpo preservado == conversão da captura atual."""
    left = strip_fold(md_text_all(preserved_md))
    right = strip_fold(''.join(md_plain(b, True) for b in source_blocks_list))
    return dict(
        descricao=('texto integral do corpo preservado == texto convertido da captura atual usada para '
                   'conferir (inclui títulos, notas e blocos fora de artigos), após normalização'),
        equivalente=left == right,
        caracteres_normalizados=len(left),
    )


def classify(result):
    """Separa divergências de forma (marcas soltas, ordinais) das substanciais."""
    minor, major = [], []
    for item in result['divergentes']:
        changed = sum(len(d['principal']) + len(d['conferencia']) for d in item['diferencas'])
        (minor if changed <= 12 and item['similaridade'] >= 0.995 else major).append(item['artigo'])
    return minor, major


def current_fingerprint(blocks):
    """SHA-256 do texto vigente do artigo (sem riscados, notas e marcas soltas)."""
    return sha256(strip_fold(''.join(current_text_of(blocks))).encode('utf-8'))


def raw_fingerprint(blocks):
    """SHA-256 do texto bruto do artigo (inclui marcadores de veto e notas da fonte)."""
    return sha256(strip_fold('\n'.join(md_plain(b, True) for b in blocks)).encode('utf-8'))


def article_proof(primary_blocks, secondary_blocks):
    primary = split_articles(main_body_blocks(primary_blocks))
    secondary = split_articles(main_body_blocks(secondary_blocks))
    result = compare_articles(primary, secondary)
    minor, major = classify(result)
    result['divergencias_de_forma'] = minor
    result['divergencias_substanciais'] = major
    for item in result['divergentes']:
        item['diferencas'] = item['diferencas'][:3]
    # devolve só o dict artigo->blocos (sem a ordem) para as travas de impressão digital
    return result, primary[0], secondary[0]


def classify_lc123_exceptions(art, camara_side='principal'):
    """Classifica editoriais (63/64/89) e vetos (63-A..E) sem remover a detecção bruta."""
    editorial_reg = LC123_REVIEWED_EXCEPTIONS['divergencias_editoriais']
    exclusive_reg = LC123_REVIEWED_EXCEPTIONS['dispositivos_exclusivos_principal']
    exclusive_key = 'apenas_na_principal' if camara_side == 'principal' else 'apenas_na_conferencia'
    art['divergencias_editoriais'] = [k for k in art['divergencias_substanciais'] if k in editorial_reg]
    art['marcadores_de_veto'] = [k for k in art.get(exclusive_key, [])
                                 if exclusive_reg.get(k, {}).get('classe') == 'veto']
    art['divergencias_substanciais_revisadas'] = [k for k in art['divergencias_substanciais']
                                                  if k in LC123_REVIEWED_EXCEPTIONS['divergencias_substanciais']]
    return art


def _mismatch(label, unexpected, missing):
    parts = []
    if unexpected:
        parts.append(f'novas sem revisão: {unexpected}')
    if missing:
        parts.append(f'revisadas ausentes: {missing}')
    return f'{label}: ' + '; '.join(parts) if parts else None


def lock_reviewed_pair(article, spec, primary_articles, secondary_articles, label, swap=False):
    """Confere impressões digitais dos dois lados; falha se o conteúdo da diferença mudou.

    `swap=True` inverte principal/conferência: mesma trava revisada, edição com fontes trocadas.
    """
    problems = []
    principal = current_fingerprint(primary_articles.get(article, []))
    conferencia = current_fingerprint(secondary_articles.get(article, []))
    expect_p = spec['conferencia_sha256'] if swap else spec['principal_sha256']
    expect_c = spec['principal_sha256'] if swap else spec['conferencia_sha256']
    if principal != expect_p or conferencia != expect_c:
        problems.append(f'{label} art. {article}: conteúdo da diferença diverge da revisão '
                        f'(não basta o número do artigo)')
    return problems


def lock_lc123_exceptions(art, primary_articles, secondary_articles, orientation='camara-primary'):
    """Recusa qualquer divergência ou dispositivo exclusivo novo da LC 123.

    Exceções só valem para o trecho revisado (impressão digital do texto); alteração
    adicional dentro de artigo já conhecido também é rejeitada. A whitelist e os
    hashes de `LC123_REVIEWED_EXCEPTIONS` são os da main (Câmara como principal);
    `orientation='planalto-primary'` só espelha a aplicação, sem aceitar diferença nova.
    """
    problems = []
    reg = LC123_REVIEWED_EXCEPTIONS
    swap = orientation == 'planalto-primary'
    classify_lc123_exceptions(art, camara_side='conferencia' if swap else 'principal')

    expected_major = set(reg['divergencias_substanciais']) | set(reg['divergencias_editoriais'])
    actual_major = set(art['divergencias_substanciais'])
    msg = _mismatch('LC 123 divergências substanciais',
                    sorted(actual_major - expected_major), sorted(expected_major - actual_major))
    if msg:
        problems.append(msg)
    for article, spec in {**reg['divergencias_substanciais'], **reg['divergencias_editoriais']}.items():
        problems.extend(lock_reviewed_pair(
            article, spec, primary_articles, secondary_articles, 'LC 123', swap=swap))

    expected_form = set(reg['divergencias_de_forma'])
    actual_form = set(art['divergencias_de_forma'])
    msg = _mismatch('LC 123 divergências de forma',
                    sorted(actual_form - expected_form), sorted(expected_form - actual_form))
    if msg:
        problems.append(msg)
    for article, spec in reg['divergencias_de_forma'].items():
        problems.extend(lock_reviewed_pair(
            article, spec, primary_articles, secondary_articles, 'LC 123 forma', swap=swap))

    # Com Câmara como principal, 63-A..E e 87-B estão só nela; com Planalto como
    # principal, os mesmos dispositivos ficam só na conferência (Câmara).
    if swap:
        expected_excl_primary, expected_excl_conf = (
            set(reg['dispositivos_exclusivos_conferencia']),
            set(reg['dispositivos_exclusivos_principal']),
        )
    else:
        expected_excl_primary, expected_excl_conf = (
            set(reg['dispositivos_exclusivos_principal']),
            set(reg['dispositivos_exclusivos_conferencia']),
        )
    actual_excl = set(art['apenas_na_principal'])
    msg = _mismatch('LC 123 dispositivos exclusivos na principal',
                    sorted(actual_excl - expected_excl_primary),
                    sorted(expected_excl_primary - actual_excl))
    if msg:
        problems.append(msg)
    camara_articles = secondary_articles if swap else primary_articles
    for article, spec in reg['dispositivos_exclusivos_principal'].items():
        raw = raw_fingerprint(camara_articles.get(article, []))
        cur = current_fingerprint(camara_articles.get(article, []))
        if raw != spec['raw_principal_sha256'] or cur != spec['principal_sha256']:
            problems.append(f'LC 123 dispositivo exclusivo art. {article}: conteúdo diverge da revisão')

    actual_conf = set(art['apenas_na_conferencia'])
    msg = _mismatch('LC 123 dispositivos exclusivos na conferência',
                    sorted(actual_conf - expected_excl_conf),
                    sorted(expected_excl_conf - actual_conf))
    if msg:
        problems.append(msg)

    exclusive_87b_side = art['apenas_na_conferencia'] if swap else art['apenas_na_principal']
    if '47' not in art['divergencias_substanciais'] or '87-B' not in exclusive_87b_side:
        problems.append('as divergências LC 123 (art. 47, art. 87-B) descritas no aviso editorial não se confirmaram')

    art['excecoes_revisadas'] = {
        'divergencias_substanciais': sorted(reg['divergencias_substanciais']),
        'divergencias_editoriais': sorted(reg['divergencias_editoriais']),
        'marcadores_de_veto': sorted(k for k, v in reg['dispositivos_exclusivos_principal'].items()
                                     if v.get('classe') == 'veto'),
        'dispositivo_exclusivo_conhecido': ['87-B'],
        'divergencias_de_forma': sorted(reg['divergencias_de_forma'], key=lambda x: (len(x), x)),
        'orientacao_fontes': orientation,
    }
    return problems


def lock_known_divergence_fingerprints(slug, art, primary_articles, secondary_articles):
    """Exige que cada divergência conhecida preserve o conteúdo revisado (caso Lei 14.133 art. 121)."""
    problems = []
    known = KNOWN_DIVERGENCES.get(slug, {})
    fingerprints = KNOWN_DIVERGENCE_FINGERPRINTS.get(slug, {})
    actual = {d['artigo'] for d in art['divergentes']}
    unexpected = sorted(actual - set(known))
    missing = sorted(set(known) - actual)
    if unexpected:
        problems.append(f'divergências não explicadas: {unexpected}')
    if missing:
        problems.append(f'divergências explicadas ausentes: {missing}')
    for article, spec in fingerprints.items():
        problems.extend(lock_reviewed_pair(article, spec, primary_articles, secondary_articles, slug))
        expected_diff = spec.get('diferenca_esperada')
        if not expected_diff:
            continue
        item = next((d for d in art['divergentes'] if d['artigo'] == article), None)
        if item is None:
            continue
        diffs = item.get('diferencas') or []
        if len(diffs) != 1 or diffs[0].get('operacao') != expected_diff['operacao'] \
                or diffs[0].get('principal') != expected_diff['principal'] \
                or diffs[0].get('conferencia') != expected_diff['conferencia']:
            problems.append(f'{slug} art. {article}: trecho divergente não é o tipográfico revisado')
    return problems


def annotate_lc123_reconciliation(artigos, camara_side='principal'):
    """Reclassifica diferenças editoriais da LC 123 e identifica marcadores de veto.

    O comparador trata arts. 63, 64 e 89 como substanciais pelo tamanho do diff, mas os
    trechos divergentes são títulos, notas de seção e fecho/assinaturas. Os arts. 63-A a
    63-E exclusivos da Câmara são marcadores de veto, não conteúdo normativo novo.
    `camara_side` indica em qual lado da comparação está a edição da Câmara.
    """
    editorial = [a for a in artigos.get('divergencias_substanciais', []) if a in LC123_EDITORIAL]
    artigos['divergencias_substanciais'] = [
        a for a in artigos.get('divergencias_substanciais', []) if a not in LC123_EDITORIAL
    ]
    artigos['divergencias_editoriais'] = {a: LC123_EDITORIAL[a] for a in editorial}
    exclusive_key = 'apenas_na_principal' if camara_side == 'principal' else 'apenas_na_conferencia'
    veto = [a for a in artigos.get(exclusive_key, []) if a in LC123_VETO_MARKERS]
    artigos['marcadores_veto'] = {a: LC123_VETO_MARKER_NOTE for a in veto}
    return artigos


def pdf_to_blocks(data):
    lines = [l.rstrip() for l in pdf_text(data).replace('\f', '\n').splitlines()]
    paragraphs = []
    for line in lines:
        if not line.strip():
            continue
        if re.match(r'^\s{6,}\S', line) or not paragraphs:
            paragraphs.append(line.strip())
        else:
            paragraphs[-1] += ' ' + line.strip()
    return paragraphs


def source_blocks(key, data):
    spec = SOURCES[key]
    if spec['formato'] == 'pdf':
        return pdf_to_blocks(data), None
    conv = convert_html(data, spec['charset'], spec['url'])
    return conv.blocks, conv


def extract_effect_text(data, article_pattern):
    """Extrai blocos do artigo cujo início casa com `article_pattern`.

    Retorna lista vazia se o marcador estiver ausente. Consumidores que publicam
    afirmações de efeitos devem passar o resultado por `require_effect_evidence`
    (ou `extract_required_effect_text`); lista vazia nunca é sucesso.
    """
    conv = convert_html(data, 'cp1252', 'https://www.planalto.gov.br/')
    out, started = [], False
    for block in conv.blocks:
        plain = re.sub(r'\s+', ' ', md_plain(block, True)).strip()
        if re.match(article_pattern, plain):
            started = True
        elif started and re.match(r'^(Brasília|Art\.)', plain):
            break
        if started:
            out.append(plain)
    return out


# Origens admitidas para data de evento de revogação (ver metadados/CONTRATO.md).
REVOGACAO_DATA_ORIGENS = {'informada-explicitamente', 'resolvida-da-publicacao-oficial', UNKNOWN}
ARTS_8666_193_I = [f'art. {n}' for n in range(89, 109)]
DOU_FOOTER_RE = re.compile(
    r'Este texto não substitui o publicado no DOU de\s+(1[ºo]|0?\d{1,2})[./](\d{1,2})[./](\d{4})'
    r'(?:\s*[-–]\s*Edição\s+[\w\-]+)?',
    re.I,
)


def dou_publication_from_planalto(data, charset='cp1252'):
    """Data ISO e trecho do rodapé do Planalto sobre publicação no DOU; (None, None) se ausente."""
    text = re.sub(r'\s+', ' ', source_text_chars_from_html(data, charset))
    match = DOU_FOOTER_RE.search(text)
    if not match:
        return None, None
    day_raw, month, year = match.group(1), match.group(2), match.group(3)
    day = 1 if re.match(r'^1[ºo]$', day_raw, re.I) else int(day_raw)
    return f'{year}-{int(month):02d}-{day:02d}', match.group(0).strip()


def extract_art193_inciso_i(data):
    """Texto literal do art. 193, I, da Lei 14.133 na fonte do Planalto (sem riscados)."""
    conv = convert_html(data, SOURCES['planalto-14133']['charset'], SOURCES['planalto-14133']['url'])
    started = False
    for block in conv.blocks:
        if block.startswith('~~'):
            continue
        plain = re.sub(r'\s+', ' ', md_plain(block, True)).strip()
        if re.match(r'^Art\.\s*193\b', plain):
            started = True
            continue
        if started and re.match(r'^Art\.\s*194\b', plain):
            break
        if started and re.match(r'^I\s*-', plain):
            return plain
    return None


def eventos_revogacao_8666(fontes, sources, lc198_texto):
    """Dois eventos distintos: arts. 89–108 na publicação (193, I) e 30/12/2023 (193, II, a / LC 198)."""
    if not lc198_texto:
        raise SystemExit(
            'LC 198: evidência de efeitos ausente para eventos_revogacao da Lei 8.666 '
            '(lista vazia não é sucesso)')
    pub_iso, pub_trecho = dou_publication_from_planalto(
        sources['planalto-14133'], SOURCES['planalto-14133']['charset'])
    art193_i = extract_art193_inciso_i(sources['planalto-14133'])
    if art193_i is None:
        raise SystemExit('Lei 14.133: art. 193, I, não encontrado na fonte do Planalto')
    if pub_iso is None:
        data_parcial = dict(valor=UNKNOWN, origem=UNKNOWN,
                            expressao_na_fonte='na data de publicação desta Lei')
    else:
        data_parcial = dict(
            valor=pub_iso,
            origem='resolvida-da-publicacao-oficial',
            expressao_na_fonte='na data de publicação desta Lei',
            prova=dict(
                tipo='rodape-planalto-dou',
                fonte_chave='planalto-14133',
                fonte_url=SOURCES['planalto-14133']['url'],
                sha256_fonte=fontes['planalto-14133']['sha256'],
                trecho=pub_trecho,
            ),
        )
    texto_ii_a = [line for line in lc198_texto if re.match(r'^(Art\.|II\b|a\)|b\)|c\))', line)]
    return [
        dict(
            id='lei8666-revogacao-parcial-193-I',
            tipo='revogacao-parcial',
            alcance='arts. 89 a 108',
            dispositivos=list(ARTS_8666_193_I),
            fundamento=dict(
                norma_id='br-federal-lei-2021-04-01-14133',
                dispositivo='art. 193, I',
                texto_literal=art193_i,
                fonte_url=SOURCES['planalto-14133']['url'],
                sha256_fonte=fontes['planalto-14133']['sha256'],
            ),
            data=data_parcial,
            leitura=('O art. 193, I, da Lei 14.133 revoga os arts. 89 a 108 da Lei 8.666 na data de publicação '
                     'da Lei 14.133. A data ISO resolve essa expressão a partir do rodapé do Planalto sobre o DOU; '
                     'não é data de aplicação a contratos concretos. Publicação, vigência e regras de transição '
                     '(art. 191) permanecem distintas.'),
        ),
        dict(
            id='lei8666-revogacao-193-II-a',
            tipo='revogacao',
            alcance='Lei nº 8.666, de 21 de junho de 1993',
            dispositivos=['Lei nº 8.666, de 21 de junho de 1993'],
            fundamento=dict(
                norma_id='br-federal-lei-2021-04-01-14133',
                dispositivo='art. 193, II, a',
                norma_modificadora='Lei Complementar nº 198, de 28 de junho de 2023',
                texto_literal=texto_ii_a,
                fonte_url=SOURCES['planalto-lc198']['url'],
                sha256_fonte=fontes['planalto-lc198']['sha256'],
            ),
            data=dict(
                valor='2023-12-30',
                origem='informada-explicitamente',
                expressao_na_fonte='em 30 de dezembro de 2023',
            ),
            leitura=('O art. 193, II, a, com a redação da LC 198/2023, indica a revogação da Lei 8.666 em '
                     '30 de dezembro de 2023. Data informada explicitamente no texto; o acervo não resolve '
                     'hipóteses de transição do art. 191 nem aplica essa data a contratos concretos.'),
        ),
    ]


# Trechos literais revisados que devem aparecer na evidência antes de publicar
# datas/leituras estruturadas. Não calcula vigência: só recusa afirmação sem
# correspondência no literal. Specs extras (LC 227 arts. 181/182) reusam o
# mesmo gate; lista vazia nunca é sucesso.
EFFECT_EVIDENCE = {
    'lc238-art-10': dict(
        sha256_literal_revisado='638aea4028ecdcfe3d13d5b8490b93bdedd776be94f79d1aeb8f03f52e17b232',
        label='LC 238 art. 10',
        source_key='planalto-lc238',
        article_pattern=r'^Art\. 10\.',
        required_fragments=(
            'entra em vigor na data de sua publicação',
            '1º de janeiro de 2028',
            'art. 18-A, §§ 1º e 2º',
            '1º de janeiro de 2027',
            'demais dispositivos',
        ),
    ),
    'lc227-art-181': dict(
        sha256_literal_revisado='e85951b772b8135f98239162fc9da30aa401b25a76bf114515e7079ea131882c',
        label='LC 227 art. 181',
        source_key='planalto-lc227',
        article_pattern=r'^Art\. 181\.\s*Revogam',
        required_fragments=(
            'Revogam-se',
            'art. 87-B',
            'Lei Complementar nº 123',
            'Lei Complementar nº 214',
        ),
    ),
    'lc227-art-182': dict(
        sha256_literal_revisado='795a57f4275636558a6b560e88f99bbbd7844373f8104b069275cd64c2a2dae2',
        label='LC 227 art. 182',
        source_key='planalto-lc227',
        article_pattern=r'^Art\. 182\.\s*Esta Lei Complementar entra',
        required_fragments=(
            'entra em vigor na data de sua publicação',
            '1º de janeiro de 2027',
            'demais dispositivos',
        ),
    ),
    'lc198-art-3': dict(
        sha256_literal_revisado='5a1dbe7b5941c3e426f3fed8b8e6a16a4adf354cdc2f34e2f58793bef827a7fb',
        label='LC 198 art. 3º',
        source_key='planalto-lc198',
        article_pattern=r'^Art\. 3º',
        required_fragments=(
            'art. 193',
            '30 de dezembro de 2023',
            'Lei nº 8.666',
            'Lei nº 10.520',
        ),
    ),
    'lc198-art-4': dict(
        sha256_literal_revisado='5bf2d006695a2d60f08543d3dc3d2826c7f2946090998c9375db4e33474d09c7',
        label='LC 198 art. 4º',
        source_key='planalto-lc198',
        article_pattern=r'^Art\. 4º',
        required_fragments=(
            'entra em vigor na data de sua publicação',
        ),
    ),
}


def require_effect_evidence(label, texts, required_fragments, reviewed_sha256=None):
    """Recusa publicação de afirmações de efeitos sem evidência literal revisada.

    `texts` é o retorno de `extract_effect_text` (lista vazia se o marcador falta).
    Fonte vazia, dispositivo ausente, literal em branco, truncado ou com data
    alterada falham até revisão explícita dos trechos em `required_fragments`.
    O hash do literal completo revisado é obrigatório para aceitar a evidência.
    Normaliza apenas espaços; não calcula vigência nem aceita mera presença dos fragmentos.
    Devolve `texts` inalterado quando a evidência passa.
    """
    problems = []
    if not texts:
        problems.append(f'{label}: evidência ausente (marcador do dispositivo não encontrado na fonte)')
    else:
        joined = ' '.join(texts)
        if not joined.strip():
            problems.append(f'{label}: evidência vazia após extração')
        literal_sha256 = sha256(re.sub(r'\s+', ' ', joined).strip().encode('utf-8'))
        if not reviewed_sha256 or literal_sha256 != reviewed_sha256:
            problems.append(f'{label}: literal completo diverge da revisão autenticada')
        missing = [frag for frag in required_fragments if frag not in joined]
        if missing:
            problems.append(
                f'{label}: evidência truncada ou alterada; faltam trechos revisados: {missing}')
    if problems:
        raise SystemExit('Evidência de efeitos insuficiente:\n - ' + '\n - '.join(problems))
    return texts


def extract_required_effect_text(sources, spec_id):
    """Extrai o dispositivo e exige os trechos revisados de `EFFECT_EVIDENCE[spec_id]`."""
    spec = EFFECT_EVIDENCE[spec_id]
    data = sources.get(spec['source_key'])
    if not data:
        texts = []
    else:
        texts = extract_effect_text(data, spec['article_pattern'])
    return require_effect_evidence(
        spec['label'], texts, spec['required_fragments'], spec['sha256_literal_revisado'])


def compute(sources, fontes, baseline_texts=None):
    """sources: chave -> bytes (None se indisponível); fontes: chave -> registro de captura."""
    docs_out, proofs = {}, {}
    manifest_docs = []
    repo_rel = {d['slug']: d['arquivo'] for d in DOCS}

    # --- edições convertidas ---
    converted = {}
    for doc in DOCS:
        if doc['modo'] != 'converter':
            continue
        key = doc['fonte']
        rec = fontes[key]
        data = sources[key]
        conv = convert_html(data, SOURCES[key]['charset'], doc['base_url'])
        body = blocks_to_markdown(conv.blocks, r'^LEI(?: COMPLEMENTAR)? N')
        title_at = body.index('# ') if body.startswith('# ') else body.index('\n# ') + 1
        title_end = body.index('\n\n', title_at)
        head, rest = body[:title_end], body[title_end + 2:]
        converted[doc['slug']] = dict(doc=doc, conv=conv, body=body, head=head, rest=rest, rec=rec,
                                      title=body[title_at + 2:title_end])

    # --- provas de conferência ---
    reconciliation = {}
    for slug, item in converted.items():
        doc, conv, rec = item['doc'], item['conv'], item['rec']
        proof = dict(documento=slug, fonte_principal=doc['fonte'], sha256_fonte_principal=rec['sha256'],
                     fontes_conferencia=[])
        coverage_ok = strip_fold(source_text_chars_from_html(sources[doc['fonte']], SOURCES[doc['fonte']]['charset'])) == \
            strip_fold(md_text_all(item['body']))
        proof['cobertura_texto'] = dict(
            descricao='texto integral da página da fonte (sem imagens) == texto do Markdown publicado, após normalização',
            equivalente=coverage_ok,
            caracteres_normalizados=len(strip_fold(md_text_all(item['body']))))
        proof['conversao'] = dict(conv.stats, imagens=conv.images, tabelas=conv.tables, blocos=len(conv.blocks))
        article_splits = {}
        for ckey in doc['conferencia']:
            if sources.get(ckey) is None:
                continue
            blocks, _ = source_blocks(ckey, sources[ckey])
            art_result, primary_arts, secondary_arts = article_proof(conv.blocks, blocks)
            entry = dict(fonte=ckey, url=SOURCES[ckey]['url'], sha256=fontes[ckey]['sha256'],
                         artigos=art_result)
            entry['titulos_e_capitulos'] = dict(
                iguais=headings(main_body_blocks(conv.blocks)) == headings(main_body_blocks(blocks)),
                principal=len(headings(main_body_blocks(conv.blocks))),
                conferencia=len(headings(main_body_blocks(blocks))))
            proof['fontes_conferencia'].append(entry)
            article_splits[ckey] = (primary_arts, secondary_arts)
        proof['_article_splits'] = article_splits
        reconciliation[slug] = proof

    # gates da Lei 14.133 — exceções vinculadas ao conteúdo revisado, não só ao número do artigo
    slug14 = 'br-federal-lei-2021-04-01-14133-consolidada'
    entry = reconciliation[slug14]['fontes_conferencia'][0]
    known = KNOWN_DIVERGENCES[slug14]
    art = entry['artigos']
    problems = []
    if art['apenas_na_principal'] or art['apenas_na_conferencia']:
        problems.append(f'artigos ausentes entre fontes: {art["apenas_na_principal"]} {art["apenas_na_conferencia"]}')
    primary14, secondary14 = reconciliation[slug14]['_article_splits'][entry['fonte']]
    problems.extend(lock_known_divergence_fingerprints(slug14, art, primary14, secondary14))
    if not entry['titulos_e_capitulos']['iguais']:
        problems.append('sequência de títulos/capítulos difere entre Planalto e Câmara')
    art['divergencias_explicadas'] = {k: v for k, v in known.items()}
    for slug, proof in reconciliation.items():
        if not proof['cobertura_texto']['equivalente']:
            problems.append(f'{slug}: cobertura de texto não equivalente à fonte')
    # LC 123: rejeitar qualquer diferença ou dispositivo exclusivo novo; classificar editoriais/vetos
    # Travas exactas da main (Câmara como principal); a edição Planalto reusa a mesma whitelist espelhada.
    def _gate_lc123(slug, orientation, camara_side):
        entry = reconciliation[slug]['fontes_conferencia'][0]
        arts = entry['artigos']
        primary, secondary = reconciliation[slug]['_article_splits'][entry['fonte']]
        gate_problems = lock_lc123_exceptions(arts, primary, secondary, orientation=orientation)
        annotate_lc123_reconciliation(arts, camara_side=camara_side)
        exclusive_key = 'apenas_na_principal' if camara_side == 'principal' else 'apenas_na_conferencia'
        if '47' not in arts['divergencias_substanciais'] or '87-B' not in arts[exclusive_key]:
            gate_problems.append(
                f'{slug}: as divergências LC 123 (art. 47, art. 87-B) descritas no aviso editorial não se confirmaram')
        editorial_found = set(arts.get('divergencias_editoriais', {}))
        if editorial_found != set(LC123_EDITORIAL):
            gate_problems.append(
                f'{slug}: divergências editoriais esperadas {sorted(LC123_EDITORIAL)}, obtidas {sorted(editorial_found)}')
        if set(arts.get('marcadores_veto', {})) != set(LC123_VETO_MARKERS):
            gate_problems.append(f'{slug}: marcadores de veto 63-A..E não identificados em {exclusive_key}')
        known = KNOWN_DIVERGENCES.get(slug, {})
        if set(known) != set(LC123_NOTE_ARTICLES):
            gate_problems.append(f'{slug}: KNOWN_DIVERGENCES deve cobrir exatamente os arts. do aviso editorial')
        for art_no, rec in known.items():
            if not isinstance(rec, dict) or any(f not in rec for f in DIVERGENCIA_FIELDS):
                gate_problems.append(
                    f'{slug} art. {art_no}: divergência conhecida sem dispositivo/fontes/descricao/tratamento/natureza')
            elif rec.get('natureza') != 'juridica':
                gate_problems.append(f'{slug} art. {art_no}: natureza deve ser juridica')
        return gate_problems

    problems.extend(_gate_lc123(LC123_SLUG, 'camara-primary', 'principal'))
    problems.extend(_gate_lc123(LC123_PLANALTO_SLUG, 'planalto-primary', 'conferencia'))
    if problems:
        raise SystemExit('Conferência falhou:\n - ' + '\n - '.join(problems))
    # limpa auxiliares internos antes de serializar provas
    for proof in reconciliation.values():
        proof.pop('_article_splits', None)

    # --- efeitos diferidos (evidência literal revisada; [] nunca publica afirmação) ---
    lc238 = extract_required_effect_text(sources, 'lc238-art-10')
    lc227_revog = extract_required_effect_text(sources, 'lc227-art-181')
    lc227_efeitos = extract_required_effect_text(sources, 'lc227-art-182')
    lc198 = extract_required_effect_text(sources, 'lc198-art-3')
    lc198_vig = extract_required_effect_text(sources, 'lc198-art-4')
    pdf_blocks = pdf_to_blocks(sources['camara-14133-pdf'])
    note44a = next(re.sub(r'\s+', ' ', b) for b in pdf_blocks if b.startswith('Art. 44-A.'))
    lc238_marker = 'Lei Complementar nº 238, de 21/10/2026'
    lc227_marker = 'Lei Complementar nº 227, de 13/1/2026'
    lc123_arts = []
    lc123_arts_227 = []
    lc123_conv = converted['br-federal-lei-complementar-2006-12-14-123']
    arts, order = split_articles(main_body_blocks(lc123_conv['conv'].blocks))
    for k in order:
        plain_arts = [md_plain(b, True) for b in arts[k]]
        if any(lc238_marker in p for p in plain_arts):
            lc123_arts.append(k)
        if any(lc227_marker in p for p in plain_arts):
            lc123_arts_227.append(k)
    lc238_slug = 'br-federal-lei-complementar-2026-10-21-238'
    lc238_arquivo = 'federal/br-federal-lei-complementar-2026-10-21-238.md'
    lc227_slug = 'br-federal-lei-complementar-2026-01-13-227'
    lc227_arquivo = 'federal/br-federal-lei-complementar-2026-01-13-227.md'
    lc123_effect = dict(
        norma_modificadora='Lei Complementar nº 238, de 21 de outubro de 2026',
        norma_id_modificadora=lc238_slug,
        arquivo_norma_modificadora=lc238_arquivo,
        fonte_modificadora=SOURCES['planalto-lc238']['url'], sha256_fonte_modificadora=fontes['planalto-lc238']['sha256'],
        remissoes_na_edicao=[f'art. {k}' for k in lc123_arts],
        dispositivos_modificados=[
            dict(dispositivo='art. 18-A, §§ 1º e 2º', efeitos_a_partir_de='2028-01-01',
                 fundamento='art. 10, I, da LC 238 (literal da fonte)'),
            dict(dispositivo='art. 18-C', efeitos_a_partir_de='2027-01-01',
                 fundamento='art. 10, II, da LC 238 (demais dispositivos; literal da fonte)'),
            dict(dispositivo='art. 48', efeitos_a_partir_de='2027-01-01',
                 fundamento='art. 10, II, da LC 238 (demais dispositivos; literal da fonte)'),
            dict(dispositivo='art. 49', efeitos_a_partir_de='2027-01-01',
                 fundamento='art. 10, II, da LC 238 (demais dispositivos; literal da fonte)'),
        ],
        marcador_no_texto='(Vide Lei Complementar nº 238, de 21/10/2026)',
        texto_da_fonte_modificadora=lc238,
        leitura='Literal do art. 10 da LC 238: entra em vigor na publicação e produz efeitos a partir de 1º/1/2028 '
                '(alterações do art. 18-A, §§ 1º e 2º, da LC 123) e de 1º/1/2027 (demais dispositivos). '
                'A edição consultada da LC 123 não incorpora a redação da LC 238: apenas remete a ela. '
                f'O texto integral da modificadora está em `{lc238_arquivo}`.')
    # Remissões "Vide LC 238" também aparecem na edição Planalto; mesmo vínculo, outra identidade de edição.
    lc123_planalto_arts = []
    lc123_planalto_conv = converted[LC123_PLANALTO_SLUG]
    arts_p, order_p = split_articles(main_body_blocks(lc123_planalto_conv['conv'].blocks))
    for k in order_p:
        if any(lc238_marker in md_plain(b, True) for b in arts_p[k]):
            lc123_planalto_arts.append(k)
    lc123_planalto_effect = dict(lc123_effect, remissoes_na_edicao=[f'art. {k}' for k in lc123_planalto_arts])
    lc227_effect = dict(
                norma_modificadora='Lei Complementar nº 227, de 13 de janeiro de 2026',
                norma_id_modificadora=lc227_slug,
                arquivo_norma_modificadora=lc227_arquivo,
                fonte_modificadora=SOURCES['planalto-lc227']['url'],
                sha256_fonte_modificadora=fontes['planalto-lc227']['sha256'],
                fonte_nota_camara=SOURCES['camara-lc227']['url'],
                sha256_fonte_nota_camara=fontes['camara-lc227']['sha256'],
                remissoes_na_edicao=[f'art. {k}' for k in lc123_arts_227],
                dispositivos_relacionados=[
                    dict(
                        dispositivo='art. 87-B',
                        evento='revogacao',
                        norma_que_acrescentou='Lei Complementar nº 214, de 16/1/2025',
                        efeitos_da_inclusao_a_partir_de='2027-01-01',
                        fundamento_inclusao='nota literal da Câmara no art. 87-B da LC 123',
                        norma_que_revogou='Lei Complementar nº 227, de 13/1/2026',
                        fundamento_revogacao='art. 181, IV, "a", da LC 227 (literal da fonte)',
                        data_especifica_na_revogacao=None,
                        leitura=('A nota do art. 87-B na LC 123 (Câmara) registra acréscimo pela LC 214 com efeitos '
                                 'a partir de 1º/1/2027 e revogação pela LC 227. O art. 181, IV, "a", da LC 227 revoga '
                                 'o art. 87-B sem fixar 1º/1/2027 para essa revogação; as alíneas "c" e "d" do mesmo '
                                 'inciso trazem datas próprias (30/11/2026 e 1º/1/2033) para outros dispositivos. '
                                 'O acervo não atribui 2027 a toda revogação nem reconstrói a redação do 87-B.'),
                    ),
                    dict(
                        dispositivo='art. 41, § 4º, I e II',
                        evento='revogacao',
                        fundamento_revogacao='art. 181, IV, "b", da LC 227 (literal da fonte)',
                        data_especifica_na_revogacao=None,
                    ),
                    dict(
                        dispositivo='art. 31, § 4º',
                        evento='revogacao',
                        fundamento_revogacao='art. 181, IV, "c", da LC 227 (literal da fonte)',
                        data_especifica_na_revogacao='2026-11-30',
                    ),
                    dict(
                        dispositivo='art. 18, § 4º, VI',
                        evento='revogacao',
                        fundamento_revogacao='art. 181, IV, "d", da LC 227 (literal da fonte)',
                        data_especifica_na_revogacao='2033-01-01',
                    ),
                ],
                marcador_no_texto='(… e revogado pela Lei Complementar nº 227, de 13/1/2026)',
                texto_da_fonte_modificadora=lc227_revog + lc227_efeitos,
                leitura=('A LC 227 altera e revoga dispositivos da LC 123 e da LC 214. O art. 181 lista revogações '
                         'com datas próprias em algumas alíneas; o art. 182 produz efeitos a partir de 1º/1/2027 '
                         'só para dispositivos ali enumerados (art. 76, II, "c"; art. 169), a partir da eleição do '
                         'Presidente do CGIBS para os §§ 4º e 5º do art. 52, e a partir da publicação para os demais. '
                         'A edição consultada da LC 123 preserva a nota do art. 87-B sem incorporar redação '
                         f'suprimida. Texto integral em `{lc227_arquivo}`; publicação original da Câmara também '
                         'capturada (`camara-lc227`).'),
            )
    effects = {
        LC123_SLUG: [lc123_effect, lc227_effect],
        LC123_PLANALTO_SLUG: [lc123_planalto_effect],
        slug14: [
            dict(dispositivo='art. 44-A', norma_modificadora='Lei nº 15.210, de 2025',
                 texto_da_fonte=note44a[note44a.find('(“Caput”'):] if '(“Caput”' in note44a else note44a,
                 fonte=SOURCES['camara-14133-pdf']['url'], sha256_fonte=fontes['camara-14133-pdf']['sha256'],
                 leitura='Nota da Câmara transcrita sem cálculo de data de vigência.'),
            dict(dispositivo='art. 193, II', norma_modificadora='Lei Complementar nº 198, de 28 de junho de 2023',
                 fonte=SOURCES['planalto-lc198']['url'], sha256_fonte=fontes['planalto-lc198']['sha256'],
                 texto_da_fonte=lc198 + lc198_vig,
                 leitura='A LC 198 dá a redação do art. 193, II (revogação em 30 de dezembro de 2023) e entra em vigor na data de sua publicação.')],
    }

    # --- documentos ---
    for doc in DOCS:
        slug = doc['slug']
        rel = doc['arquivo']
        meta = dict(id=slug, esfera='federal', manifesto='metadados/nucleo-licitacoes.json', contrato_versao=CONTRACT_VERSION,
                    vigencia_certificada=False)
        entry = dict()
        if doc['modo'] == 'historica':
            pristine = read_baseline(rel)
            assert sha256(pristine.encode()) == HISTORIC_14133_SHA256, 'corpo histórico da Lei 14.133 foi alterado'
            title = pristine.splitlines()[0]
            meta.update(norma_id=slug, norma_tipo='lei', norma_numero='14133', norma_data='2021-04-01', titulo=title,
                        edicao_id=slug + '@historica-fonte-desconhecida', edicao_tipo='historica', edicao_integral=UNKNOWN,
                        edicao_relacionada='br-federal-lei-2021-04-01-14133-consolidada',
                        fonte_orgao=UNKNOWN, fonte_url=UNKNOWN, fonte_formato=UNKNOWN, capturado_em=UNKNOWN, sha256_fonte=UNKNOWN,
                        situacao='nao-informada', situacao_fundamento=UNKNOWN, texto_riscado=False,
                        anexos_no_corpo=0, tabelas=0, imagens_omitidas=0,
                        efeitos_diferidos='nao-aplicavel-sem-notas-na-edicao',
                        sha256_corpo_preservado=HISTORIC_14133_SHA256)
            body = note_block(HISTORIC_NOTE) + '\n\n' + pristine
            entry['proveniencia'] = ('Arquivo anterior ao contrato de metadados; fonte oficial, captura e conversão não registradas. '
                                     f'Corpo preservado byte a byte do commit {BASELINE_COMMIT}.')
        elif doc['modo'] == 'conferida':
            pristine = read_baseline(rel)
            assert sha256(pristine.encode()) == BASELINE_SHA256[rel], f'corpo de {rel} foi alterado'
            ckey = doc['fonte']  # captura atual do órgão da edição (Câmara); NÃO é a captura original
            conf_keys = doc.get('conferencia') or []
            camara_blocks, camara_conv = source_blocks(ckey, sources[ckey])
            old_blocks = preserved_blocks(pristine)
            measured = measure_preserved_structure(pristine)
            # Integridade do corpo preservado contra a captura atual da Câmara (mesma URL alegada;
            # hash/data desta captura NÃO se atribuem à procedência original desconhecida).
            art_camara, _, _ = article_proof(camara_blocks, old_blocks)
            cobertura = full_body_coverage(pristine, camara_blocks)
            titulos_camara = dict(
                iguais=headings(main_body_blocks(old_blocks)) == headings(main_body_blocks(camara_blocks)),
                preservado=len(headings(main_body_blocks(old_blocks))),
                captura_atual=len(headings(main_body_blocks(camara_blocks))))
            fora_artigos = dict(
                iguais=non_article_blocks(old_blocks) == non_article_blocks(camara_blocks),
                preservado=len(non_article_blocks(old_blocks)),
                captura_atual=len(non_article_blocks(camara_blocks)))
            if (art_camara['divergentes'] or art_camara['apenas_na_principal'] or art_camara['apenas_na_conferencia']
                    or not cobertura['equivalente'] or not titulos_camara['iguais'] or not fora_artigos['iguais']):
                raise SystemExit(
                    f'{slug}: corpo preservado divergiu da captura atual da Câmara '
                    f'(artigos/cobertura/títulos/blocos fora de artigos): artigos={art_camara} '
                    f'cobertura={cobertura} titulos={titulos_camara} fora_artigos={fora_artigos}')
            # Conferência independente (segunda fonte oficial), se houver.
            fontes_conf = []
            article_splits = {}
            for indep in conf_keys:
                if sources.get(indep) is None:
                    continue
                indep_blocks, _ = source_blocks(indep, sources[indep])
                art_indep, prim, sec = article_proof(old_blocks, indep_blocks)
                entry_conf = dict(
                    fonte=indep, url=SOURCES[indep]['url'], sha256=fontes[indep]['sha256'],
                    capturado_em=fontes[indep]['capturado_em'], artigos=art_indep,
                    titulos_e_capitulos=dict(
                        iguais=headings(main_body_blocks(old_blocks)) == headings(main_body_blocks(indep_blocks)),
                        principal=len(headings(main_body_blocks(old_blocks))),
                        conferencia=len(headings(main_body_blocks(indep_blocks)))))
                fontes_conf.append(entry_conf)
                article_splits[indep] = (prim, sec, art_indep, entry_conf)
            # Gate da conferência independente (Planalto) da Lei 13.303.
            if slug == L13303_SLUG:
                if 'planalto-13303' not in article_splits:
                    raise SystemExit(f'{slug}: captura do Planalto ausente para conferência independente')
                primary_13303, secondary_13303, art_pl, entry_pl = article_splits['planalto-13303']
                form_set = set(art_pl.get('divergencias_de_forma') or [])
                major = art_pl.get('divergencias_substanciais') or []
                expected_form = set(L13303_FORM_DIVERGENCES)
                if major:
                    raise SystemExit(f'{slug}: divergências substanciais com o Planalto: {major}')
                if form_set != expected_form:
                    raise SystemExit(
                        f'{slug}: divergências de forma com o Planalto divergem do revisado '
                        f'(esperadas {sorted(expected_form, key=lambda x: (len(x), x))}, '
                        f'obtidas {sorted(form_set, key=lambda x: (len(x), x))})')
                if art_pl['apenas_na_principal'] or art_pl['apenas_na_conferencia']:
                    raise SystemExit(
                        f'{slug}: artigos exclusivos entre corpo preservado e Planalto: '
                        f'{art_pl["apenas_na_principal"]} / {art_pl["apenas_na_conferencia"]}')
                if not entry_pl['titulos_e_capitulos']['iguais']:
                    raise SystemExit(f'{slug}: sequência de títulos/capítulos difere do Planalto')
                for article, spec in L13303_FORM_FINGERPRINTS.items():
                    mismatch = lock_reviewed_pair(article, spec, primary_13303, secondary_13303, slug)
                    if mismatch:
                        raise SystemExit('\n'.join(mismatch))
                art_pl['divergencias_explicadas'] = {
                    k: ('Diferença tipográfica/editorial de forma após normalização entre a edição '
                        'preservada da Câmara e a página do Planalto; a auditoria não encontrou '
                        'divergência de conteúdo. O texto publicado permanece o corpo preservado.')
                    for k in L13303_FORM_DIVERGENCES
                }
            proof = dict(
                documento=slug,
                # Procedência original desconhecida (corpo histórico) vs captura atual usada só para conferir.
                procedencia_original=dict(
                    descricao=('Corpo preservado byte a byte; captura original (data/hash) não registrada. '
                               'fonte_url aponta o órgão/URL alegados da edição, sem atribuir a captura atual.'),
                    fonte_url_alegada=SOURCES[ckey]['url'],
                    capturado_em=UNKNOWN,
                    sha256_fonte=UNKNOWN,
                    sha256_corpo_preservado=BASELINE_SHA256[rel]),
                captura_atual_para_conferir=dict(
                    descricao=('Captura contemporânea da Câmara usada para conferir o corpo preservado. '
                               'Não é a captura original; hash e data abaixo referem-se só a esta captura.'),
                    chave=ckey,
                    url=SOURCES[ckey]['url'],
                    sha256=fontes[ckey]['sha256'],
                    capturado_em=fontes[ckey]['capturado_em'],
                    snapshot=str(snapshot_path(ckey).relative_to(ROOT))),
                cobertura_texto=cobertura,
                titulos_e_capitulos=titulos_camara,
                blocos_fora_de_artigos=fora_artigos,
                estrutura_medida=measured,
                artigos_vs_captura_atual=art_camara,
                fontes_conferencia=fontes_conf,
            )
            reconciliation[slug] = proof
            norma = doc['norma']
            conf_urls = [SOURCES[k]['url'] for k in conf_keys] or 'nenhuma'
            # fonte_conferencia = segunda fonte oficial independente; nunca a mesma URL de fonte_url.
            if conf_urls != 'nenhuma' and SOURCES[ckey]['url'] in conf_urls:
                raise SystemExit(f'{slug}: fonte_conferencia não pode repetir a URL de fonte_url')
            meta.update(norma_id=slug, norma_tipo=norma['tipo'], norma_numero=norma['numero'], norma_data=norma['data'],
                        titulo=norma['titulo'], edicao_id=slug + '@consolidada-camara', edicao_tipo='consolidada',
                        edicao_integral=True, fonte_orgao=CAMARA, fonte_url=SOURCES[ckey]['url'], fonte_formato='html',
                        fonte_conferencia=conf_urls, capturado_em=UNKNOWN, sha256_fonte=UNKNOWN,
                        situacao='nao-informada', situacao_fundamento=UNKNOWN,
                        texto_riscado=measured['texto_riscado'],
                        anexos_no_corpo=measured['anexos_no_corpo'],
                        tabelas=measured['tabelas'],
                        imagens_omitidas=0,  # imagens embutidas permanecem no corpo preservado
                        efeitos_diferidos='preservados-nas-notas-do-texto',
                        sha256_corpo_preservado=BASELINE_SHA256[rel])
            body = pristine
            entry['proveniencia'] = (
                'Corpo preservado byte a byte do commit auditado; a data e o hash da captura original não foram '
                'registrados (capturado_em/sha256_fonte = desconhecido). A captura atual da Câmara usada para '
                f'conferir o corpo está em `{proof_name(slug)}` (campo captura_atual_para_conferir), com hash e '
                'data próprios — não atribuídos retroativamente à procedência original. '
                + ('Conferência independente com o Planalto no mesmo arquivo de provas.'
                   if conf_keys else 'Nenhuma segunda fonte oficial independente foi obtida.'))
            entry['estrutura_medida'] = measured
            entry['blocos_nao_textuais'] = [dict(
                tipo='imagem-embutida', quantidade=measured['imagens_embutidas'],
                tratamento='mantida no corpo preservado (brasão/logotipo institucional)')]
            entry['fontes'] = dict(
                captura_atual_camara=dict(chave=ckey, **public_source(fontes[ckey], ckey)),
                conferencia=[dict(chave=k, **public_source(fontes[k], k)) for k in conf_keys
                             if sources.get(k) is not None])
            entry['divergencias_conhecidas'] = {}
        else:
            item = converted[slug]
            rec = item['rec']
            conv = item['conv']
            norma = doc['norma']
            anexos = sum(1 for b in conv.blocks if re.match(r'^ANEXO\b', md_plain(b, True).strip(), re.I))
            situ = doc['situacao']
            extra = []
            if doc['conferencia']:
                extra.append('Conferida artigo a artigo com ' + '; '.join(SOURCES[k]['url'] for k in doc['conferencia']) +
                             f' (ver `{proof_name(slug)}`).')
            if conv.stats['trechos_riscados']:
                extra.append('Texto entre `~~` é redação superada, vetada ou revogada que a fonte oficial mantém riscada; '
                             'não é dispositivo em vigor. As notas de alteração, remissões e indicações de vigência/produção '
                             'de efeitos da fonte foram preservadas.')
            if slug == slug14:
                extra.append('Edição histórica preservada separadamente em `../br-federal-lei-2021-04-01-14133.md`.')
            if situ['valor'] == 'revogada':
                if slug == 'br-federal-lei-1993-06-21-8666':
                    extra.append(
                        'A fonte apresenta esta lei como revogada pela Lei nº 14.133/2021: arts. 89 a 108 na publicação '
                        '(art. 193, I) e a lei integral em 30/12/2023 (art. 193, II, a, redação da LC 198/2023). '
                        'Mantida para consulta histórica e para as hipóteses de transição previstas na Lei 14.133; '
                        'o acervo não aplica essas datas a contratos concretos nem as toma como fundamento atual por padrão. '
                        'A cronologia estruturada está em `eventos_revogacao` do manifesto.')
                else:
                    extra.append('A fonte apresenta esta lei como revogada pela Lei nº 14.133/2021; ela é mantida para consulta histórica '
                                 'e para as hipóteses de transição previstas na Lei 14.133, não como fundamento atual por padrão.')
            if slug == LC123_SLUG:
                extra.append('A edição consultada remete à Lei Complementar nº 238, de 21/10/2026 ("Vide"), sem incorporar a redação '
                             'dessa lei: segundo seu art. 10, ela produz efeitos a partir de 1º/1/2028 (art. 18-A, §§ 1º e 2º) e de '
                             '1º/1/2027 (demais dispositivos). O texto integral da modificadora está em '
                             f'[`{lc238_arquivo}`]({lc238_arquivo.split("/", 1)[-1]}); o vínculo por dispositivo está em '
                             '`metadados/nucleo-licitacoes.json`.')
                extra.append('O art. 87-B traz a nota literal da Câmara: acrescido pela LC 214/2025, produzindo efeitos a '
                             'partir de 1º/1/2027, e revogado pela LC 227/2026. A data 1º/1/2027 na nota refere-se aos efeitos '
                             'da inclusão pela LC 214; a revogação pelo art. 181, IV, "a", da LC 227 não atribui essa data ao '
                             'evento de revogação (outras alíneas do mesmo inciso têm datas próprias). O texto integral da '
                             f'LC 227 está em [`{lc227_arquivo}`]({lc227_arquivo.split("/", 1)[-1]}); a publicação original '
                             f'da Câmara (fundamento da nota) está capturada em `provas/nucleo-licitacoes/fontes/` '
                             f'(`camara-lc227`). O acervo não reconstrói a redação do art. 87-B.')
                extra.append('Divergências conhecidas entre as fontes oficiais: o art. 47, caput, na edição da Câmara '
                             'tem a redação anterior à LC 147/2014, enquanto o Planalto a apresenta com a nova redação; o art. 87-B '
                             '(nota LC 214/LC 227 acima) consta da Câmara e não aparece na página do Planalto conferida. Confira a fonte antes de usar '
                             'esses dispositivos (ver o arquivo de provas desta conferência).')
                extra.append('A edição integral do Planalto da mesma norma está em '
                             f'[`{LC123_PLANALTO_ARQUIVO}`](edicoes/{LC123_PLANALTO_SLUG}.md). '
                             'São duas identidades de edição (`edicao_id` distintos, mesmo `norma_id`); o consumidor escolhe a fonte '
                             'sem presumir vigência. As redações não foram combinadas.')
            if slug == LC123_PLANALTO_SLUG:
                extra.append('Edição alternativa da LC 123 a partir da página oficial do Planalto. A edição da Câmara permanece em '
                             f'[`federal/{LC123_SLUG}.md`](../{LC123_SLUG}.md). Mesmo `norma_id`, `edicao_id` distinto; esta pasta '
                             '(`federal/edicoes/`) não incrementa a contagem de normas do README.')
                extra.append('A edição remete à Lei Complementar nº 238, de 21/10/2026 ("Vide"), sem incorporar a redação dessa lei: '
                             'segundo seu art. 10, ela produz efeitos a partir de 1º/1/2028 (art. 18-A, §§ 1º e 2º) e de 1º/1/2027 '
                             '(demais dispositivos). O texto integral da modificadora está em '
                             f'[`{lc238_arquivo}`](../{lc238_arquivo.split("/", 1)[-1]}).')
                extra.append('Divergências conhecidas entre as fontes oficiais (as mesmas da edição da Câmara, por dispositivo): '
                             'o art. 47, caput, nesta edição do Planalto traz a redação da LC 147/2014 e conserva riscada a anterior; '
                             'a Câmara mantém a redação anterior à LC 147/2014. O art. 87-B (LC 214/2025) consta da Câmara e não '
                             'aparece nesta página do Planalto. Confira a fonte antes de usar esses dispositivos '
                             '(ver o arquivo de provas desta conferência). Nenhuma redação foi eleita silenciosamente.')
            if slug == lc238_slug:
                extra.append('Esta lei altera a Lei Complementar nº 123/2006. A edição consultada da LC 123 no acervo '
                             '(`br-federal-lei-complementar-2006-12-14-123.md`) apenas remete a esta norma ("Vide") e '
                             'não incorpora as redações futuras. O art. 10 desta lei, em literal da fonte, produz efeitos '
                             'a partir de 1º/1/2028 quanto às alterações do art. 18-A, §§ 1º e 2º, da LC 123, e a partir '
                             'de 1º/1/2027 quanto aos demais dispositivos; o acervo não antecipa essa aplicação.')
                extra.append('Uma só fonte oficial (Planalto). A conferência é de cobertura do texto integral, não contra '
                             'segunda fonte.')
            if slug == lc227_slug:
                extra.append('Esta lei altera e revoga dispositivos da LC 123/2006 e da LC 214/2025, entre outras. A edição '
                             'consultada da LC 123 no acervo preserva a nota do art. 87-B (acréscimo pela LC 214 com efeitos '
                             'a partir de 1º/1/2027; revogação pela LC 227) sem reconstruir a redação do dispositivo. O '
                             'art. 181, IV, lista as revogações na LC 123 com datas próprias nas alíneas "c" (30/11/2026) e '
                             '"d" (1º/1/2033); a alínea "a" (art. 87-B) não traz data específica de revogação. O art. 182 '
                             'produz efeitos a partir de 1º/1/2027 só para os dispositivos ali enumerados, a partir da '
                             'eleição do Presidente do CGIBS para os §§ 4º e 5º do art. 52, e a partir da publicação para '
                             'os demais; o acervo não atribui 2027 a toda revogação.')
                extra.append('Markdown a partir do Planalto (estrutura utilizável para cobertura integral). A publicação '
                             f'original da Câmara ({SOURCES["camara-lc227"]["url"]}) também foi capturada como evidência '
                             'da procedência da nota do art. 87-B; o HTML dessa página não segmenta artigos em blocos '
                             'adequados à conferência artigo a artigo.')
            note = edition_note(doc, rec, extra)
            body = item['head'] + '\n\n' + note + '\n\n' + item['rest']
            meta.update(norma_id=meta_norma_id(slug),
                        norma_tipo=norma['tipo'], norma_numero=norma['numero'], norma_data=norma['data'],
                        titulo=item['title'].replace('\\', ''),
                        edicao_id=meta_norma_id(slug) + '@consolidada-' + ('planalto' if 'planalto' in doc['fonte'] else 'camara'),
                        edicao_tipo=doc['edicao']['tipo'], edicao_integral=True,
                        fonte_orgao=SOURCES[doc['fonte']]['orgao'], fonte_url=SOURCES[doc['fonte']]['url'],
                        fonte_formato=SOURCES[doc['fonte']]['formato'],
                        fonte_conferencia=[SOURCES[k]['url'] for k in doc['conferencia']] or 'nenhuma',
                        capturado_em=rec['capturado_em'], sha256_fonte=rec['sha256'],
                        situacao=situ['valor'], situacao_fundamento=situ.get('fundamento', UNKNOWN),
                        texto_riscado=conv.stats['trechos_riscados'] > 0, anexos_no_corpo=anexos,
                        tabelas=conv.stats['tabelas_markdown'] + conv.stats['tabelas_html'],
                        imagens_omitidas=len(conv.images),
                        efeitos_diferidos='preservados-nas-notas-do-texto')
            if slug == slug14:
                meta['edicao_relacionada'] = 'br-federal-lei-2021-04-01-14133'
            if slug == LC123_SLUG:
                meta['edicao_relacionada'] = LC123_PLANALTO_SLUG
            if slug == LC123_PLANALTO_SLUG:
                meta['edicao_relacionada'] = LC123_SLUG
            if slug == lc238_slug:
                meta['edicao_relacionada'] = 'nenhuma'
            if slug == lc227_slug:
                meta['edicao_relacionada'] = 'nenhuma'
            entry['conversao'] = reconciliation[slug]['conversao']
            entry['blocos_nao_textuais'] = [dict(tipo='imagem', **img) for img in conv.images] + \
                [dict(tipo='tabela', **t) for t in conv.tables]
            entry['fontes'] = dict(principal=dict(chave=doc['fonte'], **public_source(fontes[doc['fonte']], doc['fonte'])),
                                   conferencia=[dict(chave=k, **public_source(fontes[k], k)) for k in doc['conferencia']
                                                if sources.get(k) is not None])
            if slug == lc227_slug:
                entry['fontes']['evidencia_nota_camara'] = dict(
                    chave='camara-lc227', **public_source(fontes['camara-lc227'], 'camara-lc227'))
            if slug in effects:
                entry['efeitos_diferidos_detalhe'] = effects[slug]
            if slug == lc238_slug:
                entry['efeitos_diferidos_detalhe'] = [dict(
                    dispositivo='art. 10',
                    texto_da_fonte=lc238,
                    leitura=('Literal do art. 10: entra em vigor na publicação; produz efeitos a partir de 1º/1/2028 '
                             '(alterações do art. 18-A, §§ 1º e 2º, da LC 123) e de 1º/1/2027 (demais dispositivos). '
                             'O acervo não antecipa a aplicação dessas redações.'),
                    altera_norma=dict(
                        norma_id='br-federal-lei-complementar-2006-12-14-123',
                        arquivo='federal/br-federal-lei-complementar-2006-12-14-123.md',
                        dispositivos=[f'art. {k}' for k in lc123_arts],
                        dispositivos_modificados=[
                            dict(dispositivo='art. 18-A, §§ 1º e 2º', efeitos_a_partir_de='2028-01-01',
                                 fundamento='art. 10, I (literal da fonte)'),
                            dict(dispositivo='demais dispositivos alterados nesta lei (arts. 18-C, 48 e 49, entre outros)',
                                 efeitos_a_partir_de='2027-01-01', fundamento='art. 10, II (literal da fonte)'),
                        ],
                    ),
                )]
            if slug == lc227_slug:
                entry['efeitos_diferidos_detalhe'] = [
                    dict(
                        dispositivo='art. 181',
                        texto_da_fonte=lc227_revog,
                        leitura=('Literal do art. 181: lista revogações. Na LC 123 (inciso IV), a alínea "a" revoga o '
                                 'art. 87-B sem data específica neste artigo; a alínea "c" revoga o § 4º do art. 31 em '
                                 '30/11/2026; a alínea "d" revoga o inciso VI do § 4º do art. 18 em 1º/1/2033. O acervo '
                                 'não atribui 2027 a toda revogação.'),
                        altera_norma=dict(
                            norma_id='br-federal-lei-complementar-2006-12-14-123',
                            arquivo='federal/br-federal-lei-complementar-2006-12-14-123.md',
                            dispositivos=[f'art. {k}' for k in lc123_arts_227 if k == '87-B'] or ['art. 87-B'],
                            dispositivos_relacionados=[
                                dict(dispositivo='art. 87-B', evento='revogacao',
                                     data_especifica_na_revogacao=None,
                                     fundamento='art. 181, IV, "a" (literal da fonte)'),
                                dict(dispositivo='art. 41, § 4º, I e II', evento='revogacao',
                                     data_especifica_na_revogacao=None,
                                     fundamento='art. 181, IV, "b" (literal da fonte)'),
                                dict(dispositivo='art. 31, § 4º', evento='revogacao',
                                     data_especifica_na_revogacao='2026-11-30',
                                     fundamento='art. 181, IV, "c" (literal da fonte)'),
                                dict(dispositivo='art. 18, § 4º, VI', evento='revogacao',
                                     data_especifica_na_revogacao='2033-01-01',
                                     fundamento='art. 181, IV, "d" (literal da fonte)'),
                            ],
                        ),
                    ),
                    dict(
                        dispositivo='art. 182',
                        texto_da_fonte=lc227_efeitos,
                        leitura=('Literal do art. 182: entra em vigor na publicação; produz efeitos a partir de '
                                 '1º/1/2027 apenas para a alínea "c" do inciso II do art. 76 e para o art. 169; a '
                                 'partir da eleição do Presidente do CGIBS para os §§ 4º e 5º do art. 52; e a partir '
                                 'da publicação para os demais dispositivos.'),
                    ),
                ]
            if doc['situacao']['valor'] == 'revogada':
                entry['revogacao'] = {k: v for k, v in doc['situacao'].items() if k != 'valor'}
                if slug == 'br-federal-lei-1993-06-21-8666':
                    entry['eventos_revogacao'] = eventos_revogacao_8666(
                        fontes, sources, lc198 + lc198_vig)
            entry['divergencias_conhecidas'] = KNOWN_DIVERGENCES.get(slug, {})
        text_body = body
        meta['sha256_markdown'] = sha256(text_body.encode('utf-8'))
        meta = {k: meta[k] for k in FRONTMATTER_KEYS if k in meta}
        errors = validate_meta(meta, slug)
        if errors:
            raise SystemExit('\n'.join(errors))
        docs_out[rel] = render_frontmatter(meta) + text_body
        manifest_docs.append(dict(arquivo=rel, **meta, **entry,
                                  provas=[proof_name(slug)] if slug in reconciliation else []))

    # --- provas ---
    for slug, proof in reconciliation.items():
        proofs[proof_name(slug)] = proof
    hist_blocks = [b for b in re.split(r'\n\s*\n', read_baseline(HISTORIC_14133)) if b.strip()]
    cons_blocks = converted[slug14]['conv'].blocks
    cmp, _, _ = article_proof(cons_blocks, hist_blocks)
    proofs['historica-vs-consolidada-14133.json'] = dict(
        descricao='Artigos da edição consolidada (Planalto, texto em vigor segundo a fonte, sem riscados e sem notas) '
                  'contra a edição histórica preservada.',
        historica=HISTORIC_14133, historica_sha256=HISTORIC_14133_SHA256,
        consolidada=repo_rel[slug14], sha256_fonte_consolidada=fontes['planalto-14133']['sha256'],
        artigos_apenas_na_consolidada=cmp['apenas_na_principal'], artigos_apenas_na_historica=cmp['apenas_na_conferencia'],
        artigos_identicos=cmp['identicos'], artigos_alterados=[d['artigo'] for d in cmp['divergentes']],
        detalhe_alterados=cmp['divergentes'])
    if baseline_texts is not None:
        old = baseline_texts['lc123']
        old_blocks = [b for b in re.split(r'\n\s*\n', old) if b.strip() and not b.startswith('![](data:')]
        new_blocks = converted['br-federal-lei-complementar-2006-12-14-123']['conv'].blocks
        cmp, _, _ = article_proof(new_blocks, old_blocks)
        old_arts, _ = split_articles(main_body_blocks(old_blocks))
        new_with = lc123_arts
        old_with = [k for k, bs in old_arts.items() if any(lc238_marker in md_plain(b, True) for b in bs)]
        proofs[LC123_PROOF_NAME] = dict(
            descricao='Edição anterior auditada (baseline versionado, autenticado por SHA-256 e commit de procedência; '
                      'não é fonte de captura) contra a edição atual da Câmara capturada nesta entrega. '
                      'A comparação não depende da quantidade de normas do núcleo.',
            anterior_sha256=BASELINE_SHA256[LC123_PATH],
            baseline_arquivo=LC123_BASELINE_REL,
            baseline_commit=BASELINE_COMMIT,
            baseline_papel=LC123_BASELINE_PAPEL,
            artigos_identicos_no_texto=cmp['identicos'], artigos_com_texto_diferente=[d['artigo'] for d in cmp['divergentes']],
            artigos_apenas_na_nova=cmp['apenas_na_principal'], artigos_apenas_na_anterior=cmp['apenas_na_conferencia'],
            artigos_com_remissao_lc238_antes=old_with, artigos_com_remissao_lc238_agora=new_with,
            detalhe_diferentes=cmp['divergentes'])
    proofs['fontes.json'] = {k: public_source(v, k) for k, v in fontes.items()}
    manifest = dict(contrato_versao=CONTRACT_VERSION, gerado_por='scripts/nucleo_licitacoes.py',
                    nota='O acervo não certifica vigência. Valores "desconhecido" indicam informação não registrada.',
                    baseline_commit=BASELINE_COMMIT, documentos=manifest_docs)
    return docs_out, proofs, manifest


def meta_norma_id(slug):
    for suffix in ('-consolidada', '-planalto'):
        if slug.endswith(suffix):
            return slug[:-len(suffix)]
    return slug


def proof_name(slug):
    return f'reconciliacao-{slug}.json'


def public_source(rec, key):
    out = dict(orgao=SOURCES[key]['orgao'], formato=SOURCES[key]['formato'])
    out.update({k: v for k, v in rec.items() if k not in ('curl_exit',)})
    if rec.get('utilizavel'):
        out['snapshot'] = str(snapshot_path(key).relative_to(ROOT))
        out['sha256_snapshot_armazenado'] = sha256(snapshot_path(key).read_bytes()) if snapshot_path(key).exists() else None
    return out


def source_text_chars_from_html(data, charset):
    soup = BeautifulSoup(decode(data, charset), 'lxml')
    for tag in soup(list(SKIP_TAGS)):
        tag.decompose()
    return soup.get_text(' ')


# --------------------------------------------------------------------------
# build / verify / CLI
# --------------------------------------------------------------------------


def load_lc123_baseline():
    """Texto anterior auditado da LC 123, conferido por hash e procedência.

    O arquivo vive no repositório. Não consulta o Git: um checkout raso, sem o
    commit auditado, continua podendo reconciliar. Não é snapshot de captura.
    Devolve (texto ou None, erros).
    """
    path = ROOT / LC123_BASELINE_REL
    meta_path = ROOT / LC123_BASELINE_META_REL
    expected = BASELINE_SHA256[LC123_PATH]
    if not path.is_file() or not meta_path.is_file():
        return None, ['baseline da LC 123 ausente (texto auditado ou procedência)']
    try:
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return None, ['baseline da LC 123: procedência ilegível']
    if not isinstance(meta, dict):
        return None, ['baseline da LC 123: procedência ilegível']
    text = path.read_text(encoding='utf-8')
    digest = sha256(text.encode('utf-8'))
    errors = []
    if digest != expected or meta.get('sha256') != expected:
        errors.append('baseline da LC 123: hash não confere com a procedência auditada')
    if meta.get('commit') != BASELINE_COMMIT or meta.get('caminho_no_commit') != LC123_PATH:
        errors.append('baseline da LC 123: procedência (commit ou caminho) diverge')
    if meta.get('papel') != LC123_BASELINE_PAPEL or meta.get('nao_e_fonte_de_captura') is not True:
        errors.append('baseline da LC 123: papel não distingue o texto auditado da fonte de captura')
    if meta.get('arquivo') != LC123_BASELINE_REL:
        errors.append('baseline da LC 123: caminho do arquivo de baseline diverge')
    if errors:
        return None, errors
    return text, []


def proof_field_errors(name, published, expected):
    """Compara cada campo. Não exige quantidade fixa de artigos ou de normas."""
    if not isinstance(published, dict) or not isinstance(expected, dict):
        return [f'provas/{name}: formato inválido']
    errors = []
    for key in sorted(set(published) | set(expected)):
        if key not in published or key not in expected or published[key] != expected[key]:
            errors.append(f'provas/{name}: campo {key} diverge do recálculo')
    return errors


def tool_versions():
    import bs4
    import lxml.etree as etree
    poppler = subprocess.run(['pdftotext', '-v'], capture_output=True, text=True)
    first = (poppler.stderr or poppler.stdout).splitlines()[0] if (poppler.stderr or poppler.stdout) else UNKNOWN
    return dict(python=sys.version.split()[0], beautifulsoup4=bs4.__version__,
                lxml='.'.join(map(str, etree.LXML_VERSION)), libxml2='.'.join(map(str, etree.LIBXML_VERSION)),
                pdftotext=first)


def write_outputs(docs, proofs, manifest):
    for rel, text in docs.items():
        (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / rel).write_text(text, encoding='utf-8')
    for name, proof in proofs.items():
        write_json(PROVAS / name, proof)
    write_json(MANIFESTO, manifest)
    write_json(PROVAS / 'ferramentas.json', dict(
        nota='Versões usadas na geração. A conversão é determinística para estas versões; outras versões do '
             'analisador HTML (libxml2) ou do pdftotext podem alterar o resultado byte a byte.', **tool_versions()))


def build(dest):
    dest = Path(dest)
    fetched = json.loads((dest / 'fetch.json').read_text())
    sources = {}
    for key, spec in SOURCES.items():
        rec = fetched[key]
        if rec.get('utilizavel'):
            data = (dest / spec['file']).read_bytes()
            if sha256(data) != rec['sha256']:
                raise SystemExit(f'{key}: arquivo capturado não confere com fetch.json')
            write_snapshot(key, data)
            rec['sha256_conteudo'] = content_sha256(data)
            sources[key] = data
        elif spec.get('opcional'):
            sources[key] = None
        else:
            raise SystemExit(f'{key}: fonte indispensável não obtida: {rec.get("motivo")}')
    lc123_old, baseline_errors = load_lc123_baseline()
    if baseline_errors:
        raise SystemExit('\n'.join(baseline_errors))
    docs, proofs, manifest = compute(sources, fetched, {'lc123': lc123_old})
    write_outputs(docs, proofs, manifest)
    print(f'{len(docs)} documentos, {len(proofs)} provas, manifesto em {MANIFESTO.relative_to(ROOT)}')


def verify():
    errors = []
    fontes = json.loads((PROVAS / 'fontes.json').read_text())
    sources = {}
    for key, spec in SOURCES.items():
        rec = fontes[key]
        if not rec.get('utilizavel'):
            sources[key] = None
            if not spec.get('opcional'):
                errors.append(f'{key}: fonte indispensável marcada como não utilizável')
            continue
        data = read_snapshot(key)
        if sha256(data) != rec['sha256']:
            errors.append(f'{key}: snapshot não confere com o SHA-256 registrado')
        if content_sha256(data) != rec.get('sha256_conteudo'):
            errors.append(f'{key}: SHA-256 do conteúdo (sem script de proteção) não confere')
        if sha256(snapshot_path(key).read_bytes()) != rec['sha256_snapshot_armazenado']:
            errors.append(f'{key}: arquivo de snapshot armazenado diverge do registrado')
        sources[key] = data
    if errors:
        return errors
    baseline, baseline_errors = load_lc123_baseline()
    errors.extend(baseline_errors)
    if baseline is None:
        errors.append(f'provas/{LC123_PROOF_NAME}: recálculo integral não executado sem baseline íntegro')
        return errors
    docs, proofs, manifest = compute(sources, fontes, {'lc123': baseline})
    for rel, expected in docs.items():
        actual = (ROOT / rel).read_text(encoding='utf-8')
        if actual != expected:
            errors.append(f'{rel}: diverge da conversão reprodutível dos snapshots')
        meta, body = parse_frontmatter(actual)
        errors += validate_meta(meta, rel)
        if sha256(body.encode('utf-8')) != meta['sha256_markdown']:
            errors.append(f'{rel}: sha256_markdown não confere com o corpo')
    for name, expected in proofs.items():
        path = PROVAS / name
        if name == LC123_PROOF_NAME:
            if not path.exists():
                errors.append(f'provas/{name} ausente')
            else:
                try:
                    published = json.loads(path.read_text(encoding='utf-8'))
                except json.JSONDecodeError:
                    errors.append(f'provas/{name}: formato inválido')
                    continue
                errors.extend(proof_field_errors(name, published, json.loads(json.dumps(expected, ensure_ascii=False))))
            continue
        if not path.exists() or json.loads(path.read_text()) != json.loads(json.dumps(expected, ensure_ascii=False)):
            errors.append(f'provas/{name}: ausente ou diverge do recálculo')
    stored = json.loads(MANIFESTO.read_text())
    if stored != json.loads(json.dumps(manifest, ensure_ascii=False)):
        errors.append('metadados/nucleo-licitacoes.json diverge do recálculo')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('fetch').add_argument('dest')
    sub.add_parser('build').add_argument('dest')
    sub.add_parser('verify')
    args = parser.parse_args(argv)
    if args.command == 'fetch':
        fetch(args.dest)
    elif args.command == 'build':
        build(args.dest)
    else:
        errors = verify()
        for error in errors:
            print('ERRO:', error)
        if errors:
            recorded = PROVAS / 'ferramentas.json'
            if recorded.exists():
                print('Versões na geração:', json.dumps(json.loads(recorded.read_text()), ensure_ascii=False))
                print('Versões atuais:    ', json.dumps(tool_versions(), ensure_ascii=False))
            raise SystemExit(1)
        print('núcleo de licitações: documentos, provas e manifesto conferem')


if __name__ == '__main__':
    main()
