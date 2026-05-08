import unittest
from io import StringIO
from unittest.mock import patch

from lan_chat import terminal


class TerminalUiTests(unittest.TestCase):
    def tearDown(self):
        with patch("sys.stdout", StringIO()):
            terminal.restore_terminal_area()
        terminal.output_row = 1
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

        self.assertEqual("cyber", terminal.toggle_ui_style())
        self.assertEqual("plain", terminal.toggle_ui_style())

    def test_cyber_uses_plain_input_control_on_windows(self):
        terminal.set_ui_style("cyber")

        with patch.object(terminal.sys, "platform", "win32"):
            self.assertFalse(terminal.use_prompt_toolkit_input())

    def test_cyber_styles_contacts_usage_and_plain_status_lines(self):
        terminal.set_ui_style("cyber")

        self.assertIn("CONTACTS", terminal.format_line("在线联系人:"))
        self.assertIn("USER", terminal.format_line("  1. yu （我）  192.168.1.2"))
        self.assertIn("USAGE", terminal.format_line("用法: /p 名字或序号"))
        self.assertIn("WARN", terminal.format_line("找不到这个联系人。"))
        self.assertIn("LOG", terminal.format_line("普通状态文本"))

    def test_cyber_styles_help_output_as_badge_lines(self):
        terminal.set_ui_style("cyber")

        header = terminal.format_line("命令:")
        command = terminal.format_line("  /l                 查看在线联系人和群聊")

        self.assertIn("HELP", header)
        self.assertIn("CMD", command)
        self.assertIn("/l", command)
        self.assertNotIn("COMMAND DECK", header)

    def test_cyber_styles_chat_tx_and_rx_as_badge_lines(self):
        terminal.set_ui_style("cyber")

        tx = terminal.format_line("[12:00:00][我 -> 私聊:yu]: hello")
        rx = terminal.format_line("[12:00:00][私聊] yu: hello")

        self.assertIn("TX", tx)
        self.assertIn("RX", rx)
        self.assertNotIn("OUTBOUND", tx)
        self.assertNotIn("INBOUND", rx)

    def test_clear_screen_outputs_terminal_clear_sequence(self):
        output = StringIO()

        with patch("sys.stdout", output):
            terminal.clear_screen()

        self.assertEqual("\033[r\033[H\033[2J\033[3J\033[H", output.getvalue())

    def test_clear_screen_with_input_area_clears_scrollback_and_redraws_prompt(self):
        output = StringIO()

        with patch("lan_chat.terminal.terminal_size", return_value=(80, 24)):
            with patch("sys.stdout", output):
                terminal.enable_input_area()
                terminal.input_prompt = "> "
                terminal.input_buffer = ["x"]
                terminal.clear_screen()

        rendered = output.getvalue()
        self.assertIn("\033[r\033[H\033[2J\033[3J\033[H\033[1;23r\033[24;1H", rendered)
        self.assertTrue(rendered.endswith("> x"))

    def test_print_line_writes_output_top_down_and_keeps_input_on_bottom_line(self):
        output = StringIO()

        with patch("lan_chat.terminal.terminal_size", return_value=(80, 24)):
            with patch("sys.stdout", output):
                terminal.enable_input_area()
                terminal.input_prompt = "> "
                terminal.input_buffer = ["h", "i"]
                terminal.print_line("message")
                terminal.print_line("next")

        rendered = output.getvalue()
        self.assertIn("\033[1;23r", rendered)
        self.assertIn("\033[1;1H\033[2Kmessage", rendered)
        self.assertIn("\033[2;1H\033[2Knext", rendered)
        self.assertIn("\033[24;1H", rendered)
        self.assertTrue(rendered.endswith("> hi"))

    def test_print_line_supports_multiline_rich_blocks(self):
        output = StringIO()

        with patch("lan_chat.terminal.terminal_size", return_value=(80, 24)):
            with patch("sys.stdout", output):
                terminal.enable_input_area()
                terminal.input_prompt = "> "
                terminal.input_buffer = []
                terminal.print_output_line("one\ntwo\nthree")

        rendered = output.getvalue()
        self.assertIn("\033[1;1H\033[2Kone", rendered)
        self.assertIn("\033[2;1H\033[2Ktwo", rendered)
        self.assertIn("\033[3;1H\033[2Kthree", rendered)

    def test_move_to_bottom_prompt_line_restores_scroll_and_clears_last_line(self):
        output = StringIO()

        with patch("lan_chat.terminal.terminal_size", return_value=(80, 24)):
            with patch("sys.stdout", output):
                terminal.move_to_bottom_prompt_line()

        self.assertEqual("\033[r\033[24;1H\033[2K", output.getvalue())

    def test_reset_terminal_for_exit_restores_terminal_escape_state(self):
        output = StringIO()

        with patch("lan_chat.terminal.terminal_size", return_value=(80, 24)):
            with patch("lan_chat.terminal.restore_windows_console_input_mode") as restore_mode:
                with patch("sys.stdout", output):
                    terminal.reset_terminal_for_exit()

        self.assertEqual("\033[0m\033[?25h\033[?2004l\033[r\033[24;1H\033[2K", output.getvalue())
        restore_mode.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
