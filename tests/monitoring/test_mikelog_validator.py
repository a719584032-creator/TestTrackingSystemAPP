import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitoring.actions.mikelog_validator import read_resume_counter_after_end_test


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class MikeLogValidatorTests(unittest.TestCase):
    def test_reads_resume_counter_from_sample_log(self):
        sample_log = PROJECT_ROOT / "Mike_Restart_20251113-1759.log"

        count = read_resume_counter_after_end_test(sample_log)

        self.assertEqual(count, 89)

    def test_uses_last_end_test_block(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "multi_end.log"
            path.write_text(
                textwrap.dedent(
                    """
                    2024/01/01 00:00:00 :  EVENT  : End test
                    2024/01/01 00:00:00 :  EVENT  : Resume counter (Total)  = 5
                    2024/01/01 00:00:01 :  EVENT  : End test
                    2024/01/01 00:00:01 :  EVENT  : Resume counter (Total)  = 9
                    """
                ).strip(),
                encoding="utf-8",
            )

            count = read_resume_counter_after_end_test(path)

            self.assertEqual(count, 9)

    def test_raises_when_marker_missing(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "no_marker.log"
            path.write_text("Resume counter (Total)  = 5\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                read_resume_counter_after_end_test(path)

    def test_raises_when_counter_missing(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "no_counter.log"
            path.write_text("2024/01/01 00:00:00 :  EVENT  : End test\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                read_resume_counter_after_end_test(path)


if __name__ == "__main__":  # pragma: no cover - 仅用于本地调试执行
    unittest.main()
