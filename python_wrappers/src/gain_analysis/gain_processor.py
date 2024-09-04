#!/home/daqtest/anaconda3/bin python

import numpy as np
import matplotlib.pyplot as plt
import sys
import os

import json
import pandas as pd
import csv

sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import sandpro

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
# from data_processing.run_info import RunInfo
import data_processing.run_info as run_info
import data_processing.event_processor as event_processor
import fit_spe as FitSPE
import common.d2d as d2d
import common.utils as util
import common.config_reader as common_config_reader
from common.logger import setup_logger

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

class GainProcessor:
    def __init__(self):
        
        self.common_cfg_reader = common_config_reader.ConfigurationReader()
        self.config = self.common_cfg_reader.get_data_processing_config()
        
        self.run_list_path = self.config.get('RUN_PROCESSOR_SETTINGS', 'run_list_output')
        self.output_file_path = self.config.get('GAIN_PROCESSOR_SETTINGS', 'gain_list_output')
        
        self.hist_n_bins = int(self.config.get('GAIN_PROCESSOR_SETTINGS', 'hist_n_bins'))
        
        tmp = self.config.get("GAIN_PROCESSOR_SETTINGS", "hist_range")
        tmp = tmp.split(' ')
        self.hist_range = (float(tmp[0]),float(tmp[1]))
        
        self.info = run_info.RunInfo()
    
    def read_run_list(self, run_list_path: str) -> d2d.data:
        
        if os.path.isfile(run_list_path) and run_list_path.endswith('.csv'):
            df = pd.read_csv(run_list_path, 
                        parse_dates=["date_time"], 
                        delimiter=",",
                        quotechar='"', 
                        skipinitialspace=True, 
                        encoding="utf-8")
            all_runs = d2d.data(df)
            
        else:
            raise(f"Wrong path for run_list: {run_list_path}")
        
        return all_runs
    
    def data_selection_cuts_4_gain_analysis(self, all_runs: d2d.data, 
                                            from_date = np.datetime64('2024-05-18')) -> d2d.data:
        """
        Apply the cuts and return the d2d.data after cuts

        Args:
            all_runs (d2d.data): data from all runs in df/dict format

        Returns:
            d2d.data: data from all runs in df/dict format after cuts
        """
        # data selection cuts
        mask_run_tag = util.vec_regex_search('GXe/gain_calibration', all_runs.run_tag)
        mask_run_tag_remove_trash = ~util.vec_regex_search('trash', all_runs.run_tag)
        mask_time = (all_runs.date_time > from_date)
        mask_start_index_nan = ~np.isnan(all_runs.start_index)
        mask_nevents_nan = ~np.isnan(all_runs.number_of_events)
        mask_record_length_nan = ~np.isnan(all_runs.record_length_sample)
        
        mask = mask_run_tag & mask_run_tag_remove_trash & mask_time & mask_record_length_nan & mask_start_index_nan & mask_nevents_nan
        
        all_runs.apply_mask(mask, inplace=True, dry = False)
        
        return all_runs
    
    def process_single_run(self, single_run: d2d.data):
        
        tmp_info = run_info.RunInfo()
        tmp_info.bin_full_path = str(single_run.bin_full_path)
        tmp_info.number_of_events = int(single_run.number_of_events)
        tmp_info.record_length_sample = int(single_run.record_length_sample)
        
        voltage_preamp1_V = float(single_run.voltage_preamp1_V)
        
        logger.info(f"Processing file: {tmp_info.bin_full_path}")
        
        processed_events = event_processor.EventProcessor(run_info=tmp_info)
        
        
        if processed_events.failure_flag == True:
            gain = np.nan
            gain_err = np.nan
        else:
            areas = processed_events.areas
            hist_count,bin_edges = np.histogram(areas,bins=self.hist_n_bins,range=self.hist_range)

            # voltage_preamp1_V helps to predetermine the peak distance
            spe_fit = FitSPE.FitSPE(voltage_preamp1_V, 
                                    hist_count, 
                                    bin_edges, 
                                    show_plot=False, 
                                    save_plot=False)
            
            # fig, ax = plt.subplots()
            # ax.plot(bin_edges[:-1],hist_count)
            # ax.scatter(spe_fit.PE_rough_position,spe_fit.PE_rough_amplitude)
            # for i in spe_fit.mu_list:
            #     ax.axvline(i,c = "tab:green")
            
            if not (np.isnan(spe_fit.gain) or np.isnan(spe_fit.gain_error)):
                gain = spe_fit.gain
                gain_err = spe_fit.gain_error

            else:
                gain = np.nan
                gain_err = np.nan
                
                logger.warning(f"Cannot fit for file: {tmp_info.bin_full_path}")
                
            # plt.savefig("./test.png")
            # input("Press Enter to continue...")
            
        return gain, gain_err
    
    def process_runs(self):
        
        all_runs_d2d = self.read_run_list(self.run_list_path)
        all_runs_d2d = self.data_selection_cuts_4_gain_analysis(all_runs_d2d)
        
        gain_list = []
        gain_err_list = []
        
        for i in range(len(all_runs_d2d)):
            single_run = all_runs_d2d[i]
            gain, gain_err = self.process_single_run(single_run)
        
            gain_list.append(gain)
            gain_err_list.append(gain_err)

        all_runs_d2d.__setattr__("gain", np.array(gain_list))
        all_runs_d2d.__setattr__("gain_err", np.array(gain_err_list))
        
        new_df = all_runs_d2d.get_df()
        new_df.to_csv(f"{self.output_file_path}", index=False, quoting=csv.QUOTE_NONNUMERIC)
        
        return
    
if __name__ == "__main__":
    processor = GainProcessor()
    processor.process_runs()