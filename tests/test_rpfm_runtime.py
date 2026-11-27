from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tk_pack_builder.rpfm_runtime import (
    ensure_rpfm_config_redirect,
    prepare_rpfm_config_redirect,
    rpfm_default_config_dir,
    rpfm_process_environment,
    runtime_rpfm_dir,
)
from tk_pack_builder.web_runtime import _rpfm_env


class RpfmRuntimeTest(unittest.TestCase):
    def test_rpfm_server_defaults_to_warning_logs(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TK_RPFM_LOG_LEVEL", None)
            env = _rpfm_env()

        self.assertEqual(env["RUST_LOG"], "warn")

    def test_app_root_keeps_runtime_inside_writable_work_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MTU Pack Editor"

            runtime = runtime_rpfm_dir(root)

        self.assertEqual(runtime, root / "work" / "rpfm-runtime")
        self.assertNotEqual(runtime, Path(root.anchor) / "MTU_RPFM_Runtime")

    def test_process_environment_redirects_config_inside_app_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MTU Pack Editor"

            env = rpfm_process_environment(
                root,
                {"APPDATA": "outside", "LOCALAPPDATA": "outside"},
            )

        expected = str(root / "work" / "rpfm-local-appdata")
        self.assertEqual(env["APPDATA"], expected)
        self.assertEqual(env["LOCALAPPDATA"], expected)

    def test_explicit_environment_does_not_touch_external_redirect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MTU Pack Editor"
            appdata = Path(tmp) / "Roaming"
            redirect = (
                appdata
                / "FrodoWazEre"
                / "rpfm"
                / "config"
                / "config_folder.txt"
            )
            redirect.parent.mkdir(parents=True)
            redirect.write_text("stale redirect", encoding="utf-8")

            target = ensure_rpfm_config_redirect(
                root,
                {"APPDATA": str(appdata)},
            )

            self.assertEqual(target, root / "work" / "rpfm-local-appdata")
            self.assertTrue(redirect.is_file())
            self.assertEqual(
                redirect.read_text(encoding="utf-8"),
                "stale redirect",
            )
            self.assertTrue(target.is_dir())

    def test_default_config_redirect_does_not_touch_user_roaming_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MTU Pack Editor"

            target = ensure_rpfm_config_redirect(root)
            redirect = (
                root
                / "work"
                / "rpfm-local-appdata"
                / "FrodoWazEre"
                / "rpfm"
                / "config"
                / "config_folder.txt"
            )

            self.assertEqual(target, root / "work" / "rpfm-local-appdata")
            self.assertFalse(redirect.exists())
            self.assertTrue(target.is_dir())

    def test_default_config_cleanup_removes_only_isolated_local_and_roaming_redirects(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MTU Pack Editor"
            isolated_root = root / "work" / "rpfm-local-appdata"
            stale_redirects = [
                isolated_root
                / scope
                / "FrodoWazEre"
                / "rpfm"
                / suffix
                / "config_folder.txt"
                for scope in ("Local", "Roaming")
                for suffix in (Path(), Path("config"))
            ]
            for redirect in stale_redirects:
                redirect.parent.mkdir(parents=True, exist_ok=True)
                redirect.write_text("stale redirect", encoding="utf-8")

            outside_redirect = (
                Path(tmp)
                / "real-user-roaming"
                / "FrodoWazEre"
                / "rpfm"
                / "config"
                / "config_folder.txt"
            )
            outside_redirect.parent.mkdir(parents=True)
            outside_redirect.write_text("keep me", encoding="utf-8")

            ensure_rpfm_config_redirect(root)

            self.assertTrue(all(not redirect.exists() for redirect in stale_redirects))
            self.assertTrue(outside_redirect.is_file())
            self.assertEqual(
                outside_redirect.read_text(encoding="utf-8"),
                "keep me",
            )

    def test_prepare_redirect_removes_only_executable_local_redirect(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MTU Pack Editor"
            executable_dir = root / "work" / "rpfm-runtime"
            executable_dir.mkdir(parents=True)
            appdata = Path(tmp) / "Roaming"
            env = {"APPDATA": str(appdata)}

            first_target = prepare_rpfm_config_redirect(
                root,
                executable_dir,
                env,
            )

            second_target = prepare_rpfm_config_redirect(
                root,
                executable_dir,
                env,
            )

            expected = root / "work" / "rpfm-local-appdata"
            self.assertEqual(first_target, expected)
            self.assertEqual(second_target, expected)
            self.assertTrue(expected.is_dir())
            self.assertFalse((executable_dir / "config_folder.txt").exists())

    def test_default_prepare_redirect_stays_inside_app_owned_work_folder(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "MTU Pack Editor"
            executable_dir = root / "work" / "rpfm-runtime"
            executable_dir.mkdir(parents=True)

            target = prepare_rpfm_config_redirect(root, executable_dir)
            self.assertEqual(
                target,
                root / "work" / "rpfm-local-appdata",
            )
            self.assertTrue(target.is_dir())
            self.assertFalse((executable_dir / "config_folder.txt").exists())

    def test_default_config_dir_uses_roaming_appdata_on_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            appdata = Path(tmp) / "Roaming"

            config_dir = rpfm_default_config_dir(
                {"APPDATA": str(appdata)}
            )

            if os.name == "nt":
                self.assertEqual(
                    config_dir,
                    appdata / "FrodoWazEre" / "rpfm",
                )


if __name__ == "__main__":
    unittest.main()
