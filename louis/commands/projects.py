from __future__ import with_statement

from fabric.operations import prompt
from fabric.contrib.console import confirm
from fabric.api import run, put, sudo, env, cd, local, prompt, settings
from fabric.contrib import files
from fabric.colors import green, red
from louis import conf
import louis.commands
from louis.commands.users import add_ssh_keys
from louis.commands.databases import setup_postgres


branch = conf.GIT_BRANCH
project_name = conf.PROJECT_NAME
project_username = conf.PROJECT_USERNAME or ('%s-%s' % (project_name, branch))
conf.PROJECT_USERNAME = project_username
requirements_path = '/home/%s/%s/deploy/requirements.txt' % (project_username, project_name)
# requirements_path = '%s/deploy/requirements.txt' % project_name
extra_project_requirements = getattr(conf, "install_extra_project_requirements", None)
git_url = conf.GIT_URL
media_directory = '/home/%s/%s/media/' % (project_username, project_name)
# media_directory = '%s/media/' % project_name
apache_server_name = conf.APACHE_SERVER_NAME
apache_server_alias = conf.APACHE_SERVER_ALIAS
server_admin = conf.APACHE_SERVER_ADMIN
wsgi_file_path = '/home/%s/%s.wsgi' % (project_username, project_username)
django_settings = env.host_config.get("django-settings", conf.DJANGO_SETTINGS_MODULE) # or production-settings
env_path = '.virtualenvs/%s' % project_name


def setup_project_user(project_username=project_username):
    """
    Create a crippled user to hold project-specific files.
    """
    with settings(warn_only=True):
        check_user = sudo('grep -e "%s:" /etc/passwd' % project_username)
    if not check_user.failed:
        return
    sudo('adduser --gecos %s --disabled-password %s' % ((project_username,)*2))
    sudo('usermod -a -G www-data %s' % project_username)
    for u, s in conf.SYSADMINS.items():
        add_ssh_keys(target_username=project_username, ssh_key_path=s['ssh_key_path'])
    with settings(user=project_username):
        run('mkdir -p .ssh')
        run('ssh-keygen -t rsa -f .ssh/id_rsa -N ""')
        # so that we don't get a yes/no prompt when checking out repos via ssh
        files.append(['Host *', 'StrictHostKeyChecking no'], '.ssh/config')
        run('mkdir log')


def setup_project_virtualenv(project_username=project_username,
                             env_path=env_path,
                             site_packages=False):
    """
    Create a clean virtualenv for a project in the target directory. The target
    directory is relative to the project user's home dir and defaults to env ie
    the venv will be installed in /home/project/env/
    """
    with settings(user=project_username):
        with cd('/home/%s' % project_username):
            if site_packages:
                run('virtualenv %s' % env_path)
            else:
                 run('virtualenv --no-site-packages %s' % env_path)
            run('%s/bin/easy_install -U setuptools' % env_path)
            run('%s/bin/easy_install pip' % env_path)


def install_project_requirements(project_username=project_username,
                                 requirements_path=requirements_path,
                                 env_path=env_path):
    """
    Installs a requirements file via pip.

    The requirements file path should be relative to the project user's home

    directory and it defaults to project_username/deploy/requirements.txt
    The env path should also be relative to the project user's home directory and
    defaults to env.
    """
    if extra_project_requirements:
        extra_project_requirements()
    with settings(user=project_username):
        with cd('/home/%s' % project_username):
            run('%s/bin/easy_install -i http://downloads.egenix.com/python/index/ucs4/ egenix-mx-base' % env_path)
            run('%s/bin/pip install -r %s' % (env_path, requirements_path))

def setup_project_code(project_name=project_name,
                       project_username=project_username,
                       git_url=git_url,
                       branch=branch):
    """
    Check out the project's code into its home directory. Target directory will
    be relative to project_username's home directory. target directory defaults
    to the value of project_username ie you'll end up with the code in
    /home/project/project/
    """
    with cd('/home/%s' % project_username):
        with settings(user=project_username):
            if files.exists(project_name):
                print(red('Destination path already exists ie the repo has been cloned already.'))
                if confirm(red('Delete existing repo and re-clone?')):
                   run('rm -rf %s' % project_name)
                else:
                    return
            run('git clone %s %s' % (git_url, project_name))
            with cd('%s' % project_name):
                #run('git submodule update --init') # --recursive')
                run('git submodule init')
                run('git submodule update')
                # checkout and update all remote branches, so that the deployment 
                # can be any one of them
                branches = run('git branch -r').split('\n')
                for b in branches:
                    if 'master' in b or 'HEAD' in b:
                        # all remote branches except HEAD and master since those
                        # by default
                        continue
                    r, sep, branch_name = b.strip().rpartition('/')
                    run('git branch %s --track origin/%s' % (branch_name, branch_name))
                run('git checkout %s' % branch)


def setup_project_apache(project_name=project_name,
                         project_username=project_username,
                         apache_server_name=apache_server_name,
                         apache_server_alias=apache_server_alias,
                         django_settings=django_settings,
                         server_admin=server_admin,
                         media_directory=media_directory,
                         env_path=env_path,
                         branch=branch):
    """
    Configure apache-related settings for the project.
    
    This will render every  *.apache2 file in the current local directory as a
    template with project_name, project_username, branch, server_name and
    server_alias as context. It'll put the rendered template in apache
    sites-available.
    
    It will also render any *.wsgi file with the same context. It will put the
    rendered file in the project user's home directory.

    media_directory should be relative to the project user's home directory. It
    defaults to project_username/media ie you'd end up with
    /home/project/project/media/
    """
    with cd('/home/%s' % project_username):
        # permissions for media/
        sudo('chgrp www-data -R %s' % media_directory)
        sudo('chmod g+w %s' % media_directory)
    context = {
        'project_name': project_name,
        'project_username': project_username,
        'server_name': apache_server_name,
        'server_alias': apache_server_alias,
        'django_settings': django_settings,
        'env_path': env_path,
        'branch': branch,
        'server_admin': server_admin,
    }
    # apache config
    for config_path in local('find $PWD -name "*.apache2"').split('\n'):
        d, sep, config_filename = config_path.rpartition('/')
        config_filename, dot, ext = config_filename.rpartition('.')
        config_filename = '%s-%s.%s' % (config_filename, branch, ext)
        # screw it, use this username instead.  throw away the given name entirely.
        config_filename = '%s.%s' % (project_username, ext)
        dest_path = '/etc/apache2/sites-available/%s' % config_filename
        if not files.exists(dest_path, use_sudo=True):
            files.upload_template(config_path, dest_path, context=context, use_sudo=True)
            sudo('a2ensite %s' % config_filename)
    # wsgi file
    for wsgi_path in local('find $PWD -name "*.wsgi"').split('\n'):
        d, sep, wsgi_filename = wsgi_path.rpartition('/')
        wsgi_filename, dot, ext = wsgi_filename.rpartition('.')
        # apache2 file has this filename set already.
        # wsgi_filename = '%s-%s.%s' % (wsgi_filename, branch, ext)
        wsgi_filename = '%s.%s' % (project_username, ext)
        dest_path = '/home/%s/%s' % (project_username, wsgi_filename)

        if not files.exists(dest_path, use_sudo=True):
            files.upload_template(wsgi_path, dest_path, use_sudo=True, context=context)
            sudo('chown %s:%s %s' % (project_username, 'www-data', dest_path))
            sudo('chmod 755 %s' % dest_path)
    with settings(warn_only=True):
        check_config = sudo('apache2ctl configtest')
    if check_config.failed:
        print(red('Invalid apache configuration! The requested configuration was installed, but there is a problem with it.'))
    else:
        louis.commands.apache_reload()


def setup_project(project_name=project_name,
                  project_username=project_username,
                  git_url=git_url,
                  apache_server_name=apache_server_name,
                  apache_server_alias=apache_server_alias,
                  django_settings=django_settings,
                  branch=branch,
                  requirements_path=requirements_path):
    """
    Creates a user for the project, checks out the code and does basic apache config.
    """
    setup_project_user(project_username)
    setup_postgres()
    print(green("Here is the project user's public key:"))
    run('cat /home/%s/.ssh/id_rsa.pub' % project_username)
    print(green("This script will attempt a `git clone` next."))
    prompt(green("Press enter to continue."))
    setup_project_code(project_name, project_username, git_url, branch)
    setup_project_virtualenv(project_username)
    install_project_requirements(project_username, requirements_path)
    with settings(user=project_username):
        with cd('/home/%s/%s' % (project_username, project_name)):
            run('/home/%s/%s/bin/python manage.py syncdb --settings=%s --noinput' % (project_username, env_path, django_settings))
            # Don't make it an error if the project isn't using south
            with settings(warn_only=True):
                run('/home/%s/%s/bin/python manage.py migrate --settings=%s' % (project_username, env_path, django_settings))
    setup_project_apache(project_name, project_username, apache_server_name, apache_server_alias, django_settings, branch=branch)
    update_project()
    print(green("""Project setup complete. You may need to patch the virtualenv
    to install things like mx. You may do so with the patch_virtualenv command."""))


def delete_project_code(project_name=project_name,
                        project_username=project_username):
    """
    Deletes /home/project_username/target_directory/ target_directory defaults
    to project_username if not given ie /home/project/project/
    """
    sudo('rm -rf /home/%s/%s' % (project_username, project_name))


def get_project_head(project_name=project_name,
                 project_username=project_username):
    """See what remote project's last commit is."""
    with settings(user=project_username):
        with cd('/home/%s/%s' % (project_username, project_name)):
            run('git log -n1')

def update_project(project_name=project_name,
                   project_username=project_username,
                   branch=branch,
                   wsgi_file_path=wsgi_file_path,
                   django_settings=django_settings,
                   update_requirements=True):
    """
    Pull the latest source to a project deployed at target_directory. The
    target_directory is relative to project user's home dir. target_directory
    defaults to project_username ie /home/project/project/
    The wsgi path is relative to the target directory and defaults to
    deploy/project_username.wsgi.
    """
    print ("Using %s for django settings module." % django_settings)
    template_context = {
        "env_path": env_path,
        "project_username": project_username,
        "project_name": project_name,
    }
    with settings(user=project_username):
        with cd('/home/%s/%s' % (project_username, project_name)):
            run('git checkout %s' % branch)
            run('git pull')
            run('git submodule update')
            # Don't make it an error if the project isn't using south
            with settings(warn_only=True):
                run('/home/%s/%s/bin/python manage.py migrate --settings=%s' % (project_username, env_path, django_settings))
            if update_requirements is True:
                install_project_requirements(project_username, requirements_path,  env_path)
            run('touch %s' % wsgi_file_path)
            if hasattr(conf, "CRONTAB"):
                print "Setting up crontab"
                # FIXME It is kind hacky the creation of a temporary file
                # here, but we need to make it consistent with LOGROTATE.
                temp_dest = "/tmp/%s.crontab" % project_name
                # Fabric tries to keep a backup of the same file sometimes
                with settings(warn_only=True):
                    files.upload_template(conf.CRONTAB, temp_dest, context=template_context)
                run("crontab %s && rm %s" % (temp_dest, temp_dest))
    if hasattr(conf, "LOGROTATE"):
        print "Setting up logrotate"
        files.upload_template(conf.LOGROTATE, "/etc/logrotate.d/%s" % project_name, context=template_context, use_sudo=True)
