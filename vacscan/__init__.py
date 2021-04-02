import os
import logging

from flask import Flask
from flask import Response
from flask import request
from vacscan import flaskapp

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
        DEBUG=False,
        DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
    )

    if test_config is None:
        # load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # load the test config if passed in
        app.config.from_mapping(test_config)

    # ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # a simple page that says hello
    @app.route('/hello')
    def hello():
        return 'Hello, World!'

    @app.route('/scan', methods=['GET'])
    def vacscan():
        logging.getLogger().setLevel(logging.ERROR) # FIXME
        return flaskapp.VacScanPage(request)

    @app.errorhandler(404)
    def page_not_found(e):
        # Little experiment
        return Response("{'success':0}", status=403, mimetype='application/json')

    return app

logging.getLogger().setLevel(logging.ERROR)