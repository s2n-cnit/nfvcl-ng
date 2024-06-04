from enum import Enum


class BlueEventType(Enum):
    BLUE_CREATE = "create"
    BLUE_DELETE = "delete"
    BLUE_START_PROCESSING = "start_processing"
    BLUE_END_PROCESSING = "end_processing"
    BLUE_START_DAY0 = "start_day0"
    BLUE_END_DAY0 = "end_day0"
    BLUE_START_DAY2 = "start_day2"
    BLUE_END_DAY2 = "end_day2"
    BLUE_START_DAYN = "start_dayN"
    BLUE_END_DAYN = "end_dayN"