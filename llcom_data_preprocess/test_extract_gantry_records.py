from __future__ import annotations

import tempfile
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch

from extract_gantry_records import extract_gantry_records


def _make_file(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


class ExtractGantryRecordsTests(unittest.TestCase):
    def test_copy_groups_files_and_renames_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / "input"
            output = root / "output"
            first_bj = source / "A1" / "Record" / "B1"
            second_bj = source / "A2" / "Record" / "B2"

            for suffix in (
                ".bin",
                ".bmp",
                ".inf",
                ".txt",
                "_1.JPG",
                "_2.jpg",
                "_3.jpg",
            ):
                _make_file(first_bj / f"vehicle{suffix}")
            _make_file(first_bj / "orphan.bin")
            _make_file(first_bj / "orphan.txt")
            _make_file(first_bj / "unknown.dat")
            _make_file(second_bj / "vehicle_1.jpg")
            _make_file(second_bj / "vehicle.bmp")
            (source / "A3").mkdir(parents=True)

            result = extract_gantry_records(source, output, show_progress=False)

            self.assertEqual(result.ai_folders, 3)
            self.assertEqual(result.record_folders, 2)
            self.assertEqual(result.bj_folders, 2)
            self.assertEqual(result.scanned_files, 12)
            self.assertEqual(result.data_groups, 3)
            self.assertEqual(result.groups_with_front, 2)
            self.assertEqual(result.groups_without_front, 1)
            self.assertEqual(result.groups_with_both_fronts, 1)
            self.assertEqual(result.groups_only_front_1, 1)
            self.assertEqual(result.groups_missing_bmp, 0)
            self.assertEqual(result.groups_missing_inf, 1)
            self.assertEqual(result.groups_missing_txt, 1)
            self.assertEqual(result.transferred_files, 7)
            self.assertEqual(result.renamed_groups, 1)
            self.assertEqual(result.failed_files, 0)
            self.assertEqual(len(result.missing_record_folders), 1)

            self.assertTrue((output / "front_view" / "vehicle_1.JPG").is_file())
            self.assertTrue((output / "front_view" / "vehicle_2.jpg").is_file())
            self.assertTrue((output / "front_view" / "vehicle__2_1.jpg").is_file())
            for suffix in (".bmp", ".inf", ".txt"):
                self.assertTrue((output / "label" / f"vehicle{suffix}").is_file())
            self.assertTrue((output / "label" / "vehicle__2.bmp").is_file())
            self.assertTrue((first_bj / "vehicle_1.JPG").is_file())
            self.assertIsNotNone(result.report_path)
            self.assertIn("门架数据提取统计报告", result.report_path.read_text("utf-8"))

            second_result = extract_gantry_records(source, output, show_progress=False)
            self.assertEqual(second_result.transferred_files, 0)
            self.assertEqual(second_result.resumed_files, 7)
            self.assertEqual(second_result.renamed_groups, 1)
            self.assertFalse((output / "front_view" / "vehicle__3_1.JPG").exists())
            self.assertFalse((output / "front_view" / "vehicle__4_1.jpg").exists())
            self.assertNotEqual(result.report_path, second_result.report_path)

            fresh_result = extract_gantry_records(
                source,
                output,
                resume=False,
                show_progress=False,
            )
            self.assertEqual(fresh_result.transferred_files, 7)
            self.assertEqual(fresh_result.renamed_groups, 2)
            self.assertTrue((output / "front_view" / "vehicle__3_1.JPG").is_file())
            self.assertTrue((output / "front_view" / "vehicle__4_1.jpg").is_file())

    def test_move_accepts_a_single_ai_and_leaves_unselected_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source_ai = root / "A1"
            bj = source_ai / "Record" / "B1"
            output = root / "output"
            for suffix in (".bin", ".bmp", ".inf", ".txt", "_2.jpg", "_3.jpg"):
                _make_file(bj / f"car{suffix}")

            result = extract_gantry_records(
                source_ai,
                output,
                move=True,
                show_progress=False,
            )

            self.assertEqual(result.operation, "移动")
            self.assertEqual(result.ai_folders, 1)
            self.assertEqual(result.transferred_files, 4)
            self.assertTrue((output / "front_view" / "car_2.jpg").is_file())
            for suffix in (".bmp", ".inf", ".txt"):
                self.assertTrue((output / "label" / f"car{suffix}").is_file())
                self.assertFalse((bj / f"car{suffix}").exists())
            self.assertFalse((bj / "car_2.jpg").exists())
            self.assertTrue((bj / "car.bin").is_file())
            self.assertTrue((bj / "car_3.jpg").is_file())

    def test_move_resumes_after_keyboard_interrupt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            source = root / "input"
            bj = source / "A1" / "Record" / "B1"
            output = root / "output"
            for suffix in (".bmp", ".inf", ".txt", "_1.jpg"):
                _make_file(bj / f"resume_car{suffix}")

            real_move = shutil.move
            move_calls = 0

            def interrupt_during_second_move(source_path: str, target_path: str):
                nonlocal move_calls
                move_calls += 1
                if move_calls == 2:
                    raise KeyboardInterrupt
                return real_move(source_path, target_path)

            with patch(
                "extract_gantry_records.shutil.move",
                side_effect=interrupt_during_second_move,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    extract_gantry_records(
                        source,
                        output,
                        move=True,
                        show_progress=False,
                    )

            self.assertTrue((output / "label" / "resume_car.bmp").is_file())
            self.assertFalse((bj / "resume_car.bmp").exists())
            self.assertTrue((bj / "resume_car.inf").is_file())
            self.assertTrue((bj / "resume_car_1.jpg").is_file())

            resumed = extract_gantry_records(
                source,
                output,
                move=True,
                show_progress=False,
            )

            self.assertEqual(resumed.transferred_files, 3)
            self.assertEqual(resumed.renamed_groups, 0)
            self.assertEqual(resumed.groups_with_all_labels, 1)
            for suffix in (".bmp", ".inf", ".txt"):
                self.assertTrue((output / "label" / f"resume_car{suffix}").is_file())
            self.assertTrue(
                (output / "front_view" / "resume_car_1.jpg").is_file()
            )
            self.assertFalse((output / "front_view" / "resume_car__2_1.jpg").exists())


if __name__ == "__main__":
    unittest.main()
