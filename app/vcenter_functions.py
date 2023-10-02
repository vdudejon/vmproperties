import ssl
import atexit
import logging
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim, vmodl
import pyVim.task
import concurrent.futures

# A function to connect to vCenter, which includes disconnecting atExit
def connect_vcenter(vcenter: str, username: str, password: str) -> vim.ServiceInstance:
    service_instance = None

    logging.debug("Connecting to {}".format(vcenter))
    
    s = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    s.verify_mode = ssl.CERT_NONE

    try:
        service_instance = SmartConnect(
            host=vcenter, user=username, pwd=password, sslContext=s
        )

        # doing this means you don't need to remember to disconnect your script/objects
        #atexit.register(Disconnect, service_instance) 
        atexit.register(exit_handler, service_instance, vcenter)
        logging.debug("Connection successful to {}".format(vcenter))
    except IOError as io_error:
        logging.error(io_error)
        #print(io_error)

    if not service_instance:
        raise SystemExit("Unable to connect to host with supplied credentials.")

    return service_instance

# Just a function to add some things to atexit
def exit_handler(service_instance: vim.ServiceInstance, vcenter: str):
    Disconnect(service_instance)
    logging.debug(f"Disconnected from {vcenter}")

# A function to return all VMs
def get_all_vms(service_instance: vim.ServiceInstance):
    content = service_instance.RetrieveContent()
    container = content.rootFolder        # Starting point to look into
    view_type = [vim.VirtualMachine]      # Object types to look for
    recursive = True                      # Whether we should look into it recursively
    # Create VM view container
    container_view = content.viewManager.CreateContainerView(container, view_type, recursive)
    return container_view.view

# A function to return a VM uuid 
def get_vm_uuid(vm: vim.VirtualMachine) -> str:
    uuid = vm.summary.config.uuid
    # Sometimes uuids are blank?  Skip blank ones
    if uuid is not None:
        return uuid

# A function to find all the VM UUIDs in a vCenter
def get_all_vm_uuids(all_vms):
    uuids = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(get_vm_uuid, vm) for vm in all_vms]
        concurrent.futures.wait(futures)
        for future in futures:
            uuid = future.result()
            if uuid is not None:
                uuids.append(uuid)
    return uuids

# A function to return the datacenter a VM belongs to
def get_vm_datacenter(vm: vim.VirtualMachine) -> str:
    # Retrieve the VM's parent folder
    vm_folder = vm.parent

    # Check if the parent folder is the root folder (indicating it's a top-level VM)
    if isinstance(vm_folder, vim.Datacenter):
        return vm_folder.name  # The VM belongs to this datacenter

    # If the parent folder is not a datacenter, recursively check its parent
    elif isinstance(vm_folder, vim.Folder):
        return get_vm_datacenter(vm_folder)

    # If the VM's parent is neither a datacenter nor a folder, it may not be in a vCenter hierarchy.
    return "Unknown"  # VM may not belong to a datacenter

# A function to return a given custom attribute
def get_custom_attribute(virtual_machine: vim.VirtualMachine, cfm: vim.CustomFieldsManager, custom_attribute: str) -> str:
    fvalue = ""
    try: 
        for field in cfm.field:
            if field.name == custom_attribute:
                fkey = field.key
        vm_fields = virtual_machine.customValue
        
        for opts in vm_fields:
            if opts.key == fkey:
                fvalue = opts.value
        return fvalue
    except:
        # Need something to exist or the database merge fails
        fvalue =  "None found"
        return fvalue
    
def get_vm_by_uuid(uuid: str, service_instance: vim.ServiceInstance):
    try:
        search_index = service_instance.content.searchIndex
        vm = search_index.FindByUuid(None, uuid, True)
        if vm:
            return vm
    except:
        logging.error(f"Could not find virtual machine {uuid}")
        pass

# A function to return the datastore a given VM resides on
# This is lazy and cheap, and returns only the 1st datastore
def get_vm_datastore(virtual_machine: vim.VirtualMachine) -> str:
    datastore = "None Found"
    datastore_url = virtual_machine.config.datastoreUrl
    if datastore_url:
        if datastore_url[0].name:
            datastore = datastore_url[0].name 
    return datastore
