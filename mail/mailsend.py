import os
import boto3
from datetime import datetime, timedelta
from pymongo import MongoClient
from base64 import b64encode
from botocore.exceptions import ClientError
import pytz

def get_db_connection():
    client = MongoClient(os.environ["DB_URL"])
    db = client[os.environ["DB_NAME"]]
    return db

def create_email_body(events, search_terms, email):
    email_token = b64encode(email.encode()).decode()
    
    body = f"""
    <h2>Your Weekly Event Updates</h2>
    <p>Here are the upcoming events matching your search terms: {', '.join(search_terms)}</p>
    <ul>
    """
    
    for event in events:
        start_dt = datetime.fromisoformat(event['start_datetime'])
        body += f"""
        <li>
            <strong>{event['title']}</strong><br>
            {start_dt.strftime('%A %B %d at %I:%M %p')}<br>
            Venue: {event['venue']}<br>
            <a href="{event['link']}">Event Link</a>
        </li>
        """
    
    body += f"""
    </ul>
    <p>
        <a href="https://your-domain.com/manage_subscription/{email_token}">Manage your subscription</a><br>
        <a href="https://your-domain.com/unsubscribe/{email_token}">Unsubscribe</a>
    </p>
    """
    
    return body

def lambda_handler(event, context):
    db = get_db_connection()
    ses = boto3.client('ses', region_name=os.environ["AWS_REGION"])
    
    # Get all subscribers
    subscribers = db.subscribers.find()
    
    melbourne_tz = pytz.timezone("Australia/Melbourne")
    melbourne_now = datetime.now(melbourne_tz)
    
    for subscriber in subscribers:
        # Find matching events for this subscriber
        query = {
            'start_datetime': {'$gte': melbourne_now.isoformat()},
            '$or': []
        }
        
        # Add search conditions for each term
        for term in subscriber['search_terms']:
            query['$or'].extend([
                {'title': {'$regex': term, '$options': 'i'}},
                {'venue': {'$regex': term, '$options': 'i'}},
                {'tags': {'$regex': term, '$options': 'i'}},
                {'artists': {'$regex': term, '$options': 'i'}}
            ])
        
        matching_events = set(db.events.find(query))
        
        if not matching_events:
            continue
        
        # Create email content
        email_body = create_email_body(
            matching_events, 
            subscriber['search_terms'],
            subscriber['email']
        )
        
        try:
            response = ses.send_email(
                Source=os.environ["FROM_EMAIL"],
                Destination={'ToAddresses': [subscriber['email']]},
                Message={
                    'Subject': {
                        'Data': 'Your Weekly Event Updates'
                    },
                    'Body': {
                        'Html': {
                            'Data': email_body
                        }
                    }
                }
            )
            print(f"Email sent to {subscriber['email']}: {response['MessageId']}")
            print(f"Response: {response}")
        except ClientError as e:
            print(f"Error sending to {subscriber['email']}: {e.response['Error']['Message']}")
            continue
    
    return {
        'statusCode': 200,
        'body': 'Weekly emails sent successfully'
    }
