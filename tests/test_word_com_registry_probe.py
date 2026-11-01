from __future__ import annotations

import unittest
from unittest.mock import patch


class WordComRegistryProbeTests(unittest.TestCase):
    def test_probe_marks_fallback_possible_when_default_com_points_to_missing_wps(self) -> None:
        from core.word_engine_impl import registry_probe

        servers = {
            "Word.Application": r'"C:\Program Files (x86)\Kingsoft\WPS Office\office6\wps.exe" /Automation',
            "Word.Application.14": r'"E:\Office14\WINWORD.EXE" /Automation',
        }

        def fake_localserver32(progid: str) -> str:
            return servers.get(progid, "")

        def fake_exists(path: str) -> bool:
            low = str(path).lower()
            if low.endswith("wps.exe"):
                return False
            if low.endswith("winword.exe"):
                return True
            return False

        with (
            patch.object(registry_probe, "progid_localserver32", side_effect=fake_localserver32),
            patch.object(registry_probe, "discover_ms_word_versions_from_registry", return_value=[14]),
            patch.object(registry_probe.os.path, "exists", side_effect=fake_exists),
        ):
            probed = registry_probe.probe_word_com_registration()

        self.assertTrue(probed["default_com_is_wps"])
        self.assertFalse(probed["default_com_path_exists"])
        self.assertTrue(probed["fallback_possible"])
        self.assertTrue(probed["word_ok"])
        self.assertEqual(14.0, probed["word_version"])
        self.assertEqual(r"E:\Office14\WINWORD.EXE", probed["word_candidates"][0]["exe_path"])

    def test_probe_blocks_when_default_com_points_to_wps_and_no_word_candidate_exists(self) -> None:
        from core.word_engine_impl import registry_probe

        def fake_exists(path: str) -> bool:
            return str(path).lower().endswith("wps.exe")

        with (
            patch.object(
                registry_probe,
                "progid_localserver32",
                return_value=r'"C:\Program Files (x86)\Kingsoft\WPS Office\office6\wps.exe" /Automation',
            ),
            patch.object(registry_probe, "discover_ms_word_versions_from_registry", return_value=[]),
            patch.object(registry_probe.os.path, "exists", side_effect=fake_exists),
        ):
            probed = registry_probe.probe_word_com_registration()

        self.assertTrue(probed["default_com_is_wps"])
        self.assertFalse(probed["fallback_possible"])
        self.assertFalse(probed["word_ok"])
        self.assertEqual("no_word_candidates", probed["block_reason"])


if __name__ == "__main__":
    unittest.main()
