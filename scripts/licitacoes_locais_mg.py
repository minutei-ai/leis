#!/usr/bin/env python3
"""Conversão e verificação do Decreto municipal BH 18.289/2023 (MG / issue #57).

Lê somente snapshots em provas/licitacoes-locais/MG/; não acessa a rede.
Uso:
  python3 scripts/licitacoes_locais_mg.py convert
  python3 scripts/licitacoes_locais_mg.py verify
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import lzma
import re
import sys
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
HTML_XZ = ROOT / 'provas/licitacoes-locais/MG/fontes/conteudoAto_id200561.html.xz'
MD_PATH = ROOT / 'municipais/3106200/br-municipal-3106200-decreto-2023-03-28-18289.md'
CATALOGO = ROOT / 'metadados/licitacoes-locais/MG.json'
COBERTURA = ROOT / 'provas/licitacoes-locais/MG/cobertura-18289.json'
FONTES = ROOT / 'provas/licitacoes-locais/MG/fontes.json'

SHA256_HTML = '3fae24568f0c82e5ae543daa3f11424dae32af818e3ef3110d9441d5c390c38d'
SHA256_CORPO = '61cb9cbaef37cf30f8e8bbb5a27dc5377aca2851ecc4be220cd393822495f66d'
NOTE_RE = re.compile(r'<!-- nota-edicao:inicio -->.*?<!-- nota-edicao:fim -->\s*', re.S)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fold(text: str) -> str:
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r'(?<=\d)\s*[oº°ª](?![a-z0-9])', ' ', text)
    return re.sub(r'[^0-9a-z]+', '', text)


def load_html() -> bytes:
    data = lzma.open(HTML_XZ).read()
    got = sha256_bytes(data)
    if got != SHA256_HTML:
        raise SystemExit(f'HTML snapshot hash divergiu: {got}')
    return data


def inline(el) -> str:
    parts = []
    for child in el.children:
        name = getattr(child, 'name', None)
        if name is None:
            parts.append(str(child))
        elif name in ('strong', 'b'):
            t = child.get_text('', strip=False)
            parts.append(f'**{t}**' if t.strip() else t)
        elif name in ('em', 'i'):
            t = child.get_text('', strip=False)
            parts.append(f'*{t}*' if t.strip() else t)
        elif name == 'br':
            parts.append('\n')
        else:
            parts.append(child.get_text('', strip=False))
    text = ''.join(parts)
    text = html_lib.unescape(text).replace('\xa0', ' ')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text.strip()


def html_to_corpo(html_bytes: bytes) -> str:
    soup = BeautifulSoup(html_bytes, 'lxml')
    body = soup.body or soup
    blocks = [inline(p) for p in body.find_all('p')]
    blocks = [b for b in blocks if b]
    return '\n\n'.join(blocks) + '\n'


def nota_edicao() -> str:
    return '''<!-- nota-edicao:inicio -->

> **Decreto municipal de Belo Horizonte recuperado do DOM-PBH (API oficial).** Fonte do ato: https://api-dom.pbh.gov.br/api/v1/edicoes/atos/200561/publicado (ato DOM id `200561`; visualização https://dom-web.pbh.gov.br/visualizacao/ato/200561). Documento HTML do ato: https://api-dom.pbh.gov.br/api/v1/documentos/823a985c9f5d9d387b2327f529adaf8f0e8e20a02d6e555724ef4718f956f8a7/download (`conteudoAto_id200561.html`). Catálogo da PGM (identificação/ementa, sem validar a íntegra): https://prefeitura.pbh.gov.br/procuradoria/regulamentacao-municipal. Captura em 2026-11-04T11:47:38Z. SHA-256 do HTML do ato `3fae24568f0c82e5ae543daa3f11424dae32af818e3ef3110d9441d5c390c38d`; SHA-256 do JSON do ato `ca251d17670c40b4fb8c54bf1b2cfa913c1ebaa63727dcbf69dc0ef638dc128d`. Snapshots: `provas/licitacoes-locais/MG/fontes/`. Publicação no Diário Oficial do Município, edição 6730 (id 6824), em 2023-03-29; PDF do jornal `Dom6730.pdf` SHA-256 `e9b1e293198bc3cccabf939611d76ca12a1284751b23c7263c3e8634bfdff671`.
>
> Esta edição reproduz o texto do ato de 28/03/2023 na publicação do DOM (edição 6730, publicada em 29/03/2023). Não incorpora alterações posteriores (o catálogo da PGM aponta o Decreto nº 18.621, de 5/02/2024, como alterador). Não certifica vigência. Âmbito literal do art. 1º: administração municipal direta e indireta e entidades vinculadas ou controladas direta ou indiretamente pelo Poder Executivo; § 2º admite adoção, no que couber, por empresas públicas, sociedades de economia mista e subsidiárias. O art. 47 preserva exclusão transitória de procedimentos regidos pela Lei 10.520/2001 e pela Lei 12.462/2011. Anexos separados do ato: nenhum na API de anexos publicados. Não confundir com o Decreto estadual MG 48.723/2023.

<!-- nota-edicao:fim -->

'''


def strip_note(markdown: str) -> str:
    return NOTE_RE.sub('', markdown, count=1)


def convert() -> str:
    corpo = html_to_corpo(load_html())
    if sha256_bytes(corpo.encode()) != SHA256_CORPO:
        raise SystemExit('hash do corpo convertido divergiu do esperado')
    md = nota_edicao() + corpo
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_PATH.write_text(md, encoding='utf-8')
    return md


def verify() -> None:
    html_bytes = load_html()
    corpo_esperado = html_to_corpo(html_bytes)
    if sha256_bytes(corpo_esperado.encode()) != SHA256_CORPO:
        raise SystemExit('reconversão divergiu do SHA256_CORPO')

    plain_src = BeautifulSoup(html_bytes, 'lxml').get_text(' ')
    plain_src = html_lib.unescape(plain_src).replace('\xa0', ' ')
    if fold(plain_src) != fold(corpo_esperado):
        raise SystemExit('cobertura fold HTML↔Markdown falhou')

    if not MD_PATH.is_file():
        raise SystemExit(f'ausente: {MD_PATH}')
    published = MD_PATH.read_text(encoding='utf-8')
    if '<!-- nota-edicao:inicio -->' not in published:
        raise SystemExit('nota de edição ausente no Markdown publicado')
    corpo_pub = strip_note(published)
    if corpo_pub != corpo_esperado:
        raise SystemExit('corpo publicado diverge da reconversão do snapshot')
    # Fonte completa → Markdown: igualdade byte a byte do corpo, não só sentinelas.
    if sha256_bytes(corpo_pub.encode()) != SHA256_CORPO:
        raise SystemExit('hash do corpo publicado divergiu')

    arts = re.findall(r'^Art\.\s*(\d+)', corpo_pub, re.M)
    if arts != [str(i) for i in range(1, 49)]:
        raise SystemExit(f'artigos inesperados: {arts}')
    if 'Belo Horizonte, 28 de março de 2023' not in corpo_pub:
        raise SystemExit('data do ato ausente no corpo normativo')

    note = published[: published.find('<!-- nota-edicao:fim -->') + len('<!-- nota-edicao:fim -->')]
    if 'publicação do DOM (28/03/2023)' in note or 'publicação DOM de 28/03/2023' in note:
        raise SystemExit('nota confunde data do ato com publicação do DOM')
    if 'ato de 28/03/2023' not in note or 'publicada em 29/03/2023' not in note:
        raise SystemExit('nota deve separar data do ato (28/03) e publicação DOM (29/03)')

    edicao = json.loads((ROOT / 'provas/licitacoes-locais/MG/fontes/dom-edicao-6824.json').read_text(encoding='utf-8'))
    ed = edicao.get('data') or edicao
    if ed.get('numero_edicao') != 6730 or ed.get('dt_publicacao') != '2023-03-29':
        raise SystemExit('snapshot da edição DOM diverge (esperado 6730 / 2023-03-29)')

    cat = json.loads(CATALOGO.read_text(encoding='utf-8'))
    if cat.get('uf') != 'MG' or cat.get('cobertura') != 'parcial':
        raise SystemExit('catálogo MG inválido')
    docs = cat.get('documentos') or []
    if len(docs) != 1 or docs[0].get('norma_id') != 'br-municipal-3106200-decreto-2023-03-28-18289':
        raise SystemExit('documento 18.289 ausente no catálogo')
    if docs[0].get('hashes', {}).get('corpo_markdown') != SHA256_CORPO:
        raise SystemExit('hash do corpo no catálogo divergiu')
    ed_desc = (docs[0].get('edicao') or {}).get('descricao') or ''
    if '28/03/2023' not in ed_desc or '2023-03-29' not in ed_desc:
        raise SystemExit('catálogo deve registrar assinatura 28/03 e publicação 2023-03-29')
    reut = cat.get('reutilizados') or []
    if not any(r.get('arquivo') == 'estaduais/MG/br-mg-decreto-2023-11-24-48723.md' for r in reut):
        raise SystemExit('reuso do Decreto estadual 48.723 ausente')
    if not (ROOT / 'estaduais/MG/br-mg-decreto-2023-11-24-48723.md').is_file():
        raise SystemExit('arquivo estadual reutilizado ausente')

    cob = json.loads(COBERTURA.read_text(encoding='utf-8'))
    if cob.get('sha256_corpo_markdown') != SHA256_CORPO or cob.get('n_artigos') != 48:
        raise SystemExit('cobertura-18289.json inconsistente')
    limites = '\n'.join(cob.get('limites') or [])
    if 'publicação DOM de 28/03/2023' in limites or 'DOM de 28/03/2023' in limites:
        raise SystemExit('limites da cobertura confundem data do ato com publicação DOM')
    if '28/03/2023' not in limites or '29/03/2023' not in limites:
        raise SystemExit('limites devem separar data do ato e publicação DOM')

    fontes = json.loads(FONTES.read_text(encoding='utf-8'))
    chaves = {f['chave'] for f in fontes.get('fontes', [])}
    for required in (
        'dom-ato-200561-json',
        'dom-ato-200561-html',
        'dom-edicao-6824-json',
        'dom-jornal-6730-pdf',
        'dom-ato-200561-anexos',
        'pgm-regulamentacao-municipal',
    ):
        if required not in chaves:
            raise SystemExit(f'fonte ausente: {required}')

    print('OK: Decreto BH 18.289 / catálogo MG / provas')


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('cmd', choices=('convert', 'verify'))
    args = p.parse_args(argv)
    if args.cmd == 'convert':
        convert()
        print(f'escrito {MD_PATH.relative_to(ROOT)}')
    else:
        verify()
    return 0


if __name__ == '__main__':
    sys.exit(main())
