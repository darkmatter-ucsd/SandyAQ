import numpy as np
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"./"))
# from event_info import EventInfo
from run_info import RunInfo
from numba import njit
from matplotlib import pyplot as plt
from collections.abc import Iterable


class WaveformInfo(RunInfo):
    '''
    Dataclass to store the information of a single data file for peak_processor.py.
    All attributes in this class corresponse to the columns of the output csv/hdf5 file
    If the number of columns is changed, run_processor.py will reprocess all runs 
    that were being processed.
    
    For other classes inheriting this class can add more attributes, such as fast_processor
    or metadata_handler
    '''

    def __init__(self):

        super().__init__()

        self.spe_position: int = np.nan

        self.event_id: int = np.nan
        self.event_start_time_s: float = np.nan # seconds since data taking

        # waveform level information
        self.integral_window_area_Vns: float = np.nan
        self.integral_window_area_PE: float = np.nan
        self.integral_window_height_V: float = np.nan
        # self.baseline_V: float = np.nan

        # peak level information
        self.n_peaks: int = np.nan

        self.peak_start_time_s_array = np.array([], dtype=float)  # seconds since run start time
        self.peak_end_time_s_array = np.array([], dtype=float)  # seconds since run start time
        self.peak_rel_start_time_s_array = np.array([], dtype=float)  # seconds since run start time
        
        self.peak_height_V_array = np.array([], dtype=float)
        self.peak_width_ns_array = np.array([], dtype=float)
        self.peak_area_Vns_array = np.array([], dtype=float)
        self.peak_area_PE_array = np.array([], dtype=float)


    # @njit
    def set_peaks_for_single_processed_waveform(
            self,single_processed_waveform, 
            single_baseline, 
            single_baseline_std, 
            threshold_sig=1, 
            event_id=None,
            peak_merge_window_sample = 250, # samples
            show_plot = False,
            ):
        
        window_size = 6
        min_peak_width_sample = window_size*3

        smooth_waveform = np.convolve(
            single_processed_waveform, 
            np.ones(window_size)/window_size, mode='valid')

        # recalculated the baseline for the smoothed waveform
        # if threshold_sig is None:
        peak_threshold = single_baseline + threshold_sig * single_baseline_std
        # print(f"Threshold: {threshold:.3f} V")

        # applying the threshold to find peaks
        mask = smooth_waveform > peak_threshold

        # mark the start and end of the peaks
        diff = np.diff(mask)

        samples_above_threshold = np.where(diff == 1)[0]
        # start samples_above_threshold are the samples_above_threshold after the rising edge
        # samples_above_threshold[0::2] = samples_above_threshold[0::2]+1 
        samples_above_threshold[1::2] = samples_above_threshold[1::2] + window_size

        # remove the last point if it's odd
        if len(samples_above_threshold) % 2 != 0:
            samples_above_threshold = samples_above_threshold[:-1]  
            
        # reshape the points into pairs for better handling
        peak_boundaries_sample = samples_above_threshold.reshape(-1, 2)

        # remove narrow peaks
        peak_width = peak_boundaries_sample[:,1] - peak_boundaries_sample[:,0]
        tmp = np.where(peak_width < min_peak_width_sample)
        mask = peak_width > min_peak_width_sample
        peak_boundaries_sample = peak_boundaries_sample[mask,:]

        
        # merge peaks within the peak_merge_window
        ### FIXME: it is a wrong implementation
        ### current version is merging only: peak_{j,start} - peak_{i, start} < peak_merge_window_sample for all j > i
        ### correct version should merge: peak_{i+1,end} - peak_{i, start} < peak_merge_window_sample
        ### therefore the following implementation is wrong and has to be changed.

        n_peaks = len(peak_boundaries_sample)

        for iterations in np.arange(0, n_peaks-1):
            if len(peak_boundaries_sample) < 2:
                break

            if len(peak_boundaries_sample) <= iterations + 1:
                break

            peak_window_boundary = peak_boundaries_sample[iterations,0] + peak_merge_window_sample
            idxs = np.where(peak_boundaries_sample[iterations + 1:,0] < peak_window_boundary)[0] # idxs is shifted by 1 due to the slicing
            if len(idxs) > 0:
                end_boundary = peak_boundaries_sample[iterations + 1 + idxs[-1],1]
                peak_boundaries_sample = np.delete(peak_boundaries_sample, idxs+1, axis=0)
                peak_boundaries_sample[iterations,1] = end_boundary
        
        # results
        if peak_boundaries_sample.shape[0] == 0:
            self.n_peaks = 0

            self.peak_start_time_s_array = np.array([], dtype=float)  # seconds since run start time
            self.peak_end_time_s_array = np.array([], dtype=float)  # seconds since run start time
            self.peak_rel_start_time_s_array = np.array([], dtype=float)  # seconds since run start time
            
            self.peak_height_V_array = np.array([], dtype=float)
            self.peak_width_ns_array = np.array([], dtype=float)
            self.peak_area_Vns_array = np.array([], dtype=float)
            self.peak_area_PE_array = np.array([], dtype=float)
            return
        
        # go to baseline   
        end_sample_of_previous_peak = 0

        start_sample_list = []
        end_sample_list = []
        peak_area_Vsample_list = []
        peak_height_list = []

        for i, peak_boundary in enumerate(peak_boundaries_sample):
            
            # find the first sample below the baseline before the peak boundary
            pass_baseline_idx = np.where(single_processed_waveform[peak_boundary[0]::-1] < single_baseline)[0]
            if len(pass_baseline_idx) > 0:
                start_sample = peak_boundary[0] - pass_baseline_idx[0]
            else:
                start_sample = 0
            # find the first sample above the baseline after the peak boundary
            pass_baseline_idx = np.where(single_processed_waveform[peak_boundary[1]:] < single_baseline)[0]
            if len(pass_baseline_idx) > 0:
                end_sample = peak_boundary[1] + pass_baseline_idx[0]
            else:
                end_sample = len(single_processed_waveform)-1
            
            # skip if the start sample is before the end sample of the previous peak (ie overlapping peaks)
            if start_sample < end_sample_of_previous_peak:
                continue
            else:
                end_sample_of_previous_peak = end_sample              
                start_sample_list.append(start_sample)
                end_sample_list.append(end_sample)
                peak_area_Vsample_list.append(np.sum(single_processed_waveform[start_sample:end_sample]))
                peak_height_list.append(np.max(single_processed_waveform[start_sample:end_sample]))

        start_sample_array = np.array(start_sample_list, dtype=int)
        end_sample_array = np.array(end_sample_list, dtype=int)
        peak_area_Vsample_array = np.array(peak_area_Vsample_list, dtype=float)

        self.peak_height_V_array = np.array(peak_height_list, dtype=float)
        self.peak_width_ns_array = (end_sample_array - start_sample_array)*4 # in ns, FIXME: this is hardcoded for V1725, 1 sample = 4 ns, get from config
        
        rel_start_time_s = start_sample_array * 4 / 1e9 # FIXME: this is hardcoded for V1725
        rel_end_time_s = end_sample_array * 4 / 1e9
        self.peak_rel_start_time_s_array = rel_start_time_s  # in seconds, assuming the sampling rate is 250 MHz (4 ns per sample)
        self.peak_start_time_s_array = self.event_start_time_s + rel_start_time_s
        self.peak_end_time_s_array = self.event_start_time_s + rel_end_time_s  # in seconds, assuming the sampling rate is 250 MHz (4 ns per sample)

        self.peak_area_Vns_array = peak_area_Vsample_array * 4 # FIXME: this is hardcoded for V1725, 1 sample = 4 ns, get from config
        
        if isinstance(self.spe_position, Iterable):
            self.peak_area_PE_array = self.peak_area_Vns_array/self.spe_position[0]
        else:
            self.peak_area_PE_array = self.peak_area_Vns_array/self.spe_position

        self.n_peaks = int(len(self.peak_start_time_s_array))

        if show_plot:
            plt.close('all')
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.plot(single_processed_waveform, label='filtered waveform')
            ax.axhline(single_baseline, color='green', linestyle='dashdot', label='baseline')
            ax.axhline(peak_threshold, color='black', linestyle='--', label='threshold')
            for start, end, peak_area_PE in zip(start_sample_list, end_sample_list, self.peak_area_PE_array):
                ax.fill_between(np.arange(start, end),
                    single_processed_waveform[start:end],
                      alpha=0.5, label=f"area = {peak_area_PE:.1f} PE")
            plt.title(f'Event ID: {event_id}')
            plt.xlabel('Sample')
            plt.ylabel('Amplitude (V)')
            plt.legend()
            plt.show()

        # # convert all arrays to lists for better compatibility with pandas
        # self.peak_start_time_s_array = self.peak_start_time_s_array.tolist()
        # self.peak_end_time_s_array = self.peak_end_time_s_array.tolist()
        # self.peak_height_V_array = self.peak_height_V_array.tolist()
        # self.peak_width_ns_array = self.peak_width_ns_array.tolist()
        # self.peak_area_Vns_array = self.peak_area_Vns_array.tolist()
        # self.peak_area_PE_array = self.peak_area_PE_array.tolist()

        # convert data types for better compatibility with pandas
        if isinstance(self.post_trigger, Iterable):
            post_trigger = self.post_trigger[0]
        else:
            post_trigger = self.post_trigger

        if isinstance(self.record_length_sample, Iterable):
            record_length_sample = self.record_length_sample[0]
        else:
            record_length_sample = self.record_length_sample

        if isinstance(post_trigger,float) & isinstance(record_length_sample, (int, np.integer)):
            tmp_start = 1-post_trigger/100.0-0.1 # 0.1 is to avoid the edge effect
            self.integral_window = (tmp_start, tmp_start+0.25)

            sum_start = int(record_length_sample * self.integral_window[0])
            sum_end = int(record_length_sample * self.integral_window[1])

            areas_Vsamples = np.sum(single_processed_waveform[sum_start:sum_end])
            self.integral_window_area_Vns = 4 * areas_Vsamples # now it becomes V * ns (for V1725, 1 sample = 4 ns)
            self.integral_window_area_PE = self.integral_window_area_Vns / self.spe_position
            self.integral_window_height_V = np.max(single_processed_waveform[sum_start:sum_end])
        else:
            raise ValueError("post_trigger and record_length_sample must be set to calculate integral_window_area_Vns and integral_window_height_V")

        return
    

        
        


