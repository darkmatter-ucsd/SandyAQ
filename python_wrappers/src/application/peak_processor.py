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
import common.config_reader as common_config_reader
import data_processing.fast_processor_all_channel as fast_processor
from data_processing.event_processor_all_channel import EventProcessor
from common.logger import setup_logger
logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

from data_structure.waveform_info import WaveformInfo
from data_structure.peak_info import PeakInfo


class Peak_Processor:
    def __init__(self):
        self.common_cfg_reader = common_config_reader.ConfigurationReader()
        self.path_config = self.common_cfg_reader.get_absolute_path_config()
        self.peak_list_input_file = self.path_config.get('PEAK_ANALYSIS', 'peak_list_input_file')
        self.average_SPE_input_file = self.path_config.get('PEAK_ANALYSIS', 'average_SPE_input_file')
        self.peak_list_output_dirname = self.path_config.get('PEAK_ANALYSIS', 'peak_list_output_dirname')

    def get_baseline_for_all_events(self, waveform, baseline_front=(0.0,0.2)):
        baseline_start_f = int(1000 * baseline_front[0])
        baseline_end_f = int(1000 * baseline_front[1])

        # baseline is calculated with raw waveform
        # unit: same as raw waveform
        baseline_mean_V = np.mean(waveform[:,baseline_start_f:baseline_end_f], axis=1)
        baseline_std_V = np.std(waveform[:,baseline_start_f:baseline_end_f], axis=1)

        return baseline_mean_V, baseline_std_V

    def get_board_channel(self, SiPM_channel: int, board_0_channels: np.array, board_1_channels: np.array) -> int:
        if SiPM_channel in board_0_channels: 
            board_channel = np.where(board_0_channels == SiPM_channel)[0]
        elif SiPM_channel in board_1_channels:  
            board_channel = np.where(board_1_channels == SiPM_channel)[0]
        else:
            raise ValueError(f"SiPM channel {SiPM_channel} not found in both boards.")

        return board_channel[0]


    def set_peak_info_from_waveform_info(self, waveform_info: WaveformInfo):
        peak_info = PeakInfo()
        peak_info.set_info_from_dict(waveform_info.__dict__)

        # PeakInfo_df = pd.DataFrame(columns=peak_info.__dict__.keys())
        peak_info_list = []

        if waveform_info.n_peaks == 0:
            # return PeakInfo_df
            return peak_info_list

        for peak_id in range(int(waveform_info.n_peaks)):
            peak_info.peak_id = peak_id
            peak_info.peak_start_time_s = waveform_info.peak_start_time_s_array[peak_id]
            peak_info.peak_end_time_s = waveform_info.peak_end_time_s_array[peak_id]
            peak_info.peak_rel_start_time_s = waveform_info.peak_rel_start_time_s_array[peak_id]
            peak_info.peak_height_V = waveform_info.peak_height_V_array[peak_id]
            peak_info.peak_width_ns = waveform_info.peak_width_ns_array[peak_id]
            peak_info.peak_area_Vns = waveform_info.peak_area_Vns_array[peak_id]
            peak_info.peak_area_PE = waveform_info.peak_area_PE_array[peak_id]

            tmp  = deepcopy(peak_info.__dict__)
            # PeakInfo_df = PeakInfo_df.append(tmp, ignore_index=True)
            # peak_info_list.append(tmp)
            # peak_info_list += [pd.DataFrame(tmp, index = [0])]
            peak_info_list += [tmp]


        return peak_info_list


    def get_peak_level_data(self, 
            all_runs_d2d: d2d.data,
            md_full_path: str,
            peak_merge_window_sample: int):

        single_info = WaveformInfo()

        peak_info = PeakInfo()
        peak_info_all = []
        # peak_info_all = pd.DataFrame(columns=peak_info.__dict__.keys())
        
        mask = all_runs_d2d.md_full_path == md_full_path
        single_run = all_runs_d2d.apply_mask(mask, inplace=False, dry = False)

        assert len(single_run.channel) == 24, f"Run {md_full_path} has {len(single_run.channel)} channels, expected 24 channels."
        
        t1,t2,t3, t4 = 0, 0, 0, 0

        for board_id in np.unique(single_run.board):
            
            mask = single_run.board == board_id
            single_board = single_run.apply_mask(mask, inplace=False, dry = True)

            board_info = WaveformInfo()
            board_info.set_info_from_dict(single_board.get_common_info_dict())
            board_info.board_0_channels = np.array(json.loads(board_info.board_0_channels))
            board_info.board_1_channels = np.array(json.loads(board_info.board_1_channels))

            # convert string to array
            if isinstance(board_info.board_0_channels[0], str):
                board_info.board_0_channels = board_info.board_0_channels.apply(json.loads).apply(np.array)
            if isinstance(board_info.board_1_channels[0], str):
                board_info.board_1_channels = board_info.board_1_channels.apply(json.loads).apply(np.array)

            if isinstance(board_info.board_0_channels[0], str):
                if "," in board_info.board_0_channels[0]:
                    board_info.board_0_channels = board_info.board_0_channels.apply(json.loads).apply(np.array)
                else:
                    board_info.board_0_channels = board_info.board_0_channels.apply(lambda x: x.replace("  ", ","))
                    board_info.board_0_channels = board_info.board_0_channels.apply(lambda x: x.replace("[ ", "["))
                    board_info.board_0_channels = board_info.board_0_channels.apply(lambda x: x.replace(" ", ","))
                    board_info.board_0_channels = board_info.board_0_channels.apply(json.loads).apply(np.array)

                    board_info.board_1_channels = board_info.board_1_channels.apply(lambda x: x.replace("  ", ","))
                    board_info.board_1_channels = board_info.board_1_channels.apply(lambda x: x.replace("[ ", "["))
                    board_info.board_1_channels = board_info.board_1_channels.apply(lambda x: x.replace(" ", ","))
                    board_info.board_1_channels = board_info.board_1_channels.apply(json.loads).apply(np.array)
                    

            # single_info.set_info_from_dict(board_info)
            event_processor = EventProcessor(board_info)
            
            if board_id == 0:
                channel_list = board_info.board_0_channels
            else:
                channel_list = board_info.board_1_channels


            for channel_id in range(len(channel_list)):
                mask = (single_run.board == board_id) & (single_run.channel == channel_list[channel_id])
                single_channel = single_run.apply_mask(mask, inplace=False, dry = True)
                
                assert len(single_channel.channel) == 1, f"Channel {channel_id} in board {board_id} has {len(single_channel.channel)} channels, expected 1 channel."
                
                single_info.set_info_from_dict(single_channel.get_dict())
                board_channel = self.get_board_channel(channel_id, board_info.board_0_channels, board_info.board_1_channels)

                waveform_processor = event_processor.get_waveform_processor(board_channel)
                waveform = waveform_processor.filtered_wfs

                baseline, baseline_std = self.get_baseline_for_all_events(waveform)

                # print(f"Processing board {single_info.board}, channel {single_info.channel} in run {single_info.md_full_path}")

                for event_id in range(waveform.shape[0]):
                    single_waveform = waveform[event_id,:]
                    single_baseline, single_baseline_std = baseline[event_id], baseline_std[event_id]

                    single_info.event_start_time_s = waveform_processor.event_time_s[event_id]
                    single_info.event_id = event_id
                    # print(f"Processing event {single_info.event_id} in run {single_info.md_full_path}, board {single_info.board}, channel {single_info.channel}")

                    t0 = time.perf_counter()
                    single_info.set_peaks_for_single_processed_waveform(
                        single_waveform, 
                        single_baseline, 
                        single_baseline_std,
                        threshold_sig=3, 
                        peak_merge_window_sample=peak_merge_window_sample
                        # event_id=event_id
                    )
                    t1 += time.perf_counter() - t0              

                    t0 = time.perf_counter()
                    # peak_info_list = set_peak_info_from_waveform_info(single_info)
                    t2 += time.perf_counter() - t0              

                    t0 = time.perf_counter()
                    peak_info_all += self.set_peak_info_from_waveform_info(single_info)
                    t3 += time.perf_counter() - t0

        print(f'Time taken: {t1:.6f} seconds for peak finding, '
            f'{t2:.6f} seconds for peak info setting, '
            f'{t3:.6f} seconds for appending peak info list')

        return (peak_info_all, waveform, baseline, baseline_std)


    def get_waveform_from_single_info(self, single_info):
        
        # assert len(single_info.channel) == 1, f"Expected 1 channel."
        event_processor = EventProcessor(single_info)
                
        board_channel = self.get_board_channel(single_info.channel, single_info.board_0_channels, single_info.board_1_channels)

        waveform_processor = event_processor.get_waveform_processor(board_channel)
        waveform = waveform_processor.filtered_wfs
        baseline, baseline_std = self.get_baseline_for_all_events(waveform)

        return (waveform, baseline, baseline_std)


def main(input_run_tag = "LXe/gain_calibration", input_voltage=-47):
    """
    Main function to process the peak level data and save it to a DataFrame.
    
    Args:
        run_tag (str): The run tag to filter the runs.
    
    Returns:
        pd.DataFrame: DataFrame containing the peak information.
    """

    # check parameters
    if not isinstance(input_run_tag, str):
        raise ValueError("run_tag must be a string.")
    if input_run_tag not in ["LXe/gain_calibration", "LXe/Cs137", "LXe/Co57",  "LXe/tritium"]:
        raise ValueError("run_tag must be one of ['LXe/gain_calibration', 'LXe/Cs137', 'LXe/Co57', 'LXe/tritium'].")
    if not isinstance(input_voltage, (int, float)):
        raise ValueError("voltage must be an integer or a float.")
    if input_voltage > 0 or input_voltage < -60:
        raise ValueError("voltage must be between -60 and 0.")
    
    peak_processor = Peak_Processor()

    
    df_SPE_position = pd.read_csv(
        peak_processor.average_SPE_input_file,
        delimiter=",")


    df = pd.read_csv(
        peak_processor.peak_list_input_file, 
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
    print(len(idx_nan))
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
    mask_na = ~np.isnan(all_runs_d2d.spe_position)
    # mask = ~np.isnan(all_runs_d2d.gain)
    if input_voltage == -1:
        mask_voltage = (all_runs_d2d.voltage_preamp1_V <= -46)
    else:
        mask_voltage = (all_runs_d2d.voltage_preamp1_V == input_voltage)
    mask_run_tag = (all_runs_d2d.run_tag == input_run_tag)
    mask = mask_data_taking_mode & mask_na & mask_run_tag & mask_voltage

    all_runs_d2d.apply_mask(mask, inplace=True, dry = False)
    all_run_list = np.unique(all_runs_d2d.md_full_path)

    count_n_events = 0

    if len(all_run_list) >= 100:
        logger.info(f"Found {len(all_run_list)} runs. Processing only from 0-99 runs.")
        all_run_list = all_run_list[:100]

    for i, md_full_path in enumerate(all_run_list):

        mask = all_runs_d2d.md_full_path == md_full_path
        single_run = all_runs_d2d.apply_mask(mask, inplace=False, dry = True)

        if len(single_run.channel) < 24:

            continue    
        elif len(single_run.channel) == 24:
            logger.info(f"Run {i}: {md_full_path} has 24 channels. Run tag: {single_run.run_tag[0]}. Voltage: {single_run.voltage_preamp1_V[0]}. Comment: {single_run.comment[0]}. Event number: {single_run.n_processed_events[0]}")
            count_n_events += single_run.n_processed_events[0]
            
        else: 
            raise ValueError(f"Run {md_full_path} has {len(single_run.channel)} channels, expected 24 channels.")

    logger.info(f"Total number of events: {count_n_events}")

    peak_info_all = pd.DataFrame(columns=PeakInfo().__dict__.keys())

    if input_voltage == -1:
        output_basename = input_run_tag.split("/")[1] + f"_voltage_all_peak_info.csv"
    else:
        output_basename = input_run_tag.split("/")[1] + f"_voltage_{int(abs(input_voltage))}_peak_info.csv"
    output_dirname = peak_processor.peak_list_output_dirname
    output_fname = os.path.join(output_dirname, output_basename)

    output_fname = util.get_new_filename(output_fname) ## in case the file already exists, create a new name
    logger.info(f"Output file: {output_fname}")
    peak_info_all.to_csv(output_fname, mode='w', index=False, header=True)

    for md_full_path in all_run_list:
        result, _, _, _ = peak_processor.get_peak_level_data(
            all_runs_d2d=all_runs_d2d,
            md_full_path=md_full_path,
            peak_merge_window_sample=250
        )

        # append to csv

        peak_info_all = pd.DataFrame.from_dict(result)
        peak_info_all.to_csv(output_fname, mode='a', index=False, header=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process peak level data.")
    parser.add_argument('--run_tag', type=str, default="LXe/gain_calibration", help='Run tag to filter the runs.')
    parser.add_argument('--voltage', type=float, default=-47, help='Voltage to filter the runs. If input voltage = -1, then mask <=-46')

    args = parser.parse_args()

    main(input_run_tag=args.run_tag, input_voltage=args.voltage)