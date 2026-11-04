"""Cobertura por identidade dos catálogos DLG/RSF/RCD/RCN e do lote Markdown."""
from __future__ import annotations

import json
import lzma
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import especies_legislativas_federais as lote  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/especies-legislativas-federais'


class TestEspeciesLegislativasFederais(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogos = json.loads((PROVAS / 'catalogos.json').read_text(encoding='utf-8'))
        cls.manifesto = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))
        cls.fontes = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
        cls.limites = json.loads((PROVAS / 'limites-catalogos.json').read_text(encoding='utf-8'))
        cls.recs = {
            tipo: json.loads((PROVAS / f'reconciliacao-{tipo.lower()}.json').read_text(encoding='utf-8'))
            for tipo in lote.SPECIES
        }

    def test_catalogos_preservados_com_hash(self):
        for tipo, info in self.catalogos['especies'].items():
            with self.subTest(tipo=tipo):
                raw = lzma.decompress((ROOT / info['snapshot']).read_bytes())
                self.assertEqual(nl.sha256(raw), info['sha256'])
                self.assertEqual(len(lote.parse_lista(raw)), info['registros'])
                self.assertEqual(info['registros'], self.recs[tipo]['catalogo_registros'])
                self.assertGreater(info['registros'], 0)

    def test_reconciliacao_cobre_todas_as_identidades(self):
        published = {p.stem for p in (ROOT / 'federal').glob('br-federal-*.md')}
        for tipo, rec in self.recs.items():
            with self.subTest(tipo=tipo):
                self.assertEqual(len(rec['itens']), rec['catalogo_registros'])
                self.assertEqual(rec['orgao_emissor'], lote.SPECIES[tipo]['orgao_emissor'])
                slugs = set()
                for item in rec['itens']:
                    self.assertEqual(item['tipo'], tipo)
                    self.assertTrue(item['senado_id'])
                    self.assertTrue(item['slug'].startswith(f"br-federal-{lote.SPECIES[tipo]['slug_tipo']}-"))
                    expected = lote.slug_for(tipo, item['data'], item['numero'] or 'sn', item.get('complemento'))
                    self.assertEqual(item['slug'], expected)
                    self.assertIn(item['estado_coleta'], {
                        'publicado', 'identificado-nao-coletado', 'anexos-pendentes', 'fonte-sem-html',
                    })
                    self.assertNotIn(item['slug'], slugs)
                    slugs.add(item['slug'])
                    if item['estado_coleta'] == 'publicado':
                        self.assertIn(item['slug'], published)
                        self.assertTrue((ROOT / item['caminho_publicado']).is_file())
                    else:
                        self.assertIsNone(item['caminho_publicado'])
                self.assertEqual(len(slugs), rec['catalogo_registros'])
                self.assertEqual(rec['publicados'], sum(1 for i in rec['itens'] if i['estado_coleta'] == 'publicado'))

    def test_especies_nao_se_confundem(self):
        tipos = {doc['tipo'] for doc in self.manifesto['documentos']}
        self.assertTrue(tipos <= set(lote.SPECIES))
        # Identidade = espécie + número + data (+ complemento no slug).
        # O mesmo número em anos distintos é norma distinta.
        by_identity = {}
        for doc in self.manifesto['documentos']:
            key = (doc['tipo'], doc['norma']['numero'], doc['norma']['data'])
            by_identity.setdefault(key, []).append(doc['id'])
        for key, ids in by_identity.items():
            self.assertEqual(len(ids), 1, key)
        # Espécies distintas nunca compartilham o mesmo slug mesmo com número igual.
        slugs = [doc['id'] for doc in self.manifesto['documentos']]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_markdown_do_lote_reconverte(self):
        self.assertGreaterEqual(len(self.manifesto['documentos']), 20)
        for doc in self.manifesto['documentos']:
            slug = doc['id']
            with self.subTest(slug=slug):
                path = ROOT / doc['arquivo']
                text = path.read_text(encoding='utf-8')
                meta, body = nl.parse_frontmatter(text)
                self.assertEqual(meta['sha256_markdown'], nl.sha256(body.encode('utf-8')))
                self.assertIs(meta['vigencia_certificada'], False)
                self.assertEqual(meta['especie_codigo_senado'], self.fontes[slug]['tipo'])
                self.assertIn(meta['orgao_emissor'], {
                    'Congresso Nacional', 'Senado Federal', 'Câmara dos Deputados',
                })
                html = lzma.decompress((ROOT / self.fontes[slug]['snapshot']).read_bytes())
                self.assertEqual(nl.sha256(html), self.fontes[slug]['sha256'])
                item = {
                    'slug': slug,
                    'tipo': self.fontes[slug]['tipo'],
                    'fonte_url': self.fontes[slug]['url'],
                    'charset': self.fontes[slug]['charset'],
                    'normaNome': self.fontes[slug].get('normaNome') or meta['titulo'],
                    'numero': self.fontes[slug].get('numero') or meta['norma_numero'],
                    'data': self.fontes[slug].get('data') or meta['norma_data'],
                    'urn': self.fontes[slug].get('urn') or meta['urn'],
                    'ementa': self.fontes[slug].get('ementa'),
                    'capturado_em': self.fontes[slug]['capturado_em'],
                    'sha256_fonte': self.fontes[slug]['sha256'],
                    'snapshot': self.fontes[slug]['snapshot'],
                    'senado_id': self.fontes[slug]['senado_id'],
                    'fonte_orgao': meta.get('fonte_orgao'),
                }
                md2, _ = lote.build_markdown(item, html)
                self.assertEqual(md2, text)

    def test_limites_rcd_pos_1991_declarados(self):
        rcd = self.limites['RCD']
        self.assertEqual(rcd['senado_intervalo_observado']['fim'], '1991-09-25')
        self.assertIn('1991', rcd['aviso'])
        self.assertIn('16/2025', rcd['aviso'])
        self.assertTrue(rcd['fonte_complementar_regimento']['url'].startswith('https://bd.camara.leg.br/'))


if __name__ == '__main__':
    unittest.main()
