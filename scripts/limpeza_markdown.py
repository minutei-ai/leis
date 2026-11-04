#!/usr/bin/env python3
"""Limpeza de marcadores internos, HTML de apresentação, imagens base64 e chrome de portal.

Issues: #87 (marcadores + HTML), #98 (data:image), #100 (cabeçalhos/rodapés de portal).

Regras:
- Marcadores `###ESPÉCIE-…@@@` saem do Markdown e vão para metadados/limpeza-markdown/.
- HTML de apresentação (strong/em/br/font/span/p/…) vira Markdown; tabelas com
  rowspan/colspan permanecem como <table> simples (CONTRATO.md).
- Imagens data:URI vão para assets/md-inline/{sha256}.{ext} com referência relativa,
  ou são omitidas quando decorativas (brasão/logo de cabeçalho).
- Linhas de portal conhecidas são removidas; proveniência útil fica nos metadados.
- Corpos históricos com SHA travado (núcleo/LGPD) entram na allowlist documentada.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOTS = ('federal', 'estaduais', 'municipais')
META_DIR = ROOT / 'metadados' / 'limpeza-markdown'
ASSETS_DIR = ROOT / 'assets' / 'md-inline'
PROVAS_DIR = ROOT / 'provas' / 'limpeza-markdown'

# Inclui sufixos de republicação/retificação (@@@RET01+++, @@@+++, etc.).
# Pode aparecer após número de página isolado no topo do arquivo.
MARKER_LINE_RE = re.compile(r'^###[A-Z]+-[0-9][^\n]*@@@[^\n]*$', re.M)
MARKER_BLOCK_RE = re.compile(
    r'(?:^\d{1,4}\s*\n+)?^(###[A-Z]+-[0-9][^\n]*@@@[^\n]*)\s*\n*',
    re.M,
)

# data:image markdown image
IMG_RE = re.compile(
    r'!\[([^\]]*)\]\(\s*(data:image\/([a-zA-Z0-9.+-]+);base64,([^)]+))\s*\)',
    re.I,
)

# Portal families (#100). Prefer block forms; never strip "CÂMARA DOS DEPUTADOS" isolado
# dentro de dispositivo legal (ex.: "AS MESAS DA CÂMARA DOS DEPUTADOS E DO SENADO").
PORTAL_CAMARA_RE = re.compile(
    r'(?:(?:#{1,6}\s*)?(?:\*\*|__)?CÂMARA DOS DEPUTADOS(?:\*\*|__)?)\s*'
    r'(?:(?:<br\s*/?>)|\n)+\s*'
    r'(?:(?:#{1,6}\s*)?(?:\*\*|__)?Centro de Documentação e Informação(?:\*\*|__)?)'
    r'\s*(?:(?:<br\s*/?>)|\n)+',
    re.I,
)
PORTAL_ALESP_RE = re.compile(
    r'^\[Assembleia Legislativa do Estado de São Paulo\]\([^)]*\)\s*'
    r'\[Ficha informativa\]\([^)]*\)\s*\n+',
    re.M,
)
# Separador ALMG pode misturar '=' e '-'; a data OCR às vezes vem truncada/errada.
PORTAL_MG_RE = re.compile(
    r'(?:\n|^)\\?[=-]{3,}[^\n]*\n+Data da última atualização:[^\n]*\s*$',
    re.M,
)
PORTAL_SP_CITY_RE = re.compile(
    r'\n*Este texto não substitui o original publicado no Diário Oficial da Cidade de São Paulo\s*$',
)
PORTAL_DO_RE = re.compile(
    r'(?:<[^>]+>\s*)*(?:\*|_|~~|<em>|<i>){0,4}\s*'
    r'Este texto não substitui o publicado\s+(?:n[oa]|d[oe])\s+D\.?\s*O\.?\s*U?\.?'
    r'(?:[^<\n*]{0,120})?'
    r'(?:\*|_|~~|</em>|</i>){0,4}\s*(?:</[^>]+>\s*)*',
    re.I,
)

# Presentation HTML (not structural table/sup/sub with legal meaning beyond ordinals)
PRESENTATION_TAG_RE = re.compile(
    r'</?(?:strong|b|em|i|u|font|span|p|br|div|center|h[1-6]|strike|del|s)\b[^>]*>',
    re.I,
)
STRUCTURAL_TABLE_RE = re.compile(r'<table\b[^>]*>.*?</table>', re.I | re.S)
ROWSPAN_COLSPAN_RE = re.compile(r'\b(?:rowspan|colspan)\s*=', re.I)

SUP_ORDINAL_RE = re.compile(
    r'<u>\s*<sup>\s*([oaOAºª])\s*</sup>\s*</u>|<sup>\s*([oaOAºª])\s*</sup>',
    re.I,
)

# Frontmatter split
FRONTMATTER_RE = re.compile(r'\A---\n(.*?)\n---\n?', re.S)

# Allowlists vazias: geradores (núcleo/LGPD/benefícios-MDP) omitem brasão e chrome CEDI
# na conversão; corpos com sha256_corpo_preservado foram limpos com proveniência em
# metadados/limpeza-markdown/ e hashes regenerados (texto jurídico intacto).
ALLOWLIST_DATA_IMAGE: set[str] = set()
ALLOWLIST_PORTAL_CAMARA: set[str] = set()

MIME_EXT = {
    'png': 'png',
    'jpeg': 'jpg',
    'jpg': 'jpg',
    'gif': 'gif',
    'webp': 'webp',
    'svg+xml': 'svg',
    'x-icon': 'ico',
}


@dataclass
class FileResult:
    path: str
    changed: bool = False
    marker: str | None = None
    images_extracted: list[dict] = field(default_factory=list)
    images_omitted: list[dict] = field(default_factory=list)
    portals_removed: list[str] = field(default_factory=list)
    html_converted: bool = False
    skipped_reason: str | None = None
    error: str | None = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def split_frontmatter(text: str) -> tuple[str | None, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(0), text[m.end():]


def rel_asset_path(md_path: Path, asset_name: str) -> str:
    """Relative path from the markdown file to assets/md-inline/name."""
    asset = ASSETS_DIR / asset_name
    return Path(os_relpath(asset, md_path.parent)).as_posix()


def os_relpath(target: Path, start: Path) -> Path:
    return Path(target).resolve().relative_to(ROOT.resolve()) if False else Path(
        __import__('os').path.relpath(str(target), str(start))
    )


def is_decorative_header_image(body: str, match_start: int, raw_len: int, alt: str) -> bool:
    """Brasão/logo de cabeçalho, antes da epígrafe normativa.

    Notas editoriais (`<!-- nota-edicao -->`) e chrome de portal antes da imagem
    não contam como conteúdo jurídico precedente.
    """
    alt_l = (alt or '').lower()
    if any(k in alt_l for k in ('brasão', 'brasao', 'logo', 'armas', 'selo')):
        return True
    prefix = body[:match_start]
    prefix_stripped = re.sub(
        r'<!--\s*nota-edicao:inicio\s*-->.*?<!--\s*nota-edicao:fim\s*-->',
        '',
        prefix,
        flags=re.I | re.S,
    )
    prefix_stripped = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', prefix_stripped)
    prefix_stripped = re.sub(r'<br\s*/?>', '', prefix_stripped, flags=re.I)
    prefix_stripped = re.sub(
        r'(?:(?:#{1,6}\s*)?(?:\*\*|__)?CÂMARA DOS DEPUTADOS(?:\*\*|__)?)\s*',
        '',
        prefix_stripped,
        flags=re.I,
    )
    prefix_stripped = re.sub(
        r'(?:(?:#{1,6}\s*)?(?:\*\*|__)?Centro de Documentação e Informação(?:\*\*|__)?)',
        '',
        prefix_stripped,
        flags=re.I,
    )
    if prefix_stripped.strip():
        # Ainda é cabeçalho se a imagem vem antes da epígrafe (LEI/DECRETO/…)
        after = body[match_start:match_start + 4000]
        after_plain = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', after)
        after_plain = re.sub(r'<[^>]+>', ' ', after_plain)
        if re.search(
            r'(?m)^\s*(?:#\s*)?(?:LEI|DECRETO|MEDIDA\s+PROVIS[ÓO]RIA|RESOLU[ÇC][ÃA]O|PORTARIA)\b',
            after_plain,
            re.I,
        ):
            if raw_len <= 250_000:
                return True
        return False
    if raw_len <= 250_000:
        return True
    return False


def extract_images(body: str, md_rel: str, write_assets: bool) -> tuple[str, list[dict], list[dict]]:
    extracted, omitted = [], []

    def repl(m: re.Match) -> str:
        alt, _full, mime, b64 = m.group(1), m.group(2), m.group(3).lower(), m.group(4)
        b64_clean = (
            b64.replace('%20', '')
            .replace('%0A', '')
            .replace('%0D', '')
            .replace('\n', '')
            .replace('\r', '')
            .replace(' ', '')
        )
        try:
            raw = base64.b64decode(b64_clean, validate=False)
        except Exception:
            raw = base64.b64decode(b64_clean + '==')
        digest = sha256_bytes(raw)
        ext = MIME_EXT.get(mime.split(';')[0].split('/')[-1] if '/' in mime else mime, mime.split('+')[0] or 'bin')
        if '/' in mime:
            ext = MIME_EXT.get(mime.split('/', 1)[1], 'bin')
        rec = {
            'path': md_rel,
            'sha256': digest,
            'mime': f'image/{mime}' if not mime.startswith('image/') else mime,
            'bytes': len(raw),
            'alt': alt,
        }
        if is_decorative_header_image(body, m.start(), len(raw), alt):
            rec['tratamento'] = 'omitida; brasão/logo decorativo de cabeçalho sem texto jurídico associado'
            omitted.append(rec)
            return ''
        asset_name = f'{digest}.{ext}'
        if write_assets:
            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
            out = ASSETS_DIR / asset_name
            if not out.exists():
                out.write_bytes(raw)
        rel = rel_asset_path(ROOT / md_rel, asset_name)
        rec['asset'] = f'assets/md-inline/{asset_name}'
        rec['markdown_ref'] = rel
        rec['tratamento'] = 'extraída para assets/md-inline com referência relativa'
        extracted.append(rec)
        alt_out = alt.strip()
        return f'![{alt_out}]({rel})'

    new_body, n = IMG_RE.subn(repl, body)
    if n:
        # collapse excessive blank lines left by omissions
        new_body = re.sub(r'\n{3,}', '\n\n', new_body)
    return new_body, extracted, omitted


class _FragmentConverter(HTMLParser):
    """Convert presentation HTML fragments to Markdown while keeping rowspan tables."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.stack: list[str] = []
        self.bold = 0
        self.italic = 0
        self.strike = 0
        self.preserve_depth = 0
        self._capture: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_d = dict(attrs)
        if self.preserve_depth:
            self._capture.append(self.get_starttag_text())
            if tag in ('table', 'thead', 'tbody', 'tr', 'td', 'th', 'caption', 'colgroup', 'col'):
                self.preserve_depth += 1
            return
        if tag == 'table':
            # keep whole table raw if it has merges; else let cells flow
            # We decide later via placeholder path; here treat all tables as preserve
            # when rowspan/colspan present in the opening hunk — handled upstream.
            self.preserve_depth = 1
            self._capture = [self.get_starttag_text()]
            return
        if tag in ('br',):
            self.parts.append('\n')
            return
        if tag in ('p', 'div', 'center', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            if self.parts and not self.parts[-1].endswith('\n'):
                self.parts.append('\n\n')
            self.stack.append(tag)
            return
        if tag in ('strong', 'b'):
            self.bold += 1
            self.parts.append('**')
            return
        if tag in ('em', 'i'):
            self.italic += 1
            self.parts.append('*')
            return
        if tag in ('strike', 'del', 's'):
            self.strike += 1
            self.parts.append('~~')
            return
        if tag in ('font', 'span', 'u'):
            return
        if tag == 'a':
            href = attrs_d.get('href') or ''
            self.stack.append(('a', href))
            self.parts.append('[')
            return
        if tag == 'sup':
            self.stack.append('sup')
            self._sup_buf = []
            return
        # unknown: drop tag, keep text
        return

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.preserve_depth:
            self._capture.append(f'</{tag}>')
            if tag in ('table', 'thead', 'tbody', 'tr', 'td', 'th', 'caption', 'colgroup', 'col'):
                self.preserve_depth -= 1
                if self.preserve_depth == 0:
                    raw = ''.join(self._capture)
                    self._capture = None
                    # strip presentation attrs from structural table but keep merges
                    self.parts.append(simplify_structural_table(raw))
            return
        if tag in ('p', 'div', 'center', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.parts.append('\n\n')
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()
            return
        if tag in ('strong', 'b') and self.bold:
            self.parts.append('**')
            self.bold -= 1
            return
        if tag in ('em', 'i') and self.italic:
            self.parts.append('*')
            self.italic -= 1
            return
        if tag in ('strike', 'del', 's') and self.strike:
            self.parts.append('~~')
            self.strike -= 1
            return
        if tag == 'a' and self.stack and isinstance(self.stack[-1], tuple) and self.stack[-1][0] == 'a':
            _, href = self.stack.pop()
            self.parts.append(f']({href})' if href else ']')
            return
        if tag == 'sup' and self.stack and self.stack[-1] == 'sup':
            self.stack.pop()
            text = ''.join(getattr(self, '_sup_buf', [])).strip()
            if text.lower() in ('o', 'º'):
                self.parts.append('º')
            elif text.lower() in ('a', 'ª'):
                self.parts.append('ª')
            else:
                self.parts.append(f'<sup>{text}</sup>' if text else '')
            self._sup_buf = []
            return

    def handle_data(self, data):
        if self.preserve_depth and self._capture is not None:
            self._capture.append(data)
            return
        if self.stack and self.stack[-1] == 'sup':
            self._sup_buf.append(data)
            return
        self.parts.append(data)

    def handle_entityref(self, name):
        self.handle_data(f'&{name};')

    def handle_charref(self, name):
        self.handle_data(f'&#{name};')

    def output(self) -> str:
        text = ''.join(self.parts)
        text = collapse_empty_emphasis(text)
        text = re.sub(r'[ \t]+\n', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip() + ('\n' if text.strip() else '')


def collapse_empty_emphasis(text: str) -> str:
    """Remove marcadores vazios na mesma linha.

    Itálico vazio exige espaço entre os `*` — `**` colado é negrito, não itálico vazio.
    """
    text = re.sub(r'\*\*[ \t]*\*\*', '', text)
    text = re.sub(r'(?<!\*)\*[ \t]+\*(?!\*)', '', text)
    text = re.sub(r'~~[ \t]*~~', '', text)
    return text


def simplify_structural_table(html_table: str) -> str:
    """Keep table/tr/td/th/rowspan/colspan; drop presentation wrappers inside."""
    out = html_table
    out = re.sub(r'\s+style="[^"]*"', '', out, flags=re.I)
    out = re.sub(r'\s+class="[^"]*"', '', out, flags=re.I)
    out = re.sub(r'\s+align="[^"]*"', '', out, flags=re.I)
    out = re.sub(r'\s+width="[^"]*"', '', out, flags=re.I)
    out = re.sub(r'\s+border="[^"]*"', '', out, flags=re.I)
    out = re.sub(r'<br\b[^>]*>', ' ', out, flags=re.I)
    out = re.sub(r'</?p\b[^>]*>', ' ', out, flags=re.I)
    out = re.sub(r'</?(?:font|span|div|center|u)\b[^>]*>', '', out, flags=re.I)
    out = re.sub(r'<strong\b[^>]*>', '**', out, flags=re.I)
    out = re.sub(r'</strong>', '**', out, flags=re.I)
    out = re.sub(r'<b\b[^>]*>', '**', out, flags=re.I)
    out = re.sub(r'</b>', '**', out, flags=re.I)
    out = re.sub(r'<em\b[^>]*>', '*', out, flags=re.I)
    out = re.sub(r'</em>', '*', out, flags=re.I)
    out = re.sub(r'<i\b[^>]*>', '*', out, flags=re.I)
    out = re.sub(r'</i>', '*', out, flags=re.I)
    out = collapse_empty_emphasis(out)
    out = re.sub(r'[ \t]{2,}', ' ', out)
    return out


def protect_merged_tables(text: str) -> tuple[str, list[str]]:
    tables = []

    def repl(m: re.Match) -> str:
        chunk = m.group(0)
        if not ROWSPAN_COLSPAN_RE.search(chunk):
            return chunk  # leave for normal conversion
        tables.append(simplify_structural_table(chunk))
        return f'\n\n@@LIMPEZA_TABLE_{len(tables) - 1}@@\n\n'

    return STRUCTURAL_TABLE_RE.sub(repl, text), tables


def restore_tables(text: str, tables: list[str]) -> str:
    for i, table in enumerate(tables):
        text = text.replace(f'@@LIMPEZA_TABLE_{i}@@', table)
    return text


def looks_like_full_html(text: str) -> bool:
    head = text.lstrip()[:800].lower()
    if head.startswith('<!doctype') or head.startswith('<html') or head.startswith('<table'):
        return True
    tags = len(re.findall(r'<[a-zA-Z][^>]*>', text[:5000]))
    return tags >= 40 and ('<p' in head or '<table' in head or '<div' in head)


def convert_html_body(text: str) -> str:
    text = SUP_ORDINAL_RE.sub(
        lambda m: 'º' if (m.group(1) or m.group(2) or '').lower() in ('o', 'º') else 'ª',
        text,
    )
    protected, tables = protect_merged_tables(text)
    if looks_like_full_html(protected):
        protected = unwrap_layout_tables(protected)
        if re.search(r'<(?:p|font|span|div|strong|em|br|table|tr|td)\b', protected, re.I):
            try:
                import html2text
                h = html2text.HTML2Text()
                h.body_width = 0
                h.unicode_snob = True
                h.protect_links = True
                h.ignore_images = False
                h.single_line_break = False
                converted = h.handle(protected)
            except Exception:
                converted = convert_mixed_markdown_html(protected)
        else:
            converted = protected
        converted = collapse_empty_emphasis(converted)
    else:
        # light / mixed markdown+HTML
        if not PRESENTATION_TAG_RE.search(protected) and not re.search(r'<(?:table|tr|td|th)\b', protected, re.I):
            return restore_tables(protected, tables)
        converted = convert_mixed_markdown_html(protected)

    converted = restore_tables(converted, tables)
    converted = re.sub(r'\n{3,}', '\n\n', converted)
    return converted.strip() + '\n'


def convert_mixed_markdown_html(text: str) -> str:
    """Convert HTML tags embedded in mostly-Markdown text without destroying MD."""
    # Fast path replacements for common patterns
    out = text
    out = re.sub(r'<br\b[^>]*>', '\n', out, flags=re.I)
    out = re.sub(r'</?p\b[^>]*>', '\n\n', out, flags=re.I)
    out = re.sub(r'</?div\b[^>]*>', '\n', out, flags=re.I)
    out = re.sub(r'</?center\b[^>]*>', '\n', out, flags=re.I)
    out = re.sub(r'<strong\b[^>]*>', '**', out, flags=re.I)
    out = re.sub(r'</strong>', '**', out, flags=re.I)
    out = re.sub(r'<b\b[^>]*>', '**', out, flags=re.I)
    out = re.sub(r'</b>', '**', out, flags=re.I)
    out = re.sub(r'<em\b[^>]*>', '*', out, flags=re.I)
    out = re.sub(r'</em>', '*', out, flags=re.I)
    out = re.sub(r'<i\b[^>]*>', '*', out, flags=re.I)
    out = re.sub(r'</i>', '*', out, flags=re.I)
    out = re.sub(r'<strike\b[^>]*>|<del\b[^>]*>|<s\b[^>]*>', '~~', out, flags=re.I)
    out = re.sub(r'</strike>|</del>|</s>', '~~', out, flags=re.I)
    out = re.sub(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        lambda m: f'[{re.sub(r"<[^>]+>", "", m.group(2)).strip()}]({m.group(1)})'
        if m.group(1) and m.group(2).strip() else re.sub(r'<[^>]+>', '', m.group(2)),
        out,
        flags=re.I | re.S,
    )
    out = re.sub(r'</?(?:font|span|u)\b[^>]*>', '', out, flags=re.I)
    out = re.sub(r'<h([1-6])\b[^>]*>', lambda m: '\n\n' + '#' * int(m.group(1)) + ' ', out, flags=re.I)
    out = re.sub(r'</h[1-6]\s*>', '\n\n', out, flags=re.I)
    out = collapse_empty_emphasis(out)
    out = re.sub(r'[ \t]+\n', '\n', out)
    out = re.sub(r'\n{3,}', '\n\n', out)
    # Remaining full HTML blobs (GO layout tables without rowspan): unwrap; html2text só se sobrar tag
    if looks_like_full_html(out) or (out.count('<') > 20 and re.search(r'<(?:table|font|span|p)\b', out, re.I)):
        out = unwrap_layout_tables(out)
        if re.search(r'<(?:p|font|span|div|strong|em|br|table|tr|td)\b', out, re.I):
            try:
                import html2text
                h = html2text.HTML2Text()
                h.body_width = 0
                h.unicode_snob = True
                h.protect_links = True
                out = h.handle(out)
            except Exception:
                conv = _FragmentConverter()
                conv.feed(out)
                conv.close()
                out = conv.output()
        out = collapse_empty_emphasis(out)
        out = re.sub(r'\n{3,}', '\n\n', out)
    return out


def unwrap_layout_tables(html: str) -> str:
    """Remove tabelas de diagramação (sem rowspan/colspan) preservando o texto das células."""
    def repl(m: re.Match) -> str:
        chunk = m.group(0)
        if ROWSPAN_COLSPAN_RE.search(chunk):
            return chunk
        # Extract cell texts in order; drop pure spacer rows
        cells = re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>', chunk, flags=re.I | re.S)
        parts = []
        for cell in cells:
            inner = cell
            inner = re.sub(r'<br\s*/?>', '\n', inner, flags=re.I)
            inner = re.sub(r'</p\s*>', '\n\n', inner, flags=re.I)
            inner = re.sub(r'<p\b[^>]*>', '', inner, flags=re.I)
            inner = re.sub(r'</div\s*>', '\n', inner, flags=re.I)
            inner = re.sub(r'<div\b[^>]*>', '', inner, flags=re.I)
            # GO/Casa Civil usa <font> como bloco visual — quebra entre fontes consecutivas
            inner = re.sub(r'</font\s*>\s*<font\b[^>]*>', '\n', inner, flags=re.I)
            inner = re.sub(r'</font\s*>', '\n', inner, flags=re.I)
            inner = re.sub(r'<font\b[^>]*>', '', inner, flags=re.I)
            inner = re.sub(r'<strong\b[^>]*>', '**', inner, flags=re.I)
            inner = re.sub(r'</strong>', '**', inner, flags=re.I)
            inner = re.sub(r'<b\b[^>]*>', '**', inner, flags=re.I)
            inner = re.sub(r'</b>', '**', inner, flags=re.I)
            inner = re.sub(r'<em\b[^>]*>', '*', inner, flags=re.I)
            inner = re.sub(r'</em>', '*', inner, flags=re.I)
            inner = re.sub(r'<i\b[^>]*>', '*', inner, flags=re.I)
            inner = re.sub(r'</i>', '*', inner, flags=re.I)
            inner = re.sub(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', inner, flags=re.I | re.S)
            inner = re.sub(r'</?(?:table|tbody|thead|tr|td|th|span|center|u|a)\b[^>]*>', '', inner, flags=re.I)
            inner = re.sub(r'&nbsp;', ' ', inner, flags=re.I)
            inner = re.sub(r'[ \t]+\n', '\n', inner)
            inner = re.sub(r'\n{3,}', '\n\n', inner)
            inner = collapse_empty_emphasis(inner).strip()
            if inner:
                parts.append(inner)
        return '\n\n'.join(parts)
    # Apply from innermost-ish by repeating a few times for nested layout tables
    out = html
    for _ in range(8):
        new = STRUCTURAL_TABLE_RE.sub(repl, out)
        if new == out:
            break
        out = new
    return out


_NOTE_BLOCK_RE = re.compile(
    r'<!--\s*nota-edicao:inicio\s*-->.*?<!--\s*nota-edicao:fim\s*-->',
    re.I | re.S,
)


def strip_portals(body: str, md_rel: str) -> tuple[str, list[str]]:
    """Remove chrome de portal do corpo pesquisável.

    Blocos `<!-- nota-edicao -->` são preservados: avisos DOU ali são proveniência
    editorial (#100 / #70), não chrome de `_source`.
    """
    removed = []
    allow_camara = md_rel in ALLOWLIST_PORTAL_CAMARA
    notes: list[str] = []

    def stash_note(m: re.Match) -> str:
        notes.append(m.group(0))
        return f'\n\n@@LIMPEZA_NOTE_{len(notes) - 1}@@\n\n'

    body = _NOTE_BLOCK_RE.sub(stash_note, body)

    def apply(name: str, pattern: re.Pattern, text: str) -> str:
        nonlocal removed
        if name == 'camara' and allow_camara:
            return text
        new, n = pattern.subn('', text)
        if n:
            removed.extend([name] * n)
        return new

    body = apply('camara', PORTAL_CAMARA_RE, body)
    body = apply('alesp', PORTAL_ALESP_RE, body)
    body = apply('mg_atualizacao', PORTAL_MG_RE, body)
    body = apply('sp_capital', PORTAL_SP_CITY_RE, body)
    body = apply('diario_oficial', PORTAL_DO_RE, body)
    for i, note in enumerate(notes):
        body = body.replace(f'@@LIMPEZA_NOTE_{i}@@', note)
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body.strip() + ('\n' if body.strip() else ''), removed


def process_text(text: str, md_rel: str, write_assets: bool) -> tuple[str, FileResult]:
    result = FileResult(path=md_rel)
    fm, body = split_frontmatter(text)
    original_body = body

    # 1) origin marker(s) — topo ou após número de página isolado
    markers_found = MARKER_LINE_RE.findall(body)
    if markers_found:
        result.marker = markers_found[0]
        body = MARKER_BLOCK_RE.sub('', body, count=len(markers_found))
        # remove leftover leading bare page numbers left alone
        body = re.sub(r'^\d{1,4}\s*\n+', '', body)

    # 2) images
    if md_rel in ALLOWLIST_DATA_IMAGE:
        if 'data:image' in body:
            result.skipped_reason = (result.skipped_reason or '') + 'allowlist-data-image;'
    else:
        body, extracted, omitted = extract_images(body, md_rel, write_assets)
        result.images_extracted = extracted
        result.images_omitted = omitted

    # 3) HTML presentation → markdown
    if '<' in body and (PRESENTATION_TAG_RE.search(body) or re.search(r'<(?:table|tr|td|th|font|span)\b', body, re.I)):
        new_body = convert_html_body(body)
        if new_body != body:
            result.html_converted = True
            body = new_body

    # 4) portals (after HTML so GO disclaimers become plain text first)
    body, portals = strip_portals(body, md_rel)
    result.portals_removed = portals

    if body != original_body or result.marker:
        result.changed = True

    # Núcleo/LGPD exigem linha em branco após o fechamento do frontmatter (`\n---\n\n`).
    if body:
        body = body.strip() + '\n'
    if fm:
        out = fm.rstrip() + '\n\n' + body
    else:
        out = body
    if not out.endswith('\n') and out:
        out += '\n'
    return out, result


def iter_corpus_files() -> list[Path]:
    files = []
    for name in CORPUS_ROOTS:
        root = ROOT / name
        if root.is_dir():
            files.extend(sorted(root.rglob('*.md')))
    return files


def _worker(payload: tuple[str, bool]) -> dict:
    rel, write_assets = payload
    path = ROOT / rel
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        text = path.read_text(encoding='utf-8', errors='replace')
    try:
        new_text, result = process_text(text, rel, write_assets=write_assets)
        if result.changed and write_assets is not None:
            # write_assets flag doubles as apply flag when True; dry-run uses False
            pass
        return {
            'rel': rel,
            'result': asdict(result),
            'new_text': new_text if result.changed else None,
            'error': None,
        }
    except Exception as exc:
        return {'rel': rel, 'result': asdict(FileResult(path=rel, error=str(exc))), 'new_text': None, 'error': str(exc)}


def run(apply: bool, workers: int, limit: int | None = None, only: list[str] | None = None) -> dict:
    META_DIR.mkdir(parents=True, exist_ok=True)
    PROVAS_DIR.mkdir(parents=True, exist_ok=True)
    if apply:
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    if only:
        files = [ROOT / p for p in only]
    else:
        files = iter_corpus_files()
    if limit:
        files = files[:limit]

    payloads = [(str(p.relative_to(ROOT)), apply) for p in files]
    results: list[FileResult] = []
    markers = []
    images = []
    portals = Counter()
    changed = 0
    errors = 0

    # Process sequentially for apply reliability on assets; parallel for dry CPU work.
    if apply or workers <= 1:
        total = len(payloads)
        for idx, (rel, write_assets) in enumerate(payloads, 1):
            if idx == 1 or idx % 2000 == 0 or idx == total:
                print(f'[limpeza] {idx}/{total} changed={changed} errors={errors}', flush=True)
            path = ROOT / rel
            try:
                text = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                text = path.read_text(encoding='utf-8', errors='replace')
            try:
                new_text, result = process_text(text, rel, write_assets=write_assets)
            except Exception as exc:
                result = FileResult(path=rel, error=str(exc))
                new_text = None
                errors += 1
            results.append(result)
            if result.marker:
                markers.append({'path': rel, 'marcador_origem': result.marker})
            images.extend(result.images_extracted)
            images.extend(result.images_omitted)
            for p in result.portals_removed:
                portals[p] += 1
            if result.changed and apply and new_text is not None:
                path.write_text(new_text, encoding='utf-8')
                changed += 1
            elif result.changed:
                changed += 1
            if result.error:
                errors += 1
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(_worker, payload) for payload in payloads]
            for fut in as_completed(futs):
                row = fut.result()
                result = FileResult(**row['result'])
                results.append(result)
                if result.marker:
                    markers.append({'path': result.path, 'marcador_origem': result.marker})
                images.extend(result.images_extracted)
                images.extend(result.images_omitted)
                for p in result.portals_removed:
                    portals[p] += 1
                if result.changed:
                    changed += 1
                if result.error:
                    errors += 1

    summary = {
        'files_scanned': len(files),
        'files_changed': changed,
        'markers': len(markers),
        'images': len(images),
        'images_extracted': sum(1 for i in images if i.get('tratamento', '').startswith('extraída')),
        'images_omitted': sum(1 for i in images if i.get('tratamento', '').startswith('omitida')),
        'portals': dict(portals),
        'html_converted': sum(1 for r in results if r.html_converted),
        'errors': errors,
        'apply': apply,
        'allowlist_data_image': sorted(ALLOWLIST_DATA_IMAGE),
        'allowlist_portal_camara': sorted(ALLOWLIST_PORTAL_CAMARA),
    }

    if apply:
        def merge_jsonl(path: Path, new_rows: list[dict], key_fn=None) -> None:
            if key_fn is None:
                key_fn = lambda row: row.get('path') or json.dumps(row, sort_keys=True)
            existing = {}
            if path.exists():
                for line in path.read_text(encoding='utf-8').splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    existing[key_fn(row)] = row
            for row in new_rows:
                existing[key_fn(row)] = row
            path.write_text(
                ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in existing.values()),
                encoding='utf-8',
            )

        merge_jsonl(META_DIR / 'marcadores-origem.jsonl', markers)
        # Chave composta: mesmo brasão em vários arquivos gera várias linhas de proveniência.
        merge_jsonl(
            META_DIR / 'imagens.jsonl',
            images,
            key_fn=lambda row: f"{row.get('path')}|{row.get('sha256')}",
        )
        portal_path = META_DIR / 'portais-removidos.json'
        prev = {}
        if portal_path.exists():
            try:
                prev = json.loads(portal_path.read_text(encoding='utf-8')).get('contagens') or {}
            except json.JSONDecodeError:
                prev = {}
        merged_portals = Counter(prev)
        merged_portals.update(portals)
        portal_path.write_text(
            json.dumps({'contagens': dict(merged_portals), 'nota': (
                'Famílias removidas do corpo Markdown. Datas de atualização MG e avisos de '
                'não-substituição foram preservados aqui como proveniência agregada; o contrato '
                'geral de metadados por norma permanece na #70.'
            )}, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        summary['portals_acumulado'] = dict(merged_portals)
        (META_DIR / 'resumo.json').write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )

    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Escreve alterações no corpus')
    parser.add_argument('--dry-run', action='store_true', help='Só reporta (padrão)')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--only', nargs='*', default=None, help='Caminhos relativos específicos')
    parser.add_argument('--only-file', default=None, help='Arquivo com um caminho relativo por linha')
    args = parser.parse_args(argv)
    apply = bool(args.apply)
    only = list(args.only or [])
    if args.only_file:
        only.extend(
            line.strip()
            for line in Path(args.only_file).read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.strip().startswith('#')
        )
    summary = run(apply=apply, workers=args.workers, limit=args.limit, only=only or None)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary.get('errors') else 0


if __name__ == '__main__':
    sys.exit(main())
