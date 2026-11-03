"""Regressões do núcleo de legislação de licitações (Leis 14.133, 13.303, 8.666, 10.520 e LC 123).

Lê somente arquivos do repositório; não acessa a rede. Execute: python3 -m unittest discover -s tests
"""
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import nucleo_licitacoes as nl  # noqa: E402

HIST = 'federal/br-federal-lei-2021-04-01-14133.md'
CONS = 'federal/edicoes/br-federal-lei-2021-04-01-14133-consolidada.md'
LC123 = 'federal/br-federal-lei-complementar-2006-12-14-123.md'
L13303 = 'federal/br-federal-lei-2016-06-30-13303.md'
L8666 = 'federal/br-federal-lei-1993-06-21-8666.md'
L10520 = 'federal/br-federal-lei-2002-07-17-10520.md'
ALL = [HIST, CONS, LC123, L13303, L8666, L10520]


def load(rel):
    text = (ROOT / rel).read_text(encoding='utf-8')
    meta, body = nl.parse_frontmatter(text)
    return meta, body


def blocks_of(body):
    """Blocos de texto (separados por linha em branco) da parte principal, antes da assinatura."""
    out = []
    for block in re.split(r'\n\s*\n', nl.strip_note(body)):
        if re.match(r'^(?:~~)?Brasília,', block.strip()):
            break
        out.append(block.strip())
    return out


def article(body, number):
    """Blocos do artigo `number` (primeira ocorrência, incluindo redações riscadas e subsequentes até o próximo artigo)."""
    out, inside = [], False
    for block in blocks_of(body):
        key = nl.article_key(nl.md_plain(block, True).strip())
        if key is not None:
            if inside and key != number:
                break
            inside = key == number
        if inside:
            out.append(block)
    return out


def device(body, number, marker):
    """Primeiro bloco NÃO riscado do artigo que começa com a marca do dispositivo (ex.: '§ 2º')."""
    for block in article(body, number):
        if block.startswith('~~'):
            continue
        if nl.md_plain(block, True).strip().startswith(marker):
            return block
    return None


class TestEdicoes14133(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hmeta, cls.hbody = load(HIST)
        cls.cmeta, cls.cbody = load(CONS)

    def test_historica_identificada_e_corpo_preservado(self):
        self.assertEqual(self.hmeta['edicao_tipo'], 'historica')
        self.assertEqual(self.hmeta['edicao_relacionada'], 'br-federal-lei-2021-04-01-14133-consolidada')
        for key in ('fonte_url', 'capturado_em', 'sha256_fonte', 'fonte_orgao', 'edicao_integral'):
            self.assertEqual(self.hmeta[key], 'desconhecido', key)
        preserved = nl.strip_note(self.hbody)
        self.assertEqual(hashlib.sha256(preserved.encode()).hexdigest(), nl.HISTORIC_14133_SHA256)
        self.assertEqual(self.hmeta['sha256_corpo_preservado'], nl.HISTORIC_14133_SHA256)
        self.assertIn('Edição histórica', self.hbody)

    def test_historica_continua_com_vetos_e_sem_artigos_novos(self):
        for number, marker in (('37', '§ 2º'), ('54', '§ 1º'), ('115', '§ 4º'), ('175', '§ 2º')):
            block = device(self.hbody, number, marker)
            self.assertIsNotNone(block, f'art. {number} {marker}')
            self.assertIn('(VETADO)', block, f'art. {number} {marker} deve seguir vetado na edição histórica')
        self.assertEqual(article(self.hbody, '44-A'), [])
        self.assertEqual(article(self.hbody, '184-A'), [])
        self.assertIn('após decorridos 2 (dois) anos', ' '.join(article(self.hbody, '193')))

    def test_consolidada_identificada_com_fonte_captura_e_hash(self):
        m = self.cmeta
        self.assertEqual(m['edicao_tipo'], 'consolidada')
        self.assertIs(m['edicao_integral'], True)
        self.assertTrue(m['fonte_url'].startswith('https://www.planalto.gov.br/'))
        self.assertRegex(m['capturado_em'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        self.assertRegex(m['sha256_fonte'], r'^[0-9a-f]{64}$')
        self.assertEqual(m['situacao'], 'nao-informada')
        self.assertIs(m['vigencia_certificada'], False)

    def test_vetos_promulgados_estao_no_texto_consolidado(self):
        expected = {
            ('37', '§ 2º'): 'Ressalvados os casos de inexigibilidade de licitação, na licitação para contratação dos serviços técnicos',
            ('54', '§ 1º'): 'Sem prejuízo do disposto no caput, é obrigatória a publicação de extrato do edital no Diário Oficial',
            ('115', '§ 4º'): 'Nas contratações de obras e serviços de engenharia, sempre que a responsabilidade pelo licenciamento ambiental',
            ('175', '§ 2º'): 'Até 31 de dezembro de 2023, os Municípios deverão realizar divulgação complementar',
        }
        for (number, marker), phrase in expected.items():
            block = device(self.cbody, number, marker)
            self.assertIsNotNone(block, f'art. {number} {marker}')
            self.assertIn(phrase, nl.md_plain(block, True), f'art. {number} {marker}')
            self.assertNotIn('(VETADO)', block, f'art. {number} {marker}')
            self.assertFalse(block.startswith('~~'), f'art. {number} {marker} não pode estar riscado')
            self.assertIn('Promulgação partes vetadas', block, f'art. {number} {marker} deve manter a nota da fonte')

    def test_artigos_44a_e_184a_presentes(self):
        a44 = ' '.join(article(self.cbody, '44-A'))
        self.assertIn('equipamento destinado a procedimento diagnóstico ou terapêutico', a44)
        self.assertIn('Lei nº 15.210', a44)
        a184 = ' '.join(article(self.cbody, '184-A'))
        self.assertIn('regime simplificado', a184)
        self.assertIn('Lei nº 14.770', a184)

    def test_art_193_ii_com_redacao_da_lc_198(self):
        blocks = article(self.cbody, '193')
        current = [b for b in blocks if not b.startswith('~~')]
        text = '\n'.join(nl.md_plain(b, True) for b in current)
        self.assertRegex(text, r'II - em 30 de dezembro de 2023:\s*\(Redação dada pela Lei Complementar nº 198, de 2023\)')
        for item, law in (('a)', 'Lei nº 8.666, de 21 de junho de 1993'), ('b)', 'Lei nº 10.520, de 17 de julho de 2002'),
                          ('c)', 'arts. 1º a 47-A da Lei nº 12.462, de 4 de agosto de 2011')):
            self.assertTrue(any(nl.md_plain(b, True).startswith(item) and law in nl.md_plain(b, True) for b in current), item)
        # a redação original ("2 anos") só pode aparecer riscada
        for block in blocks:
            if 'após decorridos 2 (dois) anos' in block:
                self.assertTrue(block.startswith('~~'), 'redação original de 2 anos deve estar riscada')
        self.assertNotIn('Lei Complementar nº 198', ' '.join(nl.md_plain(b, True) for b in blocks if b.startswith('~~')))

    def test_diferencas_documentadas_historica_vs_consolidada(self):
        proof = json.loads((ROOT / 'provas/nucleo-licitacoes/historica-vs-consolidada-14133.json').read_text())
        self.assertEqual(proof['artigos_apenas_na_consolidada'], ['44-A', '184-A'])
        self.assertEqual(proof['artigos_apenas_na_historica'], [])
        for number in ('37', '54', '115', '175', '193'):
            self.assertIn(number, proof['artigos_alterados'])
        self.assertEqual(proof['historica_sha256'], nl.HISTORIC_14133_SHA256)

    def test_conferencia_com_segunda_fonte_oficial(self):
        proof = json.loads((ROOT / 'provas/nucleo-licitacoes/reconciliacao-br-federal-lei-2021-04-01-14133-consolidada.json').read_text())
        entry = proof['fontes_conferencia'][0]
        self.assertEqual(entry['artigos']['apenas_na_principal'], [])
        self.assertEqual(entry['artigos']['apenas_na_conferencia'], [])
        self.assertEqual(entry['artigos']['artigos_fonte_principal'], entry['artigos']['artigos_fonte_conferencia'])
        self.assertEqual([d['artigo'] for d in entry['artigos']['divergentes']], ['121'])
        self.assertTrue(entry['titulos_e_capitulos']['iguais'])
        self.assertTrue(proof['cobertura_texto']['equivalente'])


class TestLC123(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta, cls.body = load(LC123)
        cls.manifest = json.loads(nl.MANIFESTO.read_text())

    def test_remissoes_lc_238_nos_artigos_18a_18c_48_49(self):
        marker = 'Lei Complementar nº 238, de 21/10/2026'
        for number in ('18-A', '18-C', '48', '49'):
            text = ' '.join(nl.md_plain(b, True) for b in article(self.body, number))
            self.assertIn(marker, text, f'art. {number}')

    def test_notas_de_producao_de_efeitos_preservadas(self):
        text = nl.md_text_all(self.body)
        self.assertIn('produzindo efeitos a partir de 1/1/2018', text)
        self.assertIn('produzindo efeitos a partir de 1º/1/2025', text)

    def test_nao_presume_vigencia_da_lc_238(self):
        # as remissões não alteram o texto: o limite de MEI do art. 18-A, § 1º, continua o da edição consultada
        paragraph = nl.md_plain(device(self.body, '18-A', '§ 1º'), True)
        self.assertIn('R$ 81.000,00', paragraph)
        self.assertNotIn('R$ 140.000,00', nl.md_text_all(self.body))
        entry = next(d for d in self.manifest['documentos'] if d['id'] == 'br-federal-lei-complementar-2006-12-14-123')
        effect = entry['efeitos_diferidos_detalhe'][0]
        self.assertEqual(effect['remissoes_na_edicao'], ['art. 18-A', 'art. 18-C', 'art. 48', 'art. 49'])
        joined = ' '.join(effect['texto_da_fonte_modificadora'])
        self.assertIn('1º de janeiro de 2028', joined)
        self.assertIn('1º de janeiro de 2027', joined)
        self.assertIn('não incorpora', effect['leitura'])

    def test_edicao_consultada_registrada(self):
        self.assertEqual(self.meta['fonte_orgao'], nl.CAMARA)
        self.assertIn('normaatualizada', self.meta['fonte_url'])
        self.assertRegex(self.meta['capturado_em'], r'^\d{4}-')
        self.assertRegex(self.meta['sha256_fonte'], r'^[0-9a-f]{64}$')
        proof = json.loads((ROOT / 'provas/nucleo-licitacoes/lc123-anterior-vs-nova.json').read_text())
        self.assertEqual(proof['artigos_com_remissao_lc238_antes'], [])
        self.assertEqual(proof['artigos_com_remissao_lc238_agora'], ['18-A', '18-C', '48', '49'])
        self.assertEqual(proof['artigos_com_texto_diferente'], [])

    def test_anexos_e_tabelas_preservados(self):
        self.assertEqual(self.meta['tabelas'], 10)
        self.assertEqual(self.body.count('<table>'), 10)
        self.assertGreaterEqual(self.meta['anexos_no_corpo'], 5)
        for roman in ('I', 'II', 'III', 'IV', 'V'):
            self.assertRegex(self.body, rf'(?m)^ANEXO {roman}$')
        self.assertIn('<td>4,00%</td>', self.body)  # alíquota da primeira faixa do Anexo I
        self.assertNotIn('data:image', self.body)

    def test_divergencia_entre_fontes_sinalizada_no_arquivo(self):
        self.assertIn('art. 47', self.body)
        self.assertIn('art. 87-B', self.body)

    def test_divergencias_conhecidas_no_manifesto_por_dispositivo(self):
        entry = next(d for d in self.manifest['documentos'] if d['id'] == nl.LC123_SLUG)
        known = entry['divergencias_conhecidas']
        self.assertEqual(set(known), set(nl.LC123_NOTE_ARTICLES))
        self.assertNotEqual(known, {}, 'conflito documentado não pode coexistir com mapa vazio')
        for art in nl.LC123_NOTE_ARTICLES:
            rec = known[art]
            for field in nl.DIVERGENCIA_FIELDS:
                self.assertIn(field, rec, field)
                self.assertTrue(rec[field], field)
            self.assertEqual(rec['natureza'], 'juridica')
            self.assertIn('camara-lc123', rec['fontes'])
            self.assertIn('planalto-lc123', rec['fontes'])
            self.assertIn(art, rec['dispositivo'])
            # tratamento registra a fonte seguida sem eleger outra redação
            self.assertIn('Câmara', rec['tratamento'])
            self.assertNotIn('substitui', rec['tratamento'].lower())

    def test_aviso_provas_e_manifesto_coerentes_nas_divergencias(self):
        entry = next(d for d in self.manifest['documentos'] if d['id'] == nl.LC123_SLUG)
        known = entry['divergencias_conhecidas']
        note = self.body
        for art in nl.LC123_NOTE_ARTICLES:
            self.assertIn(f'art. {art}', note)
            self.assertIn(art, known)
        proof = json.loads((ROOT / 'provas/nucleo-licitacoes' /
                            f'reconciliacao-{nl.LC123_SLUG}.json').read_text())
        arts = proof['fontes_conferencia'][0]['artigos']
        self.assertIn('47', arts['divergencias_substanciais'])
        self.assertIn('87-B', arts['apenas_na_principal'])
        self.assertEqual(set(arts['divergencias_editoriais']), set(nl.LC123_EDITORIAL))
        for art in ('63', '64', '89'):
            self.assertNotIn(art, arts['divergencias_substanciais'])
            self.assertIn(art, arts['divergencias_editoriais'])
        self.assertEqual(set(arts['marcadores_veto']), set(nl.LC123_VETO_MARKERS))
        for art in nl.LC123_VETO_MARKERS:
            self.assertIn(art, arts['apenas_na_principal'])
            self.assertIn('veto', arts['marcadores_veto'][art].lower())
        # mapa vazio no manifesto é incompatível com conflito jurídico documentado
        self.assertTrue(known)
        self.assertEqual(set(known), {'47', '87-B'})


class TestRevogadas(unittest.TestCase):
    def test_8666_e_10520_incluidas_com_procedencia_e_revogacao(self):
        for rel, number, url in ((L8666, '8666', 'https://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm'),
                                 (L10520, '10520', 'https://www.planalto.gov.br/ccivil_03/leis/2002/l10520.htm')):
            meta, body = load(rel)
            self.assertEqual(meta['norma_numero'], number)
            self.assertEqual(meta['situacao'], 'revogada')
            self.assertIn('14.133', meta['situacao_fundamento'])
            self.assertEqual(meta['fonte_url'], url)
            self.assertEqual(meta['edicao_tipo'], 'consolidada')
            self.assertRegex(meta['sha256_fonte'], r'^[0-9a-f]{64}$')
            self.assertIn('Revogado pela Lei nº 14.133, de 2021', nl.md_text_all(body))
            self.assertIn('não como fundamento atual', body)
            self.assertIs(meta['vigencia_certificada'], False)

    def test_8666_integral_com_126_artigos(self):
        _, body = load(L8666)
        keys = nl.split_articles(blocks_of(body))[1]
        numbers = {k.split('-')[0] for k in keys}
        self.assertTrue({str(n) for n in range(1, 127)} <= numbers)

    def test_10520_integral_com_13_artigos(self):
        _, body = load(L10520)
        numbers = {k.split('-')[0] for k in nl.split_articles(blocks_of(body))[1]}
        self.assertTrue({str(n) for n in range(1, 14)} <= numbers)


class TestLei13303(unittest.TestCase):
    def test_corpo_preservado_e_conferido(self):
        meta, body = load(L13303)
        self.assertEqual(hashlib.sha256(body.encode()).hexdigest(), nl.BASELINE_SHA256[L13303])
        self.assertEqual(meta['sha256_corpo_preservado'], nl.BASELINE_SHA256[L13303])
        self.assertEqual(meta['capturado_em'], 'desconhecido')
        proof = json.loads((ROOT / 'provas/nucleo-licitacoes/reconciliacao-br-federal-lei-2016-06-30-13303.json').read_text())
        self.assertEqual(proof['artigos']['divergentes'], [])
        self.assertEqual(proof['artigos']['identicos'], proof['artigos']['artigos_fonte_principal'])


class TestContratoDeMetadados(unittest.TestCase):
    def test_todos_os_documentos_cumprem_o_contrato(self):
        for rel in ALL:
            meta, body = load(rel)
            self.assertEqual(nl.validate_meta(meta, rel), [], rel)
            self.assertEqual(hashlib.sha256(body.encode()).hexdigest(), meta['sha256_markdown'], rel)

    def test_manifesto_coincide_com_cabecalhos(self):
        manifest = json.loads(nl.MANIFESTO.read_text())
        self.assertEqual(sorted(d['arquivo'] for d in manifest['documentos']), sorted(ALL))
        for entry in manifest['documentos']:
            meta, _ = load(entry['arquivo'])
            for key, value in meta.items():
                self.assertEqual(entry[key], value, (entry['arquivo'], key))
            for proof in entry['provas']:
                self.assertTrue((ROOT / 'provas/nucleo-licitacoes' / proof).is_file(), proof)

    def test_edicoes_distinguiveis_por_arquivo(self):
        ids = {}
        for rel in ALL:
            meta, _ = load(rel)
            ids.setdefault(meta['edicao_id'], []).append(rel)
        self.assertTrue(all(len(v) == 1 for v in ids.values()), ids)
        a, _ = load(HIST)
        b, _ = load(CONS)
        self.assertEqual(a['norma_id'], b['norma_id'])
        self.assertNotEqual(a['edicao_id'], b['edicao_id'])

    def test_violacoes_sao_detectadas(self):
        meta, _ = load(CONS)
        self.assertEqual(nl.validate_meta(meta), [])
        broken = dict(meta, vigencia_certificada=True)
        self.assertTrue(any('vigencia_certificada' in e for e in nl.validate_meta(broken)))
        broken = {k: v for k, v in meta.items() if k != 'capturado_em'}
        self.assertTrue(any('capturado_em' in e and 'desconhecido' in e for e in nl.validate_meta(broken)))
        broken = dict(meta, sha256_fonte='zzz')
        self.assertTrue(any('sha256_fonte' in e for e in nl.validate_meta(broken)))
        broken = dict(meta, situacao='revogada', situacao_fundamento='desconhecido')
        self.assertTrue(any('situacao_fundamento' in e for e in nl.validate_meta(broken)))
        broken = dict(meta, edicao_tipo='historica', edicao_integral=True)
        self.assertTrue(any('histórica' in e for e in nl.validate_meta(broken)))

    def test_hashes_das_fontes_conferem_com_os_snapshots(self):
        fontes = json.loads((nl.PROVAS / 'fontes.json').read_text())
        for key, rec in fontes.items():
            if not rec.get('utilizavel'):
                self.assertIn(key, ('camara-14133-html',), 'só a página HTML da Câmara da Lei 14.133 pode faltar')
                self.assertTrue(rec['motivo'])
                continue
            self.assertEqual(hashlib.sha256(nl.read_snapshot(key)).hexdigest(), rec['sha256'], key)


class TestConversor(unittest.TestCase):
    def convert(self, html):
        return nl.convert_html(html.encode('utf-8'), 'utf-8', 'https://exemplo.gov.br/lei/x.htm')

    def test_riscado_ordinais_e_links(self):
        conv = self.convert('<html><body><p>Art. 1<sup>o</sup> Texto <strike>antigo</strike> e '
                            '<span style="text-decoration:line-through">velho</span> '
                            '<a href="../Lei2.htm#art1">(Redação dada pela Lei nº 2)</a></p></body></html>')
        self.assertEqual(conv.blocks, ['Art. 1º Texto ~~antigo~~ e ~~velho~~ '
                                       '[(Redação dada pela Lei nº 2)](https://exemplo.gov.br/Lei2.htm#art1)'])

    def test_tabela_simples_vira_markdown_e_com_mesclagem_vira_html(self):
        conv = self.convert('<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2|3</td></tr></table>'
                            '<table><tr><td colspan="2">T</td></tr><tr><td>x</td><td>y</td></tr></table>')
        self.assertEqual(conv.blocks[0], '| A | B |\n| --- | --- |\n| 1 | 2\\|3 |')
        self.assertTrue(conv.blocks[1].startswith('<table>') and 'colspan="2"' in conv.blocks[1])

    def test_imagem_e_registrada_com_hash_e_omitida(self):
        import base64
        raw = b'\x89PNG\r\n\x1a\nxx'
        conv = self.convert('<p><img src="data:image/png;base64,%s" alt="logo"/>Texto</p>' % base64.b64encode(raw).decode())
        self.assertEqual(conv.blocks, ['Texto'])
        self.assertEqual(conv.images[0]['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(conv.images[0]['bytes'], len(raw))

    def test_layout_de_celula_unica_nao_vira_tabela(self):
        conv = self.convert('<table><tr><td><p>Um</p></td><td><p>Dois</p></td></tr></table>')
        self.assertEqual(conv.blocks, ['Um', 'Dois'])

    def test_notas_nao_contam_no_texto_vigente(self):
        text = nl.strip_notes('Texto. (Redação dada pela Lei nº 1, de 2020) Vigência (VETADO na Lei nº 2, de 2021) Fim')
        self.assertEqual(text.split(), ['Texto.', '(VETADO)', 'Fim'])


class TestReprodutibilidade(unittest.TestCase):
    def test_verify_recalcula_tudo_a_partir_dos_snapshots(self):
        self.assertEqual(nl.verify(), [])


if __name__ == '__main__':
    unittest.main()
