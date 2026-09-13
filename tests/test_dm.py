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
@pytest.fixture(scope="session", autouse=True)
def load_vars():
    global my_vars, nbox
    with open(test_input, "r") as file_content:
        my_vars = yaml.load(file_content, Loader=yaml.FullLoader)

    tag_exists, tag_created, rt_exists, rt_created = ([] for i in range(4))
    nbox = Nbox(NBOX_URL, NBOX_TOKEN, SSL, tag_exists, tag_created, rt_exists, rt_created)


# Load the vars for Organisation class
@pytest.fixture(scope="class")
def organisation_vars():
    global org, tnt1, tnt2, site1, site2, loc, rack, rr
    org = Organisation(nbox, my_vars["tenant"], my_vars["rack_role"])
    tnt1 = my_vars["tenant"][0]
    tnt2 = my_vars["tenant"][1]
    site1 = my_vars["tenant"][0]["site"][0]
    site2 = my_vars["tenant"][1]["site"][0]
    loc = my_vars["tenant"][0]["site"][0]["location"][0]
    rack = my_vars["tenant"][0]["site"][0]["location"][0]["rack"][0]
    rr = my_vars["rack_role"][0]


# Load the vars for Devices class
@pytest.fixture(scope="class")
def devices_vars():
    global dvc, dev_role, mftr_sw, mftr_pp, pltm, dev_type_swi, dev_type_pp
    dvc = Devices(nbox, my_vars["device_role"], my_vars["manufacturer"], dvc_type_dir)
    dev_role = my_vars["device_role"][0]
    mftr_sw = my_vars["manufacturer"][0]
    mftr_pp = my_vars["manufacturer"][1]
    pltm = my_vars["manufacturer"][0]["platform"][0]
    dev_type_swi = my_vars["manufacturer"][0]["device_type"][0]
    dev_type_pp = my_vars["manufacturer"][1]["device_type"][0]


# Load the vars for IPAM class
@pytest.fixture(scope="class")
def ipam_vars():
    global ipam, rir, aggr, role, vlan_grp, vlan, vrf, pfx
    ipam = Ipam(nbox, my_vars["rir"], my_vars["role"])
    rir = my_vars["rir"][0]
    aggr = my_vars["rir"][0]["aggregate"][0]
    role = my_vars["role"][0]
    vlan_grp = my_vars["role"][0]["site"][0]["vlan_grp"][0]
    vlan = my_vars["role"][0]["site"][0]["vlan_grp"][0]["vlan"][0]
    vrf = my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]
    pfx = my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]["prefix"][0]


# Load the vars for Circuits class
@pytest.fixture(scope="class")
def circuits_vars():
    global crt, crt_type, pvdr, cirt
    crt = Circuits(nbox, my_vars["circuit_type"], my_vars["provider"])
    crt_type = my_vars["circuit_type"][0]
    pvdr = my_vars["provider"][0]
    cirt = my_vars["provider"][0]["circuit"][0]


# Load the vars for Virtualisation class
@pytest.fixture(scope="class")
def virtualisation_vars():
    global vrtl, cltr_grp, cltr_type, cltr1, cltr2
    vrtl = Virtualisation(nbox, my_vars["cluster_group"], my_vars["cluster_type"])
    cltr_grp = my_vars["cluster_group"][0]
    cltr_type = my_vars["cluster_type"][0]
    cltr1 = my_vars["cluster_type"][0]["cluster"][0]
    cltr2 = my_vars["cluster_type"][0]["cluster"][1]


# Load the vars for Contact class
@pytest.fixture(scope="class")
def contact_vars():
    global cnt, cnt_role, cnt_grp, contact, cnt_asgn
    cnt = Contacts(
        nbox,
        my_vars["contact_role"],
        my_vars["contact_group"],
        my_vars["contact_assign"],
    )
    cnt_role = my_vars["contact_role"][0]
    cnt_grp = my_vars["contact_group"][0]
    contact = my_vars["contact_group"][0]["contact"][0]
    cnt_asgn = my_vars["contact_assign"][0]


# Used to make slug for various netbox objects netbox objects
def make_slug(obj) -> str:
    if isinstance(obj, int):
        obj = str(obj)
    return obj.replace(" ", "_").lower()


# ----------------------------------------------------------------------------
# 1. ORG: Testing of organisartion data-models
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("organisation_vars")
class TestOrganisation:

    # 1a. TNT: Test method for creating dict to add a tenant
    def test_cr_tnt(self):
        err_msg = "❌ cr_tnt: Creation of tenant dictionary failed"
        global desired_tnt1
        desired_tnt1 = {
            "description": tnt1["descr"],
            "name": tnt1["name"],
            "slug": tnt1["slug"],
            "tags": [],
        }
        actual_result = org.cr_tnt(tnt1)
        assert actual_result == desired_tnt1, err_msg

    # 1b. SITE: Test method for creating dict to add a site
    def test_cr_site(self):
        err_msg = "❌ cr_site: Creation of site dictionary failed"
        global desired_site1
        desired_site1 = {
            "asn": site1["ASN"],
            "description": site1["descr"],
            "name": site1["name"],
            "physical_address": site1["addr"],
            "slug": make_slug(site1["name"]),
            "tags": [],
            "tenant": {"name": tnt1["name"]},
            "time_zone": site1["time_zone"],
        }
        actual_result = org.cr_site(tnt1, site1)
        assert actual_result == desired_site1, err_msg

    # 1c. LOC_RACK: Test method for creating dict to add a location and rack
    def test_cr_loc_rack(self):
        err_msg = "❌ cr_loc_rack: Creation of {} dictionary failed"
        global desired_prnt_loc, desired_rack, desired_chld_loc

        desired_prnt_loc = {
            "description": loc["descr"],
            "name": loc["name"],
            "site": {"name": site1["name"]},
            "slug": make_slug(loc["name"]),
            "tags": [],
        }
        desired_rack = [
            {
                "location": {"slug": "utest_location"},
                "name": rack["name"],
                "role": {"name": rr["name"]},
                "site": {"name": site1["name"]},
                "tags": [],
                "tenant": {"name": tnt2["name"]},
                "u_height": rack["height"],
            }
        ]
        actual_result = org.cr_loc_rack(loc, site1, tnt1, None)
        assert actual_result[0] == desired_prnt_loc, err_msg.format("parent location")
        assert actual_result[1] == desired_rack, err_msg.format("rack")
        desired_chld_loc = {
            "description": loc["location"][0]["descr"],
            "name": loc["location"][0]["name"],
            "site": {"name": site1["name"]},
            "slug": make_slug(loc["location"][0]["name"]),
            "parent": {"name": loc["name"]},
            "tags": [],
        }
        actual_result = org.cr_loc_rack(loc["location"][0], site1, tnt1, loc["name"])
        assert actual_result[0] == desired_chld_loc, err_msg.format("child location")

    # 1d. RACK-ROLE: Test method for creating dict to add a rack-role
    def test_cr_rr(self):
        err_msg = "❌ cr_rr: Creation of location and rack-role dictionary failed"
        global desired_rr
        desired_rr = {
            "color": rr["color"],
            "description": rr["descr"],
            "name": rr["name"],
            "slug": make_slug(rr["name"]),
            "tags": [],
        }
        actual_result = org.cr_rr(rr)
        assert actual_result == desired_rr, err_msg

    # 1e. ORG: Test method for creating dict to add all organisation objects
    def test_create_tnt_site_rack(self):
        err_msg = (
            "❌ create_tnt_site_rack: Creation of organisation objects dictionary failed"
        )
        # Need to initialise a fresh or keeps location/rack from test_cr_loc_rack
        org = Organisation(nbox, my_vars["tenant"], my_vars["rack_role"])

        desired_site = [desired_site1]
        desired_site2 = {
            "description": "",
            "name": site2["name"],
            "physical_address": "",
            "slug": make_slug(site2["name"]),
            "tags": [],
            "tenant": {"name": tnt2["name"]},
            "time_zone": "UTC",
        }
        desired_site.append(desired_site2)

        desired_tnt = [desired_tnt1]
        desired_tnt2 = {
            "description": "",
            "name": tnt2["name"],
            "slug": make_slug(tnt2["name"]),
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
@pytest.mark.usefixtures("devices_vars")
class TestDevices:

    # 2a. DVC_ROLE: Test method for creating dict to add a device role
    def test_cr_dev_role(self):
        err_msg = "❌ cr_dev_role: Creation of Device Role dictionary failed"
        global desired_dev_role
        desired_dev_role = {
            "color": dev_role["color"],
            "description": dev_role["descr"],
            "name": dev_role["name"],
            "slug": dev_role["slug"],
            "vm_role": dev_role["vm_role"],
            "tags": [],
        }
        actual_result = dvc.cr_dev_role(dev_role)
        assert actual_result == desired_dev_role, err_msg

    # 2b. MFTR: Test method for creating dict to add a manufacturer
    def test_cr_mftr(self):
        err_msg = "❌ cr_mftr: Creation of Manufacturer dictionary failed"
        global desired_mftr_sw
        desired_mftr_sw = {
            "description": mftr_sw["descr"],
            "name": mftr_sw["name"],
            "slug": mftr_sw["slug"],
            "tags": [],
        }
        actual_result = dvc.cr_mftr(mftr_sw)
        assert actual_result == desired_mftr_sw, err_msg

    # 2c. PLTM: Test method for creating dict to add a platform
    def test_cr_pltm(self):
        err_msg = "❌ cr_pltm: Creation of Platform dictionary failed"
        global desired_pltm
        desired_pltm = {
            "description": "",
            "manufacturer": {"name": mftr_sw["name"]},
            "name": pltm["name"],
            "napalm_driver": pltm["driver"],
            "slug": pltm["slug"],
            "tags": [],
        }
        actual_result = dvc.cr_pltm(mftr_sw["name"], pltm)
        assert actual_result == desired_pltm, err_msg

    # 2d. CONN: Test method for creating dict to add a connection
    def test_cr_conn(self):
        err_msg = "❌ cr_conn: Creation of Device Type Connection dictionary failed"
        global desired_conn
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
    def test_cr_dev_type_sw(self):
        err_msg = "❌ cr_dev_type: Creation of Switch Device Type dictionary failed"
        global desired_dev_type_sw
        desired_dev_type_sw = device_types.sw
        actual_result = dvc.cr_dev_type(mftr_sw["name"], dev_type_swi)
        assert actual_result == desired_dev_type_sw, err_msg

    # 2f. DEV_TYPE_PP: Test method for creating dict to add a patch panel device_type
    def test_cr_dev_type_pp(self):
        err_msg = "❌ cr_dev_type: Creation of Patch Panel Device Type dictionary failed"
        global desired_dev_type_pp
        desired_dev_type_pp = device_types.pp
        actual_result = dvc.cr_dev_type(mftr_pp["name"], dev_type_pp)
        assert actual_result == desired_dev_type_pp, err_msg

    # 2g. DVC: Test method for creating dict to add all Device Type objects
    def test_create_dvc_type_role(self):
        err_msg = "❌ create_create_dvc_type_role: Creation of Device Types objects dictionary failed"

        desired_mftr_pp = {
            "description": "",
            "name": mftr_pp["name"],
            "slug": mftr_pp["name"],
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
@pytest.mark.usefixtures("ipam_vars")
class TestIpam:

    # 3a. RIR: Test method for creating dict to add a RIR
    def test_cr_rir(self):
        err_msg = "❌ cr_rir: Creation of RIR dictionary failed"
        global desired_rir
        desired_rir = {
            "description": rir["descr"],
            "is_private": rir["is_private"],
            "name": rir["name"],
            "slug": make_slug(rir["name"]),
            "tags": [],
        }
        actual_result = ipam.cr_rir(rir)
        assert actual_result == desired_rir, err_msg

    # 3b. AGGR: Test method for creating dict to add a RIR aggregate
    def test_cr_aggr(self):
        err_msg = "❌ cr_aggr: Creation of RIR Aggregate dictionary failed"
        global desired_aggr
        desired_aggr = {
            "description": aggr["descr"],
            "prefix": aggr["prefix"],
            "rir": {"name": rir["name"]},
            "tags": [],
        }
        actual_result = ipam.cr_aggr(rir, aggr)
        assert actual_result == desired_aggr, err_msg

    # 3c. ROLE: Test method for creating dict to add a VRF/VLAN Role
    def test_cr_role(self):
        err_msg = "❌ cr_role: Creation of VRF/VLAN Role dictionary failed"
        global desired_role
        desired_role = {
            "description": role["descr"],
            "name": role["name"],
            "slug": make_slug(role["name"]),
            "tags": [],
        }
        actual_result = ipam.cr_role(role)
        assert actual_result == desired_role, err_msg

    # 3d. VL_GRP: Test method for creating dict to add a VLAN Group
    def test_cr_vl_grp(self):
        err_msg = "❌ cr_vl_grp: Creation of VLAN Group dictionary failed"
        global desired_vl_grp
        desired_vl_grp = {
            "description": vlan_grp["descr"],
            "name": vlan_grp["name"],
            "site": {"name": role["site"][0]["name"]},
            "slug": make_slug(vlan_grp["name"]),
            "tags": [],
        }
        actual_result = ipam.cr_vl_grp(role["site"][0]["name"], vlan_grp)
        assert actual_result == desired_vl_grp, err_msg

    # 3e. VLAN: Test method for creating dict to add a VLAN
    def test_cr_vlan(self):
        err_msg = "❌ cr_vlan: Creation of VLAN Group dictionary failed"
        global desired_vlan
        desired_vlan = {
            "description": vlan["descr"],
            "group": {"name": vlan_grp["name"]},
            "name": vlan["name"],
            "role": {"name": role["name"]},
            "tags": [],
            "tenant": {"name": vlan_grp["tenant"]},
            "vid": vlan["id"],
        }
        actual_result = ipam.cr_vlan(
            role["name"], None, "UTEST_tenant1", vlan_grp["name"], vlan
        )
        assert actual_result == desired_vlan, err_msg

    # 3f. VRF: Test method for creating dict to add a VRF (no VLAN association)
    def test_cr_vrf(self):
        err_msg = "❌ cr_vrf Creation of VRF dictionary (no VLAN association) failed"
        global desired_vrf
        desired_vrf = {
            "description": vrf["descr"],
            "enforce_unique": True,
            "export_targets": [],
            "import_targets": [],
            "name": vrf["name"],
            "rd": vrf["rd"],
            "tags": [],
            "tenant": {"name": vrf["tenant"]},
        }
        actual_result = ipam.cr_vrf("UTEST_tenant1", vrf)
        assert actual_result == desired_vrf, err_msg

    # 3g. VRF_VLAN: Test method for creating dict to add a VRF within VLAN Group
    def test_cr_pfx(self):
        err_msg = "❌ cr_pfx Creation of VRF dictionary (within VLAN Group) failed"
        global desired_pfx
        desired_pfx = {
            "description": pfx["descr"],
            "is_pool": pfx["pool"],
            "status": pfx["status"],
            "prefix": pfx["pfx"],
            "role": {"name": role["name"]},
            "site": {"name": role["site"][0]["name"]},
            "tags": [],
            "tenant": {"name": pfx["tenant"]},
            "vl_grp": vlan_grp["name"],
            "vlan": pfx["vl"],
            "vrf": {"name": vrf["name"]},
            "vrf_rd": vrf["rd"],
        }
        actual_result = ipam.cr_pfx(
            role["name"],
            role["site"][0]["name"],
            "",
            vlan_grp["name"],
            vrf["name"],
            vrf["rd"],
            pfx,
        )
        assert actual_result == desired_pfx, err_msg

    # 3h. FIX_DUP: Test picking first occurrence or duplicate objects (VLAN group or VRF)
    def test_fix_duplicate_obj(self):
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
    def test_create_ipam(self):
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
@pytest.mark.usefixtures("circuits_vars")
class TestCircuits:

    # 5a. CRT_TYPE: Test method for creating dict to add a circuit type
    def test_cr_crt_type(self):
        err_msg = "❌ cr_cir_type: Creation of Circuit Type dictionary failed"
        global desired_crt_type
        desired_crt_type = {
            "description": crt_type["descr"],
            "name": crt_type["name"],
            "slug": crt_type["slug"],
            "tags": [],
        }
        actual_result = crt.cr_crt_type(crt_type)
        assert actual_result == desired_crt_type, err_msg

    # 5b. PROVIDER: Test method for creating dict to add a provider
    def test_cr_pvdr(self):
        err_msg = "❌ cr_pvdr: Creation of Provider dictionary failed"
        global desired_pvdr
        desired_pvdr = {
            "account": pvdr["account_num"],
            "asn": pvdr["asn"],
            "comments": pvdr["comments"],
            "name": pvdr["name"],
            "portal_url": pvdr["portal_url"],
            "slug": pvdr["slug"],
            "tags": [],
        }
        actual_result = crt.cr_pvdr(pvdr)
        assert actual_result == desired_pvdr, err_msg

    # 5c. CIRCUIT: Test method for creating dict to add a circuit
    def test_cr_crt(self):
        err_msg = "❌ cr_crt: Creation of Circuit Type dictionary failed"
        global desired_crt
        desired_crt = {
            "cid": str(cirt["cid"]),
            "comments": cirt["comments"],
            "commit_rate": cirt["commit_rate"],
            "description": cirt["descr"],
            "provider": {"name": pvdr["name"]},
            "tags": [],
            "tenant": {"name": cirt["tenant"]},
            "type": {"name": cirt["type"]},
        }
        actual_result = crt.cr_crt(pvdr, cirt)
        assert actual_result == desired_crt, err_msg

    # 5d. CRT: Test method for creating dict to add all circuits objects
    def test_create_crt_pvdr(self):
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
@pytest.mark.usefixtures("virtualisation_vars")
class TestVirtualisation:

    # 5a. CLTR_GRP: Test method for creating dict to add a cluster group
    def test_cr_cltr_grp(self):
        err_msg = "❌ cr_cltr_grp: Creation of cluster group dictionary failed"
        global desired_cltr_grp
        desired_cltr_grp = {
            "name": cltr_grp["name"],
            "slug": make_slug(cltr_grp["name"]),
            "description": cltr_grp["descr"],
            "tags": [],
        }
        actual_result = vrtl.cr_cltr_grp(cltr_grp)
        assert actual_result == desired_cltr_grp, err_msg

    # 5b. CLTR_TYPE: Test method for creating dict to add a cluster type
    def test_cr_cltr_type(self):
        err_msg = "❌ cr_cltr_type: Creation of cluster type dictionary failed"
        global desired_cltr_type
        desired_cltr_type = {
            "description": "",
            "name": cltr_type["name"],
            "slug": make_slug(cltr_type["name"]),
            "tags": [],
        }
        actual_result = vrtl.cr_cltr_type(cltr_type)
        assert actual_result == desired_cltr_type, err_msg

    # 5c. CLTR: Test method for creating dict to add a cluster
    def test_cr_cltr(self):
        err_msg = "❌ cr_cltr: Creation of cluster dictionary failed"
        global desired_cltr1
        desired_cltr1 = {
            "comments": cltr1["comment"],
            "group": {"name": cltr_type["group"]},
            "name": cltr1["name"],
            "site": {"name": cltr_type["site"]},
            "tenant": {"name": cltr_type["tenant"]},
            "type": {"name": cltr_type["name"]},
        }
        actual_result = vrtl.cr_cltr(cltr_type, cltr1)
        assert actual_result == desired_cltr1, err_msg

    # 5d. CLTR: Test method for creating dict to add a cluster with inherited tenant and site
    def test_cr_cltr_inherited(self):
        err_msg = (
            "❌ cr_cltr: Creation of cluster with inherited objects dictionary failed"
        )
        global desired_cltr2
        desired_cltr2 = {
            "comments": "",
            "group": {"name": cltr2["group"]},
            "name": cltr2["name"],
            "site": {"name": cltr2["site"]},
            "tenant": {"name": cltr2["tenant"]},
            "type": {"name": cltr_type["name"]},
        }
        actual_result = vrtl.cr_cltr(cltr_type, cltr2)
        assert actual_result == desired_cltr2, err_msg

    # 5e. VRTL: Test method for creating dict to add all virtualisation objects
    def test_create_vrtl(self):
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
@pytest.mark.usefixtures("contact_vars")
class TestContacts:

    # 6a. CNT_ROLE: Test method for creating dict to add a Contact Role
    def test_cr_cnt_role(self):
        err_msg = "❌ cr_cnt_role: Creation of Contact Role dictionary failed"
        global desired_cnt_role
        desired_cnt_role = {
            "description": cnt_role["descr"],
            "name": cnt_role["name"],
            "slug": cnt_role["slug"],
            "tags": [],
        }
        actual_result = cnt.cr_cnt_role(cnt_role)
        assert actual_result == desired_cnt_role, err_msg

    # 6b. CNT_GRP: Test method for creating dict to add a Contact Group
    def test_cr_cnt_grp(self):
        err_msg = "❌ cr_cnt_grp: Creation of contact group dictionary failed"
        global desired_cnt_grp
        desired_cnt_grp = {
            "description": cnt_grp["descr"],
            "name": cnt_grp["name"],
            "parent": None,
            "slug": cnt_grp["slug"],
            "tags": [],
        }
        actual_result = cnt.cr_cnt_grp(cnt_grp)
        assert actual_result == desired_cnt_grp, err_msg

    # 6c. CNT: Test method for creating dict to add a Contact
    def test_cr_cnt(self):
        err_msg = "❌ cr_cnt: Creation of contact dictionary failed"
        global desired_cnt
        desired_cnt = {
            "address": contact["addr"],
            "comments": contact["comments"],
            "email": contact["email"],
            "group": {"name": cnt_grp["name"]},
            "name": contact["name"],
            "phone": contact["phone"],
            "tags": [],
        }
        actual_result = cnt.cr_cnt(cnt_grp["name"], contact)
        assert actual_result == desired_cnt, err_msg

    # 6d. CNT_ASGN: Test method for creating dict to add a Contact Assignment
    def test_cr_cnt_asgn(self):
        err_msg = "❌ cr_cnt_asgn: Creation of contact assignment dictionary failed"
        global desired_cnt_asgn
        desired_cnt_asgn = [
            {
                "contact": cnt_asgn["contact"],
                "object_type": "tenancy." + list(cnt_asgn["assign_to"].keys())[0],
                "object_id": cnt_asgn["assign_to"]["tenant"],
                "priority": "primary",
                "role": {"name": cnt_asgn["role"]},
            },
            {
                "contact": cnt_asgn["contact"],
                "object_type": "dcim." + list(cnt_asgn["assign_to"].keys())[1],
                "object_id": cnt_asgn["assign_to"]["site"],
                "priority": "primary",
                "role": {"name": cnt_asgn["role"]},
            },
        ]
        actual_result = cnt.cr_cnt_asgn(cnt_asgn)
        assert actual_result == desired_cnt_asgn, err_msg

    # 6e. CNTL: Test method for creating dict to add all Contact objects
    def test_create_contact(self):
        err_msg = "❌ create_vrtl: Creation of contact objects dictionary failed"
        actual_result = cnt.create_contact()
        desired_result = dict(
            cnt_role=[desired_cnt_role],
            cnt_grp=[desired_cnt_grp],
            cnt=[desired_cnt],
            cnt_asgn=desired_cnt_asgn,
        )
        assert actual_result == desired_result, err_msg
