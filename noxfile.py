# We include this so that we can use the `libs` module in the `tests` directory
import sys
sys.path.append('tests')

from lib import *

import os
import nox
import shutil
import pathlib
import subprocess

PACKAGE_BUILT = False

CURRENT_PATH = pathlib.Path(__file__).parent

DB_CREATED = False

DATA_PATH = CURRENT_PATH / 'tests/data'
DB_PATH = DATA_PATH / 'db'

def create_db():
    """ Creates a nexus database in the src/tests/data directory
    """
    global DB_CREATED

    if DB_CREATED: return

    # Remove the db
    if DB_PATH.exists():
        shutil.rmtree(DB_PATH)

    # Now create the database
    subprocess.run([
            "nexus",
            "testdb",
            "create",
            "admin",
            "admin",
            "--cbdir",
            str(DATA_PATH.resolve()),
        ])

    DB_CREATED = True

@nox.session()
def build(session):
    global PACKAGE_BUILT
    PACKAGE_BUILT = True
    session.run("poetry", "build", )

@nox.session(python=['pypy3', '3.6', '3.7', '3.8', '3.9', '3.10', '3.11' ])
def tests(session):
    global PACKAGE_BUILT

    create_db()

    #session.run("python", "/root/install-poetry.py")
    #session.install("pytest")

    # Build the package if not built yet in this session
    #if not PACKAGE_BUILT:
    #    session.run("poetry", "build", external=True)
    #    PACKAGE_BUILT = True
    session.run("poetry", "install", "--extras", "all", external=True)

    # Install the package
    #dist_path = pathlib.Path('dist')
    #wheels = sorted(dist_path.glob('*.whl'))
    #newest_wheel = str(wheels[-1].resolve())
    #session.install(newest_wheel)

    # Install the modules that are required for our tests
    #session.install('pytest>=4.6.11','Faker>=13.3.4','passlib>=1.7.4')

    # Let's fire up a copy of nexus
    p = launch_nexus()

    # Finally, run the tests
    try:
        session.run("pytest")

    finally:
        # And tear nexus down now that'we re done
        p.terminate()
        p.wait()
