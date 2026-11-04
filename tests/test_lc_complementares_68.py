"""Cobertura por identidade — LC 115/2002, LC 147/2014 e LC 1/1962 (issue #68)."""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVAS = ROOT / 'provas/lc-complementares-68'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
RECON = json.loads((PROVAS / 'reconciliacao-identidades.json').read_text(encoding='utf-8'))

IDS = {
    '115': 'br-federal-lei-complementar-2002-12-26-115',
    '147': 'br-federal-lei-complementar-2014-08-07-147',
    '1-1962': 'br-federal-lei-complementar-1962-07-17-1',
    '1-1967': 'br-federal-lei-complementar-1967-11-09-1',
}


class TestLcComplementares68(unittest.TestCase):
    def test_arquivos_publicados(self):
        for key, slug in IDS.items():
            path = ROOT / 'federal' / f'{slug}.md'
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding='utf-8')
            self.assertGreater(len(text), 500)
            if key != '1-1967':
                self.assertFalse(text.startswith('---\n'), 'publicação sem YAML do coletor')

    def test_identidades_distintas_lc1(self):
        a = (ROOT / f'federal/{IDS["1-1962"]}.md').read_text(encoding='utf-8')
        b = (ROOT / f'federal/{IDS["1-1967"]}.md').read_text(encoding='utf-8')
        self.assertIn('1962', a)
        self.assertIn('1967', b)
        self.assertIn('parlamentar', a.lower())
        self.assertIn('município', b.lower())
        self.assertNotEqual(
            hashlib.sha256(a.encode()).hexdigest(),
            hashlib.sha256(b.encode()).hexdigest(),
        )

    def test_hashes_senado_115_147(self):
        for slug in (IDS['115'], IDS['147']):
            meta = FONTES[slug]
            pub = (ROOT / 'federal' / f'{slug}.md').read_bytes()
            body = pub[:-1] if pub.endswith(b'\n') else pub
            self.assertEqual(hashlib.sha256(body).hexdigest(), meta['sha256_markdown'])
            html = lzma.decompress((ROOT / meta['snapshot_html']).read_bytes())
            self.assertEqual(hashlib.sha256(html).hexdigest(), meta['sha256_fonte'])
            dados = lzma.decompress((ROOT / meta['snapshot_dados']).read_bytes())
            self.assertEqual(hashlib.sha256(dados).hexdigest(), meta['sha256_dados'])

    def test_lc1_1962_planalto_snapshot(self):
        meta = FONTES[IDS['1-1962']]
        raw = lzma.decompress((ROOT / meta['snapshot_html']).read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta['sha256_fonte'])
        pub = (ROOT / f'federal/{IDS["1-1962"]}.md').read_bytes()
        self.assertEqual(hashlib.sha256(pub).hexdigest(), meta['sha256_markdown'])
        self.assertIn(b'LEI COMPLEMENTAR', pub[:200])
        self.assertIn(b'1962', pub[:200])

    def test_reconciliacao_catalogo(self):
        ids = {i['id'] for i in RECON['identidades']}
        self.assertEqual(ids, set(IDS.values()))
        by = {i['id']: i for i in RECON['identidades']}
        self.assertEqual(by[IDS['115']]['estado'], 'publicado')
        self.assertEqual(by[IDS['147']]['estado'], 'publicado')
        self.assertEqual(by[IDS['1-1962']]['estado'], 'publicado')
        self.assertEqual(by[IDS['1-1967']]['estado'], 'ja-publicado-antes')
        self.assertEqual(by[IDS['1-1962']]['senadoId'], '30812083')
        self.assertIn('não fundir', by[IDS['1-1967']]['fonte'].lower())

    def test_cobertura_por_numero_no_federal(self):
        names = [p.name for p in (ROOT / 'federal').iterdir() if p.suffix == '.md']
        for number, slug in [('115', IDS['115']), ('147', IDS['147'])]:
            hits = [
                n for n in names
                if n.startswith('br-federal-lei-complementar-')
                and re.search(r'-' + number + r'(?:-|\.md)', n)
            ]
            self.assertIn(slug + '.md', hits)
        hits_1 = [
            n for n in names
            if n.startswith('br-federal-lei-complementar-')
            and re.search(r'-1(?:-|\.md)', n)
        ]
        self.assertIn(IDS['1-1962'] + '.md', hits_1)
        self.assertIn(IDS['1-1967'] + '.md', hits_1)

    def test_lista_lcp_snapshot(self):
        cat = RECON['catalogo_senado_lista']
        snap = ROOT / cat['snapshot']
        self.assertTrue(snap.is_file())
        raw = lzma.decompress(snap.read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), cat['sha256'])
        data = json.loads(raw)
        self.assertIn('ListaDocumento', data)


if __name__ == '__main__':
    unittest.main()
