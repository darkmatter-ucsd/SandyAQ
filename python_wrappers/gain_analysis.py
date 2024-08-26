#!/home/daqtest/anaconda3/bin python

import numpy as np
import matplotlib.pyplot as plt
import sys
import os
sys.path.insert(0,"/home/daqtest/Processor/sandpro")
import sandpro
import json
import pandas as pd
import re
import csv

sys.path.insert(0,"../")
from dataclasses import dataclass
import WaveformProcessor
import FitSPE

@dataclass
class run_info_data:
    def __init__(self, input: object):
        self.import_data(input)
    
    def import_data(self, df: pd.DataFrame):
        for col_name in df.columns:
            setattr(self, col_name, df[col_name].to_numpy())
            
    def import_data(self, dictionary: dict):
        for var_name in dictionary.keys():
            setattr(self, var_name, np.array(dictionary[var_name]))
            
    def apply_mask(self, mask, inplace = False):
        print("before cut: ", len(self.__dict__['file_path']))
        new_dict = {}
        for i in self.__dict__.keys():
            if inplace:
                self.__dict__[i] = self.__dict__[i][mask]
            else:
                new_dict[i] = self.__dict__[i][mask]
        
        if inplace:   
            first = next(iter(self.__dict__.values()))
            print("after cut: ", len(first))
            return
        else:
            first = next(iter(new_dict.values()))
            print("after cut: ", len(first))
            return run_info_data(new_dict)
        
    def get_df(self):
        df = pd.DataFrame(self.__dict__,index=None)
        return df
    
    def __len__(self):
        # the length of all array should be the same
        # so just picked a random one
        first = next(iter(self.__dict__.values()))
        return len(first)
            
def _re_search(pattern: str, string):
    if pd.isnull(string):
        return False #does not match
    else:
        return bool(re.search(pattern, string))
v_re_search = np.vectorize(_re_search, excluded=["pattern"])


def main(output_name = "./gain_analysis.csv"):
    df = pd.read_csv("/home/daqtest/DAQ/SandyAQ_vera/SandyAQ/python_wrappers/run_info_single_channel.csv", 
                     parse_dates=["date_time"], 
                     delimiter=",",
                     quotechar='"', 
                     skipinitialspace=True, 
                     encoding="utf-8")
    
    # data selection cuts
    info = run_info_data(df)

    mask_record_length_nan = ~np.isnan(info.record_length_sample)
    mask_run_tag = v_re_search('GXe/gain_calibration', info.run_tag)
    mask_run_tag_remove_trash = ~v_re_search('trash', info.run_tag)
    mask_time = (info.date_time > np.datetime64('2024-05-18'))
    mask_start_index_nan = ~np.isnan(info.start_index)
    mask_nevents_nan = ~np.isnan(info.number_of_events)
    
    mask = mask_run_tag & mask_run_tag_remove_trash & mask_time & mask_record_length_nan & mask_start_index_nan & mask_nevents_nan
    info.apply_mask(mask, inplace=True)
    
    # FIXME
    nchs = 1
    record_length_sample = 1000
    sample_selection = 120
    samples_to_average = 40

    integral_window = (0.3,0.6)

    gain_list = []
    gain_err_list = []

    mask =  (info.number_of_channels == nchs) & (info.record_length_sample == record_length_sample) & (info.baseline_n_samples == sample_selection) & (info.baseline_n_samples_avg == samples_to_average)
    # check how much data is removed
    info.apply_mask(mask, inplace=True)
    
    # new_info = info.apply_mask(mask)

    process_config = {"nchs": int(nchs),
                    "nsamps": int(record_length_sample),
                    "sample_selection": int(sample_selection),
                    "samples_to_average": int(samples_to_average)}

    # dump the config to a json file
    with open("process_config.json", "w") as f:
        json.dump(process_config, f, indent=4)  
        
    processor= sandpro.processing.rawdata.RawData(config_file = "process_config.json",
                                                perchannel=False)

    for i in range(len(info)):
        start_index = int(info.start_index[i])
        end_index = int(info.start_index[i] + info.n_processed_events[i])
        
        data = processor.get_rawdata_numpy(n_evts=int(info.number_of_events[i])-1,
                                file=info.file_path[i],
                                bit_of_daq=14,
                                headersize=4,inversion=False)
        
        wfp = WaveformProcessor.WFProcessor(os.path.dirname(info.file_path[i]), 
                                            volt_per_adc=2/2**14)
        wfp.set_data(data["data_per_channel"][start_index:end_index,0], in_adc = False)
        wfp.process_wfs()
        
        areas = wfp.get_area(sum_window=integral_window)
        heights = wfp.get_height(search_window=integral_window)

        data_processed = data["data_per_channel"][start_index:end_index,0,:]
        hist_count,bin_edges = np.histogram(areas,bins=200,range=(-0.1,10))

        # voltage_preamp1_V helps to predetermine the peak distance
        spe_fit = FitSPE.FitSPE(info.voltage_preamp1_V[i], hist_count, bin_edges, show_plot=False, save_plot=False)
        
        if not (np.isnan(spe_fit.gain) or np.isnan(spe_fit.gain_error)):
            gain_list.append(spe_fit.gain)
            gain_err_list.append(spe_fit.gain_error)
        else:
            gain_list.append(np.nan)
            gain_err_list.append(np.nan)
        
    info.__setattr__("gain", np.array(gain_list))
    info.__setattr__("gain_err", np.array(gain_err_list))
    
    new_df = info.get_df()
    new_df.to_csv(f"{output_name}", index=False, quoting=csv.QUOTE_NONNUMERIC)
    
if __name__ == "__main__":
    main()
