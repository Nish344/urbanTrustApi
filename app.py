# app.py
from flask import Flask, request, jsonify
import os
import numpy as np
from PIL import Image
import io
import base64
import uuid
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import math

# Import helper modules
from text_processor import process_text
# Add an admin key for authentication
ADMIN_KEY = os.getenv('ADMIN_KEY', 'default_admin_key')  # Replace with a secure key

app = Flask(_name_)

# Initialize Firebase
def initialize_firebase():
    # You need to download your Firebase service account key from Firebase console
    # and save it as 'serviceAccountKey.json' in your project directory
    cred = credentials.Certificate('serviceAccountKey.json')
    firebase_admin.initialize_app(cred)
    db = firestore.client()
    return db

# Initialize models
def initialize_models():
    # Only keeping the text model as requested
    from transformers import BertTokenizer, BertModel
    
    # Text classification model (BERT)
    text_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    text_model = BertModel.from_pretrained('bert-base-uncased')
    text_model.eval()
    
    return {
        'text_model': text_model,
        'text_tokenizer': text_tokenizer
    }

# Haversine formula to calculate distance between two GPS coordinates
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)*2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)*2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c  # Distance in meters

# Store issue in Firestore
def store_issue(issue_data, text_embedding, category):
    db = app.config['db']
    
    issue_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    # Convert numpy embedding to base64 for storage
    text_embedding_base64 = base64.b64encode(text_embedding.tobytes()).decode('utf-8')
    
    # Check for nearby similar issues
    nearby_issues = find_nearby_issues(issue_data['latitude'], issue_data['longitude'], radius=50)
    similar_issues = []
    
    # Get ward ID from coordinates
    _, ward_id = search_ward_by_coordinates_firestore(issue_data['longitude'], issue_data['latitude'])

    # Count similar issues in the vicinity
    for issue in nearby_issues:
        if issue['category'] == category:
            similar_issues.append(issue)
    
    similar_count = len(similar_issues)

    # Store issue in Firestore
    issue_ref = db.collection('issues').document(issue_id)
    issue_ref.set({
        'latitude': issue_data['latitude'],
        'longitude': issue_data['longitude'],
        'category': category,
        'description': issue_data.get('description', ''),
        'status': 'open',
        'created_at': created_at,
        'image': issue_data.get('image', ''),
        'text_embedding': text_embedding_base64,
        'similar_count': similar_count,
        'ward_id': ward_id
    })
    
    return issue_id

# Find nearby issues using Firestore
def find_nearby_issues(latitude, longitude, radius=100):
    db = app.config['db']
    
    # Get all issues (Firestore doesn't support geospatial queries natively)
    issues_ref = db.collection('issues')
    issues = issues_ref.stream()
    
    nearby_issues = []
    for issue in issues:
        issue_data = issue.to_dict()
        issue_id = issue.id
        
        issue_lat = issue_data.get('latitude')
        issue_lon = issue_data.get('longitude')
        
        if issue_lat is None or issue_lon is None:
            continue
        
        # Calculate distance
        distance = haversine_distance(latitude, longitude, issue_lat, issue_lon)
        
        # Check if within radius
        if distance <= radius:
            nearby_issues.append({
                'issue_id': issue_id,
                'location': {'lat': issue_lat, 'lon': issue_lon},
                'category': issue_data.get('category'),
                'description': issue_data.get('description'),
                'status': issue_data.get('status'),
                'distance': distance
            })
    
    return nearby_issues

# Check for duplicate issues
@app.route('/check-duplicate', methods=['POST'])
def check_duplicate():
    data = request.json
    
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    category = data.get('category')
    
    # Find nearby issues
    nearby_issues = find_nearby_issues(latitude, longitude)
    
    # No nearby issues
    if not nearby_issues:
        return jsonify({
            'duplicate_found': False,
            'similar_issues': []
        })
    
    # Check for similar issues with the same category
    similar_issues = []
    for issue in nearby_issues:
        if issue['category'] == category:
            similar_issues.append(issue)
    
    return jsonify({
        'duplicate_found': len(similar_issues) > 0,
        'similar_issues': similar_issues
    })

# Report an issue endpoint
@app.route('/report-issue', methods=['POST'])
def report_issue():
    data = request.json
    
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    category = data.get('category')
    description = data.get('description', '')
    image_data = data.get('image')
    
    models = app.config['models']
    
    # Process text to get embedding
    text_result = process_text(description, models)
    
    # Process image for storage
    image_base64 = process_image_for_storage(image_data) if image_data else None
    
    # Store the issue
    issue_data = {
        'latitude': latitude, 
        'longitude': longitude, 
        'category': category, 
        'description': description,
        'image': image_base64
    }
    
    issue_id = store_issue(issue_data, text_result['embedding'], category)
    
    return jsonify({
        'success': True,
        'issue_id': issue_id,
        'message': 'Issue reported successfully'
    })

# Get nearby issues
@app.route('/issues-nearby', methods=['GET'])
def issues_nearby():
    latitude = float(request.args.get('latitude'))
    longitude = float(request.args.get('longitude'))
    radius = float(request.args.get('radius', 500))  # Default 500m
    
    nearby_issues = find_nearby_issues(latitude, longitude, radius)
    
    return jsonify({
        'issues': nearby_issues
    })

# Get issue details
@app.route('/issue/<issue_id>', methods=['GET'])
def get_issue(issue_id):
    db = app.config['db']
    
    issue_ref = db.collection('issues').document(issue_id)
    issue = issue_ref.get()
    
    if not issue.exists:
        return jsonify({
            'success': False,
            'message': 'Issue not found'
        }), 404
    
    issue_data = issue.to_dict()
    
    return jsonify({
        'success': True,
        'issue': {
            'id': issue_id,
            'location': {'lat': issue_data.get('latitude'), 'lon': issue_data.get('longitude')},
            'category': issue_data.get('category'),
            'description': issue_data.get('description'),
            'status': issue_data.get('status'),
            'created_at': issue_data.get('created_at'),
            'similar_count': issue_data.get('similar_count', 0)
        }
    })

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

# Initialize the Flask app
def initialize_app(app):
    # Initialize Firebase
    db = initialize_firebase()
    app.config['db'] = db
    
    # Load models
    app.config['models'] = initialize_models()
    
    return app

# Initialize the app
app = initialize_app(app)

if _name_ == '_main_':
    app.run(debug=True)
