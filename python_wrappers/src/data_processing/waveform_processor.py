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
    def __init__(self,data_folder,length_per_event=1000,volt_per_adc=1/4096,polarity=True):
        self.data_folder = data_folder
        self.length_per_event = length_per_event
        self.volt_per_adc = volt_per_adc
        self.polarity = polarity
        self.wfs = None

    def set_data(self,data, in_adc = True):
        """
        Load data from a numpy array
        Supposed to be in ADC counts
        """
        self.wfs = data
        self.n_event = len(self.wfs)
        self.time = np.arange(0, self.length_per_event, 1) * 4
        if in_adc:
            self.raw_data_unit = "ADC"
        else:
            self.raw_data_unit = "V"

    def process_wfs(self,baseline_front=(0.1,0.3),baseline_back=(0.7,0.9),cutoff=10e6,fs=250e6):
        baseline_start_f = int(self.length_per_event * baseline_front[0])
        baseline_end_f = int(self.length_per_event * baseline_front[1])
        baseline_start_b = int(self.length_per_event * baseline_back[0])
        baseline_end_b = int(self.length_per_event * baseline_back[1])

        # baseline is calculated with raw waveform
        # unit: same as raw waveform
        self.baseline_mean_V = (np.mean(self.wfs[:,baseline_start_f:baseline_end_f],axis=1) + np.mean(self.wfs[:,baseline_start_b:baseline_end_b],axis=1))/2
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

    def get_area(self,sum_window=(0.4,0.6)):
        """
        Return the area of the waveform in the sum window
        Unit: V * ns
        """
        sum_start = int(self.length_per_event * sum_window[0])
        sum_end = int(self.length_per_event * sum_window[1])
        areas_Vsamples = np.sum(self.filtered_wfs[:,sum_start:sum_end],axis=1)
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