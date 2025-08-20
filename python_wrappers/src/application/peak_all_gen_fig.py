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

sys.path.insert(0,"../")
import common.d2d as d2d
import common.utils as util
import data_processing.fast_processor_all_channel as fast_processor
from data_processing.event_processor_all_channel import EventProcessor

from data_structure.waveform_info import WaveformInfo
from data_structure.peak_info import PeakInfo

params = {
    # figure
    'figure.figsize': (15, 8),
    'figure.facecolor': 'white',  # make figure background white
    # axes
    'axes.labelsize': 20,
    'axes.linewidth': 2,
    
    'axes.titlesize': 20,
    'axes.grid.which': 'both',  # gridlines at major, minor or both ticks
    # errorbar
    'errorbar.capsize': 4,
    # font
    'font.size': 22,
    'font.family': 'DejaVu Sans',
    # color
    'image.cmap': 'viridis',
    # legend
    'savefig.bbox': 'tight',
    'legend.fontsize': 22,
    'legend.frameon': False,
    'legend.numpoints': 1,  # only one marker in legend
    # line
    'lines.linestyle': 'solid',
    'lines.linewidth': 2,
    'lines.markeredgewidth': 1,
    'lines.markersize': 8,
    # text
    'mathtext.default': 'regular',
    'savefig.bbox': 'tight',
    'savefig.transparent': False,
    # tick
    'xtick.top': True,  # draw ticks on the top side
    'xtick.direction': 'in',
    'xtick.labelsize': 20,
    'xtick.major.size': 8,
    'xtick.major.width': 1,
    'xtick.minor.size': 4,
    'xtick.minor.visible': False,
    'xtick.minor.width': 1,

    'ytick.right': False,  # draw ticks on the right side
    'ytick.direction': 'in',
    'ytick.labelsize': 20,
    'ytick.major.size': 6,
    'ytick.major.width': 1,
    'ytick.minor.size': 3,
    'ytick.minor.visible': False,
    'ytick.minor.width': 1,
    # GRIDS
    'grid.linestyle': '--',  ## dashed
    'mathtext.default': 'regular',
}
plt.rcParams.update(params)

def get_baseline_for_all_events(waveform, baseline_front=(0.0,0.2)):
    baseline_start_f = int(1000 * baseline_front[0])
    baseline_end_f = int(1000 * baseline_front[1])

    # baseline is calculated with raw waveform
    # unit: same as raw waveform
    baseline_mean_V = np.mean(waveform[:,baseline_start_f:baseline_end_f], axis=1)
    baseline_std_V = np.std(waveform[:,baseline_start_f:baseline_end_f], axis=1)

    return baseline_mean_V, baseline_std_V
        

def get_board_channel(SiPM_channel: int, board_0_channels: np.array, board_1_channels: np.array) -> int:
    if SiPM_channel in board_0_channels: 
        board_channel = np.where(board_0_channels == SiPM_channel)[0]
    elif SiPM_channel in board_1_channels:  
        board_channel = np.where(board_1_channels == SiPM_channel)[0]
    else:
        raise ValueError(f"SiPM channel {SiPM_channel} not found in both boards.")

    return board_channel[0]

def set_peak_info_from_waveform_info(waveform_info: WaveformInfo):
    PeakInfoList = []
    peak_info = PeakInfo()
    peak_info.set_info_from_dict(waveform_info.__dict__)

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
        PeakInfoList.append(tmp)

    return PeakInfoList

def get_peak_level_data(all_runs_d2d: d2d.data,
                        md_full_path: str,
                        peak_merge_window_sample: int):
    
    single_info = WaveformInfo()
    single_info_list = []
    
    mask = all_runs_d2d.md_full_path == md_full_path
    # print(f"Processing run {md_full_path}")
    single_run = all_runs_d2d.apply_mask(mask, inplace=False, dry = True)
    # print(single_run.__dict__)

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
            board_channel = get_board_channel(channel_id, board_info.board_0_channels, board_info.board_1_channels)

            waveform_processor = event_processor.get_waveform_processor(board_channel)
            waveform = waveform_processor.filtered_wfs

            baseline, baseline_std = get_baseline_for_all_events(waveform)

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
                PeakInfoList = set_peak_info_from_waveform_info(single_info)
                t2 += time.perf_counter() - t0              

                # single_info_list.append(single_info.__dict__.copy())
                # tmp = deepcopy(single_info.__dict__)
                # single_info_list.append(tmp)

                t0 = time.perf_counter()
                single_info_list += PeakInfoList
                t3 += time.perf_counter() - t0

    print(f'Time taken: {t1:.6f} seconds for peak finding, '
          f'{t2:.6f} seconds for peak info setting, '
          f'{t3:.6f} seconds for appending peak info list')
    
    return (single_info_list, waveform, baseline, baseline_std)


def main():
    df_SPE_position = pd.read_csv(
    "/kalinka/storage/darkmatter/XENONnT/sk6801/UCSD_data/processed_data/spe_position_LXe.csv",
                 delimiter=",")
    
    df = pd.read_csv(
    "/kalinka/storage/darkmatter/XENONnT/sk6801/UCSD_data/processed_data/kalinka_20250706_LXe_gain_info_single_channel.csv",
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

    # replace NaN values with SPE position
    idx_nan = np.where((df['spe_position'].isna()) & (df['voltage_preamp1_V']<-46))[0]
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
    mask_na = ~np.isnan(all_runs_d2d.spe_position)
    mask_voltage = (all_runs_d2d.voltage_preamp1_V < -46)
    mask_run_tag = (all_runs_d2d.run_tag != "LXe/tritium")
    mask = mask_data_taking_mode & mask_na & mask_voltage & mask_run_tag

    all_runs_d2d.apply_mask(mask, inplace=True, dry = True)
    all_run_list = np.unique(all_runs_d2d.md_full_path)

    print(f"Number of runs after masking: {len(all_run_list)}")
    print(all_run_list)

    # initialize the result storage
    df_result = pd.DataFrame(columns=WaveformInfo().__dict__.keys())

    for md_full_path in all_run_list:
        single_info_list = []

        result, _, _, _ = get_peak_level_data(
            all_runs_d2d=all_runs_d2d,
            md_full_path=md_full_path,
            peak_merge_window_sample=250
        )
        single_info_list += result

        df_result = pd.DataFrame.from_dict(single_info_list)
        selected_data = d2d.data(df_result)


        fig_peak_integral_area, axes_peak_integral_area = plt.subplots(3,8,figsize=(35,15))
        fig_area_height, axes_area_height = plt.subplots(3,8,figsize=(35,15))
        fig_area_width, axes_area_width = plt.subplots(3,8,figsize=(35,15))
        fig_area_height_full, axes_area_height_full = plt.subplots(3,8,figsize=(35,15))
        fig_area_width_full, axes_area_width_full = plt.subplots(3,8,figsize=(35,15), sharex=True, sharey='col')
        fig_width_height, axes_width_height = plt.subplots(3,8,figsize=(35,15))

        axes = [axes_area_height, axes_area_height_full, axes_area_width, axes_area_width_full, axes_width_height, axes_peak_integral_area]
        figures = [fig_area_height, fig_area_height_full, fig_area_width, fig_area_width_full, fig_width_height, fig_peak_integral_area] 
        axes_name = ['axes_area_height', 
                    'axes_area_height_full', 
                    'axes_area_width', 
                    'axes_area_width_full', 
                    'axes_width_height', 
                    'axes_peak_integral_area']

        for channel in range(24):
            mask = selected_data.channel == channel
            singl_channel_data = selected_data.apply_mask(mask, inplace=False, dry=True)

            # # this also remove null values from the peak_height_V_array
            # array = list(singl_channel_data.peak_height_V_array)
            # height_V = np.concatenate(array)
            # array = list(singl_channel_data.peak_area_PE_array)
            # area_Vns = np.concatenate(array)
            height_V = singl_channel_data.peak_height_V
            area_PE = singl_channel_data.peak_area_PE
            width_ns = singl_channel_data.peak_width_ns
            integral_window_area_PE = list(singl_channel_data.integral_window_area_PE)
            integral_window_area_PE = np.concatenate(integral_window_area_PE)

            plot_row = channel % 3
            plot_col = channel // 3

            # change the rows so that it match with the physical layout of the channels
            if plot_row == 0:
                plot_row = 1
            elif plot_row == 1:
                plot_row = 0

            axes_peak_integral_area[plot_row,plot_col].hist((area_PE),
                                    bins=100,
                                    range=[-0.1,10], 
                                    alpha=0.5,
                                    label='peak_area_PE_array')
            axes_peak_integral_area[plot_row,plot_col].hist((integral_window_area_PE),
                                    bins=100,
                                    range=[-0.1,10], 
                                    alpha=0.5,
                                    label='integral_window_area_PE')   
            axes_peak_integral_area[plot_row,plot_col].set_yscale('log')
            if plot_row == 2:
                axes_peak_integral_area[plot_row,plot_col].set(xlabel='Area [PE]')
            if plot_col == 0:
                axes_peak_integral_area[plot_row,plot_col].set(ylabel='Counts')

            axes_area_height[plot_row,plot_col].hist2d(area_PE,height_V,
                                    bins=[100,100],
                                    range=[[-0.1,10],[0,0.1]],
                                    cmap='viridis',
                                    norm=LogNorm())
            if plot_row == 2:
                axes_area_height[plot_row,plot_col].set(xlabel='Area [PE]')
            if plot_col == 0:
                axes_area_height[plot_row,plot_col].set(ylabel='Height [V]')


            axes_area_width[plot_row,plot_col].hist2d(area_PE,width_ns,
                                    bins=[100,100],
                                    range=[[-0.1,10],[0,1000]],
                                    cmap='viridis',
                                    norm=LogNorm())  
            if plot_row == 2:
                axes_area_width[plot_row,plot_col].set(xlabel='Area [PE]')
            if plot_col == 0:
                axes_area_width[plot_row,plot_col].set(ylabel='Width [ns]')

            
            axes_area_height_full[plot_row,plot_col].hist2d(area_PE,height_V,
                                    bins=[100,100],
                                    range=[[-0.1,1500],[0,1.5]],
                                    cmap='viridis',
                                    norm=LogNorm())
            if plot_row == 2:
                axes_area_height_full[plot_row,plot_col].set(xlabel='Area [PE]')
            if plot_col == 0:
                axes_area_height_full[plot_row,plot_col].set(ylabel='Height [V]')


            axes_area_width_full[plot_row,plot_col].hist2d(area_PE,width_ns,
                                    bins=[50,50],
                                    range=[[-0.1,1000],[0,2500]],
                                    cmap='viridis',
                                    norm=LogNorm())  
            if plot_row == 2:
                axes_area_width_full[plot_row,plot_col].set(xlabel='Area [PE]')
            if plot_col == 0:
                axes_area_width_full[plot_row,plot_col].set(ylabel='Width [ns]')
            
            
            axes_width_height[plot_row,plot_col].hist2d(width_ns,height_V,
                                    bins=[50,50],
                                    range=[[0,1000],[0,1.5]],
                                    cmap='viridis',
                                    norm=LogNorm())  
            if plot_row == 2:
                axes_width_height[plot_row,plot_col].set(xlabel='Width [ns]')
            if plot_col == 0:
                axes_width_height[plot_row,plot_col].set(ylabel='Height [V]')
            
            for ax in axes:
                ax[plot_row,plot_col].set_title(f"Channel {channel}")

        # Move title upwards
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.legend(axes_peak_integral_area, loc='upper right', fontsize='small')
        axes_peak_integral_area[2,7].legend(loc="upper right")

        # Set plot title
        for fig, ax_name in zip(figures, axes_name):
            short_name = md_full_path.replace('/kalinka/storage/darkmatter/XENONnT/sk6801/UCSD_data/raw_data/','')
            short_name = short_name.replace('/','_')
            short_name = short_name.replace('.json','')
            
            fig.suptitle(f"{ax_name}: \nPath: {short_name}\nComment: {selected_data.comment[0][0]}\nRun tag: {selected_data.run_tag[0][0]}\nVoltage: {selected_data.voltage_preamp1_V[0][0]}",
                        y=1.05, x=0.2,ha='left')
            
            dir_name = f"/kalinka/storage/darkmatter/XENONnT/sk6801/UCSD_data/plots/{short_name}/"
            os.makedirs(dir_name, exist_ok=True)
            print(f"Saving figure {ax_name} to {dir_name}/{ax_name}.png")
            fig.savefig(f"{dir_name}/{ax_name}.png", dpi=100, bbox_inches='tight')
            
            fig.clf()
            plt.clf()
            plt.cla()
            plt.close(fig)
            plt.close('all')


if __name__ == "__main__":
    main()

