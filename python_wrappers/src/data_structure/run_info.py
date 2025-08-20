from dataclasses import dataclass
import pandas as pd
import numpy as np
from typing import Union, List
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"./"))

@dataclass
class RunInfo:
    
    def __init__(self):
        '''
        Dataclass to store the information of a single data file for run_processor.py.
        All attributes in this class corresponse to the columns of the output csv/hdf5 file
        If the number of columns is changed, run_processor.py will reprocess all runs 
        that were being processed.
        
        For other classes inheriting this class can add more attributes, such as fast_processor
        or metadata_handler
        '''
        self.bin_full_path: Union[str, List[str]] = ""
        self.md_full_path: str = ""
        
        # from metadata
        self.date_time: pd.Timestamp = np.nan
        self.date_time_str: str = "" # for file regex
        self.comment: str = ""
        self.run_tag: str = ""
        self.runtime_s: float = np.nan # time during data taking in seconds
        self.voltage_preamp1_V: float = np.nan # voltage of preamp1 in Volts
        self.temperature_K: float = np.nan # temperature of the detector in Kelvin
        self.data_taking_mode: str = ""
        self.channel_list: int = np.nan # channel list of the SiPM (in case some are disabled or excluded)
        self.board_0_channels: int = np.nan # DAQ channels on board 0
        self.board_1_channels: int = np.nan # DAQ channels on board 1

        # datataking config from the metadata
        self.number_of_events: int = np.nan # number of events in the run (shared by all channels on the board)
        self.post_trigger: float = np.nan # in percentage of the record length
        self.DC_OFFSET: float = np.nan 
        self.record_length_sample: int = np.nan

        # board level info
        self.board: int = np.nan  # which board the data was taken from, 0 or 1
        self.n_channels: int = np.nan # number of channels on the board
        
        # channel level info / settings
        self.channel: int = np.nan # SiPM channel number, 0-15 (later should have also a DAQ channel number)
        self.threshold_adc: int = np.nan # triggering threshold in ADC counts (FIXME: perhaps also use for peak finding)
        self.n_processed_events: int = np.nan # number of processed events in the run (shared by all channels on the board)
        self.start_index: int = np.nan # (not very useful, the starting index of events to be processed, remove noisy events in the beginning (shared by all channels on the board)
        self.baseline_n_samples: int = np.nan
        self.baseline_n_samples_avg: int = np.nan

        # result of channel level event processing
        self.baseline_std_V: float = np.nan
        self.baseline_mean_V: float = np.nan
        self.area_hist_count_Vns: float = np.nan
        self.area_bin_edges_Vns: float = np.nan
        
        self.run_id: int = np.nan

      
    def set_info_from_dict(self, info: dict):
        for column in self.__dict__.keys():
            if column in info:
                # convert pd.Series to numpy array if needed
                if isinstance(info[column], pd.Series):
                    info[column] = info[column].to_numpy()

                # convert list to numpy array if needed
                if isinstance(info[column], list):
                    info[column] = np.array(info[column])
            
                # if the attribute is a numpy array and has only one element, convert it to a scalar
                if isinstance(info[column], np.ndarray):
                    if len(info[column]) == 1:
                        self.__dict__[column] = info[column][0]
                        continue
                    else:
                        self.__dict__[column] = info[column]
                else:
                    self.__dict__[column] = info[column]

        return