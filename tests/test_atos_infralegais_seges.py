"""INs/Portarias SEGES/ME/MGI de contratação federal (issue #72)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / 'metadados/atos-infralegais-seges.json').read_text(encoding='utf-8'))


class TestAtosInfralegaisSeges(unittest.TestCase):
    def test_especie_e_padrao_nome(self):
        self.assertIn('in', MANIFEST['especie']['norma_tipos'])
        self.assertIn('portaria', MANIFEST['especie']['norma_tipos'])
        self.assertIn('<orgao>', MANIFEST['especie']['padrao_id_in'])
        self.assertIn('<orgao>', MANIFEST['especie']['padrao_id_portaria'])
        for doc in MANIFEST['documentos']:
            self.assertIn(doc['norma_tipo'], {'in', 'portaria'})
            if doc['norma_tipo'] == 'in':
                self.assertRegex(
                    doc['id'],
                    r'^br-federal-in-(seges-me|seges|seges-mgi|seges-mpdg)-\d{4}-\d{2}-\d{2}-\d+$',
                )
            else:
                self.assertRegex(
                    doc['id'],
                    r'^br-federal-portaria-(seges-me|seges|seges-mgi)-\d{4}-\d{2}-\d{2}-\d+$',
                )
            self.assertIn(doc['orgao_emissor'], doc['id'])

    def test_nove_publicados_com_lei_e_orgao(self):
        self.assertEqual(len(MANIFEST['documentos']), 9)
        ids = {d['id'] for d in MANIFEST['documentos']}
        self.assertIn('br-federal-in-seges-mpdg-2017-05-26-5', ids)
        self.assertIn('br-federal-portaria-seges-me-2021-07-19-8678', ids)
        self.assertIn('br-federal-in-seges-me-2022-12-26-98', ids)
        for doc in MANIFEST['documentos']:
            path = ROOT / doc['arquivo']
            self.assertTrue(path.is_file(), path)
            text = path.read_text(encoding='utf-8')
            self.assertIn(f'norma_tipo: "{doc["norma_tipo"]}"', text)
            self.assertIn('lei_regulamentada', text)
            self.assertIn('orgao_emissor', text)
            self.assertIn('vigencia_certificada: false', text)
            self.assertGreater(len(text), 1500)
            self.assertRegex(text, r'(?m)^Art\.\s*1')

    def test_prioritarios_14133_e_in5_historica(self):
        for doc in MANIFEST['documentos']:
            leis = doc['lei_regulamentada']
            if doc['id'] == 'br-federal-in-seges-mpdg-2017-05-26-5':
                self.assertIn('br-federal-lei-1993-06-21-8666', leis)
                self.assertIn('br-federal-lei-2002-07-17-10520', leis)
            else:
                self.assertIn('br-federal-lei-2021-04-01-14133', leis)

    def test_in5_publicada_sem_falso_negativo_catalogo(self):
        pend = MANIFEST['pendencias_acesso']
        self.assertFalse(any(p.get('norma_numero') == '5' for p in pend))
        cat = [p for p in pend if (p.get('tema') or '').startswith('portarias-atualizacao-catalogo')]
        self.assertTrue(cat)
        for p in pend:
            self.assertNotEqual(p.get('estado_acesso'), 'inexistente')
            leitura = (p.get('leitura') or '').lower().replace('nao', 'não')
            self.assertTrue(
                'não significa inexistência' in leitura or 'não localização' in leitura
            )

    def test_in5_tem_anexos_e_tabelas(self):
        path = ROOT / 'federal/br-federal-in-seges-mpdg-2017-05-26-5.md'
        text = path.read_text(encoding='utf-8')
        self.assertGreaterEqual(len(re.findall(r'(?im)^ANEXO\b', text)), 10)
        self.assertIn('tabelas: 73', text)
        self.assertIn('Art. 1', text)

    def test_portaria_pca_menciona_plano(self):
        path = ROOT / 'federal/br-federal-portaria-seges-me-2021-07-19-8678.md'
        text = path.read_text(encoding='utf-8')
        self.assertIn('Plano de Contratações Anual', text)
        self.assertIn('norma_tipo: "portaria"', text)

    def test_in98_autoriza_in5_na_14133(self):
        path = ROOT / 'federal/br-federal-in-seges-me-2022-12-26-98.md'
        text = path.read_text(encoding='utf-8')
        self.assertIn('Instrução Normativa nº 5', text)
        self.assertIn('14.133', text)

    def test_verify_script(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / 'scripts/atos_infralegais_seges.py'), 'verify'],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={
                **dict(**{k: v for k, v in __import__('os').environ.items()}),
                'PYTHONPATH': str(ROOT / 'scripts'),
            },
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
