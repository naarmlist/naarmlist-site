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
    # Artists should be queued for review instead of written directly
    all_artists = list(db.Artists.find())
    assert all_artists == []
    pending = list(db.tmp.find({'collection_name': 'Artists'}))
    names = [p['payload']['name'] for p in pending]
    assert 'Sun Araw' in names
    assert 'Another Artist' in names
    for p in pending:
        assert p['payload']['description'] == ''
        assert p['payload']['tags'] == ''

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
    # Existing artist should avoid creating new queued writes
    pending = list(db.tmp.find({'collection_name': 'Artists'}))
    assert len(pending) == 0
    # Should still only be one Sun Araw in the destination table
    all_artists = list(db.Artists.find({'name': {'$regex': '^Sun Araw$', '$options': 'i'}}))
    assert len(all_artists) == 1

def test_approve_pending_artist_edit(client):
    db = get_db_connection()
    artist_id = db.Artists.insert_one({'name': 'Alpha', 'description': '', 'tags': ''}).inserted_id
    pending_id = db.tmp.insert_one({
        'collection_name': 'Artists',
        'payload': {'description': 'Updated bio', 'links': ['https://example.com/alpha']},
        'target_id': artist_id,
        'lookup_name': 'Alpha',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id

    with client.session_transaction() as sess:
        sess['admin'] = True

    response = client.post(f'/admin/review_edits/{pending_id}/approve', follow_redirects=True)
    assert response.status_code == 200

    updated = db.Artists.find_one({'_id': artist_id})
    assert updated['description'] == 'Updated bio'
    assert updated['links'] == ['https://example.com/alpha']
    assert db.tmp.find_one({'_id': pending_id}) is None

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
