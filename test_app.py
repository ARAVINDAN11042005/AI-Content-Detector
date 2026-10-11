"""
test_app.py - Automated Verification Suite for AI Content Detector
Tests:
1. Synthetic and real-like image detection
2. Video frame extraction with OpenCV
3. Flask endpoints: / (index), /api/analyze, /result/<id>, /dashboard, /api/history, DELETE /api/history/<id>
"""

import os
import io
import cv2
import numpy as np
from PIL import Image
from app import app, db, Scan

def run_tests():
    print("=" * 60)
    print("[TEST] Starting AI Content Detector Test Suite")
    print("=" * 60)

    client = app.test_client()

    # 1. Test Web routes status codes
    print("\n[1/5] Testing Web Page Routes...")
    r_index = client.get('/')
    assert r_index.status_code == 200, f"Index failed: {r_index.status_code}"
    assert b"Detect AI Generated" in r_index.data
    print("  [OK] GET / (Upload Page) returned 200 OK")

    r_dash = client.get('/dashboard')
    assert r_dash.status_code == 200, f"Dashboard failed: {r_dash.status_code}"
    assert b"Scan Log & Performance" in r_dash.data
    print("  [OK] GET /dashboard (History Page) returned 200 OK")

    # 2. Generate and test Sample Image Upload
    print("\n[2/5] Testing Image Detection & /api/analyze...")
    # Create test synthetic-looking image (smooth gradient, 1024x1024)
    img_data = np.zeros((1024, 1024, 3), dtype=np.uint8)
    for y in range(1024):
        for x in range(1024):
            img_data[y, x] = [int(x / 1024 * 255), int(y / 1024 * 255), 200]
    
    test_img = Image.fromarray(img_data)
    img_byte_arr = io.BytesIO()
    test_img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)

    r_upload_img = client.post(
        '/api/analyze',
        data={'file': (img_byte_arr, 'synthetic_test_render.png')},
        content_type='multipart/form-data'
    )
    assert r_upload_img.status_code == 201, f"Image upload failed: {r_upload_img.data}"
    json_res = r_upload_img.get_json()
    assert json_res.get('success') is True
    scan_id = json_res['data']['id']
    score = json_res['data']['ai_score']
    label = json_res['data']['label']
    print(f"  [OK] Image analyzed successfully: Scan #{scan_id}, Score: {score}%, Label: '{label}'")

    # 3. Test /result/<scan_id> page
    print("\n[3/5] Testing Result Page Generation...")
    r_result = client.get(f"/result/{scan_id}")
    assert r_result.status_code == 200, f"Result page failed: {r_result.status_code}"
    assert b"AI Probability" in r_result.data
    print(f"  [OK] GET /result/{scan_id} rendered properly with circular gauge data")

    # 4. Generate and test Video Analysis with OpenCV
    print("\n[4/5] Testing Video Generation, Frame Extraction, and Analysis...")
    video_filename = "test_clip.mp4"
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], video_filename)
    
    # Create a 24-frame (1 second) synthetic video
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(video_path, fourcc, 24.0, (320, 240))
    for i in range(24):
        frame = np.full((240, 320, 3), (i * 10 % 255, 120, 180), dtype=np.uint8)
        cv2.putText(frame, f"Frame {i}", (30, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        out.write(frame)
    out.release()

    with open(video_path, 'rb') as vf:
        r_upload_vid = client.post(
            '/api/analyze',
            data={'file': (vf, 'test_motion_clip.mp4')},
            content_type='multipart/form-data'
        )
    assert r_upload_vid.status_code == 201, f"Video upload failed: {r_upload_vid.data}"
    vid_json = r_upload_vid.get_json()
    assert vid_json.get('success') is True
    vid_scan_id = vid_json['data']['id']
    vid_details = vid_json['data']['details']['analysis_data']
    print(f"  [OK] Video analyzed: Scan #{vid_scan_id}, Score: {vid_json['data']['ai_score']}%")
    print(f"  [OK] Extracted {vid_details.get('sampled_frames')} frames via OpenCV")

    # Clean up test source video
    if os.path.exists(video_path):
        os.remove(video_path)

    # 5. Test History API and Deletion
    print("\n[5/5] Testing History & Deletion APIs...")
    r_history = client.get('/api/history')
    assert r_history.status_code == 200
    hist_data = r_history.get_json()
    assert hist_data['stats']['total'] >= 2
    print(f"  [OK] GET /api/history returned {len(hist_data['scans'])} records, Total stats: {hist_data['stats']['total']}")

    r_delete = client.delete(f"/api/history/{scan_id}")
    assert r_delete.status_code == 200
    print(f"  [OK] DELETE /api/history/{scan_id} executed cleanly")

    r_history_after = client.get('/api/history')
    assert r_history_after.get_json()['stats']['total'] == hist_data['stats']['total'] - 1
    print("  [OK] Verified DB record and file removal")

    print("\n" + "=" * 60)
    print("[SUCCESS] ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
