"""Static file serving routes."""
import json
import os

from flask import Blueprint, send_from_directory

from ._paths import FRONTEND_DIR, LTI_STATIC_DIR, STATIC_DIR

static_bp = Blueprint('static_files', __name__)


@static_bp.route('/')
def index():
    admin_password = os.getenv("ADMIN_PASSWORD", "admin")
    with open(os.path.join(FRONTEND_DIR, 'index.html'), 'r', encoding='utf-8') as f:
        html = f.read()
    injection = f'<script>window.SRL_ADMIN_PASSWORD = {json.dumps(admin_password)};</script>\n'
    html = html.replace('</head>', injection + '</head>', 1)
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


@static_bp.route('/frontend/<path:filename>')
def serve_frontend_assets(filename):
    """Serve frontend assets (core stubs, etc.)."""
    return send_from_directory(FRONTEND_DIR, filename)


@static_bp.route('/static/lti/<path:filename>')
def serve_lti_static(filename):
    """Serve LTI static assets (AMD bundle + core stubs for Moodle LTI mode)."""
    return send_from_directory(LTI_STATIC_DIR, filename)


@static_bp.route('/static/favicon.ico')
def serve_favicon():
    return send_from_directory(STATIC_DIR, 'favicon.ico')


@static_bp.route('/health', methods=['GET'])
def health():
    from flask import jsonify
    return jsonify({'status': 'ok', 'service': 'srl-agent'}), 200
