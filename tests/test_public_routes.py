"""Public route tests for listings, details, search, and utility pages."""


def test_directory_indexes_sort_entries_case_insensitively(client, db):
    """Sort directory index entries case-insensitively."""
    db.Artists.insert_many([
        {'name': 'bravo', 'description': '', 'tags': ''},
        {'name': 'Alpha', 'description': '', 'tags': ''},
    ])
    db.venues.insert_many([
        {'name': 'zeta', 'description': '', 'location': '', 'contact': '', 'links': []},
        {'name': 'Beta', 'description': '', 'location': '', 'contact': '', 'links': []},
    ])
    db.Organisers.insert_many([
        {'name': 'delta', 'description': '', 'contact': '', 'links': []},
        {'name': 'Charlie', 'description': '', 'contact': '', 'links': []},
    ])

    artists = client.get('/artists').data.decode()
    venues = client.get('/venues').data.decode()
    organisers = client.get('/organisers').data.decode()

    assert artists.index('Alpha') < artists.index('bravo')
    assert venues.index('Beta') < venues.index('zeta')
    assert organisers.index('Charlie') < organisers.index('delta')


def test_detail_pages_render_missing_optional_links(client, db):
    """Render detail pages when optional links fields are absent."""
    artist_id = db.Artists.insert_one(
        {'name': 'Artist', 'description': '', 'tags': ''}).inserted_id
    venue_id = db.venues.insert_one({
        'name': 'Venue',
        'description': '',
        'location': '',
        'contact': '',
    }).inserted_id
    organiser_id = db.Organisers.insert_one({
        'name': 'Organiser',
        'description': 'Description',
        'contact': 'hello@example.com',
    }).inserted_id

    artist = client.get(f'/artist/{artist_id}')
    venue = client.get(f'/venue/{venue_id}')
    organiser = client.get(f'/organiser/{organiser_id}')

    assert artist.status_code == 200
    assert b'Artist' in artist.data
    assert venue.status_code == 200
    assert b'No links available' in venue.data
    assert organiser.status_code == 200
    assert b'Organiser' in organiser.data


def test_notes_lists_existing_note_and_filters_search(client):
    """List notes and filter note search results."""
    list_response = client.get('/notes')
    found_response = client.post('/notes', data={'search': 'database'})
    missing_response = client.post('/notes', data={'search': 'zz-no-match-zz'})

    assert list_response.status_code == 200
    assert b'Database crashed out today.' in list_response.data
    assert found_response.status_code == 200
    assert b'Database crashed out today.' in found_response.data
    assert missing_response.status_code == 200
    assert b'No items found for search' in missing_response.data


def test_index_search_matches_title_artist_venue_and_tag(client, db, insert_event):
    """Find upcoming events by title, artist, venue, and tag search."""
    insert_event(
        title='Noise Night',
        artists=['Search Artist'],
        venue='Search Venue',
        tags=['leftfield'],
        start_datetime='2099-07-01T20:00',
        end_datetime='2099-07-01T22:00'
    )
    insert_event(
        title='Other Event',
        artists=['Other Artist'],
        venue='Other Venue',
        tags=['other'],
        start_datetime='2099-07-02T20:00',
        end_datetime='2099-07-02T22:00'
    )

    title_html = client.post('/', data={'search': 'Noise'}).data.decode()
    artist_html = client.post('/', data={'search': 'Search Artist'}).data.decode()
    venue_html = client.post('/', data={'search': 'Search Venue'}).data.decode()
    tag_html = client.post('/', data={'search': 'leftfield'}).data.decode()

    assert 'Noise Night' in title_html
    assert 'Noise Night' in artist_html
    assert 'Noise Night' in venue_html
    assert 'Noise Night' in tag_html
    assert 'Other Event' not in title_html


def test_add_event_and_static_robots_routes(client):
    """Render the add-event form and static robots.txt route."""
    add_event = client.get('/addEvent')
    robots = client.get('/robots.txt')

    assert add_event.status_code == 200
    assert b'/createEvent' in add_event.data
    assert robots.status_code == 200


def test_admin_logout_clears_session(client, login_admin):
    """Clear the admin flag when logging out."""
    login_admin()

    response = client.get('/admin/logout')

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess['admin'] is False
