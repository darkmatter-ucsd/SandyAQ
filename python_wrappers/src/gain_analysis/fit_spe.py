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
        # self.plot = plot
        # self.show_plot = show_plot
        # self.save_plot = save_plot
        # self.output_name = output_name
        
        self.spe_position = np.nan
        self.spe_position_error = np.nan
        self.gain = np.nan
        self.gain_error = np.nan
        
        # for checking
        self.PE_rough_position = np.nan
        self.PE_rough_amplitude = np.nan
        
        # checked by eyes that 0.03 is good, but can do a more serious cut
        self.good_fit_threshold = 0.03
        self.distance_rough_guess = {45:0.22,
                                     46:0.25, 
                                     47:0.3, 
                                     48:0.5, 
                                     49:0.5, 
                                     50:0.6,
                                     51:0.7,
                                     52:0.8}
        
        
        self.guess_peaks(distance_rough_guess = self.distance_rough_guess[abs(self.bias_voltage)])
        if self.n_peaks >= 3:
            self.fit_peaks()
            mean_peak_width = self.get_mean_peak_width()
            
            if self.n_good_fit >= 3:
                self.get_gain(tolerance = mean_peak_width/5)
                
            
    def guess_peaks(self, distance_rough_guess = 0.5):

        self.bin_centers = self.area_bin_edges_Vns[:-1] + np.diff(self.area_bin_edges_Vns)/2
        bin_density = 10/len(self.bin_centers)
        # distance_rough_guess = 0.5 # distance between peaks in mV*ns

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
            
        input_impedance = 50 #ohm
        if sem < tolerance:
            self.spe_position = mean
            self.spe_position_error = sem
        
            self.gain = self.spe_position*1e-9/input_impedance/1.6e-19 # to V*s/Ohm -> I*s -> charge / 1e charge
            self.gain_error = self.spe_position_error*1e-9/input_impedance/1.6e-19 # to V*s/Ohm -> I*s -> charge / 1e charge
        
        # print(f"Mean, error: {self.spe_position},{self.spe_position_error}")
        # print(f"Gain: {self.gain}")
        return 
        
    # Let's create a function to model and create data 
    def gaussian_func(self, x, a, x0, sigma): 
        return a*np.exp(-(x-x0)**2/(2*sigma**2))