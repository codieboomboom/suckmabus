"""
Tests for main.py.

Currently flat (one test file for the single source file). When main.py is
split during the M1/M2 refactor, split this into tests/unit/test_<module>.py
mirroring the new module layout.
"""

from main import parse_command


# ----- parse_command -----
# TODO: fill in test cases. Suggested coverage:
#   - valid command, no args:       "/reg"
#   - valid command with args:      "/reg 12345"
#   - valid command, extra spaces:  "/reg   12345  "
#   - empty string:                 ""           (currently crashes — C1)
#   - bare slash:                   "/"          (currently crashes — C1)
#   - non-command text:             "hello"
#   - non-command single char:      "h"
#
# Consider @pytest.mark.parametrize to collapse these into one test
# with a table of (input, expected_output) pairs.
class TestParseCommand:
    def test_parse_command_return_none_and_empty_arg_list_on_non_command_text(self):
        text = "hello"
        result = parse_command(text)
        assert result == (None, [])

    def test_parse_command_return_none_and_empty_arg_list_on_non_command_single_char(
        self,
    ):
        text = "h"
        result = parse_command(text)
        assert result == (None, [])

    def test_parse_command_return_command_and_no_arg_list_on_valid_command_no_args(
        self,
    ):
        text = "/start"
        result = parse_command(text)
        assert result == ("start", [])

    def test_parse_command_return_command_and_arg_list_on_valid_command(
        self,
    ):
        text = "/command arg1 arg2"
        result = parse_command(text)
        assert result == ("command", ["arg1", "arg2"])

    def test_parse_command_return_command_and_arg_list_on_valid_command_with_extra_spaces(
        self,
    ):
        text = "/command     arg1     arg2   "
        result = parse_command(text)
        assert result == ("command", ["arg1", "arg2"])

    def test_parse_command_with_empty_string_return_none_and_emptylist(self):
        text = ""
        result = parse_command(text)
        assert result == (None, [])

    def test_parse_command_with_only_single_slash_return_none_and_emptylist(self):
        text = "/"
        result = parse_command(text)
        assert result == (None, [])
