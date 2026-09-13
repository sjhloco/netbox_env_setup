import pytest
import yaml
import pynetbox
from pynetbox.core.query import RequestError
import operator
from collections import defaultdict
import os
from netbox import Nbox


# ----------------------------------------------------------------------------
# Variables to change dependant on environment
# ----------------------------------------------------------------------------
# Directory that holds inventory files
test_dir = os.path.dirname(__file__)
test_input = os.path.join(test_dir, "test_files", "test_inputs.yml")

# Default netbox instance, token and SSL verification, falls back to docker version on Orb
NBOX_URL = os.environ.get("NBOX_URL", "http://netbox.netbox-docker.orb.local")
NBOX_TOKEN = os.environ.get("NBOX_TOKEN")
SSL = os.environ.get("SSL", False)

# ----------------------------------------------------------------------------
# Fixture to initialise Nornir and load inventory
# ----------------------------------------------------------------------------
# Used to make slug for various netbox objects netbox objects
def make_slug(obj) -> str:
    if isinstance(obj, int):
        obj = str(obj)
    return obj.replace(" ", "_").lower()


# Load variable file used by all the tests
@pytest.fixture(scope="session", autouse=True)
def load_vars():
    global my_vars
    with open(test_input, "r") as file_content:
        my_vars = yaml.load(file_content, Loader=yaml.FullLoader)


# Test API calls to netbox
@pytest.fixture(scope="class")
def load_nbox():
    global nbox, nb, tnt2, cnt_usr, dvc_type, dvc_type1, mftr, vlan, vl_grp, vrf, vrf_rd, pfx, cnt_role, contact, site
    nbox = Nbox(NBOX_URL, NBOX_TOKEN, SSL, [], [], [], [])
    nb = pynetbox.api(url=NBOX_URL, token=NBOX_TOKEN)

    # Creates nbox test objects
    tnt2 = my_vars["tenant"][1]["name"]
    mftr = my_vars["manufacturer"][0]["name"]
    dvc_type = "UTEST dvc_type"
    dvc_type1 = "UTEST dvc_type1"
    vl_grp = my_vars["role"][0]["site"][0]["vlan_grp"][0]["name"]
    vrf = my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]["name"]
    vrf_rd = my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]["rd"]
    pfx = my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]["prefix"][0]
    vlan = my_vars["role"][0]["site"][0]["vlan_grp"][0]["vlan"][0]
    cnt_role = my_vars["contact_role"][0]
    contact = my_vars["contact_group"][0]["contact"][0]["name"]
    site = my_vars["role"][0]["site"][0]["name"]
    cr_nbox_obj(nb, "tenancy.tenants", {"name": tnt2, "slug": make_slug(tnt2)}, tnt2)
    cr_nbox_obj(nb, "dcim.manufacturers", {"name": mftr, "slug": make_slug(mftr)}, mftr)
    cr_nbox_obj(
        nb,
        "dcim.device_types",
        {
            "name": dvc_type,
            "slug": make_slug(dvc_type),
            "model": dvc_type,
            "manufacturer": dict(name=mftr),
        },
        "dvc_type",
    )
    cr_nbox_obj(
        nb, "ipam.vlan-groups", {"name": vl_grp, "slug": make_slug(vl_grp)}, vl_grp
    )
    cr_nbox_obj(nb, "ipam.vrfs", {"name": vrf, "rd": vrf_rd}, vrf)
    cr_nbox_obj(
        nb, "ipam.prefixes", {"prefix": pfx["pfx"], "vrf": {"name": vrf}}, pfx["pfx"]
    )
    cr_nbox_obj(nb, "ipam.prefixes", {"prefix": pfx["pfx"]}, pfx["pfx"])
    cr_nbox_obj(
        nb,
        "ipam.vlans",
        {"name": vlan["name"], "vid": vlan["id"], "group": dict(name=vl_grp)},
        vlan["name"],
    )
    cr_nbox_obj(
        nb,
        "tenancy.contact-roles",
        {"name": cnt_role["name"], "slug": cnt_role["slug"]},
        cnt_role["name"],
    )
    cr_nbox_obj(nb, "tenancy.contacts", {"name": contact}, contact)
    cr_nbox_obj(
        nb,
        "dcim.sites",
        {"name": site, "slug": make_slug(site), "tenant": dict(name=tnt2)},
        site,
    )

    # Delete nbox test objects that where created
    yield nbox
    del_nbox_obj(nb, "tenancy.tenants", "name", my_vars["tenant"][0]["name"])
    del_nbox_obj(nb, "extras.tags", "name", "UTEST_tag")
    del_nbox_obj(nb, "ipam.route-targets", "name", "UTEST1:RT")
    del_nbox_obj(nb, "ipam.route-targets", "name", "UTEST2:RT")
    del_nbox_obj(nb, "dcim.device_types", "slug", make_slug(dvc_type))
    del_nbox_obj(nb, "dcim.device_types", "slug", make_slug(dvc_type1))
    del_nbox_obj(nb, "dcim.manufacturers", "slug", make_slug(mftr))
    del_nbox_obj(nb, "ipam.vlans", "name", vlan["name"])
    del_nbox_obj(nb, "ipam.vlan-groups", "slug", make_slug(vl_grp))
    del_nbox_obj(nb, "ipam.prefixes", "prefix_vrf", pfx["pfx"])
    del_nbox_obj(nb, "ipam.prefixes", "prefix", pfx["pfx"])
    del_nbox_obj(nb, "ipam.vrfs", "name", vrf)
    del_nbox_obj(nb, "tenancy.contacts", "name", contact)
    del_nbox_obj(nb, "tenancy.contact-roles", "slug", cnt_role["slug"])
    del_nbox_obj(nb, "dcim.sites", "slug", make_slug(site))
    del_nbox_obj(nb, "tenancy.tenants", "slug", make_slug(tnt2))


# Create unittest netbox objects
def cr_nbox_obj(nb, api_attr, fltr, obj_name):
    try:
        operator.attrgetter(api_attr)(nb).create(**fltr)
    except Exception as e:
        print(type(e))
        print(
            f"❌ An error was raised creating netbox unit test '{api_attr}' object '{obj_name}' - {e}"
        )


# Delete unittest netbox objects
def del_nbox_obj(nb, api_attr, obj_fltr, obj_name):
    # Need to get VRF ID to get prefix to delete as are duplicates for test_obj_check_null_vrf
    if obj_fltr == "prefix_vrf":
        obj_fltr = "prefix"
        try:
            fltr = {obj_fltr: obj_name, "vrf_id": nb.ipam.vrfs.get(name=vrf).id}
        except (RequestError, ValueError) as e:
            print(
                f"❌ An error was raised deleting netbox unit test '{api_attr}' object '{obj_name}'  - {e}"
            )
            return
    else:
        fltr = {obj_fltr: obj_name}
    try:
        if operator.attrgetter(api_attr)(nb).get(**fltr) != None:
            obj = operator.attrgetter(api_attr)(nb).get(**fltr)
            obj.delete()
    except (RequestError, ValueError) as e:
        print(
            f"❌ An error was raised deleting netbox unit test '{api_attr}' object '{obj_name}'  - {e}"
        )


# ----------------------------------------------------------------------------
# 1.NBOX_API: Testing of API calls to netbox
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("load_nbox")
class TestNbox:

    # 1a. OBJ_CHK: Test object lookup
    def test_obj_check(self):
        err_msg = "❌ obj_check: Checking for existence of netbox object failed"
        desired_result = {
            "notexist_dm": [{"name": "no_tenant"}],
            "exist_name": [tnt2],
        }
        actual_result = nbox.obj_check(
            "tenancy.tenants",
            "name",
            [{"name": tnt2}, {"name": "no_tenant"}],
        )
        assert actual_result == desired_result, err_msg

    # 1b. OBJ_CHK_EXT: Test object lookup using extended filter (input dict)
    def test_obj_check_ext_fltr(self):
        err_msg = "❌ obj_check: Checking for existence of netbox object using extended filter (input) failed"
        desired_result = {"exist_name": [tnt2], "notexist_dm": []}
        chk_fltr = {"name": tnt2, "slug": tnt2.lower()}
        actual_result = nbox.obj_check(
            "tenancy.tenants",
            "multi-fltr",
            [{"chk_fltr": chk_fltr, "multi-fltr": tnt2}],
        )
        assert actual_result == desired_result, err_msg

    def test_obj_check_null_vrf(self):
        err_msg = "❌ obj_check: Checking for existence of netbox object in netbox global VRF failed"
        desired_result = {"exist_name": ["10.10.10.0/24"], "notexist_dm": []}
        actual_result = nbox.obj_check(
            "ipam.prefixes",
            "multi-fltr",
            [
                {
                    "prefix": pfx["pfx"],
                    "vrf": None,
                    "multi-fltr": pfx["pfx"],
                    "chk_fltr": {"prefix": pfx["pfx"], "vrf": None},
                }
            ],
        )
        assert actual_result == desired_result, err_msg

    # 1c. OBJ_CREATE_ERR: Test object creation failure error reporting works
    def test_obj_create_err(self, capsys):
        err_msg = "❌ obj_create: Netbox object creation error reporting failed"
        desired_result = "❌ Tenant 'slug' - This field is required.\n"
        try:
            nbox.obj_create(
                "Tenant",
                "tenancy.tenants",
                [{"name": my_vars["tenant"][0]["name"]}],
                [],
            )
        except SystemExit:
            pass
        assert capsys.readouterr().out == desired_result, err_msg

    # 1d. OBJ_CREATE: Test object creation works
    def test_obj_create(self, capsys):
        err_msg = "❌ obj_create: Netbox object creation failed"
        cr_tnt = [
            {
                "description": my_vars["tenant"][0]["descr"],
                "name": my_vars["tenant"][0]["name"],
                "slug": "utest_tnt",
                "tags": [],
            }
        ]
        desired_result = "✅ Tenant: 'UTEST_tenant1' successfully created\n"
        try:
            nbox.obj_create("Tenant", "tenancy.tenants", cr_tnt, [])
        except SystemExit:
            pass
        assert capsys.readouterr().out == desired_result, err_msg

    # 1d. MERGE_ERR_DICT: Test merges dictionaires for dev_type component error messages
    def test_merge_dict(self):
        err_msg = "❌ merge_dict: dev_type component error messages dict merge failed"
        desired_result = "type: 1000base-ta is not a valid choice."
        error = [
            {"type": ["1000base-ta is not a valid choice."]},
            {},
            {"type": ["1000base-ta is not a valid choice."]},
        ]
        actual_result = nbox.merge_dict(error)
        assert actual_result == desired_result, err_msg

    # 1e. DEV_TYPE_COMP_CREATE: Test adding components of the device_type (intf, power, etc)
    def test_dev_type_comp_create(self):
        err_msg = "❌ dev_type_comp_create: dev_type component (interface, etc) creation failed"
        desired_result = ["rear_port"]
        conn = {
            "rear_port": [
                {
                    "device_type": {"model": dvc_type},
                    "name": 1,
                    "type": "110-punch",
                },
                {
                    "device_type": {"model": dvc_type},
                    "name": 2,
                    "type": "110-punch",
                },
            ],
            "interface": [],
            "power": [],
            "console": [],
            "front_port": [],
            "slug": make_slug(dvc_type),
        }
        actual_result = nbox.dev_type_comp_create(conn, "Device-type")
        assert actual_result == desired_result, err_msg

        # Test adding front ports and mapping to rear ports
        err_msg = "❌ dev_type_comp_create: dev_type front-ports creation and rear-port mapping failed"
        desired_result = ["front_port"]
        conn["front_port"] = conn["rear_port"]
        conn["rear_port"] = []
        actual_result = nbox.dev_type_comp_create(conn, "Device-type")
        assert actual_result == desired_result, err_msg

    # 1f. DEV_TYPE_CREATE: Test adding device_type and connections
    def test_dev_type_create(self, capsys):
        err_msg = "❌ dev_type_create: dev_type component (interface) addition failed"
        desired_result = "✅ UTEST dvc_type: 'UTEST dvc_type1' successfully created\n"
        dvc_type_dm = [
            {
                "console": [],
                "front_port": [],
                "interface": [
                    {
                        "device_type": {"model": dvc_type1},
                        "mgmt_only": True,
                        "name": "GigabitEthernet1/0/1",
                        "type": "1000base-t",
                    }
                ],
                # "is_full_depth": False,
                "manufacturer": {"name": mftr},
                "model": dvc_type1,
                "power": [],
                "rear_port": [],
                "slug": make_slug(dvc_type1),
            }
        ]
        try:
            nbox.dev_type_create(dvc_type, "dcim.device_types", dvc_type_dm, [])
        except SystemExit:
            pass
        assert capsys.readouterr().out == desired_result, err_msg

    # 1g. VL-GRP: Test getting VLAN group ID
    def test_get_vlgrp_vrf_id_vlgrp(self):
        err_msg = "❌ get_vlgrp_vrf_id: Gathering VLAN Group ID failed"
        vlan_dict = dict(vid=vlan["id"], name=vlan["name"], group=dict(name=vl_grp))
        actual_result = nbox.get_vlgrp_site_vrf_id(
            ["", "ipam.vlan_groups"], ["name", "group_id"], vlan_dict, defaultdict(list)
        )
        assert actual_result["multi-fltr"] == vlan["name"], err_msg
        assert actual_result["chk_fltr"]["name"] == vlan["name"], err_msg
        assert isinstance(actual_result["chk_fltr"]["group_id"], int), err_msg

    # 1h. Site: Test getting site ID
    def test_get_vlgrp_vrf_id_site(self):
        err_msg = "❌ get_vlgrp_vrf_id: Gathering VLAN Group ID failed"
        vlan_dict = dict(vid=vlan["id"], name=vlan["name"], site=dict(name=site))
        actual_result = nbox.get_vlgrp_site_vrf_id(
            ["ipam.vlans", ""], ["name", "group_id"], vlan_dict, defaultdict(list)
        )
        assert actual_result["multi-fltr"] == vlan["name"], err_msg
        assert actual_result["chk_fltr"]["name"] == vlan["name"], err_msg
        assert isinstance(actual_result["chk_fltr"]["site_id"], int), err_msg

    # 1h. VRF_ID: Test getting VRF ID
    def test_get_vlgrp_vrf_id_vrf(self):
        err_msg = "❌ get_vlgrp_vrf_id: Gathering VRF ID failed"
        pfx_dict = dict(prefix=pfx["pfx"], vrf=dict(name=vrf), vrf_rd=vrf_rd)
        actual_result = nbox.get_vlgrp_site_vrf_id(
            ["", "ipam.vrfs"], ["prefix", "vrf_name"], pfx_dict, defaultdict(list)
        )
        assert actual_result["multi-fltr"] == pfx["pfx"], err_msg
        assert actual_result["chk_fltr"]["prefix"] == pfx["pfx"], err_msg
        assert isinstance(actual_result["chk_fltr"]["vrf_name"], int), err_msg

    # 1i. VL-GRP_VRF_ERR: Test getting VLAN group or VRF ID error
    def test_get_vlgrp_vrf_id_err(self):
        err_msg = "❌ get_vlgrp_vrf_id: Gathering VRF ID or VLAN group error failed"
        vlan_dict = dict(vid=vlan["id"], name=vlan["name"], group=dict(name="no_vlgrp"))
        pfx_dict = dict(prefix=pfx["pfx"], vrf=dict(name="no_vrf"), vrf_rd="no_rd")
        desired_result = {"no_vlgrp": [f"{vlan['name']}"], "no_vrf": [f"{pfx['pfx']}"]}
        error = defaultdict(list)
        nbox.get_vlgrp_site_vrf_id(
            ["", "ipam.vlan_groups"], ["name", "group_id"], vlan_dict, error
        )
        nbox.get_vlgrp_site_vrf_id(
            ["", "ipam.vrfs"], ["prefix", "vrf_name"], pfx_dict, error
        )
        assert error == desired_result, err_msg

    # 1j. VL_PFX: Test getting unique VLAN ID to be used by a prefix
    def test_get_vl_pfx_id(self):
        err_msg = "❌ get_vl_pfx_id: Gathering VLAN ID (to be used by a prefix) failed"
        # {'prefix': '10.10.10.0/24', 'vl_grp': 'UTEST vl group', 'vlan': 13, 'vrf': {'name': 'UTEST VRF1'}}
        pfx_dict = dict(
            prefix=pfx["pfx"],
            vrf=dict(
                name=vrf,
            ),
            vlan=pfx["vl"],
            vl_grp=vl_grp,
        )
        actual_result = nbox.get_vl_pfx_id(pfx_dict, defaultdict(list))
        assert isinstance(actual_result.get("vlan"), int), err_msg

    # 1k. VL_PFX_ERR: Test getting unique VLAN ID to be used by a prefix error
    def test_get_vl_pfx_id_err(self):
        err_msg = (
            "❌ get_vl_pfx_id: Gathering VLAN ID (to be used by a prefix) error failed"
        )
        desired_result = {"no_vlgrp": [f"{pfx['pfx']} 'VLAN {pfx['vl']}'"]}
        pfx_dict = dict(
            prefix=pfx["pfx"],
            vrf=dict(
                name=vrf,
            ),
            vlan=pfx["vl"],
            vl_grp="no_vlgrp",
        )
        error = defaultdict(list)
        nbox.get_vl_pfx_id(pfx_dict, error)
        assert error == desired_result, err_msg

    # 1l. CNT_ASGN: Test getting ID of object to assign contact to
    def test_get_cnt_asgn_id(self):
        err_msg = "❌ get_cnt_asgn_id: Gathering ID of object to assign contact failed"
        desired_result = "UTEST Contact UTEST_tenant2 (tenant)"
        asgn_dict = {
            "object_type": "tenancy.tenant",
            "object_id": tnt2,
            "contact": [contact],
            "role": {"name": cnt_role["name"]},
            "priority": "primary",
        }
        actual_result = nbox.get_cnt_asgn_id(asgn_dict, "name", [])
        assert isinstance(actual_result[0].get("object_id"), int), err_msg
        assert isinstance(actual_result[0].get("contact"), int), err_msg
        assert actual_result[0].get("multi-fltr") == desired_result, err_msg

    # 1m. CNT_ASGN_OBJ_ERR: Test getting ID of object to assign contact to
    def test_get_cnt_asgn_id_err_obj(self):
        err_msg = (
            "❌ get_cnt_asgn_id: Gathering of object ID to assign contact error failed"
        )
        desired_result = ["tenant - no_tenant"]
        asgn_dict = {
            "object_type": "tenancy.tenant",
            "object_id": "no_tenant",
            "contact": [contact],
            "role": {"name": cnt_role["name"]},
            "priority": "primary",
        }
        error = []
        nbox.get_cnt_asgn_id(asgn_dict, "name", error)
        assert error == desired_result, err_msg

    # 1n. CNT_ASGN: Test getting ID of object to assign contact to
    def test_get_cnt_asgn_id_err_cnt(self):
        err_msg = "❌ get_cnt_asgn_id: Gathering of contact ID to assign to object error failed"
        desired_result = ["content - no_contact"]
        asgn_dict = {
            "object_type": "tenancy.tenant",
            "object_id": tnt2,
            "contact": ["no_contact"],
            "role": {"name": cnt_role["name"]},
            "priority": "primary",
        }
        error = []
        nbox.get_cnt_asgn_id(asgn_dict, "name", error)
        assert error == desired_result, err_msg

    # 1m. TAG: Test creating tag or getting existing tag ID
    def test_get_or_create_tag(self):
        err_msg = "❌ get_or_create_tag: Creation of tag or checking for existence of tag failed"
        actual_result = nbox.get_or_create_tag({"UTEST_tag": "c0c0c0"})
        assert isinstance(actual_result[0], int), err_msg
        # Run twice as first create, then second time make sure can get the ID
        assert isinstance(actual_result[0], int), err_msg

    # 1o. RT_LIST: Test creating RT or getting existing tag ID (list input)
    def test_get_or_create_rt_list(self):
        err_msg = "❌ get_or_create_rt: Creation of RT (with a list) or checking for existence of RT failed"
        actual_result = nbox.get_or_create_rt(
            ["UTEST1:RT"], my_vars["tenant"][1]["name"]
        )
        assert isinstance(actual_result[0], int), err_msg
        # Run twice as first create, then second time make sure can get the ID
        assert isinstance(actual_result[0], int), err_msg

    # 1p. RT_DICT: Test creating RT or getting existing tag ID (dict input)
    def test_get_or_create_rt_dict(self):
        err_msg = "❌ get_or_create_rt: Creation of RT (with dict) or checking for existence of RT failed"
        actual_result = nbox.get_or_create_rt(
            {"UTEST2:RT": "test"}, my_vars["tenant"][1]["name"]
        )
        assert isinstance(actual_result[0], int), err_msg
        # Run twice as first create, then second time make sure can get the ID
        assert isinstance(actual_result[0], int), err_msg

    # 1q. SLUG: Test creating slug from object name
    def test_make_slug(self):
        err_msg = "❌ make_slug: Creation of slug from object name failed"
        desired_result = "utest_test_slug"
        actual_result = nbox.make_slug("UTEST TEST SLUG")
        assert actual_result == desired_result, err_msg

    # 1r. GET_TNT: Test getting tenant for a site
    def test_get_tnt(self):
        err_msg = "❌ get_tnt: Getting tenant name from a site failed"
        desired_result = tnt2
        actual_result = nbox.get_tnt(my_vars["role"][0]["site"][0]["name"])
        assert actual_result == desired_result, err_msg

    # 1s. NAME_NONE: Test name from netbox api filter if its value is None
    def test_name_none(self):
        err_msg = "❌ name_none: Removing netbox api filter if None failed"
        # actual_result = nbox.name_none(None, dict(name="tenant"))
        # assert actual_result == None, err_msg
        actual_result = nbox.name_none("tennat", dict(name="tenant"))
        assert actual_result == {"name": "tenant"}, err_msg
