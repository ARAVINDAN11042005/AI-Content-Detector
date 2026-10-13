"""
app.py - Flask Web Application for AI Content Detector
Provides REST APIs for file analysis, scan history, deletion,
and serves responsive HTML views for upload, results, and dashboard.
"""

import os
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, flash

from dotenv import load_dotenv
load_dotenv()

from models import db, Scan
from detector import analyze_file, get_classification_label

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'ai-content-detector-secret-key-2026')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# On Vercel the filesystem is read-only; only /tmp is writable
IS_VERCEL = os.environ.get('VERCEL') == '1' or os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None

if IS_VERCEL:
    UPLOAD_FOLDER = '/tmp/uploads'
    db_path = '/tmp/ai_detector.db'
else:
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    db_path = os.path.join(BASE_DIR, 'ai_detector.db')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(os.path.join(UPLOAD_FOLDER, 'frames'), exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max upload limit

# SQLite Database Setup
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'mp4', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in {'jpg', 'jpeg', 'png', 'webp'}:
        return 'image'
    elif ext in {'mp4', 'webm'}:
        return 'video'
    return 'unknown'

# Create tables on startup
with app.app_context():
    db.create_all()


# ==========================================
# WEB PAGE ROUTES
# ==========================================

@app.route('/')
def index():
    """Upload page: Drag & drop or file selection."""
    return render_template('index.html')


@app.route('/result/<int:scan_id>')
def result(scan_id):
    """Results page displaying circular progress gauge, breakdown, and details."""
    scan = Scan.query.get_or_404(scan_id)
    return render_template('result.html', scan=scan, details=scan.details)


@app.route('/dashboard')
def dashboard():
    """History and analytics dashboard page."""
    return render_template('history.html')


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve uploaded media files and extracted frames."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """
    POST /api/analyze
    Accepts multipart/form-data with 'file'.
    Runs AI detection engine, saves record in SQLite, and returns JSON.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file field in upload request'}), 400

    file = request.files['file']
    if not file or file.filename.strip() == '':
        return jsonify({'error': 'No file selected for analysis'}), 400

    if not allowed_file(file.filename):
        return jsonify({
            'error': f'Unsupported file type. Please upload an image (JPG, PNG, WEBP) or video (MP4, WEBM).'
        }), 400

    original_name = file.filename
    clean_name = secure_filename(original_name)
    ext = clean_name.rsplit('.', 1)[1].lower() if '.' in clean_name else 'dat'
    unique_name = f"{uuid.uuid4().hex[:12]}_{clean_name}"
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

    try:
        file.save(save_path)
    except Exception as e:
        return jsonify({'error': f'Failed to save uploaded file: {str(e)}'}), 500

    try:
        # Run detection engine
        analysis = analyze_file(save_path, app.config['UPLOAD_FOLDER'])
        file_type = analysis.get('type', get_file_type(clean_name))
        ai_score = analysis.get('ai_score', 0.0)
        label = analysis.get('label', 'Unknown')
        details = analysis.get('details', {})

        # Create DB record
        scan_record = Scan(
            filename=unique_name,
            original_filename=original_name,
            file_type=file_type,
            ai_score=ai_score,
            label=label,
            file_path=f"/uploads/{unique_name}"
        )
        scan_record.details = {
            'engine': analysis.get('engine', 'Local Heuristic Engine'),
            'summary': analysis.get('summary', ''),
            'category': analysis.get('category', 'uncertain'),
            'color': analysis.get('color', '#F59E0B'),
            'badge_class': analysis.get('badge_class', 'badge-uncertain'),
            'analysis_data': details
        }

        db.session.add(scan_record)
        db.session.commit()

        response_data = scan_record.to_dict()
        response_data['redirect_url'] = url_for('result', scan_id=scan_record.id)
        return jsonify({
            'success': True,
            'data': response_data
        }), 201

    except Exception as e:
        db.session.rollback()
        # Clean up failed file if needed
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except Exception:
                pass
        return jsonify({'error': f'Detection failed: {str(e)}'}), 500


@app.route('/api/history', methods=['GET'])
def api_history():
    """
    GET /api/history
    Returns all scans as JSON, supports filtering and summary stats.
    Query params:
      - type: 'all', 'image', 'video'
      - label: 'all', 'ai' (score >= 70), 'real' (score <= 30), 'uncertain' (30 < score < 70)
      - search: string match on filename
    """
    file_type = request.args.get('type', 'all').lower()
    label_filter = request.args.get('label', 'all').lower()
    search = request.args.get('search', '').strip().lower()

    query = Scan.query.order_by(Scan.created_at.desc())

    if file_type in ('image', 'video'):
        query = query.filter(Scan.file_type == file_type)

    if label_filter == 'ai':
        query = query.filter(Scan.ai_score >= 69.5)
    elif label_filter == 'real':
        query = query.filter(Scan.ai_score < 30.5)
    elif label_filter == 'uncertain':
        query = query.filter(Scan.ai_score >= 30.5, Scan.ai_score < 69.5)

    scans = query.all()

    if search:
        scans = [s for s in scans if search in (s.original_filename or s.filename).lower()]

    # Global Stats
    total_scans = Scan.query.count()
    ai_detected = Scan.query.filter(Scan.ai_score >= 69.5).count()
    real_detected = Scan.query.filter(Scan.ai_score < 30.5).count()
    uncertain_detected = Scan.query.filter(Scan.ai_score >= 30.5, Scan.ai_score < 69.5).count()

    one_week_ago = datetime.utcnow() - timedelta(days=7)
    this_week_scans = Scan.query.filter(Scan.created_at >= one_week_ago).count()

    return jsonify({
        'scans': [s.to_dict() for s in scans],
        'stats': {
            'total': total_scans,
            'ai_count': ai_detected,
            'real_count': real_detected,
            'uncertain_count': uncertain_detected,
            'this_week': this_week_scans
        }
    })


@app.route('/api/history/<int:scan_id>', methods=['DELETE'])
def api_delete_scan(scan_id):
    """
    DELETE /api/history/<id>
    Deletes a scan record and removes associated uploaded files from disk.
    """
    scan = Scan.query.get(scan_id)
    if not scan:
        return jsonify({'error': 'Scan record not found'}), 404

    try:
        # Remove file from disk
        file_disk_path = os.path.join(app.config['UPLOAD_FOLDER'], scan.filename)
        if os.path.exists(file_disk_path):
            try:
                os.remove(file_disk_path)
            except Exception:
                pass

        # If it was a video, remove extracted frames
        base_name = os.path.splitext(scan.filename)[0]
        frames_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'frames')
        if os.path.exists(frames_dir):
            for f in os.listdir(frames_dir):
                if f.startswith(base_name):
                    try:
                        os.remove(os.path.join(frames_dir, f))
                    except Exception:
                        pass

        db.session.delete(scan)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Scan record deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to delete scan: {str(e)}'}), 500


if __name__ == '__main__':
    print("=" * 60)
    print(">> AI Content Detector Web Application Starting...")
    print(">> Local URL: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(host='127.0.0.1', port=5000, debug=False)
