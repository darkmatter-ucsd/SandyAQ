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
        self.event_number = len(self.wfs)
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
        self.baseline = (np.mean(self.wfs[:,baseline_start_f:baseline_end_f],axis=1) + np.mean(self.wfs[:,baseline_start_b:baseline_end_b],axis=1))/2
        self.baseline_rms = np.std(self.wfs[:,baseline_start_f:baseline_end_f],axis=1)
        baseline = self.baseline.repeat(self.length_per_event).reshape(self.event_number,self.length_per_event)
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
        for i in np.random.choice(self.event_number,n):
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
        Unit: mV * ns
        """
        sum_start = int(self.length_per_event * sum_window[0])
        sum_end = int(self.length_per_event * sum_window[1])
        self.areas = np.sum(self.filtered_wfs[:,sum_start:sum_end],axis=1) # unit: mV
        self.areas *= 4 # now it becomes mV * ns
        if not self.polarity:
            self.areas = -self.areas
        return self.areas
    
    def get_height(self, search_window =(0,4,0.6)):
        """
        Return the height of the waveform in the search window
        Unit: mV
        """
        sum_start = int(self.length_per_event * search_window[0])
        sum_end = int(self.length_per_event * search_window[1])
        self.heights = np.max(self.filtered_wfs[:,sum_start:sum_end],axis=1) # unit: mV
        self.heights *= 1000 # now it becomes mV 
        if not self.polarity:
            self.heights = -self.heights
        return self.heights