# Recovery or creation of new instance

## Setup steps

### Setup and update pi

Commands:

    sudo apt update
    sudo apt full-upgrade
    sudo apt install git
    sudo apt-get install libopenjp2-7-dev
    sudo apt-get remove bluez bluez-firmware

### Disable sound

Edit/create this file

    cd /etc/modprobe.d
    sudo nano alsa-blacklist.conf

to contain this line

    blacklist snd_bcm2835

then reboot

    sudo reboot

Edit this file
 
    sudo nano /boot/firmware/config.txt

to contain the line

    dtparam=audio=off

and reboot again

    sudo reboot

### GitHub setup and initial clone

Follow this guide to create a new key: 
https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent

I call my key ~/.ssh/id_github

    ssh-keygen -t ed25519 -C "<email>"
    eval "$(ssh-agent -s)"
    ssh-add ~/.ssh/id_github

Now follow this guide to add to GitHub:
https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account

    cat ~/.ssh/id_github.pub

Now clone the repo
    
    cd ~
    mkdir src
    cd src
    git clone git@github.com:MikeRogers27/NYCSubwayDisplay.git

### Virtual env

Setup a new virtual python env

    cd ~
    mkdir venv
    cd venv
    python -m venv NYCSubwayDisplay

### Install rpi-rgb-led-matrix

Setup pre-requisites for rpi-rgb-led-matrix

    sudo apt install libgraphicsmagick++-dev
    sudo apt install python3-dev python3-setuptools cython3 

Download

    cd ~/src
    git clone https://github.com/hzeller/rpi-rgb-led-matrix
    git checkout 2183513a067599d6c0b7339cd6c6eef24cc878b0
    
Build the project using the standard hardware profile

    cd rpi-rgb-led-matrix
    make build-python

Install to the python virtual env

    source ~/venv/NYCSubwayDisplay/bin/activate
    sudo make install-python

### Python Requirements

Install python requirements into the virtual env

    source ~/venv/NYCSubwayDisplay/bin/activate
    pip install -r ~/src/NYCSubwayDisplay/requirements.txt

### Script setup

Create a new file: ~/run-matrix.sh

```
#!/bin/bash

# wait to see if we're online
for i in {1..50}; do ping -c1 www.google.com &> /dev/null && break; done

# add ssh credentials
eval "$(ssh-agent -s)"
ssh-add ${HOME}/.ssh/id_github

# get latest changes
cd ${HOME}/src/NYCSubwayDisplay/
git pull

# run
export PYTHONPATH=${PYTHONPATH}:${HOME}/src/rpi-rgb-led-matrix/bindings/python
export OWM_API_KEY=<Key from https://home.openweathermap.org/api_keys>
export SGO_API_KEYS=<Key from https://sportsgameodds.com/, comma separated>
export RPA_API_KEY=<Key from https://rapidapi.com/>
source ${HOME}/venv/NYCSubwayDisplay/bin/activate
sudo --preserve-env=PYTHONPATH,OWM_API_KEY,SGO_API_KEYS,RPA_API_KEY /home/pi/venv/NYCSubwayDisplay/bin/python main.py --led-gpio-mapping=adafruit-hat-pwm --led-rows=32 --led-cols=64 --led-rgb-sequence=RBG --led-brightness=40 --led-slowdown-gpio=1  --led-no-drop-privs
```

Now change to executable permissions:

    chmod +x ~/run-matrix.sh

### Install as service

Create the log dir

    mkdir ~/logs

Make a service configuration file

    sudo nano /lib/systemd/system/matrix.service

with this contents

```
[Unit]
Description=LED Matrix Runner
Wants=network.service
Requires=network-online.target
After=multi-user.target network.target network-online.target

[Service]
Type=idle
ExecStart=/home/pi/run-matrix.sh
User=pi
Group=pi
StandardOutput=append:/home/pi/logs/matrix.log
StandardError=append:/home/pi/logs/matrix_err.log

[Install]
WantedBy=multi-user.target
```

Then enable the service
    
    sudo systemctl daemon-reload
    sudo systemctl enable matrix.service
    sudo reboot

Commands use disable, start, stop etc

    sudo systemctl start matrix.service

For convenience, you can also add these lines to your .bashrc file to start 
the ssh-agent and add your key:

    # add ssh credentials
    eval "$(ssh-agent -s)"
    ssh-add ${HOME}/.ssh/id_github


