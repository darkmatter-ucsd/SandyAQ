'''Script with common usefull tools and style'''

import numpy as np
# from tqdm.notebook import tqdm
from matplotlib.colors import LogNorm
import matplotlib.pyplot as plt
from time import strftime
import pandas as pd
import datetime
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from matplotlib.patches import Circle
import matplotlib.font_manager as font_manager
from matplotlib import mathtext
import os
import glob
from cycler import cycler

dirname = os.path.dirname(__file__)
font_dirs = [os.path.join(dirname, 'fonts')]
font_files = font_manager.findSystemFonts(fontpaths=font_dirs)

for font_file in font_files:
    font_manager.fontManager.addfont(font_file)

W = 12 
params = {
    # figure
    'figure.figsize': (W, W/(4/3)),
    'figure.facecolor': 'white',  # make figure background white
    # axes
    'axes.labelsize': 20,
    'axes.linewidth': 2,
    'axes.titlesize': 20,
    'axes.grid.which': 'both',  # gridlines at major, minor or both ticks
    'axes.labelpad': 10,
    # errorbar
    'errorbar.capsize': 4,
    # font
    'text.usetex': False,
    'font.size': 18,
    'font.family': 'Times New Roman',
    # 'font.serif': 'computer modern roman',
    # 'pgf.texsystem': 'pdflatex',
    # 'pgf.preamble': '\n'.join([
    #      r'\usepackage[utf8x]{inputenc}',
    #      r'\usepackage[T1]{fontenc}',
    #      r'\usepackage{cmbright}',
    # ]),
    # color
    'image.cmap': 'viridis',
    # legend
    'savefig.bbox': 'tight',
    'legend.fontsize': 18,
    'legend.frameon': False,
    'legend.numpoints': 1,  # only one marker in legend
    # line
    'lines.linestyle': 'solid',
    'lines.linewidth': 2,
    'lines.markeredgewidth': 1,
    'lines.markersize': 1,
    # text
    'mathtext.default': 'regular',
    'savefig.bbox': 'tight',
    'savefig.transparent': False,
    # tick
    'xtick.top': True,  # draw ticks on the top side
    'xtick.direction': 'in',
    'xtick.labelsize': 20,
    'xtick.major.size': 8,
    'xtick.major.width': 1,
    'xtick.minor.size': 4,
    'xtick.minor.visible': True,
    'xtick.minor.width': 1,

    'ytick.right': True,  # draw ticks on the right side
    'ytick.direction': 'in',
    'ytick.labelsize': 20,
    'ytick.major.size': 6,
    'ytick.major.width': 1,
    'ytick.minor.size': 3,
    'ytick.minor.visible': True,
    'ytick.minor.width': 1,
    # GRIDS
    'grid.linestyle': '--',  ## dashed
    'mathtext.default': 'regular',
}

# from https://gist.github.com/thriveth/8560036
default_cycler = (cycler(color=[f'#{c}' for c in ['377eb8', 'ff7f00', '4daf4a', 'f781bf','a65628', '984ea3', '999999', 'e41a1c', 'dede00']]
                        ) +
                  cycler(marker=['o', 's', 'v', '^', 'D', 'P', '>', 'x', 'h']))

if __name__ == '__main__':
    plt.rcParams.update({'axes.prop_cycle':default_cycler})
    plt.rcParams.update(params)

#mathtext.FontConstantsBase.sup1 = 0.4

def set_aspect_ratio(aspect_ratio):
    '''
    width/height
    '''
    plt.rcParams.update({'figure.figsize': (W, W/aspect_ratio)})
    plt.rcParams.update({'figure.figsize': (W, W/aspect_ratio)})
    # plt.rcParams.update(params)


# Useful functions
def plt_config(title=None, xbounds=None, ybounds=None, xlabel=None,
               ylabel=None, colorbar=False, sci=False, yscale=None, xscale=None):
    if isinstance(sci, str):
        plt.ticklabel_format(style='sci', axis=sci, scilimits=(0, 0))

    if title != None:   plt.title(title)
    if xbounds != None: plt.xlim(xbounds)
    if ybounds != None: plt.ylim(ybounds)
    if xlabel != None:  plt.xlabel(xlabel)
    if ylabel != None:  plt.ylabel(ylabel)
    if xscale != None:  plt.xscale(xscale)
    if yscale != None:  plt.yscale(yscale)

    if isinstance(colorbar, str):
        plt.colorbar().set_label(label=colorbar, size=12, weight=None)
    elif colorbar:
        plt.colorbar(label='$Number\ of\ Entries$')
    else:
        pass


def annotation_line(ax,
                    xmin,
                    xmax,
                    xtext,
                    y,
                    text,
                    ytext=0,
                    linecolor='black',
                    linewidth=1,
                    fontsize=20):
    ax.annotate('', xy=(xmin, y), xytext=(xmax, y), xycoords='data', textcoords='data',
                arrowprops={'arrowstyle': '|-|', 'color': linecolor, 'linewidth': linewidth})
    ax.annotate('', xy=(xmin, y), xytext=(xmax, y), xycoords='data', textcoords='data',
                arrowprops={'arrowstyle': '<->', 'color': linecolor, 'linewidth': linewidth})

    xcenter = xtext  # xmin + (xmax-xmin)/2
    if ytext == 0:
        ytext = y + (ax.get_ylim()[1] - ax.get_ylim()[0]) / 20

    ax.annotate(text, xy=(xcenter, ytext), ha='center', va='center', fontsize=fontsize)
