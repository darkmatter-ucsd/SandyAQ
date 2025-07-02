import numpy as np
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"./"))
# from event_info import EventInfo
from run_info import RunInfo

class ProcessInfo(RunInfo):
    '''    
    Class to store the intermidate information to process single run single channel.
    More attributes can be added to this class, that is needed for the processing but not needed for the output.

    '''
    def __init__(self):

        super().__init__()

        # event level information
        self.event_id: int = np.nan
        self.event_start_time_s: float = np.nan # seconds since data taking

        self.baseline_n_samples: int = np.nan
        self.baseline_n_samples_avg: int = np.nan
        self.baseline_std_V: float = np.nan
        self.baseline_mean_V: float = np.nan
        
        self.area_hist_count_Vns: float = np.nan
        self.area_bin_edges_Vns: float = np.nan

        # waveform level information
        self.integral_window_area_unit: float = np.nan
        self.integral_window_height_unit: float = np.nan
        self.baseline_unit: float = np.nan

        # peak level information
        self.peak_id_list = np.array([], dtype=int)
        self.peak_start_time_s_array = np.array([], dtype=float)  # seconds since event start time
        self.peak_end_time_s_array = np.array([], dtype=float)  # seconds since event start time
        # FIXME add units 
        self.peak_height_unit_array = np.array([], dtype=float)
        self.peak_width_unit_array = np.array([], dtype=float)
        self.peak_area_unit_array = np.array([], dtype=float)


    def set_event_info(self, event_id, event_start_time_s, integral_window_area_unit,
                       integral_window_height_unit, baseline_unit):
        self.event_id = event_id
    
    def add_peak_info(self, peak_id, start_time_s, end_time_s, height_unit, width_unit, area_unit):
        self.peak_id_array = np.append(self.peak_id_array, peak_id)
        self.peak_start_time_s_array = np.append(self.peak_start_time_s_array,
            start_time_s)
        self.peak_end_time_s_array = np.append(self.peak_end_time_s_array,
            end_time_s)
        self.peak_height_unit_array = np.append(self.peak_height_unit_array,
            height_unit)
        self.peak_width_unit_array = np.append(self.peak_width_unit_array,
            width_unit)
        self.peak_area_unit_array = np.append(self.peak_area_unit_array,
            area_unit)
