import unittest
from foundation_next.retrieval import reciprocal_rank_fusion


class RetrievalTests(unittest.TestCase):
    def test_two_rankings_combine_scores(self):
        results = reciprocal_rank_fusion([
            [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            [{"id": "b", "text": "B"}, {"id": "a", "text": "A"}],
        ])
        self.assertEqual(len(results), 2)
        self.assertEqual({item["document"]["id"] for item in results}, {"a", "b"})
        self.assertAlmostEqual(results[0]["score"], 1 / 61 + 1 / 62)

    def test_duplicate_in_one_source_not_counted_twice(self):
        results = reciprocal_rank_fusion([[{"id": "a"}, {"id": "a"}]])
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["score"], 1 / 61)

    def test_empty_sources(self):
        self.assertEqual(reciprocal_rank_fusion([]), [])

    def test_missing_identifier_rejected(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([[{"text": "no id"}]])

    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([], limit=0)


if __name__ == "__main__":
    unittest.main()
