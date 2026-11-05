"""Cobertura fonte→Markdown do lote de decretos 8001–9000 (#81).

Lê somente o repositório; não acessa a rede. Reconverte os snapshots oficiais
preservados e confere equivalência textual integral. Valida reconciliação
Senado DEC por espécie+número/complemento+data em toda a faixa.
"""
from __future__ import annotations

import json
import lzma
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import federal_decretos_8001_9000 as lote  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/federal-decretos-8001-9000'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
MANIFESTO = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))
RECON = PROVAS / 'catalogo-reconciliacao.json'


class TestFederalDecretos80019000(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docs = lote.all_docs()
        cls.docs = docs
        cls.sources = {
            doc['fonte']: lzma.decompress((ROOT / FONTES[doc['fonte']]['snapshot']).read_bytes())
            for doc in docs
        }
        cls.docs_out, cls.proofs, cls.manifest = lote.compute(cls.sources, FONTES)

    def test_reconciliacao_senado_dec_faixa_completa(self):
        self.assertTrue(RECON.is_file(), RECON)
        recon = json.loads(RECON.read_text(encoding='utf-8'))
        self.assertEqual(recon['criterio_identidade'], 'especie+numero/complemento+data')
        self.assertEqual(recon['totais']['identidades_catalogo'], 1000)
        self.assertEqual(recon['totais']['inteiros_faixa_sem_identidade_catalogo'], 0)
        self.assertEqual(len(recon.get('inteiros_sem_identidade_catalogo') or []), 0)
        # Faixa 8001–9000: 1000 identidades DEC-n; coleta retomável zerou ausentes locais.
        local = lote.local_decretos_faixa()
        self.assertEqual(len(local), 1000)
        self.assertEqual(recon['totais']['ausentes_local'], 0)
        self.assertEqual(recon['totais']['presentes_local'], 1000)
        self.assertEqual(len(local) + recon['totais']['ausentes_local'], 1000)

    def test_lote_publica_seed_e_coletados_na_faixa(self):
        self.assertEqual(MANIFESTO['lote'], 'federal-decretos-8001-9000')
        self.assertGreaterEqual(len(MANIFESTO['documentos']), 400)
        seed_nums = {d['norma']['numero'] for d in lote.SEED_DOCS}
        self.assertEqual(seed_nums, {'8100', '8300', '8500', '8600', '8700', '8800', '8900'})
        for entry in MANIFESTO['documentos']:
            n = int(entry['norma']['numero'])
            self.assertTrue(8001 <= n <= 9000, n)

    def test_snapshots_hashes_e_conteudo_estavel(self):
        for doc in self.docs:
            key = doc['fonte']
            with self.subTest(key=key):
                meta = FONTES[key]
                snap = ROOT / meta['snapshot']
                self.assertTrue(snap.is_file(), snap)
                xz = snap.read_bytes()
                self.assertEqual(nl.sha256(xz), meta['sha256_snapshot_armazenado'])
                raw = lzma.decompress(xz)
                self.assertEqual(nl.sha256(raw), meta['sha256'])
                self.assertEqual(nl.content_sha256(raw), meta['sha256_conteudo'])
                self.assertEqual(len(raw), meta['bytes'])
                self.assertTrue(meta['capturado_em'].endswith('Z'))

    def test_markdown_reconverte_e_cobertura_integral(self):
        for doc in self.docs:
            slug = doc['slug']
            with self.subTest(slug=slug):
                path = ROOT / doc['arquivo']
                text = path.read_text(encoding='utf-8')
                self.assertEqual(text, self.docs_out[slug]['markdown'])
                meta, body = nl.parse_frontmatter(text)
                self.assertEqual(meta['norma_tipo'], 'decreto')
                self.assertEqual(meta['edicao_tipo'], 'historica')
                self.assertEqual(meta['edicao_integral'], nl.UNKNOWN)
                self.assertIs(meta['vigencia_certificada'], False)
                self.assertEqual(meta['norma_numero'], doc['norma']['numero'])
                self.assertEqual(meta['norma_data'], doc['norma']['data'])
                self.assertIn('DECRETO', body)
                self.assertIn('não certifica vigência', body)
                self.assertNotRegex(body, r'<<\s*(ANEXO|TABELA)\s*>>')
                self.assertGreater(len(body), 400, slug)
                proof = self.proofs[slug]
                self.assertTrue(proof['cobertura_texto']['equivalente'])
                published = json.loads(
                    (PROVAS / f'reconciliacao-{slug}.json').read_text(encoding='utf-8')
                )
                self.assertTrue(published['cobertura_texto']['equivalente'])


if __name__ == '__main__':
    unittest.main()
