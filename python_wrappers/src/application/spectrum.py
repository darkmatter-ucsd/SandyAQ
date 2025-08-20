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
import data_processing.fast_processor_all_channel as fast_processor
from data_processing.event_processor_all_channel import EventProcessor

from common.logger import setup_logger

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

from data_structure.waveform_info import WaveformInfo
from data_structure.peak_info import PeakInfo

@jit(nopython=True)
def get_sum_area_PE_in_time_window(
    peak_start_time_s: np.ndarray, 
    absolute_time: np.ndarray, 
    channel: np.ndarray, 
    board: np.ndarray, 
    peak_area_PE: np.ndarray,
    event_id: int,
    time_window_width_s: float,
    coincidence: int,
    ):
    """
    Calculate the sum of peak area for coincidental signals within a specified time window.
    
    Parameters:
    """
    counts = 0
    max_bin_edge = np.max(peak_start_time_s)
    min_bin_edge = np.min(peak_start_time_s)
    global_n_bins = int((max_bin_edge - min_bin_edge)/time_window_width_s) 

    # partition processing
    max_n_bins = 100000
    if global_n_bins > max_n_bins:
        partition_size = int(global_n_bins/max_n_bins)
        bin_size = (max_bin_edge - min_bin_edge) / partition_size
        bin_edge_array = np.arange(min_bin_edge, max_bin_edge, bin_size)
        bin_edge_array = np.append(bin_edge_array, max_bin_edge)  # ensure the last edge is included

    sum_area_PE_list = []
    rel_time = []
    abs_time = []

    for i, bin_edge_end in enumerate(bin_edge_array[1:]):
        n_bins = int((bin_edge_end - bin_edge_array[i])/ time_window_width_s) 

        event_in_window,bin_edge = np.histogram(
            peak_start_time_s, 
            range = [bin_edge_array[i],bin_edge_end], 
            bins = n_bins)
        
        mask = event_in_window > coincidence
        start_time_window = bin_edge[:-1][mask]
        end_time_window = start_time_window + time_window_width_s


        for start_time, end_time in zip(start_time_window, end_time_window):
            mask = peak_start_time_s >= start_time
            mask &= peak_start_time_s < end_time
            channels_within_window = channel[mask]
            # board_within_window = board[mask]
            area_PE_within_window = peak_area_PE[mask]
            # event_id_within_window = event_id[mask]
            # event_time_s_within_window = event_time[mask]
            rel_time_within_window = peak_start_time_s[mask]
            absolute_time_within_window = absolute_time[mask]
            
            # if (len(np.unique(board_within_window)) == 2) & (len(np.unique(channels_within_window)) >= coincidence):
            if (len(np.unique(channels_within_window)) >= coincidence):
                sum_area_PE = np.sum(area_PE_within_window)
                sum_area_PE_list.append(sum_area_PE)
                rel_time.append(np.min(rel_time_within_window))
                abs_time.append(np.min(absolute_time_within_window))

    return (sum_area_PE_list, rel_time, abs_time)


list_file = [
    "/kalinka/storage/darkmatter/XENONnT/sk6801/UCSD_data/processed_data/spectrum/tritium_voltage_46_peak_info.csv",
    "/kalinka/storage/darkmatter/XENONnT/sk6801/UCSD_data/processed_data/spectrum/Co57_voltage_all_peak_info.csv",
    "/kalinka/storage/darkmatter/XENONnT/sk6801/UCSD_data/processed_data/spectrum/Cs137_voltage_all_peak_info.csv",
    "/kalinka/storage/darkmatter/XENONnT/sk6801/UCSD_data/processed_data/spectrum/gain_calibration_voltage_47_peak_info_12.csv",
]


coincidence = 13
PE_threshold = 10

output_name = list_file[0].replace("spectrum/", f"spectrum/co{coincidence}_{PE_threshold}PE/")
dirname = os.path.dirname(output_name)
os.makedirs(dirname, exist_ok=True)
# copy this script to the output directory
shutil.copy(__file__, dirname)

for file_name in list_file:
    logger.info(f"processing file: {file_name}")

    df = pd.read_csv(file_name,
        parse_dates=["date_time"],
        delimiter=",",
        quotechar='"', 
        skipinitialspace=True, 
        encoding="utf-8")

    d2d_data = d2d.data(df)

    delay_time = 0

    change_time = d2d_data.get_df()
    change_time.loc[change_time.board == 1, 'peak_start_time_s'] += delay_time
    d2d_data_updated = d2d.data(change_time)

    mask = (d2d_data_updated.peak_area_PE > PE_threshold) 
    # & (d2d_data_updated.peak_height_V < 1.2)
    clean_data = d2d_data_updated.apply_mask(mask, inplace=False, dry=True)

    # mask = (d2d_data.peak_area_PE > d2d_data.spe_position*1.5)
    # clean_data = d2d_data.apply_mask(mask, inplace=False, dry=True)

    # absolute_time_list = []
    # for dtime in clean_data.event_start_time_s:
    #     dtime_pd = pd.Timedelta(dtime, 's')
    #     absolute_time = clean_data.date_time + dtime_pd
    #     absolute_time_list.append(absolute_time)

    tdeltas = (clean_data.peak_start_time_s*1e3).astype("timedelta64[ms]")
    absolute_time = clean_data.date_time + tdeltas

    sum_area_PE_list, rel_time, abs_time = get_sum_area_PE_in_time_window(
        clean_data.peak_start_time_s, 
        absolute_time,
        clean_data.channel, 
        clean_data.board, 
        clean_data.peak_area_PE, 
        clean_data.event_id,
        time_window_width_s = 0.000001,  # 1 us
        coincidence=coincidence)
    
    
    
    df_sum_area_PE = pd.DataFrame({
        "sum_area_PE": sum_area_PE_list,
        "rel_time": rel_time,
        "abs_time": abs_time
    })


    
    df_sum_area_PE.to_csv(
        output_name,
        index=False,
        float_format='%.6f',
        date_format='%Y-%m-%d %H:%M:%S'
    )


