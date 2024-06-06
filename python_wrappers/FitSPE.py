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
                
                amp_list.append(amp)
                mu_list.append(mu)
                sig_list.append(sig)
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
            labels += ['Fit: ',f'First peak mean: {mu_list[0]:.2f} mV*ns\nFirst peak sigma: {sig_list[0]:.2f} mV*ns\nSecond peak mean: {mu_list[1]:.2f} mV*ns\nSecond peak sigma: {sig_list[1]:.2f} mV*ns\nPeak diff median: {peak_diff_media:.2f}']

            # Update legend with custom lines and labels
            plt.legend(handles=handles, labels=labels,loc='upper right')
            # plt.legend()
            if show_plot:
                plt.show()
            else:
                plt.close()
            if save_plot:
                plt.savefig(output_name+'SPE_fit.png')

        self.amp_list = amp_list
        self.mu_list = mu_list
        self.sig_list = sig_list
        self.line_x = np.array(line_x) ## FIXME: the dimension of linex might not be the same, max_x out of range
        self.line_y = np.array(line_y)


    # Let's create a function to model and create data 
    def gaussian_func(self, x, a, x0, sigma): 
        return a*np.exp(-(x-x0)**2/(2*sigma**2))