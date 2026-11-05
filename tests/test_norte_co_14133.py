"""Testes setoriais do recorte Norte/CO Lei 14.133 (#73/#101).

Offline. Execute: python3 -m unittest tests.test_norte_co_14133 -v
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import nucleo_licitacoes as nl  # noqa: E402
import norte_co_14133 as nc  # noqa: E402


class TestNorteCo14133(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = json.loads((ROOT / 'metadados/norte-co-14133/index.json').read_text(encoding='utf-8'))

    def test_verify_script_ok(self):
        self.assertEqual(nc.verify(), 0)

    def test_resumo_nao_usa_substring_geral(self):
        resumo = self.index['resumo']
        for uf in ['AP', 'MS', 'PA', 'RO', 'RR', 'GO']:
            row = next(u for u in self.index['ufs'] if u['uf'] == uf)
            if 'geral-publicado' not in row['status_acervo_estado']:
                self.assertNotIn(uf, resumo['ufs_com_geral_estado'])

    def test_ufs_com_geral_estado_esperado(self):
        self.assertEqual(set(self.index['resumo']['ufs_com_geral_estado']), {'AC', 'AM', 'MT', 'DF', 'TO'})

    def test_capitais_lo_ro_rr_am(self):
        self.assertIn('RO', self.index['resumo']['capitais_com_lo'])
        self.assertIn('RR', self.index['resumo']['capitais_com_lo'])
        self.assertIn('AM', self.index['resumo']['capitais_com_lo'])
        self.assertIn('AM', self.index['resumo']['capitais_com_decreto_geral'])

    def test_ac_11363_fold_e_nota(self):
        path = ROOT / 'estaduais/AC/br-ac-decreto-2023-11-22-11363.md'
        raw = path.read_text(encoding='utf-8')
        corpo = nl.strip_note(raw)
        self.assertRegex(corpo, r'11\.?363')
        self.assertGreater(len(nl.strip_fold(corpo)), 1000)
        fontes = json.loads((ROOT / 'provas/norte-co-14133/AC/fontes.json').read_text(encoding='utf-8'))
        md_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertTrue(any(f.get('sha256_markdown') == md_sha for f in fontes['fontes']))

    def test_porto_velho_lo_artigos(self):
        path = ROOT / 'municipais/1100205/br-municipal-1100205-lei-organica-1990-03-27.md'
        corpo = nl.strip_note(path.read_text(encoding='utf-8'))
        arts = len(re.findall(r'(?m)^Art\.\s*\d+', corpo))
        self.assertGreaterEqual(arts, 40)
        self.assertIn('PREÂMBULO', corpo.upper())

    def test_boa_vista_lo_artigos(self):
        path = ROOT / 'municipais/1400100/br-municipal-1400100-lei-organica-1992-07-11.md'
        corpo = nl.strip_note(path.read_text(encoding='utf-8'))
        arts = len(re.findall(r'(?m)^Art\.\s*\d+', corpo))
        self.assertGreaterEqual(arts, 40)

    def test_srp_nao_marcado_como_geral(self):
        for uf in ['AP', 'MS']:
            row = next(u for u in self.index['ufs'] if u['uf'] == uf)
            self.assertEqual(row['status_acervo_estado'], 'decreto-especifico-sem-geral')
            self.assertTrue(row['decretos_14133_estado'][0]['carater'].startswith('especifico'))

    def test_df_fora_criterio_municipal(self):
        df = next(u for u in self.index['ufs'] if u['uf'] == 'DF')
        self.assertEqual(df['lei_organica_capital'], 'fora-criterio-df')
        self.assertTrue((ROOT / df['lei_organica_df']).is_file())

    def test_to_6606_publicado_colunas(self):
        path = ROOT / 'estaduais/TO/br-to-decreto-2023-03-28-6606.md'
        raw = path.read_text(encoding='utf-8')
        corpo = nl.strip_note(raw)
        self.assertRegex(corpo, r'6\.606')
        self.assertRegex(corpo, r'14\.133')
        arts = len(re.findall(r'(?m)^\s*Art\.\s*\d+', corpo))
        self.assertGreaterEqual(arts, 300)
        self.assertIn('WANDERLEI BARBOSA CASTRO', corpo)
        fontes = json.loads((ROOT / 'provas/norte-co-14133/TO/fontes.json').read_text(encoding='utf-8'))
        self.assertEqual(fontes['fontes'][0]['resultado'], 'publicado-colunas-coordenadas')
        self.assertEqual(len(fontes['fontes'][0]['sha256_pdf_original']), 64)
        md_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertTrue(any(f.get('sha256_markdown') == md_sha for f in fontes['fontes']))

    def test_manaus_5525_geral_nao_mistura_5524(self):
        path = ROOT / 'municipais/1302603/br-municipal-1302603-decreto-2023-03-28-5525.md'
        corpo = nl.strip_note(path.read_text(encoding='utf-8'))
        self.assertRegex(corpo, r'5\.525')
        self.assertRegex(corpo, r'14\.133')
        self.assertNotRegex(corpo, r'(?i)cr[eé]dito extraordin[aá]rio')
        arts = len(re.findall(r'(?m)^\s*Art\.\s*\d+', corpo))
        self.assertGreaterEqual(arts, 70)
        fontes = json.loads((ROOT / 'provas/norte-co-14133/AM-manaus-5525/fontes.json').read_text(encoding='utf-8'))
        self.assertEqual(fontes['fontes'][0]['resultado'], 'publicado-colunas-coordenadas')

    def test_loman_artigos(self):
        path = ROOT / 'municipais/1302603/br-municipal-1302603-lei-organica.md'
        corpo = nl.strip_note(path.read_text(encoding='utf-8'))
        self.assertTrue(re.search(r'PRE[ÂA]MBULO|N[oó]s,\s*representantes', corpo, re.I))
        arts = len(set(re.findall(r'(?m)^\s*Art\.\s*(\d+)', corpo)))
        self.assertGreaterEqual(arts, 200)
        fontes = json.loads((ROOT / 'provas/norte-co-14133/AM-manaus-lo/fontes.json').read_text(encoding='utf-8'))
        self.assertEqual(fontes['fontes'][0]['resultado'], 'publicado-layout-monopagina')

    def test_srp_ainda_nao_geral(self):
        for uf in ['AP', 'MS']:
            self.assertNotIn(uf, self.index['resumo']['ufs_com_geral_estado'])


if __name__ == '__main__':
    unittest.main()
