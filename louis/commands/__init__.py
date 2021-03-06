from fabric.api import env

from louis.commands.packages import *
from louis.commands.users import *
from louis.commands.projects import *
from louis.commands.projects import *
from louis.commands.databases import *
from louis import conf

# This is a new config added by Louis. In order to avoid problems on
# commands using it, let's initialize it here.
env.host_config = {}

# Do not execute shell in login mode, so we can avoid warnings about stdin
# not being a tty. Currently, we don't depend on anything that requires a
# shell to be executed in login mode, so the value below for env.shell is
# safe.
#     Reference: http://docs.fabfile.org/en/0.9.1/faq.html
env.shell = "/bin/bash -c"

def install_ezl_dotfiles(user=None):
    user = user or env.user
    with settings(user=user):
        with cd('/home/%s' % user):
            if files.exists(".dotfiles"):
                if confirm(red(".dotfiles already exists. Reclone?")):
                    run("rm -rf .dotfiles")
                else:
                    return
            run("git clone https://github.com/ezl/.dotfiles.git")
            with cd('/home/%s/.dotfiles' % user):
                run('source install.sh')


def command(command="ls"):
    sudo("%s" % command)

def giddyup():
    """All.  louisconf has to be properly set up."""
    with settings(user="root"):
        init_server()
    setup_project()

deploy = giddyup

def init_server(apache=True, postgres=True):
    """
    Runs basic configuration of a virgin server.
    """
    if hasattr(conf, "timezone"):
        set_timezone(conf.timezone)
    sudo("dpkg-reconfigure locales")
    sudo("update-locale LANG=en_US.UTF-8")
    setup_hosts()
    update()
    install_debconf_seeds()
    install_basic_packages()
    config_apticron()
    config_exim()
    create_sysadmins()
    config_sudo()
    if apache:
        install_apache()
    if postgres:
        install_postgres()
    config_sshd()

def setup_hosts():
    """
    Configure /etc/hosts and /etc/hostname. Make sure that env.host is the
    server's IP address and that env.hostname is the server's hostname.
    """
    if not getattr(env, 'hostname', None):
        print "setup_hosts requires env.hostname. Skipping."
        return None
    ## the following stuff will only be necessary if we need to put entries
    ## like "1.2.3.4 lrz15" into /etc/hosts, but that may not be necessary.
    ## i'll leave the code for now, but i suspect we can delete it.
    ## sanity check: env.host is an IP address, not a hostname
    #import re
    #assert(re.search(r'^(\d{0,3}\.){3}\d{0,3}$', env.host) is not None)
    #files.append("%(host)s\t%(hostname)s" % env, '/etc/hosts', use_sudo=True)
    files.append("127.0.1.1\t%s" % env.hostname, '/etc/hosts', use_sudo=True)
    sudo("hostname %s" % env.hostname)
    sudo('echo "%s" > /etc/hostname' % env.hostname)


def apache_reload():
    """
    Do a graceful restart of Apache. Reloads the configuration files and the
    client app code without severing any active connections.
    """
    sudo('/etc/init.d/apache2 reload')


def apache_restart():
    """
    Restarts Apache2. Only use this command if you're modifying Apache itself
    in some way, such as installing a new module. Otherwise, use apache reload
    to do a graceful restart.
    """
    sudo('/etc/init.d/apache2 restart')


def make_fxn(name, ip, config):
    def fxn(user=None):
        env.host_config = config
        env.hosts = [ip]
        env.hostname = name
        if user:
            env.user = user
    fxn.__doc__ = """Runs subsequent commands on %s. Takes optional user argument.""" % name
    return fxn
for entry in conf.HOSTS:
    ip, name = entry[:2]
    if len(entry) > 2:
        config = entry[2]
    else:
        config = {}
    if not globals().has_key(name):
        globals()[name] = make_fxn(name, ip, config)
globals().pop('make_fxn')
