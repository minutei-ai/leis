"""Regressões do catálogo local de licitações — UF GO (issue #57).

Lê somente arquivos do repositório; não acessa a rede.
Execute: python3 -m unittest tests.test_licitacoes_locais_GO -v
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import nucleo_licitacoes as nl  # noqa: E402

CATALOG = ROOT / 'metadados/licitacoes-locais/GO.json'
PROVAS = ROOT / 'provas/licitacoes-locais/GO'
FONTES = PROVAS / 'fontes.json'
COBERTURA = PROVAS / 'cobertura-decreto-2469.json'
MUNICIPAL = ROOT / 'municipais/5208707/br-municipal-5208707-decreto-2024-06-25-2469.md'
ESTADUAL = ROOT / 'estaduais/GO/br-go-norma-106877.md'


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_pdf_text(data: bytes) -> str:
    """Extrai texto do PDF via pdftotext (poppler), sem rede."""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
        tmp.write(data)
        tmp.flush()
        out = subprocess.check_output(
            ['pdftotext', '-layout', tmp.name, '-'],
            stderr=subprocess.DEVNULL,
        )
    return out.decode('utf-8', errors='replace')


class TestCatalogoGO(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
        cls.fontes = json.loads(FONTES.read_text(encoding='utf-8'))
        cls.cobertura = json.loads(COBERTURA.read_text(encoding='utf-8'))
        cls.md = MUNICIPAL.read_text(encoding='utf-8')
        cls.md_sha = sha256_bytes(MUNICIPAL.read_bytes())
        cls.body = nl.strip_note(cls.md)

    def test_estrutura_minima_do_catalogo(self):
        self.assertEqual(self.catalog['uf'], 'GO')
        self.assertEqual(self.catalog['cobertura'], 'parcial')
        self.assertIn('documentos', self.catalog)
        self.assertIn('reutilizados', self.catalog)
        self.assertIn('pendencias', self.catalog)
        self.assertGreaterEqual(len(self.catalog['pendencias']), 1)

    def test_documento_municipal_2469_identidade_e_ambito(self):
        docs = self.catalog['documentos']
        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertEqual(doc['norma_id'], 'br-municipal-5208707-decreto-2024-06-25-2469')
        self.assertEqual(doc['arquivo'], 'municipais/5208707/br-municipal-5208707-decreto-2024-06-25-2469.md')
        self.assertEqual(doc['uf'], 'GO')
        self.assertEqual(doc['ibge'], '5208707')
        self.assertEqual(doc['ente']['tipo'], 'municipio')
        ambito = doc['ambito']['abrangencia_literal']
        self.assertIn('Município de Goiânia', ambito)
        self.assertIn('direta e indireta', ambito)
        self.assertIn('Poder Executivo', ambito)
        self.assertIn('Estado de Goiás', doc['ambito']['nao_e'])
        self.assertIn('endereço do fornecedor', doc['ambito']['nao_e'])
        self.assertFalse(doc['edicao']['vigencia_certificada'])
        self.assertTrue(doc['edicao']['integral'])

    def test_hashes_markdown_e_fonte_batem_com_provas(self):
        doc = self.catalog['documentos'][0]
        self.assertEqual(doc['hashes']['sha256_markdown'], self.md_sha)
        self.assertEqual(self.cobertura['markdown_sha256'], self.md_sha)
        self.assertEqual(self.fontes['conversao']['sha256_markdown'], self.md_sha)
        self.assertEqual(
            doc['hashes']['sha256_corpo_markdown'],
            sha256_bytes(self.body.encode('utf-8')),
        )
        fonte = self.fontes['fontes']['sileg-dc-2469']
        self.assertEqual(doc['hashes']['sha256_fonte'], fonte['sha256_fonte'])
        snap = ROOT / fonte['arquivo']
        self.assertTrue(snap.is_file())
        raw = lzma.open(snap).read()
        self.assertEqual(sha256_bytes(raw), fonte['sha256_fonte'])
        self.assertEqual(len(raw), fonte['bytes'])
        self.assertEqual(sha256_bytes(snap.read_bytes()), fonte['sha256_snapshot_armazenado'])

    def test_snapshot_dom_inteiro(self):
        dom = self.fontes['fontes']['dom-8318-20240625']
        snap = ROOT / dom['arquivo']
        self.assertTrue(snap.is_file())
        raw = lzma.open(snap).read()
        self.assertEqual(sha256_bytes(raw), dom['sha256_fonte'])
        self.assertEqual(len(raw), dom['bytes'])
        self.assertEqual(sha256_bytes(snap.read_bytes()), dom['sha256_snapshot_armazenado'])
        self.assertEqual(
            self.catalog['documentos'][0]['hashes']['sha256_dom'],
            dom['sha256_fonte'],
        )

    def test_reconversao_integral_do_snapshot_e_identica(self):
        source = self.fontes['fontes']['sileg-dc-2469']
        raw = lzma.decompress((ROOT / source['arquivo']).read_bytes())
        converted = nl.convert_html(raw, 'utf-8', source['url'])
        blocks = []
        started = False
        for block in converted.blocks:
            plain = re.sub(r'\s+', ' ', nl.md_plain(block, True)).strip().lstrip('\ufeff')
            if not started:
                if re.match(r'^DECRETO N', plain, re.I):
                    started = True
                    blocks.append(block.lstrip('\ufeff'))
                continue
            blocks.append(block)
        self.assertTrue(started)
        expected = nl.blocks_to_markdown(blocks, r'^DECRETO N')
        self.assertEqual(expected, self.body)
        # Conferência independente de todo o texto bruto do corpo convertido.
        self.assertEqual(nl.strip_fold(nl.md_text_all(expected)), nl.strip_fold(nl.md_text_all(self.body)))

    def test_markdown_preserva_trechos_notas_e_disclaimer(self):
        for trecho in self.cobertura['trechos_obrigatorios']:
            self.assertIn(trecho, self.md, trecho)
        for art in self.cobertura['artigos_esperados']:
            self.assertIn(art, self.md, art)
        self.assertIn('nota-edicao:inicio', self.md)
        self.assertIn('5208707', self.md)
        self.assertIn('10.247', self.md)
        self.assertIsNone(re.search(r'(?m)^ANEXO\b', self.md))

    def test_dom_contem_trechos_do_ato_e_nao_o_bloco_nota_sileg(self):
        dom = self.fontes['fontes']['dom-8318-20240625']
        text = extract_pdf_text(lzma.decompress((ROOT / dom['arquivo']).read_bytes()))
        fold = nl.strip_fold(text)
        for trecho in self.cobertura['trechos_obrigatorios_dom_conferencia']:
            self.assertIn(nl.strip_fold(trecho), fold, trecho)
        self.assertNotIn(nl.strip_fold('Lei nº 11.690, de 2026'), fold)
        self.assertIn('Nota: ver', self.md)

    def test_relacoes_federais_com_evidencia_literal(self):
        rels = self.catalog['documentos'][0]['relacoes_federais']
        self.assertTrue(rels)
        art60 = next(r for r in rels if r.get('alvo_dispositivos') == ['art. 60'])
        self.assertIn('art. 60', art60['evidencia_literal'])
        self.assertIn('desempate', art60['evidencia_literal'].lower())
        for rel in rels:
            self.assertTrue(rel.get('evidencia_literal'))
            self.assertIn('desconhecidos', rel)
            self.assertIn('leitura', rel)
            self.assertTrue(rel['desconhecidos'])
            self.assertNotIn('certifica vigência', rel.get('leitura', '').lower())

    def test_reutiliza_estadual_10247_sem_duplicar(self):
        reuts = self.catalog['reutilizados']
        self.assertEqual(len(reuts), 1)
        r = reuts[0]
        self.assertEqual(r['norma_id'], 'br-go-norma-106877')
        self.assertEqual(r['arquivo'], 'estaduais/GO/br-go-norma-106877.md')
        self.assertFalse(r['duplicar'])
        self.assertEqual(r['acao'], 'reutilizar')
        self.assertEqual(r['edicao']['edicao_integral'], 'desconhecido')
        self.assertEqual(r['edicao']['status_edicao_arquivo'], 'desconhecido')
        self.assertFalse(r['edicao']['vigencia_certificada'])
        self.assertTrue(ESTADUAL.is_file())
        clones = list((ROOT / 'municipais/5208707').glob('*10247*')) + list(
            (ROOT / 'municipais/5208707').glob('*10-247*')
        ) + list((ROOT / 'municipais/5208707').glob('*106877*'))
        self.assertEqual(clones, [])
        self.assertEqual(r['ente']['tipo'], 'estado')
        self.assertIn('Estado de Goiás', r['ambito']['abrangencia_literal_no_arquivo'])
        self.assertIn('5208707', r['ambito']['nao_e'])
        body = ESTADUAL.read_text(encoding='utf-8')
        self.assertIn('10.247', body)
        self.assertIn('pregão', body.lower())

    def test_nao_ha_outro_2469_municipal_goiania_duplicado(self):
        hits = []
        base = ROOT / 'municipais/5208707'
        self.assertTrue(base.is_dir())
        for path in base.glob('*.md'):
            name = path.name.lower()
            if '2469' in name or '2-469' in name or '2.469' in name:
                hits.append(path)
        self.assertEqual(
            [p.name for p in hits],
            ['br-municipal-5208707-decreto-2024-06-25-2469.md'],
        )
        # Identidade federal homônima (1998) não é este ato
        federal = ROOT / 'federal/br-federal-decreto-1998-01-21-2469.md'
        if federal.is_file():
            text = federal.read_text(encoding='utf-8')
            self.assertNotIn('Goiânia', text)
            self.assertNotIn('5208707', text)

    def test_separacao_estado_municipio_no_catalogo(self):
        doc = self.catalog['documentos'][0]
        reut = self.catalog['reutilizados'][0]
        self.assertEqual(doc['ente']['tipo'], 'municipio')
        self.assertEqual(reut['ente']['tipo'], 'estado')
        self.assertNotEqual(doc['arquivo'], reut['arquivo'])
        self.assertTrue(doc['arquivo'].startswith('municipais/5208707/'))
        self.assertTrue(reut['arquivo'].startswith('estaduais/GO/'))


class TestNegativosGO(unittest.TestCase):
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
        self.assertNotIn('estado de goiás', lit)
        self.assertIn('município de goiânia', lit)
        self.assertIn('poder executivo', lit)

    def test_arquivo_inexistente_de_outra_uf_nao_esta_no_catalogo(self):
        catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
        for doc in catalog['documentos'] + catalog['reutilizados']:
            self.assertEqual(doc['uf'], 'GO')
            self.assertNotIn('/PR/', doc['arquivo'])
            self.assertNotIn('/MG/', doc['arquivo'])
            self.assertNotIn('/SP/', doc['arquivo'])
            self.assertNotIn('3550308', doc.get('ibge') or '')
            self.assertNotIn('3106200', doc.get('ibge') or '')

    def test_imagens_omitidas_registradas_sem_texto_juridico(self):
        fontes = json.loads(FONTES.read_text(encoding='utf-8'))
        imgs = fontes['conversao']['imagens_omitidas']
        self.assertEqual(len(imgs), 1)
        self.assertIn('Brasão', imgs[0]['alt'])
        self.assertIn('omitida', imgs[0]['tratamento'])


if __name__ == '__main__':
    unittest.main()
