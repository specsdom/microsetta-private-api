#!/usr/bin/env python3
import secrets

from microsetta_private_api.config_manager import SERVER_CONFIG
from flask import jsonify
from werkzeug.utils import redirect

from microsetta_private_api.exceptions import RepoException

"""
Basic flask/connexion-based web application

Modified from https://github.com/zalando/connexion/blob/master/examples/swagger2/oauth2/app.py  # noqa: E501

"""

import connexion
from microsetta_private_api.util.util import JsonifyDefaultEncoder


def handle_422(repo_exc):
    return jsonify(code=422, message=str(repo_exc)), 422


def build_app():
    # Create the application instance
    app = connexion.FlaskApp(__name__)

    # Read the microsetta api spec file to configure the endpoints
    app.add_api('api/microsetta_private_api.yaml', validate_responses=True)

    # ---
    # Example Client Settings
    app.add_api('example/client.yaml', validate_responses=True)
    flask_secret = SERVER_CONFIG["FLASK_SECRET_KEY"]
    if flask_secret is None:
        print("WARNING: FLASK_SECRET_KEY must be set to run with gUnicorn")
        flask_secret = secrets.token_urlsafe(16)
    app.app.secret_key = flask_secret
    app.app.config['SESSION_TYPE'] = 'memcached'
    # ---

    # Set default json encoder
    # Note: app.app is the actual Flask application instance, so any Flask
    # settings have to be set there.
    app.app.json_encoder = JsonifyDefaultEncoder

    # Set mapping from exception type to response code
    app.app.register_error_handler(RepoException, handle_422)

    @app.route('/americangut/static/<path:filename>')
    def reroute_americangut(filename):
        # This is dumb as rocks, but it fixes static images referenced in
        # surveys without a schema change.
        return redirect('/static/' + filename)
    return app


def run(app):
    if SERVER_CONFIG["ssl_cert_path"] and SERVER_CONFIG["ssl_key_path"]:
        ssl_context = (
            SERVER_CONFIG["ssl_cert_path"], SERVER_CONFIG["ssl_key_path"]
        )
    else:
        ssl_context = None

    app.run(
        port=SERVER_CONFIG['port'],
        debug=SERVER_CONFIG['debug'],
        ssl_context=ssl_context
    )


# If we're running in stand alone mode, run the application
if __name__ == '__main__':
    app = build_app()
    run(app)
