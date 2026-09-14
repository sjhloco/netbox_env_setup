"""INPUT VALIDATE.

Validates the formatting, value types and values within the input file used to build the NetBox environment.
All checks are done offline against the file, is no communication to NetBox
Some of the things it checks are:
-Main dictionaries (tenant, manufacturer, rir, role, crt_type, provider, cluster_type) and key is a list
-All mandatory dictionaries are present
-All Dictionary keys that are meant to be a list, integer, boolean or IPv4 address are the correct format
-All referenced objects such as Tenant, site, rack_role, etc, exist within the input file
-Duplicate object names

To run the script reference the directory where the input data files are.
The 'errors' directory will trigger the majority of formatting errors
python input_validate.py errors
"""

import ipaddress
import os
import re
import sys
from collections import defaultdict
from sys import argv
from typing import Any

import yaml
from rich.console import Console
from rich.theme import Theme

# ----------------------------------------------------------------------------
# Variables to change dependant on environment
# ----------------------------------------------------------------------------
# Directory that holds all device type templates
dvc_type_dir = os.path.join(os.getcwd(), "device_type")
input_directory = "errors"
base_dir = os.getcwd()

# Assigned in main(), declared here so mypy can resolve references to them in
# functions defined before main() runs. main() is the only entry point and
# always assigns these before anything else reads them (no runtime effect).
rc: Console
are_errors: bool
all_obj: list[str]
all_tnt: list[str]
all_site: list[str]


# ----------------------------------------------------------------------------
# FILE: Loads input file and validates it
# ----------------------------------------------------------------------------
def input_val(input_dir: str, argv: list[str]) -> dict[str, Any]:
    input_dir = argv[1] if len(argv) > 1 else input_directory

    # VAL_DIR: Check directory exists incurrent location or base directory
    if not os.path.exists(input_dir):
        if not os.path.exists(os.path.join(base_dir, input_dir)):
            rc.print(
                f":x: Input File Error - Input file directories '{os.path.join(os.getcwd(), input_dir)}' "
                f"or '{os.path.join(base_dir, input_dir)}' do not exist."
            )
            sys.exit(1)
        else:
            input_dir = os.path.join(base_dir, input_dir)
    my_vars: dict[str, Any] = {}
    for filename in os.listdir(input_dir):
        if filename.endswith("yml") or filename.endswith("yaml"):
            with open(os.path.join(input_dir, filename)) as file_content:
                my_vars.update(yaml.load(file_content, Loader=yaml.FullLoader))
    return my_vars


# ----------------------------------------------------------------------------
# Generic assert functions used by all classes to make it DRY
# ----------------------------------------------------------------------------
# STRING: Asserts that the variable is a string
def assert_string(msg: str, obj: dict[str, Any], errors: list[str]) -> None:
    obj_type = msg.split(".")[-1].capitalize()
    obj_parent = msg.split(".")[-2]
    obj_to_chk = obj.get(msg.split(".")[-1], "string")
    err_msg = f"-{msg}: {obj_type} '{obj_to_chk}' of {obj_parent} '{obj['name']}'  should be enclosed in quotes to make it a string"
    try:
        assert isinstance(obj_to_chk, str), err_msg
    except AssertionError as e:
        errors.append(str(e))


# INTEGER: Asserts that the variable is an integer (number)
def assert_integer(msg: str, obj: dict[str, Any], errors: list[str]) -> None:
    obj_type = msg.split(".")[-1].capitalize()
    obj_parent = msg.split(".")[-2]
    obj_to_chk = obj.get(msg.split(".")[-1], 1)
    obj_name = obj["cid"] if msg == "provider.circuit.commit_rate" else obj["name"]
    err_msg = f"-{msg}: {obj_type} '{obj_to_chk}' of {obj_parent} '{obj_name}' must be an integer"
    try:
        assert isinstance(obj_to_chk, int), err_msg
    except AssertionError as e:
        errors.append(str(e))


# LIST: Asserts that the variable is a list
def assert_list(msg: str, obj: dict[str, Any], errors: list[str]) -> None:
    obj_to_chk = obj.get(msg.split(".")[-1], {})
    if len(msg.split(".")) == 1:
        err_msg = f"-{msg}: Parent '{msg}' dictionary must be a list"
    if len(msg.split(".")) >= 2:
        obj_type = msg.split(".")[-1].capitalize()
        obj_parent = msg.split(".")[-2]
        err_msg = f"-{msg}: {obj_type} '{obj_to_chk}' in {obj_parent} '{obj['name']}' must be a list"
    try:
        assert isinstance(obj_to_chk, list), err_msg
    except AssertionError as e:
        errors.append(str(e))


# DICT: Asserts that the variable is a dict
def assert_dict(msg: str, obj: dict[str, Any], errors: list[str]) -> None:
    obj_type = msg.split(".")[-1].capitalize()
    obj_parent = msg.split(".")[-2]
    obj_to_chk = obj.get(msg.split(".")[-1], {})
    if obj_parent == "aggregate":
        prnt_name = obj["prefix"]
    elif obj_parent == "pfx":
        prnt_name = obj["pfx"]
    elif obj_parent == "circuit":
        prnt_name = obj["cid"]
    else:
        prnt_name = obj["name"]
    err_msg = f"-{msg}: {obj_type} '{obj_to_chk}' for {obj_parent} '{prnt_name}' must be a dictionary"
    try:
        assert isinstance(obj_to_chk, dict), err_msg
    except AssertionError as e:
        errors.append(str(e))


# BOOLEAN: Asserts that the variable is True or False
def assert_boolean(msg: str, obj: dict[str, Any], errors: list[str]) -> None:
    obj_type = msg.split(".")[-1].capitalize()
    obj_parent = msg.split(".")[-2]
    obj_to_chk = obj.get(msg.split(".")[-1], False)
    if msg.split(".")[-1] == "pool":
        err_msg = f"-{msg}: {obj_type} '{obj_to_chk}' in {obj_parent} '{obj['pfx']}' is not valid, it must be boolean True or False"
    else:
        err_msg = f"-{msg}: {obj_type} '{obj_to_chk}' in {obj_parent} '{obj['name']}' is not valid, it must be boolean True or False"
    try:
        assert isinstance(obj_to_chk, bool), err_msg
    except AssertionError as e:
        errors.append(str(e))


# REGEX: Matches the specified pattern at the beginning of the string
def assert_regex_match(
    msg: str, obj_to_chk: str, regex: str, prnt_name: str, errors: list[str]
) -> None:
    obj_type = msg.split(".")[-1].capitalize()
    obj_parent = msg.split(".")[-2]
    err_msg = f"-{msg}: {obj_type} '{obj_to_chk}' for {obj_parent} '{prnt_name}' is not a valid option, it must be one of the defined options"
    try:
        assert re.match(regex, obj_to_chk), err_msg
    except AssertionError as e:
        errors.append(str(e))


# IN: Asserts that the variable is within the specified value
def assert_in(
    msg: str,
    input_value: str | int | None,
    in_obj: list[str] | list[int],
    from_obj: str | dict[str, str],
    errors: list[str],
) -> None:
    if input_value is not None:
        obj_type = msg.split(".")[-1].capitalize()
        err_msg = f"-{msg}: {obj_type} '{input_value}' of '{from_obj}' does not exist"
        try:
            assert input_value in in_obj, err_msg
        except AssertionError as e:
            errors.append(str(e))


# EQUAL: Asserts that the variable does match the specified value
def assert_equal(
    errors: list[str], variable: int, input_value: int, error_message: str
) -> None:
    try:
        assert variable == input_value, error_message
    except AssertionError as e:
        errors.append(str(e))


# IPv4: Asserts that the IPv4 Address or interface address are in the correct format
def assert_ipv4(msg: str, obj: dict[str, Any], errors: list[str]) -> None:
    obj_type = msg.split(".")[-1].capitalize()
    obj_to_chk = obj[msg.split(".")[-1]]
    err_msg = f"-{msg}: {obj_type} '{obj_to_chk}' is not a valid IPv4 Address/Netmask"
    try:
        ipaddress.IPv4Interface(obj_to_chk)
    except ipaddress.AddressValueError:
        errors.append(err_msg)
    except ipaddress.NetmaskValueError:
        errors.append(err_msg)


# IPv4: Asserts that the IPv4 Address or interface address are in the correct format
def assert_ipv6(msg: str, obj: dict[str, Any], errors: list[str]) -> None:
    obj_type = msg.split(".")[-1].capitalize()
    obj_to_chk = obj[msg.split(".")[-1]]
    err_msg = f"-{msg}: {obj_type} '{obj_to_chk}' is not a valid IPv6 Address/Netmask"
    try:
        ipaddress.IPv6Interface(obj_to_chk)
    except ipaddress.AddressValueError:
        errors.append(err_msg)
    except ipaddress.NetmaskValueError:
        errors.append(err_msg)


# DUPLICATE: Asserts are no duplicate elements in a list, if so returns the duplicate in error message.
def duplicate_in_list(
    input_list: list[str], args: list[str], errors: list[str], end_msg: str
) -> None:
    # Args is a list of 0 to 4 args to use in error message before dup error
    dup = [i for i in set(input_list) if input_list.count(i) > 1]
    err_msg = "-{}: There are duplicate {} with the same {} '{}', all should be unique or if expected ensure the slugs are unique {}"
    assert_equal(errors, len(dup), 0, err_msg.format(*args, ", ".join(dup), end_msg))


# TNT_SITE_GRP: Asserts specified Tenant exists, site exists and if definnd the Cluster group exists
def assert_in_tnt_site_grp(
    msg: str, obj: dict[str, Any], all_grp: list[str], errors: list[str]
) -> None:
    assert_in(f"{msg}.tenant", obj.get("tenant"), all_tnt, obj["name"], errors)
    assert_in(f"{msg}.site", obj.get("site"), all_site, obj["name"], errors)
    assert_in(f"{msg}.group", obj.get("group"), all_grp, obj["name"], errors)


# LOCATION_RACK: Asserts Rack and Location variables exist
def assert_loc_rack(
    org_errors: list[str],
    location: dict[str, Any],
    all_rr: list[str],
    all_val_tnt: dict[str, list[str]],
    tnt: str,
    site: str,
) -> None:
    if location.get("name") is not None:
        # LOC_TAG: Checks tag is dict and creates a list of all locations
        assert_dict("tenant.site.location.tags", location, org_errors)
        all_val_tnt["loc"].append(location["name"])
        # RACK: If rack exists must be a list and has a name
        if location.get("rack") is not None:
            assert isinstance(location["rack"], list), (
                f"-tenant.site.location.rack: Rack in location '{location.get('name')}' must be a list"
            )
            for each_rack in location["rack"]:
                if each_rack.get("name") is not None:
                    all_val_tnt["rack"].append(each_rack["name"])
                    # RACK_ROLE: Assert that the rack role exists
                    assert_in(
                        "tenant.site.location.rack.rack_role",
                        each_rack.get("role"),
                        all_rr,
                        each_rack["name"],
                        org_errors,
                    )
                    # RACK_HEIGHT: Must be an integer
                    assert_integer(
                        "tenant.site.location.rack.height", each_rack, org_errors
                    )
                    # RACK_TENANT: Assert that the specified tenant of the rack exists
                    assert_in(
                        "tenant.site.location.rack.tenant",
                        each_rack.get("tenant", tnt),
                        all_val_tnt["tnt"],
                        each_rack["name"],
                        org_errors,
                    )
                    # RACK_TAG: If defined must be a dict
                    assert_dict("tenant.site.location.rack.tags", each_rack, org_errors)
                # RACK_NAME: Every rack group must have a name
                elif each_rack.get("name") is None:
                    org_errors.append(
                        f"-tenant.site.location.rack.name: A rack in location '{location.get('name')}' is missing a name, this is a mandatory dictionary"
                    )
    # LOCATION_NAME: Every rack-group must have a name
    elif location.get("name") is None:
        org_errors.append(
            f"-tenant.site.location.name: A location in site '{site}' is missing a name, this is a mandatory dictionary"
        )


# VRF_PREFIX: Asserts VRF and Prefix variables exist
def assert_vrf_pfx(
    obj: dict[str, Any],
    msg: str,
    all_vrf: list[str],
    all_vl_numb: list[int],
    errors: list[str],
) -> None:
    if obj.get("vrf") is not None:
        try:
            # VRF: Must be a list and tag validation
            assert isinstance(obj["vrf"], list), (
                f"-{msg}: VRF within VLAN-group '{obj['name']}' must be a list of sites"
            )
            for each_vrf in obj["vrf"]:
                all_pfx = []
                if each_vrf.get("name") is not None:
                    assert_dict(f"{msg}.tags", each_vrf, errors)
                    all_vrf.append(each_vrf["name"])
                    # RD: Must be a string to stop : causing equations of the RD
                    assert_string(f"{msg}.rd", each_vrf, errors)
                    # UNIQUE: Must be True or False
                    assert_boolean(f"{msg}.unique", each_vrf, errors)
                    # TNT: Asserts specified Tenant exists
                    assert_in(
                        f"{msg}.tenant",
                        each_vrf.get("tenant"),
                        all_tnt,
                        each_vrf["name"],
                        errors,
                    )
                    # PREFIX: A VRF must have a Prefix dictionary whose key is a list
                    assert each_vrf.get("prefix") is not None, (
                        f"-{msg}.prefix: VRF '{each_vrf['name']}' has no list of prefixes, this is a mandatory dictionary"
                    )
                    assert isinstance(each_vrf["prefix"], list), (
                        f"-{msg}.prefix: Prefix within VRF '{each_vrf['name']}' must be a list"
                    )
                    for each_pfx in each_vrf["prefix"]:
                        if each_pfx.get("pfx") is not None:
                            # Adds prefixes to all_pfx list to check for duplicated if the VRF is set to only have unique prefixes
                            if each_vrf.get("unique", True):
                                all_pfx.append(each_pfx["pfx"])
                            # PREFIX: Asserts it is a valid IPv4 or IPv6 address and subnet mask
                            assert_ipv4(f"{msg}.prefix.pfx", each_pfx, errors)
                            if "." in each_pfx["pfx"]:
                                assert_ipv4(f"{msg}.prefix.pfx", each_pfx, errors)
                            elif ":" in each_pfx["pfx"]:
                                assert_ipv6(f"{msg}.prefix.pfx", each_pfx, errors)
                            # VLAN_EXIST: Assert that the specified site of the role exists (is in organisation dictionary)
                            assert_in(
                                f"{msg}.prefix.vl",
                                each_pfx.get("vl"),
                                all_vl_numb,
                                each_pfx["pfx"],
                                errors,
                            )
                            # POOL: Must be True or False
                            assert_boolean(f"{msg}.prefix.pfx.pool", each_pfx, errors)
                            # TAG: Asserts tag is a dict
                            assert_dict(f"{msg}.prefix.pfx.tags", each_pfx, errors)
                            # TNT: Asserts specified Tenant exists
                            assert_in(
                                f"{msg}.prefix.pfx.tenant",
                                each_pfx.get("tenant"),
                                all_tnt,
                                each_pfx["pfx"],
                                errors,
                            )
                        elif each_pfx.get("pfx") is None:
                            errors.append(
                                f"-{msg}.prefix.pfx: A prefix within VRF '{each_vrf['name']}' has no value, this is a mandatory dictionary"
                            )
                # VRF_NAME: Every VRF must have a name
                elif each_vrf.get("name") is None:
                    errors.append(
                        f"-{msg}.name: A VRF within VLAN-group '{obj['name']}' has no name, this is a mandatory dictionary"
                    )
                # DUPLICATE_PFX: Prefixes within a VRFs should all be unique (if set to unique True)
                duplicate_in_list(
                    all_pfx,
                    [f"{msg}.prefix.pfx", "prefixes", "prefix"],
                    errors,
                    "within a VRF",
                )
        except AssertionError as e:
            errors.append(str(e))


# PRINT_ERROR: Prints out any errors to screen
def print_error(errors: list[str], section: str) -> None:
    global are_errors
    are_errors = True
    input_dir = argv[1] if len(argv) > 1 else input_directory
    rc.print(
        f"\n:x: {section}: Check the contents of '{input_dir}' for the following issues:"
    )
    for err in errors:
        rc.print(err)


# ----------------------------------------------------------------------------
# 1. ORGANISATION: Validate formatting of variables for objects within the Organisation menu
# ----------------------------------------------------------------------------
class Organisation:
    def __init__(
        self, tnt: list[dict[str, Any]], rr: list[dict[str, Any]] | None
    ) -> None:
        self.rr = rr
        self.tnt = tnt
        self.org_errors: list[str] = []

    # RACK_ROLE: Asserts it is a list, checks each dict has a name, checks tags format and creates a list of all rack-role names
    def val_rr(self) -> list[str]:
        # needs to have an element as that is used as the default in get statements
        all_rr: list[str] = []
        if self.rr is not None:
            try:
                assert isinstance(self.rr, list), "-rack_role: Rack-role must be a list"
                for each_rr in self.rr:
                    if each_rr.get("name") is not None:
                        assert_dict("rack_role.tags", each_rr, self.org_errors)
                        all_rr.append(each_rr["name"])
                    elif each_rr.get("name") is None:
                        self.org_errors.append(
                            "-rack_role.name: A rack-role is missing a name, this is a mandatory dictionary"
                        )
            except AssertionError as e:
                self.org_errors.append(str(e))
        return all_rr

    # TENANT: Asserts it is a list and checks formatting and presence of all elements within it
    def val_tnt(self, all_rr: list[str]) -> dict[str, list[str]]:
        all_val_tnt: dict[str, list[str]] = dict(tnt=[], site=[], loc=[], rack=[])
        for each_tnt in self.tnt:
            if each_tnt.get("name") is not None:
                all_val_tnt["tnt"].append(each_tnt["name"])

        for each_tnt in self.tnt:
            try:
                # TNT_NAME: Every tenant must have a name
                assert each_tnt.get("name") is not None, (
                    "-tenant.name: A tenant is missing a name, this is a mandatory dictionary"
                )
                # TNT_TAG: If defined must be a dict
                assert_dict("tenant.tags", each_tnt, self.org_errors)
                if each_tnt.get("site") is not None:
                    # SITE: If defined a site must be a list. If not failfast as cant do any of the further checks
                    assert isinstance(each_tnt["site"], list), (
                        f"-tenant.site: Site in tenant '{each_tnt.get('name')}' must be a list"
                    )
                    for each_site in each_tnt["site"]:
                        if each_site.get("name") is not None:
                            site = each_site["name"]
                            all_val_tnt["site"].append(each_site["name"])
                            # SITE_TAG: If defined must be a dict
                            assert_dict("tenant.site.tags", each_site, self.org_errors)
                            # SITE_TIMEZONE: Must start with any of the defined Regions, location within that region can be anything
                            assert_regex_match(
                                "tenant.site.time_zone",
                                each_site.get("time_zone", "UTC/"),
                                "^(Africa\/|America\/|Asia\/|Australia\/|Canada\/|Europe\/|GMT\/|Indian\/|Pacific\/|US\/|UTC\/)",
                                each_site["name"],
                                self.org_errors,
                            )
                            # PARENT_LOCATION: Validates the parent location is a list
                            if each_site.get("location") is not None:
                                assert isinstance(each_site["location"], list), (
                                    f"-tenant.site.location: Location in site '{site}' must be a list"
                                )
                                # LOC_RACK: Asserts formatting of Location and Rack variables
                                for each_prnt_loc in each_site["location"]:
                                    assert_loc_rack(
                                        self.org_errors,
                                        each_prnt_loc,
                                        all_rr,
                                        all_val_tnt,
                                        each_tnt["name"],
                                        site,
                                    )
                                    # CHILD_LOCATION: Asserts formatting of the child Location and Rack variables
                                    if each_prnt_loc.get("location") is not None:
                                        assert isinstance(
                                            each_prnt_loc["location"], list
                                        ), (
                                            f"-tenant.site.location.location: Nested location in site '{site}' must be a list[/i]"
                                        )
                                        for each_chld_loc in each_prnt_loc["location"]:
                                            assert_loc_rack(
                                                self.org_errors,
                                                each_chld_loc,
                                                all_rr,
                                                all_val_tnt,
                                                each_tnt["name"],
                                                site,
                                            )
                        # SITE_NAME: Every site must have a name
                        elif each_site.get("name") is None:
                            self.org_errors.append(
                                f"-tenant.site.name: A site in tenant '{each_tnt['name']}' is missing a name, this is a mandatory dictionary"
                            )
            except AssertionError as e:
                self.org_errors.append(str(e))
        return all_val_tnt

    def engine(self) -> None:
        all_rr = self.val_rr()
        all_val_tnt = self.val_tnt(all_rr)
        # Used for dependency checks
        all_obj.extend(all_val_tnt["tnt"])
        all_obj.extend(all_val_tnt["site"])
        all_obj.extend(all_val_tnt["loc"])
        all_obj.extend(all_val_tnt["rack"])
        all_tnt.extend(all_val_tnt["tnt"])
        all_site.extend(all_val_tnt["site"])

        # DUPLICATE_OBJ_NAME: Rack Roles, Tenants, Sites, Rack-Groups and Racks should all have a unique name
        input_data = [
            (all_rr, "rack-roles", "rack_role.name"),
            (all_val_tnt["tnt"], "tenants", "tenant.name"),
            (all_val_tnt["site"], "sites", "tenant.site.name"),
            (all_val_tnt["loc"], "location", "tenant.site.location.name"),
            (all_val_tnt["rack"], "racks", "tenant.site.location.rack.name"),
        ]
        for list_of_names, obj, err_msg in input_data:
            duplicate_in_list(
                list_of_names, [err_msg, obj, "name"], self.org_errors, ""
            )

        # ERROR: Prints error message of all issues found
        if len(self.org_errors) != 0:
            print_error(self.org_errors, "ORGANISATION")


# ----------------------------------------------------------------------------
# 2. DEVICES: Validate formatting of variables for objects within the Devices menu
# ----------------------------------------------------------------------------
class Devices:
    def __init__(
        self, mftr: list[dict[str, Any]], dvc_role: list[dict[str, Any]] | None
    ) -> None:
        self.mftr = mftr
        self.dvc_role = dvc_role
        self.dvc_errors: list[str] = []

    # DEVICE_ROLE: If defined asserts it is a list. and checks that each dict has a name creating a list of all rack-role names
    def val_dvc_role(self) -> list[str]:
        all_dvc_roles: list[str] = []

        if self.dvc_role is not None:
            try:
                assert isinstance(self.dvc_role, list), (
                    "-device_role: Device-role must be a list"
                )
                for each_dvc_role in self.dvc_role:
                    if each_dvc_role.get("name") is not None:
                        assert_boolean(
                            "device_role.vm_role", each_dvc_role, self.dvc_errors
                        )
                        all_dvc_roles.append(each_dvc_role["name"])
                    elif each_dvc_role.get("name") is None:
                        self.dvc_errors.append(
                            "-device_role.name: A device-role is missing a name, this is a mandatory dictionary"
                        )
            except AssertionError as e:
                self.dvc_errors.append(str(e))
        return all_dvc_roles

    def val_mftr(self) -> dict[str, list[str]]:
        all_val_mftr: dict[str, list[str]] = dict(mftr=[], pltm=[])

        for each_mftr in self.mftr:
            try:
                # MFTR_NAME: Every manufacturer must have a name and validates tag
                assert each_mftr.get("name") is not None, (
                    "-manufacturer.name: A manufacturer is missing a name, this is a mandatory dictionary"
                )
                assert_dict("manufacturer.tags", each_mftr, self.dvc_errors)
                all_val_mftr["mftr"].append(each_mftr["name"])
                if each_mftr.get("platform") is not None:
                    # PLATFORM: If defined a platform must be a list. If not failfast as cant do any of the further checks
                    assert isinstance(each_mftr["platform"], list), (
                        f"-manufacturer.platform: Platform in manufacturer '{each_mftr['name']}' must be a list"
                    )
                    for each_pltm in each_mftr["platform"]:
                        # PLATFORM_NAME: Every site must have a name
                        if each_pltm.get("name") is None:
                            self.dvc_errors.append(
                                f"-manufacturer.platform.name: A platform in manufacturer '{each_mftr['name']}' is missing a name, this is a mandatory dictionary"
                            )
                        elif each_pltm.get("name") is not None:
                            assert_dict(
                                "manufacturer.platform.tags", each_pltm, self.dvc_errors
                            )
                            all_val_mftr["pltm"].append(each_pltm["name"])
                if each_mftr.get("device_type") is not None:
                    # DVC_TYPE: If defined a Device type must be a list.
                    assert_list("manufacturer.device_type", each_mftr, self.dvc_errors)
            except AssertionError as e:
                self.dvc_errors.append(str(e))
        return all_val_mftr

    def engine(self) -> None:
        all_dvc_role = self.val_dvc_role()
        all_val_mftr = self.val_mftr()
        all_obj.extend(all_val_mftr["mftr"])
        # DUPLICATE_OBJ_NAME: Device Roles, Manufacturers and Platforms should all have a unique name
        input_data = [
            (all_dvc_role, "device-roles", "device_role.name"),
            (all_val_mftr["mftr"], "manufacturer", "manufacturer.name"),
            (all_val_mftr["pltm"], "platforms", "manufacturer.platform.name"),
        ]
        for list_of_names, obj, err_msg in input_data:
            duplicate_in_list(
                list_of_names, [err_msg, obj, "name"], self.dvc_errors, ""
            )
        # ERROR: Prints error message of all issues found
        if len(self.dvc_errors) != 0:
            print_error(self.dvc_errors, "DEVICE")


# ----------------------------------------------------------------------------
# 4. IPAM: Validate formatting of variables for objects within the IPAM menu
# ----------------------------------------------------------------------------
class Ipam:
    def __init__(self, rir: list[dict[str, Any]], role: list[dict[str, Any]]) -> None:
        self.rir = rir
        self.role = role
        self.ipam_errors: list[str] = []

    # DEVICE_ROLE: If defined asserts it is a list. and checks that each dict has a name creating a list of all rack-role names
    def val_rir(self) -> list[str]:
        all_rir: list[str] = []

        for each_rir in self.rir:
            try:
                # RIR_NAME: Every RIR must have a name and tag validation
                assert each_rir.get("name") is not None, (
                    "-rir.name: A RIR is missing a name, this is a mandatory dictionary"
                )
                assert_dict("rir.tags", each_rir, self.ipam_errors)
                all_rir.append(each_rir["name"])
                assert_boolean("rir.is_private", each_rir, self.ipam_errors)
                # RIR_AGGREGATES: If defined a must be a list, if not failfast as cant do any of the further checks
                if each_rir.get("aggregate") is not None:
                    assert isinstance(each_rir["aggregate"], list), (
                        f"-rir.aggregate: Aggregate in RIR '{each_rir.get('name')}' must be a list"
                    )
                    for each_aggr in each_rir["aggregate"]:
                        # RIR_PREFIX: Must be defined and a valid IPv4 or IPv6 address
                        if each_aggr.get("prefix") is not None:
                            if "." in each_aggr["prefix"]:
                                assert_ipv4(
                                    "rir.aggregate.prefix", each_aggr, self.ipam_errors
                                )
                            elif ":" in each_aggr["prefix"]:
                                assert_ipv6(
                                    "rir.aggregate.prefix", each_aggr, self.ipam_errors
                                )
                            # RIR_TAG: If defined must be a dict
                            assert_dict(
                                "rir.aggregate.tags", each_aggr, self.ipam_errors
                            )
                        elif each_aggr.get("prefix") is None:
                            self.ipam_errors.append(
                                f"-rir.ranges.prefix: A prefix is missing for one of the ranges in RIR '{each_rir['name']}', this is a mandatory dictionary"
                            )
            except AssertionError as e:
                self.ipam_errors.append(str(e))
        return all_rir

    def val_role(self) -> list[str]:
        all_role: list[str] = []

        for each_role in self.role:
            try:
                # ROLE_NAME: Every Role must have a name and validate tag
                assert each_role.get("name") is not None, (
                    "-role.name: A prefix/VLAN-role is missing a name, this is a mandatory dictionary"
                )
                # assert_dict("role.tags", each_role, self.ipam_errors)
                all_role.append(each_role["name"])
                # ROLE_SITE: A role must have a site dictionary whose key is a list
                assert each_role.get("site") is not None, (
                    f"-role.site: Prefix/VLAN-role '{each_role['name']}' has no list of sites, this is a mandatory dictionary"
                )
                assert isinstance(each_role["site"], list), (
                    f"-role.site: Site within role '{each_role['name']}' must be a list of sites"
                )

                for each_site in each_role["site"]:
                    all_vl_grp: list[str] = []
                    all_vrf: list[str] = []
                    # SITE_EXIST: Assert that the specified site of the role exists (is in organisation dictionary)
                    assert_in(
                        "role.site",
                        each_site.get("name"),
                        all_site,
                        each_role["name"],
                        self.ipam_errors,
                    )
                    # VLAN_GRP: Must be a list and tags are valid
                    if each_site.get("vlan_grp") is not None:
                        assert isinstance(each_site["vlan_grp"], list), (
                            f"-role.site.vlan_grp: VLAN-group within Site '{each_site['name']}' must be a list"
                        )
                        for each_vl_grp in each_site["vlan_grp"]:
                            all_vl_name: list[str] = []
                            all_vl_numb: list[int] = []
                            if each_vl_grp.get("name") is not None:
                                assert_dict(
                                    "role.site.vlan_grp.tags",
                                    each_vl_grp,
                                    self.ipam_errors,
                                )
                                all_vl_grp.append(each_vl_grp["name"])
                                # VL_GRP TNT: If defined make sure tenant exists
                                assert_in(
                                    "role.site.vlan_grp.tenant",
                                    each_vl_grp.get("tenant"),
                                    all_tnt,
                                    each_vl_grp["name"],
                                    self.ipam_errors,
                                )
                                if each_vl_grp.get("vlan") is not None:
                                    # VLAN: Must be a list and validates tag
                                    assert isinstance(each_vl_grp["vlan"], list), (
                                        f"-role.site.vlan_grp.vlan: VLAN within VLAN-group '{each_vl_grp['name']}' must be a list"
                                    )
                                    for each_vl in each_vl_grp["vlan"]:
                                        if each_vl.get("name") is not None:
                                            assert_dict(
                                                "role.site.vlan_grp.vlan.tags",
                                                each_vl,
                                                self.ipam_errors,
                                            )
                                            all_vl_name.append(each_vl["name"])
                                            if each_vl.get("id") is not None:
                                                all_vl_numb.append(each_vl["id"])
                                                # VLAN_ID: Must exist and be an integer
                                                assert_integer(
                                                    "role.site.vlan_grp.vlan.id",
                                                    each_vl,
                                                    self.ipam_errors,
                                                )
                                            elif each_vl.get("id") is None:
                                                self.ipam_errors.append(
                                                    f"-role.site.vlan_grp.vlan.id: VLAN '{each_vl['name']}' has no VLAN id, this is a mandatory dictionary"
                                                )
                                            # VL TNT: If defined make sure tenant exists
                                            assert_in(
                                                "role.site.vlan_grp.vlan.tenant",
                                                each_vl.get("tenant"),
                                                all_tnt,
                                                each_vl["name"],
                                                self.ipam_errors,
                                            )
                                        # VLAN_NAME: Every Group must have a name
                                        elif each_vl.get("name") is None:
                                            self.ipam_errors.append(
                                                f"-role.site.vlan_grp.vlan.name: A VLAN within VLAN-group '{each_vl_grp['name']}' has no name, this is a mandatory dictionary"
                                            )
                                    # VRF_PREFIX: Asserts VRF and Prefix variables exist for VRFs under the VLAN Group (prefixes associated to VLANs like physical site)
                                    assert_vrf_pfx(
                                        each_vl_grp,
                                        "role.site.vlan_grp.vrf",
                                        all_vrf,
                                        all_vl_numb,
                                        self.ipam_errors,
                                    )
                                # VLAN_GRP_NAME: Every VLAN Group must have a name
                                elif each_vl_grp.get("name") is None:
                                    self.ipam_errors.append(
                                        f"-role.site.vlan_grp.name: A VLAN-group within site '{each_site['name']}' has no name, this is a mandatory dictionary"
                                    )
                                # DUPLICATE_VLAN: VLAN names and Numbers within a VLAN group should all be unique
                                duplicate_in_list(
                                    all_vl_name,
                                    ["role.site.vlan_grp.vlan.name", "VLANs", "name"],
                                    self.ipam_errors,
                                    "within a VLAN-group",
                                )
                                duplicate_in_list(
                                    [str(x) for x in all_vl_numb],
                                    ["role.site.vlan_grp.vlan.id", "VLANs", "ID"],
                                    self.ipam_errors,
                                    "within a VLAN-group",
                                )
                        # VRF_PREFIX: Asserts VRF and Prefix variables exist for VRFs not associated to VLANs (such as cloud prefixes)
                        assert_vrf_pfx(
                            each_site,
                            "role.site.vlan_grp.vrf",
                            all_vrf,
                            [],
                            self.ipam_errors,
                        )
                    # SITE_NAME: Every site must have a name
                    else:
                        try:
                            each_site["name"]
                        except (KeyError, TypeError):
                            self.ipam_errors.append(
                                f"-role.site.name: A site in prefix/VLAN-role '{each_role['name']}' is missing a name, this is a mandatory dictionary"
                            )
                    # DUPLICATE_VRF: VRFs within a site should all be unique
                    duplicate_in_list(
                        all_vrf,
                        ["role.site.vlan_grp.vrf.name", "VRFs", "name"],
                        self.ipam_errors,
                        "within a site",
                    )
            except AssertionError as e:
                self.ipam_errors.append(str(e))
        return all_role

    def engine(self) -> None:
        all_rir = self.val_rir()
        all_role = self.val_role()
        # DUPLICATE_OBJ_NAME: RIRs and Roles should all have a unique name
        duplicate_in_list(all_rir, ["rir.name", "RIRs", "name"], self.ipam_errors, "")
        duplicate_in_list(
            all_role, ["role.name", "roles", "name"], self.ipam_errors, ""
        )
        # ERROR: Prints error message of all issues found
        if len(self.ipam_errors) != 0:
            print_error(self.ipam_errors, "IPAM")


# ----------------------------------------------------------------------------
# 5. CIRCUITS: Validate formatting of variables for objects within the Circuits menu
# ----------------------------------------------------------------------------
class Circuits:
    def __init__(
        self, crt_type: list[dict[str, Any]], pvdr: list[dict[str, Any]]
    ) -> None:
        self.crt_type = crt_type
        self.pvdr = pvdr
        self.crt_errors: list[str] = []

    # CIRCUIT_TYPE: Checks that each dict has a name and creates a list of all rack-role names
    def val_crt_type(self) -> list[str]:
        all_crt_type: list[str] = []

        for each_crt_type in self.crt_type:
            try:
                assert each_crt_type.get("name") is not None, (
                    "-circuit_type.name: A circuit-type is missing a name, this is a mandatory dictionary"
                )
                # TAG: If defined must be a dict
                assert_dict("circuit_type.tags", each_crt_type, self.crt_errors)
                all_crt_type.append(each_crt_type["name"])
            except AssertionError as e:
                self.crt_errors.append(str(e))
        return all_crt_type

    def val_pvdr(self, all_crt_type: list[str]) -> dict[str, list[str]]:
        all_val_pvdr: dict[str, list[str]] = dict(pvdr=[], cid=[])
        for each_pvdr in self.pvdr:
            try:
                # PVDR_NAME: Every provider must have a name
                assert each_pvdr.get("name") is not None, (
                    "-provider.name: A provider is missing a name, this is a mandatory dictionary"
                )
                all_val_pvdr["pvdr"].append(each_pvdr["name"])
                # ASN: Must be an integrar
                assert_integer("provider.asn", each_pvdr, self.crt_errors)
                # TAG: If defined must be a dict
                assert_dict("provider.tags", each_pvdr, self.crt_errors)
                assert each_pvdr.get("circuit") is not None, (
                    f"-provider.circuit: Provider '{each_pvdr['name']}' has no list of circuits, this is a mandatory dictionary"
                )
                assert isinstance(each_pvdr["circuit"], list), (
                    f"-provider.circuit: Circuit in provider '{each_pvdr.get('name')}' must be a list"
                )
                for each_crt in each_pvdr["circuit"]:
                    if each_crt.get("cid") is not None:
                        all_val_pvdr["cid"].append(str(each_crt["cid"]))
                        # CRT_TYPE: Must be from the pre-defined types
                        assert_in(
                            "provider.circuit.type",
                            each_crt.get("type", all_crt_type[0]),
                            all_crt_type,
                            each_crt["cid"],
                            self.crt_errors,
                        )
                        # CMT_RATE: Commit Rate must be an integer
                        assert_integer(
                            "provider.circuit.commit_rate", each_crt, self.crt_errors
                        )
                        # TAG: Must be a dict
                        assert_dict("provider.circuit.tags", each_crt, self.crt_errors)
                        # TNT: Asserts specified Tenant exists
                        assert_in(
                            "provider.circuit.tenant",
                            each_crt.get("tenant"),
                            all_tnt,
                            each_crt["cid"],
                            self.crt_errors,
                        )
                    # CRT_CID: Every Circuit must have a CID/name
                    elif each_crt.get("cid") is None:
                        self.crt_errors.append(
                            f"-provider.circuit.name: A Circuit in provider '{each_pvdr['name']}' is missing a name, this is a mandatory dictionary"
                        )
            except AssertionError as e:
                self.crt_errors.append(str(e))
        return all_val_pvdr

    def engine(self) -> None:
        all_crt_type = self.val_crt_type()
        all_val_pvdr = self.val_pvdr(all_crt_type)
        all_obj.extend(all_val_pvdr["pvdr"])
        all_obj.extend(all_val_pvdr["cid"])

        # DUPLICATE_OBJ_NAME: Circuit Types, Providers and CIDs should all have a unique name
        input_data = [
            (all_crt_type, "crt_type.name", "circuit-types"),
            (all_val_pvdr["pvdr"], "provider.name", "providers"),
            (all_val_pvdr["cid"], "provider.circuit.cid", "circuits"),
        ]
        for list_of_names, obj, err_msg in input_data:
            duplicate_in_list(
                list_of_names, [err_msg, obj, "name"], self.crt_errors, ""
            )
        # ERROR: Prints error message of all issues found
        if len(self.crt_errors) != 0:
            print_error(self.crt_errors, "CIRCUIT")


# ----------------------------------------------------------------------------
# 6. VIRTUAL: Validate formatting of variables for objects within the virtualization menu
# ----------------------------------------------------------------------------
class Virtualisation:
    def __init__(
        self, cltr_grp: list[dict[str, Any]] | None, cltr_type: list[dict[str, Any]]
    ) -> None:
        self.cltr_grp = cltr_grp
        self.cltr_type = cltr_type
        self.vrtl_errors: list[str] = []

    # CLUSTER_GRP: If defined asserts it is a list, checks each dict has a name, validates tags and creates a list of all cluster group names
    def val_cltr_grp(self) -> list[str]:
        all_cltr_grp: list[str] = []

        if self.cltr_grp is not None:
            try:
                assert isinstance(self.cltr_grp, list), (
                    "-cluster_group: Cluster-group must be a list"
                )
                for each_cltr_grp in self.cltr_grp:
                    if each_cltr_grp.get("name") is not None:
                        assert_dict(
                            "cluster_group.tags", each_cltr_grp, self.vrtl_errors
                        )
                        all_cltr_grp.append(each_cltr_grp["name"])
                    elif each_cltr_grp.get("name") is None:
                        self.vrtl_errors.append(
                            "-cluster_group.name: A cluster-group is missing a name, this is a mandatory dictionary"
                        )
            except AssertionError as e:
                self.vrtl_errors.append(str(e))
        return all_cltr_grp

    def val_cltr_type(self, all_cltr_grp: list[str]) -> dict[str, list[str]]:
        all_cltr_type: dict[str, list[str]] = dict(cltr_type=[], cltr=[])

        for each_cltr_type in self.cltr_type:
            try:
                # CLTR_TYPE_NAME: Every Cluster Type must have a name
                assert each_cltr_type.get("name") is not None, (
                    "-cluster_type.name: A cluster-type is missing a name, this is a mandatory dictionary"
                )
                all_cltr_type["cltr_type"].append(each_cltr_type["name"])
                # TNT_SITE_GRP_TAG: Asserts all 3 exist and validate the tag
                assert_dict("cluster_type.tags", each_cltr_type, self.vrtl_errors)
                assert_in_tnt_site_grp(
                    "cluster_type", each_cltr_type, all_cltr_grp, self.vrtl_errors
                )
                if each_cltr_type.get("cluster") is not None:
                    assert isinstance(each_cltr_type["cluster"], list), (
                        f"-cluster_type.cluster: Cluster in cluster-type '{each_cltr_type['name']}' must be a list"
                    )
                    for each_cltr in each_cltr_type["cluster"]:
                        if each_cltr.get("name") is not None:
                            # TNT_SITE_GRP_TAG: Asserts all 3 exist and validate the tag
                            assert_dict(
                                "cluster_type.cluster.tags", each_cltr, self.vrtl_errors
                            )
                            assert_in_tnt_site_grp(
                                "cluster_type.cluster",
                                each_cltr,
                                all_cltr_grp,
                                self.vrtl_errors,
                            )
                            all_cltr_type["cltr"].append(each_cltr["name"])
                        elif each_cltr.get("name") is None:
                            self.vrtl_errors.append(
                                f"-cluster_group.cluster.name: A cluster in cluster-type '{each_cltr_type['name']}' is missing a name, this is a mandatory dictionary"
                            )
            except AssertionError as e:
                self.vrtl_errors.append(str(e))
        return all_cltr_type

    def engine(self) -> None:
        all_cltr_grp = self.val_cltr_grp()
        all_cltr_type = self.val_cltr_type(all_cltr_grp)
        all_obj.extend(all_cltr_grp)
        all_obj.extend(all_cltr_type["cltr"])

        # DUPLICATE_OBJ_NAME: Circuit Types, Providers and CIDs should all have a unique name
        input_data = [
            (all_cltr_grp, "cluster_group.name", "cluster-groups"),
            (all_cltr_type["cltr_type"], "cluster_type.name", "cluster-types"),
            (all_cltr_type["cltr"], "cluster_type.cluster.name", "clusters"),
        ]
        for list_of_names, obj, err_msg in input_data:
            duplicate_in_list(
                list_of_names, [err_msg, obj, "name"], self.vrtl_errors, ""
            )
        # ERROR: Prints error message of all issues found
        if len(self.vrtl_errors) != 0:
            print_error(self.vrtl_errors, "VIRTUALIZATION")


# ----------------------------------------------------------------------------
# 7. CONTACT: Validate formatting of variables for objects for contact assignment
# ----------------------------------------------------------------------------
class Contacts:
    def __init__(
        self,
        cnt_role: list[dict[str, Any]],
        cnt_grp: list[dict[str, Any]],
        cnt_asgn: list[dict[str, Any]],
    ) -> None:
        self.cnt_role = cnt_role
        self.cnt_grp = cnt_grp
        self.cnt_asgn = cnt_asgn
        self.cnt_errors: list[str] = []

    # CONTACT_ROLE: Checks that each dict has a name creating a list of all contact-role names
    def val_cnt_role(self) -> list[str]:
        all_cnt_role: list[str] = []

        for each_cnt_role in self.cnt_role:
            if each_cnt_role.get("name") is not None:
                assert_dict("contact_role.tags", each_cnt_role, self.cnt_errors)
                all_cnt_role.append(each_cnt_role["name"])
            elif each_cnt_role.get("name") is None:
                self.cnt_errors.append(
                    "-contact_role.name: A contact_role is missing a name, this is a mandatory dictionary"
                )
        return all_cnt_role

    def val_cnt_grp(self) -> dict[str, list[str]]:
        val_cnt_grp: dict[str, list[str]] = dict(grp=[], cnt=[])

        for each_cnt_grp in self.cnt_grp:
            try:
                # CONTACT_GROUP: Validates group has a name
                assert each_cnt_grp.get("name") is not None, (
                    "-contact_group.name: A contact-group is missing a name, this is a mandatory dictionary"
                )
                assert_dict("contact_group.tags", each_cnt_grp, self.cnt_errors)
                val_cnt_grp["grp"].append(each_cnt_grp["name"])
                # CONTACT: Validates name and tags
                if each_cnt_grp.get("contact") is not None:
                    assert isinstance(each_cnt_grp["contact"], list), (
                        f"-contact_group.contact: Contact in contact-group '{each_cnt_grp['name']}' must be a list"
                    )
                    for each_cnt in each_cnt_grp["contact"]:
                        if each_cnt.get("name") is not None:
                            assert_dict(
                                "contact_group.contact.tags", each_cnt, self.cnt_errors
                            )
                            val_cnt_grp["cnt"].append(each_cnt["name"])
                        elif each_cnt.get("name") is None:
                            self.cnt_errors.append(
                                f"-contact_group.contact.name: A contact in contact-group '{each_cnt_grp['name']}' is missing a name, this is a mandatory dictionary"
                            )
            except AssertionError as e:
                self.cnt_errors.append(str(e))
        return val_cnt_grp

    def val_cnt_asgn(
        self, all_cnt_role: list[str], all_cnt_grp: dict[str, list[str]]
    ) -> None:

        for each_cnt_asgn in self.cnt_asgn:
            try:
                # ASGN_TO_EXIST: Checks assign_to exists and is a dictionary (fails if not as used in naming for other errors)
                assert each_cnt_asgn.get("assign_to") is not None, (
                    "-contact_assign.assign_to: A contact_assign is missing assign_to, this is a mandatory dictionary"
                )
                assert isinstance(each_cnt_asgn["assign_to"], dict), (
                    f"-contact_assign.assign_to: An assign_to element is not dictionary"
                )
                # ASGN_TO_CONTENT: Checks assign_to key is one of allowed and value is an existing object
                for asgn_type, asgn_name in each_cnt_asgn["assign_to"].items():
                    assert_regex_match(
                        "contact_assign.assign_to",
                        asgn_type,
                        "^(tenant|site|location|rack|manufacturer|clustergroup|cluster|provider|circuit)",
                        asgn_name,
                        self.cnt_errors,
                    )
                    assert_in(
                        "contact_assign.assign_to",
                        asgn_name,
                        all_obj,
                        asgn_type,
                        self.cnt_errors,
                    )
                # PRIORITY: Checks that the priority is on4 of allowed options
                assert_regex_match(
                    "contact_assign.role.priority",
                    each_cnt_asgn.get("priority", "primary"),
                    "^(primary|secondary|tertiary|inactive)",
                    "",
                    self.cnt_errors,
                )
                # ROLE: Checks that the role is defined and exists
                if each_cnt_asgn.get("role") is not None:
                    assert_in(
                        "contact_assign.role",
                        each_cnt_asgn["role"],
                        all_cnt_role,
                        each_cnt_asgn["assign_to"],
                        self.cnt_errors,
                    )
                elif each_cnt_asgn.get("role") is None:
                    self.cnt_errors.append(
                        f"-contact_assign.role: A role for assign_to '{each_cnt_asgn['assign_to']}' is missing, this is a mandatory dictionary"
                    )
                # CONTACT: Checks that the contact is defined and exists
                assert each_cnt_asgn.get("contact") is not None, (
                    "-contact_assign.contact: A contact_assignment is missing a list of contacts, this is a mandatory dictionary"
                )
                assert isinstance(each_cnt_asgn["contact"], list), (
                    f"-contact_assign.contact: An assign_to contact is not a list, should be a list of contacts"
                )
                for each_cnt in each_cnt_asgn["contact"]:
                    assert_in(
                        "contact_assign.contact",
                        each_cnt,
                        all_cnt_grp["cnt"],
                        each_cnt_asgn["assign_to"],
                        self.cnt_errors,
                    )
            except AssertionError as e:
                self.cnt_errors.append(str(e))

    def engine(self) -> None:

        all_cnt_role = self.val_cnt_role()
        all_cnt_grp = self.val_cnt_grp()
        self.val_cnt_asgn(all_cnt_role, all_cnt_grp)

        # DUPLICATE_OBJ_NAME: RIRs and Roles should all have a unique name
        duplicate_in_list(
            all_cnt_role,
            ["contact-role.name", "contact-role", "name"],
            self.cnt_errors,
            "",
        )
        duplicate_in_list(
            all_cnt_grp["grp"],
            ["contact-group.name", "contact-group", "name"],
            self.cnt_errors,
            "",
        )
        # ERROR: Prints error message of all issues found
        if len(self.cnt_errors) != 0:
            print_error(self.cnt_errors, "CONTACTS")


# ----------------------------------------------------------------------------
# ENGINE: Runs the methods of the script
# ----------------------------------------------------------------------------


def main() -> None:
    global are_errors, rc, all_site, all_tnt, all_obj
    are_errors = False
    my_theme = {"repr.ipv4": "none", "repr.number": "none", "repr.call": "none"}
    rc = Console(theme=Theme(my_theme))
    parent_dict_err: list[str] = []
    missing_mandatory = defaultdict(list)
    my_vars = input_val(input_directory, argv)

    # Populate these to stop alerts if not running all script elements (covers the dependencies)
    all_obj = []
    all_tnt = []
    all_site = []

    # 1. PARENT: If a parent mandatory dict is defined validates it is list, if not FAILFAST
    for parent_dict in [
        "tenant",
        "manufacturer",
        "device_role",
        "rir",
        "role",
        "circuit_type",
        "provider",
        "cluster_type",
        "contact_role",
        "contact_group",
        "contact_assign",
    ]:
        if my_vars.get(parent_dict) is not None:
            assert_list(parent_dict, my_vars, parent_dict_err)
        # FAILFAST: Exit script if is not a list as cant do further tests without these dicts
        if len(parent_dict_err) != 0:
            print_error(parent_dict_err, "PARENT DICTIONARY")
            sys.exit(1)

    # 2. ORG: Validate formatting of Organisation menu dictionaries if mandatory dicts exist
    if my_vars.get("tenant") is not None:
        org = Organisation(my_vars["tenant"], my_vars.get("rack_role"))
        org.engine()
    else:
        missing_mandatory["Organisation"].append("tenant")

    # 3. DEVICES: Validate formatting of Device menu dictionaries if mandatory dicts exist
    if (
        my_vars.get("manufacturer") is not None
        and my_vars.get("device_role") is not None
    ):
        dvc = Devices(my_vars.get("manufacturer", []), my_vars.get("device_role"))
        dvc.engine()
    else:
        if my_vars.get("manufacturer") is None:
            missing_mandatory["Devices"].append("manufacturer")
        if my_vars.get("device_role") is None:
            missing_mandatory["Devices"].append("device_role")

    # 4. IPAM: Validate formatting of IPAM menu dictionaries if mandatory dicts exist
    if my_vars.get("rir") is not None and my_vars.get("role") is not None:
        ipam = Ipam(my_vars["rir"], my_vars["role"])
        ipam.engine()
    else:
        if my_vars.get("rir") is None:
            missing_mandatory["IPAM"].append("rir")
        if my_vars.get("role") is None:
            missing_mandatory["IPAM"].append("role")

    # 5. CIRCUITS: Validate formatting of Circuit menu dictionaries if mandatory dicts exist
    if my_vars.get("circuit_type") is not None and my_vars.get("provider") is not None:
        crt = Circuits(my_vars["circuit_type"], my_vars["provider"])
        crt.engine()
    else:
        if my_vars.get("circuit_type") is None:
            missing_mandatory["Circuits"].append("circuit_type")
        if my_vars.get("provider") is None:
            missing_mandatory["Circuits"].append("provider")

    # 6. VIRTUAL: Validate formatting of Virtualization menu dictionaries if mandatory dicts exist
    if my_vars.get("cluster_type") is not None:
        vrtl = Virtualisation(my_vars.get("cluster_group"), my_vars["cluster_type"])
        vrtl.engine()
    else:
        missing_mandatory["Virtualisation"].append("cluster_type")

    # 7. CONTACTS: Validate formatting of Contacts dictionaries if mandatory dicts exist
    if (
        my_vars.get("contact_role") is not None
        and my_vars.get("contact_group") is not None
        and my_vars.get("contact_assign") is not None
    ):
        cnt = Contacts(
            my_vars["contact_role"],
            my_vars["contact_group"],
            my_vars["contact_assign"],
        )
        cnt.engine()
    else:
        if my_vars.get("contact_role") is None:
            missing_mandatory["Contacts"].append("contact_role")
        if my_vars.get("contact_group") is None:
            missing_mandatory["Contacts"].append("contact_group")
        if my_vars.get("contact_assign") is None:
            missing_mandatory["Contacts"].append("contact_assign")

    print("\n")
    if len(missing_mandatory) != 0:
        rc.print(
            f"⚠️  The following mandatory dictionaires are missing from input the files, ignore this if not validating those objects"
        )
        for menu, obj in missing_mandatory.items():
            rc.print(f"-{menu}: {', '.join(obj)}")
    if not are_errors:
        input_dir = argv[1] if len(argv) > 1 else input_directory
        rc.print(
            f":white_check_mark: No errors found in the input file, use 'python nbox_env_setup.py {input_dir}' to build the NetBox environment."
        )


if __name__ == "__main__":
    main()
