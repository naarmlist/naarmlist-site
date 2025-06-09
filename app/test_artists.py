import pytest
from flask import Flask
from app import app as flask_app, get_db_connection
import mongomock
import os
import tempfile

@pytest.fixture
def client(monkeypatch):
    # Use mongomock for MongoDB
    mock_client = mongomock.MongoClient()
    db = mock_client['testdb']
    monkeypatch.setenv('DB_URL', 'mongodb://localhost')
    monkeypatch.setenv('DB_NAME', 'testdb')
    # Patch get_db_connection to use mongomock via app.db_override
    from app import app as real_app
    real_app.db_override = db
    real_app.config['TESTING'] = True
    with real_app.test_client() as client:
        yield client
    real_app.db_override = None

def test_artist_added_on_event_creation(client):
    # Post a new event with a new artist
    response = client.post('/createEvent', data={
        'title': 'Test Event',
        'organisers': 'Org1',
        'venue': 'Venue1',
        'link': 'http://example.com',
        'start_datetime': '2025-06-09T20:00',
        'end_datetime': '2025-06-09T22:00',
        'tags': 'tag1,tag2',
        'artists': '  Sun Araw  ,Another Artist'
    }, follow_redirects=True)
    assert response.status_code == 200
    db = get_db_connection()
    # Artists should be added, trimmed, and case-insensitive
    all_artists = list(db.Artists.find())
    names = [a['name'] for a in all_artists]
    assert 'Sun Araw' in names
    assert 'Another Artist' in names
    # Description and tags should be blank
    for a in all_artists:
        assert a['description'] == ''
        assert a['tags'] == ''

def test_artist_not_duplicated(client):
    db = get_db_connection()
    db.Artists.insert_one({'name': 'Sun Araw', 'description': '', 'tags': ''})
    # Post event with same artist, different case and spaces
    response = client.post('/createEvent', data={
        'title': 'Test Event 2',
        'organisers': 'Org2',
        'venue': 'Venue2',
        'link': 'http://example.com',
        'start_datetime': '2025-06-10T20:00',
        'end_datetime': '2025-06-10T22:00',
        'tags': 'tag3',
        'artists': ' sun araw '
    }, follow_redirects=True)
    assert response.status_code == 200
    # Should still only be one Sun Araw
    all_artists = list(db.Artists.find({'name': {'$regex': '^Sun Araw$', '$options': 'i'}}))
    assert len(all_artists) == 1

def test_artists_page_table(client):
    db = get_db_connection()
    db.Artists.insert_many([
        {'name': 'Alpha', 'description': '', 'tags': ''},
        {'name': 'Bravo', 'description': 'desc', 'tags': 'tag'},
        {'name': 'Charlie', 'description': '', 'tags': 'tag2'}
    ])
    response = client.get('/artists')
    html = response.data.decode()
    # Table headers
    assert '<th>Artist</th>' in html
    assert '<th>Description</th>' in html
    assert '<th>Tags</th>' in html
    # Edit link for blank description
    assert html.count('edit this entry') >= 1
    # Sorted order
    assert html.index('Alpha') < html.index('Bravo') < html.index('Charlie')
