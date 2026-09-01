import unittest

from ingest import Material, split_material


class TestRAGMaterialChunking(unittest.TestCase):
    def test_chunk_includes_full_legal_answer(self):
        material = Material(
            id="demo-011",
            title="仲裁条款",
            article="仲裁条款应明确仲裁机构或可确定的仲裁机构。",
            scenario="审查合同争议解决条款",
            category="合同审查",
            source="materials.demo.json",
            keywords=["仲裁", "争议解决", "送达"],
            risk_level="中风险",
            typical_question="合同没有仲裁条款怎么办？",
            answer="卖方有权要求仲裁并保留证据。",
            legal_basis="CISG Art. 61",
            review_points="确认仲裁机构和送达方式。",
            risk_warning="未约定仲裁可能延误救济。",
        )

        chunks = split_material(material, chunk_size=500, overlap=50)

        self.assertTrue(chunks)
        self.assertIn("卖方有权要求仲裁并保留证据。", chunks[0]["text"])
        self.assertIn("CISG Art. 61", chunks[0]["text"])
        self.assertIn("确认仲裁机构和送达方式。", chunks[0]["text"])


if __name__ == "__main__":
    unittest.main()
