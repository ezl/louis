from __future__ import with_statement
from fabric.api import run, put, sudo, env, cd, local, prompt, settings
from fabric.colors import green
from fabric.contrib import files
from louis import conf

def _install_packages(*packages):
    packages = " ".join(packages)
    print(green('Installing %s' % packages))
    sudo('DEBIAN_FRONTEND=noninteractive apt-get -y -q=2 '
         'install %s >/dev/null' % packages, shell=False)

def update():
    """
    Updates package list and installs the ones that need updates.
    """
    # Activate Ubuntu's "Universe" repositories.
    files.uncomment('/etc/apt/sources.list', regex=r'deb.*universe',
                    use_sudo=True)
    print(green('Updating package repositories'))
    sudo('apt-get update -y -q=2')
    print(green('Upgrading installed packages'))
    sudo('DEBIAN_FRONTEND=noninteractive apt-get upgrade '
          '-y -q=2 > /dev/null')


def install_debconf_seeds():
    _install_packages("debconf-utils")
    for seed_file in conf.DEBCONF_SEEDS:
        directory, sep, seed_filename = seed_file.rpartition('/')
        print(green('Installing seed: %s' % seed_filename))
        put(seed_file, '/tmp/%s' % seed_filename)
        sudo('debconf-set-selections /tmp/%s' % seed_filename)


def install_basic_packages():
    """
    Installs basic packages as specified in louisconf.BASIC_PACKAGES
    """
    _install_packages(*conf.BASIC_PACKAGES)


def config_apticron():
    """
    Adds sysadmin emails to the apticron config.
    """
    emails = ' '.join(v['email'] for k,v in conf.SYSADMINS.items())
    files.sed('/etc/apticron/apticron.conf', '"root"', '"%s"' % emails, 
              limit="EMAIL=", use_sudo=True)

def config_exim():
    """Set exim configuration type if defined by the user."""
    if hasattr(conf, "EXIM_CONFIG_TYPE"):
        files.sed('/etc/exim4/update-exim4.conf.conf', 'local',
              conf.EXIM_CONFIG_TYPE or "local", 
              limit="dc_eximconfig_configtype=", use_sudo=True)
        sudo("/etc/init.d/exim4 restart")

def config_sshd():
    """Disables password-based and root logins. Make sure that you have some
    users created with ssh keys before running this."""
    sshd_config = '/etc/ssh/sshd_config'
    files.sed(sshd_config, 'yes', 'no', limit='PermitRootLogin', use_sudo=True)
    files.sed(sshd_config, '#PasswordAuthentication yes', 'PasswordAuthentication no', use_sudo=True)
    sudo('/etc/init.d/ssh restart')


def install_apache():
    """
    Installs apache2, mod-wsgi, and mod-ssl.
    """
    pkgs = ('apache2', 'apache2-utils', 'libapache2-mod-wsgi', )
    _install_packages(*pkgs)
    sudo('virtualenv --no-site-packages /var/www/virtualenv')
    sudo('echo "WSGIPythonHome /var/www/virtualenv" >> /etc/apache2/conf.d/wsgi-virtualenv')
    sudo('a2enmod ssl')
    files.append('ServerName localhost', '/etc/apache2/httpd.conf',
                 use_sudo=True)
    sudo('/etc/init.d/apache2 reload')


def install_postgres():
    """
    Installs postgres and python mxdatetime.
    """
    pkgs = ('postgresql', 'python-egenix-mxdatetime')
    _install_packages(*pkgs)
    sudo('DEBIAN_FRONTEND=noninteractive apt-get -y -q=2 '
         'build-dep psycopg2 >/dev/null')


def patch_virtualenv(user, package_path, virtualenv_path='env'):
    """
    Symlinks package_path in virtual env's site-packages.
    """
    with settings(user=user):
        target = '/home/%s/%s/lib/python2.6/site-packages/' % (user, virtualenv_path)
        run('ln -s %s %s' % (package_path, target))

def set_timezone(timezone):
    sudo('echo "%s" > /etc/timezone' % timezone)
    sudo("dpkg-reconfigure --frontend noninteractive tzdata")
