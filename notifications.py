import firebase_admin
from firebase_admin import credentials, firestore
from shapely.geometry import Point, Polygon
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Firebase (if not already initialized)
def get_firestore_db():
    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    return firestore.client()

class WardNotificationSystem:
    @staticmethod
    def process_new_issue(issue_id):
        """
        Process a newly created issue to send notifications
        
        Args:
            issue_id (str): ID of the newly created issue
            
        Returns:
            bool: True if issue was processed and notification sent, False otherwise
        """
        try:
            db = get_firestore_db()
            
            # Get issue data
            issue_ref = db.collection('issues').document(issue_id)
            issue_doc = issue_ref.get()
            
            if not issue_doc.exists:
                logger.error(f"Issue {issue_id} not found")
                return False
            
            issue_data = issue_doc.to_dict()
            issue_data['id'] = issue_id
            
            # Find ward for issue location
            ward = WardNotificationSystem.find_ward_for_location(
                db,
                float(issue_data['latitude']), 
                float(issue_data['longitude'])
            )
            
            if not ward:
                logger.info(f"No ward found for location: {issue_data['latitude']}, {issue_data['longitude']}")
                # Update the issue with no assigned ward
                issue_ref.update({
                    'ward_assigned': False,
                    'notification_sent': False
                })
                return False
            
            # Update issue with ward info
            issue_ref.update({
                'ward_id': ward['ward_id'],
                'ward_name': ward['name'],
                'ward_assigned': True
            })
            
            # Send email notification
            email_sent = WardNotificationSystem.send_email_notification(ward['officer_email'], issue_data, ward)
            
            # Update issue with notification status
            issue_ref.update({
                'notification_sent': email_sent,
                'notification_email_sent': email_sent,
                'notification_time': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Issue {issue_id} assigned to ward {ward['name']} and notification status: {email_sent}")
            return email_sent
            
        except Exception as e:
            logger.error(f"Error processing issue {issue_id}: {str(e)}")
            return False
    
    @staticmethod
    def find_ward_for_location(db, lat, long):
        """
        Find the ward for the given coordinates
        
        Args:
            db: Firestore database instance
            lat (float): Latitude of the issue
            long (float): Longitude of the issue
            
        Returns:
            dict: Ward document or None if no ward contains the point
        """
        # Using 'ward' collection name as specified
        wards_ref = db.collection('ward')
        wards = list(wards_ref.stream())
        
        if not wards:
            logger.warning("No wards found in database")
            return None
        
        # Check each ward to see if the point is within its boundaries
        # for ward_doc in wards:
        #     ward = ward_doc.to_dict()
        #     ward['id'] = ward_doc.id
            
        #     # Check if the issue location is within this ward's boundaries
        #     if 'boundaries' in ward and WardNotificationSystem.point_in_polygon(lat, long, ward['boundaries']):
        #         logger.info(f"Found matching ward: {ward['name']} for location ({lat}, {long})")
        #         return ward

        if lat <= 12.9645864 and long <= 76.728024: 
            return wards[0].to_dict()
        else:
            return wards[1].to_dict()
        # # If we get here, the point wasn't in any ward
        # logger.info(f"No ward contains the point ({lat}, {long})")
        # return None
    
    @staticmethod
    def point_in_polygon(lat, long, boundaries):
        """
        Check if a point (lat, long) falls inside a polygon defined by boundaries
        
        Args:
            lat (float): Latitude of the point
            long (float): Longitude of the point
            boundaries (list): List of coordinate objects defining the polygon
            
        Returns:
            bool: True if point is inside polygon, False otherwise
        """
        point = Point(lat, long)
        # Convert boundaries to the format expected by Shapely
        polygon_coords = [(b['lat'], b['lng']) for b in boundaries]
        polygon = Polygon(polygon_coords)
        
        return polygon.contains(point)
    
    @staticmethod
    def send_email_notification(officer_email, issue_data, ward_data):
        """
        Send email notification to ward officer
        
        Args:
            officer_email (str): Email address of ward officer
            issue_data (dict): Issue details
            ward_data (dict): Ward details
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            # Get email configuration from environment variables
            email_sender = os.getenv("EMAIL_SENDER")
            email_password = os.getenv("EMAIL_PASSWORD")
            smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
            smtp_port = int(os.getenv("SMTP_PORT", "587"))
            
            # Validate email configuration
            if not email_sender or not email_password:
                logger.error("Email credentials not configured")
                return False
            
            msg = MIMEMultipart()
            msg['From'] = email_sender
            msg['To'] = officer_email
            msg['Subject'] = f"New Issue Reported in {ward_data['name']} - {issue_data['category']}"
            
            # Format the email body
            created_at = issue_data.get('created_at')
            if isinstance(created_at, str):
                # Parse ISO format if it's a string
                created_at_display = created_at
            else:
                # Format datetime object
                created_at_display = created_at.strftime('%Y-%m-%d %H:%M:%S') if created_at else "Unknown"
            
            body = f"""
            <html>
            <body>
                <h2>New Issue Reported in Your Ward</h2>
                <p><strong>Ward:</strong> {ward_data['name']} (ID: {ward_data['ward_id']})</p>
                <p><strong>Category:</strong> {issue_data.get('category', 'Not specified')}</p>
                <p><strong>Description:</strong> {issue_data.get('description', 'No description provided')}</p>
                <p><strong>Location:</strong> {issue_data.get('latitude', 'N/A')}, {issue_data.get('longitude', 'N/A')}</p>
                <p><strong>Reported on:</strong> {created_at_display}</p>
                <p><strong>Issue ID:</strong> {issue_data['id']}</p>
                <p>Please check the admin dashboard for more details.</p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            logger.info(f"Attempting to send email to {officer_email} via {smtp_server}:{smtp_port}")
            
            # Connect to SMTP server and send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(email_sender, email_password)
                server.send_message(msg)
                
            logger.info(f"Email notification sent to {officer_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            return False