import os, pwd, grp
import logging

from flask import Flask
from flask import Response
from flask import request
from vacscan import flaskapp
from sys import platform



def drop_privileges(uid_name='nobody', gid_name='nogroup'):
    # https://stackoverflow.com/questions/2699907/dropping-root-permissions-in-python
    logging.debug("[drop_privileges] Dropping privileges to %s, %s" % (uid_name, gid_name))
    if platform != "linux" and platform != "linux2":
        logging.debug("[drop_privileges] No action, not linux.")
        return;

    if os.getuid() != 0:
        logging.debug("[drop_privileges] No action, not root.")
        # We're not root so, like, whatever dude
        return

    # Get the uid/gid from the name
    running_uid = pwd.getpwnam(uid_name).pw_uid
    running_gid = grp.getgrnam(gid_name).gr_gid

    # Remove group privileges
    os.setgroups([])

    # Try setting the new uid/gid
    os.setgid(running_gid)
    os.setuid(running_uid)

    # Ensure a very conservative umask
    old_umask = os.umask(077)
    logging.debug("[drop_privileges] Successfully dropped privileges.")

def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=b'_5#@7L"A4Qdz\n\xec]/',
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

    drop_privileges();
    return app

logging.getLogger().setLevel(logging.ERROR)