#!/home/daqtest/anaconda3/bin python

import numpy as np
import sys
import os

import json
import pandas as pd
import csv
from copy import deepcopy
import tracemalloc
# sys.path.insert(0,"/home/daqtest/Processor/sandpro")
# import sandpro

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
# import common.run_info as run_info
import data_structure.run_info as run_info
# import data_processing.event_processor as event_processor
import gain_analysis.fit_spe as fit_spe
import gain_analysis.gain_processor as gain_processor
import common.d2d as d2d
import common.utils as util
import common.config_reader as common_config_reader
from common.logger import setup_logger
from data_processing.event_processor_all_channel import EventProcessor
from data_structure.waveform_info import WaveformInfo
from data_structure.peak_info import PeakInfo


logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

class GainProcessor:
    def __init__(self, output_fname = "gain_info_single_channel"):
        
        self.common_cfg_reader = common_config_reader.ConfigurationReader()

        # set the paths
        self.path_config = self.common_cfg_reader.get_absolute_path_config()
        self.run_list_path = self.path_config.get('GAIN_ANALYSIS', 'gain_list_input_file')
        self.output_file_path = self.path_config.get('GAIN_ANALYSIS', 'gain_list_output_file')

        self.config = self.common_cfg_reader.get_data_processing_config()
        
        self.hdf5_key = self.config.get('RUN_PROCESSOR_SETTINGS', 'hdf5_key')

        self.hist_n_bins = int(self.config.get('GAIN_PROCESSOR_SETTINGS', 'hist_n_bins'))
        tmp = self.config.get("GAIN_PROCESSOR_SETTINGS", "hist_range")
        tmp = tmp.split(' ')
        self.hist_range = (float(tmp[0]),float(tmp[1]))

        self.info = run_info.RunInfo()
    
    def read_run_list(self, run_list_path: str) -> d2d.data:
        
        if os.path.isfile(run_list_path) and run_list_path.endswith('.h5'):
            df = pd.read_hdf(run_list_path, 
                            key=self.hdf5_key,
                            mode='r')
            df['area_hist_count_Vns'] = df['area_hist_count_Vns'].apply(json.loads).apply(np.array)
            df['area_bin_edges_Vns'] = df['area_bin_edges_Vns'].apply(json.loads).apply(np.array)
            df['channel_list'] = df['channel_list'].apply(json.loads).apply(np.array)
            df['board_0_channels'] = df['board_0_channels'].apply(json.loads).apply(np.array)
            df['board_1_channels'] = df['board_1_channels'].apply(json.loads).apply(np.array)
            
            all_runs = d2d.data(df)
            
        else:
            raise(f"Wrong path for run_list: {run_list_path}")
        
        return all_runs
    
    def data_selection(self, all_runs: d2d.data, 
                                            from_date = np.datetime64('2024-05-18')) -> d2d.data:
        """
        Apply the cuts and return the d2d.data after cuts

        Args:
            all_runs (d2d.data): data from all runs in df/dict format

        Returns:
            d2d.data: data from all runs in df/dict format after cuts
        """
        # data selection cuts
        # mask_run_tag = util.vec_regex_search('GXe/gain_calibration', all_runs.run_tag)
        mask_run_tag_remove_trash = (~util.vec_regex_search('trash', all_runs.run_tag)) & (~util.vec_regex_search('test', all_runs.run_tag))
        # mask_run_tag_remove_trash = ~util.vec_regex_search('test', all_runs.run_tag)
        mask_time = (all_runs.date_time > from_date)
        # mask_start_index_nan = ~np.isnan(all_runs.start_index)
        mask_nevents_nan = ~np.isnan(all_runs.number_of_events)
        mask_record_length_nan = ~np.isnan(all_runs.record_length_sample)
        
        # mask = mask_run_tag & mask_run_tag_remove_trash & mask_time & mask_record_length_nan & mask_start_index_nan & mask_nevents_nan
        # mask = mask_run_tag_remove_trash & mask_time & mask_record_length_nan & mask_start_index_nan & mask_nevents_nan
        mask = mask_run_tag_remove_trash & mask_time & mask_record_length_nan & mask_nevents_nan
        
        all_runs.apply_mask(mask, inplace=True, dry = False)
        
        return all_runs
    
    def get_board_channel(self, SiPM_channel: int, board_0_channels: np.array, board_1_channels: np.array) -> int:
        if SiPM_channel in board_0_channels: 
            board_channel = np.where(np.array(board_0_channels) == SiPM_channel)[0]
        elif SiPM_channel in board_1_channels:  
            board_channel = np.where(np.array(board_1_channels) == SiPM_channel)[0]
        else:
            raise ValueError(f"SiPM channel {SiPM_channel} not found in both boards.")
        return board_channel[0]
    
    def get_baseline_for_all_events(self, waveform, baseline_front=(0.0,0.2)):
        baseline_start_f = int(1000 * baseline_front[0])
        baseline_end_f = int(1000 * baseline_front[1])

        # baseline is calculated with raw waveform
        baseline_mean_V = np.mean(waveform[:,baseline_start_f:baseline_end_f], axis=1)
        baseline_std_V = np.std(waveform[:,baseline_start_f:baseline_end_f], axis=1)

        return baseline_mean_V, baseline_std_V
    
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

    
    def tmp_peak_level_analysis(self, single_run_info: run_info.RunInfo):
        """
        Temporary function to analyze peak level information.
        This is not used in the final gain processing.
        """
        event_processor = EventProcessor(single_run_info)
        board_channel = self.get_board_channel(single_run_info.channel, single_run_info.board_0_channels, single_run_info.board_1_channels)

        waveform_processor = event_processor.get_waveform_processor(board_channel)
        waveform = waveform_processor.filtered_wfs

        baseline, baseline_std = self.get_baseline_for_all_events(waveform)

        waveform_info = WaveformInfo()
        waveform_info.set_info_from_dict(single_run_info.__dict__)

        peak_area_Vns_list = []

        for event_id in range(waveform.shape[0]):
            single_waveform = waveform[event_id,:]
            single_baseline, single_baseline_std = baseline[event_id], baseline_std[event_id]

            waveform_info.event_start_time_s = waveform_processor.event_time_s[event_id]
            waveform_info.event_id = event_id

            waveform_info.set_peaks_for_single_processed_waveform(
                single_waveform, 
                single_baseline, 
                single_baseline_std,
                threshold_sig=5, 
            )

            for peak_id in range(int(waveform_info.n_peaks)):
                peak_area_Vns_list.append(waveform_info.peak_area_Vns_array[peak_id])

        area_Vns = np.array(peak_area_Vns_list)

        self.peak_hist_count_Vns,self.peak_bin_edges_Vns = np.histogram(
            area_Vns,
            bins=self.hist_n_bins,
            range=self.hist_range)
        
        return
    
    def process_single_run(self, single_run_info: run_info.RunInfo):
        
        # self.area_hist_count_Vns,self.area_bin_edges_Vns = df.area_hist_count_Vns,df.area_bin_edges_Vns

        # voltage_preamp1_V helps to predetermine the peak distance
        spe_fit = fit_spe.FitSPE(single_run_info.voltage_preamp1_V, 
                                single_run_info.area_hist_count_Vns, 
                                single_run_info.area_bin_edges_Vns)
        self.spe_fit = spe_fit
        
        # if (np.isnan(spe_fit.gain) or np.isnan(spe_fit.gain_error)):

        #     logger.info("No gain found in the integral window histogram, trying with peak level analysis.")

        #     self.tmp_peak_level_analysis(single_run_info)

        #     spe_fit = fit_spe.FitSPE(single_run_info.voltage_preamp1_V, 
        #                         self.peak_hist_count_Vns, 
        #                         self.peak_bin_edges_Vns)
        #     self.spe_fit = spe_fit
        
        if not (np.isnan(spe_fit.gain) or np.isnan(spe_fit.gain_error)):
            spe_position = spe_fit.spe_position
            spe_position_err = spe_fit.spe_position_error
            gain = spe_fit.gain
            gain_err = spe_fit.gain_error

            spe_resolution = spe_fit.spe_resolution
            spe_resolution_err = spe_fit.spe_resolution_error
            
        else:
            spe_position = np.nan
            spe_position_err = np.nan
            gain = np.nan
            gain_err = np.nan
            
            spe_resolution = np.nan
            spe_resolution_err = np.nan

            logger.warning(f"Cannot fit for file: {single_run_info.bin_full_path}")
            
        # plt.savefig("./test.png")
        # input("Press Enter to continue...")
            
        return spe_position, spe_position_err, gain, gain_err, spe_resolution, spe_resolution_err
    
    def process_runs(self):

        tracemalloc.start()
        
        all_runs_d2d = self.read_run_list(self.run_list_path)
        all_runs_d2d = self.data_selection(all_runs_d2d)

        logger.info(f"Memory usage (current, peak): {tracemalloc.get_traced_memory()}")

        spe_position_list = []
        spe_position_err_list = []
        gain_list = []
        gain_err_list = []
        spe_resolution_list = []
        spe_resolution_err_list = []

        for i in range(len(all_runs_d2d)):
            # convert one row into run_info
            single_run_info = all_runs_d2d.get_row_info(i)
            logger.info(f"Processing file: {single_run_info.bin_full_path}")
            
            
            spe_position, spe_position_err, gain, gain_err, spe_resolution, spe_resolution_err = self.process_single_run(single_run_info)
            
            spe_position_list.append(spe_position)
            spe_position_err_list.append(spe_position_err)
            gain_list.append(gain)
            gain_err_list.append(gain_err)
            spe_resolution_list.append(spe_resolution)
            spe_resolution_err_list.append(spe_resolution_err)

            # # for every 100 runs, save to csv file
            # if (i) % 1000 == 0 or i == len(all_runs_d2d) - 1:
            #     current, peak = tracemalloc.get_traced_memory()
            #     current = current/(1024*1024)
            #     peak = peak/(1024*1024)
            #     logger.info(f"Average current memory [MB]: {current:.4f}, average peak memory [MB]: {peak:.4f}")
            #     if current > 800:
            #         raise MemoryError(f"Memory usage is too high: {current:.4f} MB, peak: {peak:.4f} MB.")

        all_runs_d2d.__setattr__("spe_position", np.array(spe_position_list))
        all_runs_d2d.__setattr__("spe_position_err", np.array(spe_position_err_list))
        all_runs_d2d.__setattr__("gain", np.array(gain_list))
        all_runs_d2d.__setattr__("gain_err", np.array(gain_err_list))
        all_runs_d2d.__setattr__("spe_resolution", np.array(spe_resolution_list))
        all_runs_d2d.__setattr__("spe_resolution_err", np.array(spe_resolution_err_list))

        delattr(all_runs_d2d, "area_hist_count_Vns")
        delattr(all_runs_d2d, "area_bin_edges_Vns")
        
        new_df = all_runs_d2d.get_df()
        new_df.to_csv(f"{self.output_file_path}", index=False, quoting=csv.QUOTE_NONNUMERIC)

        tracemalloc.stop()
        
        return
    
if __name__ == "__main__":
    processor = GainProcessor()
    processor.process_runs()
    logger.info("Gain processing completed successfully.")