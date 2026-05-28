import pytest
from app import get_db_connection
import mongomock

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

def test_directory_entries_added_on_event_creation(client):
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
    # Blank directory entries should be added directly, trimmed, and without review.
    all_artists = list(db.Artists.find())
    names = [a['name'] for a in all_artists]
    assert 'Sun Araw' in names
    assert 'Another Artist' in names
    for a in all_artists:
        assert a['description'] == ''
        assert a['tags'] == ''
    assert db.Organisers.find_one({'name': 'Org1'})['description'] == ''
    assert db.venues.find_one({'name': 'Venue1'})['description'] == ''
    assert db.pending_edits.count_documents({}) == 0

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
    assert 'Artist Directory' in html
    assert 'edit this page' not in html
    # Sorted order
    assert html.index('Alpha') < html.index('Bravo') < html.index('Charlie')

def test_artist_edit_is_queued_for_review(client):
    db = get_db_connection()
    artist_id = db.Artists.insert_one({
        'name': 'Sun Araw',
        'description': '',
        'tags': '',
        'links': []
    }).inserted_id

    response = client.post(f'/artist/{artist_id}/edit', data={
        'description': 'A bio awaiting review.',
        'links': ['https://example.com', '']
    }, follow_redirects=True)

    assert response.status_code == 200
    html = response.data.decode()
    assert 'Your edit is currently under review.' in html
    artist = db.Artists.find_one({'_id': artist_id})
    assert artist['description'] == ''
    pending_edit = db.pending_edits.find_one({
        'collection_name': 'Artists',
        'target_id': str(artist_id)
    })
    assert pending_edit['lookup_name'] == 'Sun Araw'
    assert pending_edit['status'] == 'pending'
    assert pending_edit['update_fields'] == {
        'description': 'A bio awaiting review.',
        'links': ['https://example.com']
    }

def test_organiser_and_venue_edits_are_queued_for_review(client):
    db = get_db_connection()
    organiser_id = db.Organisers.insert_one({
        'name': 'Org1',
        'description': '',
        'contact': '',
        'links': []
    }).inserted_id
    venue_id = db.venues.insert_one({
        'name': 'Venue1',
        'description': '',
        'location': '',
        'contact': '',
        'links': []
    }).inserted_id

    organiser_response = client.post(f'/organiser/{organiser_id}/edit', data={
        'description': 'Organiser description',
        'contact': 'hello@example.com',
        'links': 'https://org.example\n\nhttps://org.example/social'
    }, follow_redirects=True)
    venue_response = client.post(f'/venue/{venue_id}/edit', data={
        'description': 'Venue description',
        'location': 'Brunswick',
        'contact': 'venue@example.com',
        'links': ['https://venue.example', '']
    }, follow_redirects=True)

    assert organiser_response.status_code == 200
    assert venue_response.status_code == 200
    assert db.Organisers.find_one({'_id': organiser_id})['description'] == ''
    assert db.venues.find_one({'_id': venue_id})['description'] == ''
    organiser_edit = db.pending_edits.find_one({
        'collection_name': 'Organisers',
        'target_id': str(organiser_id)
    })
    venue_edit = db.pending_edits.find_one({
        'collection_name': 'venues',
        'target_id': str(venue_id)
    })
    assert organiser_edit['update_fields'] == {
        'description': 'Organiser description',
        'contact': 'hello@example.com',
        'links': ['https://org.example', 'https://org.example/social']
    }
    assert venue_edit['update_fields'] == {
        'description': 'Venue description',
        'location': 'Brunswick',
        'contact': 'venue@example.com',
        'links': ['https://venue.example']
    }
