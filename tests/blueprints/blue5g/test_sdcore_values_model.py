import copy

from nfvcl.blueprints_ng.modules.sdcore.sdcore_default_config import default_config
from nfvcl.blueprints_ng.modules.sdcore.sdcore_blueprint import SdCoreBlueprintNG
from nfvcl.blueprints_ng.modules.sdcore.sdcore_values_model import SDCoreValuesModel
from nfvcl_models.blueprint_ng.core5g.common import Create5gModel
from tests.blueprints.blue5g.create_configs import CORE_5G


class _SdCoreUpdateOrderRecorder:
    def __init__(self):
        self.calls: list[str] = []

    def update_edge_areas(self, start_upfs: bool = True):
        self.calls.append("edge-started" if start_upfs else "edge-stopped")

    def update_core(self):
        self.calls.append("core")

    def update_gnb_configs(self):
        self.calls.append("gnb")


def _sdcore_values_from_generic_model(generic_model: Create5gModel) -> SDCoreValuesModel:
    sdcore_values = copy.deepcopy(default_config)
    sdcore_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration.from_generic_5g_model(
        generic_model
    )
    return sdcore_values


def _network_slice_gnbs(sdcore_values: SDCoreValuesModel, slice_id: str) -> list[tuple[str, int]]:
    network_slices = sdcore_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration.network_slices
    network_slice = next(network_slice for network_slice in network_slices if network_slice.slice_id.sd == slice_id)
    return [
        (gnb.name, gnb.tac)
        for gnb in network_slice.site_info.g_node_bs
    ]


def _helm_network_slice_gnbs(sdcore_values: SDCoreValuesModel, slice_id: str) -> list[dict]:
    network_slices = (
        sdcore_values.model_dump_for_helm()["omec-sub-provision"]["config"]["simapp"]["cfgFiles"]
        ["simapp.yaml"]["configuration"]["network-slices"]
    )
    network_slice = next(network_slice for network_slice in network_slices if network_slice["slice-id"]["sd"] == slice_id)
    return network_slice["site-info"]["gNodeBs"]


def test_sdcore_values_include_gnb_for_single_area_slice():
    generic_model = Create5gModel.model_validate(CORE_5G)

    sdcore_values = _sdcore_values_from_generic_model(generic_model)

    assert _network_slice_gnbs(sdcore_values, "000001") == [("gnb1", 1)]
    assert _helm_network_slice_gnbs(sdcore_values, "000001") == [{"name": "gnb1", "tac": 1}]


def test_sdcore_values_include_all_gnbs_for_multi_area_slice():
    generic_model = Create5gModel.model_validate(CORE_5G)
    second_area = copy.deepcopy(generic_model.areas[0])
    second_area.id = 2
    second_area.core = False
    generic_model.areas.append(second_area)

    sdcore_values = _sdcore_values_from_generic_model(generic_model)

    assert _network_slice_gnbs(sdcore_values, "000001") == [("gnb1", 1), ("gnb2", 2)]
    assert _helm_network_slice_gnbs(sdcore_values, "000001") == [
        {"name": "gnb1", "tac": 1},
        {"name": "gnb2", "tac": 2},
    ]


def test_sdcore_add_slice_updates_core_before_gnbs():
    recorder = _SdCoreUpdateOrderRecorder()

    SdCoreBlueprintNG.add_slice(recorder, add_slice_model=None, oss=False)

    assert recorder.calls == ["edge-stopped", "core", "edge-started", "gnb"]


def test_sdcore_add_tac_updates_core_before_gnbs():
    recorder = _SdCoreUpdateOrderRecorder()

    SdCoreBlueprintNG.add_tac(recorder, add_area_model=None)

    assert recorder.calls == ["edge-stopped", "core", "edge-started", "gnb"]


def test_sdcore_delete_updates_core_before_removing_upfs():
    recorder = _SdCoreUpdateOrderRecorder()

    SdCoreBlueprintNG.del_slice(recorder, del_slice_model=None)

    assert recorder.calls == ["core", "edge-started", "gnb"]


def test_sdcore_delete_tac_updates_core_before_removing_upfs():
    recorder = _SdCoreUpdateOrderRecorder()

    SdCoreBlueprintNG.del_tac(recorder, del_area_model=None)

    assert recorder.calls == ["core", "edge-started", "gnb"]


def test_sdcore_webui_models_match_api_response_shape():
    generic_model = Create5gModel.model_validate(CORE_5G)
    sdcore_values = _sdcore_values_from_generic_model(generic_model)
    configuration = sdcore_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration

    device_group = SdCoreBlueprintNG._expected_webui_device_group(configuration.device_groups[0])
    network_slice = SdCoreBlueprintNG._expected_webui_network_slice(configuration.network_slices[0])

    assert device_group["group-name"] == "device-group-slice_000001"
    assert "name" not in device_group
    ue_dnn_qos = device_group["ip-domain-expanded"]["ue-dnn-qos"]
    assert ue_dnn_qos["dnn-mbr-downlink"] == 100_000_000
    assert ue_dnn_qos["dnn-mbr-uplink"] == 100_000_000
    assert ue_dnn_qos["bitrate-unit"] == "mbps"
    assert network_slice["SliceName"] == "slice_000001"
    assert network_slice["slice-id"] == {"sst": "1", "sd": "000001"}
    assert network_slice["site-info"]["gNodeBs"] == [{"name": "gnb1", "tac": 1}]
    assert "name" not in network_slice


def test_sdcore_webui_empty_imsi_list_is_serialized_as_null():
    generic_model = Create5gModel.model_validate(CORE_5G)
    sdcore_values = _sdcore_values_from_generic_model(generic_model)
    device_group = (
        sdcore_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration.device_groups[0]
    )
    device_group.imsis = []

    expected_device_group = SdCoreBlueprintNG._expected_webui_device_group(device_group)

    assert expected_device_group["imsis"] is None


def test_sdcore_webui_empty_gnb_list_is_serialized_as_null():
    generic_model = Create5gModel.model_validate(CORE_5G)
    sdcore_values = _sdcore_values_from_generic_model(generic_model)
    network_slice = (
        sdcore_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration.network_slices[0]
    )
    network_slice.site_info.g_node_bs = []

    expected_network_slice = SdCoreBlueprintNG._expected_webui_network_slice(network_slice)

    assert expected_network_slice["site-info"]["gNodeBs"] is None


def test_sdcore_webui_unassigned_slice_ignores_stale_area_values():
    generic_model = Create5gModel.model_validate(CORE_5G)
    sdcore_values = _sdcore_values_from_generic_model(generic_model)
    network_slice = (
        sdcore_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration.network_slices[0]
    )
    network_slice.site_info.g_node_bs = []
    expected = SdCoreBlueprintNG._expected_webui_network_slice(network_slice)
    actual = copy.deepcopy(expected)
    actual["site-info"]["gNodeBs"] = [{"name": "gnb2", "tac": 2}]
    actual["site-info"]["upf"]["upf-name"] = "10.255.251.172"

    assert SdCoreBlueprintNG._webui_network_slice_matches(actual, expected)

    actual["site-info"]["upf"]["upf-port"] = 8806
    assert not SdCoreBlueprintNG._webui_network_slice_matches(actual, expected)


def test_sdcore_webui_configuration_requires_complete_matching_objects():
    generic_model = Create5gModel.model_validate(CORE_5G)
    sdcore_values = _sdcore_values_from_generic_model(generic_model)
    configuration = sdcore_values.omec_sub_provision.config.simapp.cfg_files.simapp_yaml.configuration
    device_group = configuration.device_groups[0]
    network_slice = configuration.network_slices[0]
    blueprint = SdCoreBlueprintNG("test-sdcore-readiness")
    blueprint.state.sdcore_config_values = sdcore_values

    responses = {
        "device-group": (200, [device_group.name]),
        f"device-group/{device_group.name}": (
            200,
            blueprint._expected_webui_device_group(device_group),
        ),
        "network-slice": (200, [network_slice.name]),
        f"network-slice/{network_slice.name}": (
            200,
            blueprint._expected_webui_network_slice(network_slice),
        ),
    }
    blueprint._get_webui_config = responses.__getitem__

    assert blueprint._webui_configuration_mismatch() is None

    responses[f"network-slice/{network_slice.name}"] = (404, None)
    assert blueprint._webui_configuration_mismatch() == (
        f"network-slice '{network_slice.name}' returned HTTP 404"
    )
