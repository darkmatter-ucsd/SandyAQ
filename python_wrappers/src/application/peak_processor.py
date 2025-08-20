import numpy as np
import sys
import glob
import os
sys.path.insert(0,"/home/ws/sk6801/sw/UCSD_analysis/sandpro")
import sandpro
import configparser
import json
import scipy.stats
from scipy.optimize import curve_fit
import datetime
import pandas as pd
import re
from matplotlib.pyplot import cm
import matplotlib as mpl
from dataclasses import dataclass
# from sklearn.linear_model import LinearRegression
# import statsmodels.api as sm
from matplotlib.lines import Line2D


sys.path.insert(0,"../src/")
import common.utils as util
import common.d2d as d2d
# import common.run_info as run_info
import data_structure.run_info as run_info

import json
import pandas as pd
import csv

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
from data_structure.peak_info import PeakInfo
import common.d2d as d2d
import common.utils as util
import common.config_reader as common_config_reader
from common.logger import setup_logger
from data_processing.event_processor_all_channel import EventProcessor

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

class PeakProcessor:
    def __init__(self, input_path):
        
        self.common_cfg_reader = common_config_reader.ConfigurationReader()

        # set the paths
        self.path_config = self.common_cfg_reader.get_absolute_path_config()
        self.input_file_path = self.path_config.get('PEAK_ANALYSIS', 'peak_list_input_file')
        self.output_file_path = self.path_config.get('PEAK_ANALYSIS', 'peak_list_output_file')
        # self.config = self.common_cfg_reader.get_data_processing_config()

        self.input_file_path = input_path
        
        self.single_info = PeakInfo()

    def data_selection(self, all_runs: d2d.data) -> d2d.data:
        """
        Apply the cuts and return the d2d.data after cuts

        Args:
            all_runs (d2d.data): data from all runs in df/dict format

        Returns:
            d2d.data: data from all runs in df/dict format after cuts
        """
        # data selection cuts
        mask_data_taking_mode = (all_runs.data_taking_mode == "all_channels")
        mask_gain_nan = ~np.isnan(all_runs.gain)
        mask = mask_data_taking_mode & mask_gain_nan
        
        all_runs.apply_mask(mask, inplace=True, dry = False)
        
        return all_runs
    
    def process_single_run(self):
        """
        Process a single run and extract peak information.

        Args:
            single_info (PeakInfo): Information about the run to be processed.
        """
        # determine threshold 
        # peak fit

        self.event_processor = EventProcessor(self.single_info)

        for rel_channel in range(self.single_info.n_channels):
            self.waveform_processor = self.event_processor.get_waveform_processor(rel_channel)
            self.waveform_processor.calculate_peak_info()

    
    def process_all_runs(self):

        self.df = pd.read_csv(self.input_file_path, 
                 parse_dates=["date_time"],
                 delimiter=",",
                 quotechar='"', 
                 skipinitialspace=True, 
                 encoding="utf-8")
        
        all_runs_d2d = d2d.data(self.df)
        all_runs_d2d = self.data_selection(all_runs_d2d)
        
        for row in range(len(all_runs_d2d)):
            tmp = all_runs_d2d.get_row_info(row)
            self.single_info.set_info_from_dict(tmp.__dict__)
            logger.info(f"Processing file: {self.info.bin_full_path}")

            self.process_single_run()







        





        

