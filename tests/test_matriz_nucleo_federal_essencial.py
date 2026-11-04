"""Matriz unificada do núcleo federal essencial (issue #62)."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIZ = ROOT / 'metadados/matriz-nucleo-federal-essencial.json'
README = ROOT / 'provas/nucleo-federal-essencial/README.md'
CONTRATO = ROOT / 'metadados/CONTRATO-matriz-nucleo-federal-essencial.md'
PENDENCIAS = ROOT / 'PENDENCIAS.md'

EXPECTED = {
    'br-federal-lei-1990-09-11-8078': 'consumidor',
    'br-federal-lei-1990-07-13-8069': 'infancia-adolescencia',
    'br-federal-lei-1966-10-25-5172': 'tributario',
    'br-federal-lei-1990-09-19-8080': 'saude',
    'br-federal-lei-1991-07-24-8213': 'previdenciario',
    'br-federal-lei-2006-08-07-11340': 'violencia-domestica',
}


def _frontmatter_sha(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        raise AssertionError(f'{path}: sem frontmatter')
    end = text.index('\n---\n', 4)
    for line in text[4:end].splitlines():
        if line.startswith('sha256_markdown:'):
            raw = line.split(':', 1)[1].strip()
            return json.loads(raw) if raw.startswith('"') else raw.strip('"')
    raise AssertionError(f'{path}: sha256_markdown ausente')


class TestMatrizNucleoFederalEssencial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matriz = json.loads(MATRIZ.read_text(encoding='utf-8'))

    def test_artefatos_presentes(self):
        self.assertTrue(MATRIZ.is_file())
        self.assertTrue(README.is_file())
        self.assertTrue(CONTRATO.is_file())

    def test_seis_identidades_por_area(self):
        docs = {d['norma_id']: d for d in self.matriz['documentos']}
        self.assertEqual(set(docs), set(EXPECTED))
        for norma_id, area in EXPECTED.items():
            self.assertEqual(docs[norma_id]['area'], area)
            self.assertEqual(docs[norma_id]['estado_recuperacao'], 'publicado')
            self.assertIs(docs[norma_id]['vigencia_certificada'], False)

    def test_backlog_espelha_documentos(self):
        backlog_ids = {b['norma_id'] for b in self.matriz['backlog']}
        self.assertEqual(backlog_ids, set(EXPECTED))
        for item in self.matriz['backlog']:
            self.assertEqual(item['estado_recuperacao'], 'publicado')
            self.assertTrue(item['fonte_oficial_indicada_na_issue'].startswith('https://'))
            self.assertEqual(item['causa_lacuna_original'], 'identificada-nao-coletada')

    def test_arquivos_e_hashes(self):
        for doc in self.matriz['documentos']:
            path = ROOT / doc['arquivo']
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.name, f"{doc['norma_id']}.md")
            stored = _frontmatter_sha(path)
            self.assertEqual(doc['sha256_markdown'], stored, doc['norma_id'])
            text = path.read_text(encoding='utf-8')
            self.assertGreater(len(text), 1000)

    def test_gate_nao_e_so_numero(self):
        """Número sozinho colide com decretos/decreto-leis; o gate usa norma_id."""
        federal = ROOT / 'federal'
        for doc in self.matriz['documentos']:
            number = doc['norma_numero']
            lei_hits = [
                p.name for p in federal.glob(f'br-federal-lei-*-{number}.md')
            ]
            self.assertIn(f"{doc['norma_id']}.md", lei_hits)
            # Pode haver outras espécies com o mesmo número; isso não as confunde.
            other = [
                p.name for p in federal.iterdir()
                if p.suffix == '.md'
                and re.search(rf'-{re.escape(number)}(?:-|\.md)', p.name)
                and not p.name.startswith('br-federal-lei-')
            ]
            # Só documenta o risco; não falha se a árvore local for parcial.
            self.assertTrue(doc['controle']['contagem_arquivos_insuficiente'])
            self.assertEqual(doc['controle']['gate'], 'identidade-area-numero-data')
            _ = other  # presença de colisões de número é esperada no acervo completo

    def test_separacao_pendencias(self):
        pend = PENDENCIAS.read_text(encoding='utf-8')
        for norma_id in EXPECTED:
            self.assertNotIn(norma_id, pend)
        for doc in self.matriz['documentos']:
            self.assertIn('fora-de-PENDENCIAS.md', doc['separacao_pendencias_pecas'])

    def test_diagnostico_e_lotes(self):
        diag = self.matriz['diagnostico_unificado']
        self.assertEqual(diag['padrao'], 'identificada-nao-coletada')
        self.assertEqual(len(diag['provas_por_lote']), 3)
        for rel in diag['provas_por_lote']:
            self.assertTrue((ROOT / rel).is_file(), rel)
        lote_ids = {lote['id'] for lote in self.matriz['lotes']}
        self.assertEqual(
            lote_ids,
            {'cdc-eca', 'nucleo-federal-ctn-sus', 'nucleo-federal-beneficios-mdp'},
        )
        self.assertEqual(self.matriz['escopo']['estado'], 'parcial')
        self.assertIn('atos infralegais', ' '.join(self.matriz['escopo']['nao_cataloga']))

    def test_issue_ref(self):
        self.assertIn(
            'https://github.com/minutei-ai/leis/issues/62',
            self.matriz['issue_refs'],
        )


if __name__ == '__main__':
    unittest.main()
