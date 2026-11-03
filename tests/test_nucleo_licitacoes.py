"""Regressões do núcleo de legislação de licitações (Leis 14.133, 13.303, 8.666, 10.520 e LCs 123, 227 e 238).

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
LC227 = 'federal/br-federal-lei-complementar-2026-01-13-227.md'
LC123_PLANALTO = 'federal/edicoes/br-federal-lei-complementar-2006-12-14-123-planalto.md'
LC238 = 'federal/br-federal-lei-complementar-2026-10-21-238.md'
L13303 = 'federal/br-federal-lei-2016-06-30-13303.md'
L8666 = 'federal/br-federal-lei-1993-06-21-8666.md'
L10520 = 'federal/br-federal-lei-2002-07-17-10520.md'
ALL = [HIST, CONS, LC123, LC123_PLANALTO, LC227, LC238, L13303, L8666, L10520]


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
        self.assertEqual(effect['norma_id_modificadora'], 'br-federal-lei-complementar-2026-10-21-238')
        self.assertEqual(effect['arquivo_norma_modificadora'], LC238)
        self.assertTrue((ROOT / effect['arquivo_norma_modificadora']).is_file())
        by_device = {d['dispositivo']: d['efeitos_a_partir_de'] for d in effect['dispositivos_modificados']}
        self.assertEqual(by_device['art. 18-A, §§ 1º e 2º'], '2028-01-01')
        self.assertEqual(by_device['art. 18-C'], '2027-01-01')
        self.assertEqual(by_device['art. 48'], '2027-01-01')
        self.assertEqual(by_device['art. 49'], '2027-01-01')
        joined = ' '.join(effect['texto_da_fonte_modificadora'])
        self.assertIn('1º de janeiro de 2028', joined)
        self.assertIn('1º de janeiro de 2027', joined)
        self.assertIn('não incorpora', effect['leitura'])
        self.assertIn(LC238, effect['leitura'])
        self.assertIn(LC238.split('/')[-1], self.body)

    def test_nota_art87b_preservada_com_cronologia_lc214_lc227(self):
        art87b_blocks = article(self.body, '87-B')
        art87b = ' '.join(nl.md_plain(b, True) for b in art87b_blocks)
        art87b_raw = '\n'.join(art87b_blocks)
        self.assertIn('Lei Complementar nº 214, de 16/1/2025', art87b)
        self.assertIn('produzindo efeitos a partir de 1º/1/2027', art87b)
        self.assertIn('revogado pela Lei Complementar nº 227, de 13/1/2026', art87b)
        self.assertIn('leicomplementar-227-13-janeiro-2026-798657-publicacaooriginal-177770-pl.html', art87b_raw)
        self.assertIn('art. 87-B', self.body)  # aviso editorial
        self.assertIn('não atribui essa data ao evento de revogação', self.body)
        self.assertIn(LC227.split('/')[-1], self.body)
        entry = next(d for d in self.manifest['documentos'] if d['id'] == 'br-federal-lei-complementar-2006-12-14-123')
        effect = next(e for e in entry['efeitos_diferidos_detalhe']
                      if e['norma_id_modificadora'] == 'br-federal-lei-complementar-2026-01-13-227')
        self.assertEqual(effect['arquivo_norma_modificadora'], LC227)
        self.assertTrue((ROOT / LC227).is_file())
        self.assertEqual(effect['fonte_nota_camara'], nl.SOURCES['camara-lc227']['url'])
        by_dev = {d['dispositivo']: d for d in effect['dispositivos_relacionados']}
        self.assertIsNone(by_dev['art. 87-B']['data_especifica_na_revogacao'])
        self.assertEqual(by_dev['art. 87-B']['efeitos_da_inclusao_a_partir_de'], '2027-01-01')
        self.assertEqual(by_dev['art. 31, § 4º']['data_especifica_na_revogacao'], '2026-11-30')
        self.assertEqual(by_dev['art. 18, § 4º, VI']['data_especifica_na_revogacao'], '2033-01-01')
        self.assertIn('art. 87-B', effect['remissoes_na_edicao'])
        known = entry['divergencias_conhecidas']['87-B']
        self.assertIn('1º/1/2027', known['descricao'])
        self.assertIn('sem atribuir essa data à revogação', known['descricao'])
        self.assertIn(LC227, known['tratamento'])

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

    def test_prova_classifica_editoriais_e_vetos_separadamente(self):
        proof = json.loads((ROOT / 'provas/nucleo-licitacoes/reconciliacao-br-federal-lei-complementar-2006-12-14-123.json').read_text())
        art = proof['fontes_conferencia'][0]['artigos']
        self.assertEqual(set(art['divergencias_editoriais']), {'63', '64', '89'})
        self.assertEqual(art['marcadores_de_veto'], ['63-A', '63-B', '63-C', '63-D', '63-E'])
        self.assertEqual(art['divergencias_substanciais_revisadas'], ['47'])
        self.assertIn('47', art['divergencias_substanciais'])
        self.assertIn('87-B', art['apenas_na_principal'])
        self.assertEqual(art['excecoes_revisadas']['dispositivo_exclusivo_conhecido'], ['87-B'])


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
        self.assertEqual(self.meta['edicao_relacionada'], nl.LC123_PLANALTO_SLUG)
        self.assertIn('edicoes/' + nl.LC123_PLANALTO_SLUG, self.body)

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


class TestLC123Planalto(unittest.TestCase):
    """Edição integral alternativa do Planalto: identidade distinta, mesmos conflitos 47/87-B."""

    @classmethod
    def setUpClass(cls):
        cls.meta, cls.body = load(LC123_PLANALTO)
        cls.camara_meta, cls.camara_body = load(LC123)
        cls.manifest = json.loads(nl.MANIFESTO.read_text())
        cls.entry = next(d for d in cls.manifest['documentos'] if d['id'] == nl.LC123_PLANALTO_SLUG)
        cls.proof = json.loads((ROOT / 'provas/nucleo-licitacoes' /
                                f'reconciliacao-{nl.LC123_PLANALTO_SLUG}.json').read_text())
        cls.camara_proof = json.loads((ROOT / 'provas/nucleo-licitacoes' /
                                       f'reconciliacao-{nl.LC123_SLUG}.json').read_text())

    def test_identidade_distinta_mesmo_norma_id(self):
        self.assertEqual(self.meta['norma_id'], self.camara_meta['norma_id'])
        self.assertEqual(self.meta['norma_id'], nl.LC123_SLUG)
        self.assertNotEqual(self.meta['edicao_id'], self.camara_meta['edicao_id'])
        self.assertTrue(self.meta['edicao_id'].endswith('@consolidada-planalto'))
        self.assertTrue(self.camara_meta['edicao_id'].endswith('@consolidada-camara'))
        self.assertEqual(self.meta['edicao_relacionada'], nl.LC123_SLUG)
        self.assertEqual(self.camara_meta['edicao_relacionada'], nl.LC123_PLANALTO_SLUG)
        self.assertEqual(self.meta['fonte_orgao'], nl.PLANALTO)
        self.assertEqual(self.meta['fonte_url'], nl.SOURCES['planalto-lc123']['url'])
        self.assertIs(self.meta['edicao_integral'], True)
        self.assertIs(self.meta['vigencia_certificada'], False)
        self.assertRegex(self.meta['capturado_em'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        self.assertRegex(self.meta['sha256_fonte'], r'^[0-9a-f]{64}$')
        self.assertEqual(self.meta['sha256_fonte'], self.entry['fontes']['principal']['sha256'])

    def test_cobertura_integral_anexos_riscados_e_nao_textuais(self):
        self.assertTrue(self.proof['cobertura_texto']['equivalente'])
        self.assertGreater(self.meta['anexos_no_corpo'], 0)
        self.assertTrue(self.meta['texto_riscado'])
        self.assertGreater(self.entry['conversao']['trechos_riscados'], 0)
        self.assertGreaterEqual(self.meta['imagens_omitidas'], 1)
        self.assertNotIn('data:image', self.body)
        # Anexos e faixas/alíquotas presentes no corpo (Planalto serializa tabelas como parágrafos)
        self.assertRegex(self.body, r'(?m)^ANEXO I\b')
        self.assertIn('4,00%', self.body)
        self.assertIn('Receita Bruta em 12 meses', nl.md_text_all(self.body))
        # Intervalos (r) da Tabela V-A e legenda com < > preservados na cobertura
        self.assertIn('(r)<0,10', nl.md_text_all(self.body))
        self.assertIn('significa menor que', nl.md_text_all(self.body))

    def test_art47_segue_planalto_com_riscado_e_divergencia_explicita(self):
        art47 = '\n'.join(article(self.body, '47'))
        self.assertIn('administração direta e indireta', nl.md_plain(art47, True))
        self.assertTrue(any(b.startswith('~~') for b in article(self.body, '47')))
        camara47 = nl.md_plain('\n'.join(article(self.camara_body, '47')), True)
        self.assertNotEqual(nl.strip_fold(nl.md_plain(art47, False)), nl.strip_fold(camara47))
        self.assertIn('art. 47', self.body)
        self.assertIn('art. 87-B', self.body)
        self.assertEqual(article(self.body, '87-B'), [])

    def test_divergencias_47_87b_nas_duas_edicoes(self):
        known = self.entry['divergencias_conhecidas']
        self.assertEqual(set(known), set(nl.LC123_NOTE_ARTICLES))
        for art in nl.LC123_NOTE_ARTICLES:
            rec = known[art]
            for field in nl.DIVERGENCIA_FIELDS:
                self.assertIn(field, rec)
            self.assertEqual(rec['natureza'], 'juridica')
            self.assertIn('Planalto', rec['tratamento'])
            self.assertNotIn('substitui', rec['tratamento'].lower())
        arts = self.proof['fontes_conferencia'][0]['artigos']
        self.assertIn('47', arts['divergencias_substanciais'])
        self.assertIn('87-B', arts['apenas_na_conferencia'])
        self.assertEqual(set(arts['divergencias_editoriais']), set(nl.LC123_EDITORIAL))
        self.assertEqual(set(arts['marcadores_veto']), set(nl.LC123_VETO_MARKERS))
        self.assertEqual(arts['excecoes_revisadas']['orientacao_fontes'], 'planalto-primary')
        # Câmara continua com a orientação original da trava
        camara_arts = self.camara_proof['fontes_conferencia'][0]['artigos']
        self.assertIn('87-B', camara_arts['apenas_na_principal'])
        self.assertEqual(camara_arts['excecoes_revisadas']['orientacao_fontes'], 'camara-primary')

    def test_nao_incrementa_contagem_de_normas_do_readme(self):
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        # a pasta edicoes é citada como fora da contagem; o arquivo planalto existe
        self.assertIn('edicoes/br-federal-lei-complementar-2006-12-14-123-planalto.md', readme)
        self.assertIn('fora da contagem de normas', readme)
        self.assertTrue(LC123_PLANALTO.startswith('federal/edicoes/'))


class TestLC238(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta, cls.body = load(LC238)
        cls.manifest = json.loads(nl.MANIFESTO.read_text())
        cls.entry = next(d for d in cls.manifest['documentos'] if d['id'] == 'br-federal-lei-complementar-2026-10-21-238')
        cls.proof = json.loads((ROOT / 'provas/nucleo-licitacoes/reconciliacao-br-federal-lei-complementar-2026-10-21-238.json').read_text())

    def test_identidade_edicao_captura_e_hashes(self):
        m = self.meta
        self.assertEqual(m['norma_tipo'], 'lei-complementar')
        self.assertEqual(m['norma_numero'], '238')
        self.assertEqual(m['norma_data'], '2026-10-21')
        self.assertEqual(m['edicao_tipo'], 'consolidada')
        self.assertIs(m['edicao_integral'], True)
        self.assertEqual(m['fonte_orgao'], nl.PLANALTO)
        self.assertEqual(m['fonte_url'], nl.SOURCES['planalto-lc238']['url'])
        self.assertEqual(m['fonte_conferencia'], 'nenhuma')
        self.assertRegex(m['capturado_em'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        self.assertRegex(m['sha256_fonte'], r'^[0-9a-f]{64}$')
        self.assertEqual(m['sha256_fonte'], self.entry['fontes']['principal']['sha256'])
        self.assertEqual(m['situacao'], 'nao-informada')
        self.assertIs(m['vigencia_certificada'], False)
        self.assertIn('não antecipa', self.body)

    def test_texto_integral_e_cobertura(self):
        text = nl.md_text_all(self.body)
        self.assertIn('R$ 140.000,00', text)
        self.assertIn('R$ 11.666,67', text)
        self.assertIn('art. 75', text)  # alteração do art. 48
        self.assertIn('microempreendedores individuais', text)
        self.assertIn('DOU de 21.10.2026', text)
        self.assertTrue(self.proof['cobertura_texto']['equivalente'])
        self.assertEqual(self.proof['fontes_conferencia'], [])
        numbers = {k.split('-')[0] for k in nl.split_articles(blocks_of(self.body))[1]}
        self.assertTrue({str(n) for n in range(1, 11)} <= numbers)

    def test_art10_literal_sem_antecipar_aplicacao(self):
        art10 = ' '.join(nl.md_plain(b, True) for b in article(self.body, '10'))
        self.assertIn('1º de janeiro de 2028', art10)
        self.assertIn('1º de janeiro de 2027', art10)
        self.assertIn('art. 18-A, §§ 1º e 2º', art10)
        self.assertIn('demais dispositivos', art10)
        effect = self.entry['efeitos_diferidos_detalhe'][0]
        joined = ' '.join(effect['texto_da_fonte'])
        self.assertIn('1º de janeiro de 2028', joined)
        self.assertIn('1º de janeiro de 2027', joined)
        altera = effect['altera_norma']
        self.assertEqual(altera['norma_id'], 'br-federal-lei-complementar-2006-12-14-123')
        self.assertEqual(altera['arquivo'], LC123)
        self.assertEqual(altera['dispositivos'], ['art. 18-A', 'art. 18-C', 'art. 48', 'art. 49'])
        by_device = {d['dispositivo']: d['efeitos_a_partir_de'] for d in altera['dispositivos_modificados']}
        self.assertEqual(by_device['art. 18-A, §§ 1º e 2º'], '2028-01-01')
        self.assertTrue(any(d['efeitos_a_partir_de'] == '2027-01-01' for d in altera['dispositivos_modificados']))
        # a LC 123 consultada permanece com o limite antigo
        _, lc123_body = load(LC123)
        self.assertIn('R$ 81.000,00', nl.md_plain(device(lc123_body, '18-A', '§ 1º'), True))
        self.assertNotIn('R$ 140.000,00', nl.md_text_all(lc123_body))

    def test_imagem_institucional_omitida_e_links_resolviveis(self):
        self.assertEqual(self.meta['imagens_omitidas'], 1)
        self.assertNotIn('data:image', self.body)
        self.assertGreaterEqual(self.meta.get('anexos_no_corpo', 0), 0)
        self.assertIn('](https://www.planalto.gov.br/', self.body)
        self.assertIn('lcp123.htm', self.body)


class TestLC227(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta, cls.body = load(LC227)
        cls.manifest = json.loads(nl.MANIFESTO.read_text())
        cls.entry = next(d for d in cls.manifest['documentos'] if d['id'] == 'br-federal-lei-complementar-2026-01-13-227')
        cls.proof = json.loads((ROOT / 'provas/nucleo-licitacoes/reconciliacao-br-federal-lei-complementar-2026-01-13-227.json').read_text())
        cls.fontes = json.loads((ROOT / 'provas/nucleo-licitacoes/fontes.json').read_text())

    def test_identidade_edicao_captura_e_hashes(self):
        m = self.meta
        self.assertEqual(m['norma_tipo'], 'lei-complementar')
        self.assertEqual(m['norma_numero'], '227')
        self.assertEqual(m['norma_data'], '2026-01-13')
        self.assertEqual(m['edicao_tipo'], 'consolidada')
        self.assertIs(m['edicao_integral'], True)
        self.assertEqual(m['fonte_orgao'], nl.PLANALTO)
        self.assertEqual(m['fonte_url'], nl.SOURCES['planalto-lc227']['url'])
        self.assertEqual(m['fonte_conferencia'], 'nenhuma')
        self.assertRegex(m['capturado_em'], r'^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$')
        self.assertRegex(m['sha256_fonte'], r'^[0-9a-f]{64}$')
        self.assertEqual(m['sha256_fonte'], self.entry['fontes']['principal']['sha256'])
        self.assertEqual(m['situacao'], 'nao-informada')
        self.assertIs(m['vigencia_certificada'], False)
        self.assertIn('não atribui 2027 a toda revogação', self.body)

    def test_texto_integral_cobertura_e_anexos_tabelas(self):
        text = nl.md_text_all(self.body)
        self.assertIn('Comitê Gestor do Imposto sobre Bens e Serviços', text)
        self.assertIn('Art. 181. Revogam-se', text)
        self.assertIn('o art. 87-B, na redação dada pelo art. 517', text)
        self.assertIn('em 30 de novembro de 2026, o § 4º do art. 31', text)
        self.assertIn('em 1º de janeiro de 2033, o inciso VI do § 4º do art. 18', text)
        self.assertTrue(self.proof['cobertura_texto']['equivalente'])
        self.assertEqual(self.proof['fontes_conferencia'], [])
        numbers = {k.split('-')[0] for k in nl.split_articles(blocks_of(self.body))[1]}
        self.assertTrue({'1', '181', '182'} <= numbers)
        self.assertEqual(self.meta['imagens_omitidas'], 1)
        self.assertNotIn('data:image', self.body)
        self.assertEqual(self.meta['tabelas'], 9)
        self.assertEqual(self.body.count('<table>'), 9)
        self.assertGreaterEqual(self.meta['anexos_no_corpo'], 1)

    def test_arts_181_182_literais_sem_atribuir_2027_a_toda_revogacao(self):
        art181 = ' '.join(nl.md_plain(b, True) for b in article(self.body, '181'))
        self.assertIn('art. 87-B', art181)
        self.assertIn('30 de novembro de 2026', art181)
        self.assertIn('1º de janeiro de 2033', art181)
        art182 = ' '.join(nl.md_plain(b, True) for b in article(self.body, '182'))
        self.assertIn('1º de janeiro de 2027', art182)
        self.assertIn('demais dispositivos', art182)
        self.assertIn('eleição do Presidente do CGIBS', art182)
        revog, efeitos = self.entry['efeitos_diferidos_detalhe']
        self.assertEqual(revog['dispositivo'], 'art. 181')
        self.assertEqual(efeitos['dispositivo'], 'art. 182')
        by_dev = {d['dispositivo']: d for d in revog['altera_norma']['dispositivos_relacionados']}
        self.assertIsNone(by_dev['art. 87-B']['data_especifica_na_revogacao'])
        self.assertEqual(by_dev['art. 31, § 4º']['data_especifica_na_revogacao'], '2026-11-30')
        self.assertEqual(by_dev['art. 18, § 4º, VI']['data_especifica_na_revogacao'], '2033-01-01')
        joined182 = ' '.join(efeitos['texto_da_fonte'])
        self.assertIn('1º de janeiro de 2027', joined182)
        self.assertIn('demais dispositivos', joined182)

    def test_evidencia_camara_capturada_e_vinculo_lc123(self):
        cam = self.fontes['camara-lc227']
        self.assertTrue(cam['utilizavel'])
        self.assertEqual(cam['url'], nl.SOURCES['camara-lc227']['url'])
        self.assertRegex(cam['sha256'], r'^[0-9a-f]{64}$')
        self.assertTrue((ROOT / 'provas/nucleo-licitacoes/fontes' / 'camara-lc-227-publicacaooriginal.html.xz').is_file())
        evid = self.entry['fontes']['evidencia_nota_camara']
        self.assertEqual(evid['chave'], 'camara-lc227')
        self.assertEqual(evid['sha256'], cam['sha256'])
        self.assertIn('publicacaooriginal', self.body)
        _, lc123_body = load(LC123)
        art87b = ' '.join(nl.md_plain(b, True) for b in article(lc123_body, '87-B'))
        self.assertIn('revogado pela Lei Complementar nº 227', art87b)
        # LC 123 não incorpora redação do 87-B além da nota
        self.assertLess(len(art87b), 500)


class TestTravaGeracaoLC123(unittest.TestCase):
    """A trava de compute() deve recusar diferenças novas; hashes/cobertura das fontes permanecem."""

    @classmethod
    def setUpClass(cls):
        cls.fontes = json.loads((nl.PROVAS / 'fontes.json').read_text())
        cls.base_sources = {
            key: nl.read_snapshot(key) if cls.fontes[key].get('utilizavel') else None
            for key in nl.SOURCES
        }

    def _compute_with(self, mutate):
        sources = dict(self.base_sources)
        fontes = json.loads(json.dumps(self.fontes))
        mutate(sources, fontes)
        return nl.compute(sources, fontes)

    def test_recusa_divergencia_nova_no_art_42(self):
        def mutate(sources, fontes):
            key = 'camara-lc123'
            text = sources[key].decode('utf-8')
            self.assertEqual(text.count('Nas licitações públicas'), 1)
            sources[key] = text.replace('Nas licitações públicas', 'Nas licitações privadas').encode('utf-8')
            fontes[key]['sha256'] = nl.sha256(sources[key])

        with self.assertRaises(SystemExit) as ctx:
            self._compute_with(mutate)
        message = str(ctx.exception)
        self.assertIn('42', message)
        self.assertIn('sem revisão', message)

    def test_recusa_alteracao_adicional_em_artigo_com_excecao_conhecida(self):
        def mutate(sources, fontes):
            key = 'camara-lc123'
            text = sources[key].decode('utf-8')
            # art. 47 já é exceção revisada; mudar seu texto deve invalidar a impressão digital
            marker = 'Nas contratações públicas da União, dos Estados e dos'
            self.assertIn(marker, text)
            sources[key] = text.replace(marker, marker + ' Territórios e', 1).encode('utf-8')
            fontes[key]['sha256'] = nl.sha256(sources[key])

        with self.assertRaises(SystemExit) as ctx:
            self._compute_with(mutate)
        message = str(ctx.exception)
        self.assertIn('47', message)
        self.assertIn('diverge da revisão', message)

    def test_recusa_dispositivo_exclusivo_novo(self):
        def mutate(sources, fontes):
            key = 'camara-lc123'
            text = sources[key].decode('utf-8')
            insert = '\n<p>Art. 42-Z. (Dispositivo exclusivo fabricado para o teste)</p>\n'
            anchor = 'Art.\n43.'
            self.assertIn(anchor, text)
            sources[key] = text.replace(anchor, insert + anchor, 1).encode('utf-8')
            fontes[key]['sha256'] = nl.sha256(sources[key])

        with self.assertRaises(SystemExit) as ctx:
            self._compute_with(mutate)
        message = str(ctx.exception)
        self.assertIn('42-Z', message)
        self.assertIn('exclusivos', message)

    def test_recusa_alteracao_adicional_no_art_121_da_lei_14133(self):
        def mutate(sources, fontes):
            key = 'planalto-14133'
            text = sources[key].decode('cp1252')
            # art. 121 é a única exceção conhecida; qualquer outra mudança no artigo deve falhar
            marker = 'A inadimplência do contratado em relação aos encargos trabalhistas'
            self.assertIn(marker, text)
            sources[key] = text.replace(marker, 'A inadimplência reiterada do contratado em relação aos encargos trabalhistas', 1).encode('cp1252')
            fontes[key]['sha256'] = nl.sha256(sources[key])

        with self.assertRaises(SystemExit) as ctx:
            self._compute_with(mutate)
        message = str(ctx.exception)
        self.assertIn('121', message)
        self.assertRegex(message, r'diverge da revisão|não explicadas|não é o tipográfico')


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
            self.assertIn('fundamento atual', body)
            self.assertIs(meta['vigencia_certificada'], False)

    def test_8666_integral_com_126_artigos(self):
        _, body = load(L8666)
        keys = nl.split_articles(blocks_of(body))[1]
        numbers = {k.split('-')[0] for k in keys}
        self.assertTrue({str(n) for n in range(1, 127)} <= numbers)

    def test_8666_eventos_revogacao_por_dispositivo_fundamento_e_data(self):
        """Recupera os dois eventos distintos (193, I em 2021 e 193, II, a em 2023)."""
        manifest = json.loads(nl.MANIFESTO.read_text())
        entry = next(d for d in manifest['documentos'] if d['arquivo'] == L8666)
        eventos = entry['eventos_revogacao']
        self.assertEqual([e['id'] for e in eventos],
                         ['lei8666-revogacao-parcial-193-I', 'lei8666-revogacao-193-II-a'])

        parcial = eventos[0]
        self.assertEqual(parcial['tipo'], 'revogacao-parcial')
        self.assertEqual(parcial['alcance'], 'arts. 89 a 108')
        self.assertEqual(parcial['dispositivos'], nl.ARTS_8666_193_I)
        self.assertEqual(parcial['dispositivos'], [f'art. {n}' for n in range(89, 109)])
        self.assertEqual(parcial['fundamento']['norma_id'], 'br-federal-lei-2021-04-01-14133')
        self.assertEqual(parcial['fundamento']['dispositivo'], 'art. 193, I')
        self.assertIn('na data de publicação desta Lei', parcial['fundamento']['texto_literal'])
        self.assertEqual(parcial['data']['valor'], '2021-04-01')
        self.assertEqual(parcial['data']['origem'], 'resolvida-da-publicacao-oficial')
        self.assertEqual(parcial['data']['expressao_na_fonte'], 'na data de publicação desta Lei')
        prova = parcial['data']['prova']
        fontes = json.loads((nl.PROVAS / 'fontes.json').read_text())
        self.assertEqual(prova['fonte_chave'], 'planalto-14133')
        self.assertEqual(prova['sha256_fonte'], fontes['planalto-14133']['sha256'])
        self.assertEqual(parcial['fundamento']['sha256_fonte'], fontes['planalto-14133']['sha256'])
        self.assertRegex(prova['trecho'], r'DOU de 1[ºo]\.4\.2021')
        self.assertIn('não é data de aplicação a contratos concretos', parcial['leitura'])
        self.assertIn('art. 191', parcial['leitura'])

        integral = eventos[1]
        self.assertEqual(integral['tipo'], 'revogacao')
        self.assertEqual(integral['fundamento']['dispositivo'], 'art. 193, II, a')
        self.assertIn('198', integral['fundamento']['norma_modificadora'])
        self.assertEqual(integral['data']['valor'], '2023-12-30')
        self.assertEqual(integral['data']['origem'], 'informada-explicitamente')
        self.assertEqual(integral['data']['expressao_na_fonte'], 'em 30 de dezembro de 2023')
        self.assertNotIn('prova', integral['data'])
        self.assertIn('nem aplica essa data a contratos concretos', integral['leitura'])
        self.assertEqual(entry['revogacao']['data_revogacao'], '2023-12-30')
        self.assertIn('art. 193, I', entry['situacao_fundamento'])
        self.assertIn('eventos_revogacao', entry['situacao_fundamento'])
        for origem in (parcial['data']['origem'], integral['data']['origem']):
            self.assertIn(origem, nl.REVOGACAO_DATA_ORIGENS)

    def test_8666_arts_89_a_108_permanecem_riscados_no_corpo(self):
        _, body = load(L8666)
        for number in range(89, 109):
            blocks = article(body, str(number))
            self.assertTrue(blocks, f'art. {number} ausente')
            self.assertTrue(all(b.startswith('~~') for b in blocks if b.strip()),
                            f'art. {number} deve permanecer riscado (redação histórica preservada)')

    def test_8666_aviso_diferencia_publicacao_vigencia_e_transicao(self):
        meta, body = load(L8666)
        self.assertIn('arts. 89 a 108 na publicação', body)
        self.assertIn('30/12/2023', body)
        self.assertIn('não aplica essas datas a contratos concretos', body)
        self.assertIn('hipóteses de transição', body)
        self.assertIs(meta['vigencia_certificada'], False)
        self.assertIn('193, I', meta['situacao_fundamento'])
        self.assertIn('193, II, a', meta['situacao_fundamento'])

    def test_10520_integral_com_13_artigos(self):
        _, body = load(L10520)
        numbers = {k.split('-')[0] for k in nl.split_articles(blocks_of(body))[1]}
        self.assertTrue({str(n) for n in range(1, 14)} <= numbers)

    def test_dou_publication_from_planalto_resolve_data_sem_inventar(self):
        data = nl.read_snapshot('planalto-14133')
        iso, trecho = nl.dou_publication_from_planalto(data, nl.SOURCES['planalto-14133']['charset'])
        self.assertEqual(iso, '2021-04-01')
        self.assertIn('DOU de 1º.4.2021', trecho)
        self.assertLess(len(trecho), 120)
        # sem rodapé reconhecível → desconhecido (não inventa)
        fake = b'<html><body><p>Sem rodape de DOU</p></body></html>'
        self.assertEqual(nl.dou_publication_from_planalto(fake, 'utf-8'), (None, None))


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

    def test_espaco_entre_riscados_adjacentes_e_angulos_escapados_na_cobertura(self):
        html = ('<html><body><p><s>§ 4º </s>'
                '<span style="text-decoration:line-through">Os Comitês elaborarão.</span></p>'
                '<p><span style="text-decoration:line-through">'
                'onde “&lt;” significa menor que, “&gt;” significa maior que'
                '</span></p></body></html>')
        conv = self.convert(html)
        self.assertEqual(conv.blocks[0], '~~§ 4º Os Comitês elaborarão.~~')
        body = '\n\n'.join(conv.blocks)
        plain = nl.md_text_all(body)
        self.assertIn('§ 4º Os Comitês', plain)
        self.assertIn('“<” significa menor que', plain)
        self.assertIn('“>” significa maior que', plain)
        src = nl.strip_fold(nl.source_text_chars_from_html(html.encode('utf-8'), 'utf-8'))
        self.assertEqual(src, nl.strip_fold(plain))

    def test_tabela_simples_vira_markdown_e_com_mesclagem_vira_html(self):
        conv = self.convert('<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2|3</td></tr></table>'
                            '<table><tr><td colspan="2">T</td></tr><tr><td>x</td><td>y</td></tr></table>')
        self.assertEqual(conv.blocks[0], '| A | B |\n| --- | --- |\n| 1 | 2\\|3 |')
        self.assertTrue(conv.blocks[1].startswith('<table>') and 'colspan="2"' in conv.blocks[1])

    def test_tabela_html_preserva_rotulo_sem_sintaxe_de_link_markdown(self):
        conv = self.convert('<table><tr><td colspan="2"><a href="lei.htm#faixas">Faixas</a></td></tr>'
                            '<tr><td>1</td><td>2</td></tr></table>')
        from bs4 import BeautifulSoup
        cell = BeautifulSoup(conv.blocks[0], 'lxml').find('th')
        self.assertEqual(cell.get_text(), 'Faixas')
        self.assertNotIn('[Faixas]', conv.blocks[0])

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
