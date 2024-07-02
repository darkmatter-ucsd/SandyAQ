from scipy.optimize import curve_fit
from scipy.signal import find_peaks
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

class FitSPE:  
    def __init__(self, n_hist, bin_edges, plot = True, show_plot=False, save_plot=True, output_name = ''):

        amp_list = []
        mu_list = []
        sig_list = []
        line_x = []
        line_y = []
        mu_err_list = []

        bin_centers = bin_edges[:-1] + np.diff(bin_edges)/2
        bin_density = 10/len(bin_centers)
        distance_rough_guess = 0.5 # distance between peaks in mV*ns

        peaks, _ = find_peaks(n_hist, height=5, distance=distance_rough_guess/bin_density)

        PE_rough_position = bin_centers[peaks] # unit: mV*ns
        PE_rough_half_width = np.median(np.diff(PE_rough_position))/2
        PE_rough_amplitude = n_hist[peaks]
        PE_half_width_index = int(np.median(np.diff(peaks))/2) # PE width in index

        if plot:
            plt.figure(figsize=(10,6))
            plt.xlabel("Area [mV*ns]")
            plt.ylabel("Counts")
            plt.title("Area Histogram")
            plt.plot(bin_centers, n_hist, color='black', label='Data',zorder=0)
            plt.plot(bin_centers[peaks], n_hist[peaks], "x", label='Identified Peaks')
            

        
        # Executing curve_fit on noisy data 
        for i, peak in enumerate(peaks[0:8]):
            try:
                min_x = int(peak-PE_half_width_index)
                max_x = int(peak+PE_half_width_index)

                (amp,mu,sig), pcov = curve_fit(self.gaussian_func, 
                                            bin_centers[min_x:max_x], 
                                            n_hist[min_x:max_x], 
                                            p0=[PE_rough_amplitude[i], 
                                                PE_rough_position[i], 
                                                PE_rough_half_width])
                
                perr = np.sqrt(np.diag(pcov))
                
                amp_list.append(amp)
                mu_list.append(mu)
                sig_list.append(sig)
                mu_err_list.append(perr[1])

                ym = self.gaussian_func(bin_centers[min_x:max_x], amp, mu, sig) 

                line_x.append(bin_centers[min_x:max_x])
                line_y.append(ym)

                if plot:
                    
                    plt.plot(bin_centers[min_x:max_x], ym ,zorder=10, color='r') 
                    # plt.text(0.9,0.9,f"")


            except:
                # print(f"Failed to fit peak {i}")
                continue
        
        peak_diff_media = np.median(np.diff(mu_list))
            
                
        if plot:

            handles, labels = plt.gca().get_legend_handles_labels()

            custom_lines = [Line2D([0], [0], color='r'),
                            Line2D([0], [0], color='r',alpha=0)]

            handles += custom_lines
            if len(mu_list) > 0:
                labels += ['Fit: ',f'First peak mean: {mu_list[0]:.2f} mV*ns\nFirst peak sigma: {sig_list[0]:.2f} mV*ns\n']
            if len(mu_list) > 1:
                labels += ['Second peak mean: {mu_list[1]:.2f} mV*ns\nSecond peak sigma: {sig_list[1]:.2f} mV*ns\nPeak diff median: {peak_diff_media:.2f}']

            # Update legend with custom lines and labels
            plt.legend(handles=handles, labels=labels,loc='upper right')
            # plt.legend()
            if show_plot:
                plt.show()
            else:
                plt.close()
            if save_plot:
                plt.savefig(output_name+'SPE_fit.png')

        self.amp_list = np.array(amp_list)
        self.mu_list = np.array(mu_list)
        self.sig_list = np.array(sig_list)
        self.mu_err_list = np.array(mu_err_list)
        self.line_x = np.array(line_x) ## FIXME: the dimension of linex might not be the same, max_x out of range
        self.line_y = np.array(line_y)

        #FIXME: add a value evaluate the founded peaks (prominence, width, fit etc.)

    def get_gain(self):
        '''Return the gain calculated from the SPE fit
        param: None
        return: gain (float)
                confidence (float)
        '''
        # calculated difference of all peaks with good enough fit 
        # checked by eyes that 0.03 is good, but can do a more serious cut
        gain_list = np.diff(self.mu_list[self.mu_err_list<0.03])
        np.append([self.mu_list[0]],gain_list)
        sorted_gain_list = sorted(gain_list)
        print(sorted_gain_list) #FIXME: should have weighted mean that favour smaller values
        
        input_impedance = 50 #ohm
        sem = 1.0
        maximum_niteration = 4
        count = 0
        while (len(gain_list) >= 3) & (sem > 0.03) & (count < maximum_niteration):
            mean = np.mean(gain_list) # mean of gain
            sem = np.std(gain_list, ddof=1) / np.sqrt(np.size(gain_list)) # Standard error of the mean
            rel_sem = np.std(gain_list, ddof=1) / np.sqrt(np.size(gain_list)) / np.mean(gain_list) # Relative error of the standard error of the mean
            distance_from_mean = np.abs(gain_list - mean)
            print(distance_from_mean)
            
            tmp_gain_list = gain_list[distance_from_mean < 1.5*sem]
            if (len(tmp_gain_list) < 3): 
                break
            else:
                gain_list = tmp_gain_list
            
            print(sem)
            
            count += 1
        
        self.mean_gain = np.mean(gain_list)/input_impedance*1e-12/1.6e-19
        self.sem = sem
        return self.sem
        
        
        
        
    # Let's create a function to model and create data 
    def gaussian_func(self, x, a, x0, sigma): 
        return a*np.exp(-(x-x0)**2/(2*sigma**2))