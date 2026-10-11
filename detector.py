"""
detector.py - AI Content Detection Engine
Supports:
1. Sightengine API integration for real-time AI image detection
2. Local forensic heuristic engine (Noise analysis, EXIF inspection, color uniformity, frequency analysis)
3. OpenCV video frame extraction and multi-frame aggregation
"""

import os
import io
import math
import cv2
import numpy as np
import requests
from PIL import Image, ExifTags
from dotenv import load_dotenv

load_dotenv()

SIGHTENGINE_API_USER = os.getenv('SIGHTENGINE_API_USER', '').strip()
SIGHTENGINE_API_SECRET = os.getenv('SIGHTENGINE_API_SECRET', '').strip()

# Common AI generator tags and keywords found in prompts or software metadata
AI_METADATA_KEYWORDS = [
    'midjourney', 'stable diffusion', 'dall-e', 'dalle', 'novelai',
    'comfyui', 'civitai', 'automatic1111', 'invokeai', 'adobe firefly',
    'flux.1', 'dreamstudio', 'sdxl', 'leonardo.ai', 'bing image creator',
    'parameters', 'prompt', 'negative prompt', 'steps: ', 'sampler: ', 'cfg scale: '
]

def get_classification_label(score: float) -> dict:
    """
    Returns label, category, color-code, and description based on AI percentage score.
    0-30%   -> Real / Human-Made (Green)
    31-69%  -> Uncertain / Mixed Signals (Yellow)
    70-100% -> AI Generated (Red)
    """
    if score < 30.5:
        return {
            'label': 'Likely Human-Made',
            'category': 'real',
            'color': '#10B981',  # Emerald Green
            'badge_class': 'badge-real',
            'summary': 'High authenticity markers found. Natural sensor noise and camera signatures suggest genuine real-world content.'
        }
    elif score < 69.5:
        return {
            'label': 'Uncertain / Mixed Signals',
            'category': 'uncertain',
            'color': '#F59E0B',  # Amber Yellow
            'badge_class': 'badge-uncertain',
            'summary': 'Mixed visual signals detected. File may be digitally edited, compressed, or partially AI-assisted.'
        }
    else:
        return {
            'label': 'Likely AI-Generated',
            'category': 'ai',
            'color': '#EF4444',  # Red / Crimson
            'badge_class': 'badge-ai',
            'summary': 'Strong synthetic indicators detected, including characteristic diffusion texture, metadata absence, or generator artifacts.'
        }


def check_sightengine_api(image_path: str) -> dict:
    """
    Queries Sightengine's GenAI detection endpoint if credentials are provided.
    Returns result dict with score (0-100) or None if not configured/failed.
    """
    if not SIGHTENGINE_API_USER or not SIGHTENGINE_API_SECRET:
        return None

    try:
        url = 'https://api.sightengine.com/1.0/check.json'
        params = {
            'models': 'genai',
            'api_user': SIGHTENGINE_API_USER,
            'api_secret': SIGHTENGINE_API_SECRET
        }
        with open(image_path, 'rb') as f:
            files = {'media': f}
            response = requests.post(url, data=params, files=files, timeout=12)

        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 'success' and 'type' in data:
                ai_prob = data['type'].get('ai_generated', 0.0)
                score = round(ai_prob * 100.0, 1)
                return {
                    'success': True,
                    'score': score,
                    'engine': 'Sightengine GenAI API',
                    'raw': data
                }
    except Exception as e:
        print(f"[Detector] Sightengine API call failed: {e}. Falling back to local heuristic engine.")

    return None


def extract_metadata_heuristics(pil_img: Image.Image, file_path: str) -> dict:
    """
    Inspects EXIF data, software headers, and raw text comments for camera hardware or AI generator fingerprints.
    """
    found_ai_keywords = []
    has_camera_hardware = False
    camera_model = None
    software_tag = None
    exif_count = 0

    # 1. Check EXIF if available
    try:
        exif = pil_img.getexif()
        if exif:
            exif_count = len(exif)
            for tag_id, value in exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                str_val = str(value).lower()

                if tag_name in ('Make', 'Model'):
                    has_camera_hardware = True
                    camera_model = str(value)
                if tag_name == 'Software':
                    software_tag = str(value)

                for kw in AI_METADATA_KEYWORDS:
                    if kw in str_val and kw not in found_ai_keywords:
                        found_ai_keywords.append(kw)
    except Exception:
        pass

    # 2. Check PNG text chunks / info dictionary
    if hasattr(pil_img, 'info') and isinstance(pil_img.info, dict):
        for k, v in pil_img.info.items():
            combined = f"{k} {v}".lower()
            for kw in AI_METADATA_KEYWORDS:
                if kw in combined and kw not in found_ai_keywords:
                    found_ai_keywords.append(kw)

    # 3. Quick binary scan of file headers for AI keywords (e.g. Midjourney / Stable Diffusion params)
    try:
        with open(file_path, 'rb') as bf:
            header_bytes = bf.read(65536)  # inspect first 64KB
            header_str = header_bytes.decode('latin-1', errors='ignore').lower()
            for kw in AI_METADATA_KEYWORDS:
                if kw in header_str and kw not in found_ai_keywords:
                    found_ai_keywords.append(kw)
    except Exception:
        pass

    return {
        'has_camera_hardware': has_camera_hardware,
        'camera_model': camera_model,
        'software_tag': software_tag,
        'exif_tag_count': exif_count,
        'found_ai_keywords': found_ai_keywords
    }


def analyze_image_noise_and_texture(cv_img_rgb: np.ndarray) -> dict:
    """
    Performs forensic computer vision analysis on image textures, noise variance,
    and high-frequency edge residual distributions.
    """
    gray = cv2.cvtColor(cv_img_rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    # 1. Laplacian variance (micro-texture sharpness & sensor noise)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    laplacian_var = float(laplacian.var())

    # 2. Noise residual: High-pass filter via Gaussian subtraction
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    noise_residual = cv2.absdiff(gray, blurred)
    noise_std = float(np.std(noise_residual))
    noise_mean = float(np.mean(noise_residual))

    # 3. Saturation uniformity and distribution (HSV space)
    hsv = cv2.cvtColor(cv_img_rgb, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1].astype(np.float32)
    sat_mean = float(np.mean(saturation))
    sat_std = float(np.std(saturation))

    # 4. Color channel correlation (AI generators often have distinctive channel co-dependence)
    r = cv_img_rgb[:, :, 0].flatten().astype(np.float32)
    g = cv_img_rgb[:, :, 1].flatten().astype(np.float32)
    b = cv_img_rgb[:, :, 2].flatten().astype(np.float32)

    r_std, g_std, b_std = np.std(r), np.std(g), np.std(b)
    rg_corr = float(np.corrcoef(r, g)[0, 1]) if (r_std > 1e-4 and g_std > 1e-4) else 1.0
    rb_corr = float(np.corrcoef(r, b)[0, 1]) if (r_std > 1e-4 and b_std > 1e-4) else 1.0

    # 5. Aspect ratio and standard AI resolution check (e.g. 512, 768, 1024, 1280)
    common_ai_dimensions = {512, 768, 1024, 1152, 1280, 1344, 1536}
    is_exact_ai_dim = (w in common_ai_dimensions) and (h in common_ai_dimensions)
    is_square = (w == h)

    return {
        'laplacian_var': round(laplacian_var, 2),
        'noise_std': round(noise_std, 2),
        'noise_mean': round(noise_mean, 2),
        'sat_mean': round(sat_mean, 2),
        'sat_std': round(sat_std, 2),
        'rg_corr': round(rg_corr, 3),
        'rb_corr': round(rb_corr, 3),
        'is_exact_ai_dim': is_exact_ai_dim,
        'is_square': is_square,
        'width': w,
        'height': h
    }


def local_heuristic_image_detector(file_path: str, pil_img: Image.Image = None) -> dict:
    """
    Forensic heuristic detector combining metadata inspection, sensor noise analysis,
    and texture synthesis metrics.
    """
    if pil_img is None:
        pil_img = Image.open(file_path).convert('RGB')
    else:
        pil_img = pil_img.convert('RGB')

    cv_img_rgb = np.array(pil_img)

    # 1. Metadata check
    meta = extract_metadata_heuristics(pil_img, file_path)

    # 2. Noise & texture check
    texture = analyze_image_noise_and_texture(cv_img_rgb)

    # Heuristic scoring formulation (0 = definitely real, 100 = definitely AI)
    ai_score_points = 50.0  # Base neutral baseline
    reasons = []

    # Evidence 1: AI Prompt / Generator signature metadata
    if meta['found_ai_keywords']:
        ai_score_points += 45.0
        reasons.append({
            'name': 'AI Generator Signature Found',
            'signal': 'AI',
            'detail': f"Detected generation tags/parameters: {', '.join(meta['found_ai_keywords'][:3])}"
        })
    elif meta['has_camera_hardware']:
        ai_score_points -= 42.0
        reasons.append({
            'name': 'Camera Hardware EXIF Found',
            'signal': 'Real',
            'detail': f"Authentic camera model verified: {meta['camera_model']}"
        })
    else:
        # Absence of EXIF is common in downloaded/synthetic images
        ai_score_points += 12.0
        reasons.append({
            'name': 'Camera EXIF Stripped/Missing',
            'signal': 'AI',
            'detail': 'No hardware sensor metadata found (characteristic of AI generation or web re-exports).'
        })

    # Evidence 2: Noise residual profile
    # Genuine camera sensors have physical grain/shot noise (std usually 4.0 - 18.0)
    # AI images often have either synthetic uniformity (< 2.8) or excessive post-diffusion smoothing
    noise_std = texture['noise_std']
    if noise_std < 2.5:
        ai_score_points += 18.0
        reasons.append({
            'name': 'Unnatural Smoothness / Low Sensor Grain',
            'signal': 'AI',
            'detail': f"Sensor noise residual is {noise_std} (typical of diffusion de-noised generation)."
        })
    elif 4.0 <= noise_std <= 22.0:
        ai_score_points -= 14.0
        reasons.append({
            'name': 'Natural Sensor Grain Pattern',
            'signal': 'Real',
            'detail': f"High-frequency sensor grain std of {noise_std} matches physical optical sensor noise."
        })
    elif noise_std > 28.0:
        ai_score_points += 8.0
        reasons.append({
            'name': 'High-Frequency Synthetic Artifacts',
            'signal': 'AI',
            'detail': f"Noise standard deviation is {noise_std}, suggesting potential latent diffusion noise."
        })

    # Evidence 3: Dimension & Aspect Ratio
    if texture['is_exact_ai_dim']:
        ai_score_points += 15.0
        reasons.append({
            'name': 'Standard AI Resolution Canvas',
            'signal': 'AI',
            'detail': f"Image dimensions {texture['width']}x{texture['height']} match standard AI generator output canvas."
        })
    elif texture['width'] > 3000 or texture['height'] > 3000:
        ai_score_points -= 10.0
        reasons.append({
            'name': 'High-Resolution Physical Sensor Format',
            'signal': 'Real',
            'detail': f"High native resolution ({texture['width']}x{texture['height']}) matches modern smartphone/DSLR sensors."
        })

    # Evidence 4: Saturation & Color Balance
    sat_mean = texture['sat_mean']
    if sat_mean > 140 and texture['sat_std'] < 45:
        ai_score_points += 10.0
        reasons.append({
            'name': 'Hyper-Vibrant Saturation Profile',
            'signal': 'AI',
            'detail': 'Unusually high and uniform color saturation often characteristic of stylized AI art models.'
        })

    # Clamp score to [2.0, 99.0]
    final_score = max(2.5, min(98.5, ai_score_points))

    return {
        'score': round(final_score, 1),
        'engine': 'Local Forensic Heuristic Engine',
        'metadata': meta,
        'texture': texture,
        'reasons': reasons
    }


def analyze_image(file_path: str) -> dict:
    """
    Main image analysis entrypoint.
    Tries Sightengine API first; if unavailable or failing, utilizes the local heuristic engine.
    """
    pil_img = Image.open(file_path).convert('RGB')

    # Try Sightengine API
    api_result = check_sightengine_api(file_path)

    # Compute local forensics for comprehensive breakdown report regardless
    local_forensics = local_heuristic_image_detector(file_path, pil_img)

    if api_result and api_result.get('success'):
        final_score = api_result['score']
        engine_name = 'Sightengine GenAI API'
        reasons = local_forensics.get('reasons', [])
        reasons.insert(0, {
            'name': 'Sightengine Cloud Model Score',
            'signal': 'AI' if final_score >= 50 else 'Real',
            'detail': f"Deep learning neural classifier returned {final_score}% AI probability."
        })
    else:
        final_score = local_forensics['score']
        engine_name = local_forensics['engine']
        reasons = local_forensics.get('reasons', [])

    label_info = get_classification_label(final_score)

    return {
        'type': 'image',
        'ai_score': final_score,
        'label': label_info['label'],
        'category': label_info['category'],
        'color': label_info['color'],
        'badge_class': label_info['badge_class'],
        'summary': label_info['summary'],
        'engine': engine_name,
        'details': {
            'dimensions': f"{pil_img.width} x {pil_img.height} px",
            'format': pil_img.format or 'JPEG/PNG',
            'reasons': reasons,
            'metadata': local_forensics['metadata'],
            'texture': local_forensics['texture']
        }
    }


def analyze_video(file_path: str, uploads_dir: str) -> dict:
    """
    Analyzes a video file by extracting evenly spaced frames using OpenCV,
    evaluating each frame individually, and computing overall statistics.
    """
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise ValueError(f"Unable to open video file at {file_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_sec = round(total_frames / fps, 1) if fps > 0 else 0.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Determine frame sample count (sample between 6 and 10 frames)
    sample_count = min(10, max(4, total_frames // 15))
    if sample_count <= 0 or total_frames < 2:
        sample_count = 1

    step = max(1, total_frames // sample_count)
    frame_indices = [i * step for i in range(sample_count)]

    # Folder to store frame thumbnail snapshots
    frames_dir = os.path.join(uploads_dir, 'frames')
    os.makedirs(frames_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(file_path))[0]

    frame_results = []
    frame_scores = []

    for idx, frame_idx in enumerate(frame_indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret or frame is None:
            continue

        # Convert BGR (OpenCV) to RGB for analysis
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_pil = Image.fromarray(frame_rgb)

        # Save thumbnail frame
        thumb_filename = f"{base_name}_frame_{idx + 1}.jpg"
        thumb_path = os.path.join(frames_dir, thumb_filename)
        # Resize thumbnail to save space while keeping detail
        thumb_pil = frame_pil.copy()
        thumb_pil.thumbnail((480, 270))
        thumb_pil.save(thumb_path, 'JPEG', quality=85)

        # Evaluate frame with local heuristic detector
        frame_analysis = local_heuristic_image_detector(thumb_path, frame_pil)
        f_score = frame_analysis['score']
        frame_scores.append(f_score)

        timestamp_sec = round(frame_idx / fps, 2) if fps > 0 else 0.0

        frame_results.append({
            'frame_number': idx + 1,
            'source_frame_idx': frame_idx,
            'timestamp': f"{timestamp_sec:.1f}s",
            'score': f_score,
            'thumbnail': f"/uploads/frames/{thumb_filename}",
            'label': get_classification_label(f_score)['label'],
            'badge_class': get_classification_label(f_score)['badge_class']
        })

    cap.release()

    if not frame_scores:
        avg_score = 50.0
    else:
        avg_score = round(float(np.mean(frame_scores)), 1)

    label_info = get_classification_label(avg_score)
    min_score = min(frame_scores) if frame_scores else avg_score
    max_score = max(frame_scores) if frame_scores else avg_score

    return {
        'type': 'video',
        'ai_score': avg_score,
        'label': label_info['label'],
        'category': label_info['category'],
        'color': label_info['color'],
        'badge_class': label_info['badge_class'],
        'summary': label_info['summary'],
        'engine': 'OpenCV Frame Extractor & Multi-Frame Analysis',
        'details': {
            'fps': round(fps, 1),
            'duration': f"{duration_sec}s",
            'total_frames': total_frames,
            'sampled_frames': len(frame_results),
            'dimensions': f"{width} x {height} px",
            'min_score': round(min_score, 1),
            'max_score': round(max_score, 1),
            'frame_breakdown': frame_results
        }
    }


def analyze_file(file_path: str, uploads_dir: str) -> dict:
    """
    Determines file type and executes corresponding detection pipeline.
    """
    ext = os.path.splitext(file_path)[1].lower()
    image_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}
    video_exts = {'.mp4', '.webm', '.mov', '.avi', '.mkv'}

    if ext in image_exts:
        return analyze_image(file_path)
    elif ext in video_exts:
        return analyze_video(file_path, uploads_dir)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Supported formats: {', '.join(image_exts | video_exts)}")
