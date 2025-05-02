# app.py
from flask import Flask, Response, request, jsonify
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
import logging

from image_process import verify_image_matches_description, describe_image
from translate import translate_to_kannada
from notifications import WardNotificationSystem  # Import the updated notification system


# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Add an admin key for authentication
ADMIN_KEY = os.getenv('ADMIN_KEY', 'default_admin_key')  # Replace with a secure key


def process_image_for_storage(image_data):
    """
    Compress, resize and validate image data before storing in Firestore
    """
    try:
        if image_data and image_data.startswith('data:image'):
            image_base64 = image_data.split(',')[1]
        else:
            image_base64 = image_data

        image_bytes = base64.b64decode(image_base64)
        img = Image.open(io.BytesIO(image_bytes))

        # Resize image (e.g., max 800x800)
        img.thumbnail((800, 800))

        # Strip metadata and convert to JPEG
        img_no_metadata = Image.new(img.mode, img.size)
        img_no_metadata.putdata(list(img.getdata()))

        # Save with compression
        buffered = io.BytesIO()
        img_no_metadata = img_no_metadata.convert("RGB")
        img_no_metadata.save(buffered, format='JPEG', quality=70)

        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return None


# Haversine formula to calculate distance between two GPS coordinates
def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c  # Distance in meters

# Initialize Firebase
def initialize_firebase():
    try:
        # You need to download your Firebase service account key from Firebase console
        # and save it as 'serviceAccountKey.json' in your project directory
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("Firebase initialized successfully")
        return db
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {str(e)}")
        # For development purposes, you might want to continue without Firebase
        return None

# Initialize models
def initialize_models():
    try:
        # Only keeping the text model as requested
        from transformers import BertTokenizer, BertModel
        
        # Text classification model (BERT)
        text_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        text_model = BertModel.from_pretrained('bert-base-uncased')
        text_model.eval()
        
        logger.info("Models initialized successfully")
        return {
            'text_model': text_model,
            'text_tokenizer': text_tokenizer
        }
    except ImportError as e:
        logger.warning(f"Could not import transformers: {str(e)}")
        logger.warning("Running without BERT models")
        return {}
    except Exception as e:
        logger.error(f"Error initializing models: {str(e)}")
        return {}

def search_ward_by_coordinates_firestore(longitude, latitude):
    """
    Find which ward contains the given coordinates
    Returns (ward_name, ward_id)
    """
    try:
        db = app.config['db']
        if not db:
            return "Unknown Ward", "unknown"
            
        # In a real implementation, this would query a geospatial index
        # For simplicity, we'll return a placeholder
        return "Sample Ward", "ward_001"
    except Exception as e:
        logger.error(f"Error searching ward: {str(e)}")
        return "Unknown Ward", "unknown"

# Store issue in Firestore
def store_issue(issue_data, category):
    try:
        db = app.config['db']
        if not db:
            # For development without Firebase, store locally and return a UUID
            issue_id = str(uuid.uuid4())
            logger.info(f"Firebase not available, generated issue ID: {issue_id}")
            return issue_id
        
        issue_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        
        # Convert numpy embedding to base64 for storage
        
        # Check for nearby similar issues
        nearby_issues = find_nearby_issues(issue_data['latitude'], issue_data['longitude'], radius=50)
        similar_issues = []
        
        # No need to get ward ID here, since we'll determine it in the notification process
        
        # Count similar issues in the vicinity
        for issue in nearby_issues:
            if issue.get('category') == category:
                similar_issues.append(issue)
        
        similar_count = len(similar_issues)

        # Store issue in Firestore with ward_assigned defaulted to false
        issue_ref = db.collection('issues').document(issue_id)
        issue_ref.set({
            'latitude': issue_data['latitude'],
            'longitude': issue_data['longitude'],
            'category': issue_data.get('category'),
            'category_kannada': issue_data.get('category_kannada', ''),
            'description': issue_data.get('description', ''),
            'description_kannada': issue_data.get('description_kannada', ''),
            'user_id': issue_data.get('user_id', ''),
            'status': 'open',
            'created_at': created_at,
            'image': issue_data.get('image', ''),
            'similar_count': similar_count,
            'ward_assigned': False,  # Default to false until determined by notification system
            'notification_sent': False  # Default to false
        })
        
        logger.info(f"Issue stored with ID: {issue_id}")
        return issue_id
    except Exception as e:
        logger.error(f"Error storing issue: {str(e)}")
        # Return a UUID even if storing fails
        return str(uuid.uuid4())

# Find nearby issues using Firestore
def find_nearby_issues(latitude, longitude, radius=100):
    try:
        db = app.config['db']
        if not db:
            # For development without Firebase
            logger.info("Firebase not available, returning empty nearby issues")
            return []
        
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
    except Exception as e:
        logger.error(f"Error finding nearby issues: {str(e)}")
        return []

# Check for duplicate issues
@app.route('/check-duplicate', methods=['POST'])
def check_duplicate():
    try:
        data = request.json
        
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        category = data.get('category')
        
        if not all([latitude, longitude, category]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400
        
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
            if issue.get('category') == category:
                similar_issues.append(issue)
        
        return jsonify({
            'duplicate_found': len(similar_issues) > 0,
            'similar_issues': similar_issues
        })
    except Exception as e:
        logger.error(f"Error in check-duplicate: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error checking duplicates: {str(e)}'
        }), 500

@app.route('/report-issue', methods=['POST'])
def report_issue():
    try:
        data = request.json
        
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        category = data.get('category')
        description = data.get('description', '')
        image_data = data.get('image')
        user_id = data.get('user_id', '')

        if not all([latitude, longitude, category]):
            return jsonify({
                'success': False,
                'message': 'Missing required fields'
            }), 400

        models = app.config.get('models', {})

        # Process image for storage
        image_base64 = process_image_for_storage(image_data) if image_data else None
        image_result = verify_image_matches_description(image_base64, description, category=category)

        # Verify image matches description
        if image_base64 and not image_result['match']:
            return jsonify({
                'success': False,
                'message': 'Image does not match the description.'
            }), 400
        category = image_result['category']
        description = image_result['description']
        # Translate to Kannada
        category_kannada = translate_to_kannada(category)
        description_kannada = translate_to_kannada(description) if description else ""

        issue_data = {
            'latitude': latitude,
            'longitude': longitude,
            'category': image_result['category'],
            'category_kannada': category_kannada,
            'description': description,
            'description_kannada': description_kannada,
            'image': image_base64,
            'user_id': user_id
        }

        # Store the issue first
        issue_id = store_issue(issue_data, category)

        # After storing, send notifications if a ward is found for the coordinates
        ward_notified = WardNotificationSystem.process_new_issue(issue_id)

        return jsonify({
            'success': True,
            'issue_id': issue_id,
            'ward_notified': ward_notified,
            'message': 'Issue reported successfully' + (', ward notified' if ward_notified else ', no matching ward found')
        })
    except Exception as e:
        logger.error(f"Error in report-issue: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error reporting issue: {str(e)}'
        }), 500
    
@app.route('/describe', methods=['POST'])
def describe():
    try:
        data = request.json
        image_data = data.get('image')

        # Process image for storage
        image_base64 = process_image_for_storage(image_data) if image_data else None
        image_result = describe_image(image_base64)
        

        return image_result
    except Exception as e:
        logger.error(f"Error in describing-issue: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error describing issue: {str(e)}'
        }), 500
        

# Get nearby issues
@app.route('/issues-nearby', methods=['GET'])
def issues_nearby():
    try:
        latitude = float(request.args.get('latitude'))
        longitude = float(request.args.get('longitude'))
        radius = float(request.args.get('radius', 500))  # Default 500m
        
        nearby_issues = find_nearby_issues(latitude, longitude, radius)
        
        return jsonify({
            'success': True,
            'issues': nearby_issues
        })
    except Exception as e:
        logger.error(f"Error in issues-nearby: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error retrieving nearby issues: {str(e)}'
        }), 500

# Get issue details
@app.route('/issue/<issue_id>', methods=['GET'])
def get_issue(issue_id):
    try:
        db = app.config.get('db')
        if not db:
            return jsonify({
                'success': False,
                'message': 'Database not available'
            }), 503
        
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
                'similar_count': issue_data.get('similar_count', 0),
                'ward_assigned': issue_data.get('ward_assigned', False),
                'ward_name': issue_data.get('ward_name', 'Not assigned'),
                'notification_sent': issue_data.get('notification_sent', False)
            }
        })
    except Exception as e:
        logger.error(f"Error in get-issue: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error retrieving issue: {str(e)}'
        }), 500

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

# Initialize the Flask app
def initialize_app(app):
    try:
        # Initialize Firebase
        db = initialize_firebase()
        app.config['db'] = db
        
        # Load models
        app.config['models'] = initialize_models()
        
        return app
    except Exception as e:
        logger.error(f"Error initializing app: {str(e)}")
        # Continue without certain features if needed
        return app

# Initialize the app
app = initialize_app(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)