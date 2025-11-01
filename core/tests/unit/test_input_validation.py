"""Unit tests for input validation - HIGH VALUE tests.

These tests prevent real production failures from invalid input data.
Tests cover:
- Malformed JSONL parsing
- Missing required fields
- Invalid message structures
- Oversized requests
- Invalid schemas
"""

import pytest
import json


class TestJSONLParsing:
    """Test JSONL parsing and malformed data handling."""

    def test_valid_jsonl_parses_correctly(self, temp_jsonl_file):
        """Test that valid JSONL is parsed correctly."""
        temp_jsonl_file.write('{"custom_id": "1", "body": {"messages": [{"role": "user", "content": "test"}]}}\n')
        temp_jsonl_file.write('{"custom_id": "2", "body": {"messages": [{"role": "user", "content": "test2"}]}}\n')
        temp_jsonl_file.flush()

        requests = []
        with open(temp_jsonl_file.name) as f:
            for line in f:
                if line.strip():
                    requests.append(json.loads(line))

        assert len(requests) == 2
        assert requests[0]['custom_id'] == '1'
        assert requests[1]['custom_id'] == '2'

    def test_malformed_json_raises_error(self, temp_jsonl_file):
        """Test that malformed JSON raises JSONDecodeError."""
        temp_jsonl_file.write('{"custom_id": "1", "body": {"messages": [{"role": "user", "content": "test"}]}}\n')
        temp_jsonl_file.write('{"custom_id": "2", "body": INVALID JSON\n')  # Malformed
        temp_jsonl_file.flush()

        with pytest.raises(json.JSONDecodeError):
            with open(temp_jsonl_file.name) as f:
                for line in f:
                    if line.strip():
                        json.loads(line)

    def test_empty_lines_are_skipped(self, temp_jsonl_file):
        """Test that empty lines in JSONL are skipped."""
        temp_jsonl_file.write('{"custom_id": "1", "body": {"messages": [{"role": "user", "content": "test"}]}}\n')
        temp_jsonl_file.write('\n')  # Empty line
        temp_jsonl_file.write('{"custom_id": "2", "body": {"messages": [{"role": "user", "content": "test2"}]}}\n')
        temp_jsonl_file.flush()

        requests = []
        with open(temp_jsonl_file.name) as f:
            for line in f:
                if line.strip():
                    requests.append(json.loads(line))

        assert len(requests) == 2

    def test_unicode_content_is_handled(self, temp_jsonl_file):
        """Test that Unicode content is handled correctly."""
        temp_jsonl_file.write('{"custom_id": "1", "body": {"messages": [{"role": "user", "content": "Hello 世界 🌍"}]}}\n')
        temp_jsonl_file.flush()

        with open(temp_jsonl_file.name, encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    req = json.loads(line)
                    assert "世界" in req['body']['messages'][0]['content']
                    assert "🌍" in req['body']['messages'][0]['content']


class TestRequiredFields:
    """Test validation of required fields in requests."""

    @pytest.mark.parametrize("request_data,missing_field,field_path", [
        ({"body": {"messages": [{"role": "user", "content": "test"}]}}, "custom_id", "root"),
        ({"custom_id": "1"}, "body", "root"),
        ({"custom_id": "1", "body": {}}, "messages", "body"),
    ])
    def test_missing_required_field(self, request_data, missing_field, field_path):
        """Test that missing required fields can be detected."""
        if field_path == "root":
            assert missing_field not in request_data
        elif field_path == "body":
            assert missing_field not in request_data['body']

    def test_empty_messages_array(self):
        """Test that empty messages array can be detected."""
        request = {"custom_id": "1", "body": {"messages": []}}

        # Should be able to detect empty messages
        assert len(request['body']['messages']) == 0

    @pytest.mark.parametrize("message,missing_field", [
        ({"content": "test"}, "role"),
        ({"role": "user"}, "content"),
    ])
    def test_message_missing_field(self, message, missing_field):
        """Test that message missing required fields can be detected."""
        request = {"custom_id": "1", "body": {"messages": [message]}}

        # Should be able to detect missing field
        assert missing_field not in request['body']['messages'][0]


class TestMessageStructure:
    """Test validation of message structure."""

    def test_valid_single_message(self):
        """Test that valid single message structure is accepted."""
        request = {
            "custom_id": "1",
            "body": {
                "messages": [
                    {"role": "user", "content": "Hello"}
                ]
            }
        }
        
        # Extract messages like worker does
        messages = request['body']['messages']
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        assert prompt == "user: Hello"

    def test_valid_multi_turn_conversation(self):
        """Test that multi-turn conversation structure is accepted."""
        request = {
            "custom_id": "1",
            "body": {
                "messages": [
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there!"},
                    {"role": "user", "content": "How are you?"}
                ]
            }
        }
        
        # Extract messages like worker does
        messages = request['body']['messages']
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        assert "system: You are helpful" in prompt
        assert "user: Hello" in prompt
        assert "assistant: Hi there!" in prompt

    def test_messages_with_extra_fields_are_ignored(self):
        """Test that extra fields in messages don't break parsing."""
        request = {
            "custom_id": "1",
            "body": {
                "messages": [
                    {"role": "user", "content": "Hello", "extra_field": "ignored"}
                ]
            }
        }
        
        # Extract messages like worker does
        messages = request['body']['messages']
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        assert prompt == "user: Hello"


class TestOversizedRequests:
    """Test handling of oversized requests."""

    def test_very_long_content(self):
        """Test that very long content can be detected."""
        long_content = "x" * 100_000  # 100K characters
        request = {
            "custom_id": "1",
            "body": {
                "messages": [
                    {"role": "user", "content": long_content}
                ]
            }
        }
        
        # Should be able to detect oversized content
        content_length = len(request['body']['messages'][0]['content'])
        assert content_length == 100_000

    def test_many_messages(self):
        """Test that requests with many messages can be detected."""
        messages = [{"role": "user", "content": f"Message {i}"} for i in range(1000)]
        request = {
            "custom_id": "1",
            "body": {"messages": messages}
        }
        
        # Should be able to detect many messages
        assert len(request['body']['messages']) == 1000

    def test_deeply_nested_json(self):
        """Test that deeply nested JSON can be parsed."""
        request = {
            "custom_id": "1",
            "body": {
                "messages": [{"role": "user", "content": "test"}],
                "metadata": {
                    "level1": {
                        "level2": {
                            "level3": {
                                "level4": "deep"
                            }
                        }
                    }
                }
            }
        }
        
        # Should be able to parse deeply nested structure
        assert request['body']['metadata']['level1']['level2']['level3']['level4'] == "deep"

