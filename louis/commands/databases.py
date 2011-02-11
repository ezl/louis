from __future__ import with_statement

from fabric.api import run, put, sudo, env, cd, local, prompt, settings
from fabric.contrib import files
from louis import conf


def create_postgres_user(username=conf.POSTGRES_USERNAME, password=conf.POSTGRES_PASSWORD):
    """
    Creates a plain postgres user: nosuperuser, nocreaterole, createdb.
    """
    psql_string = "CREATE ROLE %s PASSWORD '%s' NOSUPERUSER CREATEDB NOCREATEROLE INHERIT LOGIN;" % (username, password)
    sudo('echo "%s" | psql' % psql_string, user='postgres')


def delete_postgres_user(username):
    """
    Deletes a postgres user.
    """
    sudo('dropuser %s' % username, user='postgres')


def create_postgres_db(owner=conf.POSTGRES_USERNAME, dbname=conf.POSTGRES_DBNAME):
    """
    Creates a postgres database given its owner (a postgres user) and the name
    of the database.
    """
    sudo('createdb -E UTF8 -T template0 -O %s %s' % (owner, dbname), user='postgres')

def drop_postgres_db(dbname):
    """
    Drops a postgres database.
    """
    sudo('dropdb %s' % dbname, user='postgres')

def setup_postgres(project_name=None, password=None, dbname=None):
    """
    By default, postgres username will be the project name.
    postgres dbname == postgres username
    """
    # F it.  I'm bored.
    create_postgres_user()
    create_postgres_db()
    # create_postgres_user(username=project_name, password=password)
    # create_postgres_db(owner=project_name, dbname=project_name)

