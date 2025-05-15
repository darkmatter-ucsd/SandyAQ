from scipy.signal import butter, lfilter, freqz
import matplotlib.pyplot as plt
import numpy as np
    
def butter_lowpass(cutoff, fs, order=5):
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return b, a

def butter_lowpass_filter(data, cutoff=1e6, fs=250e6, order=1):
    b, a = butter_lowpass(cutoff, fs, order=order)
    y = lfilter(b, a, data)
    return y

class WFProcessor(object):
    """
    A class to process waveform data
    """
    def __init__(self,data_folder,length_per_event=1000,volt_per_adc=1/4096,polarity=True):
        self.data_folder = data_folder
        self.length_per_event = length_per_event
        self.volt_per_adc = volt_per_adc
        self.polarity = polarity
        self.wfs = None

    def set_data(self, data, unit = "mV"):
        """
        Load data from a numpy array
        Supposed to be in ADC counts
        
        :param data: data array
        :param unit: unit of the data. Value is either "mV", "V", or "ADC". Default "mV".
        """
        
        self.wfs = data
        self.n_event = len(self.wfs)
        self.time = np.arange(0, self.length_per_event, 1) * 4
        if unit=="ADC":
            self.raw_data_unit = "ADC"
        elif unit=="V":
            self.raw_data_unit = "V"
        elif unit=="mV":
            self.raw_data_unit = "mV"
            self.wfs /= 1000
        else:
            raise ValueError("The parameter 'unit' is either 'ADC', 'V' or 'mV'. ")

    def process_wfs(self,baseline_front=(0.0,0.2),cutoff=10e6,fs=250e6):
        baseline_start_f = int(self.length_per_event * baseline_front[0])
        baseline_end_f = int(self.length_per_event * baseline_front[1])
        # baseline_start_b = int(self.length_per_event * baseline_back[0])
        # baseline_end_b = int(self.length_per_event * baseline_back[1])

        # baseline is calculated with raw waveform
        # unit: same as raw waveform
        self.baseline_mean_V = np.mean(self.wfs[:,baseline_start_f:baseline_end_f],axis=1)
        self.baseline_std_V = np.std(self.wfs[:,baseline_start_f:baseline_end_f],axis=1)
        
        baseline = self.baseline_mean_V.repeat(self.length_per_event).reshape(self.n_event,self.length_per_event)
        self.processed_wfs = (self.wfs - baseline)
        
        if self.raw_data_unit == "ADC":
            self.processed_wfs *= self.volt_per_adc

        # filtered waveform is in V
        self.filtered_wfs = butter_lowpass_filter(self.processed_wfs,cutoff,fs)

    def plot_single_wf(self,i,filtered=True):
        plt.figure(figsize=(10,3))
        if filtered:
            plt.plot(self.time,self.filtered_wfs[i])
            plt.xlabel("Time [ns]")
            plt.ylabel("Voltage [V]")
            plt.xticks(np.arange(0, 4000, step=200))
            plt.ylim(-0.01,0.04)
            plt.xlim(0,3950)
        else:
            plt.plot(self.wfs[i])
            plt.xlabel("Sample index")
            plt.ylabel("ADC counts")
            plt.xticks(np.arange(0, 1000, step=100))
            #plt.show()
            plt.xlim(0,1000)

    def plot_random_wfs(self,n,filtered=True,random_seed=None):
        if random_seed:
            np.random.seed(random_seed)
        for i in np.random.choice(self.n_event,n):
            self.plot_single_wf(i,filtered)

    def plot_average_wfs(self,filtered=True, scaling=1,color="red",show_distribution = None,label=None):
        plt.figure(figsize=(10,3))

        if filtered:
            reference_wfs = self.filtered_wfs
        else:
            reference_wfs = self.wfs
        averaged_wfs = np.mean(reference_wfs,axis=0)

        plt.plot(self.time,averaged_wfs * scaling,color=color,label=label)

        if show_distribution:
            plt.fill_between(self.time,scaling * np.percentile(reference_wfs, 25, axis=0),scaling * np.percentile(reference_wfs, 75, axis=0),
            step='mid', alpha=0.3, color=color, linewidth=0)
            #show_index = np.random.choice(np.arange(len(reference_wfs)),show_distribution)
            #distance_list = np.max(np.abs(reference_wfs[show_index] - averaged_wfs),axis=1)
            #print(len(distance_list))
            #max_distance = np.max(distance_list)
            #for index in show_index:
                #plt.plot(self.time, reference_wfs[index] * scaling,alpha = 0.5 * (1 - (np.max(np.abs(reference_wfs[index]-averaged_wfs))/max_distance)),color=color)

        plt.xlabel("Time [ns]")
        plt.ylabel("Voltage [V]")
        plt.xticks(np.arange(1800, 2200, step=20))
        plt.xlim(1800,2200)

    def get_event_start_end_idx(self, sum_window=(0.4,0.6), consecutive_samples=3, threshold_sig=5):
        """
        Return the start and end index of the sum window.
        The start index is defined as the first index where the waveform (within sum_window) is above threshold for {n} consecutive_samples.
        The end index is defined as the last index where the waveform  (within sum_window) is above threshold.

        :param sum_window: tuple of two floats, the start and end of the sum window in percentage of the event length
        :param consecutive_samples: number of consecutive samples above threshold to be considered as the start of the sum window
        :param threshold_sig: number of standard deviations above the baseline to be considered as above threshold
        """

        if not self.polarity:
            filtered_wfs = self.filtered_wfs * -1
        else:
            filtered_wfs = self.filtered_wfs

        sum_start_idx = int(self.length_per_event * sum_window[0])
        sum_end_idx = int(self.length_per_event * sum_window[1])

        sum_start_idx_array = np.full(self.n_event, sum_start_idx)
        sum_end_idx_array = np.full(self.n_event, sum_end_idx)

        # find indexes of the waveform above threshold
        threshold = self.baseline_mean_V + threshold_sig * self.baseline_std_V
        threshold = threshold.repeat(self.length_per_event).reshape(self.n_event,self.length_per_event) # make the threshold the same array shape as the waveform
        above_threshold_idx_event = np.where(filtered_wfs > threshold)[0]
        above_threshold_idx_sample = np.where(filtered_wfs > threshold)[1]

        # select indexes within sum_window
        mask_index = (above_threshold_idx_sample >= sum_start_idx) & (above_threshold_idx_sample <= sum_end_idx)
        above_threshold_idx_event = above_threshold_idx_event[mask_index]
        above_threshold_idx_sample = above_threshold_idx_sample[mask_index]

        # find the index of the first consecutive_samples above threshold
        consecutive_sample_flag = 0
        for event in range(self.n_event):

            # sum_start_idx_array[event] = above_threshold_idx[0]
            # sum_end_idx_array[event] = above_threshold_idx[-1]

            if event in np.unique(above_threshold_idx_event):

                above_threshold_idx = above_threshold_idx_sample[np.where(above_threshold_idx_event == event)]
                above_threshold_idx_diff = np.diff(above_threshold_idx)

                for i, diff in enumerate(above_threshold_idx_diff):
                    if diff == 1:
                        consecutive_sample_flag += 1
                    else:
                        consecutive_sample_flag = 0

                    if consecutive_sample_flag == consecutive_samples:
                        sum_start_idx = above_threshold_idx[i-(consecutive_samples-1)]
                        sum_start_idx_array[event] = sum_start_idx
                        break

        return sum_start_idx_array, sum_end_idx_array
    
    def get_area(self,sum_window=(0.4,0.6), consecutive_samples=3, threshold_sig=5):
        """
        Return the area of the waveform in the sum window
        Unit: V * ns
        """
        sum_start = int(self.length_per_event * sum_window[0])
        sum_end = int(self.length_per_event * sum_window[1])

        areas_Vsamples = np.sum(self.filtered_wfs[:,sum_start:sum_end], axis=1)
        self.areas_Vns = 4 * areas_Vsamples # now it becomes V * ns (for V1725, 1 sample = 4 ns)

        if not self.polarity:
            self.areas_Vns = -self.areas_Vns
        return self.areas_Vns
    
    def get_area_rigor(self,sum_window=(0.4,0.6), consecutive_samples=3, threshold_sig=5):
        """
        Return the area of the waveform in the sum window
        Unit: V * ns
        """

        self.sum_start_list, self.sum_end_list = self.get_event_start_end_idx(sum_window, 
                                                          consecutive_samples=consecutive_samples, 
                                                          threshold_sig=threshold_sig)
        # sum_start = int(self.length_per_event * sum_window[0])
        # sum_end = int(self.length_per_event * sum_window[1])

        areas_Vsamples = np.zeros(self.n_event)

        for i, (sum_start, sum_end) in enumerate(zip(self.sum_start_list, self.sum_end_list)):
            areas_Vsamples[i] = np.sum(self.filtered_wfs[i,sum_start:sum_end])
        self.areas_Vns = 4 * areas_Vsamples # now it becomes V * ns (for V1725, 1 sample = 4 ns)

        if not self.polarity:
            self.areas_Vns = -self.areas_Vns
        return self.areas_Vns
    
    def get_height(self, search_window =(0.4,0.6)):
        """
        Return the height of the waveform in the search window
        Unit: V
        """
        sum_start = int(self.length_per_event * search_window[0])
        sum_end = int(self.length_per_event * search_window[1])
        self.heights_V = np.max(self.filtered_wfs[:,sum_start:sum_end],axis=1) # unit: V
        # self.heights *= 1000 # now it becomes V 
        if not self.polarity:
            self.heights_V = -self.heights_V
        return self.heights_V
    
    def get_rise_time_ns(self, search_window =(0.4,0.6)):
        """
        Return the rise time of the waveform in the search window
        Unit: ns
        """
        sum_start = int(self.length_per_event * search_window[0])
        sum_end = int(self.length_per_event * search_window[1])

        max_height = abs(np.max(self.filtered_wfs[:,sum_start:sum_end],axis=1)) # unit: V
        max_loc = abs(np.argmax(self.filtered_wfs[:,sum_start:sum_end],axis=1)) # sample index of the max height relative to sum_start

        # calculate the threshold
        threshold = self.baseline_mean_V + 5 * self.baseline_std_V
        self.rise_time = np.zeros(self.n_event)
        for i in range(self.n_event):

            # check if the max height is above the threshold
            if max_height[i] < threshold[i]:
                continue

            timer = 0 # unit: sample
            # count the number of samples that are above the threshold and below max height
            wfs_in_window = self.filtered_wfs[i,sum_start:sum_end]
            wfs_above_threshold_idx = np.where((wfs_in_window > threshold[i]))[0]
            
            if wfs_above_threshold_idx[0] > max_loc[i]: # exit if the first above threshold is after the max height
                break

            # rise time naive proxy: loc max - 1st loc that the waveform is above threshold
            timer = max_loc[i] - wfs_above_threshold_idx[0]    

            self.rise_time[i] = timer * 4 # now it becomes ns (for V1725, 1 sample = 4 ns)
        
        return self.rise_time