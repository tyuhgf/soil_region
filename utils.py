import numpy as np
from tkinter import ttk
from PIL import Image
import matplotlib.pyplot as plt
import sys

from matplotlib.colors import LinearSegmentedColormap, hsv_to_rgb

COLORS = np.array([[0, 0, 0], [255, 0, 0], [0, 255, 0], [0, 0, 255], [0, 255, 255], [255, 0, 255], [255, 255, 0]])
N_REGIONS = 5

TMP_FOLDER = '/tmp/' if sys.platform == 'linux' else 'C:\\Temp\\'


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


def get_color(t):
    return np.array([COLORS.transpose()[i].take(t) for i in range(3)]).transpose((1, 2, 0))


class NamedFrame(ttk.Frame):
    def __init__(self, master, name=None, number=0):
        super().__init__(master)
        self.name = name
        self.number = number
        self.pack()


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
    plt.imsave(TMP_FOLDER + 'hist2d.png', cdf[array].transpose()[::-1, :], cmap=cmap)
    plt.close('all')
    return Image.open(TMP_FOLDER + 'hist2d.png').convert('RGB')


def plot_hist(x):
    q = x.flatten().copy()
    q = q[~np.isnan(q)]
    dpi = 100
    plt.figure(figsize=(380/dpi, 300/dpi), dpi=dpi)
    plt.hist(q, bins=1000)
    plt.savefig('/tmp/hist.png', figsize=(380/dpi, 300/dpi), dpi=dpi)
    plt.close('all')
    return Image.open(TMP_FOLDER + 'hist.png').convert('RGB')
