import shutil
import numpy as np
import matplotlib.pyplot as plt
import sys
import glob
import os
sys.path.insert(0,"/home/ws/sk6801/sw/UCSD_analysis/sandpro")
import sandpro
import configparser
import json
import scipy.stats
from matplotlib.colors import LogNorm

from scipy.optimize import curve_fit
import datetime
import pandas as pd
from copy import deepcopy
from numba import jit
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
import common.d2d as d2d
import common.utils as util
from common.logger import setup_logger
import common.config_reader as common_config_reader

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

import data_processing.fast_processor_all_channel as fast_processor
from data_processing.event_processor_all_channel import EventProcessor

from data_structure.waveform_info import WaveformInfo
from data_structure.peak_info import PeakInfo

class Event_Rate:
    def __init__(self):
        self.common_cfg_reader = common_config_reader.ConfigurationReader()

        # set the paths
        self.path_config = self.common_cfg_reader.get_absolute_path_config()
        self.event_rate_input_file = self.path_config.get('EVENT_RATE_ANALYSIS', 'event_rate_input_file')
        self.average_SPE_input_file = self.path_config.get('EVENT_RATE_ANALYSIS', 'average_SPE_input_file')
        self.output_fname = self.path_config.get('EVENT_RATE_ANALYSIS', 'event_rate_output_file')

        ### all SPE position from the gain analysis (generated from the notebook) using all datasets
        df_SPE_position = pd.read_csv(self.average_SPE_input_file,
                                      delimiter=",")

        df = pd.read_csv(self.event_rate_input_file,
                        parse_dates=["date_time"],
                        delimiter=",",
                        quotechar='"', 
                        skipinitialspace=True, 
                        encoding="utf-8")


        # convert string to array
        if isinstance(df['board_0_channels'][0], str):
            if "," in df['board_0_channels'][0]:
                df['board_0_channels'] = df['board_0_channels'].apply(json.loads).apply(np.array)
            else:
                df['board_0_channels'] = df['board_0_channels'].apply(lambda x: x.replace("  ", ","))
                df['board_0_channels'] = df['board_0_channels'].apply(lambda x: x.replace("[ ", "["))
                df['board_0_channels'] = df['board_0_channels'].apply(lambda x: x.replace(" ", ","))
                df['board_0_channels'] = df['board_0_channels'].apply(json.loads).apply(np.array)

                df['board_1_channels'] = df['board_1_channels'].apply(lambda x: x.replace("  ", ","))
                df['board_1_channels'] = df['board_1_channels'].apply(lambda x: x.replace("[ ", "["))
                df['board_1_channels'] = df['board_1_channels'].apply(lambda x: x.replace(" ", ","))
                df['board_1_channels'] = df['board_1_channels'].apply(json.loads).apply(np.array)

        idx_nan = np.where((df['spe_position'].isna()) & (df['voltage_preamp1_V']<=-46))[0]
        # replace NaN values with SPE position
        voltage_array = df.loc[idx_nan, 'voltage_preamp1_V']
        channel_array = df.loc[idx_nan, 'channel']
        for idx, voltage, channel in zip(idx_nan, voltage_array, channel_array):
            # find the SPE position for the given voltage and channel
            df.loc[idx, 'spe_position'] = df_SPE_position[
                (df_SPE_position['voltage_preamp1_V'] == voltage) & 
                (df_SPE_position['channel'] == channel)
            ]['spe_position'].values
            df.loc[idx, 'spe_position_err'] = df_SPE_position[
                (df_SPE_position['voltage_preamp1_V'] == voltage) & 
                (df_SPE_position['channel'] == channel)
            ]['spe_position_err'].values


    
        #### Basic Data Selection

        all_runs_d2d = d2d.data(df)
        mask_data_taking_mode = (all_runs_d2d.data_taking_mode == "all_channels")
        # mask_path = util.vec_regex_search("10.0sig", all_runs_d2d.md_full_path)
        mask_threshold = (all_runs_d2d.threshold_adc < 4000) & (all_runs_d2d.threshold_adc > 2500)

        mask = mask_data_taking_mode  & mask_threshold
        all_runs_d2d.apply_mask(mask, inplace=True, dry = False)
        all_run_list = np.unique(all_runs_d2d.md_full_path)

        self.output_fname = util.get_new_filename(self.output_fname, use_datetime=True) ## in case the file already exists, create a new name

        logger.info(f"Output file: {self.output_fname}")

        for count, md_full_path in enumerate(all_run_list):
            logger.info(f"Processing run {md_full_path}")

            board_event_time_list = []
            
            mask = all_runs_d2d.md_full_path == md_full_path
            single_run = all_runs_d2d.apply_mask(mask, inplace=False, dry = True)

            # for board_id in np.unique(single_run.board):

            board_id = 0
            channel_id = 0

            absolute_time_list = []

            mask = single_run.board == board_id
            single_board = single_run.apply_mask(mask, inplace=False, dry = True)
            
            mean_baseline_std_V = single_board.baseline_std_V.mean()

            # get waveform information
            board_info = WaveformInfo()
            board_info.set_info_from_dict(single_board.get_common_info_dict())
            event_processor = EventProcessor(board_info)
            waveform_processor = event_processor.get_waveform_processor(0)

            tmp_start = 1 - board_info.post_trigger/100.0 - 0.1 # 0.1 is to avoid the edge effect
            integral_window = (tmp_start, tmp_start+0.25)

            # spe_position_array = single_board.spe_position[single_board.channel == channel_id]
            # if (len(spe_position_array) == 0) or (np.isnan(spe_position_array[0])):
            #     spe_position_channel0 = df_SPE_position[
            #                     (df_SPE_position['voltage_preamp1_V'] == voltage) & 
            #                     (df_SPE_position['channel'] == channel_id)
            #     ]['spe_position'].values
            # else:
            
            # check if channal 0 is in the channel list
            if 0 in single_board.channel:

                spe_position_channel0 = single_board.spe_position[single_board.channel == channel_id][0]

                integral_area_Vns_board_channel0 = waveform_processor.get_area(sum_window=integral_window)
                # noise = waveform_processor.baseline_std_V

                if pd.Timedelta(waveform_processor.event_time_s[-1], 's') > pd.Timedelta(1, 'd'):
                    continue

                for dtime in waveform_processor.event_time_s:
                    dtime_pd = pd.Timedelta(dtime, 's')

                    absolute_time = board_info.date_time + dtime_pd
                    absolute_time_list.append(absolute_time)

                # append to csv
                save_dict = {
                    "md_full_path": md_full_path,
                    "board": board_id,
                    "comment": single_run.comment[0],
                    "run_tag": single_run.run_tag[0],
                    "voltage_preamp1_V": single_run.voltage_preamp1_V[0],
                    "data_taking_mode": single_run.data_taking_mode[0],
                    "n_processed_events": single_run.n_processed_events[0],
                    "threshold_adc": single_run.threshold_adc[0],  
                    "runtime_s": board_info.runtime_s,
                    "integral_area_Vns_board_channel0": integral_area_Vns_board_channel0,
                    "integral_area_PE_board_channel0": integral_area_Vns_board_channel0/spe_position_channel0,
                    "absolute_time": absolute_time_list,
                    "mean_baseline_std_V": mean_baseline_std_V,
                }

                df_save = pd.DataFrame(save_dict)

                with open(self.output_fname, 'a') as f:
                    df_save.to_csv(f, mode='a', header=f.tell() == 0, index=False)


        dirname = os.path.dirname(self.output_fname)
        basename = os.path.basename(self.output_fname).split('.')[0]
        # copy this script to the output directory
        shutil.copy(__file__, f"{dirname}/{basename}.py")


if __name__ == "__main__":
    processor = Event_Rate()
    logger.info("Processing completed successfully.")

