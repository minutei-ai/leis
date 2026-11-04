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

    def test_pendencias_candidatos_verificados_sem_publicar_integra(self):
        pend = self.cat['pendencias']
        cand = next(p for p in pend if p['id'] == 'bh-candidatos-complementares')
        ids = {i['dom_ato_id'] for i in cand['itens']}
        self.assertEqual(ids, {7494, 23012, 30089, 30413})
        publicados = [p.name for p in (ROOT / 'municipais/3106200').glob('*.md')]
        self.assertTrue(any('decreto-2023-03-28-18289' in n for n in publicados))
        for num in ('17813', '18096', '18240', '18242'):
            self.assertFalse(any(num in n for n in publicados), num)
        for item in cand['itens']:
            self.assertIn('Íntegra não publicada', item['verificacao'])

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
