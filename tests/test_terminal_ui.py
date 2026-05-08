import unittest
from io import StringIO
from unittest.mock import patch

from lan_chat import terminal


class TerminalUiTests(unittest.TestCase):
    def tearDown(self):
        terminal.set_ui_style("plain")

    def test_plain_style_keeps_text_unchanged(self):
        terminal.set_ui_style("plain")

        self.assertEqual("[系统] hello", terminal.format_line("[系统] hello"))
        self.assertEqual("[私聊:Bob] > ", terminal.format_prompt("[私聊:Bob] > "))

    def test_fancy_style_formats_known_lines_and_prompt(self):
        terminal.set_ui_style("fancy")

        self.assertIn("\033[", terminal.format_line("[系统] hello"))
        self.assertIn("\033[", terminal.format_prompt("[私聊:Bob] > "))

    def test_toggle_ui_style_switches_between_plain_and_fancy(self):
        terminal.set_ui_style("plain")

        self.assertEqual("fancy", terminal.toggle_ui_style())
        self.assertEqual("plain", terminal.toggle_ui_style())

    def test_clear_screen_outputs_terminal_clear_sequence(self):
        output = StringIO()

        with patch("sys.stdout", output):
            terminal.clear_screen()

        self.assertEqual("\033[2J\033[H", output.getvalue())


if __name__ == "__main__":
    unittest.main()
