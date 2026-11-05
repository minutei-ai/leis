"""Cobertura por identidade — LC 115/2002, LC 147/2014 e LC 1/1962 (issue #68)."""
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
sys.dont_write_bytecode = True
import nucleo_licitacoes as nl  # noqa: E402
import cobertura_nacional as cn  # noqa: E402
import lc_complementares_68 as lc68  # noqa: E402

PROVAS = ROOT / 'provas/lc-complementares-68'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
RECON = json.loads((PROVAS / 'reconciliacao-identidades.json').read_text(encoding='utf-8'))

IDS = {
    '115': 'br-federal-lei-complementar-2002-12-26-115',
    '147': 'br-federal-lei-complementar-2014-08-07-147',
    '1-1962': 'br-federal-lei-complementar-1962-07-17-1',
    '1-1967': 'br-federal-lei-complementar-1967-11-09-1',
}


class TestLcComplementares68(unittest.TestCase):
    def test_arquivos_publicados(self):
        for key, slug in IDS.items():
            path = ROOT / 'federal' / f'{slug}.md'
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding='utf-8')
            self.assertGreater(len(text), 500)
            if key == '1-1967':
                continue
            self.assertTrue(text.startswith('---\n'), f'{slug} deve ter cabeçalho YAML')
            meta, body = nl.parse_frontmatter(text)
            self.assertEqual(meta['norma_id'], slug)
            self.assertEqual(meta['situacao'], 'nao-informada')
            self.assertIs(meta['vigencia_certificada'], False)
            self.assertEqual(meta['sha256_markdown'], nl.sha256(body.encode('utf-8')))
            self.assertNotRegex(body, r'<<\s*(anexo|ANEXO|TABELA)\s*>>')
            self.assertNotIn('@@@', body)

    def test_identidades_distintas_lc1(self):
        a_meta, a = nl.parse_frontmatter((ROOT / f'federal/{IDS["1-1962"]}.md').read_text(encoding='utf-8'))
        b = (ROOT / f'federal/{IDS["1-1967"]}.md').read_text(encoding='utf-8')
        self.assertEqual(a_meta['norma_data'], '1962-07-17')
        self.assertEqual(a_meta['norma_numero'], '1')
        self.assertIn('1962', a)
        self.assertIn('1967', b)
        self.assertIn('parlamentar', a.lower())
        self.assertIn('município', b.lower())
        self.assertNotEqual(
            hashlib.sha256(a.encode()).hexdigest(),
            hashlib.sha256(b.encode()).hexdigest(),
        )
        # 1967 file date must remain 1967 — not rewritten to accommodate 1962
        self.assertRegex(b, r'LEI COMPLEMENTAR Nº 1, DE 9 DE NOVEMBRO DE 1967')
        self.assertNotRegex(b, r'DE 17 DE JULHO DE 1962')

    def test_hashes_senado_115(self):
        slug = IDS['115']
        meta = FONTES[slug]
        pub_meta, body = nl.parse_frontmatter((ROOT / 'federal' / f'{slug}.md').read_text(encoding='utf-8'))
        self.assertEqual(pub_meta['sha256_markdown'], meta['sha256_markdown'])
        self.assertEqual(nl.sha256(body.encode('utf-8')), meta['sha256_markdown'])
        html = lzma.decompress((ROOT / meta['snapshot_html']).read_bytes())
        self.assertEqual(hashlib.sha256(html).hexdigest(), meta['sha256_fonte'])
        self.assertEqual(hashlib.sha256((ROOT / meta['snapshot_html']).read_bytes()).hexdigest(), meta['sha256_snapshot_html'])
        conv = nl.convert_html(html, 'utf-8', meta['fonte_url'])
        # O coletor inseriu um código de catálogo e um marcador literal de anexo.
        # Excluímos somente esses dois blocos conhecidos; o título, a ementa e o
        # cabeçalho ANEXO continuam fazendo parte da comparação da fonte.
        source_blocks = []
        collector_markers = []
        for block in conv.blocks:
            plain = nl.md_plain(block, True).strip()
            if re.fullmatch(r'###LCP-[^\s<>]+@@@', plain):
                collector_markers.append('catalogo')
                continue
            if plain == '<<anexo>>':
                collector_markers.append('anexo')
                continue
            source_blocks.append(plain)
        self.assertCountEqual(collector_markers, ['catalogo', 'anexo'])
        self.assertEqual(
            nl.strip_fold(' '.join(source_blocks)),
            nl.strip_fold(nl.md_text_all(nl.strip_note(body))),
            'LC 115 deve equivaler ao corpo publicado após remover somente nota de edição e marcadores documentados',
        )
        dados = lzma.decompress((ROOT / meta['snapshot_dados']).read_bytes())
        self.assertEqual(hashlib.sha256(dados).hexdigest(), meta['sha256_dados'])
        self.assertIn('ANEXO', body)

    def test_lc147_planalto_com_anexo(self):
        slug = IDS['147']
        meta = FONTES[slug]
        pub_meta, body = nl.parse_frontmatter((ROOT / 'federal' / f'{slug}.md').read_text(encoding='utf-8'))
        self.assertEqual(pub_meta['sha256_markdown'], meta['sha256_markdown'])
        self.assertEqual(pub_meta['fonte_url'], meta['fonte_url'])
        self.assertIn('planalto.gov.br', meta['fonte_url'])
        raw = lzma.decompress((ROOT / meta['snapshot_html']).read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta['sha256_fonte'])
        self.assertEqual(hashlib.sha256((ROOT / meta['snapshot_html']).read_bytes()).hexdigest(), meta['sha256_snapshot_armazenado'])
        conv = nl.convert_html(raw, 'cp1252', meta['fonte_url'])
        source_text = ' '.join(nl.md_plain(block, True) for block in conv.blocks)
        self.assertEqual(
            nl.strip_fold(source_text),
            nl.strip_fold(nl.md_text_all(nl.strip_note(body))),
            'LC 147 deve equivaler ao corpo Markdown a partir do HTML oficial completo com Anexo Único',
        )
        self.assertRegex(body, r'(?m)^ANEXO\b', msg='Anexo Único ausente')
        self.assertGreater(pub_meta.get('tabelas', 0), 0)
        senado = meta['senado_publicacao_original']
        self.assertTrue((ROOT / senado['snapshot_html']).is_file())
        self.assertIn('sem as peças tabulares', senado['limite'].lower())

    def test_lc1_1962_planalto_snapshot(self):
        meta = FONTES[IDS['1-1962']]
        raw = lzma.decompress((ROOT / meta['snapshot_html']).read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), meta['sha256_fonte'])
        pub_meta, body = nl.parse_frontmatter(
            (ROOT / f'federal/{IDS["1-1962"]}.md').read_text(encoding='utf-8'))
        self.assertEqual(pub_meta['sha256_markdown'], meta['sha256_markdown'])
        self.assertEqual(pub_meta['norma_data'], '1962-07-17')
        self.assertIn('LEI COMPLEMENTAR', body[:300])
        self.assertIn('1962', body[:300])
        self.assertTrue(meta.get('cobertura_texto_equivalente'))
        # reconversão bate a cobertura
        conv = nl.convert_html(raw, 'cp1252', meta['fonte_url'])
        rebuilt = nl.blocks_to_markdown(conv.blocks, r'^LEI COMPLEMENTAR')
        src = nl.strip_fold(nl.source_text_chars_from_html(raw, 'cp1252'))
        self.assertEqual(src, nl.strip_fold(nl.md_text_all(rebuilt)))

    def test_lc1_1962_publicacao_original_retificacao_e_planalto_atual(self):
        record = FONTES[IDS['1-1962']]
        original = record['publicacao_original_camara']
        correction = record['retificacao_camara']
        data = record['dados_norma_camara']
        for source in (original, correction, data):
            stored = (ROOT / source['snapshot_html']).read_bytes()
            raw = lzma.decompress(stored)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source['sha256_fonte'])
            self.assertEqual(hashlib.sha256(stored).hexdigest(), source['sha256_snapshot_html'])
        self.assertIn('17/07/1962, p. 7597', original['publicacao_dou'])
        self.assertIn('24/07/1962, p. 7837', correction['publicacao_dou'])
        self.assertEqual(correction['fonte_url'], lc68.CAMARA_RETIFICACAO_URL)
        self.assertEqual(data['fonte_url'], lc68.CAMARA_DADOS_URL)

        original_text = lc68._source_text(lzma.decompress((ROOT / original['snapshot_html']).read_bytes()))
        correction_text = lc68._source_text(lzma.decompress((ROOT / correction['snapshot_html']).read_bytes()))
        self.assertIn('Faço saber que o Congresso Nacional decreta e eu sanciono', original_text)
        self.assertIn('O Congresso Nacional decreta:', original_text)
        self.assertIn('Na página 7.597, 1ª coluna, após a ementa, inclua-se:', correction_text)
        self.assertIn('O Presidente da República - Em seguida ao preâmbulo, exclua-se:', correction_text)
        self.assertIn('O congresso Nacional decreta:', correction_text)
        data_text = BeautifulSoup(
            lzma.decompress((ROOT / data['snapshot_html']).read_bytes()), 'lxml'
        ).get_text(' ', strip=True)
        self.assertIn('Origem: Poder Legislativo', data_text)
        self.assertIn('Publicada no DO como Lei Complementar ao Ato Adicional.', data_text)

        ret_path = ROOT / correction['edicao_markdown']
        ret_meta, ret_body = nl.parse_frontmatter(ret_path.read_text(encoding='utf-8'))
        base_meta, _ = nl.parse_frontmatter(
            (ROOT / f'federal/{IDS["1-1962"]}.md').read_text(encoding='utf-8')
        )
        self.assertEqual(ret_meta['norma_id'], base_meta['norma_id'])
        self.assertNotEqual(ret_meta['edicao_id'], base_meta['edicao_id'])
        self.assertEqual(ret_meta['edicao_tipo'], 'retificacao')
        self.assertEqual(ret_meta['sha256_markdown'], hashlib.sha256(ret_body.encode()).hexdigest())
        _export_parser_meta, exporter_parser_body = cn.parse_frontmatter(ret_path.read_text(encoding='utf-8'))
        self.assertEqual(exporter_parser_body, ret_body)
        self.assertIn('Na página 7.597', ret_body)
        self.assertIn('O Presidente da República', ret_body)
        self.assertIn('O congresso Nacional decreta:', ret_body)
        exported_ret = cn.export_document(correction['edicao_markdown'])
        self.assertEqual(exported_ret['norma_id'], base_meta['norma_id'])
        self.assertNotEqual(exported_ret['edicao_id'], base_meta['edicao_id'])
        self.assertEqual(exported_ret['edicao_tipo'], 'retificacao')
        self.assertEqual(exported_ret['orgao_emissor'], 'desconhecido')
        self.assertEqual(exported_ret['fonte_orgao'], 'Câmara dos Deputados — Legislação Informatizada')
        _export_meta, export_body = cn.parse_frontmatter(ret_path.read_text(encoding='utf-8'))
        self.assertEqual(exported_ret['markdown_integral'], export_body)
        self.assertEqual(exported_ret['sha256_markdown'], ret_meta['sha256_markdown'])

        planalto_raw = lzma.decompress((ROOT / record['snapshot_html']).read_bytes())
        planalto_text = re.sub(r'\s+', ' ', BeautifulSoup(planalto_raw, 'lxml').get_text(' ', strip=True))
        self.assertIn('O Presidente da República Faço saber que o Congresso Nacional decreta', planalto_text)
        self.assertNotIn('O congresso Nacional decreta:', planalto_text)

    def test_lc_emissor_serie_proveniencia_e_export_filters(self):
        exports = {
            key: cn.export_document(f'federal/{slug}.md')
            for key, slug in IDS.items()
        }
        for key in ('115', '147', '1-1962'):
            doc = exports[key]
            self.assertEqual(doc['orgao_emissor'], 'Congresso Nacional')
            self.assertNotEqual(doc['orgao_emissor'], doc['fonte_orgao'])
            self.assertIn('Congresso Nacional decreta', doc['fonte_do_campo']['orgao_emissor'])
            self.assertIn('eu sanciono', doc['fonte_do_campo']['orgao_emissor'])
        self.assertEqual(exports['115']['fonte_orgao'], 'Senado Federal — normas.leg.br')
        self.assertEqual(exports['147']['fonte_orgao'], 'Presidência da República — Planalto')
        self.assertEqual(exports['1-1962']['serie_historica'], 'lei-complementar-ao-ato-adicional')
        self.assertEqual(exports['115']['serie_historica'], 'desconhecido')
        self.assertEqual(exports['147']['serie_historica'], 'desconhecido')
        self.assertEqual(exports['1-1967']['serie_historica'], 'desconhecido')
        self.assertEqual(exports['1-1967']['orgao_emissor'], 'desconhecido')
        self.assertEqual(exports['115']['edicao_tipo'], 'original')
        self.assertIn('https://www2.camara.leg.br/legin/fed/leicom/1960-1969/leicomplementar-1-17-julho-1962-541564-norma-pl.html', exports['1-1962']['fonte_do_campo']['serie_historica'])
        self.assertIn('desconhecido-explicito', exports['1-1967']['fonte_do_campo']['serie_historica'])
        self.assertIn('sha256=', exports['1-1962']['fonte_do_campo']['relacoes'])

        matching = cn.apply_bm25_filters(
            [exports['1-1962'], exports['1-1967']],
            {
                'serie_historica': 'lei-complementar-ao-ato-adicional',
                'numero': '1',
                'data_ato': '1962-07-17',
            },
        )
        self.assertEqual(matching, [exports['1-1962']])
        relation = exports['1-1962']['relacoes'][0]
        self.assertEqual(relation['tipo'], 'retificacao')
        self.assertEqual(relation['escopo_cobertura'], 'parcial')
        self.assertIn('24/07/1962', relation['dispositivo'])

    def test_reconciliacao_catalogo_completa_por_identidade(self):
        cat = RECON['catalogo_senado_lista']
        snapshot = (ROOT / cat['snapshot']).read_bytes()
        self.assertEqual(hashlib.sha256(snapshot).hexdigest(), cat['sha256_snapshot_armazenado'])
        raw = lzma.decompress(snapshot)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), cat['sha256'])
        rows = json.loads(raw)['ListaDocumento']['documentos']['documento']
        self.assertEqual(len(rows), 240)
        self.assertEqual(cat['total_registros'], len(rows))
        entries = RECON['identidades']
        self.assertEqual(len(entries), len(rows))
        self.assertEqual({i['senadoId'] for i in entries}, {r['id'] for r in rows})
        self.assertEqual(len({i['senadoId'] for i in entries}), len(entries))
        paths = []
        for entry in entries:
            row = next(r for r in rows if r['id'] == entry['senadoId'])
            self.assertEqual(entry['catalogo'], row)
            self.assertEqual(entry['norma'], row.get('norma'))
            self.assertEqual(entry['apelido'], row.get('apelido'))
            date = '-'.join(reversed(row['dataassinatura'].split('/')))
            number = re.sub(r'[^0-9A-Za-z-]', '', row['numero']).lower()
            expected = f'federal/br-federal-lei-complementar-{date}-{number}.md'
            self.assertEqual(entry['estado_caminho'], 'correspondencia_exata_data_numero')
            self.assertEqual(entry['caminhos'], [expected])
            self.assertTrue((ROOT / expected).is_file(), expected)
            paths.extend(entry['caminhos'])
        self.assertEqual(len(paths), len(set(paths)), 'um arquivo não pode cobrir duas linhas do catálogo')
        self.assertEqual(len(paths), 240)
        self.assertIn('não o universo histórico brasileiro', ' '.join(RECON['limites']))
        # A série histórica mantém ambas as identidades 1/1962 e 1/1967.
        by_slug = {i['id']: i for i in entries}
        self.assertIn(IDS['1-1962'], by_slug)
        self.assertIn(IDS['1-1967'], by_slug)
        self.assertNotEqual(by_slug[IDS['1-1962']]['senadoId'], by_slug[IDS['1-1967']]['senadoId'])
        self.assertIn('não se certifica vigência', ' '.join(RECON['limites']).lower())

    def test_cobertura_por_numero_no_federal(self):
        names = [p.name for p in (ROOT / 'federal').iterdir() if p.suffix == '.md']
        for number, slug in [('115', IDS['115']), ('147', IDS['147'])]:
            hits = [
                n for n in names
                if n.startswith('br-federal-lei-complementar-')
                and re.search(r'-' + number + r'(?:-|\.md)', n)
            ]
            self.assertIn(slug + '.md', hits)
        hits_1 = [
            n for n in names
            if n.startswith('br-federal-lei-complementar-')
            and re.search(r'-1(?:-|\.md)', n)
        ]
        self.assertIn(IDS['1-1962'] + '.md', hits_1)
        self.assertIn(IDS['1-1967'] + '.md', hits_1)

    def test_lista_lcp_snapshot(self):
        cat = RECON['catalogo_senado_lista']
        snap = ROOT / cat['snapshot']
        self.assertTrue(snap.is_file())
        raw = lzma.decompress(snap.read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), cat['sha256'])
        data = json.loads(raw)
        self.assertIn('ListaDocumento', data)


if __name__ == '__main__':
    unittest.main()
