# NFVCL-NG

## Requirements
 - Having OSM running on a reachable machine (See appendix A).
 - An Ubuntu (20.04+ LTS) instance where the NFVCL will be installed and run

## Installation
### 1 - Clone the repository
Since the repo is private you will need to create a token for your account before try to clone this project.
When you are ready
```commandline
git clone https://github.com/robertobru/nfvcl-ng
```
You will be promped with Username and Password. Instead of the password insert the created token.
### 2 - Preconfiguration
The first thing that should be done is updating repos
```commandline
sudo apt update
```
Then it's time to upgrade packages
```commandline
sudo apt upgrade
```

The following script will install Redis, MongoDB and Uvicorn.
Some empty folders should be created too.
```commandline
cd nfvcl-ng
chmod +x setup.sh
sudo ./setup.sh
```

Then we need to install python requirements
```commandline
pip install -r requirements.txt
```

### 3 - Edit configuration
You will need to edit NFVCL configuration (config.yaml) to match your infrastructure. Almost surely you will need to provide at least
the public NFVCL IP and change OSM credentials.


### 4 - Run the NFVCL
```commandline
python3 run.py
```
If you want the NFVCL to stay open in case you will need to use **Screen** CLI utility.


## A - OSM installation
Perform and update and an upgrade
```commandline
sudo apt update
sudo apt upgrade
```
Visit [OSM](https://osm.etsi.org/docs/user-guide/latest/01-quickstart.html#installing-osm) site and look for the latest 
version of OSM (at the moment 13)

Download the script, enable and run it (**It takes about 20 min to install OSM**)
```commandline
wget https://osm-download.etsi.org/ftp/osm-13.0-thirteen/install_osm.sh
chmod +x install_osm.sh
./install_osm.sh
```