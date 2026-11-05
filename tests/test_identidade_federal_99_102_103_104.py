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
import lzma
import sys
import json
import re
import unittest
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import nucleo_licitacoes as nl  # noqa: E402
PROVAS = ROOT / 'provas/identidade-federal-99-102-103'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
EXCECOES = json.loads((PROVAS / 'duplicatas-excecoes.json').read_text(encoding='utf-8'))
PROVA_CONVERSAO_103 = json.loads((PROVAS / 'prova-conversao-12985-12988.json').read_text(encoding='utf-8'))

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
        # Célula CLASSE A (jornada 4 h) recuperada por colação visual Câmara + Planalto
        self.assertIn('CLASSE A — NS-4 a 6', text)
        self.assertNotIn('parcialmente ilegível', text)
        self.assertIn('anexo-i-planalto.png', text)
        self.assertIn('anexo-ii-camara.png', text)
        self.assertIn('classe-a-4h-planalto-crop.png', text)
        self.assertIn('classe-a-4h-camara-crop.png', text)
        fac_i = PROVAS / 'anexos/br-federal-decreto-lei-1981-05-27-1873-anexo-i-planalto.png'
        fac_ii = PROVAS / 'anexos/br-federal-decreto-lei-1981-05-27-1873-anexo-ii-camara.png'
        crop_p = PROVAS / 'anexos/br-federal-decreto-lei-1981-05-27-1873-anexo-ii-classe-a-4h-planalto-crop.png'
        crop_c = PROVAS / 'anexos/br-federal-decreto-lei-1981-05-27-1873-anexo-ii-classe-a-4h-camara-crop.png'
        self.assertTrue(fac_i.is_file() and fac_i.stat().st_size > 10_000)
        self.assertTrue(fac_ii.is_file() and fac_ii.stat().st_size > 10_000)
        self.assertTrue(crop_p.is_file() and crop_p.stat().st_size > 1_000)
        self.assertTrue(crop_c.is_file() and crop_c.stat().st_size > 1_000)

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
        lote = (PROVAS / 'divergencias-cabecalho-lote.md').read_text(encoding='utf-8')
        self.assertIn('45171', lote)
        self.assertIn('45353', lote)
        self.assertIn('46934', lote)

    def test_busca_12985_viaduto_e_12988_nabuco(self):
        lei_985 = (ROOT / 'federal/br-federal-lei-2014-06-02-12985.md').read_text(encoding='utf-8')
        lei_988 = (ROOT / 'federal/br-federal-lei-2014-06-02-12988.md').read_text(encoding='utf-8')
        self.assertIn('Viaduto Deputado José Fernandes de Lima', lei_985)
        self.assertIn('BR-101', lei_985)
        self.assertIn('Mamanguape', lei_985)
        self.assertIn('Joaquim Aurélio Barreto Nabuco', lei_988)
        self.assertIn('Livro dos Heróis da Pátria', lei_988)
        self.assertNotIn('Nabuco', lei_985)
        self.assertNotIn('Viaduto', lei_988)

    def test_conversao_oficial_12985_12988_e_nao_trocada(self):
        rows = {item['id']: item for item in FONTES if item.get('issue') == 103}
        proofs = {item['id']: item for item in PROVA_CONVERSAO_103['identidades']}
        normalized_sources = {}
        normalized_markdowns = {}
        for doc_id in (
            'br-federal-lei-2014-06-02-12985',
            'br-federal-lei-2014-06-02-12988',
        ):
            with self.subTest(doc_id=doc_id):
                item = rows[doc_id]
                proof = proofs[doc_id]
                packed = (ROOT / item['snapshot']).read_bytes()
                self.assertEqual(hashlib.sha256(packed).hexdigest(), item['sha256_snapshot'])
                raw = lzma.decompress(packed)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item['sha256_fonte'])
                self.assertEqual(len(raw), item['bytes_fonte'])
                soup = BeautifulSoup(raw, 'lxml')
                official = soup.select_one('.textoNorma')
                self.assertIsNotNone(official, 'a fonte oficial deve conter .textoNorma')
                source_text = nl.strip_fold(official.get_text(' '))
                markdown = (ROOT / item['arquivo']).read_text(encoding='utf-8')
                self.assertEqual(hashlib.sha256(markdown.encode()).hexdigest(), item['sha256_markdown'])
                self.assertIn('\n\n', markdown)
                markdown_body = nl.strip_fold(nl.md_text_all(markdown.split('\n\n', 1)[1]))
                self.assertEqual(source_text, markdown_body, 'corpo deve reconverter do snapshot oficial')
                self.assertEqual(proof['seletor_oficial'], '.textoNorma')
                self.assertEqual(proof['sha256_texto_normalizado_fonte'], hashlib.sha256(source_text.encode()).hexdigest())
                self.assertEqual(proof['sha256_texto_normalizado_markdown'], hashlib.sha256(markdown_body.encode()).hexdigest())
                self.assertIs(proof['equivalente'], True)
                normalized_sources[doc_id] = source_text
                normalized_markdowns[doc_id] = markdown_body
        id_985 = 'br-federal-lei-2014-06-02-12985'
        id_988 = 'br-federal-lei-2014-06-02-12988'
        self.assertEqual(normalized_sources[id_985], normalized_markdowns[id_985])
        self.assertEqual(normalized_sources[id_988], normalized_markdowns[id_988])
        self.assertNotEqual(normalized_sources[id_985], normalized_markdowns[id_988])
        self.assertNotEqual(normalized_sources[id_988], normalized_markdowns[id_985])

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
        generica = (
            'Conteúdo byte a byte idêntico sob identidades de catálogo distintas no acervo '
            'estadual/municipal. Mantidos ambos os caminhos até desambiguação na fonte'
        )
        tipos = set()
        for group in EXCECOES['grupos']:
            with self.subTest(group['sha1'][:12]):
                actual = sorted(groups.get(group['sha1'], []))
                self.assertEqual(actual, sorted(group['arquivos']))
                self.assertIn(group.get('tipo'), {
                    'alias_catalogo',
                    'pendencia_identidade',
                    'mesmo_texto_fonte_com_ressalva',
                })
                self.assertTrue(group.get('justificativa'))
                self.assertNotIn(generica, group['justificativa'])
                tipos.add(group['tipo'])
        self.assertIn('alias_catalogo', tipos)
        self.assertIn('mesmo_texto_fonte_com_ressalva', tipos)
        aliases = [g for g in EXCECOES['grupos'] if g['tipo'] == 'alias_catalogo']
        ressalvas = [g for g in EXCECOES['grupos'] if g['tipo'] == 'mesmo_texto_fonte_com_ressalva']
        self.assertEqual(len(aliases), 13)
        self.assertEqual(len(ressalvas), 1)
        self.assertEqual(
            sorted(ressalvas[0]['arquivos']),
            sorted([
                'estaduais/MG/br-mg-decreto-1994-08-05-35816.md',
                'estaduais/MG/br-mg-decreto-1994-08-05-35817.md',
            ]),
        )
        self.assertEqual(ressalvas[0].get('status'), 'justificado_com_ressalva')
        self.assertIn('microfilme', ressalvas[0]['justificativa'].lower())
        for g in aliases:
            with self.subTest(alias=g['sha1'][:12]):
                self.assertTrue(g.get('identidade_do_corpo'))
                self.assertGreaterEqual(len(g['justificativa']), 40)
        self.assertTrue((PROVAS / 'duplicatas-auditoria.md').is_file())

    def test_mg_pares_desmembrados_nao_compartilham_corpo(self):
        """Pares ainda órfãos: corpo correto ≠ nota; recuperados JMG têm dispositivo próprio."""
        notas = [
            (
                'estaduais/MG/br-mg-decreto-1945-06-14-2159.md',
                'estaduais/MG/br-mg-decreto-1945-06-26-2160.md',
                'Sete Lagoas',
                'Pouso Alegre',
            ),
            (
                'estaduais/MG/br-mg-lei-1991-01-22-10454.md',
                'estaduais/MG/br-mg-lei-1991-11-22-10523.md',
                'Bias Fortes',
                'Sapucaí-Mirim',
            ),
            (
                'estaduais/MG/br-mg-lei-2016-11-18-22346.md',
                'estaduais/MG/br-mg-decreto-1982-09-16-22346.md',
                'Limeira do Oeste',
                'FJP',
            ),
        ]
        for keep, orphan, keep_token, orphan_token in notas:
            with self.subTest(keep=keep):
                keep_text = (ROOT / keep).read_text(encoding='utf-8')
                orphan_text = (ROOT / orphan).read_text(encoding='utf-8')
                self.assertNotEqual(sha1_file(ROOT / keep), sha1_file(ROOT / orphan))
                self.assertIn(keep_token.lower(), keep_text.lower())
                self.assertIn('corpo integral não recuperado', orphan_text)
                self.assertIn(orphan_token.lower(), orphan_text.lower())
                self.assertIn('mg-recoleta/api-', orphan_text)
                self.assertIn('excluir_denominador_integra: true', orphan_text)
                self.assertIn('edicao_integral: false', orphan_text)
                self.assertIn('nao_publicado_integra', orphan_text)

        # 803 e 40955 recuperados do JMG — dispositivo distinto do par mantido
        d804 = (ROOT / 'estaduais/MG/br-mg-decreto-1937-04-08-804.md').read_text(encoding='utf-8')
        d803 = (ROOT / 'estaduais/MG/br-mg-decreto-1937-04-08-803.md').read_text(encoding='utf-8')
        self.assertIn('Manhumirim', d804)
        self.assertIn('Jequitinhonha', d803)
        self.assertIn('Joaima', d803)
        self.assertNotIn('corpo integral não recuperado', d803)
        self.assertNotEqual(sha1_file(ROOT / 'estaduais/MG/br-mg-decreto-1937-04-08-804.md'),
                            sha1_file(ROOT / 'estaduais/MG/br-mg-decreto-1937-04-08-803.md'))
        self.assertTrue((PROVAS / 'mg-recoleta/jmg/crop-803-decreto.png').is_file())

        d40951 = (ROOT / 'estaduais/MG/br-mg-decreto-2000-03-08-40951.md').read_text(encoding='utf-8')
        d40955 = (ROOT / 'estaduais/MG/br-mg-decreto-2000-03-21-40955.md').read_text(encoding='utf-8')
        self.assertIn('FEAM', d40951)
        self.assertIn('FIA', d40955)
        self.assertIn('327.713,81', d40955)
        self.assertNotIn('corpo integral não recuperado', d40955)
        self.assertNotEqual(sha1_file(ROOT / 'estaduais/MG/br-mg-decreto-2000-03-08-40951.md'),
                            sha1_file(ROOT / 'estaduais/MG/br-mg-decreto-2000-03-21-40955.md'))
        self.assertTrue((PROVAS / 'mg-recoleta/jmg/crop-40955-decreto.png').is_file())

    def test_mg_orfaos_inventario_exclui_stubs_do_denominador_integra(self):
        inv = json.loads((PROVAS / 'mg-orfaos-inventario.json').read_text(encoding='utf-8'))
        self.assertEqual(len(inv['recuperados']), 2)
        self.assertEqual(len(inv['pendentes']), 17)
        for item in inv['pendentes']:
            with self.subTest(item['id']):
                self.assertIs(item['edicao_integral'], False)
                self.assertIs(item['excluir_denominador_integra'], True)
                self.assertEqual(item['status_publicacao'], 'nao_publicado_integra')
                text = (ROOT / item['arquivo']).read_text(encoding='utf-8')
                self.assertIn('corpo integral não recuperado', text)
                self.assertIn('excluir_denominador_integra: true', text)
                # presença/hash não reclassifica
                self.assertNotIn('edicao_integral: true', text)
        for item in inv['recuperados']:
            with self.subTest(item['id']):
                self.assertIs(item['edicao_integral'], True)
                text = (ROOT / item['arquivo']).read_text(encoding='utf-8')
                self.assertNotIn('corpo integral não recuperado', text)
                for token in item['tokens_identidade']:
                    self.assertIn(token, text)

    def test_mg_37349_recoleta_zacarias_distinto_de_37351(self):
        a = (ROOT / 'estaduais/MG/br-mg-decreto-1995-10-05-37349.md').read_text(encoding='utf-8')
        b = (ROOT / 'estaduais/MG/br-mg-decreto-1995-10-05-37351.md').read_text(encoding='utf-8')
        self.assertIn('Zacarias Roque', a)
        self.assertIn('Coronel Fabriciano', a)
        self.assertIn('Dona Valentina Alkimim', b)
        self.assertNotEqual(sha1_file(ROOT / 'estaduais/MG/br-mg-decreto-1995-10-05-37349.md'),
                            sha1_file(ROOT / 'estaduais/MG/br-mg-decreto-1995-10-05-37351.md'))
        self.assertTrue((PROVAS / 'mg-recoleta/api-DEC-37349-1995.json.xz').is_file())

    def test_lote_102_colacao_preserva_literais_senado(self):
        lote = (PROVAS / 'divergencias-cabecalho-lote.md').read_text(encoding='utf-8')
        self.assertIn('Erro literal da fonte', lote)
        self.assertIn('467738', lote)
        self.assertIn('467918', lote)
        self.assertIn('469503', lote)
        # Corpus still has source literals — no blind path rewrite
        d45171 = (ROOT / 'federal/br-federal-decreto-1958-12-31-45171.md').read_text(encoding='utf-8')
        d45353 = (ROOT / 'federal/br-federal-decreto-1959-01-28-45353.md').read_text(encoding='utf-8')
        d46934 = (ROOT / 'federal/br-federal-decreto-1959-09-30-46934.md').read_text(encoding='utf-8')
        self.assertRegex(d45171[:200], r'41\.171')
        self.assertRegex(d45353[:200], r'453\.353')
        self.assertRegex(d46934[:200], r'56\.934')
        self.assertTrue((PROVAS / 'divergencias/senado-pub-15805509.html.xz').is_file())
        self.assertTrue((PROVAS / 'divergencias/detalhe-467738.json').is_file())


if __name__ == '__main__':
    unittest.main()
