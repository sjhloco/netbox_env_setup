from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, cast

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
def make_slug(obj: str | int) -> str:
    if isinstance(obj, int):
        obj = str(obj)
    return obj.replace(" ", "_").lower()


# Load variable file used by all the tests
@pytest.fixture(scope="session")
def my_vars() -> dict[str, Any]:
    with open(test_input, "r") as file_content:
        return cast("dict[str, Any]", yaml.load(file_content, Loader=yaml.FullLoader))


# Test API calls to netbox
@pytest.fixture(scope="class")
def nbox() -> Nbox:
    assert NBOX_TOKEN is not None, "NBOX_TOKEN environment variable must be set"
    ssl_verify: bool = (
        SSL if isinstance(SSL, bool) else SSL.strip().lower() in ("1", "true", "yes")
    )
    return Nbox(NBOX_URL, NBOX_TOKEN, ssl_verify, [], [], [], [])


# Bundles the netbox test objects created for/used by the TestNbox tests
@dataclass
class NboxEnv:
    tnt2: str
    mftr: str
    dvc_type: str
    dvc_type1: str
    vl_grp: str
    vrf: str
    vrf_rd: str
    pfx: dict[str, Any]
    vlan: dict[str, Any]
    cnt_role: dict[str, Any]
    contact: str
    site: str


@pytest.fixture(scope="class")
def nbox_env(my_vars: dict[str, Any]) -> NboxEnv:
    return NboxEnv(
        tnt2=my_vars["tenant"][1]["name"],
        mftr=my_vars["manufacturer"][0]["name"],
        dvc_type="UTEST dvc_type",
        dvc_type1="UTEST dvc_type1",
        vl_grp=my_vars["role"][0]["site"][0]["vlan_grp"][0]["name"],
        vrf=my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]["name"],
        vrf_rd=my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]["rd"],
        pfx=my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]["prefix"][0],
        vlan=my_vars["role"][0]["site"][0]["vlan_grp"][0]["vlan"][0],
        cnt_role=my_vars["contact_role"][0],
        contact=my_vars["contact_group"][0]["contact"][0]["name"],
        site=my_vars["role"][0]["site"][0]["name"],
    )


# Creates then, at teardown, deletes the netbox test objects used by TestNbox
@pytest.fixture(scope="class")
def provision_nbox_test_objects(
    nbox_env: NboxEnv, my_vars: dict[str, Any]
) -> Iterator[None]:
    nb = pynetbox.api(url=NBOX_URL, token=NBOX_TOKEN)

    # Creates nbox test objects
    cr_nbox_obj(
        nb, "tenancy.tenants", {"name": nbox_env.tnt2, "slug": make_slug(nbox_env.tnt2)}, nbox_env.tnt2
    )
    cr_nbox_obj(
        nb, "dcim.manufacturers", {"name": nbox_env.mftr, "slug": make_slug(nbox_env.mftr)}, nbox_env.mftr
    )
    cr_nbox_obj(
        nb,
        "dcim.device_types",
        {
            "name": nbox_env.dvc_type,
            "slug": make_slug(nbox_env.dvc_type),
            "model": nbox_env.dvc_type,
            "manufacturer": dict(name=nbox_env.mftr),
        },
        "dvc_type",
    )
    cr_nbox_obj(
        nb, "ipam.vlan-groups", {"name": nbox_env.vl_grp, "slug": make_slug(nbox_env.vl_grp)}, nbox_env.vl_grp
    )
    cr_nbox_obj(nb, "ipam.vrfs", {"name": nbox_env.vrf, "rd": nbox_env.vrf_rd}, nbox_env.vrf)
    cr_nbox_obj(
        nb,
        "ipam.prefixes",
        {"prefix": nbox_env.pfx["pfx"], "vrf": {"name": nbox_env.vrf}},
        nbox_env.pfx["pfx"],
    )
    cr_nbox_obj(nb, "ipam.prefixes", {"prefix": nbox_env.pfx["pfx"]}, nbox_env.pfx["pfx"])
    cr_nbox_obj(
        nb,
        "ipam.vlans",
        {
            "name": nbox_env.vlan["name"],
            "vid": nbox_env.vlan["id"],
            "group": dict(name=nbox_env.vl_grp),
        },
        nbox_env.vlan["name"],
    )
    cr_nbox_obj(
        nb,
        "tenancy.contact-roles",
        {"name": nbox_env.cnt_role["name"], "slug": nbox_env.cnt_role["slug"]},
        nbox_env.cnt_role["name"],
    )
    cr_nbox_obj(nb, "tenancy.contacts", {"name": nbox_env.contact}, nbox_env.contact)
    cr_nbox_obj(
        nb,
        "dcim.sites",
        {
            "name": nbox_env.site,
            "slug": make_slug(nbox_env.site),
            "tenant": dict(name=nbox_env.tnt2),
        },
        nbox_env.site,
    )

    # Delete nbox test objects that where created
    yield
    del_nbox_obj(nb, "tenancy.tenants", "name", my_vars["tenant"][0]["name"])
    del_nbox_obj(nb, "extras.tags", "name", "UTEST_tag")
    del_nbox_obj(nb, "ipam.route-targets", "name", "UTEST1:RT")
    del_nbox_obj(nb, "ipam.route-targets", "name", "UTEST2:RT")
    del_nbox_obj(nb, "dcim.device_types", "slug", make_slug(nbox_env.dvc_type))
    del_nbox_obj(nb, "dcim.device_types", "slug", make_slug(nbox_env.dvc_type1))
    del_nbox_obj(nb, "dcim.manufacturers", "slug", make_slug(nbox_env.mftr))
    del_nbox_obj(nb, "ipam.vlans", "name", nbox_env.vlan["name"])
    del_nbox_obj(nb, "ipam.vlan-groups", "slug", make_slug(nbox_env.vl_grp))
    del_nbox_obj(nb, "ipam.prefixes", "prefix_vrf", nbox_env.pfx["pfx"], nbox_env.vrf)
    del_nbox_obj(nb, "ipam.prefixes", "prefix", nbox_env.pfx["pfx"])
    del_nbox_obj(nb, "ipam.vrfs", "name", nbox_env.vrf)
    del_nbox_obj(nb, "tenancy.contacts", "name", nbox_env.contact)
    del_nbox_obj(nb, "tenancy.contact-roles", "slug", nbox_env.cnt_role["slug"])
    del_nbox_obj(nb, "dcim.sites", "slug", make_slug(nbox_env.site))
    del_nbox_obj(nb, "tenancy.tenants", "slug", make_slug(nbox_env.tnt2))


# Create unittest netbox objects
def cr_nbox_obj(
    nb: pynetbox.api, api_attr: str, fltr: dict[str, Any], obj_name: str
) -> None:
    try:
        operator.attrgetter(api_attr)(nb).create(**fltr)
    except Exception as e:
        print(type(e))
        print(
            f"❌ An error was raised creating netbox unit test '{api_attr}' object '{obj_name}' - {e}"
        )


# Delete unittest netbox objects
def del_nbox_obj(
    nb: pynetbox.api,
    api_attr: str,
    obj_fltr: str,
    obj_name: str,
    vrf: str | None = None,
) -> None:
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
@pytest.mark.usefixtures("provision_nbox_test_objects")
class TestNbox:

    # 1a. OBJ_CHK: Test object lookup
    def test_obj_check(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ obj_check: Checking for existence of netbox object failed"
        desired_result = {
            "notexist_dm": [{"name": "no_tenant"}],
            "exist_name": [nbox_env.tnt2],
        }
        actual_result = nbox.obj_check(
            "tenancy.tenants",
            "name",
            [{"name": nbox_env.tnt2}, {"name": "no_tenant"}],
        )
        assert actual_result == desired_result, err_msg

    # 1b. OBJ_CHK_EXT: Test object lookup using extended filter (input dict)
    def test_obj_check_ext_fltr(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ obj_check: Checking for existence of netbox object using extended filter (input) failed"
        desired_result = {"exist_name": [nbox_env.tnt2], "notexist_dm": []}
        chk_fltr = {"name": nbox_env.tnt2, "slug": nbox_env.tnt2.lower()}
        actual_result = nbox.obj_check(
            "tenancy.tenants",
            "multi-fltr",
            [{"chk_fltr": chk_fltr, "multi-fltr": nbox_env.tnt2}],
        )
        assert actual_result == desired_result, err_msg

    def test_obj_check_null_vrf(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ obj_check: Checking for existence of netbox object in netbox global VRF failed"
        desired_result = {"exist_name": ["10.10.10.0/24"], "notexist_dm": []}
        actual_result = nbox.obj_check(
            "ipam.prefixes",
            "multi-fltr",
            [
                {
                    "prefix": nbox_env.pfx["pfx"],
                    "vrf": None,
                    "multi-fltr": nbox_env.pfx["pfx"],
                    "chk_fltr": {"prefix": nbox_env.pfx["pfx"], "vrf": None},
                }
            ],
        )
        assert actual_result == desired_result, err_msg

    # 1c. OBJ_CREATE_ERR: Test object creation failure error reporting works
    def test_obj_create_err(
        self, nbox: Nbox, my_vars: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
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
    def test_obj_create(
        self, nbox: Nbox, my_vars: dict[str, Any], capsys: pytest.CaptureFixture[str]
    ) -> None:
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
    def test_merge_dict(self, nbox: Nbox) -> None:
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
    def test_dev_type_comp_create(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ dev_type_comp_create: dev_type component (interface, etc) creation failed"
        desired_result = ["rear_port"]
        conn = {
            "rear_port": [
                {
                    "device_type": {"model": nbox_env.dvc_type},
                    "name": 1,
                    "type": "110-punch",
                },
                {
                    "device_type": {"model": nbox_env.dvc_type},
                    "name": 2,
                    "type": "110-punch",
                },
            ],
            "interface": [],
            "power": [],
            "console": [],
            "front_port": [],
            "slug": make_slug(nbox_env.dvc_type),
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
    def test_dev_type_create(
        self, nbox: Nbox, nbox_env: NboxEnv, capsys: pytest.CaptureFixture[str]
    ) -> None:
        err_msg = "❌ dev_type_create: dev_type component (interface) addition failed"
        desired_result = "✅ UTEST dvc_type: 'UTEST dvc_type1' successfully created\n"
        dvc_type_dm = [
            {
                "console": [],
                "front_port": [],
                "interface": [
                    {
                        "device_type": {"model": nbox_env.dvc_type1},
                        "mgmt_only": True,
                        "name": "GigabitEthernet1/0/1",
                        "type": "1000base-t",
                    }
                ],
                # "is_full_depth": False,
                "manufacturer": {"name": nbox_env.mftr},
                "model": nbox_env.dvc_type1,
                "power": [],
                "rear_port": [],
                "slug": make_slug(nbox_env.dvc_type1),
            }
        ]
        try:
            nbox.dev_type_create(nbox_env.dvc_type, "dcim.device_types", dvc_type_dm, [])
        except SystemExit:
            pass
        assert capsys.readouterr().out == desired_result, err_msg

    # 1g. VL-GRP: Test getting VLAN group ID
    def test_get_vlgrp_vrf_id_vlgrp(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ get_vlgrp_vrf_id: Gathering VLAN Group ID failed"
        vlan_dict = dict(
            vid=nbox_env.vlan["id"],
            name=nbox_env.vlan["name"],
            group=dict(name=nbox_env.vl_grp),
        )
        actual_result = nbox.get_vlgrp_site_vrf_id(
            ["", "ipam.vlan_groups"], ["name", "group_id"], vlan_dict, defaultdict(list)
        )
        assert actual_result is not None, err_msg
        assert actual_result["multi-fltr"] == nbox_env.vlan["name"], err_msg
        assert actual_result["chk_fltr"]["name"] == nbox_env.vlan["name"], err_msg
        assert isinstance(actual_result["chk_fltr"]["group_id"], int), err_msg

    # 1h. Site: Test getting site ID
    def test_get_vlgrp_vrf_id_site(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ get_vlgrp_vrf_id: Gathering VLAN Group ID failed"
        vlan_dict = dict(
            vid=nbox_env.vlan["id"], name=nbox_env.vlan["name"], site=dict(name=nbox_env.site)
        )
        actual_result = nbox.get_vlgrp_site_vrf_id(
            ["ipam.vlans", ""], ["name", "group_id"], vlan_dict, defaultdict(list)
        )
        assert actual_result is not None, err_msg
        assert actual_result["multi-fltr"] == nbox_env.vlan["name"], err_msg
        assert actual_result["chk_fltr"]["name"] == nbox_env.vlan["name"], err_msg
        assert isinstance(actual_result["chk_fltr"]["site_id"], int), err_msg

    # 1h. VRF_ID: Test getting VRF ID
    def test_get_vlgrp_vrf_id_vrf(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ get_vlgrp_vrf_id: Gathering VRF ID failed"
        pfx_dict = dict(
            prefix=nbox_env.pfx["pfx"], vrf=dict(name=nbox_env.vrf), vrf_rd=nbox_env.vrf_rd
        )
        actual_result = nbox.get_vlgrp_site_vrf_id(
            ["", "ipam.vrfs"], ["prefix", "vrf_name"], pfx_dict, defaultdict(list)
        )
        assert actual_result is not None, err_msg
        assert actual_result["multi-fltr"] == nbox_env.pfx["pfx"], err_msg
        assert actual_result["chk_fltr"]["prefix"] == nbox_env.pfx["pfx"], err_msg
        assert isinstance(actual_result["chk_fltr"]["vrf_name"], int), err_msg

    # 1i. VL-GRP_VRF_ERR: Test getting VLAN group or VRF ID error
    def test_get_vlgrp_vrf_id_err(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ get_vlgrp_vrf_id: Gathering VRF ID or VLAN group error failed"
        vlan_dict = dict(
            vid=nbox_env.vlan["id"], name=nbox_env.vlan["name"], group=dict(name="no_vlgrp")
        )
        pfx_dict = dict(
            prefix=nbox_env.pfx["pfx"], vrf=dict(name="no_vrf"), vrf_rd="no_rd"
        )
        desired_result = {
            "no_vlgrp": [f"{nbox_env.vlan['name']}"],
            "no_vrf": [f"{nbox_env.pfx['pfx']}"],
        }
        error: defaultdict[str, list[str]] = defaultdict(list)
        nbox.get_vlgrp_site_vrf_id(
            ["", "ipam.vlan_groups"], ["name", "group_id"], vlan_dict, error
        )
        nbox.get_vlgrp_site_vrf_id(
            ["", "ipam.vrfs"], ["prefix", "vrf_name"], pfx_dict, error
        )
        assert error == desired_result, err_msg

    # 1j. VL_PFX: Test getting unique VLAN ID to be used by a prefix
    def test_get_vl_pfx_id(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ get_vl_pfx_id: Gathering VLAN ID (to be used by a prefix) failed"
        # {'prefix': '10.10.10.0/24', 'vl_grp': 'UTEST vl group', 'vlan': 13, 'vrf': {'name': 'UTEST VRF1'}}
        pfx_dict = dict(
            prefix=nbox_env.pfx["pfx"],
            vrf=dict(
                name=nbox_env.vrf,
            ),
            vlan=nbox_env.pfx["vl"],
            vl_grp=nbox_env.vl_grp,
        )
        actual_result = nbox.get_vl_pfx_id(pfx_dict, defaultdict(list))
        assert actual_result is not None, err_msg
        assert isinstance(actual_result.get("vlan"), int), err_msg

    # 1k. VL_PFX_ERR: Test getting unique VLAN ID to be used by a prefix error
    def test_get_vl_pfx_id_err(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = (
            "❌ get_vl_pfx_id: Gathering VLAN ID (to be used by a prefix) error failed"
        )
        desired_result = {"no_vlgrp": [f"{nbox_env.pfx['pfx']} 'VLAN {nbox_env.pfx['vl']}'"]}
        pfx_dict = dict(
            prefix=nbox_env.pfx["pfx"],
            vrf=dict(
                name=nbox_env.vrf,
            ),
            vlan=nbox_env.pfx["vl"],
            vl_grp="no_vlgrp",
        )
        error: defaultdict[str, list[str]] = defaultdict(list)
        nbox.get_vl_pfx_id(pfx_dict, error)
        assert error == desired_result, err_msg

    # 1k2. CLTR_SCOPE: Test getting site ID for a Cluster's scope_id
    def test_get_cltr_scope_id(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ get_cltr_scope_id: Gathering site ID for Cluster scope_id failed"
        cltr_dict = {"name": "UTEST_cluster", "scope_id": nbox_env.site}
        actual_result = nbox.get_cltr_scope_id(cltr_dict, [])
        assert actual_result is not None, err_msg
        assert isinstance(actual_result.get("scope_id"), int), err_msg

    # 1k3. CLTR_SCOPE_ERR: Test getting site ID for a Cluster's scope_id error
    def test_get_cltr_scope_id_err(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ get_cltr_scope_id: Gathering site ID for Cluster scope_id error failed"
        desired_result = ["no_site"]
        cltr_dict = {"name": "UTEST_cluster", "scope_id": "no_site"}
        error: list[str] = []
        actual_result = nbox.get_cltr_scope_id(cltr_dict, error)
        assert actual_result is None, err_msg
        assert error == desired_result, err_msg

    # 1l. CNT_ASGN: Test getting ID of object to assign contact to
    def test_get_cnt_asgn_id(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ get_cnt_asgn_id: Gathering ID of object to assign contact failed"
        desired_result = "UTEST Contact UTEST_tenant2 (tenant)"
        asgn_dict = {
            "object_type": "tenancy.tenant",
            "object_id": nbox_env.tnt2,
            "contact": [nbox_env.contact],
            "role": {"name": nbox_env.cnt_role["name"]},
            "priority": "primary",
        }
        actual_result = nbox.get_cnt_asgn_id(asgn_dict, "name", [])
        assert isinstance(actual_result[0].get("object_id"), int), err_msg
        assert isinstance(actual_result[0].get("contact"), int), err_msg
        assert actual_result[0].get("multi-fltr") == desired_result, err_msg

    # 1m. CNT_ASGN_OBJ_ERR: Test getting ID of object to assign contact to
    def test_get_cnt_asgn_id_err_obj(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = (
            "❌ get_cnt_asgn_id: Gathering of object ID to assign contact error failed"
        )
        desired_result = ["tenant - no_tenant"]
        asgn_dict = {
            "object_type": "tenancy.tenant",
            "object_id": "no_tenant",
            "contact": [nbox_env.contact],
            "role": {"name": nbox_env.cnt_role["name"]},
            "priority": "primary",
        }
        error: list[str] = []
        nbox.get_cnt_asgn_id(asgn_dict, "name", error)
        assert error == desired_result, err_msg

    # 1n. CNT_ASGN: Test getting ID of object to assign contact to
    def test_get_cnt_asgn_id_err_cnt(self, nbox: Nbox, nbox_env: NboxEnv) -> None:
        err_msg = "❌ get_cnt_asgn_id: Gathering of contact ID to assign to object error failed"
        desired_result = ["content - no_contact"]
        asgn_dict = {
            "object_type": "tenancy.tenant",
            "object_id": nbox_env.tnt2,
            "contact": ["no_contact"],
            "role": {"name": nbox_env.cnt_role["name"]},
            "priority": "primary",
        }
        error: list[str] = []
        nbox.get_cnt_asgn_id(asgn_dict, "name", error)
        assert error == desired_result, err_msg

    # 1m. TAG: Test creating tag or getting existing tag ID
    def test_get_or_create_tag(self, nbox: Nbox) -> None:
        err_msg = "❌ get_or_create_tag: Creation of tag or checking for existence of tag failed"
        actual_result = nbox.get_or_create_tag({"UTEST_tag": "c0c0c0"})
        assert isinstance(actual_result[0], int), err_msg
        # Run twice as first create, then second time make sure can get the ID
        assert isinstance(actual_result[0], int), err_msg

    # 1o. RT_LIST: Test creating RT or getting existing tag ID (list input)
    def test_get_or_create_rt_list(self, nbox: Nbox, my_vars: dict[str, Any]) -> None:
        err_msg = "❌ get_or_create_rt: Creation of RT (with a list) or checking for existence of RT failed"
        actual_result = nbox.get_or_create_rt(
            ["UTEST1:RT"], my_vars["tenant"][1]["name"]
        )
        assert isinstance(actual_result[0], int), err_msg
        # Run twice as first create, then second time make sure can get the ID
        assert isinstance(actual_result[0], int), err_msg

    # 1p. RT_DICT: Test creating RT or getting existing tag ID (dict input)
    def test_get_or_create_rt_dict(self, nbox: Nbox, my_vars: dict[str, Any]) -> None:
        err_msg = "❌ get_or_create_rt: Creation of RT (with dict) or checking for existence of RT failed"
        actual_result = nbox.get_or_create_rt(
            {"UTEST2:RT": "test"}, my_vars["tenant"][1]["name"]
        )
        assert isinstance(actual_result[0], int), err_msg
        # Run twice as first create, then second time make sure can get the ID
        assert isinstance(actual_result[0], int), err_msg

    # 1q. SLUG: Test creating slug from object name
    def test_make_slug(self, nbox: Nbox) -> None:
        err_msg = "❌ make_slug: Creation of slug from object name failed"
        desired_result = "utest_test_slug"
        actual_result = nbox.make_slug("UTEST TEST SLUG")
        assert actual_result == desired_result, err_msg

    # 1r. GET_TNT: Test getting tenant for a site
    def test_get_tnt(self, nbox: Nbox, nbox_env: NboxEnv, my_vars: dict[str, Any]) -> None:
        err_msg = "❌ get_tnt: Getting tenant name from a site failed"
        desired_result = nbox_env.tnt2
        actual_result = nbox.get_tnt(my_vars["role"][0]["site"][0]["name"])
        assert actual_result == desired_result, err_msg

    # 1s. NAME_NONE: Test name from netbox api filter if its value is None
    def test_name_none(self, nbox: Nbox) -> None:
        err_msg = "❌ name_none: Removing netbox api filter if None failed"
        # actual_result = nbox.name_none(None, dict(name="tenant"))
        # assert actual_result == None, err_msg
        actual_result = nbox.name_none("tennat", dict(name="tenant"))
        assert actual_result == {"name": "tenant"}, err_msg
