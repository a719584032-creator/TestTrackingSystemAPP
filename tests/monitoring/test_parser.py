import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 通过注入模块桩来避免加载重量级依赖，便于单元测试运行。
if "utils" not in sys.modules:
    utils_pkg = ModuleType("utils")
    utils_pkg.__path__ = [str(PROJECT_ROOT / "utils")]
    sys.modules["utils"] = utils_pkg

exceptions_spec = importlib.util.spec_from_file_location(
    "utils.exceptions", PROJECT_ROOT / "utils" / "exceptions.py"
)
exceptions_module = importlib.util.module_from_spec(exceptions_spec)
sys.modules["utils.exceptions"] = exceptions_module
exceptions_spec.loader.exec_module(exceptions_module)

ValidationError = exceptions_module.ValidationError

if "monitoring" not in sys.modules:
    monitoring_pkg = ModuleType("monitoring")
    monitoring_pkg.__path__ = [str(PROJECT_ROOT / "monitoring")]
    sys.modules["monitoring"] = monitoring_pkg

spec = importlib.util.spec_from_file_location(
    "monitoring.parser", PROJECT_ROOT / "monitoring" / "parser.py"
)
parser = importlib.util.module_from_spec(spec)
sys.modules["monitoring.parser"] = parser
spec.loader.exec_module(parser)

MonitoringAction = parser.MonitoringAction
parse_keywords = parser.parse_keywords


class ParseKeywordsTests(unittest.TestCase):
    def test_simple_action_parses_amount(self):
        actions = parse_keywords(["S3+5"])

        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertEqual(action.name, "S3")
        self.assertEqual(action.amount, 5.0)
        self.assertTupleEqual(action.components, ("S3",))
        self.assertEqual(action.normalized_name, "s3")

    def test_composite_action_alias_is_normalized(self):
        actions = parse_keywords(["S3+USB+3"])

        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertIsInstance(action, MonitoringAction)
        self.assertEqual(action.name, "S3 插拔")
        self.assertEqual(action.components, ("S3 睡眠", "USB 插拔"))
        self.assertEqual(action.amount, 3.0)
        self.assertEqual(action.display_label(), "S3 插拔 (S3 睡眠 + USB 插拔)")

    def test_audio_action_uses_event_definition(self):
        actions = parse_keywords(["HEADSET_POWER_ON+5"])

        self.assertEqual(len(actions), 1)
        action = actions[0]
        self.assertEqual(action.name, "HEADSET_POWER_ON")
        self.assertEqual(action.amount, 5.0)
        self.assertEqual(action.normalized_name, "headset_power_on")
        label = action.display_label()
        self.assertIn("HEADSET_POWER_ON", label)
        self.assertIn("耳机拨动开机", label)

    def test_unsupported_action_raises_validation_error(self):
        with self.assertRaises(ValidationError) as exc_info:
            parse_keywords(["Unknown+2"])

        self.assertIn("不支持", str(exc_info.exception))


if __name__ == "__main__":  # pragma: no cover - 仅用于本地调试执行
    unittest.main()
