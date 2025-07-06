import numpy as np
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"./"))
# from event_info import EventInfo
from run_info import RunInfo
from numba import njit

@njit
def delete_workaround(arr, num):
    mask = np.zeros(arr.shape[0], dtype=np.int64) == 0
    mask[np.where(arr == num)[0]] = False
    return arr[mask]

@njit
def _set_peaks_for_single_processed_waveform(
        single_processed_waveform, 
        single_baseline, 
        single_baseline_std, 
        threshold_sig=3):
    
    window_size = 6
    threshold_sig = threshold_sig
    min_peak_width_sample = window_size*3

    smooth_waveform = np.convolve(
        single_processed_waveform, 
        np.ones(window_size)/window_size, mode='valid')

    # recalculated the baseline for the smoothed waveform
    threshold = single_baseline + threshold_sig * single_baseline_std

    # applying the threshold to find peaks
    mask = smooth_waveform > threshold

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
    peak_boundaries = samples_above_threshold.reshape(-1, 2)

    # remove the pair if they are too close to each other
    peak_width = peak_boundaries[:,1] - peak_boundaries[:,0]
    # peak_width = np.repeat(peak_width, 2).reshape(peak_boundaries.shape)
    tmp = np.where(peak_width < min_peak_width_sample)

    mask = peak_width > min_peak_width_sample
    peak_boundaries = peak_boundaries[mask,:]

    return peak_boundaries

class WaveformInfo(RunInfo):
    '''
    Dataclass to store the information of a single data file for peak_processor.py.
    All attributes in this class corresponse to the columns of the output csv/hdf5 file
    If the number of columns is changed, run_processor.py will reprocess all runs 
    that were being processed.
    
    For other classes inheriting this class can add more attributes, such as fast_processor
    or metadata_handler
    '''
    
    #     self.PeakInfoList = []
    
    # def add_peak_info(self, peak_info):
    #     if not isinstance(peak_info, PeakInfo):
    #         raise TypeError("Expected a PeakInfo instance")
    #     self.PeakInfoList.append(peak_info)

    # def set_peak_info_array(self):
    #     if not self.PeakInfoList:
    #         raise ValueError("No PeakInfo instances to set")
        
    #     start_time_array = np.concatenate([peak.start_time_array for peak in self.PeakInfoList])
    #     end_time_array = np.concatenate([peak.end_time_array for peak in self.PeakInfoList])
    #     peak_max_array = np.concatenate([peak.peak_max_array for peak in self.PeakInfoList])
    #     area_array = np.concatenate([peak.area_array for peak in self.PeakInfoList])
        
    #     return PeakInfo(start_time_array, end_time_array, peak_max_array, area_array)


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
        # self.peak_start_time_s: float = np.nan  # seconds since run start time
        # self.peak_end_time_s: float = np.nan  # seconds since run start time
        # self.peak_rel_start_time: float = np.nan  # seconds since run start time
        
        # self.peak_height_V: float = np.nan
        # self.peak_width_ns: float = np.nan
        # self.peak_area_Vns: float = np.nan
        # self.peak_area_PE: float = np.nan

        self.n_peaks: int = np.nan

        self.peak_start_time_s_array = np.array([], dtype=float)  # seconds since run start time
        self.peak_end_time_s_array = np.array([], dtype=float)  # seconds since run start time
        self.peak_rel_start_time_s_array = np.array([], dtype=float)  # seconds since run start time
        
        self.peak_height_V_array = np.array([], dtype=float)
        self.peak_width_ns_array = np.array([], dtype=float)
        self.peak_area_Vns_array = np.array([], dtype=float)
        self.peak_area_PE_array = np.array([], dtype=float)

        # self.peak_start_time_s_array = [0.1]  # seconds since run start time
        # self.peak_end_time_s_array = [0.1]  # seconds since run start time
        # self.peak_rel_start_time_s_array = [0.1]  # seconds since run start time

        # self.peak_height_V_array = [0.1]  # peak height in Volts
        # self.peak_width_ns_array = [0.1]  # peak width in nanoseconds
        # self.peak_area_Vns_array = [0.1]  # peak area in Volts * nan
        # self.peak_area_PE_array = [0.1]  # peak area in PE (photoelectrons)

    # def set_result(self, start_time_array_s, end_time_array_s, height_array_V, area_array_Vns, width_array_ns):
    #     """
    #     Set the result of the peak information.

    #     Args:
    #         start_time_array (np.ndarray): Array of start times of peaks.
    #         end_time_array (np.ndarray): Array of end times of peaks.
    #         peak_max_array (np.ndarray): Array of maximum values of peaks.
    #         area_array (np.ndarray): Array of area values of peaks.
    #     """
    #     self.peak_start_time_s_array = start_time_array_s
    #     self.peak_end_time_s_array = end_time_array_s
    #     self.peak_height_V_array = height_array_V
    #     self.peak_area_unit_array = area_array_Vns
    #     self.peak_width_unit_array = width_array_ns

    # @njit
    def set_peaks_for_single_processed_waveform(
            self,single_processed_waveform, 
            single_baseline, 
            single_baseline_std, 
            threshold_sig=1, 
            extend_sum_window=30,
            event_id=None):
        
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

        # remove the pair if they are too close to each other
        peak_width = peak_boundaries_sample[:,1] - peak_boundaries_sample[:,0]
        # peak_width = np.repeat(peak_width, 2).reshape(peak_boundaries_sample.shape)
        tmp = np.where(peak_width < min_peak_width_sample)

        mask = peak_width > min_peak_width_sample
        peak_boundaries_sample = peak_boundaries_sample[mask,:]

        
        # results
        if peak_boundaries_sample.shape[0] == 0:
            # self.peak_start_time_s_array = []
            # self.peak_end_time_s_array = []
            # self.peak_height_V_array = []
            # self.peak_width_ns_array = []
            # self.peak_area_Vns_array = []
            # self.peak_area_PE_array = []
            # self.peak_start_time_s_array = np.array([], dtype=float)
            # self.peak_end_time_s_array = np.array([], dtype=float)
            # self.peak_height_V_array = np.array([], dtype=float)
            # self.peak_width_ns_array = np.array([], dtype=float)
            # self.peak_area_Vns_array = np.array([], dtype=float)
            # self.peak_area_PE_array = np.array([], dtype=float)
            self.n_peaks = 0
            return
        
        # peak_boundaries_ns = peak_boundaries_sample * 4 # in ns, assuming the sampling rate is 250 MHz (4 ns per sample)
        
        # self.peak_rel_start_time_s_array, self.peak_end_time_s_array = peak_boundaries_ns[:,0]/1e9, peak_boundaries_ns[:,1]/1e9
        # self.peak_start_time_s_array = self.peak_rel_start_time_s_array + self.event_start_time_s
        # self.peak_end_time_s_array += self.event_start_time_s
        # self.peak_height_V_array = np.empty(peak_boundaries_sample.shape[0], dtype=float)
        # self.peak_width_ns_array = np.empty(peak_boundaries_sample.shape[0], dtype=float)
        # self.peak_area_Vns_array = np.empty(peak_boundaries_sample.shape[0], dtype=float)
        # peak_area_Vsample_array = np.empty(peak_boundaries_sample.shape[0], dtype=float)

        # avoid overlapping peaks   
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
            
            # skip if the start sample is before the end sample of the previous peak
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
        
        self.peak_area_PE_array = self.peak_area_Vns_array/self.spe_position[0]

        self.n_peaks = int(len(self.peak_start_time_s_array))

        # # convert all arrays to lists for better compatibility with pandas
        # self.peak_start_time_s_array = self.peak_start_time_s_array.tolist()
        # self.peak_end_time_s_array = self.peak_end_time_s_array.tolist()
        # self.peak_height_V_array = self.peak_height_V_array.tolist()
        # self.peak_width_ns_array = self.peak_width_ns_array.tolist()
        # self.peak_area_Vns_array = self.peak_area_Vns_array.tolist()
        # self.peak_area_PE_array = self.peak_area_PE_array.tolist()

        if (self.post_trigger is not None) & (self.record_length_sample is not None):
            tmp_start = 1-self.post_trigger/100.0-0.1 # 0.1 is to avoid the edge effect
            self.integral_window = (tmp_start, tmp_start+0.25)

            sum_start = int(self.record_length_sample * self.integral_window[0])
            sum_end = int(self.record_length_sample * self.integral_window[1])

            areas_Vsamples = np.sum(single_processed_waveform[sum_start:sum_end])
            self.integral_window_area_Vns = 4 * areas_Vsamples # now it becomes V * ns (for V1725, 1 sample = 4 ns)
            self.integral_window_area_PE = self.integral_window_area_Vns / self.spe_position
            self.integral_window_height_V = np.max(single_processed_waveform[sum_start:sum_end])

        return
    

        
        


