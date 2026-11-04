"""Regressões do catálogo local de licitações — UF SP (issue #57).

Lê somente arquivos do repositório; não acessa a rede.
Execute: python3 -m unittest tests.test_licitacoes_locais_SP -v
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import sys

from bs4 import BeautifulSoup
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import nucleo_licitacoes as nl
CATALOG = ROOT / 'metadados/licitacoes-locais/SP.json'
PROVAS = ROOT / 'provas/licitacoes-locais/SP'
FONTES = PROVAS / 'fontes.json'
COBERTURA = PROVAS / 'cobertura-decreto-62100.json'
MUNICIPAL = ROOT / 'municipais/3550308/br-municipal-3550308-decreto-2022-12-27-62100.md'
ESTADUAL = ROOT / 'estaduais/SP/br-sp-norma-207462.md'


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestCatalogoSP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
        cls.fontes = json.loads(FONTES.read_text(encoding='utf-8'))
        cls.cobertura = json.loads(COBERTURA.read_text(encoding='utf-8'))
        cls.md = MUNICIPAL.read_text(encoding='utf-8')
        cls.md_sha = sha256_bytes(MUNICIPAL.read_bytes())

    def test_estrutura_minima_do_catalogo(self):
        self.assertEqual(self.catalog['uf'], 'SP')
        self.assertEqual(self.catalog['cobertura'], 'parcial')
        self.assertIn('documentos', self.catalog)
        self.assertIn('reutilizados', self.catalog)
        self.assertIn('pendencias', self.catalog)
        self.assertGreaterEqual(len(self.catalog['pendencias']), 1)

    def test_documento_municipal_62100_identidade_e_ambito(self):
        docs = self.catalog['documentos']
        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertEqual(doc['norma_id'], 'br-municipal-3550308-decreto-2022-12-27-62100')
        self.assertEqual(doc['arquivo'], 'municipais/3550308/br-municipal-3550308-decreto-2022-12-27-62100.md')
        self.assertEqual(doc['uf'], 'SP')
        self.assertEqual(doc['ibge'], '3550308')
        self.assertEqual(doc['ente']['tipo'], 'municipio')
        ambito = doc['ambito']['abrangencia_literal']
        self.assertIn('Município de São Paulo', ambito)
        self.assertIn('direta, autárquica e fundacional', ambito)
        self.assertIn('Estado de São Paulo', doc['ambito']['nao_e'])
        self.assertFalse(doc['edicao']['vigencia_certificada'])
        self.assertEqual(doc['edicao']['situacao_informada_pela_fonte'], 'ALTERADO')

    def test_hashes_markdown_e_fonte_batem_com_provas(self):
        doc = self.catalog['documentos'][0]
        self.assertEqual(doc['hashes']['sha256_markdown'], self.md_sha)
        self.assertEqual(self.cobertura['markdown_sha256'], self.md_sha)
        self.assertEqual(
            self.fontes['conversao']['sha256_markdown'],
            self.md_sha,
        )
        fonte = self.fontes['fontes']['prefeitura-sp-decreto-62100']
        self.assertEqual(doc['hashes']['sha256_fonte'], fonte['sha256_fonte'])
        snap = ROOT / fonte['arquivo']
        self.assertTrue(snap.is_file())
        raw = lzma.open(snap).read()
        self.assertEqual(sha256_bytes(raw), fonte['sha256_fonte'])

    def test_reconversao_integral_do_snapshot_e_identica(self):
        source = self.fontes['fontes']['prefeitura-sp-decreto-62100']
        soup = BeautifulSoup(lzma.decompress((ROOT / source['arquivo']).read_bytes()), 'lxml')
        candidates = [node for node in soup.select('.col.s12.customStyle')
                      if node.get_text(' ', strip=True).startswith('DECRETO Nº 62.100')]
        self.assertEqual(len(candidates), 1)
        content = candidates[0]
        converted = nl.convert_html(('<html><body>' + str(content) + '</body></html>').encode('utf-8'),
                                    'utf-8', source['url'])
        expected = nl.blocks_to_markdown(converted.blocks, r'^DECRETO N')
        body = nl.strip_note(self.md)
        self.assertEqual(expected, body)
        # Conferência independente de todo o texto bruto, além da reconversão.
        self.assertEqual(nl.strip_fold(content.get_text(' ')), nl.strip_fold(nl.md_text_all(body)))

    def test_markdown_preserva_alteracoes_notas_e_disclaimer(self):
        for trecho in self.cobertura['trechos_obrigatorios']:
            self.assertIn(trecho, self.md, trecho)
        for marcador, minimo in self.cobertura['marcadores_alteracao_minimos'].items():
            self.assertGreaterEqual(self.md.count(marcador), minimo, marcador)
        self.assertIn('Decreto nº 62.436/2023', self.md)
        self.assertIn('Decreto nº 64.863/2025', self.md)
        self.assertIn('ALTERADO', self.md)
        self.assertRegex(self.md, r'~~.+~~')

    def test_sem_anexo_afirmado_inexistente_na_fonte(self):
        self.assertEqual(self.catalog['documentos'][0]['anexos'], [])
        self.assertFalse(self.fontes['conversao']['anexos_na_fonte'])
        self.assertIsNone(re.search(r'(?m)^ANEXO\b', self.md))

    def test_relacoes_federais_com_evidencia_literal(self):
        rels = self.catalog['documentos'][0]['relacoes_federais']
        self.assertTrue(rels)
        for rel in rels:
            self.assertTrue(rel.get('evidencia_literal'))
            self.assertIn('desconhecidos', rel)
            self.assertIn('leitura', rel)
            self.assertTrue(rel['desconhecidos'])
            self.assertNotIn('certifica vigência', rel.get('leitura', '').lower())

    def test_reutiliza_estadual_67608_sem_duplicar(self):
        reuts = self.catalog['reutilizados']
        self.assertEqual(len(reuts), 1)
        r = reuts[0]
        self.assertEqual(r['norma_id'], 'br-sp-norma-207462')
        self.assertEqual(r['arquivo'], 'estaduais/SP/br-sp-norma-207462.md')
        self.assertFalse(r['duplicar'])
        self.assertEqual(r['acao'], 'reutilizar')
        self.assertEqual(r['edicao']['edicao_integral'], 'desconhecido')
        self.assertEqual(r['edicao']['status_edicao_arquivo'], 'desconhecido')
        self.assertFalse(r['edicao']['vigencia_certificada'])
        self.assertTrue(ESTADUAL.is_file())
        # Não criar cópia municipal/estadual duplicada do 67.608
        clones = list((ROOT / 'municipais/3550308').glob('*67608*')) + list(
            (ROOT / 'municipais/3550308').glob('*67-608*')
        ) + list((ROOT / 'municipais/3550308').glob('*207462*'))
        self.assertEqual(clones, [])
        # Distinção de âmbito
        self.assertEqual(r['ente']['tipo'], 'estado')
        self.assertIn('estadual direta e autárquica', r['ambito']['abrangencia_literal_no_arquivo'])
        self.assertIn('3550308', r['ambito']['nao_e'])
        body = ESTADUAL.read_text(encoding='utf-8')
        self.assertIn('67.608', body)
        self.assertIn('transitória', body.lower())

    def test_nao_ha_outro_62100_municipal_duplicado_por_identidade(self):
        hits = []
        for path in (ROOT / 'municipais/3550308').glob('*.md'):
            name = path.name.lower()
            if '62100' in name or '62-100' in name or '62.100' in name:
                hits.append(path)
        self.assertEqual(
            [p.name for p in hits],
            ['br-municipal-3550308-decreto-2022-12-27-62100.md'],
        )

    def test_pendencias_explicitas_quando_dom_ausente(self):
        pend = ' '.join(self.catalog['pendencias']).lower()
        self.assertIn('diário oficial', pend)
        self.assertTrue(any('desconhecido' in json.dumps(r['edicao'], ensure_ascii=False)
                            for r in self.catalog['reutilizados']))


class TestNegativosSP(unittest.TestCase):
    def test_catalogo_nao_certifica_vigencia(self):
        catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
        for doc in catalog['documentos']:
            self.assertFalse(doc['edicao']['vigencia_certificada'])
        for r in catalog['reutilizados']:
            self.assertFalse(r['edicao']['vigencia_certificada'])

    def test_municipal_nao_usa_ambito_estadual(self):
        catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
        doc = catalog['documentos'][0]
        lit = doc['ambito']['abrangencia_literal'].lower()
        self.assertNotIn('administração pública estadual', lit)
        self.assertIn('município de são paulo', lit)

    def test_arquivo_inexistente_de_outra_uf_nao_esta_no_catalogo(self):
        catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
        for doc in catalog['documentos'] + catalog['reutilizados']:
            self.assertEqual(doc['uf'], 'SP')
            self.assertNotIn('/PR/', doc['arquivo'])
            self.assertNotIn('/MG/', doc['arquivo'])
            self.assertNotIn('/GO/', doc['arquivo'])
            self.assertNotIn('5208707', doc.get('ibge') or '')
            self.assertNotIn('3106200', doc.get('ibge') or '')


if __name__ == '__main__':
    unittest.main()
