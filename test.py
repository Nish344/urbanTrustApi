import requests
import json
import base64
import os
import argparse
from PIL import Image
import io
import time

# Constants
BASE_URL = "http://127.0.0.1:5000"  # Change if your Flask app is running on a different URL

def encode_image(image_path):
    """Encode an image to base64 for API request"""
    try:
        with open(image_path, 'rb') as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded_string
    except Exception as e:
        print(f"Error encoding image: {str(e)}")
        return None

def health_check():
    """Test the health endpoint"""
    url = f"{BASE_URL}/health"
    try:
        response = requests.get(url)
        print("\n=== Health Check ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error during health check: {str(e)}")
        return False

def check_duplicate(latitude, longitude, category):
    """Test the check-duplicate endpoint"""
    url = f"{BASE_URL}/check-duplicate"
    
    payload = {
        "latitude": latitude,
        "longitude": longitude,
        "category": category
    }
    
    try:
        response = requests.post(url, json=payload)
        print("\n=== Check for Duplicate Issues ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except Exception as e:
        print(f"Error checking for duplicates: {str(e)}")
        return None

def report_issue(latitude, longitude, category, description=None, image_path=None):
    """Test the report-issue endpoint"""
    url = f"{BASE_URL}/report-issue"
    
    payload = {
        "latitude": latitude,
        "longitude": longitude,
        "category": category
    }
    
    if description:
        payload["description"] = description
    
    if image_path:
        encoded_image = encode_image(image_path)
        if encoded_image:
            payload["image"] = encoded_image
    
    try:
        response = requests.post(url, json=payload)
        print("\n=== Report Issue ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except Exception as e:
        print(f"Error reporting issue: {str(e)}")
        return None

def get_nearby_issues(latitude, longitude, radius=500):
    """Test the issues-nearby endpoint"""
    url = f"{BASE_URL}/issues-nearby"
    
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "radius": radius
    }
    
    try:
        response = requests.get(url, params=params)
        print("\n=== Nearby Issues ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except Exception as e:
        print(f"Error getting nearby issues: {str(e)}")
        return None

def get_issue_details(issue_id):
    """Test the issue details endpoint"""
    url = f"{BASE_URL}/issue/{issue_id}"
    
    try:
        response = requests.get(url)
        print("\n=== Issue Details ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except Exception as e:
        print(f"Error getting issue details: {str(e)}")
        return None

def interactive_test():
    """Run interactive tests based on user input"""
    print("\n=== Interactive Test Mode ===")
    print("Choose a test to run:")
    print("1. Health Check")
    print("2. Check for Duplicate Issues")
    print("3. Report a New Issue")
    print("4. Get Nearby Issues")
    print("5. Get Issue Details")
    print("6. Run All Tests")
    print("0. Exit")
    
    choice = input("\nEnter your choice (0-6): ")
    
    if choice == "0":
        return
    
    if choice in ["1", "6"]:
        health_check()
    
    if choice in ["2", "6"]:
        latitude = float(input("\nEnter latitude (e.g., 12.9716): ") or "12.9716")
        longitude = float(input("Enter longitude (e.g., 77.5946): ") or "77.5946")
        category = input("Enter category (e.g., pothole, garbage): ") or "pothole"
        check_duplicate(latitude, longitude, category)
    
    if choice in ["3", "6"]:
        latitude = float(input("\nEnter latitude (e.g., 12.9716): ") or "12.9716")
        longitude = float(input("Enter longitude (e.g., 77.5946): ") or "77.5946")
        category = input("Enter category (e.g., pothole, garbage): ") or "pothole"
        description = input("Enter description (optional): ") or "A large pothole causing traffic issues"
        
        use_image = input("Upload an image? (y/n): ").lower() == 'y'
        image_path = None
        if use_image:
            image_path = input("Enter image path: ")
            if not os.path.exists(image_path):
                print(f"Image not found at {image_path}")
                image_path = None
        
        result = report_issue(latitude, longitude, category, description, image_path)
        if result and result.get("success") and result.get("issue_id"):
            print(f"\nIssue reported successfully with ID: {result['issue_id']}")
    
    if choice in ["4", "6"]:
        latitude = float(input("\nEnter latitude (e.g., 12.9716): ") or "12.9716")
        longitude = float(input("Enter longitude (e.g., 77.5946): ") or "77.5946")
        radius = float(input("Enter radius in meters (e.g., 500): ") or "500")
        get_nearby_issues(latitude, longitude, radius)
    
    if choice in ["5", "6"]:
        issue_id = input("\nEnter issue ID: ")
        if issue_id:
            get_issue_details(issue_id)
        else:
            print("Issue ID is required")
    
    # Ask if user wants to continue
    if input("\nRun another test? (y/n): ").lower() == 'y':
        interactive_test()

def main():
    """Main function to run the tests"""
    parser = argparse.ArgumentParser(description='Test the Issue Reporting API')
    parser.add_argument('--mode', choices=['interactive', 'auto'], default='interactive',
                        help='Test mode: interactive or auto')
    parser.add_argument('--latitude', type=float, default=12.9716,
                        help='Latitude for testing')
    parser.add_argument('--longitude', type=float, default=77.5946,
                        help='Longitude for testing')
    parser.add_argument('--category', default='pothole',
                        help='Issue category for testing')
    parser.add_argument('--description', default='A large pothole causing traffic issues',
                        help='Issue description for testing')
    parser.add_argument('--image', help='Path to image file for testing')
    
    args = parser.parse_args()
    
    if args.mode == 'interactive':
        interactive_test()
    else:
        # Run automated tests
        print("=== Automated Tests ===")
        
        # Check if API is healthy
        if not health_check():
            print("API health check failed. Make sure the Flask app is running.")
            return
        
        # Check for duplicates
        check_duplicate(args.latitude, args.longitude, args.category)
        
        # Report a new issue
        result = report_issue(args.latitude, args.longitude, args.category, args.description, args.image)
        
        if result and result.get("success") and result.get("issue_id"):
            issue_id = result.get("issue_id")
            print(f"\nIssue reported successfully with ID: {issue_id}")
            
            # Get nearby issues
            time.sleep(1)  # Brief pause to ensure the issue is stored
            get_nearby_issues(args.latitude, args.longitude)
            
            # Get issue details
            time.sleep(1)  # Brief pause
            get_issue_details(issue_id)
        else:
            print("Failed to report issue")

if __name__ == "__main__":
    main()
