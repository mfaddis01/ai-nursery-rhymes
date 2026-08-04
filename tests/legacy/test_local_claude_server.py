#!/usr/bin/env python3
"""
Tests for the local Claude API server.

Tests cover:
- Health check endpoint
- Valid rhyme generation
- Input validation (missing fields, invalid types)
- Error handling (malformed JSON, missing Content-Type)
- Timeout handling
"""

import pytest
from unittest.mock import patch, MagicMock

# Add src to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import local_claude_server
from local_claude_server import app, generate_rhyme_with_claude, sdk_importable

# The generation-path tests drive the real Agent SDK message types with a fake
# transport. They can only run where claude-agent-sdk is installed.
requires_sdk = pytest.mark.skipif(
    not sdk_importable, reason="claude-agent-sdk is not installed"
)


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthCheck:
    """Test the health check endpoint."""

    def test_health_check_success(self, client):
        """Health check should return 200 with status ok."""
        response = client.get('/health')
        assert response.status_code == 200

        data = response.get_json()
        assert data['status'] == 'ok'
        assert 'claude_available' in data
        assert 'timestamp' in data


class TestGenerateRhyme:
    """Test the /generate-rhyme endpoint."""

    @patch('local_claude_server.generate_rhyme_with_claude')
    def test_generate_rhyme_minimal_request(self, mock_generate, client):
        """Generate rhyme with minimal request (no theme)."""
        mock_rhyme = "Twinkle, twinkle, little star\nHow I wonder what you are"
        mock_generate.return_value = mock_rhyme

        response = client.post(
            '/generate-rhyme',
            json={},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['rhyme'] == mock_rhyme
        mock_generate.assert_called_once_with(theme=None, age_group='2-5')

    @patch('local_claude_server.generate_rhyme_with_claude')
    def test_generate_rhyme_with_theme(self, mock_generate, client):
        """Generate rhyme with theme."""
        mock_rhyme = "Mary had a little lamb\nWith fleece as white as snow"
        mock_generate.return_value = mock_rhyme

        response = client.post(
            '/generate-rhyme',
            json={'theme': 'animals', 'age_group': '3-5'},
            content_type='application/json'
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['rhyme'] == mock_rhyme
        mock_generate.assert_called_once_with(theme='animals', age_group='3-5')

    def test_generate_rhyme_missing_content_type(self, client):
        """Request without Content-Type should return 400."""
        response = client.post(
            '/generate-rhyme',
            data='{"theme": "test"}'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_generate_rhyme_malformed_json(self, client):
        """Malformed JSON should return 400."""
        response = client.post(
            '/generate-rhyme',
            data='{"invalid json',
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_generate_rhyme_non_json_body(self, client):
        """Non-JSON body should return 400."""
        response = client.post(
            '/generate-rhyme',
            data='not json',
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_generate_rhyme_invalid_theme_type(self, client):
        """Theme as non-string should return 400."""
        response = client.post(
            '/generate-rhyme',
            json={'theme': 123},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'theme must be a string' in data['error']

    def test_generate_rhyme_invalid_age_group_type(self, client):
        """Age group as non-string should return 400."""
        response = client.post(
            '/generate-rhyme',
            json={'age_group': 123},
            content_type='application/json'
        )
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
        assert 'age_group must be a string' in data['error']

    def test_generate_rhyme_empty_theme_becomes_none(self, client):
        """Empty theme string should be treated as None."""
        mock_generate = MagicMock(return_value="Mock rhyme")
        with patch('local_claude_server.generate_rhyme_with_claude', mock_generate):
            response = client.post(
                '/generate-rhyme',
                json={'theme': '   '},
                content_type='application/json'
            )
            assert response.status_code == 200
            # Empty theme should be treated as None
            mock_generate.assert_called_once_with(theme=None, age_group='2-5')

    def test_generate_rhyme_empty_age_group_becomes_default(self, client):
        """Empty age group string should be treated as default."""
        mock_generate = MagicMock(return_value="Mock rhyme")
        with patch('local_claude_server.generate_rhyme_with_claude', mock_generate):
            response = client.post(
                '/generate-rhyme',
                json={'age_group': '   '},
                content_type='application/json'
            )
            assert response.status_code == 200
            mock_generate.assert_called_once_with(theme=None, age_group='2-5')

    @patch('local_claude_server.generate_rhyme_with_claude')
    def test_generate_rhyme_claude_unavailable(self, mock_generate, client):
        """When Claude is unavailable, should return 500."""
        mock_generate.side_effect = RuntimeError("Claude client not available")

        response = client.post(
            '/generate-rhyme',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data
        assert 'unavailable' in data['error'].lower()

    @patch('local_claude_server.generate_rhyme_with_claude')
    def test_generate_rhyme_timeout(self, mock_generate, client):
        """When generation times out, should return 504."""
        mock_generate.side_effect = TimeoutError("Generation timeout")

        response = client.post(
            '/generate-rhyme',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 504
        data = response.get_json()
        assert 'error' in data
        assert 'timeout' in data['error'].lower()

    @patch('local_claude_server.generate_rhyme_with_claude')
    def test_generate_rhyme_error_does_not_leak_exception_text(self, mock_generate, client):
        """Internal exception detail must never reach the client."""
        # Arrange
        secret = 'x-api-key: sk-ant-SUPERSECRET at https://internal.host/v1'
        mock_generate.side_effect = ValueError(secret)

        # Act
        response = client.post(
            '/generate-rhyme',
            json={},
            content_type='application/json'
        )

        # Assert
        assert response.status_code == 500
        body = response.get_data(as_text=True)
        assert 'sk-ant-SUPERSECRET' not in body
        assert 'internal.host' not in body
        assert response.get_json()['error'] == 'Internal server error'

    @patch('local_claude_server.generate_rhyme_with_claude')
    def test_generate_rhyme_unexpected_error(self, mock_generate, client):
        """Unexpected errors should return 500."""
        mock_generate.side_effect = ValueError("Unexpected error")

        response = client.post(
            '/generate-rhyme',
            json={},
            content_type='application/json'
        )
        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


class TestErrorHandling:
    """Test error handling endpoints."""

    def test_404_not_found(self, client):
        """Non-existent endpoint should return 404."""
        response = client.post('/nonexistent', json={})
        assert response.status_code == 404
        data = response.get_json()
        assert 'error' in data

    def test_405_method_not_allowed(self, client):
        """Wrong HTTP method should return 405."""
        response = client.get('/generate-rhyme')
        assert response.status_code == 405
        data = response.get_json()
        assert 'error' in data


def _fake_query(text="Generated rhyme text", *, is_error=False, delay=0.0):
    """
    Build a stand-in for ``claude_agent_sdk.query``.

    Yields real SDK message objects so the parsing in ``_generate_async`` is
    exercised for real; only the CLI subprocess is replaced.
    """
    import anyio
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

    captured = {}

    async def fake_query(*, prompt, options=None, **kwargs):
        captured['prompt'] = prompt
        captured['options'] = options
        if delay:
            await anyio.sleep(delay)
        yield AssistantMessage(content=[TextBlock(text=text)], model='test-model')
        yield ResultMessage(
            subtype='error_during_execution' if is_error else 'success',
            duration_ms=1,
            duration_api_ms=1,
            is_error=is_error,
            num_turns=1,
            session_id='test-session',
        )

    return fake_query, captured


@requires_sdk
class TestGenerateRhymeFunction:
    """Test the generate_rhyme_with_claude function."""

    @patch('local_claude_server.claude_available', True)
    def test_generate_rhyme_function_success(self):
        """Function should drive the CLI and return the assistant text."""
        # Arrange
        fake_query, captured = _fake_query("Generated rhyme text")

        # Act
        with patch('local_claude_server.query', fake_query):
            result = generate_rhyme_with_claude(theme='animals', age_group='2-5')

        # Assert
        assert result == "Generated rhyme text"
        assert 'animals' in captured['prompt']
        assert '2-5' in captured['prompt']

    @patch('local_claude_server.claude_available', True)
    def test_generate_rhyme_function_no_theme(self):
        """Function should work without theme."""
        # Arrange
        fake_query, captured = _fake_query()

        # Act
        with patch('local_claude_server.query', fake_query):
            result = generate_rhyme_with_claude(theme=None, age_group='3-5')

        # Assert
        assert result == "Generated rhyme text"
        assert 'with theme' not in captured['prompt']

    @patch('local_claude_server.claude_available', True)
    def test_generate_rhyme_requires_no_api_key(self, monkeypatch):
        """
        Generation must succeed with ANTHROPIC_API_KEY absent from the env.

        This is the whole point of driving the local CLI: auth comes from
        `claude login`, never from a server-side API key.
        """
        # Arrange
        monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
        fake_query, _ = _fake_query("Rhyme without a key")

        # Act
        with patch('local_claude_server.query', fake_query):
            result = generate_rhyme_with_claude()

        # Assert
        assert result == "Rhyme without a key"

    @patch('local_claude_server.claude_available', True)
    def test_generate_rhyme_sends_no_tools_and_no_inherited_settings(self):
        """The rhyme call must not expose tools or the operator's settings."""
        # Arrange
        fake_query, captured = _fake_query()

        # Act
        with patch('local_claude_server.query', fake_query):
            generate_rhyme_with_claude()

        # Assert
        assert captured['options'].tools == []
        assert captured['options'].setting_sources is None
        assert captured['options'].max_turns == 1

    @patch('local_claude_server.claude_available', True)
    def test_generate_rhyme_error_result_raises(self):
        """An is_error result from the CLI must not be reported as success."""
        # Arrange
        fake_query, _ = _fake_query("partial", is_error=True)

        # Act / Assert
        with patch('local_claude_server.query', fake_query):
            with pytest.raises(RuntimeError):
                generate_rhyme_with_claude()

    @patch('local_claude_server.claude_available', True)
    def test_generate_rhyme_empty_output_raises(self):
        """Empty CLI output must raise rather than return a blank rhyme."""
        # Arrange
        fake_query, _ = _fake_query("   ")

        # Act / Assert
        with patch('local_claude_server.query', fake_query):
            with pytest.raises(RuntimeError):
                generate_rhyme_with_claude()

    @patch('local_claude_server.claude_available', True)
    def test_generate_rhyme_times_out(self):
        """Generation exceeding CLAUDE_TIMEOUT_SECONDS raises TimeoutError."""
        # Arrange
        fake_query, _ = _fake_query(delay=5.0)

        # Act / Assert
        with patch('local_claude_server.query', fake_query), \
                patch('local_claude_server.CLAUDE_TIMEOUT_SECONDS', 0.1):
            with pytest.raises(TimeoutError):
                generate_rhyme_with_claude()

    @patch('local_claude_server.claude_available', False)
    def test_generate_rhyme_function_unavailable(self):
        """Function should raise error when the CLI is unavailable."""
        with pytest.raises(RuntimeError):
            generate_rhyme_with_claude()

    @patch('local_claude_server.claude_available', True)
    def test_generate_rhyme_function_propagates_errors(self):
        """Unexpected SDK errors should propagate to the caller."""
        # Arrange
        async def exploding_query(*, prompt, options=None, **kwargs):
            raise ValueError("CLI Error")
            yield  # pragma: no cover - makes this an async generator

        # Act / Assert
        with patch('local_claude_server.query', exploding_query):
            with pytest.raises(ValueError):
                generate_rhyme_with_claude()


class TestCliResolution:
    """Test how the server locates the claude CLI."""

    def test_find_cli_uses_path_when_no_override(self):
        """With no override set, the CLI is looked up on PATH."""
        with patch('local_claude_server.CLAUDE_CLI_PATH', None), \
                patch('local_claude_server.shutil.which', return_value='/usr/bin/claude'):
            assert local_claude_server._find_claude_cli() == '/usr/bin/claude'

    def test_find_cli_returns_none_when_missing(self):
        """A missing CLI resolves to None so startup can fail fast."""
        with patch('local_claude_server.CLAUDE_CLI_PATH', None), \
                patch('local_claude_server.shutil.which', return_value=None):
            assert local_claude_server._find_claude_cli() is None

    def test_explicit_override_is_not_silently_ignored(self):
        """A CLAUDE_CLI_PATH that does not exist must not fall back to PATH."""
        with patch('local_claude_server.CLAUDE_CLI_PATH', '/nope/claude'), \
                patch('local_claude_server.shutil.which', return_value='/usr/bin/claude'):
            assert local_claude_server._find_claude_cli() is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
