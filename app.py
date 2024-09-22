from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime, timedelta
app = Flask(__name__)

# MongoDB setup
client = MongoClient('mongodb://localhost:27017/')
db = client['webhookDB']
events_collection = db['events']

@app.route('/')
def api_root():
    return render_template('index.html')


@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.json
    if not data:
        return jsonify({"error": "No data received"}), 400

    # Identify the event_type from GitHub headers
    event_type = request.headers.get('X-GitHub-Event')

    event_data = {
        "event_type": event_type,
        "timestamp": datetime.utcnow()
    }

    # Handling Push Event
    if event_type == "push":
        event_data.update({
            "request_id": data.get('head_commit', {}).get('id'),  # request id as git commit hash
            "author": data.get('pusher', {}).get('name'),
            "action": "PUSH",
            "to_branch": data.get('ref').split('/')[-1],  # Extracting branch name from ref
            "timestamp": datetime.utcnow()
        })
    elif event_type == "pull_request":
        event_data.update({
            "request_id": str(data.get('pull_request', {}).get('id')),  # request_id as PR ID
            "author": data.get('sender', {}).get('login'),
            "action": "PULL_REQUEST",
            "from_branch": data.get('pull_request', {}).get('head', {}).get('ref'),
            "to_branch": data.get('pull_request', {}).get('base', {}).get('ref'),
            "timestamp": datetime.utcnow()
        })

        # Check if the pull request is merged
        if data.get('action') == "closed" and data.get('pull_request', {}).get('merged'):
            event_data.update({
                "action": "MERGE",
                "from_branch": data.get('pull_request', {}).get('head', {}).get('ref'),
                "to_branch": data.get('pull_request', {}).get('base', {}).get('ref'),
                "timestamp": datetime.utcnow()
            })
    # Insert the action data into the MongoDB collection
    events_collection.insert_one(event_data)

    return jsonify({"status": "success"}), 200

# API endpoint to fetch actions from db to UI
@app.route('/events', methods=['GET'])
def get_events():
    events = list(events_collection.find().sort("timestamp", -1).limit(10))
    
    formatted_events = []
    for event in events:
        timestamp = event['timestamp'].strftime('%d %B %Y - %I:%M %p UTC')
        action = event.get('action') 
        
        if action == 'PUSH':
            formatted_events.append(f"{event['author']} pushed to {event['to_branch']} on {timestamp}")
        elif action == 'PULL_REQUEST':
            formatted_events.append(f"{event['author']} submitted a pull request from {event['from_branch']} to {event['to_branch']} on {timestamp}")
        elif action == 'MERGE':
            formatted_events.append(f"{event['author']} merged branch {event['from_branch']} to {event['to_branch']} on {timestamp}")
        else:
            formatted_events.append(f"Unknown action for event by {event['author']} on {timestamp}")

    return jsonify(formatted_events), 200

if __name__ == '__main__':
    app.run(debug=True)



