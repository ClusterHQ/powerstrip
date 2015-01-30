FROM        ubuntu:14.10

# Last build date - this can be updated whenever there are security updates so
# that everything is rebuilt
ENV         security_updates_as_of 2015-01-30

# Install security updates and required packages
RUN         apt-get -qy update
RUN         apt-get -qy upgrade
RUN         apt-get -qy install python-pip
RUN         apt-get -qy install python-dev
RUN         apt-get -qy install python-pyasn1
RUN         apt-get -qy install libyaml-dev
RUN         apt-get -qy install libffi-dev
RUN         apt-get -qy install libssl-dev

ADD         . /app

WORKDIR     /app

# Install requirements from the project's setup.py
RUN         python setup.py install

CMD         ["twistd", "-noy", "powerstrip.tac"]
