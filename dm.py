import os
from collections import defaultdict
from typing import Any

import yaml
from pynetbox.core.query import RequestError

from netbox import Nbox


# ----------------------------------------------------------------------------
# 2. ORG_TNT_SITE_RACK: Creates the DM for organisation objects tenant, site, rack-group and rack
# ----------------------------------------------------------------------------
class Organisation:
    def __init__(
        self,
        nbox: Nbox,
        tenant: list[dict[str, Any]],
        rack_role: list[dict[str, Any]],
    ) -> None:
        self.nb = nbox
        self.tenant = tenant
        self.rack_role = rack_role
        self.tnt: list[dict[str, Any]] = []
        self.site: list[dict[str, Any]] = []
        self.prnt_loc: list[dict[str, Any]] = []
        self.chld_loc: list[dict[str, Any]] = []
        self.rack: list[dict[str, Any]] = []
        self.rr: list[dict[str, Any]] = []

    # 2a. TNT: Create Tenant dictionary
    def cr_tnt(self, each_tnt: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_tnt["name"],
            slug=self.nb.make_slug(each_tnt.get("slug", each_tnt["name"])),
            description=each_tnt.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_tnt.get("tags")),
        )

    # 2b. SITE: Uses temp dict and joins as the ASN cant be None, it must be an integer.
    def cr_site(
        self, each_tnt: dict[str, Any], each_site: dict[str, Any]
    ) -> dict[str, Any]:
        temp_site = dict(
            name=each_site["name"],
            slug=self.nb.make_slug(each_site.get("slug", each_site["name"])),
            # tenant is a nested dict as uses name rather than id
            tenant=dict(name=each_tnt["name"]),
            time_zone=each_site.get("time_zone", "UTC"),
            description=each_site.get("descr", ""),
            physical_address=each_site.get("addr", ""),
            tags=self.nb.get_or_create_tag(each_site.get("tags")),
        )
        if each_site.get("ASN") is not None:
            temp_site["asn"] = each_site["ASN"]
        return temp_site

    # 2c. LOCATION: Method run to create parent and child location
    def cr_loc_rack(
        self,
        each_loc: dict[str, Any],
        each_site: dict[str, Any],
        each_tnt: dict[str, Any],
        parent: str | None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:

        tmp_loc = dict(
            name=each_loc["name"],
            slug=self.nb.make_slug(each_loc.get("slug", each_loc["name"])),
            site=dict(name=each_site["name"]),
            description=each_loc.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_loc.get("tags")),
        )
        if parent is not None:
            tmp_loc["parent"] = dict(name=parent)
            self.chld_loc.append(tmp_loc)
        elif parent is None:
            self.prnt_loc.append(tmp_loc)

        # 2d. RACK: Creates list of racks within the location
        if each_loc.get("rack") is not None:
            for each_rack in each_loc["rack"]:
                temp_rack = dict(
                    name=each_rack["name"],
                    site=dict(name=each_site["name"]),
                    location=dict(
                        slug=self.nb.make_slug(each_loc.get("slug", each_loc["name"])),
                    ),
                    tenant=dict(name=each_rack.get("tenant", each_tnt["name"])),
                    u_height=each_rack.get("height", 42),
                    tags=self.nb.get_or_create_tag(each_rack.get("tags")),
                )
                # Needed as Role cant be blank
                if each_rack.get("role") is not None:
                    temp_rack["role"] = dict(name=each_rack["role"])
                self.rack.append(temp_rack)
        # Only returned for unittesting
        return tmp_loc, self.rack

    # 2e. RR: Rack roles that can be used by a rack. If undefined sets the colour to white as cant be empty
    def cr_rr(self, each_rr: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_rr["name"],
            slug=self.nb.make_slug(each_rr.get("slug", each_rr["name"])),
            description=each_rr.get("descr", ""),
            color=each_rr.get("color", "ffffff"),
            tags=self.nb.get_or_create_tag(each_rr.get("tags")),
        )

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_tnt_site_rack(self) -> dict[str, Any]:
        # 2a. TNT: Create Tenant dictionary
        for each_tnt in self.tenant:
            self.tnt.append(self.cr_tnt(each_tnt))
            # 2b. SITE: Create site dictionary
            for each_site in each_tnt.get("site", []):
                self.site.append(self.cr_site(each_tnt, each_site))
                # 2c. LOC_RACK: Creates list of locations and racks at the site
                if each_site.get("location") is not None:
                    for each_loc in each_site["location"]:
                        self.cr_loc_rack(each_loc, each_site, each_tnt, None)
                        # 2d. NESTED_LOC_RACK: List of nested locations and racks within them
                        if each_loc.get("location") is not None:
                            for each_child_loc in each_loc["location"]:
                                self.cr_loc_rack(
                                    each_child_loc,
                                    each_site,
                                    each_tnt,
                                    each_loc["name"],
                                )
        # 2e. RR: Creates the Rack roles dictionary that can be used by a rack.
        for each_rr in self.rack_role:
            self.rr.append(self.cr_rr(each_rr))
        # The Data Models returned to the main method that are used to create the object
        return dict(
            tnt=self.tnt,
            site=self.site,
            prnt_loc=self.prnt_loc,
            chld_loc=self.chld_loc,
            rack=self.rack,
            rack_role=self.rr,
        )


# ----------------------------------------------------------------------------
# 3. DVC_MFTR_TYPE: Creates the DM for device objects manufacturer, platform, dvc_role and dvc_type
# ----------------------------------------------------------------------------
class Devices:
    def __init__(
        self,
        nbox: Nbox,
        device_role: list[dict[str, Any]],
        manufacturer: list[dict[str, Any]],
        dvc_type_dir: str,
    ) -> None:
        self.nb = nbox
        self.device_role = device_role
        self.manufacturer = manufacturer
        self.dvc_type_dir = dvc_type_dir
        self.dev_role: list[dict[str, Any]] = []
        self.mftr: list[dict[str, Any]] = []
        self.pltm: list[dict[str, Any]] = []
        self.dev_type: list[dict[str, Any]] = []

    # 3a. DEV_ROLE: List of device roles for all sites
    def cr_dev_role(self, each_role: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_role["name"],
            slug=self.nb.make_slug(each_role.get("slug", each_role["name"])),
            color=each_role.get("color", "ffffff"),
            description=each_role.get("descr", ""),
            vm_role=each_role.get("vm_role", True),
            tags=self.nb.get_or_create_tag(each_role.get("tags")),
        )

    # 3b. MFTR: List of manufacturers for all sites
    def cr_mftr(self, each_mftr: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_mftr["name"],
            slug=self.nb.make_slug(each_mftr.get("slug", each_mftr["name"])),
            description=each_mftr.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_mftr.get("tags")),
        )

    # 3c. PLATFORM: List of platforms for the manufacturer. Uses 'if' as platform is optional
    def cr_pltm(self, mftr: str, each_pltm: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_pltm["name"],
            slug=self.nb.make_slug(each_pltm.get("slug", each_pltm["name"])),
            manufacturer=dict(name=mftr),
            description=each_pltm.get("descr", ""),
            napalm_driver=each_pltm.get("driver", self.nb.make_slug(each_pltm["name"])),
            tags=self.nb.get_or_create_tag(each_pltm.get("tags")),
        )

    # DEV_TYPE_CONN: Creates each device type connection object
    def cr_conn(
        self,
        model: str,
        conn_name: int | str,
        conn_type: str,
        conn_descr: str | None = None,
        intf_mgmt: bool | None = None,
    ) -> dict[str, Any]:
        dev_type_obj = dict(
            device_type=dict(model=model), name=conn_name, type=conn_type
        )
        if conn_descr is not None:
            dev_type_obj.update(dict(description=conn_descr))
        if intf_mgmt is not None:
            dev_type_obj.update(dict(mgmt_only=intf_mgmt))
        return dev_type_obj

    # 3d. DVC_TYPE: List of device types for the manufacturer. Uses 'if' as device_type is optional
    def cr_dev_type(self, mftr: str, each_type: str) -> dict[str, Any]:
        # Lists need to be emptied each loop (dev_type)
        intf, con, pwr, f_port, r_port = ([] for i in range(5))
        with open(os.path.join(self.dvc_type_dir, each_type)) as file_content:
            dev_type_tmpl = yaml.load(file_content, Loader=yaml.FullLoader)

        # Create lists of interfaces, consoles, power, front_ports and rear_ports
        for each_intf in dev_type_tmpl.get("interfaces", []):
            intf.append(
                self.cr_conn(
                    dev_type_tmpl["model"],
                    each_intf["name"],
                    each_intf["type"],
                    each_intf.get("descr"),
                    each_intf.get("mgmt_only", False),
                )
            )
        for each_con in dev_type_tmpl.get("console-ports", []):
            con.append(
                self.cr_conn(dev_type_tmpl["model"], each_con["name"], each_con["type"])
            )
        for each_pwr in dev_type_tmpl.get("power-ports", []):
            pwr.append(
                self.cr_conn(dev_type_tmpl["model"], each_pwr["name"], each_pwr["type"])
            )
        for each_fport in dev_type_tmpl.get("front_port", []):
            # Creates the list of front and rear ports from a start and end port number (of front port)
            for each_port in range(
                each_fport["start_port"], each_fport["end_port"] + 1
            ):
                r_port.append(
                    self.cr_conn(dev_type_tmpl["model"], each_port, each_fport["type"])
                )
                f_port.append(
                    self.cr_conn(dev_type_tmpl["model"], each_port, each_fport["type"])
                )
        # Create list of device types which also includes the interfaces, consoles, power, front_port and rear_port lists
        return dict(
            manufacturer=dict(name=mftr),
            model=dev_type_tmpl["model"],
            slug=dev_type_tmpl["slug"],
            part_number=dev_type_tmpl.get("part_number", dev_type_tmpl["slug"]),
            u_height=dev_type_tmpl.get("u_height", 1),
            is_full_depth=dev_type_tmpl.get("is_full_depth", True),
            interface=intf,
            console=con,
            power=pwr,
            front_port=f_port,
            rear_port=r_port,
        )

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_dvc_type_role(self) -> dict[str, Any]:
        # 3a. DEV_ROLE: Create Device Role dictionary
        for each_role in self.device_role:
            self.dev_role.append(self.cr_dev_role(each_role))
        # 3b. MFTR: Create Manufacturer dictionary
        for each_mftr in self.manufacturer:
            self.mftr.append(self.cr_mftr(each_mftr))
            # 3c. PLATFORM: Create Platform dictionary
            if each_mftr.get("platform") is not None:
                for each_pltm in each_mftr["platform"]:
                    self.pltm.append(self.cr_pltm(each_mftr["name"], each_pltm))
            # 3d. DEV_TYPE: Create Device Type dictionary
            if each_mftr.get("device_type") is not None:
                for each_type in each_mftr["device_type"]:
                    self.dev_type.append(self.cr_dev_type(each_mftr["name"], each_type))

        # 3e. The Data Models returned to the main method that are used to create the objects
        return dict(
            dev_role=self.dev_role,
            mftr=self.mftr,
            pltm=self.pltm,
            dev_type=self.dev_type,
        )


# ----------------------------------------------------------------------------
# 4. IPAM_VRF_VLAN: Creates the DM for IPAM objects RIR, aggregate, VRF and VLAN
# ----------------------------------------------------------------------------
class Ipam:
    def __init__(
        self, nbox: Nbox, rir: list[dict[str, Any]], role: list[dict[str, Any]]
    ) -> None:
        self.nb = nbox
        self.ipam_rir = rir
        self.pfx_vlan_role = role
        self.rir: list[dict[str, Any]] = []
        self.aggr: list[dict[str, Any]] = []
        self.role: list[dict[str, Any]] = []
        self.vlan_grp: list[dict[str, Any]] = []
        self.vlan: list[dict[str, Any]] = []
        self.vrf: list[dict[str, Any]] = []
        self.pfx: list[dict[str, Any]] = []

    # 4a. RIR: If slug is empty replaces it with tenant name (lowercase) replacing whitespace with '_'
    def cr_rir(self, each_rir: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_rir["name"],
            slug=self.nb.make_slug(each_rir.get("slug", each_rir["name"])),
            description=each_rir.get("descr", ""),
            is_private=each_rir.get("is_private", False),
            tags=self.nb.get_or_create_tag(each_rir.get("tags")),
        )

    # 4b. AGGREGATE: Create aggregates that are associated to the RIR
    def cr_aggr(
        self, each_rir: dict[str, Any], each_aggr: dict[str, Any]
    ) -> dict[str, Any]:
        return dict(
            rir=dict(name=each_rir["name"]),
            prefix=each_aggr["prefix"],
            description=each_aggr.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_aggr.get("tags")),
        )

    # 4c. ROLE: Provides segregation of networks (i.e prod, npe, etc), applies to all VLANs and prefixes beneath it
    def cr_role(self, each_role: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_role["name"],
            slug=self.nb.make_slug(each_role.get("slug", each_role["name"])),
            description=each_role.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_role.get("tags")),
        )

    # 4d. VL_GRP: Creates per site VLAN group that holds VLANs that are unique to that group
    def cr_vl_grp(self, site: str, each_vlgrp: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_vlgrp["name"],
            slug=self.nb.make_slug(each_vlgrp.get("slug", each_vlgrp["name"])),
            site=dict(name=site),
            description=each_vlgrp.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_vlgrp.get("tags")),
        )

    # 4e. VLAN: Creates VLANs and associate to the vl_grp, tenant, site and role. The VL_GRP and role keep them unique
    def cr_vlan(
        self,
        role: str,
        site: str | None,
        vl_grp_tnt: str | None,
        each_vlgrp: str | None,
        each_vl: dict[str, Any],
    ) -> dict[str, Any]:
        tmp_vlan = dict(
            vid=each_vl["id"],
            name=each_vl["name"],
            role=dict(name=role),
            tenant=self.nb.name_none(
                vl_grp_tnt, dict(name=each_vl.get("tenant", vl_grp_tnt))
            ),
            description=each_vl.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_vl.get("tags")),
        )
        if each_vlgrp is not None:
            tmp_vlan["group"] = dict(name=each_vlgrp)
        elif site is not None:
            tmp_vlan["site"] = dict(name=site)
        return tmp_vlan

    # 4f. VRF: If defined in the VLAN Group creates VRF
    def cr_vrf(self, vrf_tnt: str, each_vrf: dict[str, Any]) -> dict[str, Any]:
        tmp_vrf = dict(
            name=each_vrf["name"],
            description=each_vrf.get("descr", ""),
            enforce_unique=each_vrf.get("unique", True),
            tenant=self.nb.name_none(vrf_tnt, dict(name=vrf_tnt)),
            tags=self.nb.get_or_create_tag(each_vrf.get("tags")),
            import_targets=self.nb.get_or_create_rt(
                each_vrf.get("import_rt"),
                vrf_tnt,
            ),
            export_targets=self.nb.get_or_create_rt(
                each_vrf.get("export_rt"),
                vrf_tnt,
            ),
        )
        if each_vrf.get("rd") is not None:
            tmp_vrf["rd"] = each_vrf["rd"]
        return tmp_vrf

    # 4g. PREFIX: Associated to a VRF, role and possibly a VLANs (SVIs) within the VLAN group. VRF and role are what make the prefix unique
    def cr_pfx(
        self,
        role: str,
        site: str | None,
        vrf_tnt: str,
        vlgrp: str | None,
        vrf: str,
        vrf_rd: str,
        each_pfx: dict[str, Any],
    ) -> dict[str, Any]:
        tmp_pfx = dict(
            prefix=each_pfx["pfx"],
            role=dict(name=role),
            is_pool=each_pfx.get("pool", False),
            vrf=dict(name=vrf),
            vrf_rd=vrf_rd,
            description=each_pfx.get("descr", ""),
            status=each_pfx.get("status", "active"),
            tenant=self.nb.name_none(
                vrf_tnt, dict(name=each_pfx.get("tenant", vrf_tnt))
            ),
            tags=self.nb.get_or_create_tag(each_pfx.get("tags")),
        )
        if site is None:
            tmp_pfx["site"] = site
        elif site is not None:
            tmp_pfx["site"] = dict(name=site)
        if vlgrp is not None:
            tmp_pfx["vl_grp"] = vlgrp
        if each_pfx.get("vl") is not None:
            tmp_pfx["vlan"] = each_pfx["vl"]
        return tmp_pfx

    # FIX_DUP: If VRFs or VL_GRP referenced in multiple diff places in input file, stops it trying to create multiple times (picks first occurrence).
    def fix_duplicate_obj(
        self, input_obj: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        all_objs = []
        tmp_obj_dict1, tmp_obj_dict2 = (defaultdict(list) for i in range(2))
        # Group all Objects with the same name {name: [{obj_dict}]}
        for each_obj in input_obj:
            tmp_obj_dict1[each_obj["name"]].append(each_obj)
        # From the Objects with same name if RD group {name: [{obj_dict}]} else add {name: [{obj_dict}]} again
        for obj_dm in tmp_obj_dict1.values():
            for each_obj_dm in obj_dm:
                if each_obj_dm.get("rd") is not None:
                    tmp_obj_dict2[each_obj_dm["rd"]].append(each_obj_dm)
                else:
                    tmp_obj_dict2[each_obj_dm["name"]].append(each_obj_dm)
        # Get first OBJ element as that should be the one with the full details (description, Tags, RTs, etc)
        for each_grp in tmp_obj_dict2.values():
            all_objs.append(each_grp[0])
        return all_objs

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_ipam(self) -> dict[str, Any]:
        # 4a. RIR: Create RIR dictionary
        for each_rir in self.ipam_rir:
            self.rir.append(self.cr_rir(each_rir))
            # 4b. AGGR: Create Aggregate dictionary
            if each_rir.get("aggregate") is not None:
                for each_aggr in each_rir["aggregate"]:
                    self.aggr.append(self.cr_aggr(each_rir, each_aggr))
        # 4c. ROLE: Create Role dictionary
        for each_role in self.pfx_vlan_role:
            self.role.append(self.cr_role(each_role))
            # Loops through sites to create vlans and prefixes
            for each_site in each_role["site"]:
                tnt = self.nb.get_tnt(each_site["name"])
                # 4d. VL_GRP: Creates per-site VLAN Group Dictionary
                if each_site.get("vlan_grp") is not None:
                    for each_vlgrp in each_site["vlan_grp"]:
                        vl_grp_tnt = each_vlgrp.get("tenant", tnt)
                        self.vlan_grp.append(
                            self.cr_vl_grp(each_site["name"], each_vlgrp)
                        )
                        # 4e. VLAN: Creates per-vlan-group VLAN Dictionary
                        for each_vl in each_vlgrp["vlan"]:
                            self.vlan.append(
                                self.cr_vlan(
                                    each_role["name"],
                                    None,
                                    vl_grp_tnt,
                                    each_vlgrp["name"],
                                    each_vl,
                                )
                            )
                        # 4f. VRF: Creates per-vlan-group VRF Dictionary
                        if each_vlgrp.get("vrf") is not None:
                            for each_vrf in each_vlgrp["vrf"]:
                                vrf_tnt = each_vrf.get("tenant", tnt)
                                self.vrf.append(self.cr_vrf(vrf_tnt, each_vrf))
                                # 4g. PREFIX: Creates per-vrf Prefix Dictionary
                                for each_pfx in each_vrf["prefix"]:
                                    self.pfx.append(
                                        self.cr_pfx(
                                            each_role["name"],
                                            each_site["name"],
                                            vrf_tnt,
                                            each_vlgrp["name"],
                                            each_vrf["name"],
                                            each_vrf.get("rd", "null"),
                                            each_pfx,
                                        )
                                    )
                # 4h. VL_SITE: Creates per-site VLAN Dictionary
                if each_site.get("vlan") is not None:
                    # VLAN: Creates per-vlan-group VLAN Dictionary
                    for each_vl in each_site["vlan"]:
                        self.vlan.append(
                            self.cr_vlan(
                                each_role["name"],
                                each_site["name"],
                                tnt,
                                None,
                                each_vl,
                            )
                        )
                # 4i. VRF_WITH_NO_VLANs: If Prefixes do not have VLANs no VL_GRP, the VRF is the main dictionary with PFX dictionaries underneath it
                if each_site.get("vrf") is not None:
                    # VRF: Creates VRF withs its optional settings
                    for each_vrf in each_site["vrf"]:
                        vrf_tnt = each_vrf.get("tenant", tnt)
                        self.vrf.append(self.cr_vrf(vrf_tnt, each_vrf))
                        # 4i. PREFIX: Creates per-vrf Prefix Dictionary, exist if a prefix has no entries ()
                        if each_vrf["prefix"] is None:
                            print(
                                f"⚠️  Prefix: VRF '{each_vrf['name']}' has an empty prefix dictionary, it must be a list of prefix dictionaries or an empty list"
                            )
                            exit()
                        else:
                            for each_pfx in each_vrf["prefix"]:
                                self.pfx.append(
                                    self.cr_pfx(
                                        each_role["name"],
                                        each_site["name"],
                                        vrf_tnt,
                                        None,
                                        each_vrf["name"],
                                        each_vrf.get("rd", "null"),
                                        each_pfx,
                                    )
                                )

        # 4j. The Data Models returned to the main method that are used to create the objects
        return dict(
            rir=self.rir,
            aggr=self.aggr,
            role=self.role,
            vlan_grp=self.fix_duplicate_obj(self.vlan_grp),
            vlan=self.vlan,
            vrf=self.fix_duplicate_obj(self.vrf),
            prefix=self.pfx,
        )


# ----------------------------------------------------------------------------
# 5. CRT_PVDR: Creates the DM for Circuit, Provider and Circuit Type
# ----------------------------------------------------------------------------
class Circuits:
    def __init__(
        self,
        nbox: Nbox,
        circuit_type: list[dict[str, Any]],
        provider: list[dict[str, Any]],
    ) -> None:
        self.nb = nbox
        self.circuit_type = circuit_type
        self.provider = provider
        self.crt_type: list[dict[str, Any]] = []
        self.pvdr: list[dict[str, Any]] = []
        self.crt: list[dict[str, Any]] = []

    # 5a. CIRCUIT_TYPE: A classification of circuits
    def cr_crt_type(self, each_type: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_type["name"],
            slug=self.nb.make_slug(each_type.get("slug", each_type["name"])),
            description=each_type.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_type.get("tags")),
        )

    # 5b. PROVIDER: Containers that hold cicuits by the same provider of connectivity (ISP)
    def cr_pvdr(self, each_pvdr: dict[str, Any]) -> dict[str, Any]:
        tmp_pvdr = dict(
            name=each_pvdr["name"],
            slug=self.nb.make_slug(each_pvdr.get("slug", each_pvdr["name"])),
            account=each_pvdr.get("account_num", ""),
            portal_url=each_pvdr.get("portal_url", ""),
            comments=each_pvdr.get("comments", ""),
            tags=self.nb.get_or_create_tag(each_pvdr.get("tags")),
        )
        # Optional setting ASN
        if each_pvdr.get("asn") is not None:
            tmp_pvdr["asn"] = each_pvdr["asn"]
        return tmp_pvdr

    # 5c. CIRCUIT: Each circuit belongs to a provider and must be assigned a circuit ID which is unique to that provider
    def cr_crt(
        self, each_pvdr: dict[str, Any], each_crt: dict[str, Any]
    ) -> dict[str, Any]:
        tmp_crt = dict(
            cid=str(each_crt["cid"]),
            type=dict(name=each_crt["type"]),
            provider=dict(name=each_pvdr["name"]),
            description=each_crt.get("descr", ""),
            comments=each_crt.get("comments", ""),
            tags=self.nb.get_or_create_tag(each_crt.get("tags")),
        )
        # Optional settings Tenant and commit_rate need to be only added if set as empty vlaues breal API calls
        if each_crt.get("tenant") is not None:
            tmp_crt["tenant"] = dict(name=each_crt["tenant"])
        if each_crt.get("commit_rate") is not None:
            tmp_crt["commit_rate"] = each_crt["commit_rate"]
        return tmp_crt

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_crt_pvdr(self) -> dict[str, Any]:
        # 5a. CRT_TYPE: Create Circuit Type dictionary
        for each_type in self.circuit_type:
            self.crt_type.append(self.cr_crt_type(each_type))
        # 5b. PVDR: Create Provider dictionary
        for each_pvdr in self.provider:
            self.pvdr.append(self.cr_pvdr(each_pvdr))
            # 4c. CRT: Create Circuit dictionary
            for each_crt in each_pvdr["circuit"]:
                self.crt.append(self.cr_crt(each_pvdr, each_crt))
        # 5c. The Data Models returned to the main method that are used to create the objects
        return dict(crt_type=self.crt_type, pvdr=self.pvdr, crt=self.crt)


# ----------------------------------------------------------------------------
# 6. VIRTUAL: Creates the DM for Cluster, cluster type and cluster group
# ----------------------------------------------------------------------------
class Virtualisation:
    def __init__(
        self,
        nbox: Nbox,
        cluster_group: list[dict[str, Any]],
        cluster_type: list[dict[str, Any]],
    ) -> None:
        self.nb = nbox
        self.cluster_group = cluster_group
        self.cluster_type = cluster_type
        self.cltr_type: list[dict[str, Any]] = []
        self.cltr: list[dict[str, Any]] = []
        self.cltr_grp: list[dict[str, Any]] = []

    # 6a. CLUSTER_GROUP: Optional, can be used to group clusters such as by region. Only required if used in clusters
    def cr_cltr_grp(self, each_grp: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_grp["name"],
            slug=self.nb.make_slug(each_grp.get("slug", each_grp["name"])),
            description=each_grp.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_grp.get("tags")),
        )

    # 6b. CLUSTER_TYPE: Represents a technology or mechanism by which to group clusters
    def cr_cltr_type(self, each_type: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_type["name"],
            slug=self.nb.make_slug(each_type.get("slug", each_type["name"])),
            description=each_type.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_type.get("tags")),
        )

    # 6c. CLUSTERS: Holds VMs and physical resources which hosts VMs
    def cr_cltr(
        self, each_type: dict[str, Any], each_cltr: dict[str, Any]
    ) -> dict[str, Any]:
        tmp_cltr = dict(
            name=each_cltr["name"],
            type=dict(name=each_type["name"]),
            comments=each_cltr.get("comment", ""),
        )
        # Optional settings (tenant, site or group), these can be set in cluster or inherited from cluster group
        type_site = each_type.get("site")
        if each_cltr.get("site", type_site) is not None:
            tmp_cltr["site"] = dict(name=each_cltr.get("site", type_site))
        type_grp = each_type.get("group")
        if each_cltr.get("group", type_grp) is not None:
            tmp_cltr["group"] = dict(name=each_cltr.get("group", type_grp))
        type_tags = each_type.get("tags")
        if each_cltr.get("tags", type_tags) is not None:
            tmp_cltr["tags"] = self.nb.get_or_create_tag(
                each_cltr.get("tags", type_tags)
            )
        # If tenant is undefined in cltr and cltr_grp gets the tenant name from the site (leaves blank if API call fails)
        if each_type.get("tenant") is not None:
            type_tnt = each_type.get("tenant")
        elif each_type.get("tenant") is None:
            try:
                site = each_cltr.get("site", type_site)
                type_tnt = dict(self.nb.nb.dcim.sites.get(name=site))["tenant"]["name"]
            except (TypeError, RequestError):
                type_tnt = None
        if each_cltr.get("tenant", type_tnt) is not None:
            tmp_cltr["tenant"] = dict(name=each_cltr.get("tenant", type_tnt))
        return tmp_cltr

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_vrtl(self) -> dict[str, Any]:
        # 6a. CLTR_GRP: Create Cluster Group dictionary
        if self.cluster_group is not None:
            for each_grp in self.cluster_group:
                self.cltr_grp.append(self.cr_cltr_grp(each_grp))
        # 6b. CLTR_TYPE: Create Cluster Type dictionary
        for each_type in self.cluster_type:
            self.cltr_type.append(self.cr_cltr_grp(each_type))
            # 5c. CLTR_TYPE: Create Cluster Type dictionary
            if each_type.get("cluster") is not None:
                for each_cltr in each_type["cluster"]:
                    self.cltr.append(self.cr_cltr(each_type, each_cltr))
        # 6c. The Data Models returned to the main method that are used to create the objects
        return dict(cltr_type=self.cltr_type, cltr=self.cltr, cltr_grp=self.cltr_grp)


# ----------------------------------------------------------------------------
# 7. CONTACTS: Creates the DM for organisation objects contacts, groups, roles and assignment
# ----------------------------------------------------------------------------
class Contacts:
    def __init__(
        self,
        nbox: Nbox,
        contact_role: list[dict[str, Any]],
        contact_grp: list[dict[str, Any]],
        contact_assign: list[dict[str, Any]],
    ) -> None:
        self.nb = nbox
        self.contact_role = contact_role
        self.contact_grp = contact_grp
        self.contact_assign = contact_assign
        self.cnt_role: list[dict[str, Any]] = []
        self.cnt_grp: list[dict[str, Any]] = []
        self.cnt: list[dict[str, Any]] = []
        self.cnt_asgn: list[dict[str, Any]] = []

    # 7a. CNT_ROLE: List of contact roles
    def cr_cnt_role(self, each_role: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_role["name"],
            slug=self.nb.make_slug(each_role.get("slug", each_role["name"])),
            description=each_role.get("descr", ""),
            tags=self.nb.get_or_create_tag(each_role.get("tags")),
        )

    # 7b. CNT_GRP: List of contact groups
    def cr_cnt_grp(self, each_grp: dict[str, Any]) -> dict[str, Any]:
        return dict(
            name=each_grp["name"],
            slug=self.nb.make_slug(each_grp.get("slug", each_grp["name"])),
            description=each_grp.get("descr", ""),
            parent=None,
            tags=self.nb.get_or_create_tag(each_grp.get("tags")),
        )

    # 7c. CNT: List of contacts
    def cr_cnt(self, grp: str, each_cnt: dict[str, Any]) -> dict[str, Any]:
        tmp_cnt = dict(
            name=each_cnt["name"],
            group=dict(name=grp),
            tags=self.nb.get_or_create_tag(each_cnt.get("tags")),
        )
        # Optional settings tjhat would break call if set to null
        if each_cnt.get("phone") is not None:
            tmp_cnt["phone"] = each_cnt["phone"]
        if each_cnt.get("addr") is not None:
            tmp_cnt["address"] = each_cnt["addr"]
        if each_cnt.get("email") is not None:
            tmp_cnt["email"] = each_cnt["email"]
        if each_cnt.get("comments") is not None:
            tmp_cnt["comments"] = each_cnt["comments"]
        return tmp_cnt

    # 7d. ASGN: List of contact assignments
    def cr_cnt_asgn(self, each_asgn: dict[str, Any]) -> list[dict[str, Any]]:
        tmp_asgn = []
        for obj_type, obj in each_asgn["assign_to"].items():
            if "circuit" in obj_type or "provider" in obj_type:
                api = "circuits." + obj_type
            elif "tenant" in obj_type:
                api = "tenancy." + obj_type
            elif "cluster" in obj_type:
                api = "virtualization." + obj_type
            else:
                api = "dcim." + obj_type
            tmp_asgn.append(
                dict(
                    object_type=api,
                    object_id=obj,
                    contact=each_asgn["contact"],
                    role={"name": each_asgn["role"]},
                    priority=each_asgn.get("priority", "primary"),
                )
            )
        return tmp_asgn

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_contact(self) -> dict[str, Any]:
        # 7a. ROLE: Creates the Rack roles dictionary that can be used by a rack.
        for each_role in self.contact_role:
            self.cnt_role.append(self.cr_cnt_role(each_role))
        # 7b. GRP: Create contact group
        for each_grp in self.contact_grp:
            self.cnt_grp.append(self.cr_cnt_grp(each_grp))
            # 7c. CNT: Creates contact
            if each_grp.get("contact") is not None:
                for each_cnt in each_grp["contact"]:
                    self.cnt.append(self.cr_cnt(each_grp["name"], each_cnt))
        # 7d ASGN: Assigns contact and role to an object
        for each_asgn in self.contact_assign:
            self.cnt_asgn.extend(self.cr_cnt_asgn(each_asgn))
        # The Data Models returned to the main method that are used to create the object
        return dict(
            cnt_role=self.cnt_role,
            cnt_grp=self.cnt_grp,
            cnt=self.cnt,
            cnt_asgn=self.cnt_asgn,
        )
