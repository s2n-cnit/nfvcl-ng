from typing import List, Optional

from pydantic import Field

from nfvcl.blueprints_ng.lcm.blueprint_type_manager import blueprint_type
from nfvcl.blueprints_ng.modules.athonet.athonet_upf_blue import ATHONET_UPF_BLUE_TYPE
from nfvcl.blueprints_ng.modules.generic_5g.generic_5g import Generic5GBlueprintNG, Generic5GBlueprintNGState
from nfvcl.models.blueprint_ng.Athonet.core import ProvisionedDataInfo, AthonetApplicationCoreConfig
from nfvcl.models.blueprint_ng.core5g.common import Create5gModel, SubSliceProfiles, SubSubscribers, SubArea, SubDataNets, SubSnssai
from nfvcl.models.blueprint_ng.g5.core import Core5GAddSubscriberModel, Core5GDelSubscriberModel, Core5GDelSliceModel, Core5GAddSliceModel, Core5GAddDnnModel, Core5GDelDnnModel
from nfvcl.models.network.network_models import PduType

ATHONET_BLUE_TYPE = "athonet"


class AthonetCoreBlueprintNGState(Generic5GBlueprintNGState):
    """
    This class represent the current state of the blueprint, the data contained in this class will be saved to the DB.

    Every Resource should be stored in a variable in this class to be able to access it after the initial creation.

    Everything in this class should be serializable by Pydantic.

    Every field need to be Optional because the state is created empty.

    """
    # ues: dict = Field(default_factory=dict)
    backup_config: Optional[AthonetApplicationCoreConfig] = Field(default=None)


@blueprint_type(ATHONET_BLUE_TYPE)
class AthonetCore(Generic5GBlueprintNG[AthonetCoreBlueprintNGState, Create5gModel]):
    default_upf_implementation = ATHONET_UPF_BLUE_TYPE
    router_needed = False

    def __init__(self, blueprint_id: str, state_type: type[Generic5GBlueprintNGState] = AthonetCoreBlueprintNGState):
        super().__init__(blueprint_id, state_type)

    def create_5g(self, create_model: Create5gModel):
        if len(self.state.current_config.areas) > 1:
            raise Exception("Athonet does not support multiple areas yet")

        pdu = self.provider.find_pdu(self.state.current_config.areas[0].id, PduType.CORE5G, 'AthonetCore')
        self.provider.lock_pdu(pdu)
        configurator = self.provider.get_pdu_configurator(pdu)

        if len(configurator.dnnvrfmapping.dnns) < len(create_model.config.network_endpoints.data_nets):
            raise Exception(f"Error, maximum number of supported dnn is {len(configurator.dnnvrfmapping.dnns)}")

        configurator.delete_all_supis()
        configurator.delete_all_udr_plmns()

        self.state.backup_config = configurator.get_core_config()
        configurator.configure(self.state.current_config)

        for subscriber in create_model.config.subscribers:
            addiotional_infos = self.ues_additional_infos(subscriber.snssai)
            configurator.add_user(subscriber, addiotional_infos)

    def destroy(self):
        pdu = self.provider.find_pdu(self.state.current_config.areas[0].id, PduType.CORE5G, 'AthonetCore')
        configurator = self.provider.get_pdu_configurator(pdu)
        configurator.restore_base_config(self.state.backup_config)
        super().destroy()

    def ues_additional_infos(self, snssai: List[SubSnssai]):
        """
        Args:
            snssai: List of slices associated to a user

        Returns: List of pairs slice, dnn

        """
        addiotional_infos: List[ProvisionedDataInfo] = []
        for _slice in snssai:
            tmp_slice = self.get_slice(_slice.sliceId)
            for dnn in tmp_slice.dnnList:
                tmp_dnn = self.get_dnn(dnn)
                add_info: ProvisionedDataInfo = ProvisionedDataInfo(
                    slice=tmp_slice,
                    dnn=tmp_dnn
                )
                addiotional_infos.append(add_info)
        return addiotional_infos

    def add_ues(self, subscriber_model: Core5GAddSubscriberModel):
        pdu = self.provider.find_pdu(self.state.current_config.areas[0].id, PduType.CORE5G, 'AthonetCore')
        configurator = self.provider.get_pdu_configurator(pdu)
        addiotional_infos = self.ues_additional_infos(subscriber_model.snssai)
        super().add_ues(subscriber_model)
        configurator.add_user(subscriber_model, addiotional_infos)

    def del_ues(self, subscriber_model: Core5GDelSubscriberModel):
        pdu = self.provider.find_pdu(self.state.current_config.areas[0].id, PduType.CORE5G, 'AthonetCore')
        configurator = self.provider.get_pdu_configurator(pdu)
        configurator.del_user(f"imsi-{subscriber_model.imsi}")
        super().del_ues(subscriber_model)

    def add_slice(self, add_slice_model: Core5GAddSliceModel, oss: bool):
        super().add_slice(add_slice_model, oss)
        pdu = self.provider.find_pdu(self.state.current_config.areas[0].id, PduType.CORE5G, 'AthonetCore')
        configurator = self.provider.get_pdu_configurator(pdu)
        configurator.configure(self.state.current_config)

    def del_slice(self, del_slice_model: Core5GDelSliceModel):
        super().del_slice(del_slice_model)
        pdu = self.provider.find_pdu(self.state.current_config.areas[0].id, PduType.CORE5G, 'AthonetCore')
        configurator = self.provider.get_pdu_configurator(pdu)
        configurator.configure(self.state.current_config)

    def update_core(self):
        pdu = self.provider.find_pdu(self.state.current_config.areas[0].id, PduType.CORE5G, 'AthonetCore')
        configurator = self.provider.get_pdu_configurator(pdu)
        configurator.configure(self.state.current_config)

    def get_amf_ip(self) -> str:
        pdu = self.provider.find_pdu(self.state.current_config.areas[0].id, PduType.CORE5G, 'AthonetCore')
        configurator = self.provider.get_pdu_configurator(pdu)
        return configurator.get_amf_ip()

    def del_dnn(self, del_dnn_model: Core5GDelDnnModel):
        super().del_dnn(del_dnn_model)
        pdu = self.provider.find_pdu(self.state.current_config.areas[0].id, PduType.CORE5G, 'AthonetCore')
        configurator = self.provider.get_pdu_configurator(pdu)
        configurator.configure(self.state.current_config)
        self.update_edge_areas()

    def add_dnn(self, dnn_model: Core5GAddDnnModel):
        super().add_dnn(dnn_model)
        pdu = self.provider.find_pdu(self.state.current_config.areas[0].id, PduType.CORE5G, 'AthonetCore')
        configurator = self.provider.get_pdu_configurator(pdu)
        configurator.configure(self.state.current_config)
        self.update_edge_areas()

    def get_nrf_ip(self) -> str:
        pass

    def wait_core_ready(self):
        pass

    def get_slice(self, slice_id: str) -> SubSliceProfiles:
        """
        Get SubSliceProfiles with specified slice_id from conf.
        Args:
            slice_id: slice id of the slice to retrieve.

        Returns: the slice with specified slice_id.

        """
        for _slice in self.state.current_config.config.sliceProfiles:
            if _slice.sliceId == slice_id:
                return _slice
        raise ValueError(f'Slice {slice_id} not found.')

    def get_subscriber(self, imsi: str) -> SubSubscribers:
        """
        Get SubSubscribers with specified imsi from conf.
        Args:
            imsi: imsi of the subscriber to retrieve.

        Returns: the subscriber with specified imsi.

        """
        for _subscriber in self.state.current_config.config.subscribers:
            if _subscriber.imsi == imsi:
                return _subscriber
        raise ValueError(f'Subscriber with imsi: {imsi} not found.')

    def get_area(self, area_id: int) -> SubArea:
        """
        Get SubArea with specified area_id from conf.
        Args:
            area_id: area id of the area to retrieve.

        Returns: the area with specified area id.

        """
        for area in self.state.current_config.areas:
            if area_id == area.id:
                return area
        raise ValueError(f'Area {area_id} not found.')

    def get_area_from_sliceid(self, sliceid: str) -> SubArea:
        """
        Get SubArea from conf, that contains the slice with specified sliceid.
        Args:
            sliceid: slice id of the slice.

        Returns: the area with specified slice.

        """
        for area in self.state.current_config.areas:
            for _slice in area.slices:
                if _slice.sliceId == sliceid:
                    return area
        raise ValueError(f'Area of slice {sliceid} not found.')

    def get_dnn(self, dnn_name: str) -> SubDataNets:
        """
        Get SubDataNets with specified dnn_name from conf.
        Args:
            dnn_name: dnn name of the dnn to retrieve.

        Returns: the dnn with specified dnn name.

        """
        for dnn in self.state.current_config.config.network_endpoints.data_nets:
            if dnn_name == dnn.dnn:
                return dnn
        raise ValueError(f'Dnn {dnn_name} not found.')
