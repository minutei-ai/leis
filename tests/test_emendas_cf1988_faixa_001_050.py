#!/usr/bin/env python3
"""Testes do lote faixa 001–050 de emendas da CF/1988 (issue #63)."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import sys

sys.path.insert(0, str(ROOT / 'scripts'))

from emendas_cf1988_faixa_001_050 import (  # noqa: E402
    CATALOGO_PATH,
    COBERTURA_PATH,
    FEDERAL,
    FONTES_PATH,
    MATRIZ_PATH,
    PROVAS,
    camara_key,
    cmd_verify,
    convert_camara,
    identity_guards_ok,
    load_catalogo,
    load_fontes,
    published_path,
)


TARGET = [5, 6, 7, 8, 11, 13, 15, 16, 19, 20, 27, 29, 32, 33, 34, 35, 37, 41, 42, 43, 45]


class EmendasFaixa001050Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogo = load_catalogo()
        cls.fontes = load_fontes()
        cls.matriz = json.loads(MATRIZ_PATH.read_text())
        cls.cobertura = json.loads(COBERTURA_PATH.read_text())

    def test_catalogo_covers_target_only(self):
        nums = [i['numero'] for i in self.catalogo]
        self.assertEqual(nums, TARGET)

    def test_no_cf1988_duplicates_for_target(self):
        for item in self.catalogo:
            n = item['numero']
            hits = []
            for p in FEDERAL.glob('br-federal-emenda-constitucional-*.md'):
                m = re.fullmatch(
                    r'br-federal-emenda-constitucional-(\d{4})-\d{2}-\d{2}-(\d+)\.md',
                    p.name,
                )
                if m and int(m.group(1)) >= 1988 and int(m.group(2)) == n:
                    hits.append(p.name)
            self.assertEqual(
                hits,
                [published_path(item).name],
                f'EC {n} deve ter exatamente um arquivo CF/1988',
            )

    def test_historical_same_number_not_confused(self):
        # EC 5/1975 e EC 15/1980 existem e não são a série CF/1988
        hist5 = FEDERAL / 'br-federal-emenda-constitucional-1975-06-28-5.md'
        hist15 = FEDERAL / 'br-federal-emenda-constitucional-1980-11-19-15.md'
        self.assertTrue(hist5.is_file())
        self.assertTrue(hist15.is_file())
        self.assertTrue((FEDERAL / 'br-federal-emenda-constitucional-1995-08-15-5.md').is_file())
        self.assertTrue((FEDERAL / 'br-federal-emenda-constitucional-1996-09-12-15.md').is_file())

    def test_camara_snapshots_usable(self):
        for item in self.catalogo:
            rec = self.fontes[camara_key(item['numero'])]
            self.assertTrue(rec.get('utilizavel'), item['numero'])
            snap = ROOT / rec['snapshot']
            self.assertTrue(snap.is_file(), snap)

    def test_published_matches_reconversion(self):
        for item in self.catalogo:
            path = published_path(item)
            from nucleo_licitacoes import parse_frontmatter, sha256
            published = path.read_text(encoding='utf-8')
            meta, body = parse_frontmatter(published) if published.startswith('---\n') else ({}, published)
            if meta:
                self.assertEqual(meta['sha256_markdown'], sha256(body.encode('utf-8')))
            _blocks, body2 = convert_camara(item, self.fontes)
            self.assertEqual(body, body2, f'EC {item["numero"]} reconversão')
            self.assertEqual(identity_guards_ok(item, body), [])

    def test_cobertura_and_matriz_mark_published(self):
        for item in self.catalogo:
            n = str(item['numero'])
            self.assertTrue(self.cobertura[n]['ok'])
            self.assertTrue(self.cobertura[n]['coverage_blocos_markdown'])
            self.assertTrue(self.cobertura[n]['reconversao_identica'])
        situacoes = {r['situacao_coleta'] for r in self.matriz['itens']}
        self.assertEqual(situacoes, {'publicada'})
        self.assertFalse(any(r.get('vigencia_certificada') for r in self.matriz['itens']))

    def test_long_emendas_have_autonomous_articles(self):
        # EC 19/20/41/45 trazem dispositivos próprios além da redação inserida na CF
        for n in (19, 20, 41, 45):
            item = next(i for i in self.catalogo if i['numero'] == n)
            text = published_path(item).read_text(encoding='utf-8')
            self.assertRegex(text, r'(?i)entra em vigor')
            self.assertGreater(len(text), 5000)

    def test_verify_cli(self):
        self.assertEqual(cmd_verify(None), 0)

    def test_provas_layout(self):
        self.assertTrue(PROVAS.is_dir())
        self.assertTrue(FONTES_PATH.is_file())
        self.assertTrue(CATALOGO_PATH.is_file())
        self.assertTrue((PROVAS / 'fontes').is_dir())


if __name__ == '__main__':
    unittest.main()
