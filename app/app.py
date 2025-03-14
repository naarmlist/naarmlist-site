from flask import Flask, request, render_template, redirect, url_for
from pymongo import MongoClient
from datetime import datetime
import pytz

app = Flask(__name__)

def get_db_connection():
    client = MongoClient('mongodb://db:27017/')
    db = client['gigsdb']
    return db

@app.route('/', methods=['GET', 'POST'])
def index():
    db = get_db_connection()
    search_query = ""
    if request.method == 'POST':
        search_query = request.form['search']
        events = list(db.events.find({
            '$or': [
                {'title': {'$regex': search_query, '$options': 'i'}},
                {'organisers': {'$regex': search_query, '$options': 'i'}},
                {'venue': {'$regex': search_query, '$options': 'i'}},
                {'tags': {'$regex': search_query, '$options': 'i'}}
            ]
        }))
    else:
        events = list(db.events.find())
    
    for event in events:
        event['datetime'] = datetime.fromisoformat(event['datetime'])
    events.sort(key=lambda x: x['datetime'])
    return render_template('index.html', events=events, search_query=search_query)

@app.route('/clearSearch', methods=['POST'])
def clear_search():
    return redirect(url_for('index'))

@app.route('/createEvent', methods=['POST'])
def create_event():
    title = request.form['title']
    organisers = request.form['organisers']
    venue = request.form['venue']
    link = request.form['link']
    datetime_str = request.form['datetime']
    tags = request.form['tags'].split(',')

    db = get_db_connection()
    db.events.insert_one({
        'datetime': datetime_str,
        'title': title,
        'organisers': organisers,
        'venue': venue,
        'link': link,
        'tags': tags
    })

    return redirect(url_for('index'))

@app.route('/addEvent', methods=['GET'])
def add_event():
    return render_template('add_event.html')

@app.route('/venues', methods=['GET'])
def venues():
    db = get_db_connection()
    venues = db.events.distinct('venue')
    return render_template('venues.html', venues=venues)

@app.route('/organisers', methods=['GET'])
def organisers():
    db = get_db_connection()
    organisers = db.events.distinct('organisers')
    return render_template('organisers.html', organisers=organisers)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
