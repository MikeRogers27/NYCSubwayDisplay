# Recovery or creation of new instance

## Setup steps

### Setup and update pi

Commands:

    sudo apt update
    sudo apt full-upgrade
    sudo apt install git
    sudo apt-get install libopenjp2-7-dev

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

Commands:

    cd ~
    mkdir venv
    cd venv
    python -m venv NYCSubwayDisplay

### Python Requirements


### Install led-rgb-matrix



### Script setup

### Install as service


    
