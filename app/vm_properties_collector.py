from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vmodl, vim
from dataclasses import dataclass, field, fields
from typing import List
from sqlalchemy import create_engine, Column, Integer, String, MetaData, Table, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from vcenter_functions import connect_vcenter, get_all_vms, get_all_vm_uuids, get_custom_attribute, get_vm_datacenter, get_vm_by_uuid, get_vm_datastore
import multiprocessing
import logging
import sys
import urllib.parse
import psycopg2
import uuid
import re
import time
import concurrent.futures
import os
from dotenv import load_dotenv
# Load environmental variables from the .env file
load_dotenv()

# A dataclass containing all the info we want about a VM
@dataclass
class VM(): 
    name:                   str = ""
    vcenter:                str = ""
    cloud_name:             str = ""
    dns_name:               str = ""
    vm_uuid:                str = ""
    vm_host:                str = ""
    parent_id:              str = ""
    vc_cluster:             str = ""
    vc_datacenter:          str = ""
    attribute_uuid:         str = ""
    powerstate:             str = ""
    connectionstate:        str = ""
    datastorecluster:       str = ""
    haprotected:            bool = False
    numcpu:                 int = 0
    cpulimit:               int = 0
    cpureservation:         int = 0
    cpushares:              str = "normal"
    cpuhotaddenabled:       bool = False
    memorymb:               int = 0
    memlimit:               int = 0
    memreservation:         int = 0
    memshares:              str = "normal"
    memhotaddenabled:       bool = False
    hardwareversion:        str = ""
    vmpath:                 str = ""
    vmpathname:             str = ""
    snapshot:               bool = False
    consolidationneeded:    bool = False
    sanreplicated:          bool = False
    srmreplicated:          bool = False
    srmplaceholder:         bool = False
    toolsstatus:            str = ""
    toolsversionstatus:     str = ""
    toolsversion:           int = 0
    guestfamily:            str = ""
    guestfullname:          str = ""
    osconfigfullname:       str = ""
    osconfigid:             str = ""
    floppydrive:            bool = False
    networkcount:           int = 0
    ipaddress:              str = ""
    vmdkcount:              int = 0
    vmdktotalgb:            int = 0
    sizeondiskgb:           int = 0
    provisioning:           str = ""
    thindisks:              int = 0
    thinprovisionedgb:      int = 0
    datastorecount:         int = 0
    scsicontrollers:        int = 0
    diskformattedflat:      int = 0
    diskformatrawvirtual:   int = 0
    diskformatrawphysical:  int = 0
    diskenableuuid:         bool = False

# A dataclass that is a list of VMs
@dataclass
class VMlist(): 
    vms: List[VM] =field(default_factory=list)

# A function to process a vim.VirtualMachine into our VM class
# This also takes a CustomFieldsManager as an argument as a dependency to process any custom attributes
def create_vm_obj(virtual_machine: vim.VirtualMachine, cfm:vim.CustomFieldsManager) -> VM:

    # Make an easier summary variable, although this ends up not being that useful
    summary = virtual_machine.summary

    # Check a bunch of device stuff
    hasfloppy, thin_provisioned_count, flat_disk_count, raw_virtual_count, raw_physical_count, scsi_controller_count = get_vm_device_info(virtual_machine)

    # Check if there is a snapshot
    hassnapshot = False
    if virtual_machine.snapshot:
        hassnapshot = True

    # Check if HA enabled
    haprotected = False
    if summary.runtime.dasVmProtection:
        haprotected = summary.runtime.dasVmProtection.dasProtected

    # Set whether thick or thin
    provisioning = "Thick"
    if thin_provisioned_count > 0:
        provisioning = "Thin"

    # Count datastores
    datastore_count = 0
    for datastore in virtual_machine.config.datastoreUrl:
        datastore_count += 1

    # Get data from vm tools
    if summary.guest is not None:
        dns_name    = summary.guest.hostName
        toolsstatus = summary.guest.toolsStatus
        ipaddress   = summary.guest.ipAddress
        guestfamily = virtual_machine.guest.guestFamily

    # Check extraconfig items
    extra_config = virtual_machine.config.extraConfig

    # Check host based replication
    srmreplicated = False
    for option in extra_config:
        if option.key == "hbr_filter.destination":
            srmreplicated = True

    # Check disk uuid enabled
    diskenableuuid = False
    for option in extra_config:
        if option.key == "disk.enableUUID" and option.value == "1":
            diskenableuuid = True

    # Check if SRM Placeholder
    srmplaceholder = False
    if virtual_machine.config.managedBy:
        srmplaceholder = True

    # Sometimes the UUID is blank, I don't know how that's possible
    # This gives it a fake one
    vm_uuid = summary.config.uuid
    if not vm_uuid:
        random_uuid = uuid.uuid4()
        vm_uuid = "fake-" + str(random_uuid)

    # Create the VM object
    vm = VM(
        name                    = summary.config.name,
        vcenter                 = (os.environ.get('VCENTER')),
        cloud_name              = (get_custom_attribute(virtual_machine, cfm, "cloud_instance_name")),
        dns_name                = dns_name,
        vm_uuid                 = vm_uuid,
        vm_host                 = summary.runtime.host.name,
        #parent_id=
        vc_cluster              = summary.runtime.host.parent.name,
        vc_datacenter           = (get_vm_datacenter(virtual_machine)),
        powerstate              = summary.runtime.powerState,
        connectionstate         = summary.runtime.connectionState,
        datastorecluster        = (get_vm_datastore(virtual_machine)),
        haprotected             = haprotected,
        numcpu                  = summary.config.numCpu,
        cpulimit                = virtual_machine.config.cpuAllocation.limit,
        cpureservation          = summary.config.cpuReservation,
        cpushares               = virtual_machine.config.cpuAllocation.shares.level,
        cpuhotaddenabled        = virtual_machine.config.cpuHotAddEnabled,
        memorymb                = summary.config.memorySizeMB,
        memlimit                = virtual_machine.config.memoryAllocation.limit,
        memreservation          = summary.config.memoryReservation,
        memshares               = virtual_machine.config.memoryAllocation.shares.level,
        memhotaddenabled        = virtual_machine.config.memoryHotAddEnabled,
        hardwareversion         = virtual_machine.config.version,
        #targethardwareversion:  int = 0
        #hardwareneedsupgrade:   bool = False
        vmpath                  = summary.config.vmPathName,
        vmpathname              = (get_vm_path_name(summary.config.vmPathName)),
        snapshot                = hassnapshot,
        consolidationneeded     = summary.runtime.consolidationNeeded,
        #sanreplicated:      bool = False
        srmreplicated           = srmreplicated,
        srmplaceholder          = srmplaceholder,
        toolsstatus             = toolsstatus,
        toolsversionstatus      = toolsstatus,
        toolsversion            = virtual_machine.config.tools.toolsVersion,
        guestfamily             = guestfamily,
        guestfullname           = summary.config.guestFullName,
        osconfigfullname        = summary.config.guestFullName,
        osconfigid              = summary.config.guestId,
        floppydrive             = hasfloppy,
        networkcount            = summary.config.numEthernetCards,
        ipaddress               = ipaddress,
        vmdkcount               = summary.config.numVirtualDisks,
        vmdktotalgb             = (round((summary.storage.committed + summary.storage.uncommitted)/ (1024 * 1024 * 1024))),
        sizeondiskgb            = (round(summary.storage.committed / (1024 * 1024 * 1024))),
        provisioning            = provisioning,
        thindisks               = thin_provisioned_count,
        #thinprovisionedgb:  int = 0
        datastorecount          = datastore_count,
        scsicontrollers         = scsi_controller_count,
        diskformattedflat       = flat_disk_count,
        diskformatrawvirtual    = raw_virtual_count,
        diskformatrawphysical   = raw_physical_count,
        diskenableuuid          = diskenableuuid
    )
    return vm

# A function to return some data about the devices on a VM
def get_vm_device_info(virtual_machine: vim.VirtualMachine) -> tuple:

    # Loop through the devices once
    try:
        for device in virtual_machine.config.hardware.device:
            # Check for Floppy
            hasfloppy = False
            if isinstance(device, vim.VirtualFloppy):
                hasfloppy = True

            # Count kinds of disks
            thin_provisioned_count = 0
            flat_disk_count = 0
            raw_virtual_count = 0
            raw_physical_count = 0
            if isinstance(device, vim.vm.device.VirtualDisk):
                try:
                    if device.backing and device.backing.thinProvisioned:
                        thin_provisioned_count += 1
                except AttributeError:
                    pass

                try:
                    if device.backing and device.backing.compatibilityMode:
                        if device.backing.compatibilityMode == "virtualMode":
                            raw_virtual_count += 1
                        elif device.backing.compatibilityMode == "physicalMode":
                            raw_physical_count += 1
                        else:
                            flat_disk_count += 1
                except AttributeError:
                    pass
            # Count SCSI Controllers
            scsi_controller_count = 0
            if isinstance(device, vim.vm.device.VirtualSCSIController):
                scsi_controller_count += 1
    except AttributeError:
        hasfloppy = False
        thin_provisioned_count = 0
        flat_disk_count = 0
        raw_virtual_count = 0
        raw_physical_count = 0
        scsi_controller_count = 0
    return hasfloppy, thin_provisioned_count, flat_disk_count, raw_virtual_count, raw_physical_count, scsi_controller_count


# A function to pull the uuid-style path of the datastore path
# Not sure if this is really needed
def get_vm_path_name(path: str) -> str:
    # Define a regex pattern to match the ID (UUID)
    pattern = r'\[.*\] ([a-f\d-]+)\/'

    # Use re.search() to find the match
    match = re.search(pattern, path)

    id = ""
    if match:
        # Extract the matched ID
        id = match.group(1)
    return id



# A function to create a database model for use by SQLAlchemy
def create_vm_model_class(Base, vm_dataclass: VM):

    # Create a dictionary of column definitions
    columns = {
        field.name: Column(
            String if field.type == str else
            Integer if field.type == int else
            Boolean if field.type == bool else String,
            default=field.default,
            primary_key=True if field.name == 'vm_uuid' else False,  # Add a primary key for 'vm_uuid' field

        )
        for field in fields(vm_dataclass)
    }

    # Create the VMModel Class
    VMModel = type('VMModel', (Base,), {'__tablename__': 'vme_watchman_properties', **columns})

    return VMModel

def process_vm_data(args):
    worker_id, uuids = args
    # Env vars
    vcenter     = os.environ.get('VCENTER')
    user        = os.environ.get('VSPHERE_USER')
    password    = os.environ.get('VSPHERE_PASSWORD')

    # Connect to vCenter using vme_function
    si = connect_vcenter(vcenter=vcenter, username=user, password=password)

    # Custom Fields Manager to be used later
    content = si.RetrieveContent()
    cfm = content.customFieldsManager

    # Empty list of VM objects
    vms = []
    # Multithread finding each VM by UUID
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(get_vm_by_uuid, uuid, si) for uuid in uuids]
        concurrent.futures.wait(futures)
        for future in futures:
            vm = future.result()
            vms.append(vm)

     # Connect to the database and get the VMModel and db session       
    logging.debug(f"# {vcenter} # Worker {worker_id} connecting to database")
    VMModel, session, engine = connect_database()
    i = 0
    timer = time.perf_counter()
    # For each VM, create a VM Object and insert it into the db
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures2 = [executor.submit(create_vm_obj, vm, cfm) for vm in vms]
        concurrent.futures.wait(futures2)
        for future2 in futures2:
            vm_obj = future2.result()
            vm_model = VMModel(**vars(vm_obj))
            session.merge(vm_model)
            i+=1

    # Commit DB changes and disconnect                
    session.commit()
    engine.dispose()
    logging.debug(f"# {vcenter} # Worker {worker_id} disconnected from database")
    timer2 = time.perf_counter()
    batchtime  = timer2 - timer
    logging.info(f"# {vcenter} # Worker {worker_id} processed {i} VMs in {batchtime:.2f} seconds")

    # Disconnect the vCenter session we created.  I don't think atexit worked for these processes
    Disconnect(si)
    logging.debug(f"# {vcenter} # Worker {worker_id} disconnected from vCenter")
    
    
# Return a database model and session
def connect_database():
        # Environmental variables
        db_user     = os.environ.get('DB_USER')
        db_password = os.environ.get('DB_PASSWORD')
        db_host     = os.environ.get('DB_HOST')
        db_port     = os.environ.get('DB_PORT')
        db_name     = os.environ.get('DB_NAME')

        # Encode the password
        encoded_password = urllib.parse.quote(db_password, safe='')

        # Construct the connection URL 
        connection_url = f'postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}'

        # Create the SQLAlchemy engine
        engine = create_engine(connection_url)

        # Create a SQLAlchemy base class
        Base = declarative_base()

        # Create a session
        Session = sessionmaker(bind=engine)
        session = Session()

        # Create a metadata object
        # This doesn't seem to be used, but maybe it's required?
        metadata = MetaData()

        # Create the dynamic VMModel class
        VMModel = create_vm_model_class(Base, VM)

        return VMModel, session, engine


def delete_vms_from_database(uuid_list):
        
        # Environmental variables
        db_user     = os.environ.get('DB_USER')
        db_password = os.environ.get('DB_PASSWORD')
        db_host     = os.environ.get('DB_HOST')
        db_port     = os.environ.get('DB_PORT')
        db_name     = os.environ.get('DB_NAME')
        vcenter     = os.environ.get('VCENTER')

        logger.debug(f"# {vcenter} # Connecting to database to delete rows")

        # Encode the password
        encoded_password = urllib.parse.quote(db_password, safe='')

        # Construct the connection URL 
        connection_url = f'postgresql://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}'

        # Create the SQLAlchemy engine
        engine = create_engine(connection_url)

        # Create a SQLAlchemy base class
        Base = declarative_base()

        # Create a session
        Session = sessionmaker(bind=engine)
        session = Session()

        # Create a metadata object
        # This doesn't seem to be used, but maybe it's required?
        metadata = MetaData()

        # Create the dynamic VMModel class
        VMModel = create_vm_model_class(Base, VM)

        # Delete VMs from the DB that no longer exist
        # Fetch all records from the VM table for the target vCenter
        db_vms_to_delete = session.query(VMModel).filter_by(vcenter=vcenter).all()

        # Create a set of primary keys from the uuid list
        vm_keys = {uuid for uuid in uuid_list}

        # Iterate over the database records for the target vCenter
        i = 0
        for db_vm in db_vms_to_delete:
            if db_vm.vm_uuid not in vm_keys:
                # If the primary key is not in vm_keys, delete the record
                session.delete(db_vm)
                i += 1

        # Commit the changes
        session.commit()
        engine.dispose()
        logger.info(f"# {vcenter} # Deleted {i} VMs from the database")


def main():
    start_time = time.perf_counter()
    # Environmental vars
    vcenter     = os.environ.get('VCENTER')
    user        = os.environ.get('VSPHERE_USER')
    password    = os.environ.get('VSPHERE_PASSWORD')

    # Connect to vCenter using vme_function
    si = connect_vcenter(vcenter=vcenter, username=user, password=password)

    # Get a container view of all VMs
    all_vms = get_all_vms(si)

    # Get all UUIDs
    logger.debug(f"# {vcenter} # Gathering UUIDs")
    uuid_list   = get_all_vm_uuids(all_vms)
    uuid_len    = len(uuid_list)
    logger.info(f"# {vcenter} # Found {uuid_len} UUIDS")

    # Set the number of processes we will use
    num_processes = 4
    # Split the UUID list into chunks for each process.
    #chunk_size  = len(uuid_list) // num_processes
    chunk_size  = 50
    uuid_chunks = [uuid_list[i:i + chunk_size] for i in range(0, len(uuid_list), chunk_size)] # Thanks ChatGPT


    logger.info(f"# {vcenter} # Split UUIDS into {len(uuid_chunks)} chunks")
    
    
    # Create a multiprocessing pool 
    with multiprocessing.Pool(processes=num_processes) as pool:
        # Use the pool to execute the process_vm_data function in parallel 
        # The chunks of UUIDs should be automatically divided among the processes
        # Thanks again, ChatGPT.  Creates worker_args as i (a number for a worker id), and a list of uuids
        worker_args = [(i, uuid_chunk) for i, uuid_chunk in enumerate(uuid_chunks)] 
        pool.map(process_vm_data, worker_args)


    # Close the pool 
    pool.close()
    pool.join()

    # Delete VMs that no longer exist from database
    logger.debug(f"# {vcenter} # Deleting VMs from database")
    delete_vms_from_database(uuid_list)

    # Track the total time and some other stats
    end_time = time.perf_counter()
    elapsed_time = time.strftime("%H:%M:%S", time.gmtime(end_time - start_time))
    logger.info(f"# {vcenter} # --- TOTAL duration: {elapsed_time} for {uuid_len} VMs ---")
    per_vm = (end_time - start_time) / uuid_len
    logger.info(f"# {vcenter} # --- {per_vm:.2f} Seconds per VM ---")

    return 0

# Start program
if __name__ == "__main__":

    # Format logging so netelk sees it correctly
    logger = logging.getLogger()
    format = "%(asctime)s | %(name)s | %(levelname)s | %(filename)s | %(funcName)s:%(lineno)d | %(message)s"
    logging.basicConfig(level=os.environ.get("LOGLEVEL", "DEBUG"), format=format, handlers=[logging.StreamHandler(sys.stdout)], force=True)

    # Run main
    main()
