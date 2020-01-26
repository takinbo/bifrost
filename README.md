# Bifrost
Bifrost is an invite-based lightning network channel-opening service written in 
the Python programming language.

[Lnd](https://github.com/lightningnetwork/lnd/) is currently supported as the backend node for channel opening to other 
wallets and nodes.

Due to the low througput of the application, SQLite is database backend used to 
store invites and track usage. It should be trivial to change this if you know 
what you're doing. Please see the `DATABASE_URL` parameter in the configuration 
options below. Please note that you'll need to install the necessary packages to 
support your chosen database backend.


## Instalation of dependencies

To install all the required dependencies needed to run Bifrost, run the following 
command. This may also be done within a `virtualenv`.

```
$ pip install -r requirements.txt
```


## Configuration

Once all the dependencies have been installed, you can then create a `.env` file 
that will contain all the configuration parameters for your instance.

The following are a list of currently available configuration options and a 
short explanation of what each does.

`DATABASE_URL` (required; e.g. *sqlite:///bifrost.db*)
This specifies the SQLite 3 file and path to use for storing invites for Bifrost.

`BASE_URL` (required)
This parameter defines the base url to use in constructing urls for use within 
the application. You should set it to a url of the form https://yourdomain.tld. 
The lnurl spec only supports https urls so be sure to make this a https url or 
your users may have problems connecting to the service.

`NODE_URI` (required; in the form *pubkey@host/ip:port*)
The node uri is an identifier for your lightning network node, you can obtain this 
by running the command `lncli getinfo` and copying any of the values in `uris`.

`LND_NETWORK` (optional; defaults to *mainnet*)
This selects the network that your node is configured for. This may take any of 
the supported values for your lnd node.

`LND_GRPC_HOST` (optional; defaults to *localhost*)
If your node is not on your local machine (say on a different server), you'll 
need to change this value to the appropriate value.

`LND_GRPC_PORT` (optional; defaults to *10009*)
If the GRPC port for your node was changed to anything other than the default 
you'll need to update this as well.

`LND_FEE_RATE` (optional)
In cases, where you want a fixed fee rate for opening channels, you can set this 
parameter to an integer representing your chosen fee rate in sats/byte.

`LND_SPEND_UNCONFIRMED` (optional; defaults to *True*)
Takes values of either *True* or *False* and determines if your node is allowed 
to spend unconfirmed outputs when opening channels.

`LND_FORCE_PRIVATE` (optional; defaults to *False*)
The lnurl spec allows the requesting node to determine whether it wants a public 
or private channel. If you want to restrict this choice to private channels only, 
then you'll need to set the value of this parameter to *True*.


## Initializing the database

To initialize the database which would create the database file and all the 
necessary tables, run the command:

```
$ ./app.py initdb
```


## Loading invites

Invites codes could be any unique combination of characters and numbers which 
form a part of a URL that gets shared with your users. The invite file itself is 
a CSV file containing the invite code, followed by the opening channel capacity 
(in sats) and then followed by the amount (in sats) to push to the remote wallet 
when the channel is open. If you don't want to push any amount to the remote 
wallet, this value should be set to *0*. Below is an example of a CSV file that 
can be imported into Bifrost.

```
Ogh5sh,500000,10000
xuJei1,500000,0
iWae0o,500000,0
Aikio7,500000,0
tiew6O,500000,0
```

The first line with invite code *Ogh5sh* will open a channel with capacity 
500,000 sats with 10,000 sats pushed to the remote wallet. The invite URL to 
share will be of the form *BASE_URL/i/invite_code* an example of which will be: 
https://yourdomain.tld/i/Ogh5sh.

To load the invites into the database, run the command:

```
$ ./app.py load invite_file.csv
```

Where *invite_file.csv* is the file name and path to a CSV file containing the 
invites.


## Running the application server

After installing the dependencies, configuring the application, initializing 
the database and loading the invites, you can start the application backend by 
running the command:

```
$ ./app.py run
```
