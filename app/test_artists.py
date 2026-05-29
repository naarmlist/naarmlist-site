"""Event, directory, and review workflow regression tests."""

from app import get_db_connection

EVENT_FORM = {
    'title': 'Test Event',
    'organisers': 'Org1',
    'venue': 'Venue1',
    'link': 'http://example.com',
    'start_datetime': '2025-06-09T20:00',
    'end_datetime': '2025-06-09T22:00',
    'tags': 'tag1,tag2',
    'artists': 'Sun Araw'
}


def login_admin(client):
    """Mark the current Flask test session as an admin."""
    with client.session_transaction() as sess:
        sess['admin'] = True


def insert_event(db, **overrides):
    """Insert a valid event document into the active test database."""
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


def test_directory_entries_added_on_event_creation(client):
    """Create blank directory records directly during event creation."""
    # Post a new event with a new artist
    response = client.post('/createEvent', data={
        **EVENT_FORM,
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
    assert db.tmp.count_documents({}) == 0


def test_create_event_rejects_end_before_start(client):
    """Reject event forms where the end time is not after the start time."""
    response = client.post('/createEvent', data={
        **EVENT_FORM,
        'start_datetime': '2025-06-09T22:00',
        'end_datetime': '2025-06-09T20:00'
    })

    assert response.status_code == 400
    assert b'End datetime must be after start datetime' in response.data
    assert get_db_connection().events.count_documents({}) == 0


def test_create_event_rejects_invalid_datetime(client):
    """Reject event forms with invalid datetime values."""
    response = client.post('/createEvent', data={
        **EVENT_FORM,
        'start_datetime': 'not-a-date'
    })

    assert response.status_code == 400
    assert b'Invalid datetime format' in response.data
    assert get_db_connection().events.count_documents({}) == 0


def test_create_event_splits_and_trims_lists(client):
    """Split and trim artists, tags, organisers, and venue inputs."""
    response = client.post('/createEvent', data={
        **EVENT_FORM,
        'artists': ' Alpha , , Bravo ',
        'tags': ' noise , , ambient ',
        'organisers': ' Org1 , Org2 ',
        'venue': ' Venue1 '
    })
    db = get_db_connection()
    event = db.events.find_one({'title': 'Test Event'})

    assert response.status_code == 302
    assert event['artists'] == ['Alpha', 'Bravo']
    assert event['tags'] == ['noise', 'ambient']
    assert db.Artists.count_documents({}) == 2
    assert db.Organisers.count_documents({}) == 2
    assert db.venues.count_documents({}) == 1


def test_artist_not_duplicated(client):
    """Avoid duplicate artist records when names differ only by case or spaces."""
    db = get_db_connection()
    db.Artists.insert_one({'name': 'Sun Araw', 'description': '', 'tags': ''})
    # Post event with same artist, different case and spaces
    response = client.post('/createEvent', data={
        **EVENT_FORM,
        'title': 'Test Event 2',
        'organisers': 'Org2',
        'venue': 'Venue2',
        'start_datetime': '2025-06-10T20:00',
        'end_datetime': '2025-06-10T22:00',
        'tags': 'tag3',
        'artists': ' sun araw '
    }, follow_redirects=True)
    assert response.status_code == 200
    # Should still only be one Sun Araw in the destination table
    all_artists = list(db.Artists.find({'name': {'$regex': '^Sun Araw$', '$options': 'i'}}))
    assert len(all_artists) == 1
    assert db.tmp.count_documents({'collection_name': 'Artists'}) == 0


def test_approve_pending_artist_edit(client):
    """Apply an approved artist edit to the target artist record."""
    db = get_db_connection()
    artist_id = db.Artists.insert_one({'name': 'Alpha', 'description': '', 'tags': ''}).inserted_id
    pending_id = db.tmp.insert_one({
        'collection_name': 'Artists',
        'payload': {'description': 'Updated bio', 'links': ['https://example.com/alpha']},
        'target_id': artist_id,
        'lookup_name': 'Alpha',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id

    login_admin(client)

    response = client.post(f'/admin/review_edits/{pending_id}/approve', follow_redirects=True)
    assert response.status_code == 200

    updated = db.Artists.find_one({'_id': artist_id})
    assert updated['description'] == 'Updated bio'
    assert updated['links'] == ['https://example.com/alpha']
    assert db.tmp.find_one({'_id': pending_id}) is None


def test_approve_pending_organiser_edit_updates_target(client):
    """Apply an approved organiser edit to the target organiser record."""
    db = get_db_connection()
    organiser_id = db.Organisers.insert_one({
        'name': 'Org1',
        'description': '',
        'contact': '',
        'links': []
    }).inserted_id
    pending_id = db.tmp.insert_one({
        'collection_name': 'Organisers',
        'payload': {
            'description': 'Approved organiser',
            'contact': 'org@example.com',
            'links': ['https://org.example']
        },
        'target_id': organiser_id,
        'lookup_name': 'Org1',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id
    login_admin(client)

    response = client.post(f'/admin/review_edits/{pending_id}/approve', follow_redirects=True)

    assert response.status_code == 200
    organiser = db.Organisers.find_one({'_id': organiser_id})
    assert organiser['description'] == 'Approved organiser'
    assert organiser['contact'] == 'org@example.com'
    assert organiser['links'] == ['https://org.example']
    assert db.tmp.find_one({'_id': pending_id}) is None


def test_approve_pending_new_venue_inserts_destination_record(client):
    """Insert a new venue when approving a queued venue submission."""
    db = get_db_connection()
    response = client.post('/createVenue', data={
        'name': 'New Venue',
        'description': 'A submitted venue',
        'location': 'Footscray',
        'contact': 'venue@example.com',
        'link': 'https://venue.example'
    })
    assert response.status_code == 302
    assert db.venues.find_one({'name': 'New Venue'}) is None

    pending = db.tmp.find_one({'collection_name': 'venues', 'lookup_name': 'New Venue'})
    assert pending is not None
    login_admin(client)
    response = client.post(f"/admin/review_edits/{pending['_id']}/approve", follow_redirects=True)

    assert response.status_code == 200
    venue = db.venues.find_one({'name': 'New Venue'})
    assert venue['description'] == 'A submitted venue'
    assert venue['location'] == 'Footscray'
    assert db.tmp.find_one({'_id': pending['_id']}) is None


def test_approve_pending_new_venue_updates_existing_case_insensitive_match(client):
    """Update an existing venue by case-insensitive lookup on approval."""
    db = get_db_connection()
    existing_id = db.venues.insert_one({
        'name': 'Existing Venue',
        'description': '',
        'location': '',
        'contact': '',
        'links': []
    }).inserted_id
    pending_id = db.tmp.insert_one({
        'collection_name': 'venues',
        'payload': {
            'name': 'existing venue',
            'description': 'Reviewed description',
            'location': 'Northcote'
        },
        'target_id': None,
        'lookup_name': 'existing venue',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id
    login_admin(client)

    response = client.post(f'/admin/review_edits/{pending_id}/approve', follow_redirects=True)

    assert response.status_code == 200
    assert db.venues.count_documents(
        {'name': {'$regex': '^existing venue$', '$options': 'i'}}) == 1
    updated = db.venues.find_one({'_id': existing_id})
    assert updated['name'] == 'existing venue'
    assert updated['description'] == 'Reviewed description'
    assert updated['location'] == 'Northcote'


def test_reject_pending_edit_removes_queue_item_without_applying_payload(client):
    """Reject a queued edit without mutating the destination record."""
    db = get_db_connection()
    artist_id = db.Artists.insert_one({'name': 'Alpha', 'description': '', 'tags': ''}).inserted_id
    pending_id = db.tmp.insert_one({
        'collection_name': 'Artists',
        'payload': {'description': 'Rejected bio'},
        'target_id': artist_id,
        'lookup_name': 'Alpha',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id
    login_admin(client)

    response = client.post(f'/admin/review_edits/{pending_id}/reject', follow_redirects=True)

    assert response.status_code == 200
    assert db.tmp.find_one({'_id': pending_id}) is None
    assert db.Artists.find_one({'_id': artist_id})['description'] == ''


def test_review_routes_require_admin_session(client):
    """Require an admin session for all review queue routes."""
    db = get_db_connection()
    pending_id = db.tmp.insert_one({
        'collection_name': 'Artists',
        'payload': {'description': 'Nope'},
        'target_id': None,
        'lookup_name': 'Alpha',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id

    list_response = client.get('/admin/review_edits')
    approve_response = client.post(f'/admin/review_edits/{pending_id}/approve')
    reject_response = client.post(f'/admin/review_edits/{pending_id}/reject')

    assert list_response.status_code == 302
    assert approve_response.status_code == 302
    assert reject_response.status_code == 302
    assert '/admin' in list_response.headers['Location']
    assert db.tmp.find_one({'_id': pending_id}) is not None


def test_approve_rejects_unknown_review_collection(client):
    """Reject queued edits that target non-reviewable collections."""
    db = get_db_connection()
    pending_id = db.tmp.insert_one({
        'collection_name': 'events',
        'payload': {'title': 'Should not apply'},
        'target_id': None,
        'lookup_name': 'Should not apply',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id
    login_admin(client)

    response = client.post(f'/admin/review_edits/{pending_id}/approve')

    assert response.status_code == 400
    assert db.events.find_one({'title': 'Should not apply'}) is None
    assert db.tmp.find_one({'_id': pending_id}) is not None


def test_admin_review_missing_edit_returns_404(client):
    """Return 404 when approving a missing queued edit."""
    login_admin(client)
    missing_id = '507f1f77bcf86cd799439011'

    response = client.post(f'/admin/review_edits/{missing_id}/approve')

    assert response.status_code == 404


def test_admin_login_success_and_failure(monkeypatch, client):
    """Handle successful and failed admin logins."""
    monkeypatch.setenv('ADMIN_USER', 'admin')
    monkeypatch.setenv('ADMIN_PASS', 'secret')

    failed = client.post('/admin', data={'username': 'admin', 'password': 'wrong'})
    passed = client.post('/admin', data={'username': 'admin', 'password': 'secret'})

    assert failed.status_code == 200
    assert b'Invalid credentials' in failed.data
    assert passed.status_code == 302
    assert passed.headers['Location'].endswith('/admin/events')


def test_admin_event_routes_require_login(client):
    """Require admin login before event management routes mutate data."""
    db = get_db_connection()
    event_id = insert_event(db)

    list_response = client.get('/admin/events')
    edit_response = client.get(f'/admin/edit/{event_id}')
    delete_response = client.post(f'/admin/delete/{event_id}')

    assert list_response.status_code == 302
    assert edit_response.status_code == 302
    assert delete_response.status_code == 302
    assert db.events.find_one({'_id': event_id}) is not None


def test_admin_delete_removes_event(client):
    """Delete an event from the admin event list."""
    db = get_db_connection()
    event_id = insert_event(db)
    login_admin(client)

    response = client.post(f'/admin/delete/{event_id}', follow_redirects=True)

    assert response.status_code == 200
    assert db.events.find_one({'_id': event_id}) is None


def test_admin_edit_updates_event_and_adds_new_artists_directly(client):
    """Update an event and add new blank artist records from admin edits."""
    db = get_db_connection()
    event_id = insert_event(db)
    login_admin(client)

    response = client.post(f'/admin/edit/{event_id}', data={
        'title': 'Updated Event',
        'organisers': 'Updated Org',
        'venue': 'Updated Venue',
        'link': 'https://example.com/updated',
        'start_datetime': '2099-06-10T20:00',
        'end_datetime': '2099-06-10T22:00',
        'tags': 'updated,tag',
        'artists': 'New Artist, Sun Araw'
    }, follow_redirects=True)

    assert response.status_code == 200
    event = db.events.find_one({'_id': event_id})
    assert event['title'] == 'Updated Event'
    assert event['tags'] == ['updated', 'tag']
    assert event['artists'] == ['New Artist', 'Sun Araw']
    assert db.Artists.find_one({'name': 'New Artist'})['description'] == ''
    assert db.tmp.count_documents({'collection_name': 'Artists'}) == 0


def test_artists_page_table(client):
    """Render the artist directory in sorted order."""
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
    """Queue public artist edits instead of applying them immediately."""
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
    pending_edit = db.tmp.find_one({
        'collection_name': 'Artists',
        'target_id': artist_id
    })
    assert pending_edit['lookup_name'] == 'Sun Araw'
    assert pending_edit['payload'] == {
        'description': 'A bio awaiting review.',
        'links': ['https://example.com']
    }


def test_artist_edit_get_allows_public_form_and_defaults_missing_links(client):
    """Render the public artist edit form when the artist has no links field."""
    db = get_db_connection()
    artist_id = db.Artists.insert_one({
        'name': 'No Links Artist',
        'description': '',
        'tags': ''
    }).inserted_id

    response = client.get(f'/artist/{artist_id}/edit')

    assert response.status_code == 200
    assert b'Edit Artist: No Links Artist' in response.data


def test_edit_detail_routes_return_404_for_missing_records(client):
    """Return 404 for missing directory records and edit forms."""
    missing_id = '507f1f77bcf86cd799439011'

    responses = [
        client.get(f'/artist/{missing_id}'),
        client.get(f'/artist/{missing_id}/edit'),
        client.get(f'/organiser/{missing_id}'),
        client.get(f'/organiser/{missing_id}/edit'),
        client.get(f'/venue/{missing_id}'),
        client.get(f'/venue/{missing_id}/edit')
    ]

    assert [response.status_code for response in responses] == [404, 404, 404, 404, 404, 404]


def test_organiser_and_venue_edits_are_queued_for_review(client):
    """Queue organiser and venue edits without mutating live records."""
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
    organiser_edit = db.tmp.find_one({
        'collection_name': 'Organisers',
        'target_id': organiser_id
    })
    venue_edit = db.tmp.find_one({
        'collection_name': 'venues',
        'target_id': venue_id
    })
    assert organiser_edit['payload'] == {
        'description': 'Organiser description',
        'contact': 'hello@example.com',
        'links': ['https://org.example', 'https://org.example/social']
    }
    assert venue_edit['payload'] == {
        'description': 'Venue description',
        'location': 'Brunswick',
        'contact': 'venue@example.com',
        'links': ['https://venue.example']
    }


def test_admin_review_page_lists_pending_edits_with_lookup_name(client):
    """Show queued edits on the admin review page using lookup names."""
    db = get_db_connection()
    db.tmp.insert_one({
        'collection_name': 'Organisers',
        'payload': {'description': 'Queued description'},
        'target_id': None,
        'lookup_name': 'Queued Org',
        'submitted_at': '2026-03-27T00:00:00'
    })
    login_admin(client)

    response = client.get('/admin/review_edits')
    html = response.data.decode()

    assert response.status_code == 200
    assert 'Queued Org' in html
    assert 'Organisers' in html
    assert 'Queued description' in html


def test_index_links_only_directory_entries_with_descriptions(client):
    """Link only described directory records from the public event list."""
    db = get_db_connection()
    artist_id = db.Artists.insert_one({
        'name': 'Linked Artist',
        'description': 'Has bio',
        'tags': '',
        'links': []
    }).inserted_id
    db.Artists.insert_one({'name': 'Plain Artist', 'description': '', 'tags': '', 'links': []})
    venue_id = db.venues.insert_one({
        'name': 'Linked Venue',
        'description': 'Has venue info',
        'location': '',
        'contact': '',
        'links': []
    }).inserted_id
    db.venues.insert_one({'name': 'Plain Venue', 'description': '',
                         'location': '', 'contact': '', 'links': []})
    organiser_id = db.Organisers.insert_one({
        'name': 'Linked Org',
        'description': 'Has org info',
        'contact': '',
        'links': []
    }).inserted_id
    insert_event(
        db,
        artists=['Linked Artist', 'Plain Artist'],
        venue='Linked Venue',
        organisers='Linked Org'
    )
    insert_event(
        db,
        title='Plain Directory Event',
        artists=['Plain Artist'],
        venue='Plain Venue',
        organisers='Plain Org'
    )

    response = client.get('/')
    html = response.data.decode()

    assert response.status_code == 200
    assert f'/artist/{artist_id}' in html
    assert f'/venue/{venue_id}' in html
    assert f'/organiser/{organiser_id}' in html
    assert html.count('/artist/') == 1
    assert html.count('/venue/') == 1
    assert html.count('/organiser/') == 1
    assert 'Plain Venue' in html
    assert 'Plain Org' in html


def test_past_events_only_lists_finished_events(client):
    """Show finished events on the past-events page but not future ones."""
    db = get_db_connection()
    insert_event(db, title='Future Event', start_datetime='2099-01-01T20:00',
                 end_datetime='2099-01-01T22:00')
    insert_event(db, title='Past Event', start_datetime='2020-01-01T20:00',
                 end_datetime='2020-01-01T22:00')

    response = client.get('/past')
    html = response.data.decode()

    assert response.status_code == 200
    assert 'Past Event' in html
    assert 'Future Event' not in html


def test_calendar_and_ics_routes_render_event_exports(client):
    """Render calendar helper HTML and ICS output for an event."""
    db = get_db_connection()
    event_id = insert_event(db, title='Calendar Event')

    calendar_response = client.get(f'/calendar/{event_id}')
    ics_response = client.get(f'/ics/{event_id}')

    assert calendar_response.status_code == 200
    assert b'Calendar Event' in calendar_response.data
    assert b'Add to Google Calendar' in calendar_response.data
    assert ics_response.status_code == 200
    assert ics_response.mimetype == 'text/calendar'
    assert b'SUMMARY:Calendar Event' in ics_response.data


def test_calendar_and_ics_return_404_for_missing_event(client):
    """Return 404 from calendar export routes for missing events."""
    missing_id = '507f1f77bcf86cd799439011'

    assert client.get(f'/calendar/{missing_id}').status_code == 404
    assert client.get(f'/ics/{missing_id}').status_code == 404


def test_clear_search_routes_redirect(client):
    """Redirect clear-search form submissions to the correct pages."""
    event_response = client.post('/clearEventSearch', data={'show_past': 'false'})
    past_response = client.post('/clearEventSearch', data={'show_past': 'true'})
    note_response = client.post('/clearNoteSearch')

    assert event_response.status_code == 302
    assert event_response.headers['Location'].endswith('/')
    assert past_response.status_code == 302
    assert past_response.headers['Location'].endswith('/past')
    assert note_response.status_code == 302
    assert note_response.headers['Location'].endswith('/notes')


def test_export_db_requires_admin(client):
    """Require admin login for database export downloads."""
    response = client.get('/admin/export_db')

    assert response.status_code == 403


def test_event_creation_does_not_duplicate_existing_directory_entries_case_insensitively(client):
    """Avoid duplicate directory entries during event creation."""
    db = get_db_connection()
    db.Artists.insert_one({'name': 'Sun Araw', 'description': '', 'tags': ''})
    db.Organisers.insert_one({'name': 'Org1', 'description': '', 'contact': '', 'links': []})
    db.venues.insert_one({'name': 'Venue1', 'description': '',
                         'location': '', 'contact': '', 'links': []})

    response = client.post('/createEvent', data={
        **EVENT_FORM,
        'organisers': ' org1 ',
        'venue': ' venue1 ',
        'artists': ' sun araw '
    }, follow_redirects=True)

    assert response.status_code == 200
    assert db.Artists.count_documents({'name': {'$regex': '^Sun Araw$', '$options': 'i'}}) == 1
    assert db.Organisers.count_documents({'name': {'$regex': '^Org1$', '$options': 'i'}}) == 1
    assert db.venues.count_documents({'name': {'$regex': '^Venue1$', '$options': 'i'}}) == 1
    assert db.tmp.count_documents({}) == 0
