from __future__ import annotations

import importlib.util
import json
import unittest
from itertools import islice
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / "src/preprocess/standardize/two_car_pros.py"
OUTPUT_PATH = Path(__file__).resolve().parent / "test-files-extracted.json"
SAMPLE_SIZE = 10

if not MODULE_PATH.exists():
	raise FileNotFoundError(f"Extractor module not found at {MODULE_PATH}")


spec = importlib.util.spec_from_file_location("two_car_pros_extractor", MODULE_PATH)
if spec is None or spec.loader is None:
	raise RuntimeError(f"Unable to load extractor module from {MODULE_PATH}")

extractor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor)


class TestTwoCarProsExtractor(unittest.TestCase):
	def test_extract_actual_dataset_sample(self) -> None:
		sample_paths = list(islice(extractor.iter_dataset_raw_paths(), SAMPLE_SIZE))

		self.assertGreater(len(sample_paths), 0)

		records = extractor.extract_pages(sample_paths)
		serialized = extractor.serialize_pages(records)
		OUTPUT_PATH.write_text(json.dumps(serialized, indent=2, ensure_ascii=False), encoding="utf-8")

		self.assertEqual(len(records), len(sample_paths))
		self.assertEqual(len(serialized), len(sample_paths))
		self.assertTrue(OUTPUT_PATH.exists())

		for source_path, record, payload in zip(sample_paths, records, serialized, strict=True):
			self.assertEqual(record.source_file, source_path.name)
			self.assertTrue(record.question.text)
			self.assertEqual(payload["source_file"], source_path.name)
			self.assertNotIn("taxonomy", payload)
			self.assertIn("question", payload)
			self.assertIn("answers", payload)
			self.assertNotIn("vehicle_specs", payload["question"])
			if payload["question"]["vehicle"] is not None:
				self.assertNotIn("engine_displacement_raw", payload["question"]["vehicle"])
			for answer in payload["answers"]:
				self.assertNotIn("vehicle", answer)
				self.assertNotIn("vehicle_specs", answer)


if __name__ == "__main__":
	unittest.main()
