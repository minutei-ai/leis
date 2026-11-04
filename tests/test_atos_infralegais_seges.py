"""INs SEGES/ME/MGI de contratação federal (issue #72)."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / 'metadados/atos-infralegais-seges.json').read_text(encoding='utf-8'))


class TestAtosInfralegaisSeges(unittest.TestCase):
    def test_especie_e_padrao_nome(self):
        self.assertEqual(MANIFEST['especie']['norma_tipo'], 'in')
        self.assertIn('<orgao>', MANIFEST['especie']['padrao_id'])
        for doc in MANIFEST['documentos']:
            self.assertEqual(doc['norma_tipo'], 'in')
            self.assertRegex(
                doc['id'],
                r'^br-federal-in-(seges-me|seges|seges-mgi)-\d{4}-\d{2}-\d{2}-\d+$',
            )
            self.assertTrue(doc['id'].startswith('br-federal-in-'))
            self.assertIn(doc['orgao_emissor'], doc['id'])

    def test_seis_publicados_com_lei_14133(self):
        self.assertEqual(len(MANIFEST['documentos']), 6)
        for doc in MANIFEST['documentos']:
            path = ROOT / doc['arquivo']
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding='utf-8')
            self.assertIn('norma_tipo: "in"', text)
            self.assertIn('lei_regulamentada', text)
            self.assertIn('br-federal-lei-2021-04-01-14133', text)
            self.assertIn('vigencia_certificada: false', text)
            self.assertGreater(len(text), 2000)
            self.assertRegex(text, r'(?m)^Art\.\s*1')

    def test_in5_pendente_sem_falso_negativo(self):
        pend = MANIFEST['pendencias_acesso']
        self.assertTrue(any(p['norma_numero'] == '5' for p in pend))
        for p in pend:
            self.assertNotEqual(p['estado_acesso'], 'inexistente')
            self.assertIn('não significa inexistência', p['leitura'].lower().replace('nao', 'não'))

    def test_verify_script(self):
        import subprocess, sys
        proc = subprocess.run(
            [sys.executable, str(ROOT / 'scripts/atos_infralegais_seges.py'), 'verify'],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={**dict(**{k: v for k, v in __import__('os').environ.items()}), 'PYTHONPATH': str(ROOT / 'scripts')},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

    def test_relacoes_regulamento(self):
        tipos = {r['tipo'] for r in MANIFEST['relacoes']}
        self.assertEqual(tipos, {'regulamento'})
        for r in MANIFEST['relacoes']:
            self.assertTrue(r['alvo']['norma_id'].startswith('br-federal-lei-'))
            self.assertTrue(r['desconhecidos'])


if __name__ == '__main__':
    unittest.main()
