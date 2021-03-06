#!/bin/bash

#
# Script to install ecoControl onto a Debian 7.6 or Ubuntu 14.04 system.
#
# curl -sL https://raw.github.com/SEC-i/ecoControl/master/autoinstaller.sh | bash
#

# Exit in case one command fails
set -e

cat <<EOF
===============================================
    Welcome to the ecoControl Autoinstaller

  Note: This script uses sudo at some points.
===============================================
EOF

# Trigger password dialog
sudo true || exit 1

IS_DEBIAN=$(( $(cat /etc/issue | grep "Debian" | wc -l) > 0 ))

# Prepare system to support PostgreSQL 9.3 or higher
if (( $( psql --version 2>/dev/null | grep '9.3\|9.4\|9.5\|9.6' | wc -l ) > 0 )); then
    CODENAME=$(lsb_release -cs 2>/dev/null)
    # Parse os-release (unreliable, does not work on Ubuntu)
    if [ -z "$CODENAME" -a -f /etc/os-release ]; then
        . /etc/os-release
        # Debian: VERSION="7.0 (wheezy)"
        # Ubuntu: VERSION="13.04, Raring Ringtail"
        CODENAME=$(echo $VERSION | sed -ne 's/.*(\(.*\)).*/\1/')
    fi
    # Guess from sources.list
    if [ -z "$CODENAME" ]; then
        CODENAME=$(grep '^deb ' /etc/apt/sources.list | head -n1 | awk '{ print $3 }')
    fi
    # Complain if no result yet
    if [ -z "$CODENAME" ]; then
        echo "Could not determine the distribution codename."
        exit 1
    fi

    echo "Writing /etc/apt/sources.list.d/pgdg.list ..."
    echo "echo deb \"http://apt.postgresql.org/pub/repos/apt/ $CODENAME-pgdg main\" > /etc/apt/sources.list.d/pgdg.list" | sudo bash

    sudo apt-get install ca-certificates
    curl -sL https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
    sudo apt-get update
fi

# Prepare Debian system to support Node.js
if  [ $IS_DEBIAN ] && [ ! $( command -v npm >/dev/null 2>&1 ) ] ; then
    curl -sL https://deb.nodesource.com/setup | sudo bash
fi

# Install packages
sudo apt-get install -y git python-pip python-dev libpq-dev nodejs postgresql-9.3 gfortran libatlas-dev libatlas3gf-base liblapack-dev

# Install bower
if ! command -v bower >/dev/null 2>&1; then
    sudo npm install -g bower
fi

# Clone repository
if [ ! -d "ecoControl" ]; then
    git clone https://github.com/SEC-i/ecoControl.git
fi

# Change directory
cd ecoControl/

# Install all Python dependencies
echo "Installing Python dependencies..."
sudo pip install -r requirements.txt

# Install all JavaScript dependencies
echo "Installing JavaScript dependencies..."
git config --global url."https://".insteadOf git:// #prevent firewall errors by using https
bower install --config.interactive=false -q --allow-root || exit 0 # ignore bower warnings
git config --global --unset url."https://".insteadOf #and change back

# Make sure LD_LIBRARY_PATH is available
# This is required to be able to compile the Holt Winters extension
if [ ! $LD_LIBRARY_PATH ]; then
    export LD_LIBRARY_PATH=/usr/lib/openblase-base
fi

# Setup database
if [ $(sudo -u postgres psql template1 -c '\du' | grep ecocontrol | wc -l) -eq 0 ]; then
    echo "Creating database user"
    sudo -u postgres psql -c "CREATE ROLE ecocontrol LOGIN PASSWORD 'sec-i';"
fi

if [ $(sudo -u postgres psql -l | grep ecocontrol | wc -l) -eq 0 ]; then
    echo "Creating database user"
    sudo -u postgres createdb --owner=ecocontrol ecocontrol
fi

echo "Creating all database tables for ecoControl..."
python manage.py syncdb --noinput

cat <<EOF

===============================================
            ecoControl is ready!

 However, don't forget to change all passwords
 if you want to use it in production!

 You should now be able to start a server by
 executing the following commands:

    $ cd ecoControl/
    $ python manage.py runserver
===============================================

EOF