# VMware vSphere VM Properties Collector

## Overview

This Python script allows you to collect and store various properties of virtual machines (VMs) in a VMware vSphere environment. It uses the VMware vSphere API, specifically the `pyVmomi` library, to retrieve information about VMs and stores it in a PostgreSQL database. This information can be useful for inventory management, monitoring, and reporting purposes.

## Features

- Retrieves a wide range of VM properties, including name, UUID, power state, resource allocation, hardware configuration, and more.
- Supports multiple vCenter servers for collecting VM information.
- Stores collected VM data in a PostgreSQL database for easy querying and reporting.
- Updates existing VM records based on UUID or adds new records if the VM doesn't exist in the database.
- Deletes VM records from the database if they no longer exist in the vCenter inventory.
- Uses multi-threading for efficient VM data collection, reducing collection time significantly.
- Provides detailed logging to help track the progress and identify any issues during the collection process.

## Prerequisites

Before running the script, make sure you have the following prerequisites set up:

- VMware vSphere environment with access to vCenter servers.
- Python 3.x installed.
- Necessary Python libraries (install using `pip install -r requirements.txt`)
- PostgreSQL database where VM data will be stored.

## Usage

1. Clone this repository to your local machine:

   ```bash
   git clone https://github.com/vdudejon/vsphere-vm-properties-collector.git
   cd vsphere-vm-properties-collector/app
   ```
 2. Configure your environmental variables by adding a .env file with the following:
    ```
    VCENTER=Set the hostname or IP address of your vCenter server.
    VSPHERE_USER=Your vSphere username
    VSPHERE_PASSWORD=Your vSphere password
    DB_HOST=Hostname or IP address of your PostgreSQL server
    DB_PORT=Port number of your PostgreSQL server
    DB_USER=Your PostgreSQL database username
    DB_PASSWORD=Your PostgreSQL database password
    DB_NAME=Name of the PostgreSQL database where VM data will be stored
    ```
  3. Run the script

     ```bash
     python vm_properties_collector.py
     ```
     OR
     ```bash
     docker build -t vsphere-vm-properties-collector .
     docker run --rm --env-file .env -it vsphere-vm-properties-collector
     ```
     
   5. The script will connect to your vCenter server, collect VM properties, and store them in the specified PostgreSQL database

## Database Schema
The script creates a table named vme_watchman_properties in the PostgreSQL database to store VM data. The table schema matches the data structure of the VM data class used in the script.

## Use with Hashicorp Nomad
You can use HashiCorp Nomad to schedule and run the VMware vSphere VM Properties Collector as a batch job. This allows you to periodically collect VM properties from multiple vCenter servers and store the data in a PostgreSQL database. An example nomad file is included to show how to run it in Nomad utilizing vault secrets.

In this Nomad job specification:

   - `variable "vcenters"` Define an array of vCenter server FQDNs that you want to collect VM properties from.
   - `job "gather_vmproperties"` Create a Nomad job named "gather_vmproperties" with periodic scheduling.
   - `dynamic "group"` Dynamically create a task group for each vCenter server specified in the vcenters variable.
   - `task "vmproperties"` Define a task named "vmproperties" that runs the VMware vSphere VM Properties Collector in a Docker container.
   - Configure the Docker image you want to use by replacing `<DOCKER IMAGE HERE>`.
   - Use HashiCorp Vault to retrieve secrets and configure environment variables for connecting to vCenter and the PostgreSQL database.
   - Set the `VCENTER` environment variable to the vCenter server being processed by this task group.
   - Allocate CPU and memory resources according to your requirements.  I have found that 600MB is required for environments as large as 22,000 VMs.

With this Nomad job specification, you can easily schedule and manage the collection of VM properties from multiple vCenter servers using HashiCorp    -    - Nomad. Adjust the configuration to match your specific environment and requirements

## Contributing
Feel free to contribute to this project by opening issues or submitting pull requests. Contributions, bug reports, and feature requests are welcome!

## License
This project is licensed under the MIT License - see the LICENSE file for details.



An example nomad file is included to show how to run it in Nomad utilizing vault secrets.
