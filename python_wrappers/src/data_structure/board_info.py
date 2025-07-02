from dataclasses import dataclass
import pandas as pd
import numpy as np
from typing import Union, List
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"./"))
# from channel_info import ChannelInfo
import run_info as RunInfo

@dataclass
class BoardInfo(RunInfo):
    
    def __init__(self, run_info: RunInfo):

        super().__init__()

        # inherit run_info attributes
        self.set_info_from_dict(run_info.__dict__)

        self.board_id: int = np.nan
        self.board_channel_list: List[int] = None  # List of channels in the board, e.g. [0, 1, 2, 3]
        self.event_time_s_list: List[float] = None  # List of event start times in seconds since data taking
        
        # self.channel_info_list: List[ChannelInfo] = None  # List of board info strings, e.g. ['board0', 'board1']
        
    # def set_info_from_dict(self, info: dict):
    #     for column in self.__dict__.keys():
    #         if column in info:
    #             self.__dict__[column] = info[column]
    #     return
