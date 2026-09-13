# NetBox - Baseline Environment

This script will create all the objects within the NetBox environment ready for the addition of devices, it does not add the devices themselves. It is not idempotent as the purpose is to add objects rather than edit or delete existing objects. The Netbox environment is defined in YAML files that follow the hierarchical structure of the NetBox menus. The script follows this same structure allowing sub-sections of the environment to be created or additions to be made to an existing section.

This tool is designed to be used against Netbox v4.7.0 (pynetbox 7.7.0), for other versions of Netbox check the [pynetbox compatibility matirx](https://github.com/netbox-community/pynetbox#compatibility) as some elements may break on earlier non-matched Netbox versions.

## API Engine

From the YAML input files *Data-Models* (per-menu) are built and fed into the API engine to create any objects that do not already exist. The *`obj_check`* method verifies whether an object already exists and uses *`obj_create`* to create the NetBox objects and handle errors.

[![flow chart](https://mermaid.ink/img/eyJjb2RlIjoiZ3JhcGggTFJcbkFbL2lucHV0IFlBTUwgZmlsZS9dLS0-Qnt7RGF0YSBNb2RlbCBNZXRob2R9fS0tPkMoW0NoZWNrIE1ldGhvZF0pLS0-RCgoQ3JlYXRlIE1ldGhvZCkpXG5cbiIsIm1lcm1haWQiOnsidGhlbWUiOiJkZWZhdWx0In0sInVwZGF0ZUVkaXRvciI6ZmFsc2V9)](https://mermaid-js.github.io/mermaid-live-editor/#/edit/eyJjb2RlIjoiZ3JhcGggTFJcbkFbL2lucHV0IFlBTUwgZmlsZS9dLS0-Qnt7RGF0YSBNb2RlbCBNZXRob2R9fS0tPkMoW0NoZWNrIE1ldGhvZF0pLS0-RCgoQ3JlYXRlIE1ldGhvZCkpXG5cbiIsIm1lcm1haWQiOnsidGhlbWUiOiJkZWZhdWx0In0sInVwZGF0ZUVkaXRvciI6ZmFsc2V9)

## Data Models

Each NetBox menu is represented by a separate data-model class (from ***`dm.py`***) that is instantiated using dictionaries from the input file to create a list of dictionaries for each of the objects under that NetBox menu. These dictionaries are passed through the *`engine`* class (from ***`netbox.py`***) which hold all the methods that interact with NetBox to check object existence and perform object creation.

All data-model classes are built in the same format consisting of *cr_xxx* methods to create object data-models and a *create_xxx* method to run all the *cr_xxx* methods and return the complete data-model. Below is an example of how *Organisation* objects are created by first instantiating the class using input friendly name (for stdout message), path of api call, filter (to check if object already exists) and data-model are passed into the engine.

``` python
org = Organisation(my_vars["tenant"], my_vars["rack_role"])
org_dict = org.create_tnt_site_rack()

nbox.engine("Rack Role", "dcim.rack_roles", "name", org_dict["rack_role"])
nbox.engine("Tenant", "tenancy.tenants", "name", org_dict["tnt"])
nbox.engine("Site", "dcim.sites", "name", org_dict["site"])
nbox.engine("Location (parent)", "dcim.locations", "slug", org_dict["prnt_loc"])
nbox.engine("Location (child)", "dcim.locations", "slug", org_dict["chld_loc"])
nbox.engine("Rack", "dcim.racks", "name", org_dict["rack"])
```

## Input data

The input data can be defined in the one file or split over multiple YAML files (*.yml*, *.yaml*) of any name, the script loads all YAML files in the input directory. Because of the hierarchical structure of the YAML file the mandatory dictionary elements will still be required in the file even if those objects are not being created by this script. For example, to create a rack the YAML file needs the tenant, site and location.

The `examples` directory has a few example data-models to show how the files are structured.
- **full:** *An example setup with all the available options defined*
- **simple1:** *A more streamlined example with just the bare minimum options defined*
- **simple2:** *Same as last example but VLANs are under a site rather than a VLAN group*
- **work_setup:** *Structured more for a corporate environment in terms of sites and the roles within IPAM*

For most options the slug is optional, if it is not defined it will be automatically generated from the name replacing any white-spaces with `_`. If you have multiple objects with the same name make sure you set the slug as this is what gives it uniqueness in Netbox

### Organisation - *Tenants, Sites, Locations, Racks, Rack-roles*

Tenants are top of the tree with optional sites that contain locations (and child locations) that in turn contain racks.

| Object | Description | Mandatory | Optional |
| ------ | ----------- | --------- | -------- |
| tenant | List of tenants | name | slug, descr, tags, ***site*** |
| tenant.site | List of sites | name | slug, descr, tags, time_zone, ASN,  ***location*** |
| tenant.site.location | List of locations (like a floor) | name | slug, descr, tags, ***rack***, ***location*** |
| tenant.site.location.rack | List of racks | name | tags, role, height, tenant |
| tenant.site.location.location | List of child locations (like a room) | name | slug, descr, tags, ***rack*** |
| tenant.site.location.location.rack | List of racks in child locations | name | tags, role, height, tenant |
| rack-role | List of rack roles | name, color, | slug, descr, tags |

Be careful with child locations as if you are using a generic name such as *Room1* although it is nested under the parent location in the GUI you need to make sure you define a unique slug as under the hood is no hierarchy.

### Devices - *Manufacturers, Platforms, Device-types, Device-roles*

The device-types are built from pre-defined YAML files that can be downloaded from the [NetBox community](https://github.com/netbox-community/devicetype-library) or custom created using that same format. By default these are expected to be stored in the *device_type* directory.

| Object | Description | Mandatory | Optional |
| ------ | ----------- | --------- | -------- |
| manufacturer | List of all device manufacturers | name | slug, descr, tags, ***platform*** |
| manufacturer.platform | List of platforms (used for NAPALM) | name | slug, descr, tags, driver |
| manufacturer.device_type | List of device-type yaml files | device-type.yaml | n/a |
| device_role | List of device roles (to assign to device types) | name, color | slug, descr, tags, vm_role |

### IPAM - *RIR, Aggregates, Prefix/VLAN roles, VLAN groups, VLANs, VRFs, Prefixes*

Prefix/VLAN roles are at the top of the IPAM hierarchy grouping together VLANs and prefixes. VLAN-groups, VLANs, VRFs and prefixes are all in some way related to sites and tenants so are defined under the site with the sites tenant automatically associated or overridden on a per-VLAN group, VLAN, VRF or prefix basis.

- A Prefix/VLAN role can only be used once in the file, it holds all VRFs and VLANs to be added beneath it.
- A VRF or VLAN group can be used multiple times under differing prefix/VLAN roles with the attributes of the first occurrence (description, RT, RD, etc) taken.
- VRFs (and prefixes) can be defined under the role (non-VLAN environments like clouds) or the VLAN group (to associate prefixes with VLANs). RDs are what make VRFs with the same name unique.
- VLANs can be grouped under a VLAN group or directly under the site. If you deploy them under the site NetBox does not enforce VLAN uniqueness however the script will not redeploy a VLAN if it already exists in that site. I prefer to use VLAN groups as they enforce uniqueness and provide a better view of unused VLANs.

| Object | Description | Mandatory | Optional |
| ------ | ----------- | --------- | -------- |
| rir | List of governing bodies (includes RFC1918) | name | slug, descr, tags, is_private, ***aggregate*** |
| rir.aggregate | List of aggregates in the RIR (your assigned PA or PI prefixes) | prefix | descr, tags |
| role | List of prefix and VLAN roles | name, ***site*** | slug, descr, tags |
| role.site | List of existing sites to associate VLANs, VRFs and prefixes | name | ***vlan_grp***, ***vrf*** |
| role.site.vlan_grp | List of VLAN groups | name, ***vlan*** | slug, descr, tags, tenant, ***vrf*** |
| role.site.vlan_grp.vlan | List of VLANs in the VLAN group | name, id | descr, tags, tenant |
| role.site.vlan_grp.vrf | VRFs in a site with VLANs (prefixes can be linked to VLANs) | name, ***prefix*** | descr, tags, tenant, rd, import_rt, export_rt, unique |
| role.site.vlan_grp.vrf.prefix | List of prefixes within this VRF | pfx | descr, tags, status, vl, pool, tenant |
| role.site.vlan | List of VLANs in a site (no vlan group) | name, id | descr, tags, tenant |
| role.site.vrf | VRFs whose prefixes aren't associated to VLANs or are associated to site VLANs | name, ***prefix*** | descr, tags, tenant, rd, import_rt, export_rt, unique |
| role.site.vrf.prefix | List of prefixes within this VRF | pfx | descr, tags, tenant, pool |

Using *Null* as the VRF name will add the prefixes to the NetBox *Global* VRF. Using this in conjunction with a prefix status of *container*  allows for prefixes from differing VRFs to be seen as child prefixes under this parent prefix. *Null* can also be used for the site to associate the prefixes with no particular site. By default all prefixes are not a pool unless specifically set as one.

### Provider/ Circuit -  *Circuit-type, Provider, Circuit*

Providers are the ISPs that hold individual circuits with pre-defined circuit-types.

| Object | Description | Mandatory | Optional |
| ------ | ----------- | --------- | -------- |
| circuit_type | List of circuit types | name | slug, descr, tags |
| provider | List of providers | name | slug, comments, tags, asn, account_num, portal_url, ***circuit*** |
| provider.circuit | List of this providers circuits | cid, type | descr, tags, tenant, commit_rate, comments |

### Virtual - *Cluster-group, Cluster-type, Cluster*

Clusters are groupings of resources which VMs run within. Cluster-groups and types allow further grouping of clusters based on things such as location or technology. Site, tenant, cluster-group and tags can be set globally for all members of a cluster-type or be overridden on a per-cluster basis.

| Object | Description | Mandatory | Optional |
| ------ | ----------- | --------- | -------- |
| cluster_group | List of groups (optional) | name | slug, descr, tags |
| cluster_type | List of cluster type | name | slug, descr, tags, ***cluster*** |
| cluster_type.cluster | List of clusters of this cluster type | name | comment, tags, tenant, site, group |

### Contacts - *Contact-role, Contact-group, Contact Assignment*

Contacts are actually in the organisation menu but are defined separately as they can be assigned to a tenant, site, location, rack, manufacturer, cluster-group, cluster, provider or circuit (in GUI you can also assign Device, PowerPanel, Region, SiteGroup, and VirtualMachine).

| Object | Description | Mandatory | Optional |
| ------ | ----------- | --------- | -------- |
| contact_role | List of contact roles | name | slug, descr, tags |
| contact_group | List of contact groups | name | slug, descr, tags |
| contact_group.contact | List of contacts (can only be member of 1 group) | name | comments, tags, phone, email, addr |
| contact_assign | Assign contacts to roles | assign_to, role, contact | priority |

## Installation and Prerequisites

Clone the repository and install the required python packages, the easiest way to do this is with uv as it automatically creates and activates the virtual environment.

```bash
git clone https://github.com/sjhloco/netbox_env_setup.git
cd netbox_env_setup

uv sync
```

To get started set the Netbox API URL and token environment variables, everything else is optional.

| Environment variable | Default | Information |
| -------------------- | ------- | ----------- |
| `NBOX_URL` | `http://netbox.netbox-docker.orb.local` | Default netbox instance, falls back to docker version on Orb |
| `NBOX_TOKEN` | n/a | Netbox API token (don't include Bearer, just the token) |
| `SSL` | `False` | To enable HTTPS for netbox API, vy default uses HTTP |
| `DVC_TYPE_DIR` | `working_dir/device_type` | Directory that holds all device type templates (mentioned in the script) |
| `INPUT_DIR` | `current_working_directory` | Directory that holds all the .yml/.yaml input files, can also be set at runtime |

## Usage

Before running ***nbox_env_setup.py*** it is recommended to use ***input_validate.py*** to verify the contents of input YAML files. It is an offline script (doesn't connect to NetBox) that verifies things such as:

- All parent dictionaries (*tenant, manufacturer, rir, role, crt_type, provider, cluster_type, contact_role, contact_group, contact_assign*) are present and the key is a list (can be an empty list if not used)
- All mandatory dictionaries are present
- All Dictionary keys that are meant to be a list, integer, boolean or IPv4 address are of the correct format
- No duplicate object names
- All referenced objects such as tenant, site, rack_role, etc, exist within the input file. If you are not running all tests (for example don't have organisation defined) you will get dependency warnings as it will look for objects such as sites and tenants which don't exist. Can either ignore these or add them to the  *all_site*, *all_tnt* and *all_obj* lists to stop the warnings

```bash
uv run input_validate.py "examples/simple1"
```

The script can be run with no flags to create all objects or with flags to only create specific section objects.

| Flag | Description |
| ---- | ----------- |
| `-o` | Create **Organisation** objects (*Circuit-type, Provider, Circuit*) |
| `-d` | Create **Device objects** (*Manufacturers, Platforms, Device-types, Device-roles*) |
| `-i` | Create **IPAM** objects (*RIR, Aggregates, Prefix/VLAN roles, VLAN groups, VLANs, VRFs, Prefixes*) |
| `-p` | Create **Provider** objects (*Circuit-type, Provider, Circuit*) |
| `-c` | Create **Contact** objects (*Cluster-group, Cluster-type, Cluster*) |
| `-v` | Create **Virtualisation** objects (*Contact-role, Contact-group, Contact Assignment*) |
| none | Create everything |

```python
uv run nbox_env_setup.py "examples/simple1"
```

There are three possible outcomes from the attempt to create each object which are relayed back in stdout:\
✅ Object created\
⚠️ Object already exists\
❌ Object can’t be created due to the defined error

![run_example_video](https://user-images.githubusercontent.com/33333983/154144431-9cbf0e5d-24d6-4bc2-b580-5096d29f0047.gif)

## Unit test

Unit-testing uses pytest test the majority of situations for the data-modelling (*test_dm.py*) and netbox api calls (*test_netbox.py*). The netbox testing script requires a netbox URL and API as it will build and destroy a test netbox setup to run the tests against.

```python
uv run pytest -vv
uv run pytest tests/test_dm.py -vv
uv run pytest tests/test_netbox.py -vv
```

## AI Disclaimer

Everything up to 2026-09-13 was written without AI assistance. Since then, some changes are made with AI assistance (mainly Claude Code).
