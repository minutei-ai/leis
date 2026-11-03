"""Cobertura dos anexos dos decretos de atualização dos valores da Lei 14.133.

Lê somente o repositório; não acessa a rede.
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVAS = ROOT / 'provas/decretos-atualizacao-14133'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
COBERTURA = json.loads((PROVAS / 'cobertura-anexos.json').read_text(encoding='utf-8'))

DOCS = [
    'br-federal-decreto-2021-12-30-10922',
    'br-federal-decreto-2022-12-29-11317',
    'br-federal-decreto-2023-12-29-11871',
    'br-federal-decreto-2024-12-30-12343',
    'br-federal-decreto-2025-12-29-12807',
]

# Sequência literal de revogações entre os próprios atos (artigo de revogação).
REVOGACOES = [
    ('br-federal-decreto-2022-12-29-11317', r'Decreto nº 10\.922'),
    ('br-federal-decreto-2023-12-29-11871', r'Decreto nº 11\.317'),
    ('br-federal-decreto-2024-12-30-12343', r'Decreto nº 11\.871'),
    ('br-federal-decreto-2025-12-29-12807', r'Decreto nº 12\.343'),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_annex_table(text: str) -> list[list[str]]:
    """Extrai a tabela Markdown imediatamente após o cabeçalho ANEXO."""
    m = re.search(r'(?m)^ANEXO\b.*?(?=\n\|)', text, flags=re.S)
    if not m:
        raise AssertionError('bloco ANEXO sem tabela')
    start = m.end()
    rows = []
    for line in text[start:].splitlines():
        if not line.startswith('|'):
            if rows:
                break
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if all(re.fullmatch(r':?-{3,}:?', c) for c in cells):
            continue
        rows.append(cells)
    return rows


class TestDecretosAtualizacao14133(unittest.TestCase):
    def test_catalogo_completo(self):
        self.assertEqual(sorted(FONTES), sorted(DOCS))
        self.assertEqual(sorted(COBERTURA), sorted(DOCS))

    def test_cada_ato_tem_anexo_e_todas_as_linhas(self):
        for doc_id in DOCS:
            with self.subTest(doc_id=doc_id):
                cob = COBERTURA[doc_id]
                path = ROOT / cob['arquivo']
                text = path.read_text(encoding='utf-8')
                self.assertRegex(text, r'(?m)^ANEXO\b')
                self.assertIn('nota-edicao:inicio', text)
                self.assertIn(FONTES[doc_id]['url'], text)
                self.assertIn(FONTES[doc_id]['sha256'], text)
                self.assertNotIn('reproducao-incompleta:inicio', text)
                rows = parse_annex_table(text)
                self.assertGreaterEqual(len(rows), 2, doc_id)
                self.assertEqual(rows[0], cob['cabecalho'])
                data = rows[1:]
                self.assertEqual(len(data), cob['linhas_tabela'], doc_id)
                self.assertEqual(len(data), len(cob['linhas']))
                for got, expected in zip(data, cob['linhas']):
                    self.assertEqual(got[0], expected['dispositivo'], doc_id)
                    self.assertEqual(got[1], expected['valor'], doc_id)
                for valor in cob['valores_r']:
                    self.assertIn(valor, text)
                # Cobertura integral: nenhum valor da prova fica de fora; nenhum extra na tabela.
                got_valores = [re.search(r'R\$\s*[\d.]+,\d{2}', r[1]).group(0) for r in data]
                self.assertEqual(got_valores, cob['valores_r'])

    def test_snapshots_inteiros_e_hashes(self):
        for doc_id in DOCS:
            with self.subTest(doc_id=doc_id):
                meta = FONTES[doc_id]
                snap = ROOT / meta['snapshot']
                self.assertTrue(snap.is_file(), snap)
                xz = snap.read_bytes()
                self.assertEqual(sha256(xz), meta['sha256_snapshot_armazenado'])
                raw = lzma.decompress(xz)
                self.assertEqual(len(raw), meta['bytes'])
                self.assertEqual(sha256(raw), meta['sha256'])

    def test_detecta_omissao_de_anexo(self):
        """Trava: se o ANEXO sumir de algum destes atos, o teste falha."""
        for doc_id in DOCS:
            text = (ROOT / COBERTURA[doc_id]['arquivo']).read_text(encoding='utf-8')
            self.assertIsNotNone(re.search(r'(?m)^ANEXO\b', text), doc_id)
            self.assertGreaterEqual(COBERTURA[doc_id]['linhas_tabela'], 8, doc_id)

    def test_sequencia_de_revogacoes_e_delegacao_12807(self):
        for doc_id, padrao in REVOGACOES:
            text = (ROOT / COBERTURA[doc_id]['arquivo']).read_text(encoding='utf-8')
            self.assertRegex(text, padrao)
        d12807 = (ROOT / COBERTURA['br-federal-decreto-2025-12-29-12807']['arquivo']).read_text(
            encoding='utf-8')
        self.assertIn(
            'Fica delegada à autoridade máxima do Ministério da Gestão e da Inovação em Serviços Públicos',
            d12807,
        )
        self.assertIn('nos exercícios subsequentes', d12807)
        # Não inventar atualização posterior: o anexo do 12.807 é a última tabela publicada nestes atos.
        self.assertIn('R$ 261.968.421,04', d12807)
        self.assertIn('Art. 184-A', d12807)
        # 184-A só a partir de 12.343/2024
        t10922 = (ROOT / COBERTURA['br-federal-decreto-2021-12-30-10922']['arquivo']).read_text(
            encoding='utf-8')
        annex_10922 = t10922[t10922.index('\nANEXO'):]
        self.assertNotIn('184-A', annex_10922)
        t12343 = (ROOT / COBERTURA['br-federal-decreto-2024-12-30-12343']['arquivo']).read_text(
            encoding='utf-8')
        self.assertIn('Art. 184-A', t12343)

    def test_preserva_typo_literal_do_planalto_no_11317(self):
        """A fonte do Decreto 11.317 traz 'reis' no art. 75, § 7º; não corrigir."""
        text = (ROOT / COBERTURA['br-federal-decreto-2022-12-29-11317']['arquivo']).read_text(
            encoding='utf-8')
        self.assertIn('nove mil cento e cinquenta e três reis e trinta e quatro centavos', text)

    def test_nao_certifica_vigencia_nem_infere_por_ano(self):
        for doc_id in DOCS:
            text = (ROOT / COBERTURA[doc_id]['arquivo']).read_text(encoding='utf-8')
            self.assertIn('não indica vigência', text.lower())
            self.assertIn('Não se deve deduzir o valor aplicável a uma data apenas pelo ano do decreto', text)


if __name__ == '__main__':
    unittest.main()
