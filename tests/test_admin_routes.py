"""Admin route tests for event management, export, and review pages."""


def test_admin_events_lists_events_in_start_order(client, db, login_admin, insert_event):
    """Render admin events ordered by start time."""
    later_id = insert_event(title='Later Event', start_datetime='2099-08-02T20:00')
    earlier_id = insert_event(title='Earlier Event', start_datetime='2099-08-01T20:00')
    login_admin()

    response = client.get('/admin/events')
    html = response.data.decode()

    assert response.status_code == 200
    assert html.index('Earlier Event') < html.index('Later Event')
    assert str(earlier_id) in html
    assert str(later_id) in html


def test_admin_edit_missing_event_returns_404(client, login_admin):
    """Return 404 when an admin tries to edit a missing event."""
    login_admin()

    response = client.get('/admin/edit/507f1f77bcf86cd799439011')

    assert response.status_code == 404


def test_admin_edit_page_prefills_event(client, db, login_admin, insert_event):
    """Pre-fill the admin event edit form from the event document."""
    event_id = insert_event(title='Editable Event', artists=['Artist A', 'Artist B'])
    login_admin()

    response = client.get(f'/admin/edit/{event_id}')

    assert response.status_code == 200
    assert b'Editable Event' in response.data
    assert b'Artist A,Artist B' in response.data


def test_admin_export_writes_all_collections(monkeypatch, client, db, login_admin, insert_event):
    """Write all live and review collections into the DB export file."""
    from app import export_database
    import json

    insert_event(title='Exported Event')
    db.Artists.insert_one({'name': 'Exported Artist', 'description': '', 'tags': ''})
    db.venues.insert_one({'name': 'Exported Venue', 'description': '',
                         'location': '', 'contact': '', 'links': []})
    db.Organisers.insert_one(
        {'name': 'Exported Org', 'description': '', 'contact': '', 'links': []})
    db.tmp.insert_one({
        'collection_name': 'Artists',
        'payload': {'description': 'Queued'},
        'target_id': None,
        'lookup_name': 'Exported Artist',
        'submitted_at': '2026-03-27T00:00:00'
    })
    login_admin()

    filename = export_database()

    with open(filename, 'r') as exported_file:
        exported = json.load(exported_file)
    assert exported['events'][0]['title'] == 'Exported Event'
    assert exported['artists'][0]['name'] == 'Exported Artist'
    assert exported['venues'][0]['name'] == 'Exported Venue'
    assert exported['organisers'][0]['name'] == 'Exported Org'
    assert exported['tmp'][0]['lookup_name'] == 'Exported Artist'


def test_admin_export_route_returns_download(client, db, login_admin, insert_event):
    """Return the exported database as an attachment for admins."""
    insert_event(title='Download Event')
    login_admin()

    response = client.get('/admin/export_db')

    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert 'attachment' in response.headers['Content-Disposition']
