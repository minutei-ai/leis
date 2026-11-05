"""Cobertura por identidade da série Emendas CF/1988 nº 1–141 (issue #63)."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import emendas_cf1988_serie_1_141 as lote  # noqa: E402

PROVAS = ROOT / 'provas/emendas-cf1988/serie-1-141'
MATRIZ = PROVAS / 'matriz-serie.json'
CRITERIOS = PROVAS / 'matriz-criterios-aceite.json'
FED = ROOT / 'federal'


class TestEmendasCf1988Serie1141(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matriz = json.loads(MATRIZ.read_text(encoding='utf-8'))
        cls.criterios = json.loads(CRITERIOS.read_text(encoding='utf-8'))
        cls.fresh = lote.scan()
        cls.fresh.pop('criterios')

    def test_matriz_completa_1_a_141(self):
        self.assertEqual(self.matriz['lote'], lote.LOTE)
        self.assertEqual(self.matriz['issue'], 63)
        self.assertEqual(self.matriz['numeros_alvo'], list(range(1, 142)))
        self.assertEqual(self.matriz['lacunas'], [])
        self.assertEqual(self.matriz['contagem']['publicados'], 141)
        self.assertEqual(self.matriz['recuperados'], list(range(1, 142)))
        self.assertEqual(self.matriz['recuperados'], self.fresh['recuperados'])
        self.assertEqual(self.matriz['lacunas'], self.fresh['lacunas'])

    def test_arquivos_publicados_sao_serie_cf1988(self):
        for item in self.matriz['itens']:
            with self.subTest(numero=item['numero']):
                path = ROOT / item['arquivo']
                self.assertTrue(path.is_file(), path)
                self.assertNotIn('revisao', path.name.lower())
                m = re.fullmatch(
                    r'federal/br-federal-emenda-constitucional-(\d{4})-\d{2}-\d{2}-(\d+)\.md',
                    item['arquivo'],
                )
                self.assertIsNotNone(m)
                self.assertGreaterEqual(int(m.group(1)), 1988)
                self.assertEqual(int(m.group(2)), item['numero'])
                self.assertEqual(item['serie'], 'cf-1988')
                self.assertTrue(item['nao_e_revisao'])
                self.assertTrue(item['nao_e_constituicao_historica'])
                self.assertGreater(item['tamanho_corpo'], 200)

    def test_historicas_e_revisao_fora_da_serie(self):
        for hist in self.matriz['emendas_historicas_no_acervo_nao_contam_nesta_serie']:
            self.assertLess(int(hist['data'][:4]), 1988)
            self.assertTrue((ROOT / hist['arquivo']).is_file())
        self.assertEqual(self.matriz['emendas_revisao_no_acervo'], [])
        # Constituição consolidada não conta como emenda coletada.
        constituicao = FED / 'br-federal-constituicao-1988-10-05.md'
        self.assertTrue(constituicao.is_file())
        ids = {item['arquivo'] for item in self.matriz['itens']}
        self.assertNotIn('federal/br-federal-constituicao-1988-10-05.md', ids)

    def test_provas_de_faixa_existem(self):
        for rel in (
            'provas/emendas-cf1988/faixa-001-050/',
            'provas/emendas-cf1988/faixa-051-100/',
            'provas/emendas-cf1988/faixa-101-141/',
        ):
            self.assertTrue((ROOT / rel).is_dir(), rel)
        self.assertEqual(
            self.matriz['lotes_faixa_preexistentes']['prs_merged'],
            lote.PRS,
        )

    def test_criterios_aceite_nao_fecham_issue_so_com_contagem(self):
        self.assertEqual(self.criterios['issue'], 63)
        self.assertFalse(self.criterios['resumo']['issue_fechavel'])
        ids = {c['id']: c for c in self.criterios['itens']}
        self.assertIn('vinculos-constituicao-adct', ids)
        self.assertIn('textos-integrais-com-dispositivos-autonomos', ids)
        self.assertIn('metadados-edicao-fonte-hashes', ids)
        self.assertEqual(ids['matriz-por-numero-data-fonte-situacao']['estado'], 'satisfeito')
        self.assertEqual(ids['nao-recontar-consolidada']['estado'], 'satisfeito')
        self.assertEqual(ids['vinculos-constituicao-adct']['estado'], 'satisfeito')
        self.assertEqual(ids['metadados-edicao-fonte-hashes']['estado'], 'satisfeito')
        # Contagem sozinha não fecha: issue_fechavel permanece false.
        self.assertGreaterEqual(self.criterios['resumo']['satisfeitos'], 5)

    def test_vinculos_constituicao_registrados(self):
        vin = self.matriz['vinculos_constituicao']
        self.assertEqual(vin['estado'], 'registrado-com-mapa')
        self.assertTrue((ROOT / vin['constituicao_arquivo']).is_file())
        self.assertGreaterEqual(len(vin['emendas_citadas_na_constituicao']), 50)
        self.assertEqual(vin['citadas_sem_arquivo_autonomo'], [])

    def test_corpo_nao_e_so_placeholder(self):
        """Detecção semântica mínima: o Markdown precisa conter a epígrafe da emenda."""
        for numero in (19, 45, 95, 132, 141):
            item = next(i for i in self.matriz['itens'] if i['numero'] == numero)
            text = (ROOT / item['arquivo']).read_text(encoding='utf-8')
            body = lote.body_of(text)
            self.assertRegex(body, re.compile(rf'EMENDA CONSTITUCIONAL Nº\s*{numero}\b', re.I))
            # Corromper artificialmente todas as ocorrências do número deve ser detectável.
            corrupted = re.sub(rf'(EMENDA CONSTITUCIONAL\s+N[ºo°\.]*)\s*{numero}\b', r'\1 XXX', body, flags=re.I)
            self.assertIsNone(re.search(rf'EMENDA CONSTITUCIONAL Nº\s*{numero}\b', corrupted, re.I))
            self.assertRegex(corrupted, re.compile(r'EMENDA CONSTITUCIONAL Nº\s*XXX\b', re.I))


    def test_frontmatter_contrato_em_toda_serie(self):
        for item in self.matriz['itens']:
            with self.subTest(numero=item['numero']):
                text = (ROOT / item['arquivo']).read_text(encoding='utf-8')
                self.assertTrue(text.startswith('---\n'))
                meta = lote.parse_frontmatter(text)
                body = lote.body_of(text)
                self.assertEqual(meta.get('contrato_versao'), 1)
                self.assertIs(meta.get('vigencia_certificada'), False)
                self.assertEqual(meta.get('sha256_markdown'), lote.sha256_text(body))
                self.assertTrue(item['tem_frontmatter'])

    def test_mapa_constituicao_adct_dispositivos(self):
        mapa_path = PROVAS / 'mapa-constituicao-adct-dispositivos.json'
        self.assertTrue(mapa_path.is_file())
        mapa = json.loads(mapa_path.read_text(encoding='utf-8'))
        self.assertEqual(mapa['issue'], 63)
        self.assertEqual(mapa['contagem']['emendas'], 141)
        self.assertEqual(len(mapa['itens']), 141)
        self.assertEqual(
            self.matriz['vinculos_constituicao']['estado'],
            'registrado-com-mapa',
        )
        # Escopo literal do issue: vínculo ato/dispositivos; sem mapa CF inteira.
        self.assertTrue(any('dispositivo-a-dispositivo' in x or 'literal' in mapa.get('escopo', '').lower() for x in mapa['limites']))
        sample = next(i for i in mapa['itens'] if i['emenda'] == 19)
        self.assertEqual(sample['estado'], 'mapeado')
        self.assertTrue(sample['arquivo'])
        self.assertTrue(isinstance(sample.get('dispositivos_do_ato'), list))


if __name__ == '__main__':
    unittest.main()
