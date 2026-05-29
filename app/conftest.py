"""Shared pytest fixtures for the Flask app test suite.

Each test gets a fresh in-memory mongomock database via ``app.db_override``.
That lets route tests seed dummy data freely without touching a real MongoDB
instance or leaking state between tests.
"""

import mongomock
import pytest


@pytest.fixture
def client(monkeypatch):
    """Return a Flask test client wired to a fresh mongomock database."""
    mock_client = mongomock.MongoClient()
    db = mock_client['testdb']
    monkeypatch.setenv('DB_URL', 'mongodb://localhost')
    monkeypatch.setenv('DB_NAME', 'testdb')

    from app import app as real_app

    real_app.db_override = db
    real_app.config['TESTING'] = True
    with real_app.test_client() as client:
        yield client
    real_app.db_override = None


@pytest.fixture
def db(client):
    """Return the current test database attached to the Flask app."""
    from app import get_db_connection

    return get_db_connection()


@pytest.fixture
def event_form():
    """Return a complete valid event form payload for POST route tests."""
    return {
        'title': 'Test Event',
        'organisers': 'Org1',
        'venue': 'Venue1',
        'link': 'http://example.com',
        'start_datetime': '2025-06-09T20:00',
        'end_datetime': '2025-06-09T22:00',
        'tags': 'tag1,tag2',
        'artists': 'Sun Araw'
    }


@pytest.fixture
def login_admin(client):
    """Return a helper that marks the current test session as admin."""

    def _login_admin():
        """Set the Flask session's admin flag for the current client."""
        with client.session_transaction() as sess:
            sess['admin'] = True

    return _login_admin


@pytest.fixture
def insert_event(db):
    """Return a helper that inserts a valid event document with overrides."""

    def _insert_event(**overrides):
        """Insert one event into the isolated test database."""
        event = {
            'title': 'Listed Event',
            'organisers': 'Org1',
            'venue': 'Venue1',
            'link': 'https://example.com/event',
            'start_datetime': '2099-06-09T20:00',
            'end_datetime': '2099-06-09T22:00',
            'tags': ['tag1', 'tag2'],
            'artists': ['Sun Araw']
        }
        event.update(overrides)
        return db.events.insert_one(event).inserted_id

    return _insert_event
