"""Database safety regression tests for public edits and admin review."""


def test_reviewer_cannot_apply_payload_with_unapproved_field(client, db, login_admin):
    """Reject review payloads that include fields outside the collection allowlist."""
    artist_id = db.Artists.insert_one(
        {'name': 'Safe Artist', 'description': '', 'tags': ''}).inserted_id
    pending_id = db.tmp.insert_one({
        'collection_name': 'Artists',
        'payload': {'description': 'Fine', 'admin': True},
        'target_id': artist_id,
        'lookup_name': 'Safe Artist',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id
    login_admin()

    response = client.post(f'/admin/review_edits/{pending_id}/approve')

    assert response.status_code == 400
    artist = db.Artists.find_one({'_id': artist_id})
    assert artist['description'] == ''
    assert 'admin' not in artist
    assert db.tmp.find_one({'_id': pending_id}) is not None


def test_reviewer_cannot_apply_payload_with_dotted_or_operator_field(client, db, login_admin):
    """Reject payload keys that could mutate nested fields or operators."""
    artist_id = db.Artists.insert_one(
        {'name': 'Safe Artist', 'description': '', 'tags': ''}).inserted_id
    dotted_id = db.tmp.insert_one({
        'collection_name': 'Artists',
        'payload': {'profile.url': 'https://bad.example'},
        'target_id': artist_id,
        'lookup_name': 'Safe Artist',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id
    operator_id = db.tmp.insert_one({
        'collection_name': 'Artists',
        'payload': {'$rename': {'name': 'Bad'}},
        'target_id': artist_id,
        'lookup_name': 'Safe Artist',
        'submitted_at': '2026-03-27T00:00:01'
    }).inserted_id
    login_admin()

    dotted_response = client.post(f'/admin/review_edits/{dotted_id}/approve')
    operator_response = client.post(f'/admin/review_edits/{operator_id}/approve')

    assert dotted_response.status_code == 400
    assert operator_response.status_code == 400
    artist = db.Artists.find_one({'_id': artist_id})
    assert artist['name'] == 'Safe Artist'
    assert 'profile' not in artist


def test_reviewer_cannot_apply_empty_payload(client, db, login_admin):
    """Reject empty review payloads instead of inserting empty records."""
    pending_id = db.tmp.insert_one({
        'collection_name': 'Artists',
        'payload': {},
        'target_id': None,
        'lookup_name': 'Empty Artist',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id
    login_admin()

    response = client.post(f'/admin/review_edits/{pending_id}/approve')

    assert response.status_code == 400
    assert db.Artists.find_one({'name': 'Empty Artist'}) is None
    assert db.tmp.find_one({'_id': pending_id}) is not None


def test_reviewer_cannot_upsert_missing_target_into_partial_record(client, db, login_admin):
    """Reject target edits when the destination document no longer exists."""
    pending_id = db.tmp.insert_one({
        'collection_name': 'Artists',
        'payload': {'description': 'Orphaned edit'},
        'target_id': '507f1f77bcf86cd799439011',
        'lookup_name': 'Missing Artist',
        'submitted_at': '2026-03-27T00:00:00'
    }).inserted_id
    login_admin()

    response = client.post(f'/admin/review_edits/{pending_id}/approve')

    assert response.status_code == 404
    assert db.Artists.find_one({'description': 'Orphaned edit'}) is None
    assert db.tmp.find_one({'_id': pending_id}) is not None


def test_public_edit_queue_uses_only_expected_payload_shape(client, db):
    """Queue public edits using a stable, reviewable document shape."""
    artist_id = db.Artists.insert_one(
        {'name': 'Artist', 'description': '', 'tags': ''}).inserted_id
    organiser_id = db.Organisers.insert_one(
        {'name': 'Org', 'description': '', 'contact': '', 'links': []}).inserted_id
    venue_id = db.venues.insert_one({
        'name': 'Venue',
        'description': '',
        'location': '',
        'contact': '',
        'links': [],
    }).inserted_id

    client.post(f'/artist/{artist_id}/edit',
                data={'description': 'Artist edit', 'links': 'https://artist.example'})
    client.post(f'/organiser/{organiser_id}/edit', data={
        'description': 'Org edit',
        'contact': 'org@example.com',
        'links': 'https://org.example'
    })
    client.post(f'/venue/{venue_id}/edit', data={
        'description': 'Venue edit',
        'location': 'Carlton',
        'contact': 'venue@example.com',
        'links': 'https://venue.example'
    })

    queued_edits = list(db.tmp.find())
    assert {edit['collection_name']
            for edit in queued_edits} == {'Artists', 'Organisers', 'venues'}
    for edit in queued_edits:
        assert '_id' in edit
        assert set(edit) == {'_id', 'collection_name', 'payload',
                             'target_id', 'lookup_name', 'submitted_at'}


def test_read_only_routes_do_not_mutate_seeded_dummy_data(client, db, insert_event):
    """Seed dummy data and verify read-only routes leave collections untouched."""
    artist_id = db.Artists.insert_one({
        'name': 'Seed Artist',
        'description': 'Seed bio',
        'tags': '',
        'links': ['https://artist.example'],
    }).inserted_id
    organiser_id = db.Organisers.insert_one({
        'name': 'Seed Org',
        'description': 'Seed org',
        'contact': 'org@example.com',
        'links': ['https://org.example'],
    }).inserted_id
    venue_id = db.venues.insert_one({
        'name': 'Seed Venue',
        'description': 'Seed venue',
        'location': 'Brunswick',
        'contact': 'venue@example.com',
        'links': ['https://venue.example'],
    }).inserted_id
    event_id = insert_event(
        title='Seed Event',
        artists=['Seed Artist'],
        organisers='Seed Org',
        venue='Seed Venue',
    )
    before = {
        'events': list(db.events.find()),
        'artists': list(db.Artists.find()),
        'organisers': list(db.Organisers.find()),
        'venues': list(db.venues.find()),
        'tmp_count': db.tmp.count_documents({}),
    }

    responses = [
        client.get('/'),
        client.post('/', data={'search': 'Seed'}),
        client.get('/past'),
        client.get('/artists'),
        client.get(f'/artist/{artist_id}'),
        client.get('/organisers'),
        client.get(f'/organiser/{organiser_id}'),
        client.get('/venues'),
        client.get(f'/venue/{venue_id}'),
        client.get('/notes'),
        client.get(f'/calendar/{event_id}'),
        client.get(f'/ics/{event_id}'),
    ]

    assert all(response.status_code == 200 for response in responses)
    assert list(db.events.find()) == before['events']
    assert list(db.Artists.find()) == before['artists']
    assert list(db.Organisers.find()) == before['organisers']
    assert list(db.venues.find()) == before['venues']
    assert db.tmp.count_documents({}) == before['tmp_count']
