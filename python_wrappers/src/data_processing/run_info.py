from dataclasses import dataclass
import pandas as pd
import numpy as np

@dataclass
class RunInfo:
    
    def __init__(self):
        '''
        Dataclass to store the information of a single data file for run_processor.py.
        All attributes in this class corresponse to the columns of the output csv file
        If the number of columns is changed, run_processor.py will reprocess all runs 
        that were being processed.
        '''
        self.bin_full_path: str = ""
        self.md_full_path: str = ""
        
        self.date_time: pd.Timestamp = np.nan
        # run_tag: list = field(default_factory=list)
        self.run_tag: str = ""
        self.comment: str = ""
        
        self.n_channels: int = np.nan
        self.channel: int = np.nan
        self.board: int = np.nan
        self.threshold_adc: int = np.nan

        self.runtime_s: float = np.nan
        self.voltage_preamp1_V: float = np.nan
        self.temperature_K: float = np.nan
        
        self.number_of_events: int = np.nan
        self.n_processed_events: int = np.nan
        self.start_index: int = np.nan
        
        self.record_length_sample: int = np.nan
        self.baseline_n_samples: int = np.nan
        self.baseline_n_samples_avg: int = np.nan
        self.baseline_std: float = np.nan
        self.baseline_mean: float = np.nan
        
        # run_id is assigned after processing all data and sorted by date_time
        # see run_processor.process_runs()
        self.run_id: int = np.nan 
      
    def set_run_info_from_dict(self, run_info: dict):
        for column in run_info.keys():
            self.__dict__[column] = run_info[column]
        return
