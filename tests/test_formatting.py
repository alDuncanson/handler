"""Tests for the formatting utilities module."""

from a2a_handler.common.formatting import format_field_name, format_value


class TestFormatFieldName:
    """Tests for format_field_name function."""

    def test_snake_case(self):
        """Test conversion of snake_case to Title Case."""
        assert format_field_name("snake_case") == "Snake Case"
        assert format_field_name("some_field_name") == "Some Field Name"

    def test_camel_case(self):
        """Test conversion of camelCase to Title Case."""
        assert format_field_name("camelCase") == "Camel Case"
        assert format_field_name("someFieldName") == "Some Field Name"

    def test_already_spaced(self):
        """Test handling of already spaced strings."""
        assert format_field_name("already spaced") == "Already Spaced"

    def test_single_word(self):
        """Test single word remains capitalized."""
        assert format_field_name("name") == "Name"
        assert format_field_name("id") == "Id"

    def test_mixed_case_with_underscores(self):
        """Test mixed camelCase with underscores."""
        assert format_field_name("some_camelCase_field") == "Some Camel Case Field"


class TestFormatValue:
    """Tests for format_value function."""

    def test_none_returns_empty(self):
        """Test None returns empty string."""
        assert format_value(None) == ""

    def test_empty_string_returns_empty(self):
        """Test empty string returns empty string."""
        assert format_value("") == ""

    def test_empty_list_returns_empty(self):
        """Test empty list returns empty string."""
        assert format_value([]) == ""

    def test_empty_dict_returns_empty(self):
        """Test empty dict returns empty string."""
        assert format_value({}) == ""

    def test_bool_true(self):
        """Test True returns 'yes'."""
        assert format_value(True) == "yes"

    def test_bool_false(self):
        """Test False returns 'no'."""
        assert format_value(False) == "no"

    def test_string(self):
        """Test string returns itself."""
        assert format_value("hello") == "hello"
        assert format_value("hello world") == "hello world"

    def test_integer(self):
        """Test integer returns string representation."""
        assert format_value(42) == "42"
        assert format_value(0) == "0"

    def test_float(self):
        """Test float returns string representation."""
        assert format_value(3.14) == "3.14"

    def test_simple_dict(self):
        """Test simple dict formatting."""
        result = format_value({"name": "test"})
        assert "Name:" in result
        assert "test" in result

    def test_dict_skips_private_keys(self):
        """Test dict skips keys starting with underscore."""
        result = format_value({"name": "test", "_private": "hidden"})
        assert "Name:" in result
        assert "_private" not in result
        assert "hidden" not in result

    def test_list_of_strings(self):
        """Test list of strings formatting."""
        result = format_value(["a", "b", "c"])
        assert "• a" in result
        assert "• b" in result
        assert "• c" in result

    def test_list_of_dicts_with_name(self):
        """Test list of dicts uses name field."""
        result = format_value([{"name": "Item1"}, {"name": "Item2"}])
        assert "Item1" in result
        assert "Item2" in result

    def test_list_of_dicts_with_description(self):
        """Test list of dicts includes description."""
        result = format_value([{"name": "Item1", "description": "Description1"}])
        assert "Item1" in result
        assert "Description1" in result

    def test_nested_dict(self):
        """Test nested dict formatting."""
        result = format_value({"outer": {"inner": "value"}})
        assert "Outer:" in result
        assert "Inner:" in result
        assert "value" in result

    def test_indentation(self):
        """Test indentation is applied."""
        result = format_value({"name": "test"}, indent=1)
        assert result.startswith("  ")
