"""Netbox Base - Setup the base netbox environment.

Creates the environment within NetBox ready for adding devices, it does not add the devices themselves.
This script is not idempotent. Its purpose to add objects rather than edit or delete existing objects.
The environment is defined in YAML files (opens all from defined directory) that follows the hierarchical structure of NetBox.

1. ORG_TNT_SITE_RACK: Create all the organisation objects
2. DVC_MTFR_TYPE: Create all the objects required to create devices
3. IPAM_VRF_VLAN: Create all the IPAM objects
4. CRT_PVDR: Create all the Circuit objects
5. VIRTUAL: Creates all the Cluster objects
6. CONTACT: Creates all the Contacts and associates them to objects

It is advisable to run the validation script against the input file to ensure the formatting of the input file is correct
python input_validate.py test.yml

When run pass in directory where yaml files are stored. Without flags will try and create all objects or can limit it using flags (-o, -d, -i, -p, -v, -c)
python nbox_env_setup.py simple_example
"""

import argparse
import os
import sys
from collections import defaultdict
from typing import Any

import yaml
from rich.console import Console
from rich.theme import Theme

from dm import Circuits, Contacts, Devices, Ipam, Organisation, Virtualisation
from netbox import Nbox

# ----------------------------------------------------------------------------
# ENV VARS: Either set as env vars or fallback to defaults
# ----------------------------------------------------------------------------
# Default netbox instance, falls back to docker version on Orb
NBOX_URL = os.environ.get("NBOX_URL", "http://netbox.netbox-docker.orb.local")
# Netbox API token (don't include Bearer, just the token) created under user profile
NBOX_TOKEN = os.environ.get("NBOX_TOKEN", "")
# By default use HTTP, if using Self-signed cert disable SSL verification (nb.http_session.verify = False) or specify the CA cert
_ssl_env = os.environ.get("SSL", False)
SSL: bool = (
    _ssl_env
    if isinstance(_ssl_env, bool)
    else _ssl_env.strip().lower() in ("1", "true", "yes")
)
# os.environ['REQUESTS_CA_BUNDLE'] = os.path.expanduser('~/Documents/Coding/Netbox/nbox_py_scripts/myCA.pem')
# Directory that holds all device type templates (mentioned in the script)
DVC_TYPE_DIR = os.environ.get("DVC_TYPE_DIR", os.path.join(os.getcwd(), "device_type"))
# Directory that holds all the .yml/.yaml input files definign netbox objects to be created, default is current working directory
INPUT_DIR = os.environ.get("INPUT_DIR", os.getcwd())


# ----------------------------------------------------------------------------
# 1. Gathers input arguments as well as loading and validating the input file
# ----------------------------------------------------------------------------
class Inputs:
    def __init__(self) -> None:
        my_theme = {"repr.ipv4": "none", "repr.number": "none", "repr.call": "none"}
        self.rc = Console(theme=Theme(my_theme))

    # 1a. ARG: Gather input args and file name
    def arg_parser(self) -> tuple[dict[str, Any], str]:
        args = argparse.ArgumentParser()
        args.add_argument(
            "-o",
            "--organisation",
            action="store_true",
            help="Create all Netbox Organisation objects",
        )
        args.add_argument(
            "-d",
            "--device",
            action="store_true",
            help="Create all Netbox Device objects",
        )
        args.add_argument(
            "-i",
            "--ipam",
            action="store_true",
            help="Create all Netbox IPAM objects",
        )
        args.add_argument(
            "-p",
            "--provider",
            action="store_true",
            help="Create all Netbox Provider objects",
        )
        args.add_argument(
            "-c",
            "--contact",
            action="store_true",
            help="Create all Netbox Contact objects and assignments",
        )
        args.add_argument(
            "-v",
            "--virtual",
            action="store_true",
            help="Create all Netbox Virtualisation objects",
        )
        # parse_known_args allows filename to be entered without needing a flag (arg)
        all_args, directory = args.parse_known_args()

        if len(directory) != 0:
            tmp_input_dir = directory[0]
        elif len(directory) == 0:
            tmp_input_dir = INPUT_DIR
        return vars(all_args), tmp_input_dir

    # 1b. FILE: Loads input file and validates it
    def input_val(self, input_dir: str, args: dict[str, Any]) -> dict[str, Any]:
        # VAL_DIR: Check directory exists incurrent location or base directory
        if not os.path.exists(input_dir):
            if not os.path.exists(INPUT_DIR):
                self.rc.print(
                    f":x: Input File Error - Input file directories '{os.path.join(os.getcwd(), input_dir)}' "
                    f"or '{INPUT_DIR}' do not exist."
                )
                sys.exit(1)
            else:
                input_dir = os.path.join(INPUT_DIR)

        # LOAD_FILE: Load the variable files
        my_vars: dict[str, Any] = {}
        for filename in os.listdir(input_dir):
            if filename.endswith(".yml") or filename.endswith(".yaml"):
                with open(os.path.join(input_dir, filename)) as file_content:
                    my_vars.update(yaml.load(file_content, Loader=yaml.FullLoader))
        # VAL_FILE: Validates the input dicts needed for the specified flags are present
        val: dict[str, tuple[str, ...]] = {
            "organisation": ("tenant", "rack_role"),
            "device": ("device_role", "manufacturer"),
            "ipam": ("rir", "role"),
            "provider": ("circuit_type", "provider"),
            "virtual": ("cluster_group", "cluster_type"),
            "contact": ("contact_role", "contact_group", "contact_assign"),
        }
        missing_dicts: defaultdict[str, list[str]] = defaultdict(list)
        for flag, required_dicts in val.items():
            if args[flag]:
                for each_dict in required_dicts:
                    if my_vars.get(each_dict) is None:
                        missing_dicts[flag].append(each_dict)
        if missing_dicts:
            for flag, missing_dict_list in missing_dicts.items():
                self.rc.print(
                    f":x: Input Error - The input flag '{flag}' requires dictionaries '{', '.join(missing_dict_list)}' in the input files"
                )
            sys.exit(1)
        return my_vars


# ----------------------------------------------------------------------------
# ENGINE: Runs the methods of the script, first creating data-model and using to create non-existant objects
# ----------------------------------------------------------------------------
def main() -> None:
    # 1. ARG_FILE_NBOX: Gathers input flags (args), input file variables (dicts) and initialises the Netbox connection (nbox)
    arg_vars = Inputs()
    args, input_dir = arg_vars.arg_parser()
    my_vars = arg_vars.input_val(input_dir, args)
    # Initialise Netbox class used to run Netbox API calls
    tag_exists: list[str] = []
    tag_created: list[str] = []
    rt_exists: list[str] = []
    rt_created: list[str] = []
    nbox = Nbox(
        NBOX_URL, NBOX_TOKEN, SSL, tag_exists, tag_created, rt_exists, rt_created
    )
    # Used to run all object creation classes if no flags input
    flag_all = any(args.values())

    # 2. ORG_TNT_SITE_RACK: Create all the organisation objects
    if args["organisation"] or not flag_all:
        org = Organisation(nbox, my_vars["tenant"], my_vars["rack_role"])
        org_dict = org.create_tnt_site_rack()
        # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
        nbox.engine("Rack Role", "dcim.rack_roles", "name", org_dict["rack_role"])
        nbox.engine("Tenant", "tenancy.tenants", "name", org_dict["tnt"])
        nbox.engine("Site", "dcim.sites", "name", org_dict["site"])
        nbox.engine("Location (parent)", "dcim.locations", "slug", org_dict["prnt_loc"])
        nbox.engine("Location (child)", "dcim.locations", "slug", org_dict["chld_loc"])
        nbox.engine("Rack", "dcim.racks", "name", org_dict["rack"])

    # 3. DVC_MTFR_TYPE: Create all the objects required to create devices
    if args["device"] or not flag_all:
        dvc = Devices(
            nbox, my_vars["device_role"], my_vars["manufacturer"], DVC_TYPE_DIR
        )
        dvc_dict = dvc.create_dvc_type_role()
        # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
        nbox.engine("Device-role", "dcim.device_roles", "name", dvc_dict["dev_role"])
        nbox.engine("Manufacturer", "dcim.manufacturers", "name", dvc_dict["mftr"])
        nbox.engine("Platform", "dcim.platforms", "name", dvc_dict["pltm"])
        nbox.engine("Device-type", "dcim.device_types", "model", dvc_dict["dev_type"])

    # 4. IPAM_VRF_VLAN: Create all the IPAM objects
    if args["ipam"] or not flag_all:
        ipam = Ipam(nbox, my_vars["rir"], my_vars["role"])
        ipam_dict = ipam.create_ipam()
        # print(ipam_dict)

        # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
        nbox.engine("RIRs", "ipam.rirs", "name", ipam_dict["rir"])
        nbox.engine("Aggregates", "ipam.aggregates", "prefix", ipam_dict["aggr"])
        nbox.engine("Prefix/VLAN Role", "ipam.roles", "name", ipam_dict["role"])
        nbox.engine("VLAN Group", "ipam.vlan-groups", "name", ipam_dict["vlan_grp"])
        nbox.engine("VRF", "ipam.vrfs", "name", ipam_dict["vrf"])
        nbox.print_tag_rt("Route-Targets", set(rt_exists), rt_created)
        # First check if VL/PFX exist in VL_GRP/VRF, then if exist in ROLE.
        nbox.engine(
            "VLAN",
            ["ipam.vlans", "ipam.vlan_groups"],
            ["name", "group_id"],
            ipam_dict["vlan"],
        )
        nbox.engine(
            "Prefix",
            ["ipam.prefixes", "ipam.vrfs"],
            ["prefix", "vrf_id"],
            ipam_dict["prefix"],
        )

    # 5. CRT_PVDR: Create all the Circuit objects
    if args["provider"] or not flag_all:
        crt = Circuits(nbox, my_vars["circuit_type"], my_vars["provider"])
        crt_dict = crt.create_crt_pvdr()
        # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
        nbox.engine(
            "Circuit Type", "circuits.circuit-types", "name", crt_dict["crt_type"]
        )
        nbox.engine("Provider", "circuits.providers", "name", crt_dict["pvdr"])
        nbox.engine("Circuit", "circuits.circuits", "cid", crt_dict["crt"])

    # 6. VIRTUAL: Creates all the Cluster objects
    if args["virtual"] or not flag_all:
        vrtl = Virtualisation(nbox, my_vars["cluster_group"], my_vars["cluster_type"])
        vrtl_dict = vrtl.create_vrtl()
        # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
        nbox.engine(
            "Cluster Type",
            "virtualization.cluster-types",
            "name",
            vrtl_dict["cltr_type"],
        )
        nbox.engine(
            "Cluster Group",
            "virtualization.cluster-groups",
            "name",
            vrtl_dict["cltr_grp"],
        )
        nbox.engine("Cluster", "virtualization.clusters", "name", vrtl_dict["cltr"])

    # 7. CONTACTS: Creates all the contacts and assigns to objects
    if args["contact"] or not flag_all:
        cnt = Contacts(
            nbox,
            my_vars["contact_role"],
            my_vars["contact_group"],
            my_vars["contact_assign"],
        )
        cnt_dict = cnt.create_contact()
        nbox.engine(
            "Contact Role", "tenancy.contact-roles", "name", cnt_dict["cnt_role"]
        )
        nbox.engine(
            "Contact Group", "tenancy.contact-groups", "name", cnt_dict["cnt_grp"]
        )
        nbox.engine("Contacts", "tenancy.contacts", "name", cnt_dict["cnt"])
        nbox.engine(
            "Contact Assignment",
            "tenancy.contact-assignments",
            "multi-fltr",
            cnt_dict["cnt_asgn"],
        )

    # 8. Prints any tags that have been created for any of the sections:
    nbox.print_tag_rt("Tags", set(tag_exists), tag_created)


if __name__ == "__main__":
    main()
