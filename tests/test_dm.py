from dataclasses import dataclass
from typing import Any, cast

import pytest
import yaml
import os
from collections import defaultdict

from netbox import Nbox
from dm import Organisation
from dm import Devices
from dm import Ipam
from dm import Circuits
from dm import Virtualisation
from dm import Contacts
import tests.test_files.device_types as device_types

# ----------------------------------------------------------------------------
# Variables to change dependant on environment
# ----------------------------------------------------------------------------
# Directory that holds inventory files
test_dir = os.path.dirname(__file__)
test_input = os.path.join(test_dir, "test_files", "test_inputs.yml")
dvc_type_dir = os.path.join(test_dir, "test_files")

# Default netbox instance, token and SSL verification, falls back to docker version on Orb
NBOX_URL = os.environ.get("NBOX_URL", "http://netbox.netbox-docker.orb.local")
NBOX_TOKEN = os.environ.get("NBOX_TOKEN")
SSL = os.environ.get("SSL", False)

# ----------------------------------------------------------------------------
# Fixture to initialise Nornir and load inventory
# ----------------------------------------------------------------------------
# Load variable file used by all the tests
@pytest.fixture(scope="session")
def my_vars() -> dict[str, Any]:
    with open(test_input, "r") as file_content:
        return cast("dict[str, Any]", yaml.load(file_content, Loader=yaml.FullLoader))


@pytest.fixture(scope="session")
def nbox() -> Nbox:
    assert NBOX_TOKEN is not None, "NBOX_TOKEN environment variable must be set"
    ssl_verify: bool = (
        SSL if isinstance(SSL, bool) else SSL.strip().lower() in ("1", "true", "yes")
    )
    tag_exists: list[str] = []
    tag_created: list[str] = []
    rt_exists: list[str] = []
    rt_created: list[str] = []
    return Nbox(NBOX_URL, NBOX_TOKEN, ssl_verify, tag_exists, tag_created, rt_exists, rt_created)


# Used to make slug for various netbox objects netbox objects
def make_slug(obj: str | int) -> str:
    if isinstance(obj, int):
        obj = str(obj)
    return obj.replace(" ", "_").lower()


# ----------------------------------------------------------------------------
# 1. ORG: Testing of organisartion data-models
# ----------------------------------------------------------------------------
@dataclass
class OrgSetup:
    tnt1: dict[str, Any]
    tnt2: dict[str, Any]
    site1: dict[str, Any]
    site2: dict[str, Any]
    loc: dict[str, Any]
    rack: dict[str, Any]
    rr: dict[str, Any]


@pytest.fixture(scope="class")
def org(nbox: Nbox, my_vars: dict[str, Any]) -> Organisation:
    return Organisation(nbox, my_vars["tenant"], my_vars["rack_role"])


@pytest.fixture(scope="class")
def org_setup(my_vars: dict[str, Any]) -> OrgSetup:
    return OrgSetup(
        tnt1=my_vars["tenant"][0],
        tnt2=my_vars["tenant"][1],
        site1=my_vars["tenant"][0]["site"][0],
        site2=my_vars["tenant"][1]["site"][0],
        loc=my_vars["tenant"][0]["site"][0]["location"][0],
        rack=my_vars["tenant"][0]["site"][0]["location"][0]["rack"][0],
        rr=my_vars["rack_role"][0],
    )


@pytest.fixture(scope="class")
def desired_tnt1(org_setup: OrgSetup) -> dict[str, Any]:
    return {
        "description": org_setup.tnt1["descr"],
        "name": org_setup.tnt1["name"],
        "slug": org_setup.tnt1["slug"],
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_site1(org_setup: OrgSetup) -> dict[str, Any]:
    return {
        "asn": org_setup.site1["ASN"],
        "description": org_setup.site1["descr"],
        "name": org_setup.site1["name"],
        "physical_address": org_setup.site1["addr"],
        "slug": make_slug(org_setup.site1["name"]),
        "tags": [],
        "tenant": {"name": org_setup.tnt1["name"]},
        "time_zone": org_setup.site1["time_zone"],
    }


@pytest.fixture(scope="class")
def desired_prnt_loc(org_setup: OrgSetup) -> dict[str, Any]:
    return {
        "description": org_setup.loc["descr"],
        "name": org_setup.loc["name"],
        "site": {"name": org_setup.site1["name"]},
        "slug": make_slug(org_setup.loc["name"]),
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_rack(org_setup: OrgSetup) -> list[dict[str, Any]]:
    return [
        {
            "location": {"slug": "utest_location"},
            "name": org_setup.rack["name"],
            "role": {"name": org_setup.rr["name"]},
            "site": {"name": org_setup.site1["name"]},
            "tags": [],
            "tenant": {"name": org_setup.tnt2["name"]},
            "u_height": org_setup.rack["height"],
        }
    ]


@pytest.fixture(scope="class")
def desired_chld_loc(org_setup: OrgSetup) -> dict[str, Any]:
    return {
        "description": org_setup.loc["location"][0]["descr"],
        "name": org_setup.loc["location"][0]["name"],
        "site": {"name": org_setup.site1["name"]},
        "slug": make_slug(org_setup.loc["location"][0]["name"]),
        "parent": {"name": org_setup.loc["name"]},
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_rr(org_setup: OrgSetup) -> dict[str, Any]:
    return {
        "color": org_setup.rr["color"],
        "description": org_setup.rr["descr"],
        "name": org_setup.rr["name"],
        "slug": make_slug(org_setup.rr["name"]),
        "tags": [],
    }


class TestOrganisation:

    # 1a. TNT: Test method for creating dict to add a tenant
    def test_cr_tnt(
        self, org: Organisation, org_setup: OrgSetup, desired_tnt1: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_tnt: Creation of tenant dictionary failed"
        actual_result = org.cr_tnt(org_setup.tnt1)
        assert actual_result == desired_tnt1, err_msg

    # 1b. SITE: Test method for creating dict to add a site
    def test_cr_site(
        self, org: Organisation, org_setup: OrgSetup, desired_site1: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_site: Creation of site dictionary failed"
        actual_result = org.cr_site(org_setup.tnt1, org_setup.site1)
        assert actual_result == desired_site1, err_msg

    # 1c. LOC_RACK: Test method for creating dict to add a location and rack
    def test_cr_loc_rack(
        self,
        org: Organisation,
        org_setup: OrgSetup,
        desired_prnt_loc: dict[str, Any],
        desired_rack: list[dict[str, Any]],
        desired_chld_loc: dict[str, Any],
    ) -> None:
        err_msg = "❌ cr_loc_rack: Creation of {} dictionary failed"

        actual_result = org.cr_loc_rack(org_setup.loc, org_setup.site1, org_setup.tnt1, None)
        assert actual_result[0] == desired_prnt_loc, err_msg.format("parent location")
        assert actual_result[1] == desired_rack, err_msg.format("rack")
        actual_result = org.cr_loc_rack(
            org_setup.loc["location"][0], org_setup.site1, org_setup.tnt1, org_setup.loc["name"]
        )
        assert actual_result[0] == desired_chld_loc, err_msg.format("child location")

    # 1d. RACK-ROLE: Test method for creating dict to add a rack-role
    def test_cr_rr(
        self, org: Organisation, org_setup: OrgSetup, desired_rr: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_rr: Creation of location and rack-role dictionary failed"
        actual_result = org.cr_rr(org_setup.rr)
        assert actual_result == desired_rr, err_msg

    # 1e. ORG: Test method for creating dict to add all organisation objects
    def test_create_tnt_site_rack(
        self,
        nbox: Nbox,
        my_vars: dict[str, Any],
        org_setup: OrgSetup,
        desired_tnt1: dict[str, Any],
        desired_site1: dict[str, Any],
        desired_prnt_loc: dict[str, Any],
        desired_chld_loc: dict[str, Any],
        desired_rack: list[dict[str, Any]],
        desired_rr: dict[str, Any],
    ) -> None:
        err_msg = (
            "❌ create_tnt_site_rack: Creation of organisation objects dictionary failed"
        )
        # Need to initialise a fresh or keeps location/rack from test_cr_loc_rack
        org = Organisation(nbox, my_vars["tenant"], my_vars["rack_role"])

        desired_site = [desired_site1]
        desired_site2 = {
            "description": "",
            "name": org_setup.site2["name"],
            "physical_address": "",
            "slug": make_slug(org_setup.site2["name"]),
            "tags": [],
            "tenant": {"name": org_setup.tnt2["name"]},
            "time_zone": "UTC",
        }
        desired_site.append(desired_site2)

        desired_tnt = [desired_tnt1]
        desired_tnt2 = {
            "description": "",
            "name": org_setup.tnt2["name"],
            "slug": make_slug(org_setup.tnt2["name"]),
            "tags": [],
        }
        desired_tnt.append(desired_tnt2)
        desired_loc = [desired_prnt_loc]
        desired_loc.append(desired_chld_loc)

        actual_result = org.create_tnt_site_rack()
        desired_result = dict(
            tnt=desired_tnt,
            site=desired_site,
            prnt_loc=[desired_prnt_loc],
            chld_loc=[desired_chld_loc],
            rack=desired_rack,
            rack_role=[desired_rr],
        )
        assert actual_result == desired_result, err_msg


# ----------------------------------------------------------------------------
# 2. DVC_TYPE: Testing of device-types data-models
# ----------------------------------------------------------------------------
@dataclass
class DevicesSetup:
    dev_role: dict[str, Any]
    mftr_sw: dict[str, Any]
    mftr_pp: dict[str, Any]
    pltm: dict[str, Any]
    dev_type_swi: str
    dev_type_pp: str


@pytest.fixture(scope="class")
def dvc(nbox: Nbox, my_vars: dict[str, Any]) -> Devices:
    return Devices(nbox, my_vars["device_role"], my_vars["manufacturer"], dvc_type_dir)


@pytest.fixture(scope="class")
def dvc_setup(my_vars: dict[str, Any]) -> DevicesSetup:
    return DevicesSetup(
        dev_role=my_vars["device_role"][0],
        mftr_sw=my_vars["manufacturer"][0],
        mftr_pp=my_vars["manufacturer"][1],
        pltm=my_vars["manufacturer"][0]["platform"][0],
        dev_type_swi=my_vars["manufacturer"][0]["device_type"][0],
        dev_type_pp=my_vars["manufacturer"][1]["device_type"][0],
    )


@pytest.fixture(scope="class")
def desired_dev_role(dvc_setup: DevicesSetup) -> dict[str, Any]:
    return {
        "color": dvc_setup.dev_role["color"],
        "description": dvc_setup.dev_role["descr"],
        "name": dvc_setup.dev_role["name"],
        "slug": dvc_setup.dev_role["slug"],
        "vm_role": dvc_setup.dev_role["vm_role"],
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_mftr_sw(dvc_setup: DevicesSetup) -> dict[str, Any]:
    return {
        "description": dvc_setup.mftr_sw["descr"],
        "name": dvc_setup.mftr_sw["name"],
        "slug": dvc_setup.mftr_sw["slug"],
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_pltm(dvc_setup: DevicesSetup) -> dict[str, Any]:
    return {
        "description": "",
        "manufacturer": {"name": dvc_setup.mftr_sw["name"]},
        "name": dvc_setup.pltm["name"],
        "napalm_driver": dvc_setup.pltm["driver"],
        "slug": dvc_setup.pltm["slug"],
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_dev_type_sw() -> dict[str, Any]:
    return device_types.sw


@pytest.fixture(scope="class")
def desired_dev_type_pp() -> dict[str, Any]:
    return device_types.pp


class TestDevices:

    # 2a. DVC_ROLE: Test method for creating dict to add a device role
    def test_cr_dev_role(
        self, dvc: Devices, dvc_setup: DevicesSetup, desired_dev_role: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_dev_role: Creation of Device Role dictionary failed"
        actual_result = dvc.cr_dev_role(dvc_setup.dev_role)
        assert actual_result == desired_dev_role, err_msg

    # 2b. MFTR: Test method for creating dict to add a manufacturer
    def test_cr_mftr(
        self, dvc: Devices, dvc_setup: DevicesSetup, desired_mftr_sw: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_mftr: Creation of Manufacturer dictionary failed"
        actual_result = dvc.cr_mftr(dvc_setup.mftr_sw)
        assert actual_result == desired_mftr_sw, err_msg

    # 2c. PLTM: Test method for creating dict to add a platform
    def test_cr_pltm(
        self, dvc: Devices, dvc_setup: DevicesSetup, desired_pltm: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_pltm: Creation of Platform dictionary failed"
        actual_result = dvc.cr_pltm(dvc_setup.mftr_sw["name"], dvc_setup.pltm)
        assert actual_result == desired_pltm, err_msg

    # 2d. CONN: Test method for creating dict to add a connection
    def test_cr_conn(self, dvc: Devices) -> None:
        err_msg = "❌ cr_conn: Creation of Device Type Connection dictionary failed"
        desired_conn = {
            "device_type": {"model": "Catalyst 3560-CX-12PC-S"},
            "name": "GigabitEthernet1/0/1",
            "type": "1000base-t",
        }
        actual_result = dvc.cr_conn(
            "Catalyst 3560-CX-12PC-S", "GigabitEthernet1/0/1", "1000base-t"
        )
        assert actual_result == desired_conn, err_msg

    # 2e. DEV_TYPE_SWI: Test method for creating dict to add a switch device_type
    def test_cr_dev_type_sw(
        self, dvc: Devices, dvc_setup: DevicesSetup, desired_dev_type_sw: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_dev_type: Creation of Switch Device Type dictionary failed"
        actual_result = dvc.cr_dev_type(dvc_setup.mftr_sw["name"], dvc_setup.dev_type_swi)
        assert actual_result == desired_dev_type_sw, err_msg

    # 2f. DEV_TYPE_PP: Test method for creating dict to add a patch panel device_type
    def test_cr_dev_type_pp(
        self, dvc: Devices, dvc_setup: DevicesSetup, desired_dev_type_pp: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_dev_type: Creation of Patch Panel Device Type dictionary failed"
        actual_result = dvc.cr_dev_type(dvc_setup.mftr_pp["name"], dvc_setup.dev_type_pp)
        assert actual_result == desired_dev_type_pp, err_msg

    # 2g. DVC: Test method for creating dict to add all Device Type objects
    def test_create_dvc_type_role(
        self,
        dvc: Devices,
        dvc_setup: DevicesSetup,
        desired_dev_role: dict[str, Any],
        desired_mftr_sw: dict[str, Any],
        desired_pltm: dict[str, Any],
        desired_dev_type_sw: dict[str, Any],
        desired_dev_type_pp: dict[str, Any],
    ) -> None:
        err_msg = "❌ create_create_dvc_type_role: Creation of Device Types objects dictionary failed"

        desired_mftr_pp = {
            "description": "",
            "name": dvc_setup.mftr_pp["name"],
            "slug": dvc_setup.mftr_pp["name"],
            "tags": [],
        }
        desired_mftr = [desired_mftr_sw]
        desired_mftr.append(desired_mftr_pp)

        desired_dev_type = [desired_dev_type_sw]
        desired_dev_type.append(desired_dev_type_pp)
        actual_result = dvc.create_dvc_type_role()
        desired_result = dict(
            dev_role=[desired_dev_role],
            mftr=desired_mftr,
            pltm=[desired_pltm],
            dev_type=desired_dev_type,
        )
        assert actual_result == desired_result, err_msg


# ----------------------------------------------------------------------------
# 3. IPAM: Testing of IPAM data-models
# ----------------------------------------------------------------------------
@dataclass
class IpamSetup:
    rir: dict[str, Any]
    aggr: dict[str, Any]
    role: dict[str, Any]
    vlan_grp: dict[str, Any]
    vlan: dict[str, Any]
    vrf: dict[str, Any]
    pfx: dict[str, Any]


@pytest.fixture(scope="class")
def ipam(nbox: Nbox, my_vars: dict[str, Any]) -> Ipam:
    return Ipam(nbox, my_vars["rir"], my_vars["role"])


@pytest.fixture(scope="class")
def ipam_setup(my_vars: dict[str, Any]) -> IpamSetup:
    return IpamSetup(
        rir=my_vars["rir"][0],
        aggr=my_vars["rir"][0]["aggregate"][0],
        role=my_vars["role"][0],
        vlan_grp=my_vars["role"][0]["site"][0]["vlan_grp"][0],
        vlan=my_vars["role"][0]["site"][0]["vlan_grp"][0]["vlan"][0],
        vrf=my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0],
        pfx=my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]["prefix"][0],
    )


@pytest.fixture(scope="class")
def desired_rir(ipam_setup: IpamSetup) -> dict[str, Any]:
    return {
        "description": ipam_setup.rir["descr"],
        "is_private": ipam_setup.rir["is_private"],
        "name": ipam_setup.rir["name"],
        "slug": make_slug(ipam_setup.rir["name"]),
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_aggr(ipam_setup: IpamSetup) -> dict[str, Any]:
    return {
        "description": ipam_setup.aggr["descr"],
        "prefix": ipam_setup.aggr["prefix"],
        "rir": {"name": ipam_setup.rir["name"]},
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_role(ipam_setup: IpamSetup) -> dict[str, Any]:
    return {
        "description": ipam_setup.role["descr"],
        "name": ipam_setup.role["name"],
        "slug": make_slug(ipam_setup.role["name"]),
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_vl_grp(ipam_setup: IpamSetup) -> dict[str, Any]:
    return {
        "description": ipam_setup.vlan_grp["descr"],
        "name": ipam_setup.vlan_grp["name"],
        "site": {"name": ipam_setup.role["site"][0]["name"]},
        "slug": make_slug(ipam_setup.vlan_grp["name"]),
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_vlan(ipam_setup: IpamSetup) -> dict[str, Any]:
    return {
        "description": ipam_setup.vlan["descr"],
        "group": {"name": ipam_setup.vlan_grp["name"]},
        "name": ipam_setup.vlan["name"],
        "role": {"name": ipam_setup.role["name"]},
        "tags": [],
        "tenant": {"name": ipam_setup.vlan_grp["tenant"]},
        "vid": ipam_setup.vlan["id"],
    }


@pytest.fixture(scope="class")
def desired_vrf(ipam_setup: IpamSetup) -> dict[str, Any]:
    return {
        "description": ipam_setup.vrf["descr"],
        "enforce_unique": True,
        "export_targets": [],
        "import_targets": [],
        "name": ipam_setup.vrf["name"],
        "rd": ipam_setup.vrf["rd"],
        "tags": [],
        "tenant": {"name": ipam_setup.vrf["tenant"]},
    }


@pytest.fixture(scope="class")
def desired_pfx(ipam_setup: IpamSetup) -> dict[str, Any]:
    return {
        "description": ipam_setup.pfx["descr"],
        "is_pool": ipam_setup.pfx["pool"],
        "status": ipam_setup.pfx["status"],
        "prefix": ipam_setup.pfx["pfx"],
        "role": {"name": ipam_setup.role["name"]},
        "site": {"name": ipam_setup.role["site"][0]["name"]},
        "tags": [],
        "tenant": {"name": ipam_setup.pfx["tenant"]},
        "vl_grp": ipam_setup.vlan_grp["name"],
        "vlan": ipam_setup.pfx["vl"],
        "vrf": {"name": ipam_setup.vrf["name"]},
        "vrf_rd": ipam_setup.vrf["rd"],
    }


class TestIpam:

    # 3a. RIR: Test method for creating dict to add a RIR
    def test_cr_rir(
        self, ipam: Ipam, ipam_setup: IpamSetup, desired_rir: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_rir: Creation of RIR dictionary failed"
        actual_result = ipam.cr_rir(ipam_setup.rir)
        assert actual_result == desired_rir, err_msg

    # 3b. AGGR: Test method for creating dict to add a RIR aggregate
    def test_cr_aggr(
        self, ipam: Ipam, ipam_setup: IpamSetup, desired_aggr: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_aggr: Creation of RIR Aggregate dictionary failed"
        actual_result = ipam.cr_aggr(ipam_setup.rir, ipam_setup.aggr)
        assert actual_result == desired_aggr, err_msg

    # 3c. ROLE: Test method for creating dict to add a VRF/VLAN Role
    def test_cr_role(
        self, ipam: Ipam, ipam_setup: IpamSetup, desired_role: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_role: Creation of VRF/VLAN Role dictionary failed"
        actual_result = ipam.cr_role(ipam_setup.role)
        assert actual_result == desired_role, err_msg

    # 3d. VL_GRP: Test method for creating dict to add a VLAN Group
    def test_cr_vl_grp(
        self, ipam: Ipam, ipam_setup: IpamSetup, desired_vl_grp: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_vl_grp: Creation of VLAN Group dictionary failed"
        actual_result = ipam.cr_vl_grp(
            ipam_setup.role["site"][0]["name"], ipam_setup.vlan_grp
        )
        assert actual_result == desired_vl_grp, err_msg

    # 3e. VLAN: Test method for creating dict to add a VLAN
    def test_cr_vlan(
        self, ipam: Ipam, ipam_setup: IpamSetup, desired_vlan: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_vlan: Creation of VLAN Group dictionary failed"
        actual_result = ipam.cr_vlan(
            ipam_setup.role["name"],
            None,
            "UTEST_tenant1",
            ipam_setup.vlan_grp["name"],
            ipam_setup.vlan,
        )
        assert actual_result == desired_vlan, err_msg

    # 3f. VRF: Test method for creating dict to add a VRF (no VLAN association)
    def test_cr_vrf(
        self, ipam: Ipam, ipam_setup: IpamSetup, desired_vrf: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_vrf Creation of VRF dictionary (no VLAN association) failed"
        actual_result = ipam.cr_vrf("UTEST_tenant1", ipam_setup.vrf)
        assert actual_result == desired_vrf, err_msg

    # 3g. VRF_VLAN: Test method for creating dict to add a VRF within VLAN Group
    def test_cr_pfx(
        self, ipam: Ipam, ipam_setup: IpamSetup, desired_pfx: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_pfx Creation of VRF dictionary (within VLAN Group) failed"
        actual_result = ipam.cr_pfx(
            ipam_setup.role["name"],
            ipam_setup.role["site"][0]["name"],
            "",
            ipam_setup.vlan_grp["name"],
            ipam_setup.vrf["name"],
            ipam_setup.vrf["rd"],
            ipam_setup.pfx,
        )
        assert actual_result == desired_pfx, err_msg

    # 3h. FIX_DUP: Test picking first occurrence or duplicate objects (VLAN group or VRF)
    def test_fix_duplicate_obj(self, ipam: Ipam) -> None:
        err_msg = "❌ fix_duplicate_obj"
        input_obj = [
            {"description": "Group1", "name": "VLAN Group1"},
            {"description": "Group2", "name": "VLAN Group2"},
            {"description": "VRF1", "name": "VRF1", "rd": "1:1"},
            {"description": "VRF2", "name": "VRF2", "rd": "2:2"},
            {"description": "Duplicate VL_GRP descr ignored", "name": "VLAN Group1"},
            {"description": "Duplicate VRF descr ignored", "name": "VRF1", "rd": "1:1"},
        ]

        actual_result = ipam.fix_duplicate_obj(input_obj)
        assert actual_result == input_obj[0:4], err_msg

    # 3i. IPAM: Test method for creating dict to add all IPAM objects
    def test_create_ipam(
        self,
        ipam: Ipam,
        desired_rir: dict[str, Any],
        desired_aggr: dict[str, Any],
        desired_role: dict[str, Any],
        desired_vl_grp: dict[str, Any],
        desired_vlan: dict[str, Any],
        desired_vrf: dict[str, Any],
        desired_pfx: dict[str, Any],
    ) -> None:
        err_msg = "❌ create_ipam: Creation of IPAM objects dictionary failed"
        actual_result = ipam.create_ipam()
        desired_result = dict(
            rir=[desired_rir],
            aggr=[desired_aggr],
            role=[desired_role],
            vlan_grp=[desired_vl_grp],
            vlan=[desired_vlan],
            vrf=[desired_vrf],
            prefix=[desired_pfx],
        )
        assert actual_result == desired_result, err_msg


# ----------------------------------------------------------------------------
# 5. CRT: Testing of circuits data-models
# ----------------------------------------------------------------------------
@dataclass
class CircuitsSetup:
    crt_type: dict[str, Any]
    pvdr: dict[str, Any]
    cirt: dict[str, Any]


@pytest.fixture(scope="class")
def crt(nbox: Nbox, my_vars: dict[str, Any]) -> Circuits:
    return Circuits(nbox, my_vars["circuit_type"], my_vars["provider"])


@pytest.fixture(scope="class")
def crt_setup(my_vars: dict[str, Any]) -> CircuitsSetup:
    return CircuitsSetup(
        crt_type=my_vars["circuit_type"][0],
        pvdr=my_vars["provider"][0],
        cirt=my_vars["provider"][0]["circuit"][0],
    )


@pytest.fixture(scope="class")
def desired_crt_type(crt_setup: CircuitsSetup) -> dict[str, Any]:
    return {
        "description": crt_setup.crt_type["descr"],
        "name": crt_setup.crt_type["name"],
        "slug": crt_setup.crt_type["slug"],
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_pvdr(crt_setup: CircuitsSetup) -> dict[str, Any]:
    return {
        "account": crt_setup.pvdr["account_num"],
        "asn": crt_setup.pvdr["asn"],
        "comments": crt_setup.pvdr["comments"],
        "name": crt_setup.pvdr["name"],
        "portal_url": crt_setup.pvdr["portal_url"],
        "slug": crt_setup.pvdr["slug"],
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_crt(crt_setup: CircuitsSetup) -> dict[str, Any]:
    return {
        "cid": str(crt_setup.cirt["cid"]),
        "comments": crt_setup.cirt["comments"],
        "commit_rate": crt_setup.cirt["commit_rate"],
        "description": crt_setup.cirt["descr"],
        "provider": {"name": crt_setup.pvdr["name"]},
        "tags": [],
        "tenant": {"name": crt_setup.cirt["tenant"]},
        "type": {"name": crt_setup.cirt["type"]},
    }


class TestCircuits:

    # 5a. CRT_TYPE: Test method for creating dict to add a circuit type
    def test_cr_crt_type(
        self, crt: Circuits, crt_setup: CircuitsSetup, desired_crt_type: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_cir_type: Creation of Circuit Type dictionary failed"
        actual_result = crt.cr_crt_type(crt_setup.crt_type)
        assert actual_result == desired_crt_type, err_msg

    # 5b. PROVIDER: Test method for creating dict to add a provider
    def test_cr_pvdr(
        self, crt: Circuits, crt_setup: CircuitsSetup, desired_pvdr: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_pvdr: Creation of Provider dictionary failed"
        actual_result = crt.cr_pvdr(crt_setup.pvdr)
        assert actual_result == desired_pvdr, err_msg

    # 5c. CIRCUIT: Test method for creating dict to add a circuit
    def test_cr_crt(
        self, crt: Circuits, crt_setup: CircuitsSetup, desired_crt: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_crt: Creation of Circuit Type dictionary failed"
        actual_result = crt.cr_crt(crt_setup.pvdr, crt_setup.cirt)
        assert actual_result == desired_crt, err_msg

    # 5d. CRT: Test method for creating dict to add all circuits objects
    def test_create_crt_pvdr(
        self,
        crt: Circuits,
        desired_crt_type: dict[str, Any],
        desired_pvdr: dict[str, Any],
        desired_crt: dict[str, Any],
    ) -> None:
        err_msg = "❌ create_crt_pvdr: Creation of circuit objects dictionary failed"
        actual_result = crt.create_crt_pvdr()
        desired_result = dict(
            crt_type=[desired_crt_type],
            pvdr=[desired_pvdr],
            crt=[desired_crt],
        )
        assert actual_result == desired_result, err_msg


# ----------------------------------------------------------------------------
# 5. VRTL: Testing of virtualisation data-models
# ----------------------------------------------------------------------------
@dataclass
class VirtualisationSetup:
    cltr_grp: dict[str, Any]
    cltr_type: dict[str, Any]
    cltr1: dict[str, Any]
    cltr2: dict[str, Any]


@pytest.fixture(scope="class")
def vrtl(nbox: Nbox, my_vars: dict[str, Any]) -> Virtualisation:
    return Virtualisation(nbox, my_vars["cluster_group"], my_vars["cluster_type"])


@pytest.fixture(scope="class")
def vrtl_setup(my_vars: dict[str, Any]) -> VirtualisationSetup:
    return VirtualisationSetup(
        cltr_grp=my_vars["cluster_group"][0],
        cltr_type=my_vars["cluster_type"][0],
        cltr1=my_vars["cluster_type"][0]["cluster"][0],
        cltr2=my_vars["cluster_type"][0]["cluster"][1],
    )


@pytest.fixture(scope="class")
def desired_cltr_grp(vrtl_setup: VirtualisationSetup) -> dict[str, Any]:
    return {
        "name": vrtl_setup.cltr_grp["name"],
        "slug": make_slug(vrtl_setup.cltr_grp["name"]),
        "description": vrtl_setup.cltr_grp["descr"],
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_cltr_type(vrtl_setup: VirtualisationSetup) -> dict[str, Any]:
    return {
        "description": "",
        "name": vrtl_setup.cltr_type["name"],
        "slug": make_slug(vrtl_setup.cltr_type["name"]),
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_cltr1(vrtl_setup: VirtualisationSetup) -> dict[str, Any]:
    return {
        "comments": vrtl_setup.cltr1["comment"],
        "group": {"name": vrtl_setup.cltr_type["group"]},
        "name": vrtl_setup.cltr1["name"],
        "site": {"name": vrtl_setup.cltr_type["site"]},
        "tenant": {"name": vrtl_setup.cltr_type["tenant"]},
        "type": {"name": vrtl_setup.cltr_type["name"]},
    }


@pytest.fixture(scope="class")
def desired_cltr2(vrtl_setup: VirtualisationSetup) -> dict[str, Any]:
    return {
        "comments": "",
        "group": {"name": vrtl_setup.cltr2["group"]},
        "name": vrtl_setup.cltr2["name"],
        "site": {"name": vrtl_setup.cltr2["site"]},
        "tenant": {"name": vrtl_setup.cltr2["tenant"]},
        "type": {"name": vrtl_setup.cltr_type["name"]},
    }


class TestVirtualisation:

    # 5a. CLTR_GRP: Test method for creating dict to add a cluster group
    def test_cr_cltr_grp(
        self,
        vrtl: Virtualisation,
        vrtl_setup: VirtualisationSetup,
        desired_cltr_grp: dict[str, Any],
    ) -> None:
        err_msg = "❌ cr_cltr_grp: Creation of cluster group dictionary failed"
        actual_result = vrtl.cr_cltr_grp(vrtl_setup.cltr_grp)
        assert actual_result == desired_cltr_grp, err_msg

    # 5b. CLTR_TYPE: Test method for creating dict to add a cluster type
    def test_cr_cltr_type(
        self,
        vrtl: Virtualisation,
        vrtl_setup: VirtualisationSetup,
        desired_cltr_type: dict[str, Any],
    ) -> None:
        err_msg = "❌ cr_cltr_type: Creation of cluster type dictionary failed"
        actual_result = vrtl.cr_cltr_type(vrtl_setup.cltr_type)
        assert actual_result == desired_cltr_type, err_msg

    # 5c. CLTR: Test method for creating dict to add a cluster
    def test_cr_cltr(
        self,
        vrtl: Virtualisation,
        vrtl_setup: VirtualisationSetup,
        desired_cltr1: dict[str, Any],
    ) -> None:
        err_msg = "❌ cr_cltr: Creation of cluster dictionary failed"
        actual_result = vrtl.cr_cltr(vrtl_setup.cltr_type, vrtl_setup.cltr1)
        assert actual_result == desired_cltr1, err_msg

    # 5d. CLTR: Test method for creating dict to add a cluster with inherited tenant and site
    def test_cr_cltr_inherited(
        self,
        vrtl: Virtualisation,
        vrtl_setup: VirtualisationSetup,
        desired_cltr2: dict[str, Any],
    ) -> None:
        err_msg = (
            "❌ cr_cltr: Creation of cluster with inherited objects dictionary failed"
        )
        actual_result = vrtl.cr_cltr(vrtl_setup.cltr_type, vrtl_setup.cltr2)
        assert actual_result == desired_cltr2, err_msg

    # 5e. VRTL: Test method for creating dict to add all virtualisation objects
    def test_create_vrtl(
        self,
        vrtl: Virtualisation,
        desired_cltr_type: dict[str, Any],
        desired_cltr_grp: dict[str, Any],
        desired_cltr1: dict[str, Any],
        desired_cltr2: dict[str, Any],
    ) -> None:
        err_msg = "❌ create_vrtl: Creation of virtualisation objects dictionary failed"
        actual_result = vrtl.create_vrtl()
        desired_cltr = [desired_cltr1]
        desired_cltr.append(desired_cltr2)
        desired_result = dict(
            cltr_type=[desired_cltr_type],
            cltr_grp=[desired_cltr_grp],
            cltr=desired_cltr,
        )
        assert actual_result == desired_result, err_msg


# ----------------------------------------------------------------------------
# 6. CNT: Testing of contact data-models
# ----------------------------------------------------------------------------
@dataclass
class ContactsSetup:
    cnt_role: dict[str, Any]
    cnt_grp: dict[str, Any]
    contact: dict[str, Any]
    cnt_asgn: dict[str, Any]


@pytest.fixture(scope="class")
def cnt(nbox: Nbox, my_vars: dict[str, Any]) -> Contacts:
    return Contacts(
        nbox,
        my_vars["contact_role"],
        my_vars["contact_group"],
        my_vars["contact_assign"],
    )


@pytest.fixture(scope="class")
def cnt_setup(my_vars: dict[str, Any]) -> ContactsSetup:
    return ContactsSetup(
        cnt_role=my_vars["contact_role"][0],
        cnt_grp=my_vars["contact_group"][0],
        contact=my_vars["contact_group"][0]["contact"][0],
        cnt_asgn=my_vars["contact_assign"][0],
    )


@pytest.fixture(scope="class")
def desired_cnt_role(cnt_setup: ContactsSetup) -> dict[str, Any]:
    return {
        "description": cnt_setup.cnt_role["descr"],
        "name": cnt_setup.cnt_role["name"],
        "slug": cnt_setup.cnt_role["slug"],
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_cnt_grp(cnt_setup: ContactsSetup) -> dict[str, Any]:
    return {
        "description": cnt_setup.cnt_grp["descr"],
        "name": cnt_setup.cnt_grp["name"],
        "parent": None,
        "slug": cnt_setup.cnt_grp["slug"],
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_cnt(cnt_setup: ContactsSetup) -> dict[str, Any]:
    return {
        "address": cnt_setup.contact["addr"],
        "comments": cnt_setup.contact["comments"],
        "email": cnt_setup.contact["email"],
        "group": {"name": cnt_setup.cnt_grp["name"]},
        "name": cnt_setup.contact["name"],
        "phone": cnt_setup.contact["phone"],
        "tags": [],
    }


@pytest.fixture(scope="class")
def desired_cnt_asgn(cnt_setup: ContactsSetup) -> list[dict[str, Any]]:
    return [
        {
            "contact": cnt_setup.cnt_asgn["contact"],
            "object_type": "tenancy." + list(cnt_setup.cnt_asgn["assign_to"].keys())[0],
            "object_id": cnt_setup.cnt_asgn["assign_to"]["tenant"],
            "priority": "primary",
            "role": {"name": cnt_setup.cnt_asgn["role"]},
        },
        {
            "contact": cnt_setup.cnt_asgn["contact"],
            "object_type": "dcim." + list(cnt_setup.cnt_asgn["assign_to"].keys())[1],
            "object_id": cnt_setup.cnt_asgn["assign_to"]["site"],
            "priority": "primary",
            "role": {"name": cnt_setup.cnt_asgn["role"]},
        },
    ]


class TestContacts:

    # 6a. CNT_ROLE: Test method for creating dict to add a Contact Role
    def test_cr_cnt_role(
        self, cnt: Contacts, cnt_setup: ContactsSetup, desired_cnt_role: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_cnt_role: Creation of Contact Role dictionary failed"
        actual_result = cnt.cr_cnt_role(cnt_setup.cnt_role)
        assert actual_result == desired_cnt_role, err_msg

    # 6b. CNT_GRP: Test method for creating dict to add a Contact Group
    def test_cr_cnt_grp(
        self, cnt: Contacts, cnt_setup: ContactsSetup, desired_cnt_grp: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_cnt_grp: Creation of contact group dictionary failed"
        actual_result = cnt.cr_cnt_grp(cnt_setup.cnt_grp)
        assert actual_result == desired_cnt_grp, err_msg

    # 6c. CNT: Test method for creating dict to add a Contact
    def test_cr_cnt(
        self, cnt: Contacts, cnt_setup: ContactsSetup, desired_cnt: dict[str, Any]
    ) -> None:
        err_msg = "❌ cr_cnt: Creation of contact dictionary failed"
        actual_result = cnt.cr_cnt(cnt_setup.cnt_grp["name"], cnt_setup.contact)
        assert actual_result == desired_cnt, err_msg

    # 6d. CNT_ASGN: Test method for creating dict to add a Contact Assignment
    def test_cr_cnt_asgn(
        self,
        cnt: Contacts,
        cnt_setup: ContactsSetup,
        desired_cnt_asgn: list[dict[str, Any]],
    ) -> None:
        err_msg = "❌ cr_cnt_asgn: Creation of contact assignment dictionary failed"
        actual_result = cnt.cr_cnt_asgn(cnt_setup.cnt_asgn)
        assert actual_result == desired_cnt_asgn, err_msg

    # 6e. CNTL: Test method for creating dict to add all Contact objects
    def test_create_contact(
        self,
        cnt: Contacts,
        desired_cnt_role: dict[str, Any],
        desired_cnt_grp: dict[str, Any],
        desired_cnt: dict[str, Any],
        desired_cnt_asgn: list[dict[str, Any]],
    ) -> None:
        err_msg = "❌ create_vrtl: Creation of contact objects dictionary failed"
        actual_result = cnt.create_contact()
        desired_result = dict(
            cnt_role=[desired_cnt_role],
            cnt_grp=[desired_cnt_grp],
            cnt=[desired_cnt],
            cnt_asgn=desired_cnt_asgn,
        )
        assert actual_result == desired_result, err_msg
