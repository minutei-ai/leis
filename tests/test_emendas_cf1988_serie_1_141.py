"""Cobertura por identidade da série Emendas CF/1988 nº 1–141 (issue #63)."""
from __future__ import annotations

import json
import hashlib
import lzma
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
        self.assertEqual(ids['textos-integrais-com-dispositivos-autonomos']['estado'], 'satisfeito')
        self.assertEqual(ids['classificacao-literal-sem-inferencia']['estado'], 'parcial')
        self.assertEqual(ids['conferencia-atual-das-edicoes-sem-substituicao']['estado'], 'satisfeito')
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
        all_articles = [a for item in mapa['itens'] for a in item.get('dispositivos_do_ato', [])]
        self.assertTrue(all(a.get('trecho_auditado') and a.get('regra_classificacao') for a in all_articles))
        self.assertTrue(all(
            a['hierarquia'] == 'texto-exterior-a-citacao'
            for a in all_articles if a['papel'] in {
                'altera-cf-ou-adct', 'producao-efeitos-ou-vigencia-textual',
                'revogacao', 'proibicao-autonoma', 'transitorio-autonomo',
            }
        ))
        self.assertTrue(all(
            a['hierarquia'] == 'revisao-explicita-sem-inferencia-de-efeito'
            for a in all_articles if a['papel'] == 'dispositivo-autonomo-regra-nao-classificada'
        ))
        review = [a for a in all_articles if a['papel'] == 'dispositivo-autonomo-regra-nao-classificada']
        self.assertEqual(len(review), 177)
        self.assertTrue(all(a.get('trecho_auditado') and a.get('regra_classificacao') for a in review))
        ec31 = next(i for i in mapa['itens'] if i['emenda'] == 31)
        main_labels = [a['dispositivo'] for a in ec31['dispositivos_do_ato']]
        self.assertEqual(main_labels, ['Art. 1º', 'Art. 2º'])
        self.assertEqual(
            [a['dispositivo'] for a in ec31['dispositivos_do_ato'][0]['redacao_inserida_citada']],
            ['Art. 79', 'Art. 80', 'Art. 81', 'Art. 82', 'Art. 83'],
        )

    def test_conferencias_oficiais_cobrem_serie_sem_substituir_legados(self):
        self.assertEqual(lote.load_reconciled_source_numbers(), set(range(1, 142)))
        fontes = PROVAS / 'fontes-conferencia'
        manifesto = json.loads((fontes / 'fontes-conferencia-legados-1-106.json').read_text(encoding='utf-8'))
        reconciliacao = json.loads((fontes / 'reconciliacao-artigos-legados-1-106.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifesto['fontes']), 54)
        self.assertEqual(reconciliacao['resumo']['emendas_conferidas'], 55)
        comparisons = {item['emenda']: item for item in reconciliacao['items']}
        ec1 = comparisons[1]
        self.assertEqual(ec1['artigos_markdown'], 3)
        self.assertEqual(ec1['artigos_fonte'], 3)
        self.assertEqual(
            {part['componente'] for part in ec1['componentes_comparados']},
            {'epigrafe', 'ementa', 'preambulo', 'Art. 1', 'Art. 2', 'Art. 3', 'fecho', 'assinaturas'},
        )
        self.assertTrue(all(part['sha256_markdown_normalizado'] and part['sha256_fonte_normalizado'] for part in ec1['componentes_comparados']))
        self.assertTrue(all(part['proveniencia_original_markdown'] == 'desconhecida' for part in manifesto['fontes']))

        # These labels were false article-level mismatches from source text inside quoted insertions.
        ec23 = comparisons[23]
        self.assertEqual(ec23['artigos_fonte_principais'], ['1', '2'])
        self.assertEqual(ec23['apenas_markdown'], [])
        self.assertEqual(ec23['apenas_fonte'], [])
        self.assertEqual(
            ec23['redacoes_inseridas_citadas_repareadas'][0]['rotulo_citado'],
            'Art. 91',
        )
        self.assertTrue(all(x['sequencia_coincide'] for x in ec23['diagnostico_de_tokens_lexicais']['comparacoes']))
        ec30 = comparisons[30]
        self.assertEqual(ec30['artigos_fonte_principais'], ['1', '2', '3'])
        self.assertEqual(ec30['apenas_markdown'], [])
        self.assertEqual(ec30['apenas_fonte'], [])
        self.assertEqual(
            ec30['redacoes_inseridas_citadas_repareadas'][0]['sob_dispositivo_principal'],
            'Art. 2º',
        )
        self.assertTrue(all(x['sequencia_coincide'] for x in ec30['diagnostico_de_tokens_lexicais']['comparacoes']))
        self.assertIn('não afirma igualdade literal', ec30['diagnostico_de_tokens_lexicais']['limite'])


    def test_segmentacao_artigos_ec9_ec12_ec44_e_proibicoes_autonomas(self):
        expected_articles = {
            9: ['Art. 1º', 'Art. 2º', 'Art. 3º'],
            12: ['Art. Único'],
            44: ['Art. 1º', 'Art. 2º'],
        }
        by_number = {item['numero']: item for item in self.matriz['itens']}
        extracted = {}
        for number, expected in expected_articles.items():
            body = lote.body_of((ROOT / by_number[number]['arquivo']).read_text(encoding='utf-8'))
            extracted[number] = lote.extract_dispositivos_emenda(body)
            self.assertEqual(
                [a['dispositivo'] for a in extracted[number]['artigos']],
                expected,
                f'EC {number} article heads must survive source indentation and inline HTML',
            )
        # Article 8(2) and EC 9(3) state standalone MP prohibitions. EC 7(2)
        # contains similar wording only inside the CF art. 246 insertion.
        all_bodies = {}
        for number in (7, 8):
            body = lote.body_of((ROOT / by_number[number]['arquivo']).read_text(encoding='utf-8'))
            all_bodies[number] = lote.extract_dispositivos_emenda(body)
        ec7 = all_bodies[7]
        self.assertEqual([a['dispositivo'] for a in ec7['artigos']], ['Art. 1º', 'Art. 2º'])
        self.assertEqual([a['dispositivo'] for a in ec7['artigos'][0]['redacao_inserida_citada']], ['Art. 178'])
        self.assertEqual([a['dispositivo'] for a in ec7['artigos'][1]['redacao_inserida_citada']], ['Art. 246'])
        ec9_art3 = next(a for a in extracted[9]['artigos'] if a['dispositivo'] == 'Art. 3º')
        ec8_art2 = next(a for a in all_bodies[8]['artigos'] if a['dispositivo'] == 'Art. 2º')
        ec7_art2 = next(a for a in all_bodies[7]['artigos'] if a['dispositivo'] == 'Art. 2º')
        self.assertEqual(ec9_art3['papel'], 'proibicao-autonoma')
        self.assertEqual(ec8_art2['papel'], 'proibicao-autonoma')
        self.assertNotEqual(ec7_art2['papel'], 'proibicao-autonoma')
        autonomes9 = lote.extract_dispositivos_autonomos(extracted[9])
        autonomes8 = lote.extract_dispositivos_autonomos(all_bodies[8])
        autonomes7 = lote.extract_dispositivos_autonomos(all_bodies[7])
        self.assertIn('Art. 3º', [a['dispositivo'] for a in autonomes9])
        self.assertIn('Art. 2º', [a['dispositivo'] for a in autonomes8])
        self.assertNotIn('Art. 2º', [a['dispositivo'] for a in autonomes7])
        self.assertEqual(
            next(a['papel'] for a in extracted[44]['artigos'] if a['dispositivo'] == 'Art. 2º'),
            'producao-efeitos-ou-vigencia-textual',
        )

    def test_hierarquia_ec2_ec24_ec31_sem_default_de_efeito(self):
        by_number = {item['numero']: item for item in self.matriz['itens']}
        bodies = {
            n: lote.body_of((ROOT / by_number[n]['arquivo']).read_text(encoding='utf-8'))
            for n in (2, 10, 24, 31)
        }
        ec2 = lote.extract_dispositivos_emenda(bodies[2])
        ec10 = lote.extract_dispositivos_emenda(bodies[10])
        ec24 = lote.extract_dispositivos_emenda(bodies[24])
        ec31 = lote.extract_dispositivos_emenda(bodies[31])
        self.assertEqual([a['dispositivo'] for a in ec2['artigos']], ['Art. único'])
        self.assertEqual([a['dispositivo'] for a in ec10['artigos']], ['Art. 1°', 'Art. 2°', 'Art. 3°'])
        self.assertEqual([a['dispositivo'] for a in ec10['artigos'][0]['redacao_inserida_citada']], ['Art. 71'])
        self.assertEqual([a['dispositivo'] for a in ec10['artigos'][1]['redacao_inserida_citada']], ['Art. 72'])
        self.assertEqual([a['dispositivo'] for a in ec24['artigos']], ['Art. 1º', 'Art. 2º', 'Art. 3º', 'Art. 4º'])
        self.assertEqual([a['dispositivo'] for a in ec31['artigos']], ['Art. 1º', 'Art. 2º'])
        ec31_art1 = ec31['artigos'][0]
        self.assertEqual(ec31_art1['papel'], 'altera-cf-ou-adct')
        self.assertEqual(
            [a['dispositivo'] for a in ec31_art1['redacao_inserida_citada']],
            ['Art. 79', 'Art. 80', 'Art. 81', 'Art. 82', 'Art. 83'],
        )
        self.assertTrue(all(a['papel'] == 'texto-de-redacao-inserida-citada' for a in ec31_art1['redacao_inserida_citada']))
        ec24_article1 = next(a for a in ec24['artigos'] if a['dispositivo'] == 'Art. 1º')
        ec24_article2 = next(a for a in ec24['artigos'] if a['dispositivo'] == 'Art. 2º')
        self.assertEqual(ec24_article1['papel'], 'altera-cf-ou-adct')
        self.assertIn('passam a vigorar', ec24_article1['regra_classificacao'])
        for item in [ec2['artigos'][0], ec24_article2]:
            self.assertEqual(item['papel'], 'dispositivo-autonomo-regra-nao-classificada')
            self.assertEqual(item['hierarquia'], 'revisao-explicita-sem-inferencia-de-efeito')
            self.assertTrue(item['trecho_auditado'])
            self.assertTrue(item['regra_classificacao'])

        # Inserted Constitution/ADCT text remains nested under its amendment article.
        ec23 = lote.extract_dispositivos_emenda(
            lote.body_of((ROOT / next(i['arquivo'] for i in self.matriz['itens'] if i['numero'] == 23)).read_text())
        )
        ec30 = lote.extract_dispositivos_emenda(
            lote.body_of((ROOT / next(i['arquivo'] for i in self.matriz['itens'] if i['numero'] == 30)).read_text())
        )
        self.assertEqual([a['dispositivo'] for a in ec23['artigos']], ['Art. 1º', 'Art. 2º'])
        self.assertIn('Art. 91', [a['dispositivo'] for a in ec23['artigos'][0]['redacao_inserida_citada']])
        self.assertEqual([a['dispositivo'] for a in ec30['artigos']], ['Art. 1º', 'Art. 2º', 'Art. 3º'])
        self.assertEqual([a['dispositivo'] for a in ec30['artigos'][1]['redacao_inserida_citada']], ['Art. 78'])

    def test_conferencias_atuais_preservam_proveniencia_original_desconhecida(self):
        conf_dir = PROVAS / 'fontes-conferencia'
        fontes = json.loads((conf_dir / 'fontes-conferencia.json').read_text(encoding='utf-8'))
        reconciliacao = json.loads((conf_dir / 'reconciliacao-artigos.json').read_text(encoding='utf-8'))
        self.assertEqual([f['emenda'] for f in fontes['fontes']], [9, 12, 44])
        expected_devices = {
            9: ['Art. 1º', 'Art. 2º', 'Art. 3º'],
            12: ['Artigo único'],
            44: ['Art. 1º', 'Art. 2º'],
        }
        expected_literal_equality = {9: [False, False, True], 12: [False], 44: [True, True]}
        comparisons = {item['emenda']: item for item in reconciliacao['items']}
        for fonte in fontes['fontes']:
            with self.subTest(emenda=fonte['emenda']):
                snapshot = ROOT / fonte['snapshot']
                self.assertTrue(snapshot.is_file())
                stored = snapshot.read_bytes()
                self.assertEqual(hashlib.sha256(stored).hexdigest(), fonte['sha256_snapshot_armazenado'])
                raw = lzma.decompress(stored)
                self.assertEqual(len(raw), fonte['bytes_fonte'])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), fonte['sha256_fonte'])
                self.assertEqual(fonte['proveniencia_original_markdown'], 'desconhecida')
                comparison = comparisons[fonte['emenda']]
                self.assertEqual(
                    [item['dispositivo'] for item in comparison['artigos_comparados']],
                    expected_devices[fonte['emenda']],
                )
                self.assertEqual(
                    [item['igual_literal'] for item in comparison['artigos_comparados']],
                    expected_literal_equality[fonte['emenda']],
                )
                markdown = ROOT / comparison['arquivo_markdown']
                metadata = lote.parse_frontmatter(markdown.read_text(encoding='utf-8'))
                self.assertEqual(metadata['fonte_url'], 'desconhecido')
                self.assertEqual(metadata['capturado_em'], 'desconhecido')
                self.assertEqual(metadata['sha256_fonte'], 'desconhecido')
                self.assertNotEqual(metadata['fonte_conferencia'], 'desconhecido')


if __name__ == '__main__':
    unittest.main()
