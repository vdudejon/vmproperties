# vmproperties
A python script to gather certain VM properties and insert them into a database

## To Use
Add a .env file to your directory with the following:
```
VCENTER=<vCenter>
VSPHERE_USER=<vCenter user>
VSPHERE_PASSWORD=<vCenter Password>
DB_HOST=<Address to DB Server>
DB_PORT=<DB Port>
DB_USER=<DB User>
DB_PASSWORD=<DB Password>
DB_NAME=<Database Name>
```

Run `docker build -t vmproperties .`
Run `docker run --rm --env-file .env -it vmproperties`

The script will connect to your vCenter, gather the vm properites, then insert them into your database.

An example nomad file is included to show how to run it in Nomad utilizing vault secrets.
