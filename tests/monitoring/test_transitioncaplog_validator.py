import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from monitoring.actions.transitioncaplog_validator import read_loop_count_after_end


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TransitionCapLogValidatorTests(unittest.TestCase):
    def test_reads_loop_count_from_sample_log(self):
        sample_log = PROJECT_ROOT / "12.08.2025_17.02.55_Result.log"

        count = read_loop_count_after_end(sample_log)

        self.assertEqual(count, 400)

    def test_raises_when_end_missing(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "no_end.log"
            path.write_text("12092025-000040 # result = OK\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                read_loop_count_after_end(path)

    def test_raises_when_result_not_ok(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "result_not_ok.log"
            path.write_text(
                textwrap.dedent(
                    """
                    12092025-000040 # end
                    12092025-000040 # result = NG
                    12092025-000040 # loop count = 10
                    """
                ).strip(),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                read_loop_count_after_end(path)

    def test_raises_when_loop_count_missing(self):
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "no_loop_count.log"
            path.write_text(
                textwrap.dedent(
                    """
                    12092025-000040 # end
                    12092025-000040 # result = OK
                    """
                ).strip(),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                read_loop_count_after_end(path)


if __name__ == "__main__":  # pragma: no cover - 仅用于本地调试执行
    unittest.main()
