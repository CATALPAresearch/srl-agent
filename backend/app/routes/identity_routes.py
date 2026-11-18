"""Identity endpoints for the frontend.

POST /session/identity  returns the caller's identity + token; creates an anonymous
                        standalone identity if the caller has none yet.
GET  /session/identity  returns the caller's identity (401 if none).
"""
from flask import Blueprint, jsonify, session

from ..identity import current_identity, issue_token, new_standalone_identity

identity_bp = Blueprint('identity', __name__)


def _public(identity: dict) -> dict:
    return {"userid": identity["uid"], "role": identity.get("role", "student")}


@identity_bp.route("/session/identity", methods=["POST"])
def create_or_refresh_identity():
    identity = current_identity()
    if not identity:
        identity = new_standalone_identity()
        session["identity"] = identity
    return jsonify({**_public(identity), "token": issue_token(identity)}), 200


@identity_bp.route("/session/identity", methods=["GET"])
def get_identity():
    identity = current_identity()
    if not identity:
        return jsonify({"error": "no identity"}), 401
    return jsonify(_public(identity)), 200
