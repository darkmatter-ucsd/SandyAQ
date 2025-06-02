from scipy.optimize import curve_fit
from scipy.signal import find_peaks
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import os
import sys

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,os.path.join(current_dir,"../"))
import common.config_reader as common_config_reader
from common.logger import setup_logger

logger = setup_logger(os.path.splitext(os.path.basename(__file__))[0])

class FitSPE:  
    def __init__(self, bias_voltage, area_hist_count_Vns, area_bin_edges_Vns):

        self.amp_list = []
        self.mu_list = []
        self.sig_list = []
        self.line_x = []
        self.line_y = []
        self.mu_err_list = []
        
        self.bias_voltage = bias_voltage
        self.area_hist_count_Vns = area_hist_count_Vns
        self.area_bin_edges_Vns = area_bin_edges_Vns
        
        self.spe_position = np.nan
        self.spe_position_error = np.nan
        self.gain = np.nan
        self.gain_error = np.nan
        
        # for checking
        self.PE_rough_position = np.nan
        self.PE_rough_amplitude = np.nan

        ###########
        self.read_config()
        self.distance_rough_guess = self.distance_rough_guess_dict[abs(self.bias_voltage)]
        self.guess_peaks(distance_rough_guess = self.distance_rough_guess)

        if self.n_peaks >= 2:
            self.fit_peaks()
            self.mean_peak_width = self.get_mean_peak_width()
            
            if self.n_good_fit >= 3:
                self.get_gain(tolerance = self.mean_peak_width/5)

            elif self.n_good_fit >= 1:
                self.get_rough_gain()

            else:
                logger.warning("Not enough good peaks to calculate gain")
        else:
            logger.warning("Not enough peaks to determine the finger fit")




    def read_config(self):
        '''Read the config file and set the parameters'''
        # This function can be used to read the config file and set the parameters

        self.common_cfg_reader = common_config_reader.ConfigurationReader()
        self.fit_config = self.common_cfg_reader.get_data_processing_config()
        
        self.good_fit_threshold = float(self.fit_config.get('FIT_SPE_SETTINGS', 'good_fit_threshold'))  
        
        self._input_impedance = float(self.fit_config.get('FIT_SPE_SETTINGS', 'input_impedance_Ohm'))  
        
        tmp = self.fit_config.get('FIT_SPE_SETTINGS', 'spe_position_guess')
        tmp = tmp.split(' ')
        self.distance_rough_guess_list = tmp

        tmp = self.fit_config.get('FIT_SPE_SETTINGS', 'spe_bias_voltage')
        tmp = tmp.split(' ')
        self.distance_rough_guess_Vbias_list = tmp
        
        # create a dictionary for the distance_rough_guess
        self.distance_rough_guess_dict = {}
        for i in range(len(self.distance_rough_guess_list)):
            self.distance_rough_guess_dict[float(self.distance_rough_guess_Vbias_list[i])] = float(self.distance_rough_guess_list[i])
            
    def guess_peaks(self, distance_rough_guess = 0.5):

        self.bin_centers = self.area_bin_edges_Vns[:-1] + np.diff(self.area_bin_edges_Vns)/2
        bin_density = 10/len(self.bin_centers)

        self.peaks, _ = find_peaks(self.area_hist_count_Vns, height=5, 
                              distance=distance_rough_guess/bin_density)
        self.n_peaks = len(self.peaks)
        return
        
    def fit_peaks(self):
        
        peaks = self.peaks
        
        # if self.n_peaks > 1:
        
        PE_rough_position = self.bin_centers[peaks] # unit: V*ns
        # PE_rough_half_width = np.median(np.diff(PE_rough_position))/2
        PE_rough_half_width = np.min(np.diff(PE_rough_position))
        PE_rough_amplitude = self.area_hist_count_Vns[peaks]
        PE_half_width_index = int(np.median(np.diff(peaks))/2) # PE width in index
        
        self.PE_rough_position = PE_rough_position
        self.PE_rough_amplitude = PE_rough_amplitude
        

        # if self.plot:
        #     plt.figure(figsize=(10,6))
        #     plt.xlabel("Area [V*ns]")
        #     plt.ylabel("Counts")
        #     plt.title("Area Histogram")
        #     plt.plot(self.bin_centers, self.area_hist_count_Vns, color='black', label='Data',zorder=0)
        #     plt.plot(self.bin_centers[peaks], self.area_hist_count_Vns[peaks], "x", label='Identified Peaks')
        
        # Executing curve_fit on noisy data 
        for i, peak in enumerate(peaks[0:8]):
            min_x = int(peak-PE_half_width_index)
            max_x = int(peak+PE_half_width_index)
            compensation_length_min = 0
            compensation_length_max = 0
            len_bin_centers = len(self.bin_centers)
            if min_x < 0:
                # after setting min_x to 0 so that indexing not 
                # out of bound, but then the arrays size will be
                # different, so need to use the compensation for
                # line_x and line_y
                compensation_length_min = 0 - min_x
                min_x = 0
            elif max_x > len_bin_centers:
                # after setting min_x to 0 so that indexing not 
                # out of bound, but then the arrays size will be
                # different, so need to use the compensation for
                # line_x and line_y
                compensation_length_max = max_x - len_bin_centers
                max_x = len_bin_centers
                
            try:
                (amp,mu,sig), pcov = curve_fit(self.gaussian_func, 
                                            self.bin_centers[min_x:max_x], 
                                            self.area_hist_count_Vns[min_x:max_x], 
                                            p0=[PE_rough_amplitude[i], 
                                                PE_rough_position[i], 
                                                PE_rough_half_width])
                perr = np.sqrt(np.diag(pcov))
                
            except RuntimeError as e:
                logger.warning(e)
                pass
            except:
                raise Exception
            else:
                self.amp_list.append(amp)
                self.mu_list.append(mu)
                if sig<0: # somehow abs doesn't work
                    self.sig_list.append(-sig)
                else:
                    self.sig_list.append(sig)
                self.mu_err_list.append(perr[1])
                
                if compensation_length_min > 0:
                    compensation = np.zeros(int(compensation_length_min), dtype = self.bin_centers[0])
                    line_x = np.concatenate((compensation,self.bin_centers[min_x:max_x]))
                elif compensation_length_max > 0:
                    compensation = np.ones(int(compensation_length_max), dtype = self.bin_centers[0])*self.bin_centers[-1]
                    line_x = np.concatenate((self.bin_centers[min_x:max_x], compensation))
                else:
                    line_x = self.bin_centers[min_x:max_x]

                ym = self.gaussian_func(line_x, amp, mu, sig) 
                
                self.line_x.append(line_x)
                self.line_y.append(ym)

        peak_diff_media = np.median(np.diff(self.mu_list))
                
        # if self.plot:

        #     handles, labels = plt.gca().get_legend_handles_labels()

        #     custom_lines = [Line2D([0], [0], color='r'),
        #                     Line2D([0], [0], color='r',alpha=0)]

        #     handles += custom_lines
        #     if len(self.mu_list) > 0:
        #         labels += ['Fit: ',f'First peak mean: {self.mu_list[0]:.2f} mV*ns\nFirst peak sigma: {sig_list[0]:.2f} mV*ns\n']
        #     if len(self.mu_list) > 1:
        #         labels += ['Second peak mean: {mu_list[1]:.2f} mV*ns\nSecond peak sigma: {sig_list[1]:.2f} mV*ns\nPeak diff median: {peak_diff_media:.2f}']

        #     # Update legend with custom lines and labels
        #     plt.legend(handles=handles, labels=labels,loc='upper right')
        #     # plt.legend()
        #     if self.show_plot:
        #         plt.show()
        #     else:
        #         plt.close()
        #     if self.save_plot:
        #         plt.savefig(self.output_name+'SPE_fit.png')

        self.amp_list = np.array(self.amp_list)
        self.mu_list = np.array(self.mu_list)
        self.sig_list = np.array(self.sig_list)
        # self.sig_list = np.abs(np.array((self.sig_list.copy())))
        self.mu_err_list = np.array(self.mu_err_list)
        self.line_x = np.array(self.line_x, dtype=object) ## FIXME: the dimension of linex might not be the same, max_x out of range
        self.line_y = np.array(self.line_y, dtype=object)
        
        self.n_good_fit = len(self.mu_err_list[self.mu_err_list < self.good_fit_threshold])
        # good peaks are true
        self.good_peaks = self.mu_err_list < self.good_fit_threshold
        
        # if self.n_peaks > 1:
        #     self.get_gain()

        #FIXME: add a value evaluate the founded peaks (prominence, width, fit etc.)

        return
    
    def get_mean_peak_width(self):
        '''Return the resolution from all well-fitted peaks
        param: None
        return: resolution (float)
                error (float)
        '''
        # calculated resolution for only the good enough fit 
        
        sig_list = self.sig_list[self.good_peaks]
        
        mean = np.mean(sig_list) # mean of gain
        sem = np.std(sig_list, ddof=1) / np.sqrt(np.size(sig_list)) # Standard error of the mean
        
        # FIXME: write this into a function and double check the numbers
        # input_impedance = 50 #ohm
        # self.resolution = mean*1e-12/input_impedance/1.6e-19 # to V*s/Ohm -> I*s -> charge / 1e charge
        # self.resolution_error = sem*1e-12/input_impedance/1.6e-19 # to V*s/Ohm -> I*s -> charge / 1e charge

        return mean
    
    def get_gain(self, tolerance = 0.03):
        '''Return the gain calculated from the SPE fit
        param: None
        return: gain (float)
                confidence (float)
        '''
        
        # prevent the case where all good peaks were
        # exactly separated by a bad peak
        # if self.n_good_fit <= len(self.mu_list)-self.n_good_fit+2: # if the number of good peak is less than bad peaks
        consecutive_good_peaks = 0
        max_n_consective_good_peaks = 0
        for i in self.good_peaks:
            if i == True:
                consecutive_good_peaks += 1
                if consecutive_good_peaks > max_n_consective_good_peaks:
                    max_n_consective_good_peaks = consecutive_good_peaks
            else:
                consecutive_good_peaks = 0
        
        if (max_n_consective_good_peaks < len(self.mu_list) - self.n_good_fit) or (max_n_consective_good_peaks<3):
            self.get_rough_gain()
            logger.warning("Not enough good peaks to calculate gain")
            return
                    
        
        # calculated difference of all peaks with good enough fit 
        gain_list = np.diff(self.mu_list[self.good_peaks])
        
        # if the fit error of first peak is also good, 
        # it might be the SPE peak, include it to the SPE list
        # if self.mu_err_list[0] < self.good_fit_threshold:
        #     gain_list = np.append([self.mu_list[0]],gain_list)
        # turns out this introduce error to the gain
            
        # sort in ascending order the SPE guess
        # give a bias on smallest guess (more likely to have 
        # skipped a peak than including too many peak)
        gain_list = sorted(gain_list)
        
        mean = np.mean(gain_list) # mean of gain
        sem = np.std(gain_list, ddof=1) / np.sqrt(np.size(gain_list)) # Standard error of the mean
        
        # sem = 1.0
        maximum_niteration = 3
        count = 0
        
        # Cut requirement: 
        # at least 4 fitted peaks
        while (len(gain_list) > 3) & (sem > tolerance) & (count < maximum_niteration):
            # print("Entring optimization loop")
            # remove the largest SPE guess
            gain_list = gain_list[:-1] # rmb gain_list is sorted
            
            # update measurement
            mean = np.mean(gain_list)
            sem = np.std(gain_list, ddof=1) / np.sqrt(np.size(gain_list)) # Standard error of the mean
            # rel_sem = np.std(gain_list, ddof=1) / np.sqrt(np.size(gain_list)) / np.mean(gain_list) # Relative error of the standard error of the mean
            # distance_from_mean = np.abs(gain_list - mean)
            # print(distance_from_mean)
            
            # tmp_gain_list = gain_list[distance_from_mean < 1.5*sem]
            # if (len(tmp_gain_list) < 3): 
            #     break
            # else:
            #     gain_list = tmp_gain_list
            
            # print(sem)
            
            count += 1
            
        if sem < tolerance:
            self.spe_position = mean
            self.spe_position_error = sem
        
            self.gain = self.spe_position*1e-9/self._input_impedance/1.6e-19 # to V*s/Ohm -> I*s -> charge / 1e charge
            self.gain_error = self.spe_position_error*1e-9/self._input_impedance/1.6e-19 # to V*s/Ohm -> I*s -> charge / 1e charge
        else: 
            self.get_rough_gain()

        
        # print(f"Mean, error: {self.spe_position},{self.spe_position_error}")
        # print(f"Gain: {self.gain}")
        return 

    def get_rough_gain(self):  
        logger.warning("Cannot find a good peak to calculate gain, using rough guess")

        '''Return the gain calculated from the maximum peak
        param: error (float) - the error of the gain
        return: gain (float)
                confidence (float)
        '''  

        # self.amp_list = np.array(self.amp_list)
        # self.mu_list = np.array(self.mu_list)
        # self.sig_list = np.array(self.sig_list)

        # good peaks are true
        # self.good_peaks = self.mu_err_list < self.good_fit_threshold

        # if the largest peak is good fit & < than rough position, use it as the SPE peak
        max_peak_index = np.argmax(self.amp_list)
        if (self.good_peaks[max_peak_index]) and (self.mu_list[max_peak_index] < 1.7*self.distance_rough_guess):
            self.spe_position = self.mu_list[max_peak_index]
            self.spe_position_error = self.sig_list[max_peak_index]
    
            self.gain = self.spe_position*1e-9/self._input_impedance/1.6e-19 # to V*s/Ohm -> I*s -> charge / 1e charge
            self.gain_error = self.spe_position_error*1e-9/self._input_impedance/1.6e-19 # to V*s/Ohm -> I*s -> charge / 1e charge
        else:
            logger.warning("No rough guess found, setting gain to NaN")
    
        return

    # Let's create a function to model and create data 
    def gaussian_func(self, x, a, x0, sigma): 
        return a*np.exp(-(x-x0)**2/(2*sigma**2))