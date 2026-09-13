from multiprocessing.connection import Listener
from typing import Any, Dict, List, Union
import pynetbox
from pynetbox.core.query import RequestError
import operator
import ast
from rich.console import Console
from rich.theme import Theme
import ipdb
from collections import defaultdict
import urllib3

urllib3.disable_warnings()


# ----------------------------------------------------------------------------
# INZT_LOAD: Opens netbox connection and loads the variable file
# ----------------------------------------------------------------------------
class Nbox:
    def __init__(
        self,
        netbox_url: str,
        token: str,
        ssl: bool,
        tag_exists: List,
        tag_created: List,
        rt_exists: List,
        rt_created: List,
    ):
        self.nb = pynetbox.api(url=netbox_url, token=token)
        self.nb.http_session.verify = ssl
        my_theme = {"repr.ipv4": "none", "repr.number": "none", "repr.call": "none"}
        self.rc = Console(theme=Theme(my_theme))
        self.tag_exists = tag_exists
        self.tag_created = tag_created
        self.rt_exists = rt_exists
        self.rt_created = rt_created

    # ----------------------------------------------------------------------------
    # OBJ_CHECK: API call to check if objects already exists in Netbox (e.g. Tenants, tenancy.tenants, tnt, name)
    # ----------------------------------------------------------------------------
    def obj_check(
        self, api_attr: str, obj_fltr: str, obj_dm: List[Dict[str, Any]]
    ) -> Dict[str, List]:
        # Creates 2 lists of DMs based on whether the object already exists or not
        obj_notexist_dm, obj_exist_name = ([] for i in range(2))
        for each_obj_dm in obj_dm:
            # For checking complex filter (filter based on more than 1 item)
            if obj_fltr == "multi-fltr":
                fltr = each_obj_dm["chk_fltr"]
            # For checking all other contacts
            else:
                fltr = {obj_fltr: each_obj_dm[obj_fltr]}
            # GET: Majority of API calls will produce one result (as most objects unique) so can use the get method
            try:
                # GBL_VRF: If in Netbox global VRF ignore (name null)
                if api_attr == "ipam.vrfs" and each_obj_dm["name"] == None:
                    pass
                # If not exist add DM for object to list to be created
                elif operator.attrgetter(api_attr)(self.nb).get(**fltr) == None:
                    obj_notexist_dm.append(each_obj_dm)
                # If object exists various methods used to add name to list for stdout
                else:
                    if obj_fltr == "slug":
                        obj_exist_name.append(
                            each_obj_dm["name"] + f" ({each_obj_dm[obj_fltr]})"
                        )
                    else:
                        try:
                            obj_exist_name.append(each_obj_dm[obj_fltr])
                        except:
                            obj_exist_name.append(
                                each_obj_dm.get(each_obj_dm["obj_fltr"], "")
                            )
            # FLTR: For odd excpetion where objects not unique uses the filter method
            except:
                obj_result = list(operator.attrgetter(api_attr)(self.nb).filter(**fltr))
                for each_rslt in obj_result:
                    # GBL_VRF_PFX: To differentiate between prefixes in null and in VRFs
                    if api_attr == "ipam.prefixes":
                        # breakpoint()
                        if each_rslt["vrf"] == fltr.get("vrf_id", fltr.get("vrf")):
                            obj_exist_name.append(each_obj_dm[obj_fltr])
                        elif each_rslt["vrf"]["id"] == fltr.get("vrf_id", fltr.get("vrf")):
                            obj_exist_name.append(each_obj_dm[obj_fltr])

        return dict(notexist_dm=obj_notexist_dm, exist_name=obj_exist_name)

    # ----------------------------------------------------------------------------
    # OBJ_CREATE: If not already present adds the object. If for any reason fails returns error message
    # ----------------------------------------------------------------------------
    def obj_create(
        self,
        output_name: str,
        api_attr: str,
        obj_notexist_dm: List,
        obj_exist_name: List,
    ) -> None:
        all_result = []
        if len(obj_notexist_dm) != 0:
            try:
                result = operator.attrgetter(api_attr)(self.nb).create(obj_notexist_dm)
            except RequestError as e:
                # ERR: Message is a string but has the format of list of dicts, literal_eval converts back into a list
                err_msg = ast.literal_eval(e.error)
                for err in err_msg["errors"]:
                    if len(err) != 0:  # safe guards against empty dicts
                        for obj, msg in err["errors"].items():
                            self.rc.print(f":x: {output_name} '{obj}' - {', '.join(msg)}")    
        # If result variable exists means an object was created
        if "result" in locals():
            all_result = result
        # PRINT: Prints object already exists or create message
        self.result_msg(output_name, obj_exist_name, all_result)

    # ----------------------------------------------------------------------------
    # RESULT_MSG: Reports if device was created or already existed
    # ----------------------------------------------------------------------------
    def result_msg(self, output_name: str, obj_exist_name: List, result: List) -> None:
        # EXISTING: Message returned if already exists (as long as no errors)
        if len(obj_exist_name) != 0:
            self.rc.print(
                f"⚠️  {output_name}: '{', '.join(obj_exist_name)}' already exist"
            )
        # NEW: Message returned if try/except created a new object
        if len(result) != 0:
            self.rc.print(
                f":white_check_mark: {output_name}: '{str(result).replace('[', '').replace(']', '')}' successfully created"
            )

    # ----------------------------------------------------------------------------
    # MERGE_DICT: Merges dictionaires for dev_type component error messages
    # ----------------------------------------------------------------------------
    def merge_dict(self, err_msg: List) -> str:
        tmp_err_msg = defaultdict(list)
        error = []
        # Merge all dicts with the same key
        for err in err_msg:
            if len(err) != 0:
                tmp_err_msg[list(err.keys())[0]].append(list(err.values())[0][0])
        # Remove all duplicates in value and turn into a list of string err message
        error = []
        for err_type, err in tmp_err_msg.items():
            tmp_err = set(err)
            error.append(err_type + ": " + ", ".join(tmp_err))
        # return a string of all errors
        return ", ".join(error)

    # ----------------------------------------------------------------------------
    # DEV_TYPE_COMP_CREATE: Adds components of the device_type (intf, power, etc)
    # ----------------------------------------------------------------------------
    def dev_type_comp_create(self, each_type: Dict[str, Any], output_name: str) -> List:
        component = dict(
            interface="interface_templates",
            power="power_port_templates",
            console="console_port_templates",
            rear_port="rear_port_templates",
            front_port="front_port_templates",
        )
        cmpt_created = []
        try:
            for cmpt, api in component.items():
                if len(each_type[cmpt]) != 0:
                    # Creates everything except 'Front-port' as it needs the rear-port ID to map to it (as name is shared)
                    if cmpt != "front_port":
                        operator.attrgetter(api)(self.nb.dcim).create(each_type[cmpt])
                    # front-port needs rear_port ID (using device_type ID) to get the  to map front to rear ports (patch-panels)
                    elif cmpt == "front_port":
                        dt_id = self.nb.dcim.device_types.get(slug=each_type["slug"]).id
                        for port in each_type[cmpt]:
                            port["rear_port"] = list(
                                self.nb.dcim.rear_port_templates.filter(
                                    name=port["name"], devicetype_id=dt_id
                                )
                            )[0].id
                        operator.attrgetter(api)(self.nb.dcim).create(each_type[cmpt])
                    cmpt_created.append(cmpt)
            return cmpt_created
        # DEV_TYPE_COMP_ERR: If dev_type component was not able to be created returns an error message
        except RequestError as e:
            err_msg = ast.literal_eval(e.error)
            error = self.merge_dict(err_msg)
            dev_model = each_type["model"]
            self.rc.print(
                f":x: {output_name}: Failed to create '{dev_model}' because of errors with '{cmpt}' component - {error}"
            )
            return []

    # ----------------------------------------------------------------------------
    # DEV_TYPE_CREATE: If not already present and no componets fail adds the device_type
    # ----------------------------------------------------------------------------
    def dev_type_create(
        self,
        output_name: str,
        api_attr: str,
        obj_notexist_dm: List,
        obj_exist_name: List,
    ) -> None:
        all_result = []
        if len(obj_notexist_dm) != 0:
            for each_type in obj_notexist_dm:
                # DEV_TYPE: Tries to create the device_type, if fails returns error message
                try:
                    result = operator.attrgetter(api_attr)(self.nb).create(each_type)
                    # DEV_TYPE_COMP: If dev_type creation succeeds tries to create each device_type component
                    comp_created = self.dev_type_comp_create(each_type, result)
                    # Dependant on component result either adds dev_type to result message or deletes
                    if len(comp_created) != 0:
                        all_result.append(
                            result
                        )  # add dev_type name to print success message
                    elif len(comp_created) == 0:
                        self.nb.dcim.device_types.get(model=each_type["model"]).delete()
                # DEV_TYPE_ERR: If dev_type was not able to be created returns an error message
                except RequestError as e:
                    # Converts string error message back into a list (literal_eval)
                    err_msg = ast.literal_eval(e.error)
                    for err in err_msg:
                        if len(err) != 0:
                            self.rc.print(
                                f":x: {output_name}: {list(err.keys())[0]} - {list(err.values())[0]}"
                            )
        # PRINT: Prints object already exists or create message
        self.result_msg(output_name, obj_exist_name, all_result)

    # ----------------------------------------------------------------------------
    # VLGRP/VRF_ID: Gets the ID for the VLAN Groups and Prefix VRFs
    # ----------------------------------------------------------------------------
    def get_vlgrp_site_vrf_id(
        self,
        api_attr: List[str],
        obj_fltr: List[str],
        obj_dm: Dict[str, Any],
        error: Dict[str, List],
    ) -> Dict[str, Any]:
        # VL_SITE: If no VLAN Group uses site ID instead to see if exists
        if api_attr[0] == "ipam.vlans" and obj_dm.get("group") == None:
            obj_fltr[1] = "site_id"
            api_attr[1] = "dcim.sites"
        # VL_GRP/VRF EXIST: Checks if VLAN_GRP or VRF exists, if so gets the id
        grp_site_vrf_name = obj_dm[obj_fltr[1].split("_")[0]]["name"]
        # FLTR: Create filter for VRF or VL-GRP as VRF needs RD to make unique
        if api_attr[1] == "ipam.vrfs":
            fltr = dict(name=grp_site_vrf_name, rd=obj_dm["vrf_rd"])
        else:
            fltr = dict(name=grp_site_vrf_name)
        # GBL_VRF: If in the netbox global routing table no need to get VRF ID
        if api_attr[0] == "ipam.prefixes" and obj_dm["vrf"]["name"] == None:
            obj_dm["vrf"] = None
            fltr = {obj_fltr[0]: obj_dm[obj_fltr[0]], "vrf": None}
            obj_dm["chk_fltr"] = fltr
            # Used to by object_chk to add name of VLAN/PFX to exist list (obj["exist_name"])
            obj_dm["multi-fltr"] = obj_dm[obj_fltr[0]]
            return obj_dm
        elif operator.attrgetter(api_attr[1])(self.nb).get(**fltr) != None:
            obj_id = operator.attrgetter(api_attr[1])(self.nb).get(**fltr).id
            # Adds object-id for VRF used for creating prefixes (not used if not VRF)
            obj_dm["vrf"] = obj_id
            # VLAN/PFX FLTR: Creates filter of IDs to check if VLAN or PFX already exists in VL_GRP or  VRF
            fltr = {
                obj_fltr[0]: obj_dm[obj_fltr[0]],
                obj_fltr[1]: obj_id,
            }
            obj_dm["chk_fltr"] = fltr
            # Used to by object_chk to add name of VLAN/PFX to exist list (obj["exist_name"])
            obj_dm["multi-fltr"] = obj_dm[obj_fltr[0]]
            return obj_dm

        # ERROR: If VRF or VL_GRP dont exist collects details for message (cant create VLAN/PFX without them)
        elif operator.attrgetter(api_attr[1])(self.nb).get(**fltr) == None:
            vl_pfx_name = obj_dm[obj_fltr[0]]
            error[grp_site_vrf_name].append(vl_pfx_name)

    # ----------------------------------------------------------------------------
    # PREFIX_VLAN: If is a Prefix associated to a VLAN checks against VL_GRP and role to get the unique ID
    # ----------------------------------------------------------------------------
    def get_vl_pfx_id(
        self, obj_dm: Dict[str, Any], error: Dict[str, List]
    ) -> Dict[str, Any]:
        if obj_dm.get("vlan") == None:
            return obj_dm
        # GET_VLAN_ID: If pfx has a vlan, if vl_grp or site exists gets the VLAN ID and add it to the dict
        elif obj_dm.get("vlan") != None:
            vlan = obj_dm["vlan"]
            # VL_GRP VLAN ID
            if obj_dm.get("vl_grp") != None:
                vl_grp = obj_dm["vl_grp"]
                try:
                    vl_grp_slug = self.nb.ipam.vlan_groups.get(name=vl_grp)["slug"]
                    obj_dm["vlan"] = self.nb.ipam.vlans.get(
                        vid=vlan, group=vl_grp_slug
                    ).id
                    return obj_dm
                # VLAN_NOT_EXIST: If the vlan does not exists collects details for message
                except:
                    pfx = obj_dm["prefix"]
                    error[vl_grp].append(f"{pfx} 'VLAN {vlan}'")
            # SITE VLAN ID
            elif obj_dm.get("site") != None:
                try:
                    site_id = self.nb.dcim.sites.get(**obj_dm["site"]).id
                    obj_dm["vlan"] = self.nb.ipam.vlans.get(
                        vid=vlan, site_id=site_id
                    ).id
                    return obj_dm
                # VLAN_NOT_EXIST: If the vlan does not exists collects details for message
                except:
                    pfx = obj_dm["prefix"]
                    error[vl_grp].append(f"{pfx} 'VLAN {vlan}'")

    # ----------------------------------------------------------------------------
    # CNT_ASGN_ID: Gets the ID for the assignment objects and contacts
    # ----------------------------------------------------------------------------
    def get_cnt_asgn_id(
        self, asgn: Dict[str, Any], api_fltr: str, error: List
    ) -> List[Dict[str, Any]]:
        api = asgn["object_type"] + "s"
        tmp_asgn = []
        # GET_ID: Get ID of the object the contact is to be assigned to
        try:
            if api == "virtualization.clustergroups":
                api = "virtualization.cluster-groups"
            obj_id = (
                operator.attrgetter(api)(self.nb)
                .get(**{api_fltr: asgn["object_id"]})
                .id
            )
            for each_cnt in asgn["contact"]:
                # GET_CNT_ID: Get ID of each contact
                try:
                    cnt_id = self.nb.tenancy.contacts.get(name=each_cnt).id
                    asgn_copy = asgn.copy()
                    asgn_copy["object_id"] = obj_id
                    asgn_copy["contact"] = cnt_id
                    # CHK: Create dictionary used for checking if assignment already exists
                    asgn_copy["chk_fltr"] = {
                        "object_type": asgn["object_type"],
                        "object_id": obj_id,
                        "contact_id": cnt_id,
                    }
                    # IDNTY: Used to identify obj in the already exist list (obj["exist_name"])
                    asgn_copy[
                        "multi-fltr"
                    ] = f"{each_cnt} {asgn['object_id']} ({asgn['object_type'].split('.')[1]})"
                    tmp_asgn.append(asgn_copy)
                except:
                    error.append(f"content - {each_cnt}")
        except:
            error.append(f"{asgn['object_type'].split('.')[1]} - {asgn['object_id']}")

        return tmp_asgn

    # ----------------------------------------------------------------------------
    # NBOX_ENGINE: Checks existence of objects and creates them if they do not exist
    # ----------------------------------------------------------------------------
    def engine(
        self, output_name: str, api_attr: str, obj_fltr: str, obj_dm: Dict[str, Any]
    ) -> None:
        # VRF: Adds RD to VRF object check as used to identify unique VRFs (VRFs dont have slugs)
        if output_name == "VRF":
            for each_obj_dm in obj_dm:
                each_obj_dm["chk_fltr"] = dict(
                    name=each_obj_dm["name"], rd=each_obj_dm.get("rd", "null")
                )
                each_obj_dm["obj_fltr"] = obj_fltr
            obj_fltr = "multi-fltr"

        # VL-GRP/VRF: Check object exists and get ID which is used when creating VLAN/PFX. Merges error message for all VL-GRP/VRF
        if output_name == "VLAN" or output_name == "Prefix":
            tmp_obj_dm = []
            err = defaultdict(list)
            for each_obj_dm in obj_dm:
                tmp = self.get_vlgrp_site_vrf_id(api_attr, obj_fltr, each_obj_dm, err)
                if tmp != None:
                    tmp_obj_dm.append(tmp)
            if len(err) != 0:
                api_name = api_attr[1].split(".")[1][:-1]
                for vlgrp_vrf, vl_pfx in err.items():
                    self.rc.print(
                        f":x: {output_name}: {', '.join(set(vl_pfx))} - The {api_name} '{vlgrp_vrf}' for this {output_name.lower()} does not exist"
                    )
            obj_dm = tmp_obj_dm
            api_attr = api_attr[0]
            obj_fltr = "multi-fltr"

        # CNT_ASGN: Has to gather object IDs for contact assignment. Merges error message for all CNT ASGN
        elif output_name == "Contact Assignment":
            tmp_obj_dm, err = ([] for i in range(2))
            for each_asgn in obj_dm:
                # NAME: Try get ID of the object the contact is to be assigned to using object name
                try:
                    if each_asgn["object_type"] == "circuits.circuit":
                        tmp_fltr = "cid"
                    else:
                        tmp_fltr = "name"
                    tmp_obj_dm.extend(self.get_cnt_asgn_id(each_asgn, tmp_fltr, err))
                except:
                    # SLUG: Try get ID of the object the contact is to be assigned to using object slug
                    try:
                        tmp_obj_dm.extend(self.get_cnt_asgn_id(each_asgn, "slug", err))
                    # If cant get the ID add object to error list
                    except:
                        err.append(
                            f"{each_asgn['object_type'].split('.')[1]} - {each_asgn['object_id']}"
                        )
            if len(err) != 0:
                self.rc.print(
                    f":x: {output_name}: Can't get the ID for the name or slug of: '{', '.join(set(err))}'"
                )
            obj_dm = tmp_obj_dm
            
        # CHK_OBJ: Check if object already exists.
        if len(obj_dm) != 0:
            obj = self.obj_check(api_attr, obj_fltr, obj_dm)

            # PRF_VL: If prefix is associated with vlan gets vlan ID. Merges error message for all VL/PFX
            if api_attr == "ipam.prefixes":
                tmp_obj = []
                err = defaultdict(list)
                for each_obj_dm in obj["notexist_dm"]:
                    tmp = self.get_vl_pfx_id(each_obj_dm, err)
                    if tmp != None:
                        tmp_obj.append(tmp)
                if len(err) != 0:
                    for vlgrp, pfx_vl in err.items():
                        self.rc.print(
                            f":x: {output_name}: {', '.join(set(pfx_vl))} in VLAN Group '{vlgrp}' does not exist"
                        )
                obj["notexist_dm"] = tmp_obj

            # CRTE_OBJ: Creates all objects
            if output_name == "Device-type":
                self.dev_type_create(
                    output_name, api_attr, obj["notexist_dm"], obj["exist_name"]
                )
            else:
                self.obj_create(
                    output_name, api_attr, obj["notexist_dm"], obj["exist_name"]
                )

    # ----------------------------------------------------------------------------
    # Methods that that provide Netbox interaction for DM building classes
    # ----------------------------------------------------------------------------
    # TAGS: Gathers ID of existing tag or creates new one and returns ID (list of IDs)
    def get_or_create_tag(self, tag: Dict[str, Any]) -> List:
        tags = []
        if tag != None:
            for name, colour in tag.items():
                name = str(name)
                tag = self.nb.extras.tags.get(name=name)
                if not tag:
                    tag = self.nb.extras.tags.create(
                        dict(name=name, slug=self.make_slug(name), color=colour)
                    )
                    self.tag_created.append(name)
                else:
                    self.tag_exists.append(name)
                tags.append(tag.id)
        return tags

    # RT: Gathers ID of existing RT or creates new one and returns ID (list of IDs)
    def get_or_create_rt(self, rt: Union[List, Dict[str, str]], tnt: str) -> List:
        all_rt = []
        if isinstance(rt, list):
            rt = dict.fromkeys(rt, "")
        if rt != None:
            for name, descr in rt.items():
                rt = self.nb.ipam.route_targets.get(name=name)
                if not rt:
                    fltr = {
                        "name": name,
                        "description": descr,
                        "tenant": self.name_none(tnt, {"name": tnt}),
                    }
                    rt = self.nb.ipam.route_targets.create(**fltr)
                    self.rt_created.append(name)
                else:
                    self.rt_exists.append(name)

                all_rt.append(rt.id)
        return all_rt

    # PRINT_TAG_RT: Prints the result of existing and newly created tags
    def print_tag_rt(self, input_msg, exists, created) -> None:
        if len(created) != 0:
            self.rc.print(
                f":white_check_mark: {input_msg}: '{', '.join(created)}' successfully created"
            )
        elif len(exists) != 0:
            self.rc.print(f"⚠️  {input_msg}: '{', '.join(exists)}' already exist")

    # SLUG: If slug is empty replaces it with tenant name (lowercase) replacing whitespace with '_'
    def make_slug(self, obj: str) -> str:
        if isinstance(obj, int):
            obj = str(obj)
        return obj.replace(" ", "_").lower()

    # TNT: Gets the tennat name for a a site fed into it (if API call fails leaves blank)
    def get_tnt(self, site: str) -> str:
        try:
            return dict(self.nb.dcim.sites.get(name=site))["tenant"]["name"]
        except:
            return None

    # NAME_NONE: Removes name from netbox filter if its value is None
    def name_none(self, name_value: str, full_key_value: Dict) -> str:
        if name_value == None:
            return name_value
        else:
            return full_key_value
