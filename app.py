from flask import Flask, render_template, request, jsonify, send_file, url_for
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import boto3
from io import BytesIO
import pandas as pd

app = Flask(__name__)

# AWS S3 Configuration
S3_BUCKET = os.environ.get('S3_BUCKET_NAME')
USE_S3 = os.environ.get('USE_S3', 'False').lower() == 'true'

# Configure download folder
DOWNLOAD_FOLDER = 'data/downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Move imports inside the route functions to prevent automatic execution
# We'll only import when needed

CATEGORIES = ['wireless_accessory',
    'wireless',
    'watch',
    'video_games',
    'toy',
    'tools',
    'tires',
    'sports',
    'software',
    'shoes',
    'pet_products',
    'personal_care_appliances',
    'pc',
    'outdoors',
    'office_product',
    'musical_instruments',
    'major_appliances',
    'luxury_beauty',
    'luggage',
    'lawn_and_garden',
    'kitchen',
    'jewelry',
    'home_improvement',
    'home_entertainment',
    'home',
    'grocery',
    'game',
    'furniture',
    'electronics',
    'drugstore',
    'camera',
    'book',
    'biss',
    'beauty',
    'baby',
    'automotive',
    'apparel']

# Add this configuration
UPLOAD_FOLDER = 'data/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html', categories=CATEGORIES)

@app.route('/start_scraping', methods=['POST'])
def start_scraping():
    import trendyol_scraper

    category = request.form.get('category')
    if not category:
        return jsonify({'status': 'error', 'message': 'Category is required'})
    
    try:
        # Create timestamp for this run
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_dir = f'data/output/{timestamp}'
        os.makedirs(output_dir, exist_ok=True)
        
        # Start the scraping process with category and S3 options
        # Set user_interaction_needed to True to disable headless mode
        result = trendyol_scraper.start_scraping(
            category=category,
            save_to_s3=USE_S3,
            s3_bucket=S3_BUCKET,
            user_interaction_needed=True
        )
        
        # Get the filename from the result
        filename = result['filename']
        
        # Create a download URL
        download_url = url_for('download_file', filename=filename)
        
        return jsonify({
            'status': 'success',
            'message': 'Scraping completed successfully',
            'timestamp': timestamp,
            'download_url': download_url,
            'filename': filename
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


# Processing routes have been removed as they're no longer needed

# Add a new route for file downloads
@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    # Check if file exists in local storage
    local_path = os.path.join(DOWNLOAD_FOLDER, filename)
    
    # If using S3 and file doesn't exist locally, try to get it from S3
    if USE_S3 and not os.path.exists(local_path):
        try:
            s3_client = boto3.client('s3')
            s3_key = f"scraped_data/{filename}"
            
            # Download file to memory
            file_obj = BytesIO()
            s3_client.download_fileobj(S3_BUCKET, s3_key, file_obj)
            file_obj.seek(0)
            
            # Save to local cache for future requests
            with open(local_path, 'wb') as f:
                f.write(file_obj.getvalue())
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Error downloading file from S3: {str(e)}'})
    
    # If file exists locally now, send it
    if os.path.exists(local_path):
        return send_file(
            local_path,
            as_attachment=True,
            download_name=filename
        )
    else:
        return jsonify({'status': 'error', 'message': 'File not found'})

if __name__ == '__main__':
    # Get port from environment variable for cloud deployment compatibility
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'True').lower() == 'true')