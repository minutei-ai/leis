#!/usr/bin/env python3
"""Regressão da limpeza de Markdown (#87, #98, #100)."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys
sys.path.insert(0, str(ROOT / 'scripts'))
import limpeza_markdown as lm  # noqa: E402


MARKER_RE = re.compile(r'^###[A-Z]+-[0-9]', re.M)
DATA_IMAGE_RE = re.compile(r'!\[[^\]]*\]\(\s*data:image', re.I)
PRESENTATION_RE = re.compile(
    r'<(?:strong|em|b|i|font|span|p|br)\b',
    re.I,
)
PORTAL_FAMILIES = {
    'camara': re.compile(
        r'(?:\*\*|__)?CÂMARA DOS DEPUTADOS(?:\*\*|__)?\s*'
        r'(?:(?:<br\s*/?>)|\n)+\s*'
        r'(?:\*\*|__)?Centro de Documentação e Informação',
        re.I,
    ),
    'alesp': re.compile(
        r'\[Assembleia Legislativa do Estado de São Paulo\]\([^)]*\)\s*'
        r'\[Ficha informativa\]\([^)]*\)',
    ),
    'mg_atualizacao': re.compile(
        r'\\?={3,}\s*\n+Data da última atualização:\s*\d{1,2}/\d{1,2}/\d{4}',
    ),
    'sp_capital': re.compile(
        r'Este texto não substitui o original publicado no Diário Oficial da Cidade de São Paulo',
    ),
    'diario_oficial': re.compile(
        r'Este texto não substitui\b',
        re.I,
    ),
}


class LimpezaUnit(unittest.TestCase):
    def test_marker_to_metadata_and_removed(self):
        src = '###LEI-001961-0-000-26-08-1953@@@\n\n<strong>Art.</strong> 1º Texto.\n'
        out, res = lm.process_text(src, 'federal/exemplo.md', write_assets=False)
        self.assertEqual(res.marker, '###LEI-001961-0-000-26-08-1953@@@')
        self.assertFalse(MARKER_RE.search(out))
        self.assertIn('**Art.** 1º Texto.', out)
        self.assertNotIn('<strong>', out)

    def test_marker_with_retificacao_and_page_prefix(self):
        src = '1\n\n###DEC-041380-0-000-24-04-1957@@@RET01+++\n\n**DECRETO**\n'
        out, res = lm.process_text(src, 'federal/exemplo.md', write_assets=False)
        self.assertEqual(res.marker, '###DEC-041380-0-000-24-04-1957@@@RET01+++')
        self.assertNotIn('###DEC-', out)
        self.assertTrue(out.lstrip().startswith('**DECRETO**'))

    def test_base64_with_percent20(self):
        b64 = (
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQ'
            'AAAABJRU5ErkJggg=='
        )
        src = f'![](data:image/png;base64,%20{b64})\n\nArt. 1º Texto.\n'
        out, res = lm.process_text(src, 'federal/x.md', write_assets=False)
        self.assertNotIn('data:image', out)
        self.assertTrue(res.images_omitted or res.images_extracted)

    def test_strike_preserved_as_markdown(self):
        src = '<p>Vigente <strike>revogado</strike> e <del>outro</del>.</p>\n'
        out, res = lm.process_text(src, 'federal/x.md', write_assets=False)
        self.assertIn('~~revogado~~', out)
        self.assertIn('~~outro~~', out)
        self.assertTrue(res.html_converted)

    def test_merged_table_kept_as_html(self):
        src = (
            '<p>Antes</p>\n'
            '<table><tr><td rowspan="2">A</td><td>B</td></tr>'
            '<tr><td>C</td></tr></table>\n'
            '<p>Depois</p>\n'
        )
        out, _ = lm.process_text(src, 'federal/x.md', write_assets=False)
        self.assertIn('<table>', out)
        self.assertIn('rowspan="2"', out)
        self.assertIn('Antes', out)
        self.assertIn('Depois', out)

    def test_base64_image_extracted_or_omitted(self):
        # 1x1 png
        b64 = (
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQ'
            'AAAABJRU5ErkJggg=='
        )
        src = f'![](data:image/png;base64,{b64})\n\nArt. 1º Texto.\n'
        out, res = lm.process_text(src, 'federal/x.md', write_assets=False)
        self.assertNotIn('data:image', out)
        self.assertTrue(res.images_omitted or res.images_extracted)
        self.assertIn('Art. 1º Texto.', out)

    def test_portal_families_removed(self):
        src = (
            'CÂMARA DOS DEPUTADOS\n\nCentro de Documentação e Informação\n\n'
            'LEI Nº 1\n\nArt. 1º Ok.\n\n'
            '\\================================\n\n'
            'Data da última atualização: 29/7/2016.\n'
        )
        out, res = lm.process_text(src, 'estaduais/MG/x.md', write_assets=False)
        self.assertIn('camara', res.portals_removed)
        self.assertIn('mg_atualizacao', res.portals_removed)
        self.assertNotIn('Centro de Documentação e Informação', out)
        self.assertNotIn('Data da última atualização', out)
        self.assertIn('Art. 1º Ok.', out)

    def test_camara_heading_and_messy_mg_date(self):
        src = (
            '# CÂMARA DOS DEPUTADOS\n\n# Centro de Documentação e Informação\n\n'
            '# DECRETO-LEI Nº 1\n\nArt. 1º Ok.\n\n'
            '\\===============================-======\n\n'
            'Data da última atualização: 31/1//2007.\n'
        )
        out, res = lm.process_text(src, 'estaduais/MG/y.md', write_assets=False)
        self.assertIn('camara', res.portals_removed)
        self.assertIn('mg_atualizacao', res.portals_removed)
        self.assertNotIn('CÂMARA DOS DEPUTADOS', out)
        self.assertNotIn('Data da última atualização', out)
        self.assertIn('Art. 1º Ok.', out)
        self.assertIn('DECRETO-LEI Nº 1', out)

    def test_camara_in_legal_text_kept(self):
        src = (
            'AS MESAS DA CÂMARA DOS DEPUTADOS E DO SENADO FEDERAL, nos termos do '
            '§ 3º do art. 60 da Constituição Federal, promulgam a seguinte Emenda.\n'
        )
        out, res = lm.process_text(src, 'federal/ec.md', write_assets=False)
        self.assertNotIn('camara', res.portals_removed)
        self.assertIn('CÂMARA DOS DEPUTADOS E DO SENADO', out)

    def test_alesp_and_sp_city(self):
        src = (
            '[Assembleia Legislativa do Estado de São Paulo](http://www.al.sp.gov.br/) '
            '[Ficha informativa](https://www.al.sp.gov.br/norma/?id=1)\n\n'
            '# LEI\n\nArt. 1º X.\n\n'
            'Este texto não substitui o original publicado no Diário Oficial da Cidade de São Paulo\n'
        )
        out, res = lm.process_text(src, 'municipais/3550308/x.md', write_assets=False)
        self.assertIn('alesp', res.portals_removed)
        self.assertIn('sp_capital', res.portals_removed)
        self.assertIn('Art. 1º X.', out)

    def test_dou_disclaimer_removed_keeps_articles(self):
        src = (
            'Art. 1º Norma.\n\n'
            '*Este texto não substitui o publicado no D.O.U. de 1º/1/2020.*\n'
        )
        out, res = lm.process_text(src, 'federal/x.md', write_assets=False)
        self.assertIn('diario_oficial', res.portals_removed)
        self.assertIn('Art. 1º Norma.', out)
        body_wo_note = re.sub(
            r'<!--\s*nota-edicao:inicio\s*-->.*?<!--\s*nota-edicao:fim\s*-->',
            '',
            out,
            flags=re.I | re.S,
        )
        self.assertNotIn('não substitui', body_wo_note)
        self.assertIn('nota-edicao:inicio', out)
        self.assertIn('Este texto não substitui o publicado no D.O.U. de 1º/1/2020.', out)

    def test_dou_aviso_kept_inside_edition_note(self):
        src = (
            '<!-- nota-edicao:inicio -->\n\n'
            '> Este texto não substitui o publicado no DOU de 25.7.1991.\n\n'
            '<!-- nota-edicao:fim -->\n\n'
            'Art. 1º Norma.\n\n'
            'Este texto não substitui o publicado no DOU de 25.7.1991.\n'
        )
        out, res = lm.process_text(src, 'federal/x.md', write_assets=False)
        self.assertIn('diario_oficial', res.portals_removed)
        self.assertIn('Art. 1º Norma.', out)
        self.assertIn('nota-edicao:inicio', out)
        self.assertIn('> Este texto não substitui o publicado no DOU de 25.7.1991.', out)
        body_wo_note = re.sub(
            r'<!--\s*nota-edicao:inicio\s*-->.*?<!--\s*nota-edicao:fim\s*-->',
            '',
            out,
            flags=re.I | re.S,
        )
        self.assertNotIn('não substitui', body_wo_note)

    def test_dou_suplemento_dpl_pa_variants_to_note(self):
        cases = [
            (
                'estaduais/GO/x.md',
                'Art. 1º X.\n\n(D.O. de 13-01-2020-Suplemento) '
                '*Este texto não substitui o publicado no Suplemento do D.O. de 13-01-2020.*\n',
                'Suplemento do D.O.',
                'D.O. de 13-01-2020-Suplemento',
            ),
            (
                'estaduais/ES/x.md',
                'Art. 1º X.\n\nEste texto não substitui o publicado no D.P.L. de 19/11/2015.\n',
                'D.P.L.',
                'Art. 1º X.',
            ),
            (
                'estaduais/PA/x.md',
                'Art. 1º X.\n\nDOE Nº 1.\n\n\\*Este texto não substitui o texto '
                'publicado no Diário Oficial do Estado do Pará.\n',
                'Diário Oficial do Estado do Pará',
                'DOE Nº 1.',
            ),
            (
                'municipais/5208707/x.md',
                '<!-- nota-edicao:inicio -->\n\n> Captura SILEG.\n\n<!-- nota-edicao:fim -->\n\n'
                'Art. 1º X.\n\nEste texto não substitui o publicado no '
                '[DOM 8318 de 25/06/2024.](https://example.test/do.pdf)\n',
                'DOM 8318',
                'Art. 1º X.',
            ),
        ]
        for path, src, needle, keep in cases:
            with self.subTest(path=path):
                out, res = lm.process_text(src, path, write_assets=False)
                self.assertIn('diario_oficial', res.portals_removed)
                self.assertIn(keep, out)
                self.assertIn(needle, out)
                self.assertIn('nota-edicao:inicio', out)
                body_wo_note = re.sub(
                    r'<!--\s*nota-edicao:inicio\s*-->.*?<!--\s*nota-edicao:fim\s*-->',
                    '',
                    out,
                    flags=re.I | re.S,
                )
                self.assertNotIn('não substitui', body_wo_note)

    def test_link_and_relation_text_preserved(self):
        src = (
            '<p>Vide <a href="https://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm">'
            'Lei nº 8.666/1993</a> e a <strong>relação</strong> com o art. 193.</p>\n'
        )
        out, res = lm.process_text(src, 'federal/x.md', write_assets=False)
        self.assertIn('[Lei nº 8.666/1993](https://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm)', out)
        self.assertIn('**relação**', out)
        self.assertIn('art. 193', out)
        self.assertTrue(res.html_converted)

    def test_note_before_brasao_is_omitted(self):
        b64 = (
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQ'
            'AAAABJRU5ErkJggg=='
        )
        src = (
            '<!-- nota-edicao:inicio -->\n\n> nota\n\n<!-- nota-edicao:fim -->\n\n'
            f'![](data:image/png;base64,{b64})\n\n'
            'CÂMARA DOS DEPUTADOS\n\nCentro de Documentação e Informação\n\n'
            'LEI Nº 1\n\nArt. 1º Ok.\n'
        )
        out, res = lm.process_text(src, 'federal/hist.md', write_assets=False)
        self.assertTrue(res.images_omitted)
        self.assertFalse(res.images_extracted)
        self.assertNotIn('data:image', out)
        self.assertIn('camara', res.portals_removed)
        self.assertIn('Art. 1º Ok.', out)
        self.assertIn('nota-edicao:inicio', out)

    def test_frontmatter_keeps_blank_line(self):
        src = '---\nid: "x"\n---\n\n###LEI-001961-0-000-26-08-1953@@@\n\nArt. 1º.\n'
        out, res = lm.process_text(src, 'federal/x.md', write_assets=False)
        self.assertTrue(out.startswith('---\n'))
        self.assertIn('\n---\n\n', out)
        self.assertIn('Art. 1º.', out)

    def test_generator_drops_camara_portal_prefix(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        try:
            import nucleo_licitacoes as nl  # noqa: WPS433
        except ModuleNotFoundError as exc:
            self.skipTest(f'dependência do gerador ausente: {exc}')
        blocks = [
            'CÂMARA DOS DEPUTADOS',
            'Centro de Documentação e Informação',
            'LEI Nº 1, DE 1º DE JANEIRO DE 2000',
            'Art. 1º Texto.',
        ]
        pub = nl.drop_camara_portal_prefix(blocks)
        self.assertEqual(pub[0], 'LEI Nº 1, DE 1º DE JANEIRO DE 2000')
        md = nl.blocks_to_markdown(pub, r'^LEI\s+N')
        self.assertTrue(md.startswith('# LEI'))
        self.assertNotIn('Centro de Documentação', md)

    def test_allowlists_empty_after_generator_fix(self):
        self.assertEqual(lm.ALLOWLIST_DATA_IMAGE, set())
        self.assertEqual(lm.ALLOWLIST_PORTAL_CAMARA, set())

    def test_amostra_families_preserve_articles(self):
        """Pares antes/depois: artigos do antes continuam no depois (famílias #87/#100)."""
        amostra = ROOT / 'provas' / 'limpeza-markdown' / 'amostras'
        pairs = sorted(amostra.glob('*.antes.md'))
        self.assertGreaterEqual(len(pairs), 4)
        for antes_path in pairs:
            depois_path = Path(str(antes_path).replace('.antes.md', '.depois.md'))
            self.assertTrue(depois_path.is_file(), depois_path)
            antes = antes_path.read_text(encoding='utf-8', errors='replace')
            # Reaplica o cleaner no antes e confere artigos (não depende do snapshot truncado).
            out, _ = lm.process_text(antes, 'federal/amostra.md', write_assets=False)
            arts = re.findall(r'(?i)Art\.?\s*\d+', antes)
            for art in arts[:30]:
                self.assertIn(art, out, f'{antes_path.name}: artigo {art!r} ausente após limpeza')


def _rg_count(
    pattern: str,
    paths: list[str],
    fixed: bool = False,
    multiline: bool | None = None,
) -> int:
    cmd = ['rg', '-l', '--glob', '*.md']
    if fixed:
        cmd.append('-F')
    if multiline is None:
        multiline = (not fixed) and ('\\n' in pattern or '\n' in pattern)
    if multiline:
        cmd.append('--multiline')
    cmd.append(pattern)
    cmd.extend(paths)
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True)
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 1:
            return 0
        raise
    files = [line for line in out.splitlines() if line.strip()]
    return len(files)


def _rg_files(
    pattern: str,
    paths: list[str],
    multiline: bool | None = None,
) -> set[str]:
    cmd = ['rg', '-l', '--glob', '*.md']
    if multiline is None:
        multiline = '\\n' in pattern or '\n' in pattern
    if multiline:
        cmd.append('--multiline')
    cmd.extend([pattern, *paths])
    try:
        out = subprocess.check_output(cmd, cwd=ROOT, text=True)
    except subprocess.CalledProcessError as exc:
        if exc.returncode == 1:
            return set()
        raise
    return {line.strip() for line in out.splitlines() if line.strip()}


class LimpezaCorpusGates(unittest.TestCase):
    """Gates de regressão no acervo publicado. Rodar após --apply."""

    roots = ['federal', 'estaduais', 'municipais']

    def test_no_origin_markers(self):
        self.assertEqual(_rg_count(r'^###[A-Z]+-[0-9]', self.roots), 0)

    def test_no_inline_data_image_outside_allowlist(self):
        files = _rg_files(r'!\[[^]]*\]\(data:image', self.roots)
        unexpected = files - set(lm.ALLOWLIST_DATA_IMAGE)
        self.assertEqual(
            unexpected,
            set(),
            f'data:image restante fora da allowlist histórica: {sorted(unexpected)[:20]}',
        )

    def test_portal_families_zero_outside_allowlist(self):
        # Câmara: bloco portal (não o sintagma legal isolado)
        camara_files = _rg_files(
            r'CÂMARA DOS DEPUTADOS\s*(\n|<br)[^\n]*Centro de Documentação e Informação',
            self.roots,
        )
        unexpected = camara_files - set(lm.ALLOWLIST_PORTAL_CAMARA)
        self.assertEqual(unexpected, set(), sorted(unexpected)[:20])

        # Portal ALESP = links de cabeçalho, não o sintagma no corpo legal.
        self.assertEqual(
            _rg_count(
                r'^\[Assembleia Legislativa do Estado de São Paulo\]\([^)]*\)\s*\[Ficha informativa\]',
                ['estaduais/SP'],
            ),
            0,
        )
        self.assertEqual(
            _rg_count(
                r'\\?[=-]{3,}[^\n]*\n+Data da última atualização:',
                ['estaduais/MG'],
            ),
            0,
        )
        self.assertEqual(
            _rg_count(
                'Este texto não substitui o original publicado no Diário Oficial da Cidade de São Paulo',
                ['municipais'],
                fixed=True,
            ),
            0,
        )

        # Aviso «não substitui…» fora de <!-- nota-edicao --> (proveniência fica na nota).
        offenders = []
        for rel in sorted(_rg_files(
            r'Este texto não substitui\b',
            self.roots,
        )):
            text = (ROOT / rel).read_text(encoding='utf-8', errors='replace')
            body = re.sub(
                r'<!--\s*nota-edicao:inicio\s*-->.*?<!--\s*nota-edicao:fim\s*-->',
                '',
                text,
                flags=re.I | re.S,
            )
            if re.search(r'Este texto não substitui\b', body, re.I):
                offenders.append(rel)
        self.assertEqual(offenders, [], offenders[:20])

    def test_presentation_html_outside_merged_tables(self):
        """Tags de apresentação fora de <table> com rowspan/colspan devem ser zero.

        O CONTRATO admite <table> simples com merges; <br> residual só dentro dessas
        tabelas é limpo pelo simplify, e o gate abaixo ignora o interior de tables.
        """
        files = _rg_files(r'<(strong|em|b|i|font|span|p|br)[ >/]', self.roots)
        offenders = []
        for rel in sorted(files):
            text = (ROOT / rel).read_text(encoding='utf-8', errors='replace')
            # Remove structural tables before searching presentation tags.
            stripped = lm.STRUCTURAL_TABLE_RE.sub(
                lambda m: m.group(0) if lm.ROWSPAN_COLSPAN_RE.search(m.group(0)) else m.group(0),
                text,
            )
            # Drop all tables with merges entirely for the gate.
            without_merged = re.sub(
                r'<table\b[^>]*>.*?</table>',
                lambda m: '' if lm.ROWSPAN_COLSPAN_RE.search(m.group(0)) else m.group(0),
                text,
                flags=re.I | re.S,
            )
            if PRESENTATION_RE.search(without_merged):
                offenders.append(rel)
        self.assertEqual(offenders, [], offenders[:20])


if __name__ == '__main__':
    unittest.main()
