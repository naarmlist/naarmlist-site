from flask import Flask, request, render_template, redirect, url_for, abort, Response, session, send_from_directory, send_file
from pymongo import MongoClient
from datetime import datetime, timedelta
import os
from bson.objectid import ObjectId  # Added for ObjectId conversion
import markdown
import json
import pytz

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # New: secret key for admin sessions

def get_db_connection():
    # Allow override for testing
    if hasattr(app, 'db_override') and app.db_override is not None:
        return app.db_override
    client = MongoClient(os.getenv("DB_URL"))
    db = client[os.getenv("DB_NAME")]
    return db
        
@app.route('/', methods=['GET', 'POST'])
def index():
    db = get_db_connection()
    search_query = ""
    # Use cutoff time of 6 hours past the finish time in Melbourne timezone
    # This is to ensure we only show events that are still going on or starting soon
    melbourne_tz = pytz.timezone("Australia/Melbourne")
    melbourne_now = datetime.now(melbourne_tz)
    cutofftime = melbourne_now - timedelta(hours=6)
    if request.method == 'POST':
        search_query = request.form['search']
        events = list(db.events.find({
            '$and': [
                {'end_datetime': {'$gte': cutofftime.isoformat()}},
                {'$or': [
                    {'title': {'$regex': search_query, '$options': 'i'}},
                    {'organisers': {'$regex': search_query, '$options': 'i'}},
                    {'venue': {'$regex': search_query, '$options': 'i'}},
                    {'tags': {'$regex': search_query, '$options': 'i'}},
                    {'artists': {'$regex': search_query, '$options': 'i'}}
                ]}
            ]
        }))
    else:
        events = list(db.events.find({'end_datetime': {'$gte': cutofftime.isoformat()}}))

    for event in events:
        event['start_datetime'] = datetime.fromisoformat(event['start_datetime'])
        event['end_datetime'] = datetime.fromisoformat(event['end_datetime'])
    events.sort(key=lambda x: x['start_datetime'])

    # --- ARTIST LINK LOGIC ---
    # Collect all unique artist names (case-insensitive, stripped)
    artist_names = set()
    for event in events:
        for artist in event.get('artists', []):
            artist_names.add(artist.strip().lower())
    # Fetch all artists from the DB (case-insensitive lookup in Python)
    artist_docs = list(db.Artists.find())
    # Build lookup dict (lowercase name -> artist doc)
    artist_lookup = {a['name'].strip().lower(): a for a in artist_docs}
    # For each event, build a new list for template
    for event in events:
        event['artist_links'] = []
        for artist in event.get('artists', []):
            key = artist.strip().lower()
            artist_doc = artist_lookup.get(key)
            if artist_doc and artist_doc.get('description', '').strip():
                event['artist_links'].append({'name': artist.strip(), 'id': str(artist_doc['_id'])})
            else:
                event['artist_links'].append({'name': artist.strip(), 'id': None})
    # --- END ARTIST LINK LOGIC ---

    return render_template('index.html', events=events, search_query=search_query, show_past=False, artists=artist_docs)

@app.route('/clearEventSearch', methods=['POST'])
def clear_event_search():
    show_past = request.form.get('show_past') == 'true'
    if show_past:
        return redirect(url_for('past_events'))
    return redirect(url_for('index'))

@app.route('/past', methods=['GET', 'POST'])
def past_events():
    db = get_db_connection()
    search_query = ""
    melbourne_tz = pytz.timezone("Australia/Melbourne")
    melbourne_now = datetime.now(melbourne_tz)
    cutofftime = melbourne_now - timedelta(hours=6)

    if request.method == 'POST':
        search_query = request.form['search']
        events = list(db.events.find({
            '$and': [
                {'end_datetime': {'$lt': cutofftime.isoformat()}},
                {'$or': [
                    {'title': {'$regex': search_query, '$options': 'i'}},
                    {'organisers': {'$regex': search_query, '$options': 'i'}},
                    {'venue': {'$regex': search_query, '$options': 'i'}},
                    {'tags': {'$regex': search_query, '$options': 'i'}},
                    {'artists': {'$regex': search_query, '$options': 'i'}}
                ]}
            ]
        }))
    else:
        events = list(db.events.find({'end_datetime': {'$lt': cutofftime.isoformat()}}))
    for event in events:
        event['start_datetime'] = datetime.fromisoformat(event['start_datetime'])
        event['end_datetime'] = datetime.fromisoformat(event['end_datetime'])
    events.sort(key=lambda x: x['start_datetime'], reverse=True)

    # --- ARTIST LINK LOGIC ---
    # Collect all unique artist names (case-insensitive, stripped)
    artist_names = set()
    for event in events:
        for artist in event.get('artists', []):
            artist_names.add(artist.strip().lower())
    # Fetch all artists from the DB (case-insensitive lookup in Python)
    artist_docs = list(db.Artists.find())
    # Build lookup dict (lowercase name -> artist doc)
    artist_lookup = {a['name'].strip().lower(): a for a in artist_docs}
    # For each event, build a new list for template
    for event in events:
        event['artist_links'] = []
        for artist in event.get('artists', []):
            key = artist.strip().lower()
            artist_doc = artist_lookup.get(key)
            if artist_doc and artist_doc.get('description', '').strip():
                event['artist_links'].append({'name': artist.strip(), 'id': str(artist_doc['_id'])})
            else:
                event['artist_links'].append({'name': artist.strip(), 'id': None})
    # --- END ARTIST LINK LOGIC ---

    return render_template('index.html', events=events, search_query=search_query, show_past=True)

@app.route('/createEvent', methods=['POST'])
def create_event():

    ## Validate the input data
    if not request.form['title'] or not request.form['start_datetime'] or not request.form['end_datetime']:
        return "Missing required fields", 400
    # check end datetime is after start datetime
    try:
        start_datetime = datetime.fromisoformat(request.form['start_datetime'])
        end_datetime = datetime.fromisoformat(request.form['end_datetime'])
        if end_datetime <= start_datetime:
            return "End datetime must be after start datetime", 400
    except ValueError:
        return "Invalid datetime format", 400
    
    title = request.form['title']
    organisers = request.form['organisers']
    venue = request.form['venue']
    link = request.form['link']
    start_datetime = request.form['start_datetime']
    end_datetime = request.form['end_datetime']
    tags = [t.strip() for t in request.form['tags'].split(',') if t.strip()]
    artists = [a.strip() for a in request.form['artists'].split(',') if a.strip()]

    db = get_db_connection()
    db.events.insert_one({
        'start_datetime': start_datetime,
        'end_datetime': end_datetime,
        'title': title,
        'organisers': organisers,
        'venue': venue,
        'link': link,
        'tags': tags,
        'artists': artists
    })

    # --- Artists Table Management ---
    for artist in artists:
        artist_clean = artist.strip()
        if not artist_clean:
            continue
        # Check if artist exists (case-insensitive, trimmed)
        existing = db.Artists.find_one({
            'name': {'$regex': f'^{artist_clean}$', '$options': 'i'}
        })
        if not existing:
            db.Artists.insert_one({
                'name': artist_clean,
                'description': '',
                'tags': ''
            })
    # --- End Artists Table Management ---

    return redirect(url_for('index'))

@app.route('/createVenue', methods=['POST'])
def create_venue():
    name = request.form['name']
    description = request.form['description']
    location = request.form['location']
    contact = request.form['contact']
    link = request.form['link']

    db = get_db_connection()
    db.venues.insert_one({
        'name': name,
        'description': description,
        'location': location,
        'contact': contact,
        'link': link
    })
    return redirect(url_for('venues'))

@app.route('/addEvent', methods=['GET'])
def add_event():
    return render_template('add_event.html')

@app.route('/venues', methods=['GET'])
def venues():
    db = get_db_connection()
    venues = db.venues.find()
    return render_template('venues.html', venues=venues)

@app.route('/organisers', methods=['GET'])
def organisers():
    db = get_db_connection()
    organisers = db.events.distinct('organisers')
    return render_template('organisers.html', organisers=organisers)

@app.route('/artists', methods=['GET'])
def artists():
    db = get_db_connection()
    # Fetch all artists, sort alphabetically (case-insensitive)
    artists = list(db.Artists.find())
    artists.sort(key=lambda x: x['name'].lower())
    return render_template('artists.html', artists=artists)

# New route to show calendar options.
@app.route('/calendar/<event_id>')
def calendar_event(event_id):
    db = get_db_connection()
    event = db.events.find_one({'_id': ObjectId(event_id)})
    if not event:
        abort(404)
    # Parse datetime and set Melbourne timezone
    start_dt = datetime.fromisoformat(event['start_datetime'])
    end_dt = datetime.fromisoformat(event['end_datetime'])

    # Format for Google Calendar (removing the Z suffix to prevent UTC interpretation)
    start_str = start_dt.strftime("%Y%m%dT%H%M%S")
    end_str = end_dt.strftime("%Y%m%dT%H%M%S")
    gcal_url = ("https://calendar.google.com/calendar/r/eventedit?text=" +
                f"{event['title']}&dates={start_str}/{end_str}&details={event['link']}&location={event['venue']}")
    # Render minimal HTML with options.
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Calendar Options for {event['title']}</title>
    </head>
    <body>
      <h2>{event['title']}</h2>
      <p>
        <a href="{gcal_url}" target="_blank">Add to Google Calendar</a>
      </p>
      <p>
        <a href="{url_for('ics_file', event_id=event_id)}" target="_blank">Download ICS to use in iCalendar</a>
      </p>
    </body>
    </html>
    """

# New route to generate ICS file.
@app.route('/ics/<event_id>')
def ics_file(event_id):
    db = get_db_connection()
    event = db.events.find_one({'_id': ObjectId(event_id)})
    if not event:
        abort(404)
    start_dt = datetime.fromisoformat(event['start_datetime'])
    end_dt = datetime.fromisoformat(event['end_datetime'])
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:NaarmList
BEGIN:VEVENT
UID:{event_id}@naarm-list
DTSTAMP:{dtstamp}
DTSTART:{start_dt.strftime("%Y%m%dT%H%M%SZ")}
DTEND:{end_dt.strftime("%Y%m%dT%H%M%SZ")}
SUMMARY:{event['title']}
DESCRIPTION:{event['link']}
LOCATION:{event['venue']}
END:VEVENT
END:VCALENDAR
"""
    return Response(ics_content, mimetype="text/calendar", headers={"Content-Disposition": f"attachment; filename={event['title']}.ics"})

@app.route('/notes', methods=['GET', 'POST'])
def notes():
    notes_dir = os.path.join(os.path.dirname(__file__), 'notes')
    search_query = ""
    notes = []
    
    if request.method == 'POST' and 'search' in request.form:
        search_query = request.form['search']
    
    if os.path.exists(notes_dir):
        for filename in os.listdir(notes_dir):
            if filename.endswith('.md'):
                filepath = os.path.join(notes_dir, filename)
                with open(filepath, 'r') as f:
                    content = f.read()
                    # Parse front matter
                    metadata = {}
                    if content.startswith('---'):
                        parts = content.split('---', 2)[1:]
                        if len(parts) >= 2:
                            front_matter = parts[0].strip()
                            content = parts[1].strip()
                            # Parse each line of front matter
                            for line in front_matter.split('\n'):
                                if ':' in line:
                                    key, value = line.split(':', 1)
                                    metadata[key.strip()] = value.strip()
                    
                    # Convert date string to datetime if present
                    if 'date' in metadata:
                        try:
                            metadata['date'] = datetime.strptime(metadata['date'], '%Y-%m-%d')
                        except ValueError:
                            metadata['date'] = datetime.now()
                    else:
                        metadata['date'] = datetime.now()

                    # Convert tags string to list if present
                    if 'tags' in metadata:
                        metadata['tags'] = [tag.strip() for tag in metadata['tags'].split(',')]
                    else:
                        metadata['tags'] = []

                    # Apply search filter only if there's a query from POST
                    if search_query:
                        title_match = metadata.get('title', '').lower().find(search_query.lower()) != -1
                        tags_match = any(search_query.lower() in tag.lower() for tag in metadata.get('tags', []))
                        content_match = content.lower().find(search_query.lower()) != -1
                        if not (title_match or tags_match or content_match):
                            continue

                    html_content = markdown.markdown(content)
                    notes.append({
                        'filename': filename,
                        'content': html_content,
                        'metadata': metadata
                    })

    # Sort notes by date, newest first
    notes.sort(key=lambda x: x['metadata']['date'], reverse=True)
    has_results = len(notes) > 0
    return render_template('notes.html', 
                         notes=notes, 
                         search_query=search_query, 
                         has_results=has_results)

@app.route('/clearNoteSearch', methods=['POST'])
def clear_note_search():
    return redirect(url_for('notes'))

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == os.getenv("ADMIN_USER") and password == os.getenv("ADMIN_PASS"):
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid credentials"
            return render_template('admin_login.html', error=error)
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    db = get_db_connection()
    events = list(db.events.find())
    for event in events:
        event['start_datetime'] = datetime.fromisoformat(event['start_datetime'])
        event['end_datetime'] = datetime.fromisoformat(event['end_datetime'])
    events.sort(key=lambda x: x['start_datetime'])
    return render_template('admin_dashboard.html', events=events)

@app.route('/admin/delete/<event_id>', methods=['POST'])
def admin_delete(event_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    db = get_db_connection()
    db.events.delete_one({'_id': ObjectId(event_id)})
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit/<event_id>', methods=['GET', 'POST'])
def admin_edit(event_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    db = get_db_connection()
    if request.method == 'POST':
        updated_fields = {
            'title': request.form['title'],
            'organisers': request.form['organisers'],
            'venue': request.form['venue'],
            'link': request.form['link'],
            'start_datetime': request.form['start_datetime'],
            'end_datetime': request.form['end_datetime'],
            'tags': [tag.strip() for tag in request.form['tags'].split(',') if tag.strip()],
            'artists': [artist.strip() for artist in request.form['artists'].split(',') if artist.strip()]
        }
        db.events.update_one({'_id': ObjectId(event_id)}, {'$set': updated_fields}, upsert=True)
        # --- Artists Table Management for update ---
        for artist in updated_fields['artists']:
            artist_clean = artist.strip()
            if not artist_clean:
                continue
            existing = db.Artists.find_one({
                'name': {'$regex': f'^{artist_clean}$', '$options': 'i'}
            })
            if not existing:
                db.Artists.insert_one({
                    'name': artist_clean,
                    'description': '',
                    'tags': '',
                    'links': []
                })
        # --- End Artists Table Management ---
        return redirect(url_for('admin_dashboard'))
    else:
        event = db.events.find_one({'_id': ObjectId(event_id)})
        if not event:
            abort(404)
        return render_template('admin_edit.html', event=event)

def export_database():
    db = get_db_connection()
    export_data = {
        'events': list(db.events.find()),
        'venues': list(db.venues.find()),
    }
    
    for collection in export_data.values():
        for doc in collection:
            doc['_id'] = str(doc['_id'])
    
    # Create exports directory if it doesn't exist
    exports_dir = os.path.join(os.path.dirname(__file__), 'exports')
    if not os.path.exists(exports_dir):
        os.makedirs(exports_dir)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(exports_dir, f'db_backup_{timestamp}.json')
    
    with open(filename, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)
    
    return filename

@app.route('/admin/export_db')
def admin_export_db():
    if not session.get('admin'):
        abort(403)
    try:
        filename = export_database()
        return send_file(
            filename,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'naarm_list_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
    except Exception as e:
        return f"Export failed: {str(e)}", 500

@app.route('/admin/logout')
def admin_logout():
    session['admin'] = False
    return redirect(url_for('index'))

@app.route('/robots.txt')
def robots():
    return send_from_directory(os.path.dirname(__file__), 'robots.txt')

@app.route('/artist/<artist_id>')
def artist_detail(artist_id):
    db = get_db_connection()
    artist = db.Artists.find_one({'_id': ObjectId(artist_id)})
    if not artist:
        abort(404)
    return render_template('artist_detail.html', artist=artist)

@app.route('/artist/<artist_id>/edit', methods=['GET', 'POST'])
def edit_artist(artist_id):
    db = get_db_connection()
    artist = db.Artists.find_one({'_id': ObjectId(artist_id)})
    if not artist:
        abort(404)
    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        # Gather all non-blank links from the form
        links = [l.strip() for l in request.form.getlist('links') if l.strip()]
        update_fields = {'description': description}
        if links:
            update_fields['links'] = links
        else:
            update_fields['links'] = []
        db.Artists.update_one({'_id': ObjectId(artist_id)}, {'$set': update_fields})
        return redirect(url_for('artist_detail', artist_id=artist_id))
    # Ensure links field exists for rendering
    if 'links' not in artist:
        artist['links'] = []
    return render_template('edit_artist.html', artist=artist)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
