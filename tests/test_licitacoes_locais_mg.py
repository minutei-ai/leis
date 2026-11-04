"""Testes do catálogo MG de licitações locais (Decreto BH 18.289 / issue #57).

Offline: lê somente o repositório. Execute:
  python3 -m unittest tests.test_licitacoes_locais_mg -v
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import licitacoes_locais_mg as mg  # noqa: E402

MD = 'municipais/3106200/br-municipal-3106200-decreto-2023-03-28-18289.md'
CAT = 'metadados/licitacoes-locais/MG.json'
ESTADUAL = 'estaduais/MG/br-mg-decreto-2023-11-24-48723.md'


class TestLicitacoesLocaisMG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = json.loads((ROOT / CAT).read_text(encoding='utf-8'))
        cls.md = (ROOT / MD).read_text(encoding='utf-8')
        cls.corpo = mg.strip_note(cls.md)

    def test_verify_script_ok(self):
        mg.verify()

    def test_markdown_tem_48_artigos_e_ambito_literal(self):
        arts = re.findall(r'^Art\.\s*(\d+)', self.corpo, re.M)
        self.assertEqual(arts, [str(i) for i in range(1, 49)])
        self.assertIn(
            'administração municipal direta e indireta e das entidades vinculadas ou controladas direta ou indiretamente pelo Poder Executivo',
            self.corpo,
        )
        self.assertIn('empresas públicas, as sociedades de economia mista e suas subsidiárias', self.corpo)
        self.assertIn('Lei Federal nº 10.520, de 17 de junho de 2001', self.corpo)
        self.assertIn('Lei Federal nº 12.462, de 4 de agosto de 2011', self.corpo)
        self.assertIn('Fuad Noman', self.corpo)
        self.assertIn('Belo Horizonte, 28 de março de 2023', self.corpo)

    def test_corpo_hash_e_cobertura_fold(self):
        self.assertEqual(hashlib.sha256(self.corpo.encode()).hexdigest(), mg.SHA256_CORPO)
        html = lzma.open(ROOT / 'provas/licitacoes-locais/MG/fontes/conteudoAto_id200561.html.xz').read()
        self.assertEqual(hashlib.sha256(html).hexdigest(), mg.SHA256_HTML)
        recon = mg.html_to_corpo(html)
        self.assertEqual(recon, self.corpo)

    def test_fonte_completa_para_markdown_byte_a_byte(self):
        """Reconversão do HTML integral deve coincidir com o corpo publicado inteiro."""
        html = lzma.open(ROOT / 'provas/licitacoes-locais/MG/fontes/conteudoAto_id200561.html.xz').read()
        recon = mg.html_to_corpo(html)
        self.assertEqual(recon, self.corpo)
        self.assertEqual(hashlib.sha256(recon.encode()).hexdigest(), mg.SHA256_CORPO)
        # Não basta checar sentinelas: o corpo inteiro (48 arts + encerramento) entra no hash.
        self.assertGreater(len(self.corpo), 10_000)
        self.assertTrue(self.corpo.startswith('DECRETO Nº 18.289, DE 28 DE MARÇO DE 2023.'))
        self.assertTrue(self.corpo.rstrip().endswith('Prefeito de Belo Horizonte'))
        # Erro de fonte no art. 47 (citação da Lei 10.520) permanece literal; não "corrigir".
        self.assertIn('Lei Federal nº 10.520, de 17 de junho de 2001', self.corpo)

    def test_separa_data_ato_e_publicacao_dom(self):
        note = self.md[: self.md.find('<!-- nota-edicao:fim -->')]
        self.assertIn('ato de 28/03/2023', note)
        self.assertIn('publicada em 29/03/2023', note)
        self.assertNotIn('publicação do DOM (28/03/2023)', note)
        self.assertNotIn('publicação DOM de 28/03/2023', note)
        # Corpo normativo mantém a data do ato; publicação DOM fica só na nota/metadados.
        self.assertIn('Belo Horizonte, 28 de março de 2023', self.corpo)
        self.assertNotIn('29/03/2023', self.corpo)
        self.assertNotIn('29 de março de 2023', self.corpo)

        edicao = json.loads(
            (ROOT / 'provas/licitacoes-locais/MG/fontes/dom-edicao-6824.json').read_text(encoding='utf-8')
        )
        ed = edicao['data']
        self.assertEqual(ed['numero_edicao'], 6730)
        self.assertEqual(ed['dt_publicacao'], '2023-03-29')

        cob = json.loads((ROOT / 'provas/licitacoes-locais/MG/cobertura-18289.json').read_text(encoding='utf-8'))
        limites = '\n'.join(cob['limites'])
        self.assertIn('data do ato 28/03/2023', limites)
        self.assertIn('29/03/2023', limites)
        self.assertNotIn('publicação DOM de 28/03/2023', limites)

        doc = self.cat['documentos'][0]
        self.assertIn('assinatura 28/03/2023', doc['edicao']['descricao'])
        self.assertIn('2023-03-29', doc['edicao']['descricao'])

    def test_catalogo_separa_estado_e_municipio(self):
        self.assertEqual(self.cat['uf'], 'MG')
        self.assertEqual(self.cat['cobertura'], 'parcial')
        doc = self.cat['documentos'][0]
        self.assertEqual(doc['ibge'], '3106200')
        self.assertEqual(doc['ente']['tipo'], 'municipio')
        self.assertEqual(doc['fonte']['ato_dom_id'], 200561)
        self.assertIs(doc['vigencia_certificada'], False)
        self.assertTrue(doc['edicao']['integral'])
        self.assertEqual(doc['edicao']['tipo'], 'historica')
        self.assertIn('nao-incorporadas', doc['edicao']['alteracoes_posteriores']['estado'])
        ambito = doc['ambito']
        self.assertIn('direta', ambito['administracao'])
        self.assertEqual(ambito['nao_e'], 'localização do fornecedor')
        self.assertEqual(ambito['adesao']['natureza'], 'facultativa-no-que-couber')

        reut = self.cat['reutilizados'][0]
        self.assertEqual(reut['ente']['tipo'], 'estado')
        self.assertEqual(reut['arquivo'], ESTADUAL)
        self.assertEqual(reut['edicao_integral'], 'desconhecido')
        self.assertTrue((ROOT / ESTADUAL).is_file())
        # sem duplicar o estadual como documento novo
        self.assertNotEqual(doc['norma_id'], reut['norma_id'])

    def test_pendencias_candidatos_complementares_publicados(self):
        pend = self.cat['pendencias']
        cand = next(p for p in pend if p['id'] == 'bh-candidatos-complementares')
        self.assertEqual(cand['tipo'], 'recuperacao-integral-concluida-parcial')
        publicados = [p.name for p in (ROOT / 'municipais/3106200').glob('*.md')]
        self.assertTrue(any('decreto-2023-03-28-18289' in n for n in publicados))
        for num in ('17813', '18096', '18240', '18242'):
            self.assertTrue(any(num in n for n in publicados), num)
        ids = {d['norma_id'] for d in self.cat['documentos']}
        for nid in cand['itens_publicados']:
            self.assertIn(nid, ids)
            doc = next(d for d in self.cat['documentos'] if d['norma_id'] == nid)
            self.assertTrue((ROOT / doc['arquivo']).is_file())
            self.assertIs(doc['vigencia_certificada'], False)
            cob = ROOT / doc['provas']['cobertura']
            self.assertTrue(cob.is_file(), cob)

    def test_negativo_nao_confundir_com_estadual_nem_inventar_vigencia(self):
        doc = self.cat['documentos'][0]
        self.assertNotEqual(doc['arquivo'], ESTADUAL)
        self.assertIs(doc['vigencia_certificada'], False)
        self.assertEqual(doc['situacao'], 'nao-informada')
        self.assertIn('html_ato', doc['hashes'])
        self.assertEqual(len(doc['hashes']['html_ato']), 64)
        self.assertNotEqual(doc['hashes']['html_ato'], doc.get('ementa_catalogo_pgm', ''))

    def test_provas_fontes_presentes(self):
        fontes = json.loads((ROOT / 'provas/licitacoes-locais/MG/fontes.json').read_text(encoding='utf-8'))
        for f in fontes['fontes']:
            rel = f['arquivo']
            self.assertTrue((ROOT / rel).is_file(), rel)
            if rel.endswith('.xz'):
                self.assertEqual(f.get('sha256_conteudo'), hashlib.sha256(lzma.open(ROOT / rel).read()).hexdigest(), rel)
            else:
                self.assertEqual(f.get('sha256_conteudo'), hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), rel)


if __name__ == '__main__':
    unittest.main()
