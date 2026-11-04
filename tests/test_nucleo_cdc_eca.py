"""Testes do lote CDC/ECA: identidade, reconversão e travas de conferência."""
from __future__ import annotations

import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import nucleo_cdc_eca as lote  # noqa: E402


class IdentityCoverageTests(unittest.TestCase):
    def test_published_identities_are_present(self):
        errors = lote.identity_coverage_errors(ROOT)
        self.assertEqual(errors, [], msg='\n'.join(errors))

    def test_missing_cdc_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'federal').mkdir()
            # só o ECA
            src = ROOT / 'federal/br-federal-lei-1990-07-13-8069.md'
            if src.exists():
                (root / 'federal/br-federal-lei-1990-07-13-8069.md').write_text(
                    src.read_text(encoding='utf-8'), encoding='utf-8')
            errors = lote.identity_coverage_errors(root)
            self.assertTrue(any('8078' in e or 'ausente' in e for e in errors), errors)

    def test_wrong_norma_numero_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fed = root / 'federal'
            fed.mkdir()
            for doc in lote.DOCS:
                text = (ROOT / doc['arquivo']).read_text(encoding='utf-8')
                meta, body = lote.parse_frontmatter(text)
                meta['norma_numero'] = '99999'
                bad = lote.render_frontmatter(meta) + body
                (root / doc['arquivo']).write_text(bad, encoding='utf-8')
            errors = lote.identity_coverage_errors(root)
            self.assertTrue(any('norma_numero/data divergem' in e for e in errors), errors)

    def test_alias_alone_does_not_satisfy_canonical_id(self):
        """Arquivo com menção a CDC sob outro número não fecha a lacuna canônica."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fed = root / 'federal'
            fed.mkdir()
            decoy = fed / 'br-federal-lei-1990-01-01-1.md'
            decoy.write_text(
                '---\n'
                'id: "br-federal-lei-1990-01-01-1"\n'
                'norma_id: "br-federal-lei-1990-01-01-1"\n'
                'norma_tipo: "lei"\n'
                'norma_numero: "1"\n'
                'norma_data: "1990-01-01"\n'
                'titulo: "LEI Nº 1"\n'
                'esfera: "federal"\n'
                'edicao_id: "x"\n'
                'edicao_tipo: "consolidada"\n'
                'edicao_integral: true\n'
                'fonte_orgao: "x"\n'
                'fonte_url: "https://example.invalid"\n'
                'fonte_formato: "html"\n'
                'fonte_conferencia: ["https://example.invalid/c"]\n'
                'capturado_em: "2026-11-04T00:00:00Z"\n'
                'sha256_fonte: "' + ('a' * 64) + '"\n'
                'situacao: "nao-informada"\n'
                'situacao_fundamento: "desconhecido"\n'
                'vigencia_certificada: false\n'
                'texto_riscado: false\n'
                'anexos_no_corpo: 0\n'
                'tabelas: 0\n'
                'imagens_omitidas: 0\n'
                'efeitos_diferidos: "preservados-nas-notas-do-texto"\n'
                'sha256_markdown: "' + ('b' * 64) + '"\n'
                'manifesto: "metadados/nucleo-cdc-eca.json"\n'
                'contrato_versao: 1\n'
                'lote: "cdc-eca"\n'
                'area: "consumidor"\n'
                '---\n\n'
                '# LEI Nº 1\n\n'
                'Código de Defesa do Consumidor aparece só como menção.\n',
                encoding='utf-8',
            )
            errors = lote.identity_coverage_errors(root)
            self.assertTrue(any('ausente' in e and '8078' in e for e in errors), errors)
            self.assertTrue(any('ausente' in e and '8069' in e for e in errors), errors)


class VerifyOfflineTests(unittest.TestCase):
    def test_verify_clean(self):
        errors = lote.verify()
        self.assertEqual(errors, [], msg='\n'.join(errors))

    def test_runtime_versions_do_not_rewrite_generation_provenance(self):
        versions = dict(lote.nl.tool_versions(), python='3.12-ci', pdftotext='CI poppler')
        with patch.object(lote.nl, 'tool_versions', return_value=versions):
            self.assertEqual(lote.verify(), [])

    def test_new_substantial_divergence_fails(self):
        doc = lote.DOCS[0]
        original = list(doc['known_subst'])
        doc['known_subst'] = original + ['1']
        try:
            with self.assertRaises(SystemExit) as ctx:
                lote.verify()
            self.assertIn('divergencias_substanciais', str(ctx.exception))
        finally:
            doc['known_subst'] = original

    def test_manifest_lists_both_areas(self):
        manifest = json.loads((ROOT / 'metadados/nucleo-cdc-eca.json').read_text(encoding='utf-8'))
        areas = {d['area'] for d in manifest['documentos']}
        self.assertEqual(areas, {'consumidor', 'infancia-adolescencia'})
        ids = {d['id'] for d in manifest['documentos']}
        self.assertEqual(ids, {
            'br-federal-lei-1990-09-11-8078',
            'br-federal-lei-1990-07-13-8069',
        })
        self.assertFalse(manifest['vigencia_certificada'])


class StructureTests(unittest.TestCase):
    def test_markdown_preserves_struck_text_markers_when_source_has_them(self):
        eca = (ROOT / 'federal/br-federal-lei-1990-07-13-8069.md').read_text(encoding='utf-8')
        self.assertIn('~~', eca)
        meta, _body = lote.parse_frontmatter(eca)
        self.assertTrue(meta['texto_riscado'])

    def test_does_not_touch_licitacoes_manifest_keys(self):
        """Sanity: lote próprio não reescreve nucleo-licitacoes.json."""
        licit = json.loads((ROOT / 'metadados/nucleo-licitacoes.json').read_text(encoding='utf-8'))
        cdc = json.loads((ROOT / 'metadados/nucleo-cdc-eca.json').read_text(encoding='utf-8'))
        self.assertNotEqual(licit.get('lote'), 'cdc-eca')
        self.assertEqual(cdc.get('lote'), 'cdc-eca')
        for doc in licit.get('documentos', []):
            self.assertNotIn(doc.get('id'), {
                'br-federal-lei-1990-09-11-8078',
                'br-federal-lei-1990-07-13-8069',
            })


if __name__ == '__main__':
    unittest.main()
