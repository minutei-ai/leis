"""LGPD — edição histórica preservada e consolidada após Lei 15.352/2026.

Lê somente o repositório (snapshots em provas/lgpd/); não acessa a rede.
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

from lgpd import (  # noqa: E402
    CONSOLIDADA,
    build_historica,
    HISTORICA,
    MANIFESTO,
    MODIFICADORA,
    PROVAS,
    SOURCES,
    extract_device_snippets,
    read_snapshot,
    trim_lgpd_blocks,
)
from nucleo_licitacoes import (  # noqa: E402
    blocks_to_markdown,
    convert_html,
    coverage,
    parse_frontmatter,
    sha256,
)

FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
ALVO = json.loads((PROVAS / 'dispositivos-alvo-mp1317-lei15352.json').read_text(encoding='utf-8'))
VAL15352 = json.loads((PROVAS / 'validacao-lei-15352.json').read_text(encoding='utf-8'))


class TestLgpdEdicoes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta_h, cls.body_h = parse_frontmatter(HISTORICA.read_text(encoding='utf-8'))
        cls.meta_c, cls.body_c = parse_frontmatter(CONSOLIDADA.read_text(encoding='utf-8'))
        m = re.search(r'<!-- nota-edicao:fim -->\n\n(.*)\Z', cls.body_h, re.S)
        assert m, 'histórica sem corpo após nota'
        cls.corpo_h = m.group(1)
        cls.corpo_c = cls.body_c.split('<!-- nota-edicao:fim -->\n\n', 1)[1]

    def test_recusa_alteracao_corpo_historico(self):
        with self.assertRaises(RuntimeError):
            build_historica(self.corpo_h + 'alterado')

    def test_hashes_frontmatter(self):
        self.assertEqual(self.meta_h['edicao_tipo'], 'historica')
        self.assertEqual(self.meta_c['edicao_tipo'], 'consolidada')
        self.assertEqual(self.meta_h['norma_id'], self.meta_c['norma_id'])
        self.assertNotEqual(self.meta_h['edicao_id'], self.meta_c['edicao_id'])
        self.assertEqual(
            self.meta_h['sha256_corpo_preservado'],
            sha256(self.corpo_h.encode('utf-8')),
        )
        self.assertEqual(
            self.meta_c['sha256_markdown'],
            sha256(self.body_c.encode('utf-8')),
        )
        self.assertEqual(
            self.meta_c['sha256_fonte'],
            FONTES['camara-lgpd-atualizada']['sha256'],
        )
        self.assertNotIn(self.meta_c['fonte_url'], self.meta_c['fonte_conferencia'])
        self.assertFalse(self.meta_h['vigencia_certificada'])
        self.assertFalse(self.meta_c['vigencia_certificada'])

    def test_alerta_historica_por_dispositivo(self):
        self.assertIn('Alerta por dispositivo', self.body_h)
        for trecho in [
            'art. 5º, VIII',
            'art. 55-A',
            'art. 55-C',
            'Capítulo IX',
            'Seção I',
            'Lei nº 15.352',
        ]:
            self.assertIn(trecho, self.body_h)
        # Corpo histórico ainda tem Autoridade no 55-A / Cap IX
        self.assertRegex(
            self.corpo_h,
            r'Art\.\s*55-A\.\s*Fica criada a Autoridade Nacional de Proteção de Dados \(ANPD\)',
        )
        self.assertIn('DA AUTORIDADE NACIONAL DE PROTEÇÃO DE DADOS', self.corpo_h)
        self.assertIn('Da Autoridade Nacional de Proteção de Dados (ANPD)', self.corpo_h)
        self.assertRegex(
            self.corpo_h,
            r'VIII\s*[-–]\s*encarregado:.*?Autoridade Nacional de Proteção de Dados \(ANPD\)',
            re.S,
        )

    def test_consolidada_art5_VIII_55A_55C_titulos(self):
        snippets = extract_device_snippets(self.corpo_c)
        self.assertIn('Agência Nacional de Proteção de Dados (ANPD)', snippets['art5_VIII'])
        self.assertNotIn('Autoridade Nacional de Proteção de Dados (ANPD)', snippets['art5_VIII'])
        self.assertIn('entidade da administração pública', snippets['art5_XIX'])
        self.assertIn('autoridade nacional', snippets['art5_XIX'])
        self.assertIn('DA AGÊNCIA NACIONAL DE PROTEÇÃO DE DADOS', snippets['cap_ix_titulo'])
        self.assertIn('Da Agência Nacional de Proteção de Dados', snippets['secao_i_titulo'])
        self.assertIn(
            'vinculada ao Ministério da Justiça e Segurança Pública',
            snippets['art55A'],
        )
        self.assertIn('V-B', snippets['art55C'])
        self.assertIn('Auditoria', snippets['art55C'])
        self.assertTrue(snippets['nota_art5_VIII'])
        self.assertTrue(snippets['nota_art55A'])
        self.assertTrue(snippets['nota_art55C_VB'])
        self.assertTrue(snippets['nota_cap_ix'])
        self.assertTrue(snippets['nota_secao_i'])
        # Espelha prova versionada
        for key in ['art5_VIII', 'art55A', 'art55C', 'cap_ix_titulo', 'secao_i_titulo']:
            self.assertEqual(
                re.sub(r'\s+', ' ', ALVO['snippets'][key]),
                re.sub(r'\s+', ' ', snippets[key]),
            )

    def test_nao_renomeia_mecanicamente_autoridade(self):
        # XIX permanece "autoridade nacional" na consolidada
        self.assertRegex(
            self.corpo_c,
            r'XIX\s*[-–]\s*autoridade nacional:\s*entidade da administração pública',
        )
        # Modificadora ainda usa Autoridade em transição
        mod = MODIFICADORA.read_text(encoding='utf-8')
        self.assertIn('Autoridade Nacional de Proteção de Dados', mod)
        self.assertIn('Agência Nacional de Proteção de Dados (ANPD)', mod)

    def test_snapshots_e_reconversao_offline_byte_a_byte(self):
        for key, rec in FONTES.items():
            with self.subTest(key=key):
                snap = ROOT / rec['snapshot']
                self.assertTrue(snap.is_file(), snap)
                self.assertEqual(sha256(snap.read_bytes()), rec['sha256_snapshot_armazenado'])
                data = lzma.decompress(snap.read_bytes())
                self.assertEqual(sha256(data), rec['sha256'])

        cam = read_snapshot('camara-lgpd-atualizada')
        conv = convert_html(cam, 'utf-8', SOURCES['camara-lgpd-atualizada']['url'])
        blocks = trim_lgpd_blocks(conv.blocks)
        body = blocks_to_markdown(blocks, r'^LEI\s+N')
        if not body.endswith('\n'):
            body += '\n'
        self.assertTrue(coverage(blocks, body))
        # Comparação byte a byte do corpo normativo publicado com a reconversão offline
        self.assertEqual(self.corpo_c, body)
        self.assertEqual(sha256(self.corpo_c.encode('utf-8')), sha256(body.encode('utf-8')))

    def test_presenca_lei_15352_nao_basta_como_prova_de_atualizacao(self):
        """Negativo: só existir a modificadora no acervo não atualiza a histórica."""
        self.assertTrue(MODIFICADORA.is_file())
        self.assertIn('Agência Nacional de Proteção de Dados', MODIFICADORA.read_text(encoding='utf-8'))
        # A histórica continua desatualizada nos dispositivos-alvo
        self.assertNotIn(
            'vinculada ao Ministério da Justiça e Segurança Pública',
            self.corpo_h,
        )
        self.assertNotIn('V-B - Auditoria', self.corpo_h)
        self.assertNotIn('V-B – Auditoria', self.corpo_h)

    def test_lei_15352_reutilizada_sem_duplicar(self):
        man = json.loads(MANIFESTO.read_text(encoding='utf-8'))
        self.assertFalse(man['documentos']['br-federal-lei-2026-02-25-15352']['republicada_neste_catalogo'])
        self.assertEqual(
            VAL15352['sha256_markdown_publicado'],
            sha256(MODIFICADORA.read_text(encoding='utf-8').encode('utf-8')),
        )
        self.assertTrue(VAL15352['contem_art55A_agencia'])
        self.assertTrue(VAL15352['preserva_autoridade_em_transicao'])
        self.assertFalse(VAL15352['anexos_tabulares_no_markdown_publicado'])
        self.assertIn('provas/lgpd/fontes/', VAL15352['limite'])
        self.assertIn('não foi republicada', VAL15352['limite'].lower())

    def test_manifesto_relacoes_e_alertas(self):
        man = json.loads(MANIFESTO.read_text(encoding='utf-8'))
        self.assertEqual(man['vigencia_certificada'], False)
        alertas = man['documentos']['br-federal-lei-2018-08-14-13709']['alerta_por_dispositivo']
        self.assertIn('art. 55-A', alertas)
        self.assertIn('art. 5º, VIII', alertas)
        tipos = {r['tipo'] for r in man['relacoes']}
        self.assertIn('alteracao', tipos)
        destinos = {r['destino'] for r in man['relacoes']}
        self.assertIn('br-federal-lei-2018-08-14-13709', destinos)
        self.assertIn('anexos tabulares da Lei 15.352', ' '.join(man['desconhecidos']))

    def test_negativo_corrupcao_snapshot_quebra_verify_logica(self):
        """Corrromper bytes do snapshot Câmara torna a reconversão distinta do publicado."""
        key = 'camara-lgpd-atualizada'
        snap = ROOT / FONTES[key]['snapshot']
        original = snap.read_bytes()
        try:
            raw = lzma.decompress(original)
            corrupted = raw[:-50] + b'CORRUPTED_LGPD_TEST_BYTES_XXXX'
            snap.write_bytes(lzma.compress(corrupted))
            data = lzma.decompress(snap.read_bytes())
            self.assertNotEqual(sha256(data), FONTES[key]['sha256'])
            conv = convert_html(data, 'utf-8', SOURCES[key]['url'])
            blocks = trim_lgpd_blocks(conv.blocks)
            body = blocks_to_markdown(blocks, r'^LEI\s+N')
            self.assertNotEqual(body.strip(), self.corpo_c.strip())
        finally:
            snap.write_bytes(original)

    def test_negativo_historica_nao_equivale_trechos_consolidados(self):
        with self.assertRaises(ValueError):
            extract_device_snippets(self.corpo_h)


if __name__ == '__main__':
    unittest.main()
