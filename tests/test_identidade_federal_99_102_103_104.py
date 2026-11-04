"""Identidade federal — issues #99, #102, #103, #104.

Garante:
1. Epígrafes/ementas das normas recolhidas neste lote batem com o caminho.
2. Anexos dos DL 1.873 e 2.111 estão transcritos e pesquisáveis.
3. Nenhum grupo SHA-1 idêntico novo fora de `duplicatas-excecoes.json`.
4. A divergência Senado 1.014-A vs Câmara 4.014-A permanece documentada.

Não acessa a rede. Não força título≡caminho em todo o federal (issue #102).
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVAS = ROOT / 'provas/identidade-federal-99-102-103'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
EXCECOES = json.loads((PROVAS / 'duplicatas-excecoes.json').read_text(encoding='utf-8'))

IDENTIDADES = {
    'br-federal-decreto-2019-09-03-10000': {
        'arquivo': 'federal/br-federal-decreto-2019-09-03-10000.md',
        'epigrafe': r'DECRETO Nº 10\.000',
        'proibido': [r'DECRETO Nº 10\.001', r'Ir ao conteúdo'],
    },
    'br-federal-decreto-2019-04-11-9764': {
        'arquivo': 'federal/br-federal-decreto-2019-04-11-9764.md',
        'epigrafe': r'DECRETO Nº 9\.764',
        'proibido': [r'DECRETO Nº 9\.754', r'Ir ao conteúdo'],
    },
    'br-federal-decreto-2018-06-29-9432': {
        'arquivo': 'federal/br-federal-decreto-2018-06-29-9432.md',
        'epigrafe': r'DECRETO Nº 9\.432',
        'proibido': [r'DECRETO Nº 9\.739', r'Ir ao conteúdo'],
    },
    'br-federal-decreto-2014-06-05-8264': {
        'arquivo': 'federal/br-federal-decreto-2014-06-05-8264.md',
        'epigrafe': r'DECRETO Nº 8\.264',
        'proibido': [r'Medida Provisória', r'MP Nº 649', r'Ir ao conteúdo'],
    },
    'br-federal-decreto-1959-12-23-47482': {
        'arquivo': 'federal/br-federal-decreto-1959-12-23-47482.md',
        'epigrafe': r'DECRETO Nº 47\.482',
        'proibido': [r'DECRETO Nº 50\.367', r'###DEC-050367', r'Ir ao conteúdo'],
    },
    'br-federal-lei-2014-06-02-12985': {
        'arquivo': 'federal/br-federal-lei-2014-06-02-12985.md',
        'epigrafe': r'LEI Nº 12\.985',
        'ementa': r'Viaduto Deputado José Fernandes de Lima',
        'proibido': [r'LEI Nº 12\.988', r'Joaquim Aurélio Barreto Nabuco'],
    },
    'br-federal-lei-2014-06-02-12988': {
        'arquivo': 'federal/br-federal-lei-2014-06-02-12988.md',
        'epigrafe': r'LEI Nº 12\.988',
        'ementa': r'Joaquim Aurélio Barreto Nabuco',
        'proibido': [r'LEI Nº 12\.985', r'Viaduto Deputado José Fernandes de Lima'],
    },
    'br-federal-decreto-lei-1942-01-13-4014-a': {
        'arquivo': 'federal/br-federal-decreto-lei-1942-01-13-4014-a.md',
        'epigrafe': r'DECRETO-LEI Nº 4\.014-A',
        'ementa': r'Fernando de Noronha',
        'proibido': [r'DECRETO-LEI N\. 1\.014-A', r'Ir ao conteúdo'],
    },
}


def sha1_file(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


class TestIdentidadeFederal99102103104(unittest.TestCase):
    def test_fontes_cataloga_as_dez_identidades(self):
        ids = {e['id'] for e in FONTES}
        expected = set(IDENTIDADES) | {
            'br-federal-decreto-lei-1981-05-27-1873',
            'br-federal-decreto-lei-1984-04-04-2111',
        }
        self.assertEqual(ids, expected)

    def test_identidades_recolhidas_batem_com_caminho(self):
        for doc_id, spec in IDENTIDADES.items():
            with self.subTest(doc_id):
                text = (ROOT / spec['arquivo']).read_text(encoding='utf-8')
                self.assertRegex(text[:400], spec['epigrafe'])
                if 'ementa' in spec:
                    self.assertRegex(text, spec['ementa'])
                for bad in spec.get('proibido', []):
                    self.assertIsNone(re.search(bad, text), f'{doc_id} ainda contém {bad!r}')

    def test_hashes_markdown_conferem_com_fontes_json(self):
        for entry in FONTES:
            path = ROOT / entry['arquivo']
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, entry['sha256_markdown'], entry['id'])

    def test_anexo_1873_transcrito_e_pesquisavel(self):
        text = (ROOT / 'federal/br-federal-decreto-lei-1981-05-27-1873.md').read_text(encoding='utf-8')
        self.assertIn('## ANEXO I', text)
        self.assertIn('## ANEXO II', text)
        self.assertIn('GRATIFICAÇÃO DE INTERIORIZAÇÃO', text)
        self.assertIn('60%', text)
        self.assertIn('50%', text)
        self.assertIn('40%', text)
        self.assertIn('NS-901', text)
        self.assertIn('Odontólogo', text)
        self.assertIn('anexo-i-planalto.png', text)
        self.assertIn('anexo-ii-camara.png', text)
        fac_i = PROVAS / 'anexos/br-federal-decreto-lei-1981-05-27-1873-anexo-i-planalto.png'
        fac_ii = PROVAS / 'anexos/br-federal-decreto-lei-1981-05-27-1873-anexo-ii-camara.png'
        self.assertTrue(fac_i.is_file() and fac_i.stat().st_size > 10_000)
        self.assertTrue(fac_ii.is_file() and fac_ii.stat().st_size > 10_000)

    def test_anexo_2111_transcrito_e_pesquisavel(self):
        text = (ROOT / 'federal/br-federal-decreto-lei-1984-04-04-2111.md').read_text(encoding='utf-8')
        self.assertIn('## ANEXO', text)
        self.assertIn('GRATIFICAÇÃO DE FUNÇÃO POLICIAL', text)
        self.assertIn('20%', text)
        self.assertIn('Grupo-Polícia Federal', text)
        self.assertIn('2.196', text)  # nota da redação posterior, sem substituir
        fac = PROVAS / 'anexos/br-federal-decreto-lei-1984-04-04-2111-anexo-camara.png'
        self.assertTrue(fac.is_file() and fac.stat().st_size > 10_000)

    def test_divergencia_senado_4014a_documentada(self):
        nota = (PROVAS / 'NOTA-DIVERGENCIA-4014-A.md').read_text(encoding='utf-8')
        self.assertIn('1.014-A', nota)
        self.assertIn('4.014-A', nota)
        pub = PROVAS / 'divergencias/senado-529102-publicacao-15820792.html.xz'
        self.assertTrue(pub.is_file())
        # Markdown publicado não reproduz o cabeçalho senatorial errôneo
        md = (ROOT / 'federal/br-federal-decreto-lei-1942-01-13-4014-a.md').read_text(encoding='utf-8')
        self.assertIn('4.014-A', md)
        self.assertNotIn('1.014-A', md)

    def test_sha1_duplicatas_somente_nas_excecoes(self):
        allowed = {g['sha1'] for g in EXCECOES['grupos']}
        groups: dict[str, list[str]] = defaultdict(list)
        for root_name in ('federal', 'estaduais', 'municipais'):
            root = ROOT / root_name
            if not root.is_dir():
                continue
            for path in root.rglob('*.md'):
                groups[sha1_file(path)].append(str(path.relative_to(ROOT)))
        unexpected = {
            h: sorted(ps)
            for h, ps in groups.items()
            if len(ps) > 1 and h not in allowed
        }
        self.assertEqual(
            unexpected,
            {},
            msg=f'Novos grupos SHA-1 idênticos fora de duplicatas-excecoes.json: {unexpected}',
        )
        # Toda exceção ainda deve existir como grupo real
        for group in EXCECOES['grupos']:
            with self.subTest(group['sha1'][:12]):
                actual = sorted(groups.get(group['sha1'], []))
                self.assertEqual(actual, sorted(group['arquivos']))


if __name__ == '__main__':
    unittest.main()
