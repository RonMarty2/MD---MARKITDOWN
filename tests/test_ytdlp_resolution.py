import sys
import unittest

import app


class YtDlpResolutionTest(unittest.TestCase):
    def test_ytdlp_command_uses_current_python_module(self):
        command = app.yt_dlp_command(["--version"])

        self.assertEqual(command[:3], [sys.executable, "-m", "yt_dlp"])
        self.assertEqual(command[3], "--version")


if __name__ == "__main__":
    unittest.main()
