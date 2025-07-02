from dataclasses import dataclass
import pandas as pd
import numpy as np
from typing import Union, List
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"./"))
# from event_info import EventInfo
import board_info as BoardInfo

@dataclass
class ChannelInfo(BoardInfo):
    
    def __init__(self, board_info: BoardInfo):

        super().__init__()
        # FIXME what happen with the input of boardinfo?

        self.set_info_from_dict(board_info.__dict__)


        # result of channel level event processing
        self.baseline_std_V: float = np.nan
        self.baseline_mean_V: float = np.nan
        self.area_hist_count_Vns: float = np.nan
        self.area_bin_edges_Vns: float = np.nan

        # self.event_info_list: List[EventInfo] = None  # List of board info strings, e.g. ['board0', 'board1']

        
      
    # def set_run_info_from_dict(self, run_info: dict):
    #     for column in self.__dict__.keys():
    #         if column in run_info:
    #             self.__dict__[column] = run_info[column]
    #     return