import os

import numpy as np
from tkinter import ttk
from PIL import Image
import matplotlib.pyplot as plt
from tempfile import gettempdir

from matplotlib.colors import LinearSegmentedColormap, hsv_to_rgb

TMP_FOLDER = gettempdir()  # '/tmp/' if sys.platform == 'linux' else 'C:\\Temp\\'

SATELLITE_CHANNELS = {
    'LT05': {
        '01': 'blue',
        '02': 'green',
        '03': 'red',
        '04': 'nir',
        '05': 'swir1',
        '07': 'swir2'
    },
    'LE07': {
        '01': 'blue',
        '02': 'green',
        '03': 'red',
        '04': 'nir',
        '05': 'swir1',
        '07': 'swir2'
    },
    'LC08': {
        '02': 'blue',
        '03': 'green',
        '04': 'red',
        '05': 'nir',
        '06': 'swir1',
        '07': 'swir2'
    }
}


class Mask:
    def __init__(self, x_min, x_max, x_step, y_min, y_max, y_step, array, channels):
        self.x_min = x_min
        self.x_max = x_max
        self.x_step = x_step
        self.y_min = y_min
        self.y_max = y_max
        self.y_step = y_step
        self.array = array
        self.channels = channels

    def get_value(self, x, y):
        x_ = np.maximum(np.minimum(((x - self.x_min) // self.x_step).astype(int), self.array.shape[0] - 1), 0)
        y_ = np.maximum(np.minimum(((y - self.y_min) // self.y_step).astype(int), self.array.shape[1] - 1), 0)
        return self.array.flatten()[x_ * self.array.shape[1] + y_]

    def update_array(self, array):
        self.array = array


def get_color(t, colors):
    return np.array([colors.transpose()[i].take(t) for i in range(3)]).transpose((1, 2, 0))


class AugmentedLabelFrame(ttk.LabelFrame):
    def __init__(self, master):
        super().__init__(master)
        self.name = None
        self.number = None
        self.image = None


def string_to_value(s, dtype='int_to_str', logger=None):
    try:
        if dtype == 'int_to_str':
            n = int(s)
            if not 0 < n < 8:
                raise ValueError('Unknown Channel')
            return str(n).zfill(2)
        elif dtype == 'float':
            return float(s)
        elif dtype == 'int':
            return int(s)
    except Exception as e:
        if logger is not None:
            logger.log(e)
        return None


def plot_hist2d(hist):
    array = hist.copy()
    array[0][:] = 0
    array[:][0] = 0

    array = array * 10000 // array.max()
    array[hist > 0] += 1
    array = array.astype(int)
    h, _ = np.histogram(array.flatten(), array.max() + 1)
    cdf = (h ** .5).cumsum()

    cmap = LinearSegmentedColormap.from_list('my_cmap',
                                             [hsv_to_rgb([0, 0, 0])] +
                                             [hsv_to_rgb([i / 1000, 1, 1]) for i in range(888, 20, -1)])
    fn = os.path.join(TMP_FOLDER, 'hist2d.png')
    plt.imsave(fn, cdf[array].transpose()[::-1, :], cmap=cmap)
    plt.close('all')
    return Image.open(fn).convert('RGB')


def plot_hist(x):
    q = x.flatten().copy()
    q = q[~np.isnan(q)]
    dpi = 100
    plt.figure(figsize=(380 / dpi, 300 / dpi), dpi=dpi)
    plt.hist(q, bins=256)
    fn = os.path.join(TMP_FOLDER, 'hist.png')
    plt.savefig(fn, figsize=(380 / dpi, 300 / dpi), dpi=dpi)
    plt.close('all')
    return Image.open(fn).convert('RGB')
