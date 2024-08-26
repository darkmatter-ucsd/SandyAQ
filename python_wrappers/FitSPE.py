from scipy.optimize import curve_fit
from scipy.signal import find_peaks
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

class fit_SPE:  
    def __init__(self, bias_voltage, n_hist, bin_edges, plot = True, 
                 show_plot=False, save_plot=True, output_name = ''):

        self.amp_list = []
        self.mu_list = []
        self.sig_list = []
        self.line_x = []
        self.line_y = []
        self.mu_err_list = []
        
        self.bias_voltage = bias_voltage
        self.n_hist = n_hist
        self.bin_edges = bin_edges
        self.plot = plot
        self.show_plot = show_plot
        self.save_plot = save_plot
        self.output_name = output_name
        
        self.spe_position = np.nan
        self.spe_position_error = np.nan
        self.gain = np.nan
        self.gain_error = np.nan
        
        # checked by eyes that 0.03 is good, but can do a more serious cut
        self.good_fit_threshold = 0.03
        self.distance_rough_guess = {46:0.25, 
                                     47:0.3, 
                                     48:0.5, 
                                     49:0.5, 
                                     50:0.6,
                                     51:0.7,
                                     52:0.8}
        
        
        self.guess_peaks(distance_rough_guess = self.distance_rough_guess[abs(self.bias_voltage)])
        if self.n_peaks > 1:
            self.fit_peaks()
            if self.n_good_fit >= 3:
                self.get_gain()
            
    def guess_peaks(self, distance_rough_guess = 0.5):

        self.bin_centers = self.bin_edges[:-1] + np.diff(self.bin_edges)/2
        bin_density = 10/len(self.bin_centers)
        # distance_rough_guess = 0.5 # distance between peaks in mV*ns

        self.peaks, _ = find_peaks(self.n_hist, height=5, 
                              distance=distance_rough_guess/bin_density)
        self.n_peaks = len(self.peaks)
        return
        
    def fit_peaks(self):
        
        peaks = self.peaks
        
        # if self.n_peaks > 1:
        
        PE_rough_position = self.bin_centers[peaks] # unit: V*ns
        PE_rough_half_width = np.median(np.diff(PE_rough_position))/2
        PE_rough_amplitude = self.n_hist[peaks]
        PE_half_width_index = int(np.median(np.diff(peaks))/2) # PE width in index

        # if self.plot:
        #     plt.figure(figsize=(10,6))
        #     plt.xlabel("Area [V*ns]")
        #     plt.ylabel("Counts")
        #     plt.title("Area Histogram")
        #     plt.plot(self.bin_centers, self.n_hist, color='black', label='Data',zorder=0)
        #     plt.plot(self.bin_centers[peaks], self.n_hist[peaks], "x", label='Identified Peaks')
        
        # Executing curve_fit on noisy data 
        for i, peak in enumerate(peaks[0:8]):
            try:
                min_x = int(peak-PE_half_width_index)
                max_x = int(peak+PE_half_width_index)

                (amp,mu,sig), pcov = curve_fit(self.gaussian_func, 
                                            self.bin_centers[min_x:max_x], 
                                            self.n_hist[min_x:max_x], 
                                            p0=[PE_rough_amplitude[i], 
                                                PE_rough_position[i], 
                                                PE_rough_half_width])
                
                perr = np.sqrt(np.diag(pcov))
                
                self.amp_list.append(amp)
                self.mu_list.append(mu)
                self.sig_list.append(sig)
                self.mu_err_list.append(perr[1])

                ym = self.gaussian_func(self.bin_centers[min_x:max_x], amp, mu, sig) 

                self.line_x.append(self.bin_centers[min_x:max_x])
                self.line_y.append(ym)

                # if self.plot:
                    
                #     plt.plot(self.bin_centers[min_x:max_x], ym ,zorder=10, color='r') 
                #     # plt.text(0.9,0.9,f"")

            except:
                continue
        
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
        self.mu_err_list = np.array(self.mu_err_list)
        self.line_x = np.array(self.line_x, dtype=object) ## FIXME: the dimension of linex might not be the same, max_x out of range
        self.line_y = np.array(self.line_y, dtype=object)
        
        self.n_good_fit = len(self.mu_err_list[self.mu_err_list < self.good_fit_threshold])
        
        # if self.n_peaks > 1:
        #     self.get_gain()

        #FIXME: add a value evaluate the founded peaks (prominence, width, fit etc.)

        return
    
    def get_gain(self):
        '''Return the gain calculated from the SPE fit
        param: None
        return: gain (float)
                confidence (float)
        '''
        # calculated difference of all peaks with good enough fit 
        gain_list = np.diff(self.mu_list[self.mu_err_list < self.good_fit_threshold ])
        
        # if the fit error of first peak is also good, 
        # it might be the SPE peak, include it to the SPE list
        if self.mu_err_list[0] < self.good_fit_threshold:
            gain_list = np.append([self.mu_list[0]],gain_list)
            
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
        while (len(gain_list) > 3) & (sem > self.good_fit_threshold) & (count < maximum_niteration):
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
            
        if sem < self.good_fit_threshold:
            self.spe_position = mean
            self.spe_position_error = sem
        
        input_impedance = 50 #ohm
        self.gain = self.spe_position*1e-12/input_impedance/1.6e-19 # to V*s/Ohm -> I*s -> charge / 1e charge
        self.gain_error = self.spe_position_error*1e-12/input_impedance/1.6e-19 # to V*s/Ohm -> I*s -> charge / 1e charge
        
        # print(f"Mean, error: {self.spe_position},{self.spe_position_error}")
        # print(f"Gain: {self.gain}")
        return 
        
        
        
        
    # Let's create a function to model and create data 
    def gaussian_func(self, x, a, x0, sigma): 
        return a*np.exp(-(x-x0)**2/(2*sigma**2))